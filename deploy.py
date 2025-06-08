#!/usr/bin/env python3
import argparse
import os
import pathlib
import subprocess

import graphviz # graphviz package
import hcl2 # python-hcl2 package

class Deployment:
    def __init__(self, args):
        self.args = args
        self.args.omit = set(self.args.omit)
        self.args.prune = set(self.args.prune)
        self.args.stack = set(self.args.stack)
        self.project_root = self.get_project_root()
        self.env_root = self.get_env_root()

    def get_stack_map(self):
        stacks = []

        def find_files(filename, search_path=self.env_root):
            path = pathlib.Path(search_path)
            return list(path.rglob(filename))

        results = find_files("stack.tm.hcl")

        for stackfile in results:
            with open(stackfile, "r") as f:
                try:
                    hcl_data = hcl2.load(f)
                except Exception:
                    print (f"In {stackfile}")
                    raise
                stack_data = hcl_data.get("stack")
                if stack_data:
                    stack = stack_data[0]
                    stack["directory"] = os.path.dirname(stackfile)
                    stacks.append(stack)

        stack_map = {}
        for stack in stacks:
            tags = set(stack.get("tags", []))
            for tag in tags:
                stack_map[tag] = stack
                # first tag is name
                break

        return stack_map

    def setup(self):
        args = self.args
        stacks = args.stack
        omits = args.omit
        prunes = args.prune

        stack_map = self.get_stack_map()

        for stack in stack_map.values():
            tags = set(stack.get("tags", []))
            stack_name = None

            if stack_name:
                for tag in tags:
                    if tag.startswith("workspace."):
                        if tag[len("workspace."):] != self.args.workspace:
                            omits.add(stack_name)
                            print(f"Omitting {stack_name}: foreign ws {tag}")

        if not stacks:
            stacks = set(stack_map.keys())
        else:
            stacks = set(stacks)

        omits = set(omits)
        prunes = set(prunes)

        if self.args.nodeps:
            pruned_deps = set(stacks)
            pruned_edges = set()
            for stack in stacks:
                pruned_edges.add(("__root__", stack))
        else:
            pruned_edges = self.find_edges(stack_map, stacks, prunes)
            pruned_deps = self.flatten_edges(pruned_edges)

        final_deps = pruned_deps.difference(omits)

        command = args.command

        var_files = []
        cwd = os.getcwd()
        for var_file in args.var_file:
            if os.path.isabs(var_file):
               var_files.append(var_file)
            else:
                var_files.append(os.path.join(cwd, var_file))


        return dict(
            command = command,
            stacks = stacks,
            omits = omits,
            prunes = prunes,
            pruned_edges = pruned_edges,
            pruned_deps = pruned_deps,
            final_deps = final_deps,
            workspace = args.workspace,
            unattended = args.unattended,
            stack_map = stack_map,
            parallel = args.parallel,
            noinit = args.noinit,
            var_files = var_files,
            backend_bucket = args.backend_bucket
        )

    def get_project_root(self):
        gitdir = find_directory_upwards(".git")
        if not gitdir:
            raise ValueError(".git could not be found in parents")
        return os.path.dirname(gitdir)

    def get_env_root(self):
        project_root = self.get_project_root()
        return os.path.abspath(os.path.join(project_root, self.args.env))

    def flatten_edges(self, edges):
        flattened = set()
        for src, dst in edges:
            if src != "__root__":
                flattened.add(src)
            flattened.add(dst)
        return flattened

    def find_edges(self, stack_map, target_tags, prunes=None):
        if prunes is None:
            prunes = set()
        else:
            prunes = set(prunes)

        edges = set()

        for stack_tag, stack in stack_map.items():
            for before_tag in stack.get("before", []):
                if before_tag.startswith("tag:"):
                    raise ValueError(f"before tags unsupported: {stack_tag}")

        def resolve_after_dependencies(stack_tag):
            if not stack_tag in stack_map:
                return

            stack = stack_map[stack_tag]

            after_tags = [
                tag for tag in stack.get("after", []) if
                tag.startswith("tag:")
            ]

            if not after_tags:
                edges.add(("__root__", stack_tag))

            for after_tag in after_tags:
                after_tag = after_tag[4:] # "tag:"
                edges.add((after_tag, stack_tag))
                resolve_after_dependencies(after_tag)

        for target_tag in target_tags:
            resolve_after_dependencies(target_tag)

        def add_dependents_to_prune(edges, start):
            for src, dst in edges:
                if src == start:
                    prunes.add(dst)
                    add_dependents_to_prune(edges, dst)

        for prune in set(prunes):
            add_dependents_to_prune(edges, prune)

        for src, dst in set(edges):
            if dst in prunes:
                edges.remove((src, dst))

        return edges

    def debug(self, data):
        stacks = data["stacks"]
        pruned_edges = data["pruned_edges"]
        pruned_deps = data["pruned_deps"]
        omits = data["omits"]
        final_deps = data["final_deps"]
        stack_map = data["stack_map"]
        raw_edges = self.find_edges(stack_map, stacks)
        raw_deps = self.flatten_edges(raw_edges)

        print("All stacks")
        for k, v in sorted(stack_map.items()):
            print(f"  {k} -> {v['directory'][len(self.env_root):]}")
        print("Raw Edges")
        for src, dst in sorted(raw_edges):
            print(f"  {src} -> {dst}")
        print("Raw Dependencies")
        for dep in sorted(raw_deps):
            print(f"  {dep}")
        print("Pruned Edges")
        for src, dst in sorted(pruned_edges):
            print(f"  {src} -> {dst}")
        print("Pruned Dependencies")
        for dep in sorted(pruned_deps):
            print(f"  {dep}")
        print("Omits")
        for dep in sorted(omits):
            print(f"  {dep}")
        print("Final Dependencies")
        for dep in sorted(final_deps):
            print(f"  {dep}")

    def deploy(self, data):
        workspace = data["workspace"]
        omits = data["omits"]
        final_deps = data["final_deps"]
        command = data["command"]
        unattended = data["unattended"]
        parallel = data["parallel"]
        noinit = data["noinit"]
        var_files = data["var_files"]
        backend_bucket = data["backend_bucket"]

        print(f"using workspace {workspace}")
        if omits:
            print(f"omitting stacks {omits}")
        print(f"{command} {final_deps}")

        tagsopt = ""
        autoa = ""
        if data["unattended"] and command in ("apply", "destroy"):
            autoa="-auto-approve"
        if final_deps:
            tagsopt = f'--tags={",".join(final_deps)}'

        tmrun = f"terramate run {tagsopt} -X"
        tmrun_for_init = tmrun
        tmrun_for_deploy = tmrun
        if parallel:
            tmrun_for_init = f"{tmrun} --parallel {parallel}"
            if unattended:
                tmrun_for_deploy = tmrun_for_init
        tf = "terraform"
        var_files = " ".join(["-var-file=" + x for x in var_files])

        backend_config = ""

        if backend_bucket is not None:
            backend_config = f"-backend-config=bucket={backend_bucket}"
            os.environ["TF_VAR_backend"] =  backend_bucket

        if command == "destroy":
            tmrun_for_deploy = f"{tmrun_for_deploy} --reverse"

        env_root = self.env_root

        run(
            "terramate generate",
            cwd=env_root
        )
        if not noinit:
            run(
                f"{tmrun_for_init} -- {tf} init {backend_config}",
                cwd=env_root
            )
            run(
                f"{tmrun_for_init} -- {tf} workspace select -or-create "
                f"{workspace}",
                cwd=env_root
            )
        run(
            f"{tmrun_for_deploy} -- {tf} {command} {autoa} {var_files}",
            cwd=env_root
        )

    def show_graph(self, data):
        edges = data["pruned_edges"]
        omits = data["omits"]
        dot = graphviz.Digraph()
        for s, d in edges:
            col = "green"
            fcol = "black"
            for node in (s, d):
                col = "green"
                fcol = "black"
                if node in omits:
                    col = "red"
                    fcol = "white"
                if node == "__root__":
                    col = "white"
                    fcol = "black"
                dot.node(
                    node, node, style="filled", fillcolor=col, fontcolor=fcol
                )
            dot.edge(s, d)
        os.chdir(self.project_root) # dont write files everywhere
        dot.render("infra-graph", format="png", view=True)

    def run(self):
        data = self.setup()
        command = data["command"]
        if command == "debug":
            self.debug(data)
        if command == "graph":
            self.show_graph(data)
        if command in ("apply", "destroy", "plan"):
            self.deploy(data)


