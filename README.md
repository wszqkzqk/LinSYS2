# LinSYS2

<div align="center">
  <img src="logo.svg" alt="LinSYS2" width="450">
</div>

[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2+-blue.svg)](COPYING)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/wszqkzqk/LinSYS2)

LinSYS2 installs the [MSYS2](https://www.msys2.org/) Windows package ecosystem on Linux: the same Windows toolchain and libraries that run on Windows, executed through [Wine](https://www.winehq.org/). No VM, no dual-boot, no containers.

It also builds MSYS2 packages on Linux: `linsys2-makepkg` compiles [MINGW-packages](https://github.com/msys2/MINGW-packages) PKGBUILDs natively, like MSYS2's `makepkg-mingw` but without Windows.

---

## Quick Start

```bash
# One-time setup
linsys2-pacman init

# Install a Windows compiler
linsys2-pacman -Sy mingw-w64-ucrt-x86_64-gcc

# Run it on Linux. No VM needed.
linsys2 run -- gcc -v
```

---

## Why LinSYS2

Traditional cross-compilation uses a Linux port of the MinGW toolchain: the build process differs from Windows, and you cannot run or debug the result.

LinSYS2 installs the actual Windows toolchain from MSYS2, so compiling, debugging, and running work exactly as they do on Windows, from your Linux shell. The same goes for packaging: `linsys2-makepkg` builds MSYS2's MINGW-packages PKGBUILDs on Linux, with the build behaving as it does on Windows.

| | Traditional Cross-Compile | LinSYS2 |
|---|---|---|
| Build toolchain | Linux port of MinGW | Windows Compiler from MSYS2 |
| Build behavior | May differ from Windows | Identical to Windows |
| Build MSYS2 packages (PKGBUILD) | No | Yes (`linsys2-makepkg`) |
| Run binaries | No | Yes (through Wine) |
| Debug with Windows GDB | No | Yes |
| Libraries | Linux-distro packaged | Identical to Windows |
| Package manager | Distro or manual | MSYS2 pacman |

---

## Features

- Same toolchain as Windows: the Windows GCC/LLVM, GDB/LLDB, and CMake/Meson from MSYS2, not a Linux cross-compiler port
- Build MSYS2 packages on Linux: `linsys2-makepkg` builds MINGW-packages PKGBUILDs natively, like `makepkg-mingw` (experimental)
- Full dev lifecycle on Linux: install packages, compile, debug, run tests, and ship Windows binaries from your Linux shell
- Runs through Wine at near-native speed, no VM or containers
- Everything lives in `~/.local/share/linsys2/`, no root or system conflicts
- Multiple targets (ucrt64, clang64, clangarm64) from one machine

---

## How It Works

LinSYS2 has three commands:

| Command | Purpose |
|---------|---------|
| `linsys2-pacman` | Package management: install, remove, and upgrade Windows packages from MSYS2 repos |
| `linsys2` | Wine integration: run programs, manage PATH registration, inspect environments |
| `linsys2-makepkg` | Package building (experimental): build [MINGW-packages](https://github.com/msys2/MINGW-packages) PKGBUILDs on Linux, like MSYS2's `makepkg-mingw` |

`linsys2-pacman` runs the patched [MSYS2 fork of pacman](https://github.com/msys2/msys2-pacman) built for Linux, pointed at MSYS2's official repositories. Packages install to `~/.local/share/linsys2/`.

`linsys2 run` uses an isolated Wine prefix and injects the environment via `WINEPATH`, so there is no setup, no registry changes, and no interference with your existing `~/.wine`. If you prefer, `linsys2 register` adds the environment to your existing Wine installation instead.

---

## Installation

### Arch Linux

From AUR (recommended):

```bash
# Using yay
yay -S linsys2

# Or using paru
paru -S linsys2
```

Or build manually:

```bash
git clone --recursive https://github.com/wszqkzqk/LinSYS2.git
cd LinSYS2
makepkg -si
```

### Other distributions

Other distributions should install the equivalent packages under their own package names.

* Build dependencies: `meson ninja-build gcc git patch pkg-config libarchive libssl libgpgme libcurl`
* Runtime dependencies: `bash coreutils gawk grep gettext which curl gnupg openssl libarchive bsdtar bzip2 xz zstd wine python bubblewrap`

On Debian/Ubuntu:

```bash
sudo apt install meson ninja-build gcc git patch pkg-config \
    libarchive-dev libarchive-tools libssl-dev libgpgme-dev libcurl4-openssl-dev \
    bzip2 xz zstd curl \
    gawk gettext which gnupg wine python3 bubblewrap
```

On Fedora:

```bash
sudo dnf install meson ninja-build gcc git patch pkg-config \
    libarchive-devel bsdtar openssl-devel gpgme-devel libcurl-devel \
    bzip2 xz zstd curl \
    gawk gettext which gnupg wine python3 bubblewrap
```

Build and install (the toolchain lands in its private home
`/usr/lib/linsys2-pacman`; only the three commands go to `/usr/bin`):

```bash
git clone --recursive https://github.com/wszqkzqk/LinSYS2.git
cd LinSYS2
meson setup build
meson compile -C build
sudo meson install -C build
```

---

## Usage

### Package Management (`linsys2-pacman`)

```bash
# One-time setup
linsys2-pacman init

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

### Build, Debug, Run (`linsys2`)

#### Isolated Wine Prefix

`linsys2 run` works out of the box. It uses an isolated Wine prefix under `~/.local/share/linsys2/` and injects the environment's bin directory via `WINEPATH`, so there is no prior setup, no registry changes, and no interference with your existing Wine installation.

```bash
# Compile a Windows executable with Windows GCC
linsys2 run -- gcc -o app.exe app.c

# Debug it with Windows GDB
linsys2 run -- gdb app.exe

# Build a CMake project the Windows way
linsys2 run -- cmake -B build -S .
linsys2 run -- cmake --build build

# Run any installed Windows program
linsys2 run -- python --version
# Run your own Windows executable
linsys2 run -- ./example.exe --your-flags

# Or drop into a shell where all Windows tools are in PATH
linsys2 shell
```

Always use `--` to separate `linsys2` options from the program's own flags.

#### Existing Wine Integration

Your existing Wine environment (`~/.wine` or `$WINEPREFIX`) is also supported:

```bash
linsys2 register    # add bin directory to your Wine PATH registry
linsys2 env         # inspect registration
linsys2 unregister  # remove from Wine PATH
```

### Building Packages (`linsys2-makepkg`, experimental)

`linsys2-makepkg` is experimental: many packages build fine, but expect rough edges and per-package quirks.

It builds [MINGW-packages](https://github.com/msys2/MINGW-packages) PKGBUILDs directly on Linux, like MSYS2's `makepkg-mingw` but without Windows. The PKGBUILD shell logic runs natively; the Windows toolchain (GCC/Clang, CMake, ...) installed by `linsys2-pacman` runs through Wine:

* `binfmt_misc` runs PE binaries through Wine transparently, so `foo.exe` is directly executable, including configure's freshly compiled test programs.
* Bare names like `gcc` resolve through small wrapper scripts in a private shim directory (`build-bin/`) that exec the real `.exe` via Wine with the environment's `WINEPREFIX`.
* The build runs inside a private `bubblewrap` mount namespace where the environment prefix is bind-mounted at its canonical location (`/ucrt64`, ...).

```bash
# Clone MINGW-packages and build a package
git clone https://github.com/msys2/MINGW-packages.git
cd MINGW-packages/mingw-w64-zlib

# One-time setup of the environments you build for
linsys2-pacman init
linsys2-pacman init --env clang64

# Build (installs mingw build dependencies into the environment with -s)
linsys2-makepkg -s

# Target a non-default environment
linsys2-makepkg --env clang64 -s

# Build for several environments in one go (like makepkg-mingw)
MINGW_ARCH="ucrt64 clang64" linsys2-makepkg -s

# Install the result into the matching environment
linsys2-pacman -U mingw-w64-ucrt-x86_64-zlib-*-any.pkg.tar.zst
linsys2-pacman --env clang64 -U mingw-w64-clang-x86_64-zlib-*-any.pkg.tar.zst
```

All state stays inside `~/.local/share/linsys2/<env>/`; builds only write to the PKGBUILD directory (`src/`, `pkg/`, `*.pkg.tar.zst`), following makepkg conventions.

Building also needs a one-time root setup: the kernel's `binfmt_misc` must dispatch Windows binaries to Wine. Most distributions already register this (systemd's `DOSWin` entry). If yours does not:

```bash
echo ':DOSWin:M::MZ::/usr/bin/wine:F' | sudo tee /etc/binfmt.d/linsys2-wine.conf
sudo systemctl restart systemd-binfmt
```

In a container, register on the host; the `F` flag makes it work inside the container too.

Known limitations: `check()` is disabled by default because test suites usually cannot run in this setup (pass `--check` to force it); `.bat`/`.cmd` build scripts run through `wine cmd`; packages with unusual Windows-only build steps may need per-package adjustments; a build kills all Windows processes running in the selected Wine prefix (it restarts the prefix's `wineserver` on entry and exit).

---

## Environments

| Name | Compiler | Default On |
|------|----------|-----------|
| `ucrt64` | GCC and Clang | x86_64 |
| `clang64` | Clang Only | — |
| `clangarm64` | Clang Only | ARM64 |

The default is auto-detected from your CPU. Override with `--env`.

---

## License

* [GPL v2 or later](COPYING).
* The pacman binaries are built from [MSYS2 pacman](https://github.com/msys2/msys2-pacman) sources with additional patches, also GPL v2+.

---

## Acknowledgments

- [MSYS2](https://www.msys2.org/) — the pacman fork and package ecosystem
- [Arch Linux](https://archlinux.org/) — original pacman
- [Wine](https://www.winehq.org/) — the Windows compatibility layer
