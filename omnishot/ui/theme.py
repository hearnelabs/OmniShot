"""
OmniShot KDE Plasma 6 Breeze Theme & Styling
Matches KDE Plasma 6 aesthetic with dark/light theme support.
"""

BREEZE_DARK_QSS = """
QMainWindow, QDialog {
    background-color: #232629;
    color: #eff0f1;
    font-family: "Noto Sans", "Cantarell", sans-serif;
    font-size: 13px;
}

QWidget {
    background-color: #232629;
    color: #eff0f1;
    font-family: "Noto Sans", "Cantarell", sans-serif;
    font-size: 13px;
}

QToolBar {
    background-color: #2a2e32;
    border-bottom: 1px solid #31363b;
    padding: 6px;
    spacing: 6px;
}

QToolButton {
    background-color: transparent;
    color: #eff0f1;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 6px 10px;
    font-weight: 500;
}

QToolButton:hover {
    background-color: #31363b;
    border: 1px solid #3daee9;
}

QToolButton:checked {
    background-color: #1d3b53;
    border: 1px solid #3daee9;
    color: #ffffff;
}

QToolButton:pressed {
    background-color: #264a66;
}

QPushButton {
    background-color: #31363b;
    color: #eff0f1;
    border: 1px solid #474e54;
    border-radius: 5px;
    padding: 7px 16px;
    font-weight: 500;
    min-width: 70px;
}

QPushButton:hover {
    background-color: #3b4249;
    border: 1px solid #3daee9;
}

QPushButton:pressed {
    background-color: #264a66;
    border: 1px solid #3daee9;
}

QPushButton#primaryBtn {
    background-color: #1d6fa5;
    border: 1px solid #3daee9;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#primaryBtn:hover {
    background-color: #2282c0;
}

QPushButton#primaryBtn:pressed {
    background-color: #165682;
}

QPushButton#accentBtn {
    background-color: #27ae60;
    border: 1px solid #2ecc71;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#accentBtn:hover {
    background-color: #2ecc71;
}

QPushButton#dangerBtn {
    background-color: #962d22;
    border: 1px solid #e74c3c;
    color: #ffffff;
}

QPushButton#dangerBtn:hover {
    background-color: #c0392b;
}

QScrollArea {
    background-color: #1b1e20;
    border: 1px solid #31363b;
    border-radius: 6px;
}

QScrollBar:vertical {
    background-color: #232629;
    width: 12px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #474e54;
    min-height: 24px;
    border-radius: 6px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #3daee9;
}

QScrollBar:horizontal {
    background-color: #232629;
    height: 12px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #474e54;
    min-width: 24px;
    border-radius: 6px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #3daee9;
}

QSlider::groove:horizontal {
    border: 1px solid #31363b;
    height: 6px;
    background: #1b1e20;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #3daee9;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #eff0f1;
    border: 1px solid #3daee9;
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #3daee9;
}

QStatusBar {
    background-color: #1d2023;
    color: #bdc3c7;
    border-top: 1px solid #31363b;
    font-size: 12px;
}

QLabel {
    color: #eff0f1;
}

QComboBox {
    background-color: #31363b;
    color: #eff0f1;
    border: 1px solid #474e54;
    border-radius: 5px;
    padding: 5px 10px;
    min-width: 90px;
}

QComboBox:hover {
    border: 1px solid #3daee9;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: none;
}

QComboBox QAbstractItemView {
    background-color: #2a2e32;
    border: 1px solid #3daee9;
    selection-background-color: #1d3b53;
    selection-color: #ffffff;
}

QSpinBox {
    background-color: #31363b;
    color: #eff0f1;
    border: 1px solid #474e54;
    border-radius: 5px;
    padding: 4px 8px;
}

QSpinBox:hover {
    border: 1px solid #3daee9;
}

QToolTip {
    background-color: #1b1e20;
    color: #ffffff;
    border: 1px solid #3daee9;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
}
"""

# Palette colors for annotations
ANNOTATION_PALETTE = [
    "#e74c3c", # Vibrant Red
    "#3daee9", # Breeze Blue
    "#2ecc71", # Emerald Green
    "#f1c40f", # Bright Yellow
    "#9b59b6", # Purple
    "#e67e22", # Orange
    "#ffffff", # White
    "#111111", # Dark
]
