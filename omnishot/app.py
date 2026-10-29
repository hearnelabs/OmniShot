"""
OmniShot Application Orchestrator
Handles capture requests, snip overlay, scrolling session lifecycle,
and window management.
"""

import sys
import time
from typing import Optional
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, QTimer, QRect, Qt, QPoint
from PySide6.QtGui import QImage, QGuiApplication, QCursor

from .core.config import OmniShotConfig
from .core.capture import get_capture_backend
from .core.uinput_mouse import UInputScroller
from .core.stitcher import ScrollingStitcher
from .core.clipboard import copy_image_to_clipboard, ClipboardPersistenceKeeper
from .ui.main_window import OmniShotMainWindow
from .ui.snip_overlay import SnipSelectionOverlay
from .ui.scroll_hud import ScrollingCaptureHUD
from .ui.launch_overlay import SpectacleLaunchOverlay

class OmniShotApp(QObject):
    def __init__(self, qapp: QApplication, config: Optional[OmniShotConfig] = None):
        super().__init__()
        self.qapp = qapp
        self.config = config or OmniShotConfig.load()
        self.capture_backend = get_capture_backend()
        self.uinput_scroller = UInputScroller()
        self.clipboard_keeper = ClipboardPersistenceKeeper(self.qapp, parent=self)

        # Windows (Editor is lazily shown only post-capture)
        self.main_window: Optional[OmniShotMainWindow] = None

        self._active_overlay: Optional[SpectacleLaunchOverlay] = None
        self._scroll_hud: Optional[ScrollingCaptureHUD] = None
        self._stitcher: Optional[ScrollingStitcher] = None
        self._scroll_timer: Optional[QTimer] = None
        self._scroll_target_rect: Optional[QRect] = None
        self._is_auto_scroll = True
        self._ticks_without_movement = 0

    def get_or_create_main_window(self) -> OmniShotMainWindow:
        if self.main_window is None:
            self.main_window = OmniShotMainWindow(self.config)
            self.main_window.clipboard_keeper = self.clipboard_keeper
            self.main_window.requestCapture.connect(self.trigger_capture)
            self.main_window.windowClosed.connect(self._on_main_window_closed)
        return self.main_window

    def _on_main_window_closed(self):
        """Called when the user closes the OmniShot editor window."""
        self.clipboard_keeper.enter_background_persistence()

    def show_main_window(self):
        mw = self.get_or_create_main_window()
        mw.show()
        mw.raise_()
        mw.activateWindow()

    def _get_active_screen(self):
        """Identifies the active display screen based on KWin active output or cursor pos."""
        # 1. Authoritative KWin Wayland active output
        try:
            active_name = self.capture_backend.get_active_output_name()
            if active_name:
                for s in QGuiApplication.screens():
                    if s.name() == active_name:
                        return s
        except Exception:
            pass

        # 2. Cursor position (works on X11 / XWayland / when cursor pos is valid)
        try:
            pos = QCursor.pos()
            if pos != QPoint(0, 0):
                s = QGuiApplication.screenAt(pos)
                if s:
                    return s
        except Exception:
            pass

        # 3. Fallback to primary screen
        return QGuiApplication.primaryScreen()

    def launch_interactive(self, delay_ms: int = 0):
        """Launches the Spectacle 6 in-situ floating overlay (initial launch state)."""
        if self.main_window and self.main_window.isVisible():
            self.main_window.hide()

        if delay_ms > 0:
            QTimer.singleShot(delay_ms, self._do_launch_interactive)
        else:
            self._do_launch_interactive()

    def _do_launch_interactive(self):
        active_screen = self._get_active_screen()
        bg_screen = None
        if active_screen:
            bg_screen = self.capture_backend.capture_screen(active_screen.name())
            if not bg_screen or bg_screen.isNull():
                geo = active_screen.geometry()
                bg_screen = self.capture_backend.capture_area(geo.x(), geo.y(), geo.width(), geo.height())

        if not bg_screen or bg_screen.isNull():
            bg_screen = self.capture_backend.capture_workspace()

        if not bg_screen or bg_screen.isNull():
            print("[OmniShot] Failed to capture screen for launch overlay")
            self.show_main_window()
            return

        self._active_overlay = SpectacleLaunchOverlay(bg_screen, target_screen=active_screen)
        self._active_overlay.snapshotConfirmed.connect(self._on_snapshot_confirmed)
        self._active_overlay.scrollCaptureConfirmed.connect(self._on_scroll_confirmed)
        self._active_overlay.fullscreenConfirmed.connect(lambda: self.trigger_capture("fullscreen"))
        self._active_overlay.windowConfirmed.connect(lambda: self.trigger_capture("window"))
        self._active_overlay.overlayCancelled.connect(self._on_overlay_cancelled)
        self._active_overlay.showFullScreen()
        self._active_overlay.raise_()
        self._active_overlay.activateWindow()

    def _on_overlay_cancelled(self):
        if self.main_window and not self.main_window.isHidden():
            self.show_main_window()
        else:
            if self.clipboard_keeper.has_image_offered():
                self.clipboard_keeper.enter_background_persistence()
            else:
                self.qapp.quit()

    def trigger_capture(self, mode: str):
        """Triggers capture for: region, scroll_auto, scroll_manual, fullscreen, window."""
        if self.main_window and self.main_window.isVisible():
            self.main_window.hide()
        # Brief pause to allow window manager to hide window
        QTimer.singleShot(250, lambda: self._execute_capture_trigger(mode))

    def _execute_capture_trigger(self, mode: str):
        if mode in ("region", "interactive"):
            self._do_launch_interactive()

        elif mode in ("scroll_auto", "scroll_manual"):
            active_screen = self._get_active_screen()
            bg_screen = None
            if active_screen:
                bg_screen = self.capture_backend.capture_screen(active_screen.name())
                if not bg_screen or bg_screen.isNull():
                    geo = active_screen.geometry()
                    bg_screen = self.capture_backend.capture_area(geo.x(), geo.y(), geo.width(), geo.height())

            if not bg_screen or bg_screen.isNull():
                bg_screen = self.capture_backend.capture_workspace()

            if not bg_screen or bg_screen.isNull():
                print("[OmniShot] Failed to capture screen for scroll overlay")
                self.show_main_window()
                return

            self._active_overlay = SpectacleLaunchOverlay(bg_screen, target_screen=active_screen)
            self._active_overlay.snapshotConfirmed.connect(self._on_snapshot_confirmed)
            self._active_overlay.scrollCaptureConfirmed.connect(self._on_scroll_confirmed)
            self._active_overlay.fullscreenConfirmed.connect(lambda: self.trigger_capture("fullscreen"))
            self._active_overlay.windowConfirmed.connect(lambda: self.trigger_capture("window"))
            self._active_overlay.overlayCancelled.connect(self._on_overlay_cancelled)
            # Switch into scroll prompt
            self._active_overlay._on_pill_scroll_triggered()
            self._active_overlay.showFullScreen()
            self._active_overlay.raise_()
            self._active_overlay.activateWindow()

        elif mode == "fullscreen":
            active_screen = self._get_active_screen()
            img = None
            if active_screen:
                img = self.capture_backend.capture_screen(active_screen.name())
                if not img or img.isNull():
                    geo = active_screen.geometry()
                    img = self.capture_backend.capture_area(geo.x(), geo.y(), geo.width(), geo.height())

            if not img or img.isNull():
                img = self.capture_backend.capture_workspace()

            if img:
                self._show_editor_with_image(img)
            else:
                self.show_main_window()

        elif mode == "window":
            img = self.capture_backend.capture_active_window()
            if img:
                self._show_editor_with_image(img)
            else:
                self.show_main_window()

    def _on_snapshot_confirmed(self, rect: QRect, img: Optional[QImage] = None):
        # Translate local overlay coordinates to global multi-monitor coordinates
        if self._active_overlay:
            rect = rect.translated(self._active_overlay.geometry().topLeft())

        if not img or img.isNull():
            img = self.capture_backend.capture_area(rect.x(), rect.y(), rect.width(), rect.height())
        if img:
            self._show_editor_with_image(img)
        else:
            self.show_main_window()

    def _show_editor_with_image(self, img: QImage):
        """Displays the full OmniShot Annotation Editor loaded with the captured image and copies to clipboard."""
        mw = self.get_or_create_main_window()
        mw.set_captured_image(img)
        mw.show()
        mw.raise_()
        mw.activateWindow()

        # Multi-format MIME copy to clipboard and mark offer for persistence
        if copy_image_to_clipboard(img):
            self.clipboard_keeper.mark_image_offered()

    def _on_scroll_confirmed(self, rect: QRect, is_auto: bool):
        # Translate local overlay coordinates to global multi-monitor coordinates
        if self._active_overlay:
            rect = rect.translated(self._active_overlay.geometry().topLeft())

        self._scroll_target_rect = rect
        self._is_auto_scroll = is_auto
        # Wait 300ms for overlay to close and target window focus to be restored
        QTimer.singleShot(300, lambda: self._start_scrolling_session(rect, is_auto))

    def _start_scrolling_session(self, rect: QRect, is_auto: bool):
        print(f"[OmniShot] Starting scrolling capture session ({'Auto' if is_auto else 'Manual'}) for region {rect}")
        self._ticks_without_movement = 0

        # Pre-open uinput scroller if needed
        if is_auto:
            if not self.uinput_scroller.open():
                print("[OmniShot] Notice: /dev/uinput not accessible. Falling back to interactive manual scroll mode.")
                is_auto = False
                self._is_auto_scroll = False

        # Capture initial frame of the region
        initial_frame = self.capture_backend.capture_area(rect.x(), rect.y(), rect.width(), rect.height())
        if not initial_frame or initial_frame.isNull():
            print("[OmniShot] Error: Failed to capture initial frame for scrolling session")
            self.show_main_window()
            return

        # Initialize stitcher with is_manual flag
        self._stitcher = ScrollingStitcher(
            margin_x_left=10,
            margin_x_right=self.config.scrollbar_margin_right,
            margin_y_top=self.config.header_margin_top,
            margin_y_bottom=self.config.footer_margin_bottom,
            max_allowed_diff=self.config.scroll_similarity_threshold,
            is_manual=(not is_auto)
        )
        self._stitcher.start(initial_frame)

        # Show Floating HUD (configured not to steal focus)
        self._scroll_hud = ScrollingCaptureHUD(is_auto=is_auto)
        self._scroll_hud.finishRequested.connect(self._finish_scrolling_session)
        self._scroll_hud.stepScrollRequested.connect(self._on_manual_step_requested)
        self._scroll_hud.cancelRequested.connect(self._cancel_scrolling_session)
        self._scroll_hud.pauseToggled.connect(self._on_scroll_pause_toggled)

        # Position HUD near top or bottom outside region, clamped to target monitor
        self._scroll_hud.adjustSize()
        hw = self._scroll_hud.width()
        hh = self._scroll_hud.height()
        
        target_screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        screen_geo = target_screen.geometry()

        hx = rect.center().x() - hw // 2
        hx = max(screen_geo.left() + 20, min(screen_geo.right() - hw - 20, hx))
        hy = rect.bottom() + 15
        if hy + hh > screen_geo.bottom() - 20:
            hy = max(screen_geo.top() + 20, rect.top() - hh - 15)
        
        self._scroll_hud.move(hx, hy)
        self._scroll_hud.show()
        self._scroll_hud.update_status(initial_frame.height(), 1, initial_frame)

        # Start timer loop
        # Auto: 180ms delay between scroll ticks
        # Manual: 80ms delay polling for user's own scroll actions
        interval = max(160, self.config.scroll_delay_ms) if is_auto else 80
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(interval)
        self._scroll_timer.timeout.connect(self._on_scroll_tick)
        self._scroll_timer.start()

    def _on_manual_step_requested(self):
        """User clicked '⬇ Scroll Step' button on HUD."""
        if not self._scroll_target_rect or not self._stitcher:
            return
        # Fire both wheel and key down to ensure scroll
        self.uinput_scroller.scroll_down(steps=1, high_res_delta=-120)
        self.qapp.processEvents()
        # Schedule capture after 120ms
        QTimer.singleShot(120, self._capture_and_stitch_frame)

    def _on_scroll_pause_toggled(self, is_paused: bool):
        if self._scroll_timer:
            if is_paused:
                self._scroll_timer.stop()
            else:
                self._scroll_timer.start()

    def _on_scroll_tick(self):
        if not self._stitcher or not self._scroll_target_rect:
            return

        # In Auto mode, inject scroll down event
        if self._is_auto_scroll:
            # Emit wheel event
            self.uinput_scroller.scroll_down(steps=1, high_res_delta=-120)
            
            # If 5 consecutive ticks saw no movement, try PageDown/Down key
            if self._ticks_without_movement >= 5 and (self._ticks_without_movement % 3 == 0):
                self.uinput_scroller.scroll_key_down()

            self.qapp.processEvents()

        self._capture_and_stitch_frame()

    def _capture_and_stitch_frame(self):
        if not self._stitcher or not self._scroll_target_rect:
            return

        rect = self._scroll_target_rect
        frame = self.capture_backend.capture_area(rect.x(), rect.y(), rect.width(), rect.height())
        if not frame or frame.isNull():
            return

        success, offset, status = self._stitcher.add_frame(frame)
        if success:
            if offset > 0:
                self._ticks_without_movement = 0
                thumb = self._stitcher.get_preview_thumbnail(max_height=140)
                if self._scroll_hud:
                    self._scroll_hud.update_status(self._stitcher.current_height, self._stitcher.frame_count, thumb)
            elif offset == 0:
                self._ticks_without_movement += 1
                # Auto-stop ONLY if we already stitched several frames (frame_count >= 3)
                # AND there have been at least 25 consecutive unchanged ticks!
                if self._is_auto_scroll and self._stitcher.frame_count >= 3 and self._ticks_without_movement >= 25:
                    if self.config.auto_detect_end_of_scroll:
                        print("[OmniShot] End of scroll detected after multiple successful stitches")
                        self._finish_scrolling_session()
                        return

        # Check maximum bounds safeguard
        if self._stitcher.frame_count >= self.config.scroll_max_frames or self._stitcher.current_height >= self.config.scroll_max_height:
            print("[OmniShot] Reached maximum capture frames/height safety limit")
            self._finish_scrolling_session()

    def _finish_scrolling_session(self):
        if self._scroll_timer:
            self._scroll_timer.stop()
            self._scroll_timer = None

        if self._scroll_hud:
            self._scroll_hud.close()
            self._scroll_hud = None

        if self.uinput_scroller:
            self.uinput_scroller.close()

        if self._stitcher and self._stitcher.get_stitched_image():
            stitched = self._stitcher.get_stitched_image()
            print(f"[OmniShot] Scrolling session finished! Final image size: {stitched.width()}x{stitched.height()} ({self._stitcher.frame_count} frames)")
            self._show_editor_with_image(stitched)
        else:
            self.show_main_window()

    def _cancel_scrolling_session(self):
        if self._scroll_timer:
            self._scroll_timer.stop()
            self._scroll_timer = None

        if self._scroll_hud:
            self._scroll_hud.close()
            self._scroll_hud = None

        if self.uinput_scroller:
            self.uinput_scroller.close()

        print("[OmniShot] Scrolling session cancelled by user")
        if self.main_window and not self.main_window.isHidden():
            self.show_main_window()
        else:
            if self.clipboard_keeper.has_image_offered():
                self.clipboard_keeper.enter_background_persistence()
            else:
                self.qapp.quit()
