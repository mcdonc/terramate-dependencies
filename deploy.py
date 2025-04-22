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

    def get_stack_map(self):
        stacks = []

        def find_files(filename, search_path=self.project_root):
            path = pathlib.Path(search_path)
            return list(path.rglob(filename))

        results = find_files("stack.tm.hcl")

        for stackfile in results:
            with open(stackfile, "r") as f:
                hcl_data = hcl2.load(f)
                stack_data = hcl_data.get("stack")
                if stack_data:
                    stack = stack_data[0]
                    stack["directory"] = os.path.dirname(stackfile)
                    stacks.append(stack)

        stack_map = {}
        for stack in stacks:
            tags = set(stack.get("tags", []))
            for tag in tags:
                if tag.startswith("stack."):
                    stack_map[tag] = stack

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
            stacks = set([ f"stack.{stack}" for stack in stacks ])

        omits = set([ f"stack.{stack}" for stack in omits ])
        prunes = set([ f"stack.{stack}" for stack in prunes ])

        pruned_edges = self.find_edges(stack_map, stacks, prunes)
        pruned_deps = self.flatten_edges(pruned_edges)

        final_deps = pruned_deps.difference(omits)

        command = args.command

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
            parallel = args.parallel
        )

    def get_project_root(self):
        gitdir = find_directory_upwards(".git")
        if not gitdir:
            raise ValueError(".git could not be found in parents")
        return os.path.dirname(gitdir)

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
                if before_tag.startswith("tag:stack."):
                    raise ValueError(f"before tags unsupported: {stack_tag}")

        def resolve_after_dependencies(stack_tag):
            if not stack_tag in stack_map:
                return

            stack = stack_map[stack_tag]

            after_tags = [
                tag for tag in stack.get("after", []) if
                tag.startswith("tag:stack.")
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

        if command == "destroy":
            tmrun_for_deploy = f"{tmrun_for_deploy} --reverse"

        project_root = self.project_root

        run(
            "terramate generate",
            cwd=project_root
        )
        run(
            "terramate list --run-order",
            cwd=project_root
        )
        run(
            f"{tmrun_for_init} -- {tf} init",
            cwd=project_root
        )
        run(
            f"{tmrun_for_init} -- {tf} workspace select -or-create "
            f"{workspace}",
            cwd=project_root
        )
        run(
            "terramate list --run-order",
            cwd=project_root
        )
        run(
            f"{tmrun_for_deploy} -- {tf} {command} {autoa}",
            cwd=project_root
        )

    def show_graph(self, data):
        edges = data["pruned_edges"]
        omits = data["omits"]
        project_root = self.project_root
        dot = graphviz.Digraph()
        dot.node("__root__", "__root__")
        for s, d in edges:
            col = "green"
            fcol = "black"
            for node in (s, d):
                if s == "__root__":
                    continue
                if node in omits:
                    col = "red"
                    fcol = "white"
                n = node[6:] # "stack."
                dot.node(n, n, style="filled", fillcolor=col, fontcolor=fcol)
            if s != "__root__":
                s = s[6:] # "stack."
            dot.edge(s, d[6:])
        os.chdir(project_root) # dont write files everywhere
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
    args = ap.parse_args()
    deployment = Deployment(args)
    deployment.run()
