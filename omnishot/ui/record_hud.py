"""
OmniShot Floating Screen Recording HUD & Region Outline (KDE Breeze Native)
Floating non-intrusive capsule with live timer, pause/resume, and stop recording controls.
Includes a transparent, click-through bounding frame around the active recording region.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect, QApplication
)
from PySide6.QtGui import (
    QPainter, QPen, QColor, QFont, QMouseEvent, QPaintEvent, QIcon
)
from PySide6.QtCore import Qt, QPoint, QRect, Signal, QTimer, QSize


class RecordRegionOutline(QWidget):
    """Transparent click-through 2px red frame surrounding the active recorded region."""

    def __init__(self, rect: QRect, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.target_rect = rect

        # Expand geometry slightly by 2px on all sides to surround the region
        self.setGeometry(
            rect.x() - 2,
            rect.y() - 2,
            rect.width() + 4,
            rect.height() + 4
        )

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 2px bright red border with subtle semi-transparent glow
        pen = QPen(QColor(231, 76, 60, 220), 2)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        w = self.width() - 2
        h = self.height() - 2
        painter.drawRect(1, 1, w, h)


class RecordHUD(QFrame):
    """
    Floating, draggable capsule HUD indicating live recording state.
    Displays pulsing red REC dot, live MM:SS timer, pause/resume, and stop controls.
    """
    pauseToggled = Signal(bool) # True = paused, False = resumed
    finishRequested = Signal()
    discardRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("recordHUD")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._is_paused = False
        self._elapsed_seconds = 0
        self._drag_start_pos: Optional[QPoint] = None

        # Blinking dot animation timer
        self._dot_visible = True
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(600)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self._blink_timer.start()

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame#recordHUD {
                background-color: rgba(18, 22, 28, 245);
                border: 1.5px solid rgba(231, 76, 60, 0.7);
                border-radius: 20px;
                padding: 4px 10px;
            }
            QLabel {
                color: #eff0f1;
                font-family: system-ui, -apple-system, sans-serif;
            }
            QLabel#recBadge {
                color: #ff5252;
                font-weight: 800;
                font-size: 12px;
                letter-spacing: 0.5px;
            }
            QLabel#timerLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: 700;
                min-width: 50px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #eff0f1;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 14px;
                padding: 0 12px;
                font-weight: 600;
                font-size: 12px;
                height: 28px;
            }
            QPushButton:hover {
                background-color: rgba(61, 174, 233, 0.25);
                border: 1px solid #3daee9;
                color: #ffffff;
            }
            QPushButton#btnFinish {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e74c3c, stop:1 #c0392b);
                border: 1px solid #ff7675;
                color: #ffffff;
                font-weight: bold;
                padding: 0 16px;
            }
            QPushButton#btnFinish:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff7675, stop:1 #e74c3c);
            }
            QPushButton#btnDiscard {
                background-color: rgba(255, 255, 255, 0.05);
                color: #b2bec3;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            QPushButton#btnDiscard:hover {
                background-color: rgba(231, 76, 60, 0.2);
                color: #ff7675;
                border: 1px solid #e74c3c;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        # 1. Pulsing red dot + REC indicator
        self.lbl_rec = QLabel("⏺ REC", self)
        self.lbl_rec.setObjectName("recBadge")
        layout.addWidget(self.lbl_rec)

        # 2. Elapsed Timer (00:00)
        self.lbl_timer = QLabel("00:00", self)
        self.lbl_timer.setObjectName("timerLabel")
        layout.addWidget(self.lbl_timer)

        # Separator line
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 0.15); width: 1px; max-width: 1px; margin: 4px 2px;")
        layout.addWidget(sep)

        # 3. Pause / Resume button
        self.btn_pause = QPushButton("⏸ Pause", self)
        self.btn_pause.setFixedHeight(28)
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        layout.addWidget(self.btn_pause)

        # 4. Finish / Stop button
        self.btn_finish = QPushButton("⏹ Finish", self)
        self.btn_finish.setObjectName("btnFinish")
        self.btn_finish.setFixedHeight(28)
        self.btn_finish.clicked.connect(self.finishRequested.emit)
        layout.addWidget(self.btn_finish)

        # 5. Discard / Cancel button
        self.btn_discard = QPushButton("✕", self)
        self.btn_discard.setObjectName("btnDiscard")
        self.btn_discard.setFixedWidth(28)
        self.btn_discard.setFixedHeight(28)
        self.btn_discard.setToolTip("Discard recording")
        self.btn_discard.clicked.connect(self.discardRequested.emit)
        layout.addWidget(self.btn_discard)

        # Soft drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def _toggle_blink(self):
        if self._is_paused:
            self.lbl_rec.setText("⏸ PAUSED")
            self.lbl_rec.setStyleSheet("color: #f39c12; font-weight: 800; font-size: 12px;")
            return

        self._dot_visible = not self._dot_visible
        if self._dot_visible:
            self.lbl_rec.setText("⏺ REC")
            self.lbl_rec.setStyleSheet("color: #ff5252; font-weight: 800; font-size: 12px;")
        else:
            self.lbl_rec.setText("  REC")
            self.lbl_rec.setStyleSheet("color: #b71540; font-weight: 800; font-size: 12px;")

    def update_time(self, seconds: int):
        self._elapsed_seconds = seconds
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            self.lbl_timer.setText(f"{h:02d}:{m:02d}:{s:02d}")
        else:
            self.lbl_timer.setText(f"{m:02d}:{s:02d}")

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def set_paused_state(self, paused: bool):
        self._is_paused = paused
        if self._is_paused:
            self.btn_pause.setText("▶ Resume")
            self.lbl_rec.setText("⏸ PAUSED")
            self.lbl_rec.setStyleSheet("color: #f39c12; font-weight: 800; font-size: 12px;")
        else:
            self.btn_pause.setText("⏸ Pause")
            self.lbl_rec.setText("⏺ REC")
            self.lbl_rec.setStyleSheet("color: #ff5252; font-weight: 800; font-size: 12px;")

    def _on_pause_clicked(self):
        self.set_paused_state(not self._is_paused)
        self.pauseToggled.emit(self._is_paused)

    # Drag-to-reposition anywhere on screen
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_start_pos and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_start_pos = None
