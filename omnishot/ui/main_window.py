"""
OmniShot Main Window and Spectacle-Style Annotator
Provides screenshot viewing, editing, annotation tools, OCR extraction,
and comprehensive export options.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QToolBar,
    QToolButton, QPushButton, QLabel, QScrollArea, QFileDialog,
    QMessageBox, QDialog, QTextEdit, QStatusBar, QSpinBox,
    QColorDialog, QButtonGroup, QFrame
)
from PySide6.QtGui import (
    QImage, QPixmap, QIcon, QKeySequence, QShortcut, QColor, QFont, QClipboard, QGuiApplication
)
from PySide6.QtCore import Qt, QSize, Signal, QRect

from ..core.config import OmniShotConfig
from ..core.ocr import OCREngine
from .canvas import AnnotationCanvas, AnnotationTool
from .theme import BREEZE_DARK_QSS, ANNOTATION_PALETTE

class OCRDialog(QDialog):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OmniShot - Extracted Text (OCR)")
        self.resize(500, 350)
        self.setStyleSheet(BREEZE_DARK_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        lbl = QLabel("Text extracted from screenshot:", self)
        lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #3daee9;")
        layout.addWidget(lbl)

        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(text)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1a1c1e;
                color: #eff0f1;
                border: 1px solid #31363b;
                border-radius: 6px;
                padding: 8px;
                font-family: monospace;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.text_edit)

        btn_layout = QHBoxLayout()
        btn_copy = QPushButton("📋 Copy to Clipboard", self)
        btn_copy.setObjectName("primaryBtn")
        btn_copy.clicked.connect(self._copy_text)

        btn_close = QPushButton("Close", self)
        btn_close.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_copy)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _copy_text(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        QMessageBox.information(self, "Copied", "Extracted text copied to clipboard!")


class OmniShotMainWindow(QMainWindow):
    requestCapture = Signal(str) # "region", "scroll_auto", "scroll_manual", "fullscreen", "window"

    def __init__(self, config: Optional[OmniShotConfig] = None, parent=None):
        super().__init__(parent)
        self.config = config or OmniShotConfig.load()
        self.setWindowTitle("OmniShot - Spectacle with Scrolling Capture")
        self.resize(1100, 750)
        self.setStyleSheet(BREEZE_DARK_QSS)

        # Central widgets
        self._init_ui()
        self._setup_shortcuts()

    def _init_ui(self):
        # Canvas
        self.canvas = AnnotationCanvas(self)
        self.canvas.statusMessage.connect(self._on_canvas_status)
        self.canvas.imageChanged.connect(self._on_image_changed)

        # Scroll Area container
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.canvas)
        self.setCentralWidget(self.scroll_area)

        # Toolbars
        self._create_top_toolbar()
        self._create_annotation_toolbar()

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.lbl_dims = QLabel("No image", self)
        self.lbl_zoom = QLabel("100%", self)
        self.status_bar.addPermanentWidget(self.lbl_dims)
        self.status_bar.addPermanentWidget(self.lbl_zoom)
        self.status_bar.showMessage("Ready. Click 'Scrolling Capture' or 'New Region' to start.")

    def _create_top_toolbar(self):
        tb = QToolBar("Capture Actions", self)
        tb.setIconSize(QSize(20, 20))
        tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        # Primary Scrolling Capture button
        btn_scroll = QPushButton("📜 Scrolling Capture", self)
        btn_scroll.setObjectName("primaryBtn")
        btn_scroll.setToolTip("Start a seamless vertical scrolling screenshot (Auto / Manual)")
        btn_scroll.clicked.connect(lambda: self.requestCapture.emit("scroll_auto"))
        tb.addWidget(btn_scroll)

        tb.addSeparator()

        btn_region = QPushButton("🔲 Region", self)
        btn_region.setToolTip("Capture a rectangular region (Shift+Print)")
        btn_region.clicked.connect(lambda: self.requestCapture.emit("region"))
        tb.addWidget(btn_region)

        btn_window = QPushButton("🪟 Active Window", self)
        btn_window.setToolTip("Capture the active window")
        btn_window.clicked.connect(lambda: self.requestCapture.emit("window"))
        tb.addWidget(btn_window)

        btn_full = QPushButton("🖥️ Full Screen", self)
        btn_full.setToolTip("Capture entire desktop workspace")
        btn_full.clicked.connect(lambda: self.requestCapture.emit("fullscreen"))
        tb.addWidget(btn_full)

        tb.addSeparator()

        # Copy & Save Actions
        self.btn_copy = QPushButton("📋 Copy", self)
        self.btn_copy.setToolTip("Copy screenshot to clipboard (Ctrl+C)")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        tb.addWidget(self.btn_copy)

        self.btn_save = QPushButton("💾 Quick Save", self)
        self.btn_save.setObjectName("accentBtn")
        self.btn_save.setToolTip(f"Save to {self.config.save_directory} (Ctrl+S)")
        self.btn_save.clicked.connect(self.quick_save)
        tb.addWidget(self.btn_save)

        self.btn_save_as = QPushButton("Save As...", self)
        self.btn_save_as.setToolTip("Choose file path and save (Ctrl+Shift+S)")
        self.btn_save_as.clicked.connect(self.save_as)
        tb.addWidget(self.btn_save_as)

        tb.addSeparator()

        # OCR Extract Text
        btn_ocr = QPushButton("🔤 Extract Text (OCR)", self)
        btn_ocr.setToolTip("Extract all text from the current capture via Tesseract OCR")
        btn_ocr.clicked.connect(self.extract_ocr_text)
        tb.addWidget(btn_ocr)

    def _create_annotation_toolbar(self):
        tb = QToolBar("Annotation Tools", self)
        tb.setIconSize(QSize(18, 18))
        tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)

        tools = [
            (AnnotationTool.SELECT, "↖ Select / Pan", "Select and pan (Ctrl+Drag)"),
            (AnnotationTool.PEN, "✏️ Pen", "Draw freehand annotations"),
            (AnnotationTool.HIGHLIGHTER, "🖍️ Highlight", "Translucent highlighter"),
            (AnnotationTool.ARROW, "➡️ Arrow", "Draw arrows pointing to items"),
            (AnnotationTool.LINE, "📏 Line", "Straight line"),
            (AnnotationTool.RECTANGLE, "🔲 Box", "Draw rectangle border"),
            (AnnotationTool.ELLIPSE, "⭕ Circle", "Draw circle or ellipse"),
            (AnnotationTool.NUMBER_BADGE, "🔢 1-2-3", "Click to place numbered step badges (1, 2, 3...)"),
            (AnnotationTool.TEXT, "🔤 Text", "Click to add text box"),
            (AnnotationTool.BLUR, "💧 Blur/Pixelate", "Obfuscate sensitive credentials or PII"),
            (AnnotationTool.CROP, "✂️ Crop", "Crop image to box"),
        ]

        for tool_id, label, tip in tools:
            btn = QToolButton(self)
            btn.setText(label)
            btn.setCheckable(True)
            btn.setToolTip(tip)
            if tool_id == AnnotationTool.PEN:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, t=tool_id: self._select_tool(t))
            self.tool_group.addButton(btn)
            tb.addWidget(btn)

        tb.addSeparator()

        # Stroke thickness
        lbl_w = QLabel(" Width: ", self)
        tb.addWidget(lbl_w)
        self.spin_width = QSpinBox(self)
        self.spin_width.setRange(1, 40)
        self.spin_width.setValue(self.config.default_stroke_width)
        self.spin_width.valueChanged.connect(self._on_stroke_width_changed)
        tb.addWidget(self.spin_width)

        tb.addSeparator()

        # Color Swatches
        lbl_c = QLabel(" Color: ", self)
        tb.addWidget(lbl_c)
        for hex_code in ANNOTATION_PALETTE:
            swatch = QPushButton(self)
            swatch.setFixedSize(20, 20)
            swatch.setStyleSheet(f"background-color: {hex_code}; border-radius: 10px; border: 1.5px solid #555;")
            swatch.setToolTip(hex_code)
            swatch.clicked.connect(lambda checked, c=hex_code: self._set_color(c))
            tb.addWidget(swatch)

        btn_more_color = QToolButton(self)
        btn_more_color.setText("🎨")
        btn_more_color.setToolTip("Custom Color...")
        btn_more_color.clicked.connect(self._pick_custom_color)
        tb.addWidget(btn_more_color)

        tb.addSeparator()

        # Undo / Redo
        self.btn_undo = QToolButton(self)
        self.btn_undo.setText("↩ Undo")
        self.btn_undo.setToolTip("Undo last annotation (Ctrl+Z)")
        self.btn_undo.clicked.connect(self.canvas.undo)
        tb.addWidget(self.btn_undo)

        self.btn_redo = QToolButton(self)
        self.btn_redo.setText("↪ Redo")
        self.btn_redo.setToolTip("Redo (Ctrl+Y)")
        self.btn_redo.clicked.connect(self.canvas.redo)
        tb.addWidget(self.btn_redo)

        tb.addSeparator()

        # Zoom buttons
        btn_zin = QToolButton(self)
        btn_zin.setText("🔍+")
        btn_zin.setToolTip("Zoom In (Ctrl++)")
        btn_zin.clicked.connect(self.canvas.zoom_in)
        tb.addWidget(btn_zin)

        btn_zout = QToolButton(self)
        btn_zout.setText("🔍-")
        btn_zout.setToolTip("Zoom Out (Ctrl+-)")
        btn_zout.clicked.connect(self.canvas.zoom_out)
        tb.addWidget(btn_zout)

        btn_z100 = QToolButton(self)
        btn_z100.setText("100%")
        btn_z100.setToolTip("Reset Zoom to 100%")
        btn_z100.clicked.connect(self.canvas.zoom_reset)
        tb.addWidget(btn_z100)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+C"), self, self.copy_to_clipboard)
        QShortcut(QKeySequence("Ctrl+S"), self, self.quick_save)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self.save_as)
        QShortcut(QKeySequence("Ctrl+Z"), self, self.canvas.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self.canvas.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, self.canvas.redo)
        QShortcut(QKeySequence("Ctrl+="), self, self.canvas.zoom_in)
        QShortcut(QKeySequence("Ctrl++"), self, self.canvas.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self.canvas.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self.canvas.zoom_reset)

    def set_captured_image(self, image: QImage):
        """Loads a newly taken screenshot into canvas."""
        self.canvas.set_image(image)
        self._update_info()
        self.show()
        self.raise_()
        self.activateWindow()

    def _select_tool(self, tool_id: str):
        self.canvas.current_tool = tool_id
        self.status_bar.showMessage(f"Tool selected: {tool_id.title()}")

    def _set_color(self, hex_code: str):
        self.canvas.current_color = QColor(hex_code)
        self.status_bar.showMessage(f"Color: {hex_code}")

    def _pick_custom_color(self):
        c = QColorDialog.getColor(self.canvas.current_color, self, "Select Annotation Color")
        if c.isValid():
            self._set_color(c.name())

    def _on_stroke_width_changed(self, val: int):
        self.canvas.current_stroke_width = val

    def _on_canvas_status(self, msg: str):
        self.status_bar.showMessage(msg)

    def _on_image_changed(self):
        self._update_info()

    def _update_info(self):
        img = self.canvas.get_image()
        if img and not img.isNull():
            self.lbl_dims.setText(f"{img.width()} × {img.height()} px")
            self.lbl_zoom.setText(f"{int(self.canvas._zoom * 100)}%")
            self.btn_copy.setEnabled(True)
            self.btn_save.setEnabled(True)
            self.btn_save_as.setEnabled(True)
        else:
            self.lbl_dims.setText("No image")
            self.lbl_zoom.setText("100%")
            self.btn_copy.setEnabled(False)
            self.btn_save.setEnabled(False)
            self.btn_save_as.setEnabled(False)

    def copy_to_clipboard(self):
        img = self.canvas.get_image()
        if not img or img.isNull():
            return
        clipboard = QGuiApplication.clipboard()
        clipboard.setImage(img)
        self.status_bar.showMessage("✓ Screenshot copied to clipboard!")

    def quick_save(self):
        img = self.canvas.get_image()
        if not img or img.isNull():
            return

        save_dir = Path(self.config.save_directory)
        save_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        filename = now.strftime(self.config.filename_template)
        file_path = save_dir / filename

        success = img.save(str(file_path))
        if success:
            if self.config.copy_to_clipboard_on_save:
                self.copy_to_clipboard()
            self.status_bar.showMessage(f"✓ Saved to {file_path}")
            # Try to send desktop notification
            self._notify_saved(str(file_path))
        else:
            QMessageBox.critical(self, "Save Error", f"Failed to save screenshot to:\n{file_path}")

    def save_as(self):
        img = self.canvas.get_image()
        if not img or img.isNull():
            return

        now = datetime.now()
        default_name = now.strftime(self.config.filename_template)
        default_path = str(Path(self.config.save_directory) / default_name)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Screenshot As",
            default_path,
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;WebP Image (*.webp)"
        )
        if path:
            success = img.save(path)
            if success:
                self.status_bar.showMessage(f"✓ Saved to {path}")
                self._notify_saved(path)
            else:
                QMessageBox.critical(self, "Save Error", f"Failed to save image to:\n{path}")

    def _notify_saved(self, path: str):
        try:
            import subprocess
            subprocess.run([
                "notify-send",
                "-a", "OmniShot",
                "-i", "spectacle",
                "Screenshot Saved",
                f"Saved to {os.path.basename(path)}"
            ], check=False)
        except Exception:
            pass

    def extract_ocr_text(self):
        img = self.canvas.get_image()
        if not img or img.isNull():
            QMessageBox.information(self, "OCR", "No screenshot to extract text from.")
            return

        self.status_bar.showMessage("Extracting text via OCR...")
        text = OCREngine.extract_text(img)
        if text:
            dlg = OCRDialog(text, self)
            dlg.exec()
            self.status_bar.showMessage("OCR extraction complete.")
        else:
            QMessageBox.warning(self, "OCR Result", "No text detected in the image or OCR failed.")
            self.status_bar.showMessage("OCR found no text.")
