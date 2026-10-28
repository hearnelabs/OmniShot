"""
OmniShot Main Window - Professional Image Editor (KDE Plasma 6 Native)
Faithfully implements the modern OmniShot layout and design:
- Primary Categorized Ribbon (Drawing, Shapes, Redact, Badges, Output) with crisp vector icons
- Collapsible Right-Hand Properties Panel (Color Palette grid, Active swatch, Sliders for Thickness & Opacity, Font settings, Toggles)
- Centered Studio Viewport with image drop-shadow and dynamic resolution pill badge
- Bottom Floating Action Capsule (Zoom, Finish, Discard, Copy, Save, Save As, OCR, Pin)
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QToolBar,
    QToolButton, QPushButton, QLabel, QScrollArea, QFileDialog,
    QMessageBox, QDialog, QTextEdit, QStatusBar, QSpinBox,
    QColorDialog, QButtonGroup, QFrame, QMenu, QSlider, QSplitter
)
from PySide6.QtGui import (
    QImage, QPixmap, QIcon, QKeySequence, QShortcut, QColor, QFont, QClipboard,
    QGuiApplication, QPainter, QPen, QBrush
)
from PySide6.QtCore import Qt, QSize, Signal, QRect, QPoint, QTimer

from ..core.config import OmniShotConfig
from ..core.ocr import OCREngine
from .canvas import (
    AnnotationCanvas, ToolType, BaseAnnotation, TextAnnotation,
    RectAnnotation, SpeechBalloonAnnotation, StepBadgeAnnotation,
    RedactAnnotation
)
from .icons import get_tool_icon
from .theme import OMNISHOT_DARK_QSS
from .settings_dialog import OmniShotSettingsDialog


class OCRDialog(QDialog):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OmniShot - Extracted Text (OCR)")
        self.resize(520, 360)
        self.setStyleSheet(OMNISHOT_DARK_QSS)

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
                background-color: #1a1d24;
                color: #d4d4d4;
                border: 1px solid #3e444c;
                border-radius: 6px;
                padding: 8px;
                font-family: monospace;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.text_edit)

        btn_layout = QHBoxLayout()
        btn_copy = QPushButton("📋 Copy to Clipboard", self)
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                padding: 6px 18px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
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


class RibbonGroup(QFrame):
    """Categorized tool group card in the top ribbon."""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ribbonGroup")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 3)
        self.main_layout.setSpacing(2)

        self.btn_layout = QHBoxLayout()
        self.btn_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_layout.setSpacing(3)
        self.main_layout.addLayout(self.btn_layout)

        self.lbl_title = QLabel(title, self)
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setStyleSheet("color: #7f8c8d; font-size: 10px; font-weight: bold; text-transform: uppercase; margin-top: 1px;")
        self.main_layout.addWidget(self.lbl_title)

    def add_widget(self, widget: QWidget):
        self.btn_layout.addWidget(widget)


class PropertiesSidebar(QFrame):
    """Collapsible right-hand properties panel matching Mockup 2."""
    colorSelected = Signal(QColor)
    thicknessChanged = Signal(int)
    opacityChanged = Signal(int)
    fontSizeChanged = Signal(int)
    shadowToggled = Signal(bool)
    boldToggled = Signal(bool)
    italicToggled = Signal(bool)
    underlineToggled = Signal(bool)

    PALETTE_COLORS = [
        "#000000", "#4a4a4a", "#e74c3c", "#e67e22",
        "#f1c40f", "#2ecc71", "#1abc9c", "#00bcd4",
        "#0078d4", "#2980b9", "#9b59b6", "#8e44ad",
        "#e91e63", "#795548", "#bdc3c7", "#ffffff",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("propertiesPanel")
        self.setFixedWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Color Palette Header
        lbl_pal = QLabel("Color Palette", self)
        lbl_pal.setProperty("class", "panelHeader")
        layout.addWidget(lbl_pal)

        # Palette 4x4 Grid
        swatch_frame = QFrame(self)
        grid = QHBoxLayout(swatch_frame)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)

        col_layout1 = QVBoxLayout()
        col_layout1.setSpacing(4)
        col_layout2 = QVBoxLayout()
        col_layout2.setSpacing(4)
        col_layout3 = QVBoxLayout()
        col_layout3.setSpacing(4)
        col_layout4 = QVBoxLayout()
        col_layout4.setSpacing(4)
        cols = [col_layout1, col_layout2, col_layout3, col_layout4]

        self.swatch_buttons: List[QPushButton] = []
        for idx, hex_code in enumerate(self.PALETTE_COLORS):
            btn = QPushButton(self)
            btn.setProperty("class", "swatchBtn")
            btn.setStyleSheet(f"background-color: {hex_code};")
            btn.setToolTip(hex_code)
            btn.clicked.connect(lambda ch, c=hex_code: self._on_swatch_clicked(c))
            cols[idx % 4].addWidget(btn)
            self.swatch_buttons.append(btn)

        for col in cols:
            grid.addLayout(col)
        layout.addWidget(swatch_frame)

        # Active Color Bar with Dropper
        bar_layout = QHBoxLayout()
        bar_layout.setContentsMargins(0, 4, 0, 4)
        bar_layout.setSpacing(6)

        self.active_color_bar = QLabel(self)
        self.active_color_bar.setFixedHeight(26)
        self.active_color_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.active_color_bar.setStyleSheet("background-color: #e74c3c; border-radius: 4px; font-weight: bold; color: #ffffff;")
        bar_layout.addWidget(self.active_color_bar, 1)

        btn_dropper = QPushButton(self)
        btn_dropper.setIcon(get_tool_icon("dropper"))
        btn_dropper.setIconSize(QSize(18, 18))
        btn_dropper.setFixedSize(32, 26)
        btn_dropper.setToolTip("Custom Color Picker...")
        btn_dropper.clicked.connect(self._open_custom_color_picker)
        bar_layout.addWidget(btn_dropper)

        layout.addLayout(bar_layout)

        # Separator line
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #2a2e36; height: 1px;")
        layout.addWidget(sep)

        # 2. Stroke / Text Properties Header
        lbl_props = QLabel("Stroke / Text", self)
        lbl_props.setProperty("class", "panelHeader")
        layout.addWidget(lbl_props)

        # Stroke Thickness
        thick_head = QHBoxLayout()
        lbl_thick = QLabel("Stroke Thickness", self)
        lbl_thick.setProperty("class", "propLabel")
        self.lbl_thick_val = QLabel("4 px", self)
        self.lbl_thick_val.setStyleSheet("color: #3daee9; font-weight: bold;")
        thick_head.addWidget(lbl_thick)
        thick_head.addStretch()
        thick_head.addWidget(self.lbl_thick_val)
        layout.addLayout(thick_head)

        self.slider_thick = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_thick.setRange(1, 40)
        self.slider_thick.setValue(4)
        self.slider_thick.valueChanged.connect(self._on_thick_slider_changed)
        layout.addWidget(self.slider_thick)

        # Opacity
        opac_head = QHBoxLayout()
        lbl_opac = QLabel("Opacity", self)
        lbl_opac.setProperty("class", "propLabel")
        self.lbl_opac_val = QLabel("100%", self)
        self.lbl_opac_val.setStyleSheet("color: #3daee9; font-weight: bold;")
        opac_head.addWidget(lbl_opac)
        opac_head.addStretch()
        opac_head.addWidget(self.lbl_opac_val)
        layout.addLayout(opac_head)

        self.slider_opac = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_opac.setRange(10, 100)
        self.slider_opac.setValue(100)
        self.slider_opac.valueChanged.connect(self._on_opac_slider_changed)
        layout.addWidget(self.slider_opac)

        # Font Size
        font_head = QHBoxLayout()
        lbl_font = QLabel("Font Size", self)
        lbl_font.setProperty("class", "propLabel")
        font_head.addWidget(lbl_font)
        font_head.addStretch()

        self.spin_font = QSpinBox(self)
        self.spin_font.setRange(10, 80)
        self.spin_font.setValue(24)
        self.spin_font.setSuffix(" pt")
        self.spin_font.valueChanged.connect(self.fontSizeChanged.emit)
        font_head.addWidget(self.spin_font)
        layout.addLayout(font_head)

        # Toggles: Shadow, Bold, Italic, Underline
        toggle_layout = QHBoxLayout()
        toggle_layout.setSpacing(6)

        self.btn_shadow = QPushButton("Shadow", self)
        self.btn_shadow.setCheckable(True)
        self.btn_shadow.setChecked(True)
        self.btn_shadow.setStyleSheet("padding: 5px 8px; font-size: 11px;")
        self.btn_shadow.clicked.connect(self.shadowToggled.emit)
        toggle_layout.addWidget(self.btn_shadow)

        self.btn_bold = QPushButton("B", self)
        self.btn_bold.setCheckable(True)
        self.btn_bold.setChecked(True)
        self.btn_bold.setFixedWidth(28)
        self.btn_bold.setStyleSheet("font-weight: bold;")
        self.btn_bold.clicked.connect(self.boldToggled.emit)
        toggle_layout.addWidget(self.btn_bold)

        self.btn_italic = QPushButton("I", self)
        self.btn_italic.setCheckable(True)
        self.btn_italic.setFixedWidth(28)
        self.btn_italic.setStyleSheet("font-style: italic;")
        self.btn_italic.clicked.connect(self.italicToggled.emit)
        toggle_layout.addWidget(self.btn_italic)

        self.btn_underline = QPushButton("U", self)
        self.btn_underline.setCheckable(True)
        self.btn_underline.setFixedWidth(28)
        self.btn_underline.setStyleSheet("text-decoration: underline;")
        self.btn_underline.clicked.connect(self.underlineToggled.emit)
        toggle_layout.addWidget(self.btn_underline)

        layout.addLayout(toggle_layout)
        layout.addStretch()

        self.set_current_color(QColor("#ff0000"))

    def _on_swatch_clicked(self, hex_code: str):
        c = QColor(hex_code)
        self.set_current_color(c)
        self.colorSelected.emit(c)

    def _open_custom_color_picker(self):
        c = QColorDialog.getColor(QColor(self.active_color_bar.text()), self, "Select Custom Color")
        if c.isValid():
            self.set_current_color(c)
            self.colorSelected.emit(c)

    def set_current_color(self, color: QColor):
        self.active_color_bar.setStyleSheet(f"background-color: {color.name()}; border-radius: 4px; font-weight: bold; color: {'#ffffff' if color.lightness() < 130 else '#000000'};")
        self.active_color_bar.setText(color.name().upper())

    def _on_thick_slider_changed(self, val: int):
        self.lbl_thick_val.setText(f"{val} px")
        self.thicknessChanged.emit(val)

    def _on_opac_slider_changed(self, val: int):
        self.lbl_opac_val.setText(f"{val}%")
        self.opacityChanged.emit(val)


class OmniShotMainWindow(QMainWindow):
    requestCapture = Signal(str) # "region", "scroll_auto", "scroll_manual", "fullscreen", "window"

    def __init__(self, config: Optional[OmniShotConfig] = None, parent=None):
        super().__init__(parent)
        self.config = config or OmniShotConfig.load()
        self.current_filename: str = "OmniShot_Image.png"
        self._is_pinned = False

        icon_path = Path(__file__).parent.parent.parent / "omnishot.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon.fromTheme("omnishot", QIcon(str(icon_path))))

        self.resize(1180, 820)
        self.setStyleSheet(OMNISHOT_DARK_QSS)

        self._init_ui()
        self._setup_shortcuts()
        self._update_window_title()

    def _init_ui(self):
        root_widget = QWidget(self)
        self.setCentralWidget(root_widget)
        main_vbox = QVBoxLayout(root_widget)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(0)

        # 1. Canvas and Viewport
        self.canvas = AnnotationCanvas(self)
        self.canvas.statusMessage.connect(self._on_canvas_status)
        self.canvas.imageChanged.connect(self._on_image_changed)
        self.canvas.selectionChanged.connect(self._on_annotation_selection_changed)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.canvas)

        # 2. Top Categorized Ribbon Bar
        self.ribbon_bar = self._create_ribbon_bar()
        main_vbox.addWidget(self.ribbon_bar)

        # 3. Main Workspace Split: Canvas Area (Left) + Properties Sidebar (Right)
        workspace = QWidget(self)
        ws_layout = QHBoxLayout(workspace)
        ws_layout.setContentsMargins(0, 0, 0, 0)
        ws_layout.setSpacing(0)

        # Viewport frame with floating pills
        self.viewport_container = QWidget(self)
        vp_layout = QVBoxLayout(self.viewport_container)
        vp_layout.setContentsMargins(0, 0, 0, 0)
        vp_layout.setSpacing(0)
        vp_layout.addWidget(self.scroll_area)

        ws_layout.addWidget(self.viewport_container, 1)

        # Properties Sidebar (Right)
        self.sidebar = PropertiesSidebar(self)
        self.sidebar.colorSelected.connect(self._on_color_selected)
        self.sidebar.thicknessChanged.connect(self._on_thickness_changed)
        self.sidebar.opacityChanged.connect(self._on_opacity_changed)
        self.sidebar.fontSizeChanged.connect(self._on_font_size_changed)
        self.sidebar.shadowToggled.connect(self._on_shadow_toggled)
        self.sidebar.boldToggled.connect(self._on_bold_toggled)
        self.sidebar.italicToggled.connect(self._on_italic_toggled)
        self.sidebar.underlineToggled.connect(self._on_underline_toggled)
        ws_layout.addWidget(self.sidebar)

        main_vbox.addWidget(workspace, 1)

        # 3. Bottom Floating Action Pill (OmniShot signature capsule)
        self._create_bottom_action_pill()

    def _create_ribbon_bar(self) -> QFrame:
        """Categorized Ribbon with Drawing, Shapes, Redact, Badges, Output sections matching Mockup 2."""
        ribbon = QFrame(self)
        ribbon.setObjectName("ribbonBar")
        layout = QHBoxLayout(ribbon)
        layout.setContentsMargins(8, 6, 8, 4)
        layout.setSpacing(6)

        self.tool_button_group = QButtonGroup(self)
        self.tool_button_group.setExclusive(True)

        def add_ribbon_btn(group: RibbonGroup, tool_id: str, label: str, icon_name: str, tooltip: str, is_default: bool = False):
            btn = QToolButton(self)
            btn.setProperty("class", "ribbonBtn")
            btn.setText(label)
            btn.setIcon(get_tool_icon(icon_name))
            btn.setIconSize(QSize(22, 22))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setFixedSize(60, 56)
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            if is_default:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, t=tool_id: self._on_tool_selected(t))
            self.tool_button_group.addButton(btn)
            group.add_widget(btn)
            return btn

        def add_divider():
            sep = QFrame(ribbon)
            sep.setObjectName("groupDivider")
            sep.setFrameShape(QFrame.Shape.VLine)
            layout.addWidget(sep)

        # Group 1: Drawing
        grp_draw = RibbonGroup("Drawing", ribbon)
        add_ribbon_btn(grp_draw, ToolType.POINTER, "Pointer", "pointer", "Select & Move Annotations (V)", True)
        add_ribbon_btn(grp_draw, ToolType.PEN, "Pen", "pen", "Freehand Pen (P)")
        add_ribbon_btn(grp_draw, ToolType.ARROW, "Arrow", "arrow", "Line with Arrowhead (A)")
        add_ribbon_btn(grp_draw, ToolType.HIGHLIGHTER, "Highlight", "highlighter", "Translucent Highlighter (H)")
        layout.addWidget(grp_draw)
        add_divider()

        # Group 2: Shapes
        grp_shapes = RibbonGroup("Shapes", ribbon)
        add_ribbon_btn(grp_shapes, ToolType.RECTANGLE, "Box", "box", "Rectangle Box (R)")
        add_ribbon_btn(grp_shapes, ToolType.ROUNDED_RECT, "Rounded", "rounded_rect", "Rounded Rectangle (Shift+R)")
        add_ribbon_btn(grp_shapes, ToolType.ELLIPSE, "Circle", "circle", "Circle / Ellipse (E)")
        add_ribbon_btn(grp_shapes, ToolType.LINE, "Line", "arrow", "Straight Line (L)")
        layout.addWidget(grp_shapes)
        add_divider()

        # Group 3: Redact
        grp_redact = RibbonGroup("Redact", ribbon)
        add_ribbon_btn(grp_redact, ToolType.BLUR, "Blur", "blur", "Gaussian Blur Redaction (B)")
        add_ribbon_btn(grp_redact, ToolType.PIXELATE, "Pixelate", "pixelate", "Checkered Mosaic Redaction (X)")
        add_ribbon_btn(grp_redact, ToolType.CROP, "Crop", "crop", "Crop Canvas (K)")
        layout.addWidget(grp_redact)
        add_divider()

        # Group 4: Badges
        grp_badges = RibbonGroup("Badges", ribbon)
        add_ribbon_btn(grp_badges, ToolType.STEP_BADGE, "Steps", "step_badge", "Sequential Step Badges 1-2-3 (S)")
        add_ribbon_btn(grp_badges, ToolType.SPEECH_BALLOON, "Balloon", "speech_balloon", "Speech Balloon Bubble (C)")
        add_ribbon_btn(grp_badges, ToolType.TEXT, "Text", "text", "Rich Text Box (T)")
        layout.addWidget(grp_badges)
        add_divider()

        # Group 5: Output
        grp_output = RibbonGroup("Output", ribbon)

        btn_scroll = QToolButton(ribbon)
        btn_scroll.setObjectName("scrollingCaptureRibbonBtn")
        btn_scroll.setText("Scroll")
        btn_scroll.setIcon(get_tool_icon("scrolling_capture"))
        btn_scroll.setIconSize(QSize(22, 22))
        btn_scroll.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn_scroll.setFixedSize(58, 56)
        btn_scroll.setToolTip("Start Wayland Scrolling Capture")
        btn_scroll.clicked.connect(lambda: self.requestCapture.emit("scroll_auto"))
        grp_output.add_widget(btn_scroll)

        btn_copy = QToolButton(ribbon)
        btn_copy.setProperty("class", "ribbonBtn")
        btn_copy.setText("Copy")
        btn_copy.setIcon(get_tool_icon("copy"))
        btn_copy.setIconSize(QSize(22, 22))
        btn_copy.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn_copy.setFixedSize(54, 56)
        btn_copy.setToolTip("Copy to Clipboard (Ctrl+C)")
        btn_copy.clicked.connect(self.copy_to_clipboard)
        grp_output.add_widget(btn_copy)

        btn_save = QToolButton(ribbon)
        btn_save.setProperty("class", "ribbonBtn")
        btn_save.setText("Save")
        btn_save.setIcon(get_tool_icon("save"))
        btn_save.setIconSize(QSize(22, 22))
        btn_save.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn_save.setFixedSize(52, 56)
        btn_save.setToolTip("Save Image (Ctrl+S)")
        btn_save.clicked.connect(self.quick_save)
        grp_output.add_widget(btn_save)

        btn_ocr = QToolButton(ribbon)
        btn_ocr.setProperty("class", "ribbonBtn")
        btn_ocr.setText("OCR")
        btn_ocr.setIcon(get_tool_icon("ocr"))
        btn_ocr.setIconSize(QSize(22, 22))
        btn_ocr.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn_ocr.setFixedSize(52, 56)
        btn_ocr.setToolTip("Extract Text via OCR")
        btn_ocr.clicked.connect(self.extract_ocr_text)
        grp_output.add_widget(btn_ocr)

        layout.addWidget(grp_output)
        layout.addStretch()

        # Far right: Undo / Redo / Sidebar Toggle
        btn_undo = QToolButton(ribbon)
        btn_undo.setText("↩")
        btn_undo.setToolTip("Undo (Ctrl+Z)")
        btn_undo.setFixedSize(32, 32)
        btn_undo.clicked.connect(self.canvas.undo)
        layout.addWidget(btn_undo)

        btn_redo = QToolButton(ribbon)
        btn_redo.setText("↪")
        btn_redo.setToolTip("Redo (Ctrl+Y)")
        btn_redo.setFixedSize(32, 32)
        btn_redo.clicked.connect(self.canvas.redo)
        layout.addWidget(btn_redo)

        btn_toggle_side = QToolButton(ribbon)
        btn_toggle_side.setText("🎨")
        btn_toggle_side.setToolTip("Toggle Color Palette & Properties Sidebar")
        btn_toggle_side.setFixedSize(32, 32)
        btn_toggle_side.clicked.connect(self._toggle_sidebar)
        layout.addWidget(btn_toggle_side)

        btn_settings = QToolButton(ribbon)
        btn_settings.setText("⚙")
        btn_settings.setToolTip("Configure OmniShot Settings & Hotkeys (Ctrl+,)")
        btn_settings.setFixedSize(32, 32)
        btn_settings.clicked.connect(self.open_settings)
        layout.addWidget(btn_settings)

        return ribbon

    def _create_bottom_action_pill(self):
        """Bottom Floating Action Capsule (Matching OmniShot bottom pill)"""
        self.action_pill = QFrame(self.viewport_container)
        self.action_pill.setObjectName("bottomActionPill")

        layout = QHBoxLayout(self.action_pill)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

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

        # 2. Big Green Finish Play/Check Button
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
        self.btn_copy.setIcon(get_tool_icon("copy"))
        self.btn_copy.setToolTip("Copy to Clipboard (Ctrl+C)")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        layout.addWidget(self.btn_copy)

        self.btn_save = QToolButton(self)
        self.btn_save.setObjectName("pillActionBtn")
        self.btn_save.setIcon(get_tool_icon("save"))
        self.btn_save.setToolTip("Quick Save (Ctrl+S)")
        self.btn_save.clicked.connect(self.quick_save)
        layout.addWidget(self.btn_save)

        self.btn_save_as = QToolButton(self)
        self.btn_save_as.setObjectName("pillActionBtn")
        self.btn_save_as.setIcon(get_tool_icon("save_as"))
        self.btn_save_as.setToolTip("Save As... (Ctrl+Shift+S)")
        self.btn_save_as.clicked.connect(self.save_as)
        layout.addWidget(self.btn_save_as)

        self.btn_ocr = QToolButton(self)
        self.btn_ocr.setObjectName("pillActionBtn")
        self.btn_ocr.setIcon(get_tool_icon("ocr"))
        self.btn_ocr.setToolTip("Extract Text (OCR)")
        self.btn_ocr.clicked.connect(self.extract_ocr_text)
        layout.addWidget(self.btn_ocr)

        self.btn_pin = QToolButton(self)
        self.btn_pin.setObjectName("pillActionBtn")
        self.btn_pin.setText("📌")
        self.btn_pin.setToolTip("Pin to Screen (Always on top)")
        self.btn_pin.clicked.connect(self._toggle_pin)
        layout.addWidget(self.btn_pin)

        self.btn_settings = QToolButton(self)
        self.btn_settings.setObjectName("pillActionBtn")
        self.btn_settings.setText("⚙")
        self.btn_settings.setToolTip("Settings & Hotkeys (Ctrl+,)")
        self.btn_settings.clicked.connect(self.open_settings)
        layout.addWidget(self.btn_settings)

        self.canvas.zoomChanged.connect(self._on_zoom_changed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.action_pill.adjustSize()
        pw = self.action_pill.width()
        ph = self.action_pill.height()
        px = (self.viewport_container.width() - pw) // 2
        py = self.viewport_container.height() - ph - 20
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
        QShortcut(QKeySequence("Ctrl+0"), self, self._zoom_fit)
        QShortcut(QKeySequence("Ctrl+1"), self, self.canvas.zoom_reset)
        QShortcut(QKeySequence("Ctrl+,"), self, self.open_settings)

    def open_settings(self):
        dlg = OmniShotSettingsDialog(config=self.config, parent=self)
        dlg.settingsSaved.connect(self._on_settings_saved)
        dlg.exec()

    def _on_settings_saved(self):
        self.config = OmniShotConfig.load()

    def _toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def _on_tool_selected(self, tool_type: str):
        self.canvas.set_active_tool(tool_type)

    def _on_color_selected(self, color: QColor):
        self.canvas.current_stroke_color = color
        if self.canvas.selected_annotation:
            self.canvas.selected_annotation.stroke_color = color
            if isinstance(self.canvas.selected_annotation, TextAnnotation):
                self.canvas.selected_annotation.outline_color = color
            elif isinstance(self.canvas.selected_annotation, StepBadgeAnnotation):
                self.canvas.selected_annotation.badge_color = color
            elif isinstance(self.canvas.selected_annotation, SpeechBalloonAnnotation):
                self.canvas.selected_annotation.stroke_color = color
            self.canvas.update()
            self.canvas.imageChanged.emit()

    def _on_thickness_changed(self, val: int):
        self.canvas.current_stroke_width = val
        if self.canvas.selected_annotation:
            self.canvas.selected_annotation.stroke_width = val
            self.canvas.update()
            self.canvas.imageChanged.emit()

    def _on_opacity_changed(self, val: int):
        opacity_float = max(0.01, min(1.0, val / 100.0))
        self.canvas.current_opacity = opacity_float
        if self.canvas.selected_annotation:
            self.canvas.selected_annotation.opacity = opacity_float
            self.canvas.update()
            self.canvas.imageChanged.emit()

    def _on_font_size_changed(self, val: int):
        self.canvas.current_font_size = val
        if self.canvas.selected_annotation:
            if hasattr(self.canvas.selected_annotation, "font_size"):
                self.canvas.selected_annotation.font_size = val
            if isinstance(self.canvas.selected_annotation, StepBadgeAnnotation):
                self.canvas.selected_annotation.radius = float(val)
            self.canvas.update()
            self.canvas.imageChanged.emit()

    def _on_bold_toggled(self, checked: bool):
        self.canvas.is_bold = checked
        if self.canvas.selected_annotation and isinstance(self.canvas.selected_annotation, TextAnnotation):
            self.canvas.selected_annotation.is_bold = checked
            self.canvas.update()
            self.canvas.imageChanged.emit()

    def _on_italic_toggled(self, checked: bool):
        self.canvas.is_italic = checked
        if self.canvas.selected_annotation and isinstance(self.canvas.selected_annotation, TextAnnotation):
            self.canvas.selected_annotation.is_italic = checked
            self.canvas.update()
            self.canvas.imageChanged.emit()

    def _on_underline_toggled(self, checked: bool):
        self.canvas.is_underline = checked
        if self.canvas.selected_annotation and isinstance(self.canvas.selected_annotation, TextAnnotation):
            self.canvas.selected_annotation.is_underline = checked
            self.canvas.update()
            self.canvas.imageChanged.emit()

    def _on_shadow_toggled(self, checked: bool):
        self.canvas.has_shadow = checked
        if self.canvas.selected_annotation:
            self.canvas.selected_annotation.has_shadow = checked
            self.canvas.update()
            self.canvas.imageChanged.emit()

    def _on_annotation_selection_changed(self, ann: Optional[BaseAnnotation]):
        if ann:
            opac_pct = int(round(getattr(ann, "opacity", 1.0) * 100))
            self.sidebar.slider_opac.blockSignals(True)
            self.sidebar.slider_opac.setValue(opac_pct)
            self.sidebar.lbl_opac_val.setText(f"{opac_pct}%")
            self.sidebar.slider_opac.blockSignals(False)

            self.sidebar.slider_thick.blockSignals(True)
            self.sidebar.slider_thick.setValue(ann.stroke_width)
            self.sidebar.lbl_thick_val.setText(f"{ann.stroke_width} px")
            self.sidebar.slider_thick.blockSignals(False)

            self.sidebar.set_current_color(QColor(ann.stroke_color))

            self.sidebar.btn_shadow.blockSignals(True)
            self.sidebar.btn_shadow.setChecked(ann.has_shadow)
            self.sidebar.btn_shadow.blockSignals(False)

            if isinstance(ann, TextAnnotation):
                self.sidebar.spin_font.blockSignals(True)
                self.sidebar.spin_font.setValue(ann.font_size)
                self.sidebar.spin_font.blockSignals(False)
                self.sidebar.btn_bold.blockSignals(True)
                self.sidebar.btn_bold.setChecked(ann.is_bold)
                self.sidebar.btn_bold.blockSignals(False)
                self.sidebar.btn_italic.blockSignals(True)
                self.sidebar.btn_italic.setChecked(ann.is_italic)
                self.sidebar.btn_italic.blockSignals(False)
                self.sidebar.btn_underline.blockSignals(True)
                self.sidebar.btn_underline.setChecked(ann.is_underline)
                self.sidebar.btn_underline.blockSignals(False)

    def _on_zoom_changed(self, zoom: float):
        self.btn_zoom.setText(f"🔍 {int(zoom * 100)}% ▾")

    def _zoom_fit(self):
        img = self.canvas.get_image()
        if not img or img.isNull():
            return
        vw = max(100, self.scroll_area.viewport().width() - 30)
        vh = max(100, self.scroll_area.viewport().height() - 30)
        scale = min(vw / img.width(), vh / img.height(), 1.0)
        self.canvas.set_zoom(max(0.1, scale))

    def _on_canvas_status(self, msg: str):
        pass

    def _on_image_changed(self):
        self._update_window_title()

    def _update_window_title(self):
        img = self.canvas.get_image()
        if img and not img.isNull():
            self.setWindowTitle(f"OmniShot - [Current Screenshot] - {img.width()} × {img.height()} px")
        else:
            self.setWindowTitle("OmniShot - [Current Screenshot]")

    def set_captured_image(self, image: QImage):
        self.canvas.set_image(image)
        self._update_window_title()
        self.show()
        self.raise_()
        self.activateWindow()

        # For tall scrolling images (e.g. height > 1600), fit window so entire document is surveyed;
        # For standard region and window captures, default to 100% (1:1 native hardware resolution)!
        if image.height() > 1600 or image.width() > 2400:
            QTimer.singleShot(60, self._zoom_fit)
        else:
            self.canvas.set_zoom(1.0)

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
