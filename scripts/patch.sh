#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu

cd "$(dirname "$0")/.."

usage() {
    echo 'usage: scripts/patch.sh list | catalog-check | inspect <selector> | check|apply|reverse <selector>' >&2
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

# Resolve selector to diff path via patch_catalog.py
patch_diff=$(python3 scripts/patch_catalog.py resolve "$selector")

# git apply checks every hunk before writing; never use --reject here.
case $action in
check) git apply --check "$patch_diff" ;;
apply) git apply "$patch_diff" ;;
reverse) git apply --reverse "$patch_diff" ;;
esac
printf '%s %s OK\n' "$action" "$selector"
