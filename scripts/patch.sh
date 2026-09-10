#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu

cd "$(dirname "$0")/.."

usage() {
    echo 'usage: scripts/patch.sh list | check|apply|reverse <name>' >&2
    exit 2
}

[ "$#" -ge 1 ] || usage
action=$1
shift
case $action in
list)
    [ "$#" -eq 0 ] || usage
    for file in patches/*/*.diff; do
        [ -f "$file" ] || continue
        name=${file#patches/}
        printf '%s\n' "${name%%/*}"
    done
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
name=$1
case $name in
''|*[!a-z0-9-]*) usage ;;
esac
set -- patches/"$name"/*.diff
if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
    printf 'error: expected one diff for patch %s; see scripts/patch.sh list\n' "$name" >&2
    exit 1
fi
patch=$1

# git apply checks every hunk before writing; never use --reject here.
case $action in
check) git apply --check "$patch" ;;
apply) git apply "$patch" ;;
reverse) git apply --reverse "$patch" ;;
esac
printf '%s %s OK\n' "$action" "$name"
