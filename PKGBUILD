# Maintainer: HearneLabs <contact@hearnelabs.com>
pkgname=omnishot
pkgver=1.0.0
pkgrel=1
pkgdesc="Next-generation screenshot and seamless scrolling capture tool for KDE Plasma 6 on CachyOS / Arch"
arch=('x86_64')
url="https://github.com/HearneLabs/OmniShot"
license=('GPL3')
depends=(
    'python>=3.10'
    'pyside6'
    'python-dbus'
    'kconfig'
    'kservice'
    'libnotify'
    'tesseract'
    'tesseract-data-eng'
)
makedepends=('gcc')
source=()

build() {
    cd "$startdir"
    gcc -O3 -march=native -fPIC -shared native/stitcher.c -o omnishot/core/libomnishot_stitch.so -lm 2>/dev/null || \
    gcc -O3 -fPIC -shared native/stitcher.c -o omnishot/core/libomnishot_stitch.so -lm
}

package() {
    cd "$startdir"

    # Install application files to /opt/omnishot
    install -d "$pkgdir/opt/omnishot"
    cp -r omnishot "$pkgdir/opt/omnishot/"
    cp -r bin "$pkgdir/opt/omnishot/"
    install -m 644 omnishot.svg "$pkgdir/opt/omnishot/"

    # Install binary launcher symlink in /usr/bin
    install -d "$pkgdir/usr/bin"
    ln -sf /opt/omnishot/bin/omnishot "$pkgdir/usr/bin/omnishot"

    # Install .desktop file
    install -Dm644 omnishot.desktop "$pkgdir/usr/share/applications/omnishot.desktop"

    # Install udev rule for uinput
    install -d "$pkgdir/usr/lib/udev/rules.d"
    echo 'KERNEL=="uinput", SUBSYSTEM=="misc", TAG+="uaccess", OPTIONS+="static_node=uinput"' > \
        "$pkgdir/usr/lib/udev/rules.d/99-omnishot-uinput.rules"

    # Render and install icons across standard hicolor sizes
    python3 -c "
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray, Qt

app = QApplication(['icon-render', '-platform', 'offscreen'])
renderer = QSvgRenderer(QByteArray(Path('omnishot.svg').read_bytes()))
pkgdir = Path('$pkgdir')
hicolor = pkgdir / 'usr/share/icons/hicolor'

for sz in [16, 22, 24, 32, 48, 64, 128, 256, 512]:
    d = hicolor / f'{sz}x{sz}/apps'
    d.mkdir(parents=True, exist_ok=True)
    img = QImage(sz, sz, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p)
    p.end()
    img.save(str(d / 'omnishot.png'))

sc = hicolor / 'scalable/apps'
sc.mkdir(parents=True, exist_ok=True)
shutil.copyfile('omnishot.svg', sc / 'omnishot.svg')
"
}
