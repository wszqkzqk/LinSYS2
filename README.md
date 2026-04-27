# LinSYS2

[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2+-blue.svg)](COPYING)

**Build Windows programs with full MSYS2 ecosystem on Linux. No VM. No dual-boot. No containers.**

LinSYS2 brings the [MSYS2](https://www.msys2.org/) package ecosystem to Linux. Install thousands of native Windows libraries and tools directly from MSYS2 repositories, cross-compile Windows executables, and run them through [Wine](https://www.winehq.org/) — all from your Linux terminal.

---

## Features

- **Full MSYS2 ecosystem** — thousands of packages: GCC, Clang, CMake, Qt, OpenSSL, FFmpeg, and more
- **No VM, no emulation** — programs run through Wine at near-native speed
- **User-level isolation** — everything lives in `~/.local/share/`. No root, no system conflicts
- **Cross-compilation from Linux** — build Windows executables, DLLs, and libraries in your CI/CD pipelines
- **Multi-target** — ucrt64, clang64, and clangarm64 environments from a single machine

---

## How It Works

LinSYS2 has two commands:

| Command | Purpose |
|---------|---------|
| `linsys2-pacman` | Package management — install, remove, and upgrade Windows packages from MSYS2 repos |
| `linsys2` | Wine integration — run programs, manage PATH registration, inspect environments |

Under the hood, `linsys2-pacman` runs the patched [MSYS2 fork of pacman](https://github.com/msys2/msys2-pacman) built for Linux, pointed at MSYS2's official repositories. Packages go to `~/.local/share/linsys2-pacman/`. `linsys2` manages Wine prefixes and PATH so programs just work.

---

## Installation

### Arch Linux

```bash
git clone --recursive https://github.com/wszqkzqk/LinSYS2.git
cd LinSYS2
makepkg -si
```

## Quick Start

```bash
# Install a Windows compiler
linsys2-pacman -Sy mingw-w64-ucrt-x86_64-gcc

# Run it on Linux. No VM needed.
linsys2 run -- gcc -v
```

Two commands. You just installed and ran a Windows program without leaving Linux.

---

### Other distributions

* **Build dependencies:** `meson ninja gcc make git libarchive`
* **Runtime dependencies:** `curl gnupg libarchive wine`

```bash
git clone --recursive https://github.com/wszqkzqk/LinSYS2.git
cd LinSYS2
make && sudo make PREFIX=/usr install
```

---

## Usage

### Package Management (`linsys2-pacman`)

`linsys2-pacman` is a transparent pacman wrapper. All standard pacman operations work:

```bash
# Sync databases and upgrade
linsys2-pacman -Syu

# Install packages
linsys2-pacman -Sy mingw-w64-ucrt-x86_64-gcc

# Search
linsys2-pacman -Ss zlib

# Remove
linsys2-pacman -R mingw-w64-ucrt-x86_64-cmake

# List installed packages
linsys2-pacman -Q

# Target a different environment
linsys2-pacman --env clang64 -S mingw-w64-clang-x86_64-llvm
```

### Running Windows Programs (`linsys2`)

```bash
# One-time: initialize Wine prefix (auto-registers bin to PATH)
linsys2 init

# Run a program from the installed environment
linsys2 run -- gcc --version

# Run your own Windows executable
linsys2 run -- ./my-app.exe --some-flag

# Register bin directory to your existing Wine installation
linsys2 register

# Start an interactive shell with the Windows environment in PATH
linsys2 shell

# Inspect environment and PATH registration
linsys2 env

# Remove from Wine PATH
linsys2 unregister
```

> **Recommend to use `--`** to separate `linsys2` options from the program's own flags. This prevents conflicts like `-E` (preprocessor flag) vs. the `--env` option.

---

## Environments

| Name | Compiler | Default On |
|------|----------|-----------|
| `ucrt64` | GCC (UCRT) | x86_64 |
| `clang64` | Clang (UCRT) | — |
| `clangarm64` | Clang (UCRT) | ARM64 |

The default is auto-detected from your CPU. Override with `--env`.

---

## License

[GPL v2 or later](COPYING). The pacman binaries are built from [MSYS2 pacman](https://github.com/msys2/msys2-pacman) sources with additional patches, also GPL v2+.

---

## Acknowledgments

- [MSYS2](https://www.msys2.org/) — the pacman fork and package ecosystem
- [Arch Linux](https://archlinux.org/) — original pacman
- [Wine](https://www.winehq.org/) — the Windows compatibility layer
