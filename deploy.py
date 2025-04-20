#!/usr/bin/env python3
import argparse
import os
import pathlib
import subprocess

import graphviz
import hcl2

def run(command, **runargs):
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

    def find_dependencies(self, *target_tags):
        if not target_tags:
            target_tags = list(self.stack_map.keys())

        dependencies = set()
        edges = set()

        def resolve_after_dependencies(stack_tag):
            if stack_tag not in self.stack_map:
                return

            stack = self.stack_map[stack_tag]

            for after_tag in stack.get("after", []):
                if after_tag.startswith("tag:"):
                    after_tag = after_tag[4:]
                    if after_tag not in dependencies:
                        dependencies.add(after_tag)
                        resolve_after_dependencies(after_tag)
                    edges.add((after_tag[6:], stack_tag[6:]))

        for target_tag in sorted(target_tags):
            dependencies.add(target_tag)
            resolve_after_dependencies(target_tag)

        for stack_tag, stack in self.stack_map.items():
            for before_tag in stack.get("before", []):
                if before_tag.startswith("tag:"):
                    before_tag = before_tag[4:]
                    if before_tag in dependencies:
                        dependencies.add(stack_tag)
                        resolve_after_dependencies(stack_tag)
                        edges.add((stack_tag[6:], before_tag[6:]))

        return dependencies, edges


def show_graph(edges):
    dot = graphviz.Digraph()
    for src, dst in edges:
        dot.edge(src, dst)
    dot.render("infra-graph", format="png", view=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "command",
        choices=["apply", "destroy", "graph"],
    )
    ap.add_argument(
        "--stack",
        action="append",
        help="Specify a stack (can be used multiple times)."
        )
    ap.add_argument(
        "--workspace",
        help="Specify a deployment workspace",
        default="default"
        )
    args = ap.parse_args()
    deployment = Deployment()
    if args.stack is None:
        stacks = ()
    else:
        stacks = [ f"stack.{stack}" for stack in args.stack ]
    deps, edges = deployment.find_dependencies(*stacks)
    command = args.command
    if command == "graph":
        print("All Dependencies")
        for dep in sorted(deps):
            print(f"  {dep}")
        print("Edges")
        for src, dst in sorted(edges):
            print(f"  {src} -> {dst}")
        show_graph(edges)
    if command in ("apply", "destroy"):
        workspace = args.workspace
        root = deployment.root
        tagsopt = ""
        if deps:
            tagsopt = f'--tags={",".join(deps)}'
        tm_run = f"terramate run {tagsopt} -X"
        run(
            f"{tm_run} -- terraform init",
            cwd=root
        )
        run(
            f"{tm_run} -- terraform workspace select -or-create {workspace}",
            cwd=root
        )
        if command == "apply":
            run(f"{tm_run} -- terraform apply", cwd=root)
        else:
            run(f"{tm_run} --reverse -- terraform destroy", cwd=root)
   
    
    
