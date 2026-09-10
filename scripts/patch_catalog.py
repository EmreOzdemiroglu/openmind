#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validation and query operations for the versioned patch catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

FEATURE_RE = re.compile(r"^[a-z][a-z0-9-]*$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SELECTOR_RE = re.compile(r"^([a-z][a-z0-9-]*)(?:@([1-9][0-9]*))?$")


class CatalogError(Exception):
    pass


def parse_selector(text: str) -> tuple[str, int | None]:
    match = SELECTOR_RE.fullmatch(text)
    if not match:
        raise CatalogError(f"invalid selector '{text}'; expected feature or feature@revision")
    feature, rev_str = match.groups()
    rev = int(rev_str) if rev_str is not None else None
    return feature, rev


def load_catalog(root: Path, check_commits: bool = True) -> dict[str, dict[int, dict]]:
    catalog_dir = root / "patches"
    if not catalog_dir.is_dir():
        return {}

    catalog: dict[str, dict[int, dict]] = {}

    for feature_dir in sorted(catalog_dir.iterdir()):
        if not feature_dir.is_dir() or feature_dir.name.startswith("."):
            continue
        feature_name = feature_dir.name
        if not FEATURE_RE.fullmatch(feature_name):
            raise CatalogError(f"invalid feature directory name: '{feature_name}'")

        catalog[feature_name] = {}

        for rev_dir in sorted(feature_dir.iterdir()):
            if not rev_dir.is_dir() or rev_dir.name.startswith("."):
                continue
            rev_str = rev_dir.name
            if not rev_str.isdigit() or rev_str.startswith("0") or int(rev_str) <= 0:
                raise CatalogError(f"invalid revision directory '{rev_str}' in '{feature_name}'")
            revision = int(rev_str)

            patch_json = rev_dir / "patch.json"
            if not patch_json.is_file():
                raise CatalogError(f"missing patch.json in '{feature_name}/{revision}'")

            try:
                data = json.loads(patch_json.read_text(encoding="utf-8"))
            except Exception as e:
                raise CatalogError(f"malformed JSON in '{patch_json}': {e}")

            validate_entry(data, patch_json, feature_name, revision, check_commits=check_commits)
            catalog[feature_name][revision] = data

    validate_catalog_consistency(catalog)
    return catalog


def validate_entry(
    data: dict, path: Path, feature: str, revision: int, check_commits: bool = True
) -> None:
    required_keys = {
        "schema", "feature", "revision", "base_commit",
        "diff", "sha256", "requires", "conflicts", "status"
    }
    if set(data.keys()) != required_keys:
        missing = required_keys - set(data.keys())
        extra = set(data.keys()) - required_keys
        msg = f"in '{path}':"
        if missing:
            msg += f" missing keys {sorted(missing)}"
        if extra:
            msg += f" unexpected keys {sorted(extra)}"
        raise CatalogError(msg)

    if data["schema"] != 1:
        raise CatalogError(f"in '{path}': unsupported schema {data['schema']}, expected 1")

    if data["feature"] != feature:
        raise CatalogError(f"in '{path}': feature '{data['feature']}' does not match directory '{feature}'")

    if data["revision"] != revision:
        raise CatalogError(f"in '{path}': revision {data['revision']} does not match directory {revision}")

    if not isinstance(data["base_commit"], str) or not COMMIT_RE.fullmatch(data["base_commit"]):
        raise CatalogError(f"in '{path}': base_commit must be exactly 40 lowercase hex characters")

    if check_commits:
        res = subprocess.run(
            ["git", "cat-file", "-e", f"{data['base_commit']}^{{commit}}"],
            capture_output=True,
        )
        if res.returncode != 0:
            raise CatalogError(f"in '{path}': base_commit '{data['base_commit']}' does not resolve to a local commit")

    if not isinstance(data["status"], str) or data["status"] not in ("active", "archived"):
        raise CatalogError(f"in '{path}': status must be 'active' or 'archived'")

    if not isinstance(data["diff"], str):
        raise CatalogError(f"in '{path}': diff must be a string filename")
    if Path(data["diff"]).is_absolute() or ".." in Path(data["diff"]).parts:
        raise CatalogError(f"in '{path}': diff path '{data['diff']}' must be local and cannot traverse")

    diff_file = path.parent / data["diff"]
    if not diff_file.is_file() or diff_file.is_symlink():
        raise CatalogError(f"in '{path}': diff file '{data['diff']}' does not exist or is symlink")

    if not isinstance(data["sha256"], str) or not SHA256_RE.fullmatch(data["sha256"]):
        raise CatalogError(f"in '{path}': sha256 must be exactly 64 lowercase hex characters")

    actual_digest = hashlib.sha256(diff_file.read_bytes()).hexdigest()
    if actual_digest != data["sha256"]:
        raise CatalogError(
            f"in '{path}': digest mismatch for '{data['diff']}': expected {data['sha256']}, got {actual_digest}"
        )

    if not isinstance(data["requires"], list):
        raise CatalogError(f"in '{path}': requires must be a list")
    for req in data["requires"]:
        if not isinstance(req, str) or "@" not in req:
            raise CatalogError(f"in '{path}': requires entries must be exact selectors ('feature@revision'): '{req}'")
        try:
            r_feat, r_rev = parse_selector(req)
            if r_rev is None:
                raise CatalogError("")
        except Exception:
            raise CatalogError(f"in '{path}': invalid requirement selector '{req}'")

    if not isinstance(data["conflicts"], list):
        raise CatalogError(f"in '{path}': conflicts must be a list")
    for conf in data["conflicts"]:
        if not isinstance(conf, str) or not FEATURE_RE.fullmatch(conf):
            raise CatalogError(f"in '{path}': conflicts entries must be feature ids: '{conf}'")


def validate_catalog_consistency(catalog: dict[str, dict[int, dict]]) -> None:
    # 1. At most one active artifact per feature
    for feature, revisions in catalog.items():
        active_revs = [r for r, d in revisions.items() if d["status"] == "active"]
        if len(active_revs) > 1:
            raise CatalogError(f"feature '{feature}' has multiple active revisions: {active_revs}")

    # 2. Check requirements exist and no graph cycles
    entries_by_sel: dict[str, dict] = {}
    for feature, revisions in catalog.items():
        for rev, d in revisions.items():
            entries_by_sel[f"{feature}@{rev}"] = d

    for sel, d in entries_by_sel.items():
        for req in d["requires"]:
            if req not in entries_by_sel:
                raise CatalogError(f"patch '{sel}' requires missing patch '{req}'")

    # Cycle check via DFS
    visited = {}  # 0=unvisited, 1=visiting, 2=visited

    def dfs(node: str, path: list[str]):
        visited[node] = 1
        for req in entries_by_sel[node]["requires"]:
            if visited.get(req) == 1:
                cycle_str = " -> ".join(path + [req])
                raise CatalogError(f"dependency cycle detected: {cycle_str}")
            if visited.get(req, 0) == 0:
                dfs(req, path + [req])
        visited[node] = 2

    for sel in entries_by_sel:
        if visited.get(sel, 0) == 0:
            dfs(sel, [sel])

    # 3. Conflicts check (either-side exclusion)
    for sel, d in entries_by_sel.items():
        feat = d["feature"]
        for conf in d["conflicts"]:
            if conf == feat:
                raise CatalogError(f"patch '{sel}' conflicts with itself")


def resolve_selector(catalog: dict[str, dict[int, dict]], selector_str: str) -> tuple[dict, Path]:
    feature, rev = parse_selector(selector_str)
    if feature not in catalog:
        raise CatalogError(f"unknown feature '{feature}'")

    if rev is not None:
        if rev not in catalog[feature]:
            raise CatalogError(f"unknown revision {rev} for feature '{feature}'")
        entry = catalog[feature][rev]
    else:
        active = [d for d in catalog[feature].values() if d["status"] == "active"]
        if not active:
            raise CatalogError(f"no active revision for feature '{feature}'")
        if len(active) > 1:
            raise CatalogError(f"ambiguous active revisions for feature '{feature}'")
        entry = active[0]

    patch_dir = Path("patches") / entry["feature"] / str(entry["revision"])
    diff_path = patch_dir / entry["diff"]
    return entry, diff_path


def compare_catalogs(old_cat: dict[str, dict[int, dict]], new_cat: dict[str, dict[int, dict]]) -> None:
    """Ensure immutability: past revisions cannot change base, diff, digest, requires, conflicts."""
    for feat, revs in old_cat.items():
        if feat not in new_cat:
            raise CatalogError(f"feature '{feat}' was removed from catalog")
        for rev, old_entry in revs.items():
            if rev not in new_cat[feat]:
                raise CatalogError(f"revision '{feat}@{rev}' was removed from catalog")
            new_entry = new_cat[feat][rev]
            for immutable_field in ["schema", "feature", "revision", "base_commit", "diff", "sha256", "requires", "conflicts"]:
                if old_entry[immutable_field] != new_entry[immutable_field]:
                    raise CatalogError(
                        f"immutable field '{immutable_field}' modified in '{feat}@{rev}'"
                    )


def main():
    parser = argparse.ArgumentParser(description="Patch catalog manager")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    sub.add_parser("list")
    sub.add_parser("check")
    insp = sub.add_parser("inspect")
    insp.add_argument("selector", help="feature or feature@revision")
    res = sub.add_parser("resolve")
    res.add_argument("selector", help="feature or feature@revision")

    args = parser.parse_args()
    root = Path.cwd()

    try:
        catalog = load_catalog(root, check_commits=(args.subcommand == "check"))

        if args.subcommand == "list":
            for feat in sorted(catalog.keys()):
                for rev in sorted(catalog[feat].keys()):
                    e = catalog[feat][rev]
                    status_str = f" [{e['status']}]" if e["status"] == "archived" else ""
                    print(f"{feat}@{rev}{status_str}")
        elif args.subcommand == "check":
            print(f"catalog OK ({sum(len(r) for r in catalog.values())} patches)")
        elif args.subcommand == "inspect":
            entry, diff_path = resolve_selector(catalog, args.selector)
            print(f"Feature:     {entry['feature']}")
            print(f"Revision:    {entry['revision']}")
            print(f"Status:      {entry['status']}")
            print(f"Base commit: {entry['base_commit']}")
            print(f"Diff:        {diff_path}")
            print(f"SHA-256:     {entry['sha256']}")
            print(f"Requires:    {', '.join(entry['requires']) if entry['requires'] else 'none'}")
            print(f"Conflicts:   {', '.join(entry['conflicts']) if entry['conflicts'] else 'none'}")
        elif args.subcommand == "resolve":
            _, diff_path = resolve_selector(catalog, args.selector)
            print(diff_path)

    except CatalogError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
