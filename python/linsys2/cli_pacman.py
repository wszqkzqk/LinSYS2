#
# linsys2-pacman - CLI wrapper for MSYS2 pacman on Linux
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

import argparse
import os
import subprocess
import sys

from linsys2 import __version__
from linsys2.common import (
    CONFIG_DIR,
    DEFAULT_ENV,
    ENVIRONMENTS,
    KEYRING_IMPORT_DIR,
    LIBALPM_DIR,
    LIBMAKEPKG_DIR,
    PACMAN_BIN,
    PACMAN_KEY,
    PRIVATE_PREFIX,
    error,
    get_env_dir,
    info,
    warn,
)

MSYS2_MIRRORS = [
    "https://mirror.msys2.org/mingw/$repo",
    "https://repo.msys2.org/mingw/$repo",
    "https://mirrors.tuna.tsinghua.edu.cn/msys2/mingw/$repo",
    "https://mirrors.ustc.edu.cn/msys2/mingw/$repo",
    "https://mirrors.bfsu.edu.cn/msys2/mingw/$repo",
    "https://mirrors.aliyun.com/msys2/mingw/$repo",
]

LINSYS2_SUBCOMMANDS = {"init", "update-keyring"}


def get_pacman_binary():
    if PACMAN_BIN.exists():
        return str(PACMAN_BIN)
    error("Pacman binary not found.")
    error(f"Expected: {PACMAN_BIN}")
    sys.exit(1)


def get_pacman_key_binary():
    if PACMAN_KEY.exists():
        return str(PACMAN_KEY)
    error("pacman-key not found.")
    error(f"Expected: {PACMAN_KEY}")
    sys.exit(1)


def get_pacman_env():
    """Make the private prefix's binaries (pacman-conf) and libalpm
    discoverable."""
    env = os.environ.copy()
    env["MSYS2_PACMAN_LINUX"] = "1"

    # Override hardcoded build-time paths for relocatable installs.
    env["MAKEPKG_LIBRARY"] = str(LIBMAKEPKG_DIR)
    env["KEYRING_IMPORT_DIR"] = str(KEYRING_IMPORT_DIR)

    if LIBALPM_DIR.exists():
        old = env.get("LD_LIBRARY_PATH")
        env["LD_LIBRARY_PATH"] = str(LIBALPM_DIR) + (":" + old if old else "")

    bin_dir = PRIVATE_PREFIX / "bin"
    if bin_dir.exists():
        old = env.get("PATH")
        env["PATH"] = str(bin_dir) + (":" + old if old else "")

    return env


def get_env_config(env_name):
    if env_name not in ENVIRONMENTS:
        error(f"Unknown environment: {env_name}")
        error(f"Supported: {', '.join(ENVIRONMENTS.keys())}")
        sys.exit(1)
    return ENVIRONMENTS[env_name]


def get_config_file(env_name):
    return CONFIG_DIR / f"{env_name}.conf"


def get_db_dir(env_name):
    return get_env_dir(env_name) / "var" / "lib" / "pacman"


def create_mirrorlist():
    mirrorlist_file = CONFIG_DIR / "mirrorlist.mingw"
    if mirrorlist_file.exists():
        return

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(mirrorlist_file, "w") as f:
        f.write("##\n")
        f.write("## MSYS2 MINGW Repository Mirrorlist\n")
        f.write("##\n\n")
        for mirror in MSYS2_MIRRORS:
            f.write(f"Server = {mirror}\n")


def create_config(env_name):
    env_cfg = get_env_config(env_name)
    env_dir = get_env_dir(env_name)
    config_file = get_config_file(env_name)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    env_dir.mkdir(parents=True, exist_ok=True)

    get_db_dir(env_name).mkdir(parents=True, exist_ok=True)
    (env_dir / "var" / "cache" / "pacman" / "pkg").mkdir(parents=True, exist_ok=True)
    (env_dir / "var" / "log").mkdir(parents=True, exist_ok=True)
    (env_dir / "etc" / "pacman.d" / "hooks").mkdir(parents=True, exist_ok=True)
    (env_dir / env_cfg["install_prefix"].lstrip("/")).mkdir(parents=True, exist_ok=True)

    create_mirrorlist()

    config_content = f"""#
# LinSYS2 pacman configuration for {env_name}
#

[options]
RootDir      = {env_dir}
DBPath       = {env_dir}/var/lib/pacman
CacheDir     = {env_dir}/var/cache/pacman/pkg
GPGDir       = {env_dir}/etc/pacman.d/gnupg
HookDir      = {env_dir}/etc/pacman.d/hooks
LogFile      = {env_dir}/var/log/pacman.log
Architecture = auto
Color
CheckSpace
ParallelDownloads = 8
SigLevel     = Required DatabaseOptional
LocalFileSigLevel = Optional

[{env_name}]
Include = {CONFIG_DIR / "mirrorlist.mingw"}
"""

    with open(config_file, "w") as f:
        f.write(config_content)

    info(f"Configuration created: {config_file}")


