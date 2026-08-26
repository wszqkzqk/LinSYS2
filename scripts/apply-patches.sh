#!/bin/sh
# Apply LinSYS2 patches to the vendored msys2-pacman (idempotent).
# Invoked by meson at configure time; safe to run by hand.
set -e

top=$(cd "$(dirname "$0")/.." && pwd)
sub="$top/subprojects/msys2-pacman"
stamp="$sub/.linsys2-patched.stamp"

if [ ! -f "$sub/meson.build" ]; then
    if [ -e "$top/.git" ]; then
        git -C "$top" submodule update --init --recursive subprojects/msys2-pacman
    fi
fi
if [ ! -f "$sub/meson.build" ]; then
    echo "error: subprojects/msys2-pacman is missing; run:" >&2
    echo "  git submodule update --init --recursive" >&2
    exit 1
fi

needs_patch=1
if [ -f "$stamp" ]; then
    needs_patch=0
    for p in "$top"/patches/*.patch; do
        if [ "$p" -nt "$stamp" ]; then
            needs_patch=1
            break
        fi
    done
fi

if [ "$needs_patch" -eq 0 ]; then
    exit 0
fi

echo "[LinSYS2] Applying patches..."
git -C "$sub" checkout -- .
for p in "$top"/patches/*.patch; do
    patch -p1 -d "$sub" --no-backup-if-mismatch -i "$p"
done
touch "$stamp"