def run(command, **runargs):
    print(f"Running {command}")
    kwargs = dict(shell=True, check=True, text=True)
    kwargs.update(runargs)
    result = subprocess.run(command, **kwargs)
    return result

def find_directory_upwards(dirname, start_dir=None):
    current_path = pathlib.Path(start_dir or pathlib.Path.cwd())

    for parent in [current_path] + list(current_path.parents):
        potential_dir = parent / dirname
        if potential_dir.is_dir():
            return potential_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "command",
        choices=["apply", "destroy", "plan", "graph", "debug"],
        help="Deploy/teardown or graph a stack and its dependencies"
    )
    ap.add_argument(
        "--stack",
        action="append",
        help="Specify a stack (may be used multiple times).",
        default=[]
    )
    ap.add_argument(
        "--prune",
        action="append",
        help=("Omit this stack and any dependent stacks "
              "(may be used multiple times)."),
        default = [],
    )
    ap.add_argument(
        "--nodeps",
        action="store_true",
        help="Deploy only the named --stack",
        default = False,
    )

    ap.add_argument(
        "--omit",
        action="append",
        help=("Omit this stack, but not any of its dependent stacks "
              "(may be used multiple times)."),
        default = [],
        )
    ap.add_argument(
        "--unattended",
        action="store_true",
        help="Run deployment commmands without confirmation",
        default = False,
    )
    ap.add_argument(
        "--parallel",
        type=int,
        help=("Run terraform commands in parallel (number of parallel tasks) "
              "when possible (disabled for apply/plan/destroy when "
              "--unattended is false"),
        default = 0,
    )
    ap.add_argument(
        "--workspace",
        help="Specify a deployment workspace",
        default="default"
    )
    ap.add_argument(
        "--env",
        help="Specify an environment directory relative to the project root",
        default = "stacks"
    )
    ap.add_argument(
        "--noinit",
        help=("Skip workspace-setting and terramate init when running an apply "
              "destroy or plan."),
        action="store_true",
        default=False,
    )
    ap.add_argument(
        "--var-file",
        action="append",
        help="Use a tfvars file (may be used multiple times).",
        default = [],
    )
    ap.add_argument(
        "--backend-bucket",
        help="The s3 bucket name to use as the Terraform backend",
        default = None,
    )
    args = ap.parse_args()
    if args.nodeps and not args.stack:
        raise RuntimeError("Cannot specify --nodeps without --stack")
    deployment = Deployment(args)
    deployment.run()
