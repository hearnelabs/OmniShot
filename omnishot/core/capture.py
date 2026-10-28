"""
OmniShot KWin Wayland Screen Capture Engine
Direct high-speed pipe-based screencopy using org.kde.KWin.ScreenShot2
"""

import os
import dbus
from typing import Optional, Tuple
from PySide6.QtGui import QImage

class KWinCaptureBackend:
    def __init__(self):
        self._bus = None
        self._iface = None
        self._init_dbus()

    def _init_dbus(self):
        try:
            self._bus = dbus.SessionBus()
            kwin_obj = self._bus.get_object("org.kde.KWin", "/org/kde/KWin/ScreenShot2")
            self._iface = dbus.Interface(kwin_obj, "org.kde.KWin.ScreenShot2")
        except Exception as e:
            print(f"[OmniShot] Error connecting to org.kde.KWin.ScreenShot2: {e}")
            self._iface = None

    def _read_image_from_pipe(self, r_fd: int, metadata: dict) -> Optional[QImage]:
        try:
            width = int(metadata.get("width", 0))
            height = int(metadata.get("height", 0))
            stride = int(metadata.get("stride", 0))
            fmt_code = int(metadata.get("format", 16)) # 16 = Format_RGBX8888
            
            total_bytes = stride * height
            if total_bytes <= 0 or width <= 0 or height <= 0:
                return None

            chunks = []
            read_bytes = 0
            while read_bytes < total_bytes:
                chunk = os.read(r_fd, min(131072, total_bytes - read_bytes))
                if not chunk:
                    break
                chunks.append(chunk)
                read_bytes += len(chunk)

            raw_bytes = b"".join(chunks)
            if len(raw_bytes) < total_bytes:
                print(f"[OmniShot] Incomplete frame: read {len(raw_bytes)} of {total_bytes} bytes")
                return None

            fmt = QImage.Format(fmt_code) if fmt_code in QImage.Format.__members__.values() else QImage.Format.Format_RGBX8888
            # Construct QImage and copy to own buffer
            img = QImage(raw_bytes, width, height, stride, fmt).copy()
            return img
        except Exception as e:
            print(f"[OmniShot] Failed reading image from pipe: {e}")
            return None

    def capture_workspace(self, include_cursor: bool = False) -> Optional[QImage]:
        """Captures entire Wayland desktop / all monitors at native hardware resolution."""
        if not self._iface:
            self._init_dbus()
            if not self._iface:
                return None

        r_fd, w_fd = os.pipe()
        try:
            unix_fd = dbus.types.UnixFd(w_fd)
            options = dbus.Dictionary({
                "include-cursor": dbus.Boolean(include_cursor),
                "native-resolution": dbus.Boolean(True)
            }, signature="sv")
            res = self._iface.CaptureWorkspace(options, unix_fd)
            os.close(w_fd)
            return self._read_image_from_pipe(r_fd, res)
        finally:
            os.close(r_fd)

    def capture_screen(self, screen_name: str = "", include_cursor: bool = False) -> Optional[QImage]:
        """Captures current or specified screen/monitor at native resolution."""
        if not self._iface:
            self._init_dbus()
            if not self._iface:
                return None

        # Fallback to CaptureWorkspace if screen name is not given or invalid
        if not screen_name:
            screen_name = "eDP-1"

        r_fd, w_fd = os.pipe()
        try:
            unix_fd = dbus.types.UnixFd(w_fd)
            options = dbus.Dictionary({
                "include-cursor": dbus.Boolean(include_cursor),
                "native-resolution": dbus.Boolean(True)
            }, signature="sv")
            try:
                res = self._iface.CaptureScreen(screen_name, options, unix_fd)
            except Exception:
                # Fallback to workspace capture
                return self.capture_workspace(include_cursor=include_cursor)
            os.close(w_fd)
            return self._read_image_from_pipe(r_fd, res)
        finally:
            os.close(r_fd)

    def capture_active_window(self, include_cursor: bool = False) -> Optional[QImage]:
        """Captures the currently active window with native resolution and decorations."""
        if not self._iface:
            self._init_dbus()
            if not self._iface:
                return None

        r_fd, w_fd = os.pipe()
        try:
            unix_fd = dbus.types.UnixFd(w_fd)
            options = dbus.Dictionary({
                "include-cursor": dbus.Boolean(include_cursor),
                "include-decoration": dbus.Boolean(True),
                "include-shadow": dbus.Boolean(True),
                "native-resolution": dbus.Boolean(True)
            }, signature="sv")
            res = self._iface.CaptureActiveWindow(options, unix_fd)
            os.close(w_fd)
            return self._read_image_from_pipe(r_fd, res)
        finally:
            os.close(r_fd)

    def capture_area(self, x: int, y: int, width: int, height: int, include_cursor: bool = False) -> Optional[QImage]:
        """Captures a specific rectangular region in logical coordinates at native resolution."""
        if not self._iface:
            self._init_dbus()
            if not self._iface:
                return None

        if width <= 0 or height <= 0:
            return None

        r_fd, w_fd = os.pipe()
        try:
            unix_fd = dbus.types.UnixFd(w_fd)
            options = dbus.Dictionary({
                "include-cursor": dbus.Boolean(include_cursor),
                "native-resolution": dbus.Boolean(True)
            }, signature="sv")
            res = self._iface.CaptureArea(int(x), int(y), int(width), int(height), options, unix_fd)
            os.close(w_fd)
            return self._read_image_from_pipe(r_fd, res)
        finally:
            os.close(r_fd)

# Global singleton
_capture_backend: Optional[KWinCaptureBackend] = None

def get_capture_backend() -> KWinCaptureBackend:
    global _capture_backend
    if _capture_backend is None:
        _capture_backend = KWinCaptureBackend()
    return _capture_backend
