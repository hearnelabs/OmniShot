"""
OmniShot Floating Scroll Capture HUD
Non-intrusive floating control bar and mini visual preview during scrolling capture.
Never steals focus from target applications.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QFrame
)
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QKeyEvent
from PySide6.QtCore import Qt, Signal

class ScrollThumbnailPreview(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(64, 120)
        self.setStyleSheet("""
            QLabel {
                background-color: #14171a;
                border: 1px solid #3daee9;
                border-radius: 4px;
            }
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def update_thumbnail(self, image: QImage):
        if image and not image.isNull():
            pix = QPixmap.fromImage(image.scaled(60, 116, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.setPixmap(pix)


class ScrollingCaptureHUD(QFrame):
    finishRequested = Signal()
    stepScrollRequested = Signal()
    pauseToggled = Signal(bool)
    cancelRequested = Signal()

    def __init__(self, is_auto: bool = True, parent=None):
        super().__init__(parent)
        self.is_auto = is_auto
        self.is_paused = False

        # CRITICAL: Never steal focus from the target application under Wayland
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setStyleSheet("""
            QFrame#hudContainer {
                background-color: rgba(23, 26, 32, 245);
                border: 2px solid #3daee9;
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
                padding: 7px 14px;
                font-weight: 600;
                font-size: 13px;
                min-width: 85px;
            }
            QPushButton:hover {
                background-color: #3b4249;
                border: 1px solid #3daee9;
            }
            QPushButton#finishBtn {
                background-color: #27ae60;
                border: 1px solid #2ecc71;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#finishBtn:hover {
                background-color: #2ecc71;
            }
            QPushButton#stepBtn {
                background-color: #1d6fa5;
                border: 1px solid #3daee9;
                color: #ffffff;
            }
            QPushButton#stepBtn:hover {
                background-color: #2282c0;
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

        # Thumbnail preview on the left
        self.thumbnail = ScrollThumbnailPreview(self)
        main_layout.addWidget(self.thumbnail)

        # Center info stats
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        mode_str = "Auto-Scroll" if is_auto else "Manual Scroll"
        self.lbl_title = QLabel(f"🔴 Live Scrolling ({mode_str})", self)
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #3daee9;")
        
        self.lbl_stats = QLabel("Height: 0 px  ·  Frames: 1", self)
        self.lbl_stats.setStyleSheet("font-size: 13px; font-weight: 600; color: #ffffff;")

        hint_text = "Scroll content with mouse wheel / trackpad" if not is_auto else "Auto-scrolling content downwards..."
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
        self.btn_finish.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_finish.clicked.connect(self.finishRequested.emit)

        # Step scroll button: allows immediate manual step anytime
        self.btn_step = QPushButton("⬇ Scroll Step", self)
        self.btn_step.setObjectName("stepBtn")
        self.btn_step.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_step.setToolTip("Click to manually advance one scroll step")
        self.btn_step.clicked.connect(self.stepScrollRequested.emit)
        btn_layout.addWidget(self.btn_step)

        if is_auto:
            self.btn_pause = QPushButton("⏸ Pause", self)
            self.btn_pause.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.btn_pause.clicked.connect(self._toggle_pause)
            btn_layout.addWidget(self.btn_pause)

        self.btn_cancel = QPushButton("✕ Cancel (Esc)", self)
        self.btn_cancel.setObjectName("cancelBtn")
        self.btn_cancel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_cancel.clicked.connect(self.cancelRequested.emit)

        btn_layout.addWidget(self.btn_finish)
        btn_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_layout)

    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        if hasattr(self, "btn_pause"):
            self.btn_pause.setText("▶ Resume" if self.is_paused else "⏸ Pause")
        self.lbl_title.setText(f"⏸ Paused ({'Auto' if self.is_auto else 'Manual'})" if self.is_paused else f"🔴 Live Scrolling ({'Auto' if self.is_auto else 'Manual'})")
        self.pauseToggled.emit(self.is_paused)

    def update_status(self, height: int, frames: int, preview_img: Optional[QImage] = None):
        self.lbl_stats.setText(f"Height: {height:,} px  ·  Frames: {frames}")
        if preview_img and not preview_img.isNull():
            self.thumbnail.update_thumbnail(preview_img)
