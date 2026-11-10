# Maintainer: yerel kullanım
pkgname=sistem-temizleyici
pkgver=1.0.0
pkgrel=2
pkgdesc="CachyOS/Arch için grafik arayüzlü sistem temizleme aracı"
arch=('any')
license=('MIT')
depends=('python' 'python-pyqt6' 'pacman-contrib' 'polkit')
optdepends=('flatpak: kullanılmayan Flatpak bileşenlerini temizleme')
source=('sistem_temizleyici.py' 'helper.py' 'sistem-temizleyici.desktop' 'org.sistemtemizleyici.helper.policy')
sha256sums=('SKIP' 'SKIP' 'SKIP' 'SKIP')

package() {
  install -Dm755 sistem_temizleyici.py "$pkgdir/usr/lib/sistem-temizleyici/sistem_temizleyici.py"
  install -Dm755 helper.py             "$pkgdir/usr/lib/sistem-temizleyici/helper.py"
  install -Dm644 sistem-temizleyici.desktop "$pkgdir/usr/share/applications/sistem-temizleyici.desktop"
  install -Dm644 org.sistemtemizleyici.helper.policy "$pkgdir/usr/share/polkit-1/actions/org.sistemtemizleyici.helper.policy"
  install -dm755 "$pkgdir/usr/bin"
  printf '#!/bin/sh\nexec /usr/bin/python3 /usr/lib/sistem-temizleyici/sistem_temizleyici.py "$@"\n' > "$pkgdir/usr/bin/sistem-temizleyici"
  chmod 755 "$pkgdir/usr/bin/sistem-temizleyici"
}
