"""
OmniShot Theme - ShareX Professional Dark Theme (KDE Plasma 6 Native)
Faithfully implements the modern ShareX Pro ribbon, right-hand palette drawer,
and bottom action capsule.
"""

SHAREX_DARK_QSS = """
QMainWindow, QDialog {
    background-color: #14171c;
    color: #eff0f1;
    font-family: "Noto Sans", "Segoe UI", sans-serif;
    font-size: 13px;
}

QWidget {
    background-color: transparent;
    color: #eff0f1;
    font-family: "Noto Sans", "Segoe UI", sans-serif;
    font-size: 13px;
}

/* Primary Top Categorized Ribbon Bar */
QFrame#ribbonBar {
    background-color: #1b1e24;
    border-bottom: 1.5px solid #2a2e36;
}

/* Ribbon Groups */
QFrame#ribbonGroup {
    background-color: transparent;
    border: none;
    margin: 0px;
}

QFrame#groupDivider {
    background-color: rgba(255, 255, 255, 0.12);
    width: 1px;
    max-width: 1px;
    margin: 8px 6px;
}

/* Ribbon Tool Buttons */
QToolButton.ribbonBtn {
    background-color: transparent;
    color: #d8dce2;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 3px 2px;
    font-size: 11px;
    font-weight: 500;
}

QToolButton.ribbonBtn:hover {
    background-color: rgba(61, 174, 233, 0.18);
    border: 1px solid rgba(61, 174, 233, 0.45);
    color: #ffffff;
}

QToolButton.ribbonBtn:checked {
    background-color: #0078d4;
    border: 1px solid #3daee9;
    color: #ffffff;
    font-weight: 600;
}

QToolButton.ribbonBtn:pressed {
    background-color: #005a9e;
}

/* Special High-Visibility Scrolling Capture Button in Ribbon */
QToolButton#scrollingCaptureRibbonBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #1e824c);
    border: 1.5px solid #2ecc71;
    border-radius: 6px;
    color: #ffffff;
    font-weight: bold;
}

QToolButton#scrollingCaptureRibbonBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2ecc71, stop:1 #27ae60);
    border: 1.5px solid #a3e4d7;
}

/* Right-Hand Properties Panel */
QFrame#propertiesPanel {
    background-color: #171a20;
    border-left: 1.5px solid #2a2e36;
}

QLabel.panelHeader {
    color: #e4e7eb;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

QLabel.propLabel {
    color: #a0a8b4;
    font-size: 12px;
}

/* Color Swatches Grid */
QPushButton.swatchBtn {
    border: 2px solid #2a2e36;
    border-radius: 4px;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
}

QPushButton.swatchBtn:hover {
    border: 2px solid #3daee9;
}

QPushButton.swatchBtn:checked {
    border: 2px solid #ffffff;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 4px;
    background: #2a2e36;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #0078d4;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 1px solid #3daee9;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #3daee9;
}

/* SpinBoxes */
QSpinBox {
    background-color: #242830;
    color: #ffffff;
    border: 1px solid #3a404c;
    border-radius: 4px;
    padding: 3px 6px;
    font-size: 12px;
}

QSpinBox:hover, QSpinBox:focus {
    border: 1px solid #0078d4;
}

/* Bottom Floating Pill Container */
QFrame#bottomActionPill {
    background-color: rgba(18, 22, 28, 245);
    border: 1.5px solid rgba(61, 174, 233, 0.45);
    border-radius: 22px;
    padding: 4px 10px;
}

/* Big Green Finish Play/Check Button */
QPushButton#finishGreenBtn {
    background-color: #27ae60;
    color: #ffffff;
    border: 1px solid #2ecc71;
    border-radius: 16px;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    font-size: 14px;
    font-weight: bold;
}

QPushButton#finishGreenBtn:hover {
    background-color: #2ecc71;
    border: 1px solid #a3e4d7;
}

/* Red Cancel Button */
QPushButton#cancelRedBtn {
    background-color: rgba(231, 76, 60, 0.2);
    color: #ff7675;
    border: 1px solid rgba(231, 76, 60, 0.4);
    border-radius: 16px;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    font-size: 14px;
    font-weight: bold;
}

QPushButton#cancelRedBtn:hover {
    background-color: #c0392b;
    border: 1px solid #e74c3c;
    color: #ffffff;
}

/* Standard Pill Action Buttons */
QToolButton#pillActionBtn {
    background-color: rgba(255, 255, 255, 0.08);
    color: #d8dce2;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 500;
}

QToolButton#pillActionBtn:hover {
    background-color: rgba(61, 174, 233, 0.22);
    border: 1px solid #3daee9;
    color: #ffffff;
}

QScrollArea {
    background-color: #121519;
    border: none;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #121519;
    width: 10px;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #2a2e36;
    min-height: 20px;
    min-width: 20px;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar::handle:hover {
    background-color: #0078d4;
}

QMenu {
    background-color: #1b1e24;
    color: #eff0f1;
    border: 1px solid #3a404c;
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}
"""
