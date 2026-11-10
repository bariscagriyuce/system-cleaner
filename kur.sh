#!/bin/sh
# Sistem Temizleyici kurulumu: bir paket oluşturur ve pacman ile kurar.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD="$(mktemp -d)"
cp "$DIR/PKGBUILD" "$DIR"/src/*.py "$DIR"/data/* "$BUILD/"
cd "$BUILD"
makepkg -si --noconfirm
rm -rf "$BUILD"
echo
echo "Kurulum tamamlandı. Uygulama menüsünde 'Sistem Temizleyici' olarak bulabilirsiniz."
