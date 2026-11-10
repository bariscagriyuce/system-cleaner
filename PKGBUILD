# Maintainer: yerel kullanım
pkgname=sistem-temizleyici
pkgver=1.1.0
pkgrel=1
pkgdesc="Graphical system cleaner for CachyOS/Arch (Türkçe, English, Português do Brasil)"
arch=('any')
license=('MIT')
depends=('python' 'python-pyqt6' 'pacman-contrib' 'polkit')
optdepends=('flatpak: clean unused Flatpak runtimes')
source=('sistem_temizleyici.py' 'i18n.py' 'helper.py' 'sistem-temizleyici.desktop' 'org.sistemtemizleyici.helper.policy')
sha256sums=('SKIP' 'SKIP' 'SKIP' 'SKIP' 'SKIP')

package() {
  install -Dm755 sistem_temizleyici.py "$pkgdir/usr/lib/sistem-temizleyici/sistem_temizleyici.py"
  install -Dm644 i18n.py               "$pkgdir/usr/lib/sistem-temizleyici/i18n.py"
  install -Dm755 helper.py             "$pkgdir/usr/lib/sistem-temizleyici/helper.py"
  install -Dm644 sistem-temizleyici.desktop "$pkgdir/usr/share/applications/sistem-temizleyici.desktop"
  install -Dm644 org.sistemtemizleyici.helper.policy "$pkgdir/usr/share/polkit-1/actions/org.sistemtemizleyici.helper.policy"
  install -dm755 "$pkgdir/usr/bin"
  printf '#!/bin/sh\nexec /usr/bin/python3 /usr/lib/sistem-temizleyici/sistem_temizleyici.py "$@"\n' > "$pkgdir/usr/bin/sistem-temizleyici"
  chmod 755 "$pkgdir/usr/bin/sistem-temizleyici"
}
