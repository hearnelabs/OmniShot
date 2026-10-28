"""
OmniShot Interactive Spectacle Launch Overlay (KDE Plasma 6 Native)
Faithfully implements the Spectacle 6 in-situ launch experience:
- Screen softly dimmed with high-DPI guidance prompt
- Top status capsule: 'OmniShot - Ready'
- Bottom floating capsule pill with highlighted green '📜 Scrolling Capture',
  '⛶ Rectangular Region', '🪟 Window', '🖥️ Full Screen', '⏱️ Delay', '⚙️ Options', '✕ Cancel'
- Interactive click-and-drag rectangular snip with 8 resize handles
- Loupe magnifier with real-time RGB & coordinate badge
- In-situ action strip on selection: Accept, Auto-Scroll, Manual Scroll, Discard
"""

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QFrame,
    QToolButton, QMenu, QApplication
)
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QMouseEvent, QKeyEvent,
    QPaintEvent, QImage, QAction, QCursor
)
from PySide6.QtCore import Qt, QPoint, QRect, Signal, QSize


class SelectionActionStrip(QFrame):
    """Micro-action toolbar attached directly to the active drawn rectangle."""
    acceptClicked = Signal()
    autoScrollClicked = Signal()
    manualScrollClicked = Signal()
    discardClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("selectionStrip")
        self.setStyleSheet("""
            QFrame#selectionStrip {
                background-color: rgba(24, 28, 34, 240);
                border: 1px solid #3daee9;
                border-radius: 10px;
                padding: 3px;
            }
            QPushButton {
                background-color: #2d3238;
                color: #eff0f1;
                border: 1px solid #474e54;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3daee9;
                color: #ffffff;
            }
            QPushButton#btnAccept {
                background-color: #1d6fa5;
                border: 1px solid #3daee9;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#btnAccept:hover {
                background-color: #2980b9;
            }
            QPushButton#btnAutoScroll {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #1e824c);
                border: 1px solid #2ecc71;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#btnAutoScroll:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2ecc71, stop:1 #27ae60);
            }
            QPushButton#btnDiscard {
                background-color: #3a3f44;
                color: #e74c3c;
            }
            QPushButton#btnDiscard:hover {
                background-color: #c0392b;
                color: #ffffff;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        self.btn_accept = QPushButton("✔ Accept (Enter)", self)
        self.btn_accept.setObjectName("btnAccept")
        self.btn_accept.clicked.connect(self.acceptClicked.emit)

        self.btn_auto_scroll = QPushButton("📜 Auto-Scroll (A)", self)
        self.btn_auto_scroll.setObjectName("btnAutoScroll")
        self.btn_auto_scroll.clicked.connect(self.autoScrollClicked.emit)

        self.btn_manual_scroll = QPushButton("🖱️ Manual Scroll (M)", self)
        self.btn_manual_scroll.clicked.connect(self.manualScrollClicked.emit)

        self.btn_discard = QPushButton("✕ Discard", self)
        self.btn_discard.setObjectName("btnDiscard")
        self.btn_discard.clicked.connect(self.discardClicked.emit)

        layout.addWidget(self.btn_accept)
        layout.addWidget(self.btn_auto_scroll)
        layout.addWidget(self.btn_manual_scroll)
        layout.addWidget(self.btn_discard)


class FloatingLaunchPill(QFrame):
    """The signature Plasma 6 Spectacle bottom floating pill with prominent green Scrolling Capture."""
    scrollCaptureTriggered = Signal()
    regionModeSelected = Signal()
    windowCaptureTriggered = Signal()
    fullscreenCaptureTriggered = Signal()
    delayChanged = Signal(int) # delay in ms
    optionsChanged = Signal(dict)
    cancelTriggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("bottomPill")
        self.current_delay_ms = 0
        self.include_cursor = False
        self.copy_to_clipboard_direct = False

        self.setStyleSheet("""
            QFrame#bottomPill {
                background-color: rgba(22, 26, 32, 235);
                border: 1px solid rgba(61, 174, 233, 0.45);
                border-radius: 24px;
                padding: 4px 10px;
            }
            QPushButton, QToolButton {
                background-color: #2a2e33;
                color: #eff0f1;
                border: 1px solid #3e444a;
                border-radius: 17px;
                padding: 7px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover, QToolButton:hover {
                background-color: #353b42;
                border: 1px solid #3daee9;
                color: #ffffff;
            }
            QPushButton#btnScroll {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #1e824c);
                border: 1px solid #2ecc71;
                border-radius: 17px;
                padding: 7px 18px;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnScroll:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2ecc71, stop:1 #27ae60);
                border: 1px solid #58d68d;
            }
            QPushButton#btnCancel {
                background-color: #2d3238;
                color: #e74c3c;
                border: 1px solid #4a3333;
                border-radius: 17px;
            }
            QPushButton#btnCancel:hover {
                background-color: #c0392b;
                color: #ffffff;
                border: 1px solid #e74c3c;
            }
            QFrame#vSep {
                background-color: #474e54;
                width: 1px;
                max-width: 1px;
            }
            QMenu {
                background-color: #1e2227;
                color: #eff0f1;
                border: 1px solid #3e444a;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #3daee9;
                color: #ffffff;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # 1. 📜 Scrolling Capture (Highlighted Green Button)
        self.btn_scroll = QPushButton("📜 Scrolling Capture", self)
        self.btn_scroll.setObjectName("btnScroll")
        self.btn_scroll.setToolTip("Start automated vertical scrolling capture on target window/region")
        self.btn_scroll.clicked.connect(self.scrollCaptureTriggered.emit)
        layout.addWidget(self.btn_scroll)

        # 2. ⛶ Rectangular Region
        self.btn_region = QPushButton("⛶ Rectangular Region", self)
        self.btn_region.setToolTip("Draw a rectangular region on screen (or click and drag directly)")
        self.btn_region.clicked.connect(self.regionModeSelected.emit)
        layout.addWidget(self.btn_region)

        # 3. 🪟 Window
        self.btn_window = QPushButton("🪟 Window", self)
        self.btn_window.setToolTip("Capture active or clicked window")
        self.btn_window.clicked.connect(self.windowCaptureTriggered.emit)
        layout.addWidget(self.btn_window)

        # 4. 🖥️ Full Screen
        self.btn_fullscreen = QPushButton("🖥️ Full Screen", self)
        self.btn_fullscreen.setToolTip("Capture all screens / entire workspace")
        self.btn_fullscreen.clicked.connect(self.fullscreenCaptureTriggered.emit)
        layout.addWidget(self.btn_fullscreen)

        # Separator
        sep = QFrame(self)
        sep.setObjectName("vSep")
        sep.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(sep)

        # 5. ⏱️ Delay Dropdown
        self.btn_delay = QToolButton(self)
        self.btn_delay.setText("⏱️ Delay: None ▾")
        self.btn_delay.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._setup_delay_menu()
        layout.addWidget(self.btn_delay)

        # 6. ⚙️ Options Menu
        self.btn_options = QToolButton(self)
        self.btn_options.setText("⚙️ Options ▾")
        self.btn_options.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._setup_options_menu()
        layout.addWidget(self.btn_options)

        # 7. ✕ Cancel
        self.btn_cancel = QPushButton("✕ Cancel", self)
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.setToolTip("Close OmniShot (Esc)")
        self.btn_cancel.clicked.connect(self.cancelTriggered.emit)
        layout.addWidget(self.btn_cancel)

    def _setup_delay_menu(self):
        menu = QMenu(self)
        delays = [
            ("No delay (Instant)", 0),
            ("2 seconds", 2000),
            ("5 seconds", 5000),
            ("10 seconds", 10000),
        ]
        for label, ms in delays:
            action = QAction(label, self)
            action.triggered.connect(lambda ch, m=ms, l=label: self._set_delay(m, l))
            menu.addAction(action)
        self.btn_delay.setMenu(menu)

    def _set_delay(self, ms: int, label: str):
        self.current_delay_ms = ms
        text = "⏱️ Delay: None ▾" if ms == 0 else f"⏱️ Delay: {ms // 1000}s ▾"
        self.btn_delay.setText(text)
        self.delayChanged.emit(ms)

    def _setup_options_menu(self):
        menu = QMenu(self)
        
        # Include pointer toggle
        self.action_cursor = QAction("Include Mouse Pointer", self)
        self.action_cursor.setCheckable(True)
        self.action_cursor.setChecked(self.include_cursor)
        self.action_cursor.toggled.connect(self._on_options_updated)
        menu.addAction(self.action_cursor)

        # Direct copy toggle
        self.action_copy_direct = QAction("Copy directly to Clipboard without Editor", self)
        self.action_copy_direct.setCheckable(True)
        self.action_copy_direct.setChecked(self.copy_to_clipboard_direct)
        self.action_copy_direct.toggled.connect(self._on_options_updated)
        menu.addAction(self.action_copy_direct)

        self.btn_options.setMenu(menu)

    def _on_options_updated(self):
        self.include_cursor = self.action_cursor.isChecked()
        self.copy_to_clipboard_direct = self.action_copy_direct.isChecked()
        self.optionsChanged.emit({
            "include_cursor": self.include_cursor,
            "copy_to_clipboard_direct": self.copy_to_clipboard_direct
        })


class SpectacleLaunchOverlay(QWidget):
    """
    KDE Plasma 6 Spectacle interactive launch overlay:
    - Screen softly dimmed
    - Top status capsule 'OmniShot - Ready'
    - Center guidance text: 'Click and drag to draw a capture region, or select a mode below'
    - Bottom floating capsule bar with highlighted green 'Scrolling Capture'
    - Interactive rectangle selection with live coordinates, resize handles, and loupe
    """
    snapshotConfirmed = Signal(QRect)
    scrollCaptureConfirmed = Signal(QRect, bool) # (rect, is_auto)
    fullscreenConfirmed = Signal()
    windowConfirmed = Signal()
    overlayCancelled = Signal()

    def __init__(self, background_image: QImage, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._bg_image: QImage = background_image
        self._start_pos: Optional[QPoint] = None
        self._current_pos: Optional[QPoint] = None
        self._selected_rect: Optional[QRect] = None
        self._is_selecting = False
        self._active_handle: Optional[int] = None # 0..7 for resize handles
        self._is_dragging_rect = False
        self._drag_offset = QPoint()
        self._prompt_text = "Click and drag to draw a capture region,\nor select a mode below"
        self._is_scroll_mode_pending = False

        # 1. Top status capsule
        self.top_pill = QLabel("OmniShot - Ready", self)
        self.top_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.top_pill.setStyleSheet("""
            QLabel {
                background-color: rgba(24, 28, 34, 215);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 12px;
                padding: 4px 18px;
                color: #a0a8b4;
                font-size: 11px;
                font-weight: 600;
            }
        """)

        # 2. Bottom Floating Launch Pill
        self.bottom_pill = FloatingLaunchPill(self)
        self.bottom_pill.scrollCaptureTriggered.connect(self._on_pill_scroll_triggered)
        self.bottom_pill.regionModeSelected.connect(self._on_pill_region_selected)
        self.bottom_pill.windowCaptureTriggered.connect(self._on_pill_window_triggered)
        self.bottom_pill.fullscreenCaptureTriggered.connect(self._on_pill_fullscreen_triggered)
        self.bottom_pill.cancelTriggered.connect(self._on_cancel_requested)

        # 3. Selection micro-strip (attached to selection rect)
        self.selection_strip = SelectionActionStrip(self)
        self.selection_strip.hide()
        self.selection_strip.acceptClicked.connect(self._confirm_snapshot)
        self.selection_strip.autoScrollClicked.connect(lambda: self._confirm_scroll(True))
        self.selection_strip.manualScrollClicked.connect(lambda: self._confirm_scroll(False))
        self.selection_strip.discardClicked.connect(self._clear_selection)

        if self._bg_image and not self._bg_image.isNull():
            self.resize(self._bg_image.width(), self._bg_image.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Position top pill at top-center
        self.top_pill.adjustSize()
        self.top_pill.move((self.width() - self.top_pill.width()) // 2, 14)

        # Position bottom pill at bottom-center
        self.bottom_pill.adjustSize()
        self.bottom_pill.move((self.width() - self.bottom_pill.width()) // 2, self.height() - self.bottom_pill.height() - 32)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._on_cancel_requested()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if self._selected_rect and self._selected_rect.width() > 10 and self._selected_rect.height() > 10:
                self._confirm_snapshot()
            else:
                self._on_pill_fullscreen_triggered()
        elif key in (Qt.Key.Key_A, Qt.Key.Key_S):
            if self._selected_rect and self._selected_rect.width() > 10 and self._selected_rect.height() > 10:
                self._confirm_scroll(True)
            else:
                self._on_pill_scroll_triggered()
        elif key == Qt.Key.Key_M:
            if self._selected_rect and self._selected_rect.width() > 10 and self._selected_rect.height() > 10:
                self._confirm_scroll(False)
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            # If clicked inside child controls, don't intercept
            if self.bottom_pill.geometry().contains(pos) or (self.selection_strip.isVisible() and self.selection_strip.geometry().contains(pos)):
                return

            # Check handle hits if selection exists
            if self._selected_rect and not self._selected_rect.isEmpty():
                handle_idx = self._hit_test_handles(pos)
                if handle_idx is not None:
                    self._active_handle = handle_idx
                    self._start_pos = pos
                    self.selection_strip.hide()
                    return

                # Check if clicking inside rect to move it
                if self._selected_rect.contains(pos):
                    self._is_dragging_rect = True
                    self._drag_offset = pos - self._selected_rect.topLeft()
                    self.selection_strip.hide()
                    return

            # Start new rectangular selection
            self._is_selecting = True
            self._start_pos = pos
            self._current_pos = pos
            self._selected_rect = None
            self.selection_strip.hide()
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.pos()
        self._current_pos = pos

        # Update cursor shape based on hover
        if not self._is_selecting and not self._is_dragging_rect and self._active_handle is None:
            if self._selected_rect and not self._selected_rect.isEmpty():
                h = self._hit_test_handles(pos)
                if h is not None:
                    cursors = [
                        Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeBDiagCursor,
                        Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeBDiagCursor,
                        Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeVerCursor,
                        Qt.CursorShape.SizeHorCursor, Qt.CursorShape.SizeHorCursor
                    ]
                    self.setCursor(cursors[h])
                elif self._selected_rect.contains(pos):
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                else:
                    self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)

        # Handle active operations
        if self._is_selecting and self._start_pos:
            self._selected_rect = QRect(
                min(self._start_pos.x(), pos.x()),
                min(self._start_pos.y(), pos.y()),
                abs(pos.x() - self._start_pos.x()),
                abs(pos.y() - self._start_pos.y())
            )
            self.update()

        elif self._is_dragging_rect and self._selected_rect:
            new_tl = pos - self._drag_offset
            # Constrain to screen bounds
            nx = max(0, min(self.width() - self._selected_rect.width(), new_tl.x()))
            ny = max(0, min(self.height() - self._selected_rect.height(), new_tl.y()))
            self._selected_rect.moveTo(nx, ny)
            self.update()

        elif self._active_handle is not None and self._selected_rect:
            self._resize_by_handle(self._active_handle, pos)
            self.update()

        else:
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_selecting:
                self._is_selecting = False
                if self._start_pos and self._current_pos:
                    rect = QRect(
                        min(self._start_pos.x(), self._current_pos.x()),
                        min(self._start_pos.y(), self._current_pos.y()),
                        abs(self._current_pos.x() - self._start_pos.x()),
                        abs(self._current_pos.y() - self._start_pos.y())
                    )
                    if rect.width() > 20 and rect.height() > 20:
                        self._selected_rect = rect
                        if self._is_scroll_mode_pending:
                            self._is_scroll_mode_pending = False
                            self._confirm_scroll(True)
                            return
                        self._position_selection_strip(rect)
                    else:
                        self._selected_rect = None
                        self.selection_strip.hide()

            elif self._is_dragging_rect:
                self._is_dragging_rect = False
                if self._selected_rect:
                    self._position_selection_strip(self._selected_rect)

            elif self._active_handle is not None:
                self._active_handle = None
                if self._selected_rect:
                    self._position_selection_strip(self._selected_rect)

            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._selected_rect and self._selected_rect.contains(event.pos()):
                self._confirm_snapshot()

    def _hit_test_handles(self, pos: QPoint) -> Optional[int]:
        if not self._selected_rect:
            return None
        r = self._selected_rect
        hsize = 12
        corners = [
            QPoint(r.left(), r.top()),            # 0 TL
            QPoint(r.right(), r.top()),           # 1 TR
            QPoint(r.right(), r.bottom()),        # 2 BR
            QPoint(r.left(), r.bottom()),         # 3 BL
            QPoint(r.center().x(), r.top()),      # 4 TC
            QPoint(r.center().x(), r.bottom()),   # 5 BC
            QPoint(r.left(), r.center().y()),     # 6 LC
            QPoint(r.right(), r.center().y()),    # 7 RC
        ]
        for idx, pt in enumerate(corners):
            box = QRect(pt.x() - hsize, pt.y() - hsize, hsize * 2, hsize * 2)
            if box.contains(pos):
                return idx
        return None

    def _resize_by_handle(self, handle_idx: int, pos: QPoint):
        r = self._selected_rect
        if not r:
            return
        left, top, right, bottom = r.left(), r.top(), r.right(), r.bottom()
        
        if handle_idx == 0: # TL
            left = min(pos.x(), right - 20)
            top = min(pos.y(), bottom - 20)
        elif handle_idx == 1: # TR
            right = max(pos.x(), left + 20)
            top = min(pos.y(), bottom - 20)
        elif handle_idx == 2: # BR
            right = max(pos.x(), left + 20)
            bottom = max(pos.y(), top + 20)
        elif handle_idx == 3: # BL
            left = min(pos.x(), right - 20)
            bottom = max(pos.y(), top + 20)
        elif handle_idx == 4: # TC
            top = min(pos.y(), bottom - 20)
        elif handle_idx == 5: # BC
            bottom = max(pos.y(), top + 20)
        elif handle_idx == 6: # LC
            left = min(pos.x(), right - 20)
        elif handle_idx == 7: # RC
            right = max(pos.x(), left + 20)

        self._selected_rect = QRect(left, top, right - left, bottom - top)

    def _position_selection_strip(self, rect: QRect):
        self.selection_strip.adjustSize()
        tw = self.selection_strip.width()
        th = self.selection_strip.height()

        tx = rect.center().x() - tw // 2
        tx = max(14, min(self.width() - tw - 14, tx))

        # Position underneath selection, or above if close to bottom
        ty = rect.bottom() + 10
        if ty + th > self.height() - self.bottom_pill.height() - 40:
            ty = rect.top() - th - 10
        ty = max(10, min(self.height() - th - 10, ty))

        self.selection_strip.move(tx, ty)
        self.selection_strip.show()

    def _clear_selection(self):
        self._selected_rect = None
        self._start_pos = None
        self._current_pos = None
        self.selection_strip.hide()
        self._is_scroll_mode_pending = False
        self._prompt_text = "Click and drag to draw a capture region,\nor select a mode below"
        self.update()

    def _on_pill_scroll_triggered(self):
        """User clicked '📜 Scrolling Capture' on the bottom pill."""
        if self._selected_rect and self._selected_rect.width() > 20 and self._selected_rect.height() > 20:
            self._confirm_scroll(True)
        else:
            # Highlight scroll prompt: user can click any window or drag an area
            self._is_scroll_mode_pending = True
            self._prompt_text = "✨ Scroll Mode Active ✨\nDrag any area or click to begin Scrolling Capture"
            self.top_pill.setText("OmniShot - Scrolling Capture Mode")
            self.update()

    def _on_pill_region_selected(self):
        self._is_scroll_mode_pending = False
        self._prompt_text = "Click and drag to draw a capture region,\nor select a mode below"
        self.top_pill.setText("OmniShot - Ready")
        self.update()

    def _on_pill_window_triggered(self):
        self.close()
        self.windowConfirmed.emit()

    def _on_pill_fullscreen_triggered(self):
        self.close()
        self.fullscreenConfirmed.emit()

    def _on_cancel_requested(self):
        self.close()
        self.overlayCancelled.emit()

    def _confirm_snapshot(self):
        if self._selected_rect:
            rect = self._selected_rect
            self.close()
            self.snapshotConfirmed.emit(rect)

    def _confirm_scroll(self, is_auto: bool):
        if self._selected_rect:
            rect = self._selected_rect
            self.close()
            self.scrollCaptureConfirmed.emit(rect, is_auto)
        else:
            # Full primary screen as fallback target
            r = QRect(0, 0, self.width(), self.height())
            self.close()
            self.scrollCaptureConfirmed.emit(r, is_auto)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 1. Base desktop screen image
        if self._bg_image and not self._bg_image.isNull():
            painter.drawImage(0, 0, self._bg_image)

        # 2. Dimming mask (KDE Spectacle style)
        dim_color = QColor(0, 0, 0, 115)
        r = self._selected_rect

        if not r or r.isEmpty():
            painter.fillRect(self.rect(), dim_color)

            # Draw Centered Guidance Prompt
            painter.save()
            painter.setPen(QPen(QColor(0, 0, 0, 180), 2))
            font = QFont("Noto Sans", 18, QFont.Weight.Bold)
            painter.setFont(font)
            
            prompt_rect = QRect(0, self.height() // 2 - 80, self.width(), 90)
            
            # Subtle drop shadow
            painter.drawText(prompt_rect.adjusted(1, 1, 1, 1), Qt.AlignmentFlag.AlignCenter, self._prompt_text)
            
            # Text color (emerald green if scroll mode, else crisp white)
            text_color = QColor("#2ecc71") if self._is_scroll_mode_pending else QColor("#ffffff")
            painter.setPen(text_color)
            painter.drawText(prompt_rect, Qt.AlignmentFlag.AlignCenter, self._prompt_text)

            # Subtitle
            sub_font = QFont("Noto Sans", 11, QFont.Weight.Normal)
            painter.setFont(sub_font)
            painter.setPen(QColor("#bdc3c7"))
            sub_rect = QRect(0, self.height() // 2 + 15, self.width(), 30)
            painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, "Press Enter to capture full screen • Esc to cancel")
            painter.restore()

        else:
            # Cut out selection: mask top, bottom, left, right
            painter.fillRect(0, 0, self.width(), r.top(), dim_color)
            painter.fillRect(0, r.bottom() + 1, self.width(), self.height() - r.bottom() - 1, dim_color)
            painter.fillRect(0, r.top(), r.left(), r.height() + 1, dim_color)
            painter.fillRect(r.right() + 1, r.top(), self.width() - r.right() - 1, r.height() + 1, dim_color)

            # Selection border (KDE Breeze Cyan)
            border_pen = QPen(QColor("#3daee9"), 2, Qt.PenStyle.SolidLine)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)

            # 8 Resize Handles
            handle_size = 8
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(QPen(QColor("#3daee9"), 1))
            corners = [
                QPoint(r.left(), r.top()),
                QPoint(r.right(), r.top()),
                QPoint(r.right(), r.bottom()),
                QPoint(r.left(), r.bottom()),
                QPoint(r.center().x(), r.top()),
                QPoint(r.center().x(), r.bottom()),
                QPoint(r.left(), r.center().y()),
                QPoint(r.right(), r.center().y()),
            ]
            for c in corners:
                painter.drawRect(c.x() - handle_size // 2, c.y() - handle_size // 2, handle_size, handle_size)

            # Dimension badge
            dim_text = f"{r.width()} × {r.height()} px"
            painter.setFont(QFont("Noto Sans", 11, QFont.Weight.Bold))
            metrics = painter.fontMetrics()
            bw = metrics.horizontalAdvance(dim_text) + 16
            bh = metrics.height() + 8
            bx = r.left() + 6
            by = r.top() - bh - 6
            if by < 40:
                by = r.top() + 6
            badge_rect = QRect(bx, by, bw, bh)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(24, 28, 34, 230)))
            painter.drawRoundedRect(badge_rect, 5, 5)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, dim_text)

        # 3. High-precision Loupe Magnifier (shown during selection or mouse movement when strip is hidden)
        if self._current_pos and (not self.selection_strip.isVisible() or self._is_selecting):
            # Don't overlap bottom pill
            if not self.bottom_pill.geometry().contains(self._current_pos):
                self._draw_loupe(painter, self._current_pos)

    def _draw_loupe(self, painter: QPainter, pos: QPoint):
        if not self._bg_image or self._bg_image.isNull():
            return

        loupe_radius = 52
        zoom_factor = 4
        sample_w = int(loupe_radius * 2 / zoom_factor)
        sample_h = sample_w

        sx = pos.x() - sample_w // 2
        sy = pos.y() - sample_h // 2

        cropped = self._bg_image.copy(sx, sy, sample_w, sample_h)
        if cropped.isNull():
            return

        lx = pos.x() + 28
        ly = pos.y() + 28
        if lx + loupe_radius * 2 > self.width() - 20:
            lx = pos.x() - loupe_radius * 2 - 28
        if ly + loupe_radius * 2 > self.height() - self.bottom_pill.height() - 40:
            ly = pos.y() - loupe_radius * 2 - 28

        center = QPoint(lx + loupe_radius, ly + loupe_radius)

        painter.save()
        painter.setClipRect(QRect(lx, ly, loupe_radius * 2, loupe_radius * 2))
        zoomed = cropped.scaled(loupe_radius * 2, loupe_radius * 2, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        painter.drawImage(lx, ly, zoomed)

        # Border
        painter.setPen(QPen(QColor("#3daee9"), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, loupe_radius, loupe_radius)

        # Crosshairs
        painter.setPen(QPen(QColor(255, 40, 40, 220), 1))
        painter.drawLine(center.x() - 8, center.y(), center.x() + 8, center.y())
        painter.drawLine(center.x(), center.y() - 8, center.x(), center.y() + 8)

        # Info badge
        pixel_color = self._bg_image.pixelColor(min(self._bg_image.width() - 1, max(0, pos.x())), min(self._bg_image.height() - 1, max(0, pos.y())))
        coord_text = f"{pos.x()},{pos.y()} {pixel_color.name()}"
        painter.setFont(QFont("Noto Sans", 9, QFont.Weight.Bold))
        painter.fillRect(lx, ly + loupe_radius * 2 + 2, loupe_radius * 2, 18, QColor(0, 0, 0, 190))
        painter.setPen(QColor("#eff0f1"))
        painter.drawText(QRect(lx, ly + loupe_radius * 2 + 2, loupe_radius * 2, 18), Qt.AlignmentFlag.AlignCenter, coord_text)

        painter.restore()
