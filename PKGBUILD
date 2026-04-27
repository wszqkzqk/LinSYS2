# Maintainer: wszqkzqk <wszqkzqk@qq.com>

pkgname=linsys2
pkgver=r0.00000000.0000000
pkgrel=1
pkgdesc='MSYS2 pacman fork for managing mingw-w64 packages on Linux'
arch=('x86_64')
url='https://github.com/wszqkzqk/LinSYS2'
license=('GPL-2.0-or-later')
depends=('bash' 'curl' 'gettext' 'gnupg' 'libarchive' 'which' 'bzip2' 'xz' 'zstd' 'wine')
makedepends=('git' 'meson' 'ninja' 'asciidoc' 'doxygen' 'gcc')
source=("${pkgname}::git+file://${startdir}")
sha256sums=('SKIP')

pkgver() {
    cd "${pkgname}"
    printf "r%s.%s.%s" \
        "$(git rev-list --count HEAD)" \
        "$(git log -1 --format=%cd --date=format:%Y%m%d)" \
        "$(git rev-parse --short HEAD)"
}

build() {
    cd "${pkgname}"
    make
}

package() {
    cd "${pkgname}"
    make DESTDIR="${pkgdir}" PREFIX=/usr install
}
