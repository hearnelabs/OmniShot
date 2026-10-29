"""
OmniShot Paste & Canvas Expansion Dialog
Allows user to expand the current canvas (Right, Down, Left, Up) when pasting
a secondary screenshot, or insert it as a movable vector overlay sticker.
"""

from typing import Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QFrame, QScrollArea
)
from PySide6.QtGui import (
    QImage, QPixmap, QIcon, QPainter, QColor, QFont, QKeyEvent
)
from PySide6.QtCore import Qt, QSize, Signal

from .theme import OMNISHOT_DARK_QSS


class DirectionButton(QPushButton):
    """Rich interactive card button for choosing canvas expansion direction."""
    def __init__(self, title: str, subtitle: str, badge: str, key_hint: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(64)
        self.setStyleSheet("""
            QPushButton {
                background-color: #1e222a;
                border: 1.5px solid #2e3440;
                border-radius: 8px;
                padding: 6px 14px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #272d38;
                border-color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #1a1e26;
                border-color: #005a9e;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)

        # Text column
        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(2)

        lbl_title = QLabel(title, self)
        lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffffff;")
        v_layout.addWidget(lbl_title)

        lbl_sub = QLabel(subtitle, self)
        lbl_sub.setStyleSheet("font-size: 11px; color: #8a93a0;")
        v_layout.addWidget(lbl_sub)
        layout.addLayout(v_layout, 1)

        # Badge column
        if badge:
            lbl_badge = QLabel(badge, self)
            lbl_badge.setStyleSheet("""
                background-color: rgba(0, 120, 212, 0.15);
                border: 1px solid rgba(0, 120, 212, 0.4);
                border-radius: 4px;
                padding: 3px 8px;
                color: #3daee9;
                font-size: 11px;
                font-family: monospace;
                font-weight: 600;
            """)
            layout.addWidget(lbl_badge)

        # Key hint pill
        if key_hint:
            lbl_key = QLabel(key_hint, self)
            lbl_key.setStyleSheet("""
                background-color: #2a303c;
                border: 1px solid #3e4450;
                border-radius: 4px;
                padding: 2px 7px;
                color: #e4e7eb;
                font-size: 10px;
                font-family: monospace;
                font-weight: bold;
            """)
            layout.addWidget(lbl_key)


class PasteExpandDialog(QDialog):
    """
    Dialog asking where to expand the screenshot when pasting another image:
    - Right
    - Down
    - Left
    - Up
    - Overlay (Sticker)
    """
    def __init__(self, current_img: QImage, pasted_img: QImage, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OmniShot — Expand Canvas with Pasted Image")
        self.setMinimumWidth(640)
        self.setStyleSheet(OMNISHOT_DARK_QSS)

        icon_path = Path(__file__).parent.parent.parent / "omnishot.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.current_img = current_img
        self.pasted_img = pasted_img

        self.chosen_action: str = "right"
        self.gap: int = 0
        self.alignment: str = "center"
        self.bg_color: QColor = QColor(0, 0, 0, 0) # transparent by default

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(14)

        # Header Title
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_head = QLabel("📋 Paste Image into Canvas", self)
        lbl_head.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        title_box.addWidget(lbl_head)

        lbl_sub = QLabel("Choose how to combine the clipboard screenshot with your current image:", self)
        lbl_sub.setStyleSheet("font-size: 12px; color: #a0a8b4;")
        title_box.addWidget(lbl_sub)
        main_layout.addLayout(title_box)

        # Visual Image Comparison Cards (Current + Pasted)
        cards_frame = QFrame(self)
        cards_frame.setStyleSheet("""
            QFrame {
                background-color: #16191f;
                border: 1px solid #2a2e36;
                border-radius: 8px;
            }
        """)
        cards_layout = QHBoxLayout(cards_frame)
        cards_layout.setContentsMargins(14, 12, 14, 12)
        cards_layout.setSpacing(16)

        # Card 1: Current Image
        w1, h1 = self.current_img.width(), self.current_img.height()
        c1_box = QVBoxLayout()
        c1_box.setSpacing(4)
        c1_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        thumb1 = QLabel(self)
        thumb1.setFixedSize(140, 85)
        thumb1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb1.setStyleSheet("background-color: #101216; border: 1px solid #333a46; border-radius: 4px;")
        pm1 = QPixmap.fromImage(self.current_img).scaled(136, 81, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        thumb1.setPixmap(pm1)
        c1_box.addWidget(thumb1)

        lbl_c1 = QLabel(f"Current Canvas\n<b>{w1} × {h1} px</b>", self)
        lbl_c1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_c1.setStyleSheet("font-size: 11px; color: #8a93a0;")
        c1_box.addWidget(lbl_c1)
        cards_layout.addLayout(c1_box)

        # Plus indicator
        lbl_plus = QLabel("+", self)
        lbl_plus.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d4;")
        lbl_plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(lbl_plus)

        # Card 2: Pasted Image
        w2, h2 = self.pasted_img.width(), self.pasted_img.height()
        c2_box = QVBoxLayout()
        c2_box.setSpacing(4)
        c2_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        thumb2 = QLabel(self)
        thumb2.setFixedSize(140, 85)
        thumb2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb2.setStyleSheet("background-color: #101216; border: 1px solid #333a46; border-radius: 4px;")
        pm2 = QPixmap.fromImage(self.pasted_img).scaled(136, 81, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        thumb2.setPixmap(pm2)
        c2_box.addWidget(thumb2)

        lbl_c2 = QLabel(f"Clipboard Screenshot\n<b>{w2} × {h2} px</b>", self)
        lbl_c2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_c2.setStyleSheet("font-size: 11px; color: #3daee9;")
        c2_box.addWidget(lbl_c2)
        cards_layout.addLayout(c2_box)

        main_layout.addWidget(cards_frame)

        # Action Buttons Section
        lbl_actions = QLabel("Where to expand the canvas?", self)
        lbl_actions.setStyleSheet("font-size: 12px; font-weight: bold; color: #ffffff; margin-top: 4px;")
        main_layout.addWidget(lbl_actions)

        # 1. Expand Right
        self.btn_right = DirectionButton(
            title="➡️  Expand Right",
            subtitle="Append to the right of current canvas (Side-by-Side)",
            badge=f"➔ {w1 + w2} × {max(h1, h2)} px",
            key_hint="R / →",
            parent=self
        )
        self.btn_right.clicked.connect(lambda: self._select_action("right"))
        main_layout.addWidget(self.btn_right)

        # 2. Expand Down
        self.btn_down = DirectionButton(
            title="⬇️  Expand Down",
            subtitle="Append below current canvas (Vertical Stack)",
            badge=f"➔ {max(w1, w2)} × {h1 + h2} px",
            key_hint="D / ↓",
            parent=self
        )
        self.btn_down.clicked.connect(lambda: self._select_action("down"))
        main_layout.addWidget(self.btn_down)

        # 3. Expand Left
        self.btn_left = DirectionButton(
            title="⬅️  Expand Left",
            subtitle="Prepend to the left of current canvas",
            badge=f"➔ {w1 + w2} × {max(h1, h2)} px",
            key_hint="L / ←",
            parent=self
        )
        self.btn_left.clicked.connect(lambda: self._select_action("left"))
        main_layout.addWidget(self.btn_left)

        # 4. Expand Up
        self.btn_up = DirectionButton(
            title="⬆️  Expand Up",
            subtitle="Prepend above current canvas",
            badge=f"➔ {max(w1, w2)} × {h1 + h2} px",
            key_hint="U / ↑",
            parent=self
        )
        self.btn_up.clicked.connect(lambda: self._select_action("up"))
        main_layout.addWidget(self.btn_up)

        # 5. Overlay Sticker
        self.btn_overlay = DirectionButton(
            title="🖼️  Insert as Overlay Sticker",
            subtitle="Place directly on top as a movable / resizable annotation (No canvas resizing)",
            badge="Annotation",
            key_hint="O",
            parent=self
        )
        self.btn_overlay.clicked.connect(lambda: self._select_action("overlay"))
        main_layout.addWidget(self.btn_overlay)

        # Optional Settings Bar (Gap, Alignment, Background)
        opt_box = QHBoxLayout()
        opt_box.setSpacing(12)

        # Gap
        lbl_gap = QLabel("Spacing (Gap):", self)
        lbl_gap.setStyleSheet("font-size: 11px; color: #a0a8b4;")
        opt_box.addWidget(lbl_gap)

        self.spin_gap = QSpinBox(self)
        self.spin_gap.setRange(0, 200)
        self.spin_gap.setValue(0)
        self.spin_gap.setSuffix(" px")
        self.spin_gap.setFixedWidth(80)
        opt_box.addWidget(self.spin_gap)

        # Alignment
        lbl_align = QLabel("Alignment:", self)
        lbl_align.setStyleSheet("font-size: 11px; color: #a0a8b4; margin-left: 10px;")
        opt_box.addWidget(lbl_align)

        self.combo_align = QComboBox(self)
        self.combo_align.addItem("Center (Default)", "center")
        self.combo_align.addItem("Top / Left", "top")
        self.combo_align.addItem("Bottom / Right", "bottom")
        self.combo_align.setFixedWidth(130)
        opt_box.addWidget(self.combo_align)

        # Background Fill
        lbl_bg = QLabel("Background:", self)
        lbl_bg.setStyleSheet("font-size: 11px; color: #a0a8b4; margin-left: 10px;")
        opt_box.addWidget(lbl_bg)

        self.combo_bg = QComboBox(self)
        self.combo_bg.addItem("Transparent", "transparent")
        self.combo_bg.addItem("Dark Theme (#1e2227)", "dark")
        self.combo_bg.addItem("White (#ffffff)", "white")
        self.combo_bg.setFixedWidth(140)
        opt_box.addWidget(self.combo_bg)

        opt_box.addStretch()
        main_layout.addLayout(opt_box)

        # Bottom Cancel Button
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_cancel = QPushButton("Cancel (Esc)", self)
        self.btn_cancel.setFixedWidth(110)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_box)

    def _select_action(self, action: str):
        self.chosen_action = action
        self.gap = self.spin_gap.value()
        self.alignment = self.combo_align.currentData() or "center"

        bg_mode = self.combo_bg.currentData()
        if bg_mode == "dark":
            self.bg_color = QColor("#1e2227")
        elif bg_mode == "white":
            self.bg_color = QColor("#ffffff")
        else:
            self.bg_color = QColor(0, 0, 0, 0) # transparent

        self.accept()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key.Key_R, Qt.Key.Key_Right):
            self._select_action("right")
        elif key in (Qt.Key.Key_D, Qt.Key.Key_Down):
            self._select_action("down")
        elif key in (Qt.Key.Key_L, Qt.Key.Key_Left):
            self._select_action("left")
        elif key in (Qt.Key.Key_U, Qt.Key.Key_Up):
            self._select_action("up")
        elif key == Qt.Key.Key_O:
            self._select_action("overlay")
        elif key == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
