"""
OmniShot Clipboard Engine
Handles multi-format MIME encoding (PNG, BMP, Qt) and background persistence
across Wayland and X11 so screenshot data remains available on the system
clipboard after the editor window is closed, until explicitly overwritten.
"""

import sys
import shutil
import subprocess
from typing import Optional
from PySide6.QtCore import QObject, QTimer, QMimeData, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QImage, QGuiApplication, QClipboard


def ensure_klipper_image_support():
    """Configures KDE Plasma 6 Klipper to retain image selections in clipboard history."""
    kwriteconfig = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
    if kwriteconfig:
        try:
            subprocess.run(
                [kwriteconfig, "--file", "klipperrc", "--group", "General", "--key", "IgnoreImages", "false"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            if shutil.which("dbus-send"):
                subprocess.run([
                    "dbus-send", "--type=method_call", "--dest=org.kde.klipper",
                    "/klipper", "org.kde.klipper.klipper.reloadConfig"
                ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def copy_image_to_clipboard(image: QImage) -> bool:
    """
    Copies a QImage to the system clipboard with multi-format MIME data:
    - image/png: standard format for Chromium, Discord, Slack, Firefox, Telegram, etc.
    - image/x-png: legacy PNG alias
    - image/bmp: standard BMP bitmap
    - application/x-qt-image: native Qt image payload

    Also delegates to wl-copy if installed on Wayland systems, and ensures KDE Klipper
    has image support enabled.
    """
    if not image or image.isNull():
        return False

    try:
        # 1. Encode PNG bytes
        ba_png = QByteArray()
        buf_png = QBuffer(ba_png)
        buf_png.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buf_png, "PNG")

        # 2. Encode BMP bytes
        ba_bmp = QByteArray()
        buf_bmp = QBuffer(ba_bmp)
        buf_bmp.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buf_bmp, "BMP")

        # 3. Create rich QMimeData
        mime = QMimeData()
        mime.setImageData(image)  # Sets application/x-qt-image
        mime.setData("image/png", ba_png)
        mime.setData("image/x-png", ba_png)
        mime.setData("image/bmp", ba_bmp)

        # 4. Set to system clipboard
        clipboard = QGuiApplication.clipboard()
        if QGuiApplication.platformName() == "offscreen":
            clipboard.setImage(image)
        else:
            clipboard.setMimeData(mime, QClipboard.Mode.Clipboard)

        # 5. Delegate to wl-copy if installed on Wayland
        wl_copy = shutil.which("wl-copy")
        if wl_copy:
            try:
                p = subprocess.Popen(
                    [wl_copy, "-t", "image/png"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                p.communicate(input=ba_png.data(), timeout=1.0)
            except Exception:
                pass

        # 6. Ensure KDE Klipper image support
        ensure_klipper_image_support()
        return True
    except Exception as e:
        print(f"[OmniShot] Warning: Failed to copy image to clipboard: {e}")
        return False


class ClipboardPersistenceKeeper(QObject):
    """
    Maintains clipboard persistence after the OmniShot editor window is closed.
    Keeps the Wayland/X11 data source alive until the user copies something else
    or until a safety timeout expires.
    """
    def __init__(self, qapp, parent=None):
        super().__init__(parent)
        self.qapp = qapp
        self._has_clipboard_offer = False
        self._is_persisting_in_background = False
        self._listening_to_changes = False

    def mark_image_offered(self):
        """Notifies the keeper that OmniShot has placed an image on the clipboard."""
        self._has_clipboard_offer = True

    def has_image_offered(self) -> bool:
        return self._has_clipboard_offer

    def enter_background_persistence(self, timeout_ms: int = 7200000):
        """
        Called when editor window closes.
        If an image was copied to clipboard during this session, keeps the process alive
        in the background until the user copies something else (or safety timeout expires).
        If no image was copied, cleanly quits the application immediately.
        """
        if not self._has_clipboard_offer:
            self.qapp.quit()
            return

        self._is_persisting_in_background = True
        print("[OmniShot] Editor window closed. Maintaining clipboard persistence in background...")

        # Delay arming clipboard listener to ignore the synthetic event fired during window unmap
        QTimer.singleShot(400, self._arm_clipboard_listener)

        # Safety timeout: default 2 hours
        QTimer.singleShot(timeout_ms, self._on_timeout)

    def _arm_clipboard_listener(self):
        if not self._listening_to_changes:
            self._listening_to_changes = True
            clipboard = QGuiApplication.clipboard()
            clipboard.dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self):
        if self._is_persisting_in_background:
            self._is_persisting_in_background = False
            print("[OmniShot] External clipboard change detected. Cleanly exiting background persistence.")
            self.qapp.quit()

    def _on_timeout(self):
        if self._is_persisting_in_background:
            self._is_persisting_in_background = False
            print("[OmniShot] Background clipboard persistence timeout reached. Cleanly exiting.")
            self.qapp.quit()
