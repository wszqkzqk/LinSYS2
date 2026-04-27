# LinSYS2 Makefile
# Unified build system for MSYS2 pacman on Linux

PREFIX ?= /usr
DESTDIR ?=

SUBMODULE = vendor/msys2-pacman
PATCH = patches/0001-LinSYS2-Adapt-MSYS2-pacman-for-Linux.patch
BUILD_DIR = $(SUBMODULE)/build
PATCH_STAMP = $(SUBMODULE)/.linsys2-patched.stamp

KEYRING_SUBMODULE = vendor/msys2-keyring
KEYRING_DIR = $(DESTDIR)$(PRIVATE_PREFIX)/share/pacman/keyrings

PRIVATE_PREFIX = $(PREFIX)/lib/linsys2-pacman
PACMAN_CFLAGS = -DMSYS2_PACMAN_LINUX

.PHONY: all build configure install clean checkout bump-submodule bump-keyring

all: build

$(SUBMODULE)/.git $(KEYRING_SUBMODULE)/.git:
	git submodule update --init --recursive

checkout: $(SUBMODULE)/.git $(KEYRING_SUBMODULE)/.git
ifdef SUBMODULE_VERSION
	@cd $(SUBMODULE) && git fetch origin $(SUBMODULE_VERSION) 2>/dev/null || true
	@cd $(SUBMODULE) && git checkout $(SUBMODULE_VERSION)
endif

$(PATCH_STAMP): $(PATCH) | checkout
	@echo "[LinSYS2] Applying patches..."
	@cd $(SUBMODULE) && git checkout -- .
	@cd $(SUBMODULE) && patch -p1 -i ../../$(PATCH)
	@touch $@

configure: $(PATCH_STAMP)
	@test -f $(BUILD_DIR)/build.ninja || \
		(echo "[LinSYS2] Configuring meson..." && \
		 cd $(SUBMODULE) && meson setup build \
			--prefix=$(PRIVATE_PREFIX) \
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
	@rm -f $(DESTDIR)/usr/share/bash-completion/completions/pacman
	@rm -f $(DESTDIR)/usr/share/bash-completion/completions/pacman-key
	@rm -f $(DESTDIR)/usr/share/bash-completion/completions/makepkg
	install -Dm644 $(KEYRING_SUBMODULE)/msys2.gpg $(KEYRING_DIR)/msys2.gpg
	install -Dm644 $(KEYRING_SUBMODULE)/msys2-trusted $(KEYRING_DIR)/msys2-trusted
	install -Dm644 $(KEYRING_SUBMODULE)/msys2-revoked $(KEYRING_DIR)/msys2-revoked
	install -Dm755 scripts/linsys2-pacman $(DESTDIR)$(PREFIX)/bin/linsys2-pacman
	install -Dm755 scripts/linsys2 $(DESTDIR)$(PREFIX)/bin/linsys2
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
	@cd $(SUBMODULE) && git checkout -- . && patch -p1 -i ../../$(PATCH) --dry-run --quiet
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
