"""
OmniShot Application Orchestrator
Handles capture requests, snip overlay, scrolling session lifecycle,
and window management.
"""

import sys
import time
from typing import Optional
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, QTimer, QRect, Qt
from PySide6.QtGui import QImage, QGuiApplication

from .core.config import OmniShotConfig
from .core.capture import get_capture_backend
from .core.uinput_mouse import UInputScroller
from .core.stitcher import ScrollingStitcher
from .ui.main_window import OmniShotMainWindow
from .ui.snip_overlay import SnipSelectionOverlay
from .ui.scroll_hud import ScrollingCaptureHUD

class OmniShotApp(QObject):
    def __init__(self, qapp: QApplication, config: Optional[OmniShotConfig] = None):
        super().__init__()
        self.qapp = qapp
        self.config = config or OmniShotConfig.load()
        self.capture_backend = get_capture_backend()
        self.uinput_scroller = UInputScroller()

        # Windows
        self.main_window = OmniShotMainWindow(self.config)
        self.main_window.requestCapture.connect(self.trigger_capture)

        self._active_overlay: Optional[SnipSelectionOverlay] = None
        self._scroll_hud: Optional[ScrollingCaptureHUD] = None
        self._stitcher: Optional[ScrollingStitcher] = None
        self._scroll_timer: Optional[QTimer] = None
        self._scroll_target_rect: Optional[QRect] = None
        self._is_auto_scroll = True
        self._ticks_without_movement = 0

    def show_main_window(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def trigger_capture(self, mode: str):
        """Triggers capture for: region, scroll_auto, scroll_manual, fullscreen, window."""
        self.main_window.hide()
        # Brief pause to allow window manager to hide window
        QTimer.singleShot(250, lambda: self._execute_capture_trigger(mode))

    def _execute_capture_trigger(self, mode: str):
        if mode in ("region", "scroll_auto", "scroll_manual"):
            # Capture whole workspace to display on overlay
            bg_screen = self.capture_backend.capture_workspace()
            if not bg_screen or bg_screen.isNull():
                print("[OmniShot] Failed to capture workspace for snip overlay")
                self.show_main_window()
                return

            self._active_overlay = SnipSelectionOverlay(bg_screen)
            self._active_overlay.snapshotConfirmed.connect(self._on_snapshot_confirmed)
            self._active_overlay.scrollCaptureConfirmed.connect(self._on_scroll_confirmed)
            self._active_overlay.overlayCancelled.connect(self.show_main_window)
            self._active_overlay.showFullScreen()
            self._active_overlay.raise_()
            self._active_overlay.activateWindow()

        elif mode == "fullscreen":
            img = self.capture_backend.capture_workspace()
            if img:
                self.main_window.set_captured_image(img)
            else:
                self.show_main_window()

        elif mode == "window":
            img = self.capture_backend.capture_active_window()
            if img:
                self.main_window.set_captured_image(img)
            else:
                self.show_main_window()

    def _on_snapshot_confirmed(self, rect: QRect):
        img = self.capture_backend.capture_area(rect.x(), rect.y(), rect.width(), rect.height())
        if img:
            self.main_window.set_captured_image(img)
        else:
            self.show_main_window()

    def _on_scroll_confirmed(self, rect: QRect, is_auto: bool):
        self._scroll_target_rect = rect
        self._is_auto_scroll = is_auto
        # Wait 300ms for overlay to close and target window focus to be restored
        QTimer.singleShot(300, lambda: self._start_scrolling_session(rect, is_auto))

    def _start_scrolling_session(self, rect: QRect, is_auto: bool):
        print(f"[OmniShot] Starting scrolling capture session ({'Auto' if is_auto else 'Manual'}) for region {rect}")
        self._ticks_without_movement = 0

        # Pre-open uinput scroller if needed
        if is_auto:
            self.uinput_scroller.open()

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

        # Position HUD near top or bottom outside region
        self._scroll_hud.adjustSize()
        hw = self._scroll_hud.width()
        hh = self._scroll_hud.height()
        
        screen_geo = QGuiApplication.primaryScreen().geometry()
        hx = rect.center().x() - hw // 2
        hx = max(20, min(screen_geo.width() - hw - 20, hx))
        hy = rect.bottom() + 15
        if hy + hh > screen_geo.height() - 20:
            hy = max(20, rect.top() - hh - 15)
        
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
            self.main_window.set_captured_image(stitched)
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
        self.show_main_window()
