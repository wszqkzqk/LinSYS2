#
# linsys2 - Wine integration for LinSYS2 mingw-w64 environments
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
import shutil
import subprocess
import sys
from pathlib import Path

from linsys2 import __version__
from linsys2.common import (
    DEFAULT_ENV,
    ENVIRONMENTS,
    error,
    get_bin_dir,
    info,
    resolve_wineprefix,
    warn,
)


def ensure_wine():
    if not shutil.which("wine"):
        error("Wine is not installed or not in PATH. Please install Wine and try again.")
        sys.exit(1)


def winepath_unix_to_windows(unix_path, env=None):
    try:
        result = subprocess.run(
            ["winepath", "-w", str(unix_path)],
            capture_output=True, encoding="utf-8",
            check=True, env=env
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        p = Path(unix_path).resolve()
        win_path = str(p).replace("/", "\\")
        return f"Z:{win_path}"


def wine_registry_get(path, value, env=None):
    try:
        result = subprocess.run(
            ["wine", "reg", "query", path, "/v", value],
            capture_output=True, encoding="utf-8",
            check=True, env=env
        )
        for line in result.stdout.splitlines():
            if value in line:
                parts = line.strip().split(None, 2)
                if len(parts) >= 3:
                    return parts[2]
        return ""
    except subprocess.CalledProcessError:
        return ""


def get_current_wine_path(env=None):
    return wine_registry_get(
        r"HKEY_CURRENT_USER\Environment",
        "PATH",
        env=env
    )


def set_wine_path(path_value, env=None):
    subprocess.run(
        ["wine", "reg", "add", r"HKEY_CURRENT_USER\Environment",
         "/v", "PATH", "/t", "REG_EXPAND_SZ", "/d", path_value, "/f"],
        check=True, capture_output=True, env=env
    )


def delete_wine_path(env=None):
    subprocess.run(
        ["wine", "reg", "delete", r"HKEY_CURRENT_USER\Environment",
         "/v", "PATH", "/f"],
        check=False, capture_output=True, env=env
    )


def _normalize_wine_path(path):
    """Wine treats both slash kinds as equivalent; unify for comparison."""
    return path.strip().rstrip("\\/").replace("\\", "/").lower()


def _register_bin_to_prefix(wineprefix, bin_dir):
    """Move the bin directory to the front of the prefix's registry PATH.
    Returns True if it already is at the front."""
    env = os.environ.copy()
    env["WINEPREFIX"] = str(wineprefix)
    env["LC_ALL"] = "C.UTF-8"

    current_path = get_current_wine_path(env=env)
    win_bin_path = winepath_unix_to_windows(bin_dir, env=env)

    norm_target = _normalize_wine_path(win_bin_path)
    original_entries = [p for p in current_path.split(";") if p.strip()]
    norm_entries = [_normalize_wine_path(p) for p in original_entries]

    if norm_entries and norm_entries[0] == norm_target:
        return True

    filtered = [p for p in original_entries if _normalize_wine_path(p) != norm_target]

    new_path = win_bin_path
    if filtered:
        new_path += ";" + ";".join(filtered)

    if new_path != current_path:
        set_wine_path(new_path, env=env)

    return False


def _set_pango_backend(wineprefix):
    """Force the fontconfig Pango backend: the PangoWin32 default bypasses
    Wine's FontSubstitutes/FontLink fallback mechanism."""
    env = os.environ.copy()
    env["WINEPREFIX"] = str(wineprefix)
    env["LC_ALL"] = "C.UTF-8"
    subprocess.run(
        ["wine", "reg", "add", r"HKEY_CURRENT_USER\Environment",
         "/v", "PANGOCAIRO_BACKEND", "/t", "REG_SZ",
         "/d", "fontconfig", "/f"],
        check=True, capture_output=True, env=env
    )


def _delete_pango_backend(wineprefix):
    """Remove PANGOCAIRO_BACKEND only if we set it (value is 'fontconfig')."""
    env = os.environ.copy()
    env["WINEPREFIX"] = str(wineprefix)
    env["LC_ALL"] = "C.UTF-8"

    current = wine_registry_get(
        r"HKEY_CURRENT_USER\Environment",
        "PANGOCAIRO_BACKEND",
        env=env
    )
    if current != "fontconfig":
        return

    subprocess.run(
        ["wine", "reg", "delete", r"HKEY_CURRENT_USER\Environment",
         "/v", "PANGOCAIRO_BACKEND", "/f"],
        check=False, capture_output=True, env=env
    )


def cmd_init(args):
    env_name = args.env
    wineprefix = resolve_wineprefix(env_name, args.prefix)

    info(f"Initializing Wine integration for {env_name}...")
    info(f"WINEPREFIX: {wineprefix}")

    ensure_wine()

    wineprefix.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["WINEPREFIX"] = str(wineprefix)
    # winemenubuilder would pollute the host with desktop/MIME entries
    env["WINEDLLOVERRIDES"] = "winemenubuilder.exe=d"

    info("Initializing Wine prefix...")
    result = subprocess.run(["wineboot", "--init"], env=env, check=False)
    if result.returncode != 0:
        warn("wineboot failed; prefix may be incomplete")

    info("Configuring font backend...")
    try:
        _set_pango_backend(wineprefix)
    except subprocess.CalledProcessError as e:
        warn(f"Failed to set font backend: {e}")

    bin_dir = get_bin_dir(env_name)
    if bin_dir.exists():
        info("Registering bin directory to Wine PATH...")
        try:
            already = _register_bin_to_prefix(wineprefix, bin_dir)
            if already:
                info("Already registered")
            else:
                info("Registered to Wine PATH")
        except subprocess.CalledProcessError as e:
            warn(f"Failed to register PATH: {e}")

    info(f"Wine integration initialized for {env_name}")
    return 0


def cmd_register(args):
    """Register the bin directory to the user's existing Wine prefix
    ($WINEPREFIX or ~/.wine), not the project-managed one."""
    env_name = args.env
    wineprefix = resolve_wineprefix(env_name, args.prefix, prefer_user=True)
    bin_dir = get_bin_dir(env_name)

    if not bin_dir.exists():
        warn(f"Bin directory not found: {bin_dir}")
        warn(f"Install some packages first: linsys2-pacman --env {env_name} -S ...")
        return 1

    ensure_wine()

    try:
        already = _register_bin_to_prefix(wineprefix, bin_dir)
    except subprocess.CalledProcessError as e:
        error(f"Failed to modify Wine registry: {e}")
        return 1

    if already:
        info(f"Already registered in {wineprefix}")
    else:
        info(f"Registered {env_name} bin directory to Wine PATH")
        info(f"Target prefix: {wineprefix}")

    try:
        _set_pango_backend(wineprefix)
    except subprocess.CalledProcessError as e:
        error(f"Failed to set font backend: {e}")
        return 1

    info("Restart Wine applications for changes to take effect")
    return 0


def cmd_unregister(args):
    """Remove the bin directory from the user's existing Wine prefix."""
    env_name = args.env
    wineprefix = resolve_wineprefix(env_name, args.prefix, prefer_user=True)
    bin_dir = get_bin_dir(env_name)

    ensure_wine()

    env = os.environ.copy()
    env["WINEPREFIX"] = str(wineprefix)
    env["LC_ALL"] = "C.UTF-8"

    current_path = get_current_wine_path(env=env)
    win_bin_path = winepath_unix_to_windows(bin_dir, env=env)

    norm_target = _normalize_wine_path(win_bin_path)
    path_entries = [_normalize_wine_path(p) for p in current_path.split(";") if p.strip()]
    if norm_target not in path_entries:
        warn(f"Not registered: {win_bin_path}")
        return 0

    parts = [p for p in current_path.split(";")
             if _normalize_wine_path(p) != norm_target]
    new_path = ";".join(parts)

    info(f"Unregistering from Wine PATH: {win_bin_path}")
    try:
        if new_path:
            set_wine_path(new_path, env=env)
        else:
            delete_wine_path(env=env)
    except subprocess.CalledProcessError as e:
        error(f"Failed to modify Wine registry: {e}")
        return 1

    # Drop the font backend only when no other LinSYS2 environment remains
    remaining_entries = [_normalize_wine_path(p) for p in new_path.split(";") if p.strip()]
    has_other_linsys2 = False
    for other_env_name in ENVIRONMENTS:
        if other_env_name == env_name:
            continue
        other_bin_dir = get_bin_dir(other_env_name)
        other_win_bin_path = winepath_unix_to_windows(other_bin_dir, env=env)
        if _normalize_wine_path(other_win_bin_path) in remaining_entries:
            has_other_linsys2 = True
            break

    if not has_other_linsys2:
        try:
            _delete_pango_backend(wineprefix)
        except subprocess.CalledProcessError as e:
            error(f"Failed to remove font backend: {e}")
    else:
        info("Other LinSYS2 environments remain registered, keeping font backend")

    info(f"Unregistered {env_name} bin directory from Wine PATH")
    return 0


def cmd_env(args):
    env_name = args.env
    wineprefix = resolve_wineprefix(env_name, args.prefix, prefer_user=True)
    bin_dir = get_bin_dir(env_name)

    print(f"Environment: {env_name}")
    print(f"WINEPREFIX:  {wineprefix}")
    print(f"Bin dir:     {bin_dir}")
    if bin_dir.exists():
        print(f"  Status:    exists ({sum(1 for _ in bin_dir.iterdir())} items)")
    else:
        print(f"  Status:    not found")

    ensure_wine()

    env = os.environ.copy()
    env["WINEPREFIX"] = str(wineprefix)
    env["LC_ALL"] = "C.UTF-8"

    current_path = get_current_wine_path(env=env)
    win_bin_path = winepath_unix_to_windows(bin_dir, env=env)

    print(f"\nWine PATH:")
    registered = False
    norm_win_bin = _normalize_wine_path(win_bin_path)
    for i, p in enumerate(current_path.split(";"), 1):
        if p.strip():
            marker = "  *" if _normalize_wine_path(p) == norm_win_bin else "   "
            print(f"{marker} {i}. {p.strip()}")
            if _normalize_wine_path(p) == norm_win_bin:
                registered = True

    print(f"\nRegistration status: {'registered' if registered else 'not registered'}")

    pango_backend = wine_registry_get(
        r"HKEY_CURRENT_USER\Environment",
        "PANGOCAIRO_BACKEND",
        env=env
    )
    print(f"Font backend:    {pango_backend if pango_backend else 'default (PangoWin32)'}")
    return 0


def cmd_run(args):
    env_name = args.env
    wineprefix = resolve_wineprefix(env_name, args.prefix)
    bin_dir = get_bin_dir(env_name)

    program = args.program
    program_args = args.args

    ensure_wine()

    is_simple_name = "/" not in program and "\\" not in program

    if is_simple_name:
        if not bin_dir.exists():
            error(f"No packages installed for {env_name}")
            error(f"Run: linsys2-pacman init --env {env_name}")
            error(f"Then: linsys2-pacman --env {env_name} -Syu <package>")
            return 1

        candidates = [program]
        if not program.endswith(".exe"):
            candidates.append(program + ".exe")

        program_path = None
        for candidate in candidates:
            candidate_path = bin_dir / candidate
            if candidate_path.exists():
                program_path = candidate_path
                break

        if program_path is None:
            error(f"Program not found: {program}")
            error(f"Searched in: {bin_dir}")
            return 1
    else:
        program_path = Path(program)

    if not wineprefix.exists():
        warn(f"WINEPREFIX not initialized: {wineprefix}")
        warn(f"Run: linsys2 init --env {env_name}")

    env = os.environ.copy()
    env["WINEPREFIX"] = str(wineprefix)
    env["WINEDLLOVERRIDES"] = "winemenubuilder.exe=d"
    env["PANGOCAIRO_BACKEND"] = "fontconfig"

    if bin_dir.exists():
        winepath_env = env.copy()
        winepath_env["LC_ALL"] = "C.UTF-8"
        try:
            wine_lib_path = subprocess.run(
                ["winepath", "-w", str(bin_dir)],
                capture_output=True, encoding="utf-8",
                check=True, env=winepath_env
            ).stdout.strip()
            env["WINEPATH"] = wine_lib_path
        except subprocess.CalledProcessError:
            warn("winepath failed; DLL search may be incomplete")

    cmd = ["wine", str(program_path)] + program_args
    return subprocess.run(cmd, env=env).returncode


def cmd_shell(args):
    env_name = args.env
    wineprefix = resolve_wineprefix(env_name, args.prefix)
    bin_dir = get_bin_dir(env_name)

    if not wineprefix.exists():
        warn(f"WINEPREFIX not initialized: {wineprefix}")
        warn(f"Run: linsys2 init --env {env_name}")

    if not bin_dir.exists():
        warn(f"No packages installed for {env_name}")
        warn(f"Run: linsys2-pacman init --env {env_name}")
        warn(f"Then: linsys2-pacman --env {env_name} -S <package>")

    ensure_wine()

    env = os.environ.copy()
    env["WINEPREFIX"] = str(wineprefix)
    env["WINEDLLOVERRIDES"] = "winemenubuilder.exe=d"
    env["PANGOCAIRO_BACKEND"] = "fontconfig"

    if bin_dir.exists():
        old_path = env.get("PATH")
        env["PATH"] = f"{bin_dir}" + (":" + old_path if old_path else "")
        winepath_env = env.copy()
        winepath_env["LC_ALL"] = "C.UTF-8"
        try:
            wine_lib_path = subprocess.run(
                ["winepath", "-w", str(bin_dir)],
                capture_output=True, encoding="utf-8",
                check=True, env=winepath_env
            ).stdout.strip()
            env["WINEPATH"] = wine_lib_path
        except subprocess.CalledProcessError:
            warn("winepath failed; DLL search may be incomplete")

    shell = os.environ.get("SHELL", "/bin/bash")
    info(f"Starting shell with {env_name} Wine environment...")
    info(f"WINEPREFIX: {wineprefix}")
    info(f"Type 'exit' to leave")

    return subprocess.run([shell], env=env).returncode


def main():
    argv = sys.argv[1:]

    if argv and argv[0] in ("-v", "--version"):
        print(f"linsys2 {__version__}")
        return 0

    env_choices = list(ENVIRONMENTS.keys())

    parser = argparse.ArgumentParser(
        prog="linsys2",
        description="Wine integration for LinSYS2 mingw-w64 environments",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND",
                                title="commands")

    def _add_common(p):
        p.add_argument("--env", default=DEFAULT_ENV, choices=env_choices,
                       help=f"target environment (default: {DEFAULT_ENV})")
        p.add_argument("--prefix", default=None,
                       help="WINEPREFIX path")

    p = sub.add_parser("init", help="Initialize Wine prefix for an environment")
    _add_common(p)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("register", help="Register bin dir to Wine PATH")
    _add_common(p)
    p.set_defaults(func=cmd_register)

    p = sub.add_parser("unregister", help="Remove bin dir from Wine PATH")
    _add_common(p)
    p.set_defaults(func=cmd_unregister)

    p = sub.add_parser("env", help="Show Wine environment configuration")
    _add_common(p)
    p.set_defaults(func=cmd_env)

    p = sub.add_parser(
        "run",
        help="Run a Windows program with environment integrated",
        description="Run a Windows program with the specified environment integrated.\n\n"
                    "Usage: linsys2 run [OPTIONS] <program> [args...]",
        epilog="Use -- to separate linsys2 options from program options:\n"
               "  linsys2 run --env clang64 -- gcc --version",
    )
    _add_common(p)
    p.add_argument("program", help="Program to run")
    p.add_argument("args", nargs=argparse.REMAINDER, default=[],
                   help="Arguments to pass to the program")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("shell",
                        help="Start a shell with Wine environment configured")
    _add_common(p)
    p.set_defaults(func=cmd_shell)

    try:
        args = parser.parse_args()
    except SystemExit as e:
        return e.code

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)
