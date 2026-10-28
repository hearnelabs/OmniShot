#!/usr/bin/env bash
# ==============================================================================
# OmniShot Automated Installer for CachyOS & Arch Linux (KDE Plasma 6)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "====================================================================="
echo "  OmniShot — Professional Screenshot & Scrolling Capture for CachyOS"
echo "====================================================================="

# 1. Check and install package dependencies via pacman
REQUIRED_PKGS=(
    "pyside6"
    "python-dbus"
    "kconfig"
    "kservice"
    "libnotify"
    "tesseract"
    "tesseract-data-eng"
    "gcc"
)

MISSING_PKGS=()
for pkg in "${REQUIRED_PKGS[@]}"; do
    if ! pacman -Qi "$pkg" &>/dev/null; then
        MISSING_PKGS+=("$pkg")
    fi
done

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo "[1/6] Installing missing dependencies: ${MISSING_PKGS[*]}"
    if command -v sudo &>/dev/null; then
        sudo pacman -S --needed --noconfirm "${MISSING_PKGS[@]}"
    else
        echo "Error: sudo not found. Please install the following packages manually:"
        echo "  pacman -S --needed ${MISSING_PKGS[*]}"
        exit 1
    fi
else
    echo "[1/6] All dependencies satisfied (${REQUIRED_PKGS[*]})"
fi

# 2. Build high-performance native C stitching engine
echo "[2/6] Compiling native stitching acceleration library..."
if [ -f "native/stitcher.c" ]; then
    gcc -O3 -march=native -fPIC -shared native/stitcher.c -o omnishot/core/libomnishot_stitch.so -lm 2>/dev/null || \
    gcc -O3 -fPIC -shared native/stitcher.c -o omnishot/core/libomnishot_stitch.so -lm
    echo "      Compiled: omnishot/core/libomnishot_stitch.so"
fi

# 3. Configure udev rules for unprivileged /dev/uinput scrolling access
echo "[3/6] Verifying /dev/uinput permissions for scrolling capture..."
if [ -w "/dev/uinput" ]; then
    echo "      /dev/uinput is already accessible by current user ($USER)."
else
    UDEV_RULE_FILE="/etc/udev/rules.d/99-omnishot-uinput.rules"
    if [ -w "/etc/udev/rules.d" ]; then
        echo 'KERNEL=="uinput", SUBSYSTEM=="misc", TAG+="uaccess", OPTIONS+="static_node=uinput"' > "$UDEV_RULE_FILE"
        echo "      Installed $UDEV_RULE_FILE"
    elif command -v sudo &>/dev/null && [ -t 0 ]; then
        echo 'KERNEL=="uinput", SUBSYSTEM=="misc", TAG+="uaccess", OPTIONS+="static_node=uinput"' | sudo tee "$UDEV_RULE_FILE" >/dev/null
        sudo udevadm control --reload-rules && sudo udevadm trigger --name-match=uinput 2>/dev/null || true
        echo "      Installed $UDEV_RULE_FILE"
    else
        echo "      Notice: /dev/uinput is not writable by current user. To enable auto-scrolling without root, run:"
        echo "      echo 'KERNEL==\"uinput\", SUBSYSTEM==\"misc\", TAG+=\"uaccess\", OPTIONS+=\"static_node=uinput\"' | sudo tee /etc/udev/rules.d/99-omnishot-uinput.rules"
    fi
fi

# 4. Install Desktop Entry and Icons across all standard hicolor dimensions
echo "[4/6] Installing desktop launcher and hicolor taskbar icons..."
mkdir -p "$HOME/.local/share/applications"
mkdir -p "$HOME/.local/bin"

cp "omnishot.desktop" "$HOME/.local/share/applications/omnishot.desktop"

# Render icons using PySide6 to guarantee pixel-perfect Breeze scaling
python3 -c "
import sys, shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray, Qt

app = QApplication(['icon-render', '-platform', 'offscreen'])
svg_path = Path('omnishot.svg')
renderer = QSvgRenderer(QByteArray(svg_path.read_bytes()))
hicolor = Path.home() / '.local/share/icons/hicolor'

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

# Also copy directly into active icon theme if custom theme is installed
if command -v kreadconfig6 &>/dev/null; then
    ACTIVE_THEME=$(kreadconfig6 --file kdeglobals --group Icons --key Theme || echo "")
    if [ -n "$ACTIVE_THEME" ] && [ -d "$HOME/.local/share/icons/$ACTIVE_THEME" ]; then
        mkdir -p "$HOME/.local/share/icons/$ACTIVE_THEME/64x64/apps"
        mkdir -p "$HOME/.local/share/icons/$ACTIVE_THEME/24x24/apps"
        cp "omnishot.svg" "$HOME/.local/share/icons/$ACTIVE_THEME/64x64/apps/omnishot.svg"
        cp "$HOME/.local/share/icons/hicolor/64x64/apps/omnishot.png" "$HOME/.local/share/icons/$ACTIVE_THEME/64x64/apps/omnishot.png"
        cp "$HOME/.local/share/icons/hicolor/24x24/apps/omnishot.png" "$HOME/.local/share/icons/$ACTIVE_THEME/24x24/apps/omnishot.png"
    fi
fi

# Create launcher symlink in ~/.local/bin
ln -sf "$SCRIPT_DIR/bin/omnishot" "$HOME/.local/bin/omnishot"

# 5. Configure KDE Plasma 6 Global Shortcuts & Refresh Shell
echo "[5/6] Registering KDE Plasma 6 Shortcuts and refreshing icon caches..."
if command -v kwriteconfig6 &>/dev/null; then
    # Standard OmniShot hotkey: Meta+Shift+S (Spectacle default)
    kwriteconfig6 --file kglobalshortcutsrc --group "omnishot.desktop" --key "_k_friendly_name" "OmniShot"
    kwriteconfig6 --file kglobalshortcutsrc --group "omnishot.desktop" --key "RectangularRegionScreenShot" "Meta+Shift+S\tPrint,none,Capture Rectangular Region"
    kwriteconfig6 --file kglobalshortcutsrc --group "omnishot.desktop" --key "ScrollingCapture" "Meta+Shift+R,none,Scrolling Capture"
    kwriteconfig6 --file kglobalshortcutsrc --group "omnishot.desktop" --key "FullScreenScreenShot" "Shift+Print,none,Capture Entire Desktop"
    kwriteconfig6 --file kglobalshortcutsrc --group "omnishot.desktop" --key "ActiveWindowScreenShot" "Meta+Print,none,Capture Active Window"
fi

if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" &>/dev/null || true
fi

# Purge Plasma desktop icon and pixmap caches
rm -f "$HOME/.cache/plasma_theme_"*.kcache 2>/dev/null || true
rm -rf "$HOME/.cache/plasmashell/qmlcache" 2>/dev/null || true

if command -v kbuildsycoca6 &>/dev/null; then
    kbuildsycoca6 --noincremental &>/dev/null || true
fi

# Reload Plasma Shell if active so launcher icons update immediately without logout
if systemctl --user is-active --quiet plasma-plasmashell.service 2>/dev/null; then
    systemctl --user restart plasma-plasmashell.service &>/dev/null || true
fi

# 6. Verification
echo "[6/6] Running system verification suite..."
python3 -m unittest discover tests -v

echo "====================================================================="
echo "  OmniShot installed successfully!"
echo "  Launch anytime by running: omnishot"
echo "  Or press: Meta+Shift+S or Print"
echo "====================================================================="
