#!/usr/bin/env python3
import argparse
import os
import pathlib
import subprocess

import graphviz # graphviz package
import hcl2 # python-hcl2 package

class Deployment:
    def __init__(self):
        stacks = []
        self.root = root = self.get_project_root()

        def find_files(filename, search_path=root):
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

        self.stacks = stacks

        stack_map = {}
        for stack in stacks:
            tags = set(stack.get("tags", []))
            for tag in tags:
                if tag.startswith("stack."):
                    stack_map[tag] = stack

        self.stack_map = stack_map

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

    def find_edges(self, target_tags, prunes=None):
        if prunes is None:
            prunes = set()
        else:
            prunes = set(prunes)

        edges = set()

        for stack_tag, stack in self.stack_map.items():
            for before_tag in stack.get("before", []):
                if before_tag.startswith("tag:stack."):
                    raise ValueError(f"before tags unsupported: {stack_tag}")

        def resolve_after_dependencies(stack_tag):
            if not stack_tag in self.stack_map:
                return

            stack = self.stack_map[stack_tag]

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

        def find_dependents(edges, start):
            for src, dst in edges:
                if src == start:
                    prunes.add(dst)
                    find_dependents(edges, dst)

        for prune in set(prunes):
            find_dependents(edges, prune)

        for src, dst in set(edges):
            if dst in prunes:
                edges.remove((src, dst))

        return edges

    def run(self, args):
        stacks = args.stack
        if not stacks:
            stacks = set(self.stack_map.keys())
        else:
            stacks = set([ f"stack.{stack}" for stack in stacks ])

        omits = args.omit
        if omits is None:
            omits = set()
        else:
            omits = set([ f"stack.{stack}" for stack in omits ])

        prunes = args.prune
        if prunes is None:
            prunes = set()
        else:
            prunes = set([ f"stack.{stack}" for stack in prunes ])

        raw_edges = self.find_edges(stacks)
        raw_deps = self.flatten_edges(raw_edges)

        pruned_edges = self.find_edges(stacks, prunes)
        pruned_deps = self.flatten_edges(pruned_edges)

        final_deps = pruned_deps.difference(omits)

        command = args.command

        if command == "debug":
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

        if command == "graph":
            self.show_graph(pruned_edges, omits)

        if command in ("apply", "destroy", "plan"):
            workspace = args.workspace
            print(f"using workspace {workspace}")
            if omits:
                print(f"omitting stacks {omits}")
            print(f"{command}ing {final_deps}")
            root = deployment.root
            tagsopt = ""
            autoa = ""
            if args.unattended:
                autoa="-auto-approve"
            if final_deps:
                tagsopt = f'--tags={",".join(final_deps)}'
            trun = f"terramate run {tagsopt} -X"

            run("terramate generate", cwd=root)
            run("terramate list --run-order", cwd=root)
            run(
                f"{trun} -- terraform init",
                cwd=root
            )
            run(
                f"{trun} -- terraform workspace select -or-create {workspace}",
                cwd=root
            )
            run("terramate list --run-order", cwd=root)
            if command == "apply":
                run(
                    f"{trun} -- terraform apply {autoa}",
                    cwd=root
                )
            if command == "plan":
                run(
                    f"{trun} -- terraform plan",
                    cwd=root
                )
            if command == "destroy":
                run(
                    f"{trun} --reverse -- terraform destroy {autoa}",
                    cwd=root
                )

    def show_graph(self, edges, omits):
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
        os.chdir(self.get_project_root()) # dont write files everywhere
        dot.render("infra-graph", format="png", view=True)

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
        choices=["apply", "destroy", "graph", "debug", "plan"],
    )
    ap.add_argument(
        "--stack",
        action="append",
        help="Specify a stack (can be used multiple times)."
        )
    ap.add_argument(
        "--prune",
        action="append",
        help=("Omit these stacks and dependent stacks "
              "(can be used multiple times).")
        )
    ap.add_argument(
        "--omit",
        action="append",
        help=("Omit these stacks, but not dependent stacks "
              "(can be used multiple times).")
        )
    ap.add_argument(
        "--unattended",
        action="store_true",
        help="Automatically approve apply or destroy, no questions asked."
        )
    ap.add_argument(
        "--workspace",
        help="Specify a deployment workspace",
        default="default"
        )
    args = ap.parse_args()
    deployment = Deployment()
    deployment.run(args)
