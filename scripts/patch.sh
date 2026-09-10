#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu

cd "$(dirname "$0")/.."

usage() {
    echo 'usage: scripts/patch.sh list | catalog-check | inspect <selector> | recipe-check <recipe> | check|apply|reverse <selector>' >&2
    exit 2
}

[ "$#" -ge 1 ] || usage
action=$1
shift

case $action in
list)
    [ "$#" -eq 0 ] || usage
    python3 scripts/patch_catalog.py list
    exit 0
    ;;
catalog-check)
    [ "$#" -eq 0 ] || usage
    if ! command -v git >/dev/null 2>&1; then
        printf '%s\n' 'error: git required; install git to check catalog commits' >&2
        exit 1
    fi
    python3 scripts/patch_catalog.py check
    exit 0
    ;;
recipe-check)
    [ "$#" -eq 1 ] || usage
    if ! command -v git >/dev/null 2>&1; then
        printf '%s\n' 'error: git required; install git to check recipe base commit' >&2
        exit 1
    fi
    python3 scripts/patch_catalog.py recipe-check "$1"
    exit 0
    ;;
inspect)
    [ "$#" -eq 1 ] || usage
    python3 scripts/patch_catalog.py inspect "$1"
    exit 0
    ;;
check|apply|reverse) ;;
*) usage ;;
esac

if ! command -v git >/dev/null 2>&1; then
    printf '%s\n' 'error: git required; install git to check, apply, or reverse patches' >&2
    exit 1
fi

[ "$#" -eq 1 ] || usage
selector=$1

# Validate the selected artifact and its paths before asking Git to inspect or mutate files.
patch_diff=$(python3 scripts/patch_catalog.py preflight "$selector")
patch_base=$(python3 scripts/patch_catalog.py base "$selector")
head_commit=$(git rev-parse HEAD 2>/dev/null || printf '%s' unavailable)
compatibility="recorded base $patch_base; current HEAD $head_commit; manual compatibility"

case $action in
check) git apply --check "$patch_diff" ;;
apply) git apply "$patch_diff" ;;
reverse) git apply --reverse "$patch_diff" ;;
esac
printf '%s %s OK (%s checked)\n' "$action" "$selector" "$compatibility"
