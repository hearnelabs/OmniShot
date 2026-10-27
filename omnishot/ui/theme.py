"""
OmniShot Theme - ShareX Professional Dark Theme
Matches the ShareX Image Editor aesthetic:
Dark neutral canvas, vibrant blue tool selections (#0078d4),
contextual options sub-toolbar, and bottom action capsule.
"""

SHAREX_DARK_QSS = """
QMainWindow, QDialog {
    background-color: #1e1e1e;
    color: #cccccc;
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 13px;
}

QWidget {
    background-color: #1e1e1e;
    color: #cccccc;
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 13px;
}

/* Primary Top Toolbar */
QToolBar#primaryToolBar {
    background-color: #252526;
    border-bottom: 1px solid #333337;
    padding: 4px 8px;
    spacing: 3px;
}

/* Secondary Contextual Options Bar */
QToolBar#contextualToolBar {
    background-color: #2d2d30;
    border-bottom: 1px solid #3e3e42;
    padding: 3px 12px;
    spacing: 8px;
}

QToolButton {
    background-color: transparent;
    color: #cccccc;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 13px;
}

QToolButton:hover {
    background-color: #3e3e42;
    border: 1px solid #4e4e52;
}

QToolButton:checked {
    background-color: #0078d4;
    color: #ffffff;
    border: 1px solid #1084d8;
}

QToolButton:pressed {
    background-color: #005a9e;
}

/* Special High-Visibility Scrolling Capture Button */
QToolButton#scrollingCaptureBtn {
    background-color: #107c41;
    color: #ffffff;
    font-weight: bold;
    border: 1px solid #168c4a;
    border-radius: 4px;
    padding: 5px 12px;
}

QToolButton#scrollingCaptureBtn:hover {
    background-color: #168c4a;
}

/* SpinBox & ComboBox in Context Bar */
QSpinBox, QComboBox {
    background-color: #333337;
    color: #ffffff;
    border: 1px solid #434346;
    border-radius: 3px;
    padding: 3px 6px;
    font-size: 12px;
}

QSpinBox:hover, QComboBox:hover {
    border: 1px solid #0078d4;
}

/* Bottom Floating Pill Container */
QFrame#bottomActionPill {
    background-color: rgba(37, 37, 38, 0.95);
    border: 1.5px solid #434346;
    border-radius: 24px;
    padding: 4px 10px;
}

/* Big Green Finish Play/Check Button */
QPushButton#finishGreenBtn {
    background-color: #107c41;
    color: #ffffff;
    border: none;
    border-radius: 17px;
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
    font-size: 16px;
    font-weight: bold;
}

QPushButton#finishGreenBtn:hover {
    background-color: #16c60c;
}

QPushButton#finishGreenBtn:pressed {
    background-color: #0e6b37;
}

/* Red Cancel Button */
QPushButton#cancelRedBtn {
    background-color: #c42b1c;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
    font-size: 14px;
    font-weight: bold;
}

QPushButton#cancelRedBtn:hover {
    background-color: #e81123;
}

/* Standard Pill Action Buttons */
QToolButton#pillActionBtn {
    background-color: transparent;
    color: #d4d4d4;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px 8px;
    font-size: 14px;
}

QToolButton#pillActionBtn:hover {
    background-color: #3e3e42;
    border: 1px solid #4e4e52;
}

QScrollArea {
    background-color: #1e1e1e;
    border: none;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #1e1e1e;
    width: 12px;
    height: 12px;
    margin: 0px;
}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #424242;
    min-height: 20px;
    min-width: 20px;
    border-radius: 6px;
    margin: 2px;
}

QScrollBar::handle:hover {
    background-color: #0078d4;
}

QStatusBar {
    background-color: #007acc;
    color: #ffffff;
    font-size: 12px;
}
"""
