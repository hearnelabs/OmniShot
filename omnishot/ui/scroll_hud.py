"""
OmniShot Floating Scroll Capture HUD
Real-time floating control bar and mini visual preview during scrolling capture.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QFrame
)
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QKeyEvent
from PySide6.QtCore import Qt, Signal, QRect

class ScrollThumbnailPreview(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 120)
        self.setStyleSheet("""
            QLabel {
                background-color: #1a1c1e;
                border: 1px solid #3daee9;
                border-radius: 4px;
            }
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def update_thumbnail(self, image: QImage):
        if image and not image.isNull():
            pix = QPixmap.fromImage(image.scaled(56, 116, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.setPixmap(pix)


class ScrollingCaptureHUD(QFrame):
    finishRequested = Signal()
    pauseToggled = Signal(bool)
    cancelRequested = Signal()

    def __init__(self, is_auto: bool = True, parent=None):
        super().__init__(parent)
        self.is_auto = is_auto
        self.is_paused = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.setStyleSheet("""
            QFrame#hudContainer {
                background-color: rgba(26, 29, 34, 240);
                border: 1.5px solid #3daee9;
                border-radius: 12px;
                padding: 10px;
            }
            QLabel {
                color: #eff0f1;
                font-family: "Noto Sans", sans-serif;
            }
            QPushButton {
                background-color: #31363b;
                color: #eff0f1;
                border: 1px solid #474e54;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 13px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3b4249;
                border: 1px solid #3daee9;
            }
            QPushButton#finishBtn {
                background-color: #27ae60;
                border: 1px solid #2ecc71;
                color: #ffffff;
            }
            QPushButton#finishBtn:hover {
                background-color: #2ecc71;
            }
            QPushButton#cancelBtn {
                background-color: #7f8c8d;
                border: 1px solid #95a5a6;
            }
            QPushButton#cancelBtn:hover {
                background-color: #95a5a6;
            }
        """)
        self.setObjectName("hudContainer")

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(14)

        # Thumbnail on the left
        self.thumbnail = ScrollThumbnailPreview(self)
        main_layout.addWidget(self.thumbnail)

        # Center info stats
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        mode_str = "Auto-Scrolling" if is_auto else "Manual Scrolling"
        self.lbl_title = QLabel(f"🔴 Live Capture ({mode_str})", self)
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #3daee9;")
        
        self.lbl_stats = QLabel("Height: 0 px  ·  Frames: 1", self)
        self.lbl_stats.setStyleSheet("font-size: 13px; font-weight: 600; color: #ffffff;")

        hint_text = "Scroll target page with mouse or trackpad" if not is_auto else "Auto-scrolling content downwards..."
        self.lbl_hint = QLabel(hint_text, self)
        self.lbl_hint.setStyleSheet("font-size: 11px; color: #bdc3c7;")

        info_layout.addWidget(self.lbl_title)
        info_layout.addWidget(self.lbl_stats)
        info_layout.addWidget(self.lbl_hint)
        main_layout.addLayout(info_layout)

        # Buttons on the right
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_finish = QPushButton("⏹ Done (Enter)", self)
        self.btn_finish.setObjectName("finishBtn")
        self.btn_finish.clicked.connect(self.finishRequested.emit)

        if is_auto:
            self.btn_pause = QPushButton("⏸ Pause (Space)", self)
            self.btn_pause.clicked.connect(self._toggle_pause)
            btn_layout.addWidget(self.btn_pause)

        self.btn_cancel = QPushButton("✕ Cancel (Esc)", self)
        self.btn_cancel.setObjectName("cancelBtn")
        self.btn_cancel.clicked.connect(self.cancelRequested.emit)

        btn_layout.addWidget(self.btn_finish)
        btn_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_layout)

    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        if hasattr(self, "btn_pause"):
            self.btn_pause.setText("▶ Resume (Space)" if self.is_paused else "⏸ Pause (Space)")
        self.lbl_title.setText(f"⏸ Paused ({'Auto' if self.is_auto else 'Manual'})" if self.is_paused else f"🔴 Live Capture ({'Auto' if self.is_auto else 'Manual'})")
        self.pauseToggled.emit(self.is_paused)

    def update_status(self, height: int, frames: int, preview_img: Optional[QImage] = None):
        self.lbl_stats.setText(f"Height: {height:,} px  ·  Frames: {frames}")
        if preview_img and not preview_img.isNull():
            self.thumbnail.update_thumbnail(preview_img)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.finishRequested.emit()
        elif key == Qt.Key.Key_Space and self.is_auto:
            self._toggle_pause()
        elif key == Qt.Key.Key_Escape:
            self.cancelRequested.emit()
        else:
            super().keyPressEvent(event)
