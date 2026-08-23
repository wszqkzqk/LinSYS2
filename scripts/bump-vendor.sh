#!/bin/sh
# Bump a vendored submodule: bump-vendor.sh <pacman|keyring> <tag|commit|branch>
set -e

top=$(cd "$(dirname "$0")/.." && pwd)

case "$1" in
    pacman)  sub=subprojects/msys2-pacman ;;
    keyring) sub=vendor/msys2-keyring ;;
    *)
        echo "Usage: $0 <pacman|keyring> <tag|commit|branch>" >&2
        exit 1
        ;;
esac

if [ -z "$2" ]; then
    echo "Usage: $0 <pacman|keyring> <tag|commit|branch>" >&2
    exit 1
fi

echo "[LinSYS2] Fetching $2..."
git -C "$top/$sub" fetch origin "$2"
echo "[LinSYS2] Checking out $2..."
git -C "$top/$sub" checkout "$2"

if [ "$1" = "pacman" ]; then
    echo "[LinSYS2] Verifying patch compatibility..."
    git -C "$top/$sub" checkout -- .
    for p in "$top"/patches/*.patch; do
        patch -p1 -d "$top/$sub" -i "$p" --dry-run --quiet
    done
fi

echo "[LinSYS2] OK. Staging..."
git -C "$top" add "$sub"
echo "Review: git diff --cached"
echo "Commit: git commit -m 'Bump $1 to $2'"