def run_pacman(env_name, pacman_args):
    pacman_bin = get_pacman_binary()
    config_file = get_config_file(env_name)

    if not config_file.exists():
        error(f"Environment not initialized: {env_name}")
        error(f"Run: linsys2-pacman init --env {env_name}")
        return 1

    cmd = [pacman_bin, "--config", str(config_file)] + pacman_args
    env = get_pacman_env()
    try:
        rc = subprocess.run(cmd, env=env).returncode
    except KeyboardInterrupt:
        return 130
    # shell convention: killed by signal N -> 128+N
    return 128 - rc if rc < 0 else rc


def show_help():
    print(f"""LinSYS2 - Manage MSYS2 mingw-w64 packages on Linux

Usage:
  linsys2-pacman [pacman-options...]
    Run pacman commands directly. Defaults to {DEFAULT_ENV} environment.
    Examples:
      linsys2-pacman -Syu               # Upgrade packages
      linsys2-pacman -S gcc             # Install a package
      linsys2-pacman -R gcc             # Remove a package
      linsys2-pacman -Q                 # List installed packages
      linsys2-pacman -Ss search         # Search packages

  linsys2-pacman --env ENV [pacman-options...]
    Use a non-default environment.

  linsys2-pacman init [--env ENV] [--force]
    Initialize a new environment.

  linsys2-pacman update-keyring [--env ENV]
    Refresh the pacman keyring.

Environments: {', '.join(ENVIRONMENTS.keys())} (default: {DEFAULT_ENV})
""")


def cmd_init(args):
    env_name = args.env
    force = args.force

    config_file = get_config_file(env_name)
    db_dir = get_db_dir(env_name)

    info(f"Initializing {env_name} environment...")

    # The env dir is shared with Wine/build tools; only pacman state counts.
    if config_file.exists() or db_dir.exists():
        warn(f"Pacman environment already initialized: {env_name}")
        if not force:
            try:
                response = input("Reinitialize? [y/N] ")
            except EOFError:
                response = "n"
            if response.lower() not in ("y", "yes"):
                info("Aborted")
                return 1

    pacman_key = get_pacman_key_binary()
    env = get_pacman_env()

    create_config(env_name)

    info("Initializing pacman keyring...")
    try:
        subprocess.run([pacman_key, "--config", str(config_file), "--init"],
                       env=env, check=True)
        subprocess.run([pacman_key, "--config", str(config_file), "--populate", "msys2"],
                       env=env, check=True)
    except (subprocess.CalledProcessError, OSError) as e:
        error(f"pacman-key initialization failed: {e}")
        error(f"Run 'linsys2-pacman init --env {env_name} --force' to retry.")
        return 1

    info(f"Environment {env_name} initialized successfully")
    return 0


def cmd_update_keyring(args):
    env_name = args.env
    config_file = get_config_file(env_name)

    if not config_file.exists():
        error(f"Configuration not found: {config_file}")
        error(f"Run: linsys2-pacman init --env {env_name}")
        return 1

    pacman_key = get_pacman_key_binary()
    env = get_pacman_env()

    info(f"Updating keyring for {env_name}...")
    try:
        subprocess.run([pacman_key, "--config", str(config_file), "--populate", "msys2"],
                       env=env, check=True)
        info("Keyring updated successfully")
    except (subprocess.CalledProcessError, OSError) as e:
        error(f"Keyring update failed: {e}")
        return 1
    return 0


def main():
    argv = sys.argv[1:]

    if not argv:
        show_help()
        return 0

    env_choices = list(ENVIRONMENTS.keys())

    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--env", default=DEFAULT_ENV, choices=env_choices,
                     help=f"target environment (default: {DEFAULT_ENV})")
    pre_args, remaining = pre.parse_known_args(argv)
    env_name = pre_args.env

    if remaining and remaining[0] in ("-h", "--help", "help"):
        show_help()
        return 0

    if remaining and remaining[0] in ("-V", "--version"):
        print(f"LinSYS2 pacman wrapper {__version__}")
        return 0

    if remaining and remaining[0] in LINSYS2_SUBCOMMANDS:
        subcmd = remaining[0]
        sub_args = remaining[1:]

        if subcmd == "init":
            p = argparse.ArgumentParser(add_help=False)
            p.add_argument("--env", default=env_name, choices=env_choices,
                           help=f"target environment (default: {env_name})")
            p.add_argument("--force", action="store_true",
                           help="reinitialize without prompt")
            p.add_argument("-h", "--help", action="store_true",
                           help="show this help message and exit")
            try:
                parsed = p.parse_args(sub_args)
            except SystemExit:
                return 2
            if parsed.help:
                p.print_help()
                return 0
            return cmd_init(parsed)

        elif subcmd == "update-keyring":
            p = argparse.ArgumentParser(add_help=False)
            p.add_argument("--env", default=env_name, choices=env_choices,
                           help=f"target environment (default: {env_name})")
            p.add_argument("-h", "--help", action="store_true",
                           help="show this help message and exit")
            try:
                parsed = p.parse_args(sub_args)
            except SystemExit:
                return 2
            if parsed.help:
                p.print_help()
                return 0
            return cmd_update_keyring(parsed)

    return run_pacman(env_name, remaining)
