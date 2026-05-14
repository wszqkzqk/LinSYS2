#
# LinSYS2 Makefile
# Unified build system for MSYS2 pacman on Linux
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

PREFIX ?= /usr
DESTDIR ?=

SUBMODULE = vendor/msys2-pacman
PATCHES = patches/0001-LinSYS2-Adapt-MSYS2-pacman-for-Linux.patch \
          patches/0002-LinSYS2-Accept-non-mingw-deps-as-host-provided.patch \
          patches/0003-LinSYS2-Install-bash-completion-under-prefix.patch \
          patches/0004-LinSYS2-Skip-chroot-scriptlet-execution.patch
BUILD_DIR = $(SUBMODULE)/build
PATCH_STAMP = $(SUBMODULE)/.linsys2-patched.stamp

KEYRING_SUBMODULE = vendor/msys2-keyring
KEYRING_DIR = $(DESTDIR)$(PRIVATE_PREFIX)/share/pacman/keyrings

PRIVATE_PREFIX = $(PREFIX)/lib/linsys2-pacman
PACMAN_CFLAGS = -DMSYS2_PACMAN_LINUX

VERSION := $(shell \
	count=$$(git rev-list --count HEAD 2>/dev/null); \
	date=$$(git log -1 --format=%cd --date=format:%Y%m%d 2>/dev/null); \
	hash=$$(git rev-parse --short HEAD 2>/dev/null); \
	if [ -n "$$count" ] && [ -n "$$date" ] && [ -n "$$hash" ]; then \
		printf "r%s.%s.%s" "$$count" "$$date" "$$hash"; \
	else \
		echo "unknown"; \
	fi)

.PHONY: all build configure install clean checkout bump-submodule bump-keyring

all: build

$(SUBMODULE)/.git $(KEYRING_SUBMODULE)/.git &:
	git submodule update --init --recursive

checkout: $(SUBMODULE)/.git $(KEYRING_SUBMODULE)/.git
ifdef SUBMODULE_VERSION
	@cd $(SUBMODULE) && git fetch origin $(SUBMODULE_VERSION) 2>/dev/null || true
	@cd $(SUBMODULE) && git checkout $(SUBMODULE_VERSION)
endif

$(PATCH_STAMP): $(PATCHES) | checkout
	@echo "[LinSYS2] Applying patches..."
	@cd $(SUBMODULE) && git checkout -- .
	@for p in $(PATCHES); do \
		(cd $(SUBMODULE) && patch -p1 -i "../../$$p") || exit 1; \
	done
	@touch $@

configure: $(PATCH_STAMP)
	@test -f $(BUILD_DIR)/build.ninja || \
		(echo "[LinSYS2] Configuring meson..." && \
		 cd $(SUBMODULE) && meson setup build \
			--prefix=$(PRIVATE_PREFIX) \
			--libdir=$(PRIVATE_PREFIX)/lib \
			--sysconfdir=$(PRIVATE_PREFIX)/etc \
			--localstatedir=$(PRIVATE_PREFIX)/var \
			--buildtype=release \
			--default-library=shared \
			-Dscriptlet-shell=/bin/bash \
			-Dpkg-ext=.pkg.tar.zst \
			-Dbuildstatic=false \
			-Dc_args="$(PACMAN_CFLAGS)" \
			-Dcpp_args="$(PACMAN_CFLAGS)")

build: configure
	@cd $(SUBMODULE) && ninja -C build

install:
	@test -f $(BUILD_DIR)/pacman || \
		(echo "ERROR: Build artifacts not found. Run 'make build' first." && exit 1)
	cd $(SUBMODULE) && DESTDIR=$(DESTDIR) ninja -C build install
	@rm -rf $(DESTDIR)$(PRIVATE_PREFIX)/share/bash-completion
	install -Dm644 $(KEYRING_SUBMODULE)/msys2.gpg $(KEYRING_DIR)/msys2.gpg
	install -Dm644 $(KEYRING_SUBMODULE)/msys2-trusted $(KEYRING_DIR)/msys2-trusted
	install -Dm644 $(KEYRING_SUBMODULE)/msys2-revoked $(KEYRING_DIR)/msys2-revoked
	@mkdir -p $(DESTDIR)$(PREFIX)/bin
	@sed 's/@VERSION@/$(VERSION)/g' scripts/linsys2-pacman > $(DESTDIR)$(PREFIX)/bin/linsys2-pacman
	@chmod 755 $(DESTDIR)$(PREFIX)/bin/linsys2-pacman
	@sed 's/@VERSION@/$(VERSION)/g' scripts/linsys2 > $(DESTDIR)$(PREFIX)/bin/linsys2
	@chmod 755 $(DESTDIR)$(PREFIX)/bin/linsys2
	@sed 's/@VERSION@/$(VERSION)/g' scripts/linsys2-makepkg > $(DESTDIR)$(PREFIX)/bin/linsys2-makepkg
	@chmod 755 $(DESTDIR)$(PREFIX)/bin/linsys2-makepkg
	install -Dm644 README.md $(DESTDIR)$(PREFIX)/share/doc/linsys2-pacman/README.md
	install -Dm644 COPYING $(DESTDIR)$(PREFIX)/share/licenses/linsys2-pacman/COPYING

clean:
	@cd $(SUBMODULE) && rm -rf build
	@cd $(SUBMODULE) && git checkout -- .
	@rm -f $(PATCH_STAMP)

bump-submodule: $(SUBMODULE)/.git
ifndef SUBMODULE_VERSION
	@echo "Usage: make bump-submodule SUBMODULE_VERSION=<tag|commit|branch>"
	@exit 1
endif
	@echo "[LinSYS2] Fetching $(SUBMODULE_VERSION)..."
	@cd $(SUBMODULE) && git fetch origin $(SUBMODULE_VERSION)
	@echo "[LinSYS2] Checking out $(SUBMODULE_VERSION)..."
	@cd $(SUBMODULE) && git checkout $(SUBMODULE_VERSION)
	@echo "[LinSYS2] Verifying patch compatibility..."
	@cd $(SUBMODULE) && git checkout -- .
	@for p in $(PATCHES); do \
		(cd $(SUBMODULE) && patch -p1 -i "../../$$p" --dry-run --quiet) || exit 1; \
	done
	@echo "[LinSYS2] OK. Staging..."
	@git add $(SUBMODULE)
	@echo "Review: git diff --cached"
	@echo "Commit: git commit -m 'Bump msys2-pacman to $(SUBMODULE_VERSION)'"

bump-keyring: $(KEYRING_SUBMODULE)/.git
ifndef KEYRING_VERSION
	@echo "Usage: make bump-keyring KEYRING_VERSION=<tag|commit|branch>"
	@exit 1
endif
	@echo "[LinSYS2] Fetching keyring $(KEYRING_VERSION)..."
	@cd $(KEYRING_SUBMODULE) && git fetch origin $(KEYRING_VERSION)
	@echo "[LinSYS2] Checking out $(KEYRING_VERSION)..."
	@cd $(KEYRING_SUBMODULE) && git checkout $(KEYRING_VERSION)
	@echo "[LinSYS2] OK. Staging..."
	@git add $(KEYRING_SUBMODULE)
	@echo "Review: git diff --cached"
	@echo "Commit: git commit -m 'Bump msys2-keyring to $(KEYRING_VERSION)'"
