#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate and exercise every active patch in the catalog."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

import patch_catalog


class RunnerError(Exception):
    """A catalog or verification operation failed."""


def selector(feature: str, revision: int) -> str:
    return f"{feature}@{revision}"


def entry_map(catalog: dict[str, dict[int, dict]]) -> dict[str, dict]:
    return {
        selector(feature, revision): entry
        for feature, revisions in catalog.items()
        for revision, entry in revisions.items()
    }


def resolve_closure(catalog: dict[str, dict[int, dict]], target: str) -> list[tuple[str, dict]]:
    """Return target requirements in dependency-first order."""
    entries = entry_map(catalog)
    if target not in entries:
        raise RunnerError(f"active patch '{target}' is missing from the catalog")

    ordered: list[tuple[str, dict]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(current: str) -> None:
        if current in visiting:
            raise RunnerError(f"dependency cycle detected while resolving '{target}' at '{current}'")
        if current in visited:
            return
        if current not in entries:
            raise RunnerError(f"patch '{target}' requires missing patch '{current}'")
        visiting.add(current)
        entry = entries[current]
        for requirement in entry["requires"]:
            visit(requirement)
        visiting.remove(current)
        visited.add(current)
        ordered.append((current, entry))

    visit(target)

    target_base = entries[target]["base_commit"]
    for current, entry in ordered:
        if entry["base_commit"] != target_base:
            raise RunnerError(
                f"patch '{target}' requires '{current}' with base '{entry['base_commit']}', "
                f"but the closure base is '{target_base}'"
            )

    features = [entry["feature"] for _, entry in ordered]
    if len(features) != len(set(features)):
        raise RunnerError(f"patch '{target}' has more than one revision of a feature in its closure")

    for current, entry in ordered:
        for other, other_entry in ordered:
            if current == other:
                continue
            if other_entry["feature"] in entry["conflicts"]:
                raise RunnerError(f"patch '{current}' conflicts with '{other}' in '{target}' closure")

    return ordered


def run(command: list[str], cwd: Path) -> None:
    print(f"+ {' '.join(command)} (in {cwd})", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def apply_closure(root: Path, worktree: Path, closure: list[tuple[str, dict]]) -> None:
    for current, entry in closure:
        diff_path = root / "patches" / entry["feature"] / str(entry["revision"]) / entry["diff"]
        try:
            run(["git", "apply", "--check", str(diff_path)], worktree)
            run(["git", "apply", str(diff_path)], worktree)
        except subprocess.CalledProcessError as error:
            raise RunnerError(f"applying patch '{current}' failed with exit code {error.returncode}") from error


def verify_worktree(
    root: Path,
    commit: str,
    closure: list[tuple[str, dict]],
    label: str,
    lint: bool,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hax-patch-ci-") as temp:
        worktree = Path(temp) / "source"
        added = False
        try:
            run(["git", "worktree", "add", "--detach", str(worktree), commit], root)
            added = True
            apply_closure(root, worktree, closure)
            try:
                run(["make", "tests"], worktree)
                if lint:
                    run(["make", "lint"], worktree)
            except subprocess.CalledProcessError as error:
                raise RunnerError(
                    f"{label} verification failed with exit code {error.returncode}"
                ) from error
        finally:
            if added:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(worktree)],
                    cwd=root,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )


def build_plan(root: Path) -> tuple[dict[str, dict[int, dict]], list[tuple[str, list[tuple[str, dict]]]]]:
    catalog = patch_catalog.load_catalog(root, check_commits=True)
    active = [
        selector(feature, revision)
        for feature, revisions in catalog.items()
        for revision, entry in revisions.items()
        if entry["status"] == "active"
    ]
    active.sort()
    plan = [(current, resolve_closure(catalog, current)) for current in active]
    return catalog, plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify active catalog patches in CI")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="validate the catalog and print active selectors without building",
    )
    args = parser.parse_args(argv)
    root = Path.cwd()

    try:
        _, plan = build_plan(root)
        if args.discover:
            for current, _ in plan:
                print(current)
            return 0

        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
        if not plan:
            print("No active patches to verify.")
            return 0

        for current, closure in plan:
            base = closure[-1][1]["base_commit"]
            print(f"Verifying {current} closure: {', '.join(item[0] for item in closure)}")
            verify_worktree(root, base, closure, f"{current} at recorded base {base}", lint=False)
            verify_worktree(root, head, closure, f"{current} at candidate {head}", lint=True)
        return 0
    except (patch_catalog.CatalogError, RunnerError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
