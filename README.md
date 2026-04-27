# LinSYS2

[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2+-blue.svg)](COPYING)

Manage [MSYS2](https://www.msys2.org/) mingw-w64 packages on Linux, and run them through [Wine](https://www.winehq.org/).

## Overview

LinSYS2 lets you install, manage, and upgrade Windows programs from the MSYS2 ecosystem directly on Linux. It builds the MSYS2 fork of [pacman](https://gitlab.archlinux.org/pacman/pacman) for Linux, creating fully isolated user-level environments for each mingw-w64 target.

## Features

- **No package repository fork** — Uses MSYS2 official repositories directly
- **User-level isolation** — All data stored in `~/.local/share/linsys2-pacman/`
- **No root required** — Runs entirely as a regular user
- **Transparent pacman interface** — Native pacman syntax with `--env` selector
- **Wine integration** — Dedicated `linsys2` tool for PATH management and execution
- **Multi-environment** — Supports ucrt64, clang64, clangarm64
- **Architecture-aware defaults** — Auto-detects ARM (clangarm64) vs x86_64 (ucrt64)

## Installation

### From source (Arch Linux)

```bash
git clone --recursive https://github.com/wszqkzqk/LinSYS2.git
cd LinSYS2
makepkg -si
```

### Quick build (development)

```bash
git clone --recursive https://github.com/wszqkzqk/LinSYS2.git
cd LinSYS2
make PREFIX="$PWD/dist" install
export PATH="$PWD/dist/bin:$PATH"
```

### Updating the default submodule version (maintainers)

```bash
# Test a new upstream version
make SUBMODULE_VERSION=v6.1.0 clean build

# Permanently bump the submodule pointer in the repository
make bump-submodule SUBMODULE_VERSION=v6.1.0
git diff --cached   # review
git commit -m "Bump msys2-pacman to v6.1.0"
```

## Quick Start

### 1. Initialize an environment

```bash
linsys2-pacman init --env ucrt64
```

### 2. Sync package databases

```bash
linsys2-pacman -Sy
```

### 3. Install packages

```bash
linsys2-pacman -S mingw-w64-ucrt-x86_64-gcc
```

### 4. Run programs

Using the Wine wrapper (recommended):

```bash
linsys2 init
linsys2 register
linsys2 run gcc --version
```

Or manually:

```bash
wine ~/.local/share/linsys2-pacman/ucrt64/ucrt64/bin/gcc.exe --version
```

## Usage

### `linsys2-pacman` — Package Management

All pacman operations are transparently forwarded. `--env` is intercepted by the wrapper; if omitted, the default environment is auto-detected (`ucrt64` on x86_64, `clangarm64` on ARM).

```bash
# Install (uses default environment)
linsys2-pacman -S mingw-w64-ucrt-x86_64-cmake

# Remove
linsys2-pacman -R mingw-w64-ucrt-x86_64-cmake

# Upgrade all
linsys2-pacman -Syu

# Search
linsys2-pacman -Ss zlib

# Query installed
linsys2-pacman -Q

# Show package info
linsys2-pacman -Qi mingw-w64-ucrt-x86_64-gcc

# Use a non-default environment
linsys2-pacman --env clang64 -S mingw-w64-clang-x86_64-llvm
```

### `linsys2` — Wine Integration

Manages WINEPREFIX and Wine PATH registration for seamless execution.

```bash
# Register default environment to Wine PATH
linsys2 register

# Remove from Wine PATH
linsys2 unregister

# Show environment configuration (PATH, WINEPREFIX, etc.)
linsys2 env

# Run a program (searches in environment bin)
linsys2 run gcc --version

# Start a shell with Wine env configured
linsys2 shell
```

### `linsys2-pacman` Subcommands

```bash
# Initialize default environment
linsys2-pacman init

# Interactive shell with environment PATH
linsys2-pacman shell
```

## Environments

| Environment | Prefix | Default On |
|-------------|--------|-----------|
| `ucrt64` | `mingw-w64-ucrt-x86_64` | x86_64 (recommended) |
| `clang64` | `mingw-w64-clang-x86_64` | — |
| `clangarm64` | `mingw-w64-clang-aarch64` | ARM64 (aarch64) |

The default environment is automatically detected from the host architecture:
- `x86_64` → `ucrt64`
- `aarch64` / `arm64` → `clangarm64`

## Project Structure

```
LinSYS2/
├── COPYING                    # GPL v2 or later
├── Makefile                   # Unified build system
├── PKGBUILD                   # Arch Linux packaging
├── README.md
├── bin/
│   ├── linsys2-pacman         # Package management wrapper
│   └── linsys2           # Wine integration wrapper
├── configs/
│   └── pacman.conf.template   # Configuration template
├── patches/
│   └── 0001-LinSYS2-Adapt-MSYS2-pacman-for-Linux.patch
└── src/
    └── msys2-pacman (submodule)  # Clean MSYS2 pacman fork
```

## Technical Details

### Why build the MSYS2 pacman fork?

MSYS2 changed the epoch separator from `:` to `~` (Windows filenames cannot contain `:`). Using the unmodified Arch pacman would fail to parse MSYS2 package versions correctly.

### Linux adaptations

The patch `0001-LinSYS2-Adapt-MSYS2-pacman-for-Linux.patch` extends MSYS2's `#ifdef __MSYS__` blocks to also activate on Linux via `-DMSYS2_PACMAN_LINUX`:

- `~` epoch separator support
- Skip root permission checks (user-level operation)
- Skip UID/GID checks (packages in user directories)
- Fixed tool paths and CR handling

### Security isolation

Each environment has independent:
- `RootDir` — package installation root
- `DBPath` — local and sync databases
- `CacheDir` — downloaded package cache
- `GPGDir` — PGP keyring
- `LogFile` — operation logs

No conflicts with system pacman (`/var/lib/pacman`, `/etc/pacman.conf`).

## Dependencies

Build:
- `meson`, `ninja`
- `gcc`
- `git`
- `libarchive`

Runtime:
- `bash`
- `curl`
- `gnupg`
- `wine` (for running Windows programs)

## License

GPL v2 or later — see [COPYING](COPYING).

The wrapper scripts and build infrastructure are part of this project. The pacman binaries are built from [MSYS2 sources](https://github.com/msys2/msys2-pacman), which are also GPL v2 or later.

## Acknowledgments

- [MSYS2](https://www.msys2.org/) — pacman fork and package repositories
- [Arch Linux](https://archlinux.org/) — original pacman package manager
