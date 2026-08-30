#
# linsys2.common - shared constants, environment table, and helpers
#
# Copyright (C) 2026 Zhou Qiankang <wszqkzqk@qq.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import platform
import sys
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or
                  Path.home() / ".config") / "linsys2"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME") or
                Path.home() / ".local" / "share") / "linsys2"

try:
    from ._paths import BIN_DIR, PRIVATE_PREFIX
except ImportError:
    # Repo checkout: the toolchain is not built yet; features needing the
    # private prefix report "not found".
    _repo = Path(__file__).resolve().parents[2]
    BIN_DIR = _repo / "scripts"
    PRIVATE_PREFIX = _repo / "lib" / "linsys2-pacman"
PACMAN_BIN = PRIVATE_PREFIX / "bin" / "pacman"
PACMAN_CONF_BIN = PRIVATE_PREFIX / "bin" / "pacman-conf"
PACMAN_KEY = PRIVATE_PREFIX / "bin" / "pacman-key"
MAKEPKG_BIN = PRIVATE_PREFIX / "bin" / "makepkg"
MAKEPKG_CONF = PRIVATE_PREFIX / "etc" / "makepkg_linsys2.conf"
LIBALPM_DIR = PRIVATE_PREFIX / "lib"
LIBMAKEPKG_DIR = PRIVATE_PREFIX / "share" / "makepkg"
KEYRING_IMPORT_DIR = PRIVATE_PREFIX / "share" / "pacman" / "keyrings"

ENVIRONMENTS = {
    "ucrt64": {
        "prefix": "mingw-w64-ucrt-x86_64",
        "install_prefix": "/ucrt64",
        "mirror_path": "ucrt64",
        "msystem": "UCRT64",
        "chost": "x86_64-w64-mingw32",
    },
    "clang64": {
        "prefix": "mingw-w64-clang-x86_64",
        "install_prefix": "/clang64",
        "mirror_path": "clang64",
        "msystem": "CLANG64",
        "chost": "x86_64-w64-mingw32",
    },
    "clangarm64": {
        "prefix": "mingw-w64-clang-aarch64",
        "install_prefix": "/clangarm64",
        "mirror_path": "clangarm64",
        "msystem": "CLANGARM64",
        "chost": "aarch64-w64-mingw32",
    },
}

_machine = platform.machine().lower()
if _machine in ("aarch64", "arm64"):
    DEFAULT_ENV = "clangarm64"
else:
    DEFAULT_ENV = "ucrt64"


def info(msg):
    print(f"\033[0;32m[INFO]\033[0m {msg}")


def warn(msg):
    print(f"\033[1;33m[WARN]\033[0m {msg}")


def error(msg):
    print(f"\033[0;31m[ERROR]\033[0m {msg}", file=sys.stderr)


def disable_winemenubuilder(env):
    """Prepend winemenubuilder.exe=d to WINEDLLOVERRIDES: our default
    applies, but any user setting still wins on conflict (last wins)."""
    existing = env.get("WINEDLLOVERRIDES")
    env["WINEDLLOVERRIDES"] = ("winemenubuilder.exe=d" +
                               (";" + existing if existing else ""))


def get_env_dir(env_name):
    return DATA_DIR / env_name


def get_bin_dir(env_name):
    env_cfg = ENVIRONMENTS[env_name]
    env_dir = get_env_dir(env_name)
    return env_dir / env_cfg["install_prefix"].lstrip("/") / "bin"


def get_wineprefix(env_name):
    return get_env_dir(env_name) / "wine"


def resolve_wineprefix(env_name, prefix_arg=None, prefer_user=False):
    """Resolve the Wine prefix for an environment: explicit argument,
    optionally the user's own prefix, then a user-created wine.config
    override, then the project-managed default."""
    if prefix_arg:
        return Path(prefix_arg)

    if prefer_user:
        user_wineprefix = os.environ.get("WINEPREFIX")
        if user_wineprefix:
            return Path(user_wineprefix)
        default_wine = Path.home() / ".wine"
        if default_wine.exists():
            return default_wine

    config_file = get_env_dir(env_name) / "wine.config"
    if config_file.exists():
        with open(config_file) as f:
            for line in f:
                if line.startswith("WINEPREFIX="):
                    parts = line.strip().split("=", 1)
                    if len(parts) == 2 and parts[1]:
                        return Path(parts[1])

    return get_wineprefix(env_name)
