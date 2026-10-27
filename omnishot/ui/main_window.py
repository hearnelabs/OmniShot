"""
OmniShot Main Window - ShareX Professional Image Editor
Faithfully implements the ShareX Image Editor layout and annotation suite:
- Primary top tool ribbon (Pointer, Shapes, Lines, Text, Speech, Step, Loupe, Redact, Crop)
- Secondary contextual options bar (Border Color, Fill Color, Thickness, Font Size, Bold/Italic/Underline, Shadow)
- Bottom floating action capsule (Zoom, Finish, Cancel, Copy, Save, Save As, OCR, Pin)
- Seamless integration with native KWin Wayland Scrolling Capture
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QToolBar,
    QToolButton, QPushButton, QLabel, QScrollArea, QFileDialog,
    QMessageBox, QDialog, QTextEdit, QStatusBar, QSpinBox,
    QColorDialog, QButtonGroup, QFrame, QMenu
)
from PySide6.QtGui import (
    QImage, QPixmap, QIcon, QKeySequence, QShortcut, QColor, QFont, QClipboard,
    QGuiApplication, QPainter, QPen, QBrush
)
from PySide6.QtCore import Qt, QSize, Signal, QRect, QPoint

from ..core.config import OmniShotConfig
from ..core.ocr import OCREngine
from .canvas import (
    AnnotationCanvas, ToolType, BaseAnnotation, TextAnnotation,
    RectAnnotation, SpeechBalloonAnnotation, StepBadgeAnnotation,
    RedactAnnotation
)
from .theme import SHAREX_DARK_QSS

class OCRDialog(QDialog):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OmniShot - Extracted Text (OCR)")
        self.resize(520, 360)
        self.setStyleSheet(SHAREX_DARK_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        lbl = QLabel("Text extracted from image:", self)
        lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #0078d4;")
        layout.addWidget(lbl)

        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(text)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 8px;
                font-family: monospace;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.text_edit)

        btn_layout = QHBoxLayout()
        btn_copy = QPushButton("📋 Copy to Clipboard", self)
        btn_copy.setStyleSheet("background-color: #0078d4; color: #ffffff; padding: 6px 16px; border-radius: 4px;")
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
        QMessageBox.information(self, "Copied", "Text copied to clipboard!")


class OmniShotMainWindow(QMainWindow):
    requestCapture = Signal(str) # "region", "scroll_auto", "scroll_manual", "fullscreen", "window"

    def __init__(self, config: Optional[OmniShotConfig] = None, parent=None):
        super().__init__(parent)
        self.config = config or OmniShotConfig.load()
        self.current_filename: str = "OmniShot_Image.png"
        self._is_pinned = False

        self.resize(1150, 800)
        self.setStyleSheet(SHAREX_DARK_QSS)

        self._init_ui()
        self._setup_shortcuts()
        self._update_window_title()

    def _init_ui(self):
        # 1. Central Viewport with Checkered Canvas
        self.canvas = AnnotationCanvas(self)
        self.canvas.statusMessage.connect(self._on_canvas_status)
        self.canvas.imageChanged.connect(self._on_image_changed)
        self.canvas.selectionChanged.connect(self._on_annotation_selection_changed)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.canvas)
        self.setCentralWidget(self.scroll_area)

        # 2. Toolbars
        self._create_primary_ribbon()
        self._create_contextual_options_bar()

        # 3. Bottom Floating Action Pill (ShareX signature capsule)
        self._create_bottom_action_pill()

    def _update_window_title(self):
        img = self.canvas.get_image()
        if img and not img.isNull():
            self.setWindowTitle(f"OmniShot - Image Editor - {img.width()}x{img.height()} - {self.current_filename}")
        else:
            self.setWindowTitle("OmniShot - Image Editor")

    def _create_primary_ribbon(self):
        """Row 1: ShareX-style Primary Annotation Tools Ribbon"""
        tb = QToolBar("Primary Tools", self)
        tb.setObjectName("primaryToolBar")
        tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        self.tool_button_group = QButtonGroup(self)
        self.tool_button_group.setExclusive(True)

        tools = [
            (ToolType.POINTER, "↖", "Select / Move (V)"),
            (ToolType.RECTANGLE, "🔲", "Rectangle (R)"),
            (ToolType.ROUNDED_RECT, "▢", "Rounded Rectangle (Shift+R)"),
            (ToolType.ELLIPSE, "⭕", "Ellipse (E)"),
            (ToolType.LINE, "─", "Line (L)"),
            (ToolType.ARROW, "➔", "Arrow (A)"),
            (ToolType.PEN, "✏️", "Freehand Pen (P)"),
            (ToolType.HIGHLIGHTER, "🖍️", "Highlighter (H)"),
            (ToolType.TEXT, "T", "Text (T)"),
            (ToolType.SPEECH_BALLOON, "💬", "Speech Balloon (C)"),
            (ToolType.STEP_BADGE, "#", "Step Badges 1-2-3 (S)"),
            (ToolType.MAGNIFY, "☡", "Magnifier Loupe (M)"),
            (ToolType.BLUR, "💧", "Blur Redaction (B)"),
            (ToolType.PIXELATE, "▦", "Pixelate Redaction (X)"),
            (ToolType.CROP, "✂️", "Crop Canvas (K)"),
        ]

        for tool_id, icon_char, tooltip in tools:
            btn = QToolButton(self)
            btn.setText(icon_char)
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            font = btn.font()
            font.setPointSize(13)
            font.setBold(True)
            btn.setFont(font)
            if tool_id == ToolType.POINTER:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, t=tool_id: self._on_tool_selected(t))
            self.tool_button_group.addButton(btn)
            tb.addWidget(btn)

        tb.addSeparator()

        # Capture Actions directly in top bar
        btn_scroll = QToolButton(self)
        btn_scroll.setObjectName("scrollingCaptureBtn")
        btn_scroll.setText("📜 Scrolling Capture")
        btn_scroll.setToolTip("Start Wayland Scrolling Capture (Auto / Manual)")
        btn_scroll.clicked.connect(lambda: self.requestCapture.emit("scroll_auto"))
        tb.addWidget(btn_scroll)

        btn_snip = QToolButton(self)
        btn_snip.setText("📸 New Snip")
        btn_snip.setToolTip("Capture a regional snip (Shift+Print)")
        btn_snip.clicked.connect(lambda: self.requestCapture.emit("region"))
        tb.addWidget(btn_snip)

    def _create_contextual_options_bar(self):
        """Row 2: Contextual Tool Options Bar (Directly underneath the tool ribbon)"""
        tb = QToolBar("Tool Options", self)
        tb.setObjectName("contextualToolBar")
        tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        self.context_bar = tb

        # 1. Border / Stroke Color Swatch Button
        self.btn_stroke_color = QToolButton(self)
        self.btn_stroke_color.setText("  Border  ▾")
        self.btn_stroke_color.setToolTip("Choose Border / Stroke Color")
        self.btn_stroke_color.clicked.connect(self._pick_stroke_color)
        tb.addWidget(self.btn_stroke_color)
        self._update_color_button_icon(self.btn_stroke_color, self.canvas.current_stroke_color)

        # 2. Fill Color Swatch Button
        self.btn_fill_color = QToolButton(self)
        self.btn_fill_color.setText("  Fill  ▾")
        self.btn_fill_color.setToolTip("Choose Fill Color (or Transparent)")
        self.btn_fill_color.clicked.connect(self._pick_fill_color)
        tb.addWidget(self.btn_fill_color)
        self._update_color_button_icon(self.btn_fill_color, self.canvas.current_fill_color)

        tb.addSeparator()

        # 3. Stroke Thickness SpinBox
        lbl_w = QLabel(" Thickness: ", self)
        tb.addWidget(lbl_w)
        self.spin_thickness = QSpinBox(self)
        self.spin_thickness.setRange(1, 40)
        self.spin_thickness.setValue(self.canvas.current_stroke_width)
        self.spin_thickness.setSuffix(" px")
        self.spin_thickness.valueChanged.connect(self._on_thickness_changed)
        tb.addWidget(self.spin_thickness)

        tb.addSeparator()

        # 4. Text Font Size SpinBox
        self.lbl_font_size = QLabel(" Font Size: ", self)
        tb.addWidget(self.lbl_font_size)
        self.spin_font_size = QSpinBox(self)
        self.spin_font_size.setRange(8, 120)
        self.spin_font_size.setValue(self.canvas.current_font_size)
        self.spin_font_size.setSuffix(" pt")
        self.spin_font_size.valueChanged.connect(self._on_font_size_changed)
        tb.addWidget(self.spin_font_size)

        # 5. Bold, Italic, Underline Toggles
        self.btn_bold = QToolButton(self)
        self.btn_bold.setText("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setChecked(True)
        font_b = self.btn_bold.font()
        font_b.setBold(True)
        self.btn_bold.setFont(font_b)
        self.btn_bold.clicked.connect(self._on_bold_toggled)
        tb.addWidget(self.btn_bold)

        self.btn_italic = QToolButton(self)
        self.btn_italic.setText("I")
        self.btn_italic.setCheckable(True)
        font_i = self.btn_italic.font()
        font_i.setItalic(True)
        self.btn_italic.setFont(font_i)
        self.btn_italic.clicked.connect(self._on_italic_toggled)
        tb.addWidget(self.btn_italic)

        self.btn_underline = QToolButton(self)
        self.btn_underline.setText("U")
        self.btn_underline.setCheckable(True)
        font_u = self.btn_underline.font()
        font_u.setUnderline(True)
        self.btn_underline.setFont(font_u)
        self.btn_underline.clicked.connect(self._on_underline_toggled)
        tb.addWidget(self.btn_underline)

        tb.addSeparator()

        # 6. Drop Shadow Toggle
        self.btn_shadow = QToolButton(self)
        self.btn_shadow.setText("Shadow")
        self.btn_shadow.setCheckable(True)
        self.btn_shadow.setChecked(True)
        self.btn_shadow.clicked.connect(self._on_shadow_toggled)
        tb.addWidget(self.btn_shadow)

        # 7. Undo / Redo
        tb.addSeparator()
        self.btn_undo = QToolButton(self)
        self.btn_undo.setText("↩ Undo")
        self.btn_undo.clicked.connect(self.canvas.undo)
        tb.addWidget(self.btn_undo)

        self.btn_redo = QToolButton(self)
        self.btn_redo.setText("↪ Redo")
        self.btn_redo.clicked.connect(self.canvas.redo)
        tb.addWidget(self.btn_redo)

    def _create_bottom_action_pill(self):
        """Bottom Floating Action Capsule (Matching ShareX bottom pill)"""
        self.action_pill = QFrame(self)
        self.action_pill.setObjectName("bottomActionPill")

        layout = QHBoxLayout(self.action_pill)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)

        # 1. Zoom Dropdown Button
        self.btn_zoom = QToolButton(self)
        self.btn_zoom.setObjectName("pillActionBtn")
        self.btn_zoom.setText("🔍 100% ▾")
        self.btn_zoom.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        zoom_menu = QMenu(self)
        zoom_menu.addAction("Fit Window", lambda: self._zoom_fit())
        zoom_menu.addAction("50%", lambda: self.canvas.set_zoom(0.5))
        zoom_menu.addAction("100%", lambda: self.canvas.set_zoom(1.0))
        zoom_menu.addAction("150%", lambda: self.canvas.set_zoom(1.5))
        zoom_menu.addAction("200%", lambda: self.canvas.set_zoom(2.0))
        self.btn_zoom.setMenu(zoom_menu)
        layout.addWidget(self.btn_zoom)

        # 2. Big Green Finish Play/Check Button (ShareX Signature)
        self.btn_finish = QPushButton("▶", self)
        self.btn_finish.setObjectName("finishGreenBtn")
        self.btn_finish.setToolTip("Finish & Copy to Clipboard")
        self.btn_finish.clicked.connect(self._finish_and_copy)
        layout.addWidget(self.btn_finish)

        # 3. Red Cancel Button
        self.btn_cancel = QPushButton("✕", self)
        self.btn_cancel.setObjectName("cancelRedBtn")
        self.btn_cancel.setToolTip("Discard / Close")
        self.btn_cancel.clicked.connect(self.close)
        layout.addWidget(self.btn_cancel)

        # 4. Standard action icons
        self.btn_copy = QToolButton(self)
        self.btn_copy.setObjectName("pillActionBtn")
        self.btn_copy.setText("📋")
        self.btn_copy.setToolTip("Copy to Clipboard (Ctrl+C)")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        layout.addWidget(self.btn_copy)

        self.btn_save = QToolButton(self)
        self.btn_save.setObjectName("pillActionBtn")
        self.btn_save.setText("💾")
        self.btn_save.setToolTip(f"Quick Save (Ctrl+S)")
        self.btn_save.clicked.connect(self.quick_save)
        layout.addWidget(self.btn_save)

        self.btn_save_as = QToolButton(self)
        self.btn_save_as.setObjectName("pillActionBtn")
        self.btn_save_as.setText("🗐")
        self.btn_save_as.setToolTip("Save As... (Ctrl+Shift+S)")
        self.btn_save_as.clicked.connect(self.save_as)
        layout.addWidget(self.btn_save_as)

        self.btn_ocr = QToolButton(self)
        self.btn_ocr.setObjectName("pillActionBtn")
        self.btn_ocr.setText("🔤")
        self.btn_ocr.setToolTip("Extract Text (OCR)")
        self.btn_ocr.clicked.connect(self.extract_ocr_text)
        layout.addWidget(self.btn_ocr)

        self.btn_pin = QToolButton(self)
        self.btn_pin.setObjectName("pillActionBtn")
        self.btn_pin.setText("📌")
        self.btn_pin.setToolTip("Pin to Screen (Always on top)")
        self.btn_pin.clicked.connect(self._toggle_pin)
        layout.addWidget(self.btn_pin)

        self.canvas.zoomChanged.connect(self._on_zoom_changed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Position floating pill at bottom center
        self.action_pill.adjustSize()
        pw = self.action_pill.width()
        ph = self.action_pill.height()
        px = (self.width() - pw) // 2
        py = self.height() - ph - 20
        self.action_pill.setGeometry(px, py, pw, ph)
        self.action_pill.raise_()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+C"), self, self.copy_to_clipboard)
        QShortcut(QKeySequence("Ctrl+S"), self, self.quick_save)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self.save_as)
        QShortcut(QKeySequence("Ctrl+Z"), self, self.canvas.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self.canvas.redo)
        QShortcut(QKeySequence("Ctrl++"), self, self.canvas.zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self, self.canvas.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self.canvas.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self.canvas.zoom_reset)

        # Single key tool shortcuts (ShareX standards)
        QShortcut(QKeySequence("V"), self, lambda: self._select_tool_by_type(ToolType.POINTER))
        QShortcut(QKeySequence("R"), self, lambda: self._select_tool_by_type(ToolType.RECTANGLE))
        QShortcut(QKeySequence("E"), self, lambda: self._select_tool_by_type(ToolType.ELLIPSE))
        QShortcut(QKeySequence("L"), self, lambda: self._select_tool_by_type(ToolType.LINE))
        QShortcut(QKeySequence("A"), self, lambda: self._select_tool_by_type(ToolType.ARROW))
        QShortcut(QKeySequence("P"), self, lambda: self._select_tool_by_type(ToolType.PEN))
        QShortcut(QKeySequence("H"), self, lambda: self._select_tool_by_type(ToolType.HIGHLIGHTER))
        QShortcut(QKeySequence("T"), self, lambda: self._select_tool_by_type(ToolType.TEXT))
        QShortcut(QKeySequence("C"), self, lambda: self._select_tool_by_type(ToolType.SPEECH_BALLOON))
        QShortcut(QKeySequence("S"), self, lambda: self._select_tool_by_type(ToolType.STEP_BADGE))
        QShortcut(QKeySequence("M"), self, lambda: self._select_tool_by_type(ToolType.MAGNIFY))
        QShortcut(QKeySequence("B"), self, lambda: self._select_tool_by_type(ToolType.BLUR))
        QShortcut(QKeySequence("X"), self, lambda: self._select_tool_by_type(ToolType.PIXELATE))
        QShortcut(QKeySequence("K"), self, lambda: self._select_tool_by_type(ToolType.CROP))

    def _select_tool_by_type(self, tool_type: str):
        for btn in self.tool_button_group.buttons():
            # Match tool
            if getattr(btn, "_tool_id", None) == tool_type:
                btn.setChecked(True)
                self._on_tool_selected(tool_type)
                break

    def _on_tool_selected(self, tool_type: str):
        self.canvas.current_tool = tool_type
        # Show/hide relevant contextual options based on tool
        is_text_tool = (tool_type in (ToolType.TEXT, ToolType.SPEECH_BALLOON))
        self.lbl_font_size.setVisible(is_text_tool)
        self.spin_font_size.setVisible(is_text_tool)
        self.btn_bold.setVisible(is_text_tool)
        self.btn_italic.setVisible(is_text_tool)
        self.btn_underline.setVisible(is_text_tool)

    def _update_color_button_icon(self, btn: QToolButton, color: QColor):
        pix = QPixmap(18, 18)
        if color.alpha() == 0:
            pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(pix)
            p.setPen(QPen(QColor("#cccccc"), 1.5))
            p.drawRect(1, 1, 15, 15)
            p.setPen(QPen(QColor("#e74c3c"), 2))
            p.drawLine(2, 16, 16, 2)
            p.end()
        else:
            pix.fill(color)
            p = QPainter(pix)
            p.setPen(QPen(QColor(255, 255, 255, 180), 1))
            p.drawRect(0, 0, 17, 17)
            p.end()
        btn.setIcon(QIcon(pix))

    def _pick_stroke_color(self):
        c = QColorDialog.getColor(self.canvas.current_stroke_color, self, "Select Border Color")
        if c.isValid():
            self.canvas.current_stroke_color = c
            self._update_color_button_icon(self.btn_stroke_color, c)
            if self.canvas.selected_annotation:
                self.canvas.selected_annotation.stroke_color = c
                if isinstance(self.canvas.selected_annotation, TextAnnotation):
                    self.canvas.selected_annotation.outline_color = c
                elif isinstance(self.canvas.selected_annotation, StepBadgeAnnotation):
                    self.canvas.selected_annotation.badge_color = c
                self.canvas.update()

    def _pick_fill_color(self):
        menu = QMenu(self)
        act_trans = menu.addAction("Transparent (No Fill)")
        act_custom = menu.addAction("Custom Color...")
        action = menu.exec(self.btn_fill_color.mapToGlobal(QPoint(0, self.btn_fill_color.height())))
        if action == act_trans:
            c = QColor(0, 0, 0, 0)
            self.canvas.current_fill_color = c
            self._update_color_button_icon(self.btn_fill_color, c)
            if self.canvas.selected_annotation:
                self.canvas.selected_annotation.fill_color = c
                self.canvas.update()
        elif action == act_custom:
            c = QColorDialog.getColor(self.canvas.current_fill_color, self, "Select Fill Color", QColorDialog.ColorDialogOption.ShowAlphaChannel)
            if c.isValid():
                self.canvas.current_fill_color = c
                self._update_color_button_icon(self.btn_fill_color, c)
                if self.canvas.selected_annotation:
                    self.canvas.selected_annotation.fill_color = c
                    self.canvas.update()

    def _on_thickness_changed(self, val: int):
        self.canvas.current_stroke_width = val
        if self.canvas.selected_annotation:
            self.canvas.selected_annotation.stroke_width = val
            self.canvas.update()

    def _on_font_size_changed(self, val: int):
        self.canvas.current_font_size = val
        if self.canvas.selected_annotation and isinstance(self.canvas.selected_annotation, (TextAnnotation, SpeechBalloonAnnotation)):
            self.canvas.selected_annotation.font_size = val
            self.canvas.update()

    def _on_bold_toggled(self, checked: bool):
        self.canvas.is_bold = checked
        if self.canvas.selected_annotation and isinstance(self.canvas.selected_annotation, TextAnnotation):
            self.canvas.selected_annotation.is_bold = checked
            self.canvas.update()

    def _on_italic_toggled(self, checked: bool):
        self.canvas.is_italic = checked
        if self.canvas.selected_annotation and isinstance(self.canvas.selected_annotation, TextAnnotation):
            self.canvas.selected_annotation.is_italic = checked
            self.canvas.update()

    def _on_underline_toggled(self, checked: bool):
        self.canvas.is_underline = checked
        if self.canvas.selected_annotation and isinstance(self.canvas.selected_annotation, TextAnnotation):
            self.canvas.selected_annotation.is_underline = checked
            self.canvas.update()

    def _on_shadow_toggled(self, checked: bool):
        self.canvas.has_shadow = checked
        if self.canvas.selected_annotation:
            self.canvas.selected_annotation.has_shadow = checked
            self.canvas.update()

    def _on_annotation_selection_changed(self, ann: Optional[BaseAnnotation]):
        if ann:
            # Sync options bar to selected annotation
            self.spin_thickness.setValue(ann.stroke_width)
            self._update_color_button_icon(self.btn_stroke_color, ann.stroke_color)
            self._update_color_button_icon(self.btn_fill_color, ann.fill_color)
            self.btn_shadow.setChecked(ann.has_shadow)
            if isinstance(ann, TextAnnotation):
                self.spin_font_size.setValue(ann.font_size)
                self.btn_bold.setChecked(ann.is_bold)
                self.btn_italic.setChecked(ann.is_italic)
                self.btn_underline.setChecked(ann.is_underline)

    def _on_zoom_changed(self, zoom: float):
        self.btn_zoom.setText(f"🔍 {int(zoom * 100)}% ▾")

    def _zoom_fit(self):
        img = self.canvas.get_image()
        if not img or img.isNull():
            return
        vw = self.scroll_area.viewport().width() - 20
        vh = self.scroll_area.viewport().height() - 20
        scale = min(vw / img.width(), vh / img.height(), 1.0)
        self.canvas.set_zoom(max(0.1, scale))

    def _on_canvas_status(self, msg: str):
        pass

    def _on_image_changed(self):
        self._update_window_title()

    def set_captured_image(self, image: QImage):
        self.canvas.set_image(image)
        self._update_window_title()
        self.show()
        self.raise_()
        self.activateWindow()

    def _finish_and_copy(self):
        self.copy_to_clipboard()
        self.quick_save()

    def copy_to_clipboard(self):
        composite = self.canvas.render_composite_image()
        if not composite or composite.isNull():
            return
        clipboard = QGuiApplication.clipboard()
        clipboard.setImage(composite)

    def quick_save(self):
        composite = self.canvas.render_composite_image()
        if not composite or composite.isNull():
            return

        save_dir = Path(self.config.save_directory)
        save_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        filename = now.strftime(self.config.filename_template)
        file_path = save_dir / filename

        success = composite.save(str(file_path))
        if success:
            self._notify_saved(str(file_path))
        else:
            QMessageBox.critical(self, "Save Error", f"Failed to save screenshot to:\n{file_path}")

    def save_as(self):
        composite = self.canvas.render_composite_image()
        if not composite or composite.isNull():
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
            success = composite.save(path)
            if success:
                self._notify_saved(path)
            else:
                QMessageBox.critical(self, "Save Error", f"Failed to save image to:\n{path}")

    def _toggle_pin(self):
        self._is_pinned = not self._is_pinned
        flags = self.windowFlags()
        if self._is_pinned:
            flags |= Qt.WindowType.WindowStaysOnTopHint
            self.btn_pin.setStyleSheet("color: #0078d4;")
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
            self.btn_pin.setStyleSheet("")
        self.setWindowFlags(flags)
        self.show()

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
        composite = self.canvas.render_composite_image()
        if not composite or composite.isNull():
            QMessageBox.information(self, "OCR", "No screenshot to extract text from.")
            return

        text = OCREngine.extract_text(composite)
        if text:
            dlg = OCRDialog(text, self)
            dlg.exec()
        else:
            QMessageBox.warning(self, "OCR Result", "No text detected in the image.")
