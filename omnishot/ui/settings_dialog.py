"""
OmniShot Settings Dialog - Preferences, Save Locations & KDE Plasma 6 Shortcuts
"""

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QSpinBox, QKeySequenceEdit, QFileDialog, QGroupBox,
    QFormLayout, QMessageBox, QFrame, QScrollArea
)
from PySide6.QtGui import (
    QIcon, QKeySequence, QFont, QDesktopServices
)
from PySide6.QtCore import Qt, Signal, QUrl

from ..core.config import OmniShotConfig
from .theme import OMNISHOT_DARK_QSS


class OmniShotSettingsDialog(QDialog):
    settingsSaved = Signal()

    def __init__(self, config: Optional[OmniShotConfig] = None, parent=None):
        super().__init__(parent)
        self.config = config or OmniShotConfig.load()
        self.setWindowTitle("OmniShot - Settings & Preferences")
        self.resize(680, 560)
        self.setStyleSheet(OMNISHOT_DARK_QSS)

        icon_path = Path(__file__).parent.parent.parent / "omnishot.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon.fromTheme("omnishot", QIcon(str(icon_path))))

        self._init_ui()
        self._load_config_values()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Tab Widget
        self.tabs = QTabWidget(self)
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #2a2e36;
                background-color: #16191f;
                border-radius: 8px;
                padding: 12px;
            }
            QTabBar::tab {
                background-color: #1e222a;
                color: #a0a8b4;
                padding: 8px 20px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #16191f;
                color: #ffffff;
                font-weight: 600;
                border-bottom: 2px solid #0078d4;
            }
            QTabBar::tab:hover:!selected {
                background-color: #262b35;
                color: #e4e7eb;
            }
            QGroupBox {
                border: 1px solid #2c313a;
                border-radius: 6px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: bold;
                color: #0078d4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                color: #3daee9;
            }
            QLineEdit, QKeySequenceEdit, QSpinBox, QComboBox {
                background-color: #1e222a;
                color: #eff0f1;
                border: 1px solid #3e444c;
                border-radius: 5px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus, QKeySequenceEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1.5px solid #0078d4;
            }
        """)

        # Add Tabs
        self.tab_save = self._create_save_location_tab()
        self.tab_shortcuts = self._create_shortcuts_tab()
        self.tab_scrolling = self._create_scrolling_tab()
        self.tab_about = self._create_about_tab()

        self.tabs.addTab(self.tab_save, "📁 Save Location && Files")
        self.tabs.addTab(self.tab_shortcuts, "⌨️ Global Hotkeys (KDE)")
        self.tabs.addTab(self.tab_scrolling, "📜 Scrolling Engine")
        self.tabs.addTab(self.tab_about, "ℹ️ About OmniShot")

        main_layout.addWidget(self.tabs, 1)

        # Dialog Buttons at Bottom
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.lbl_status = QLabel("", self)
        self.lbl_status.setStyleSheet("color: #2ecc71; font-weight: bold;")
        btn_layout.addWidget(self.lbl_status)
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #262b35;
                color: #eff0f1;
                border: 1px solid #3e444c;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #323846;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Save && Apply", self)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: 1px solid #0078d4;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        btn_save.clicked.connect(self._save_and_apply)
        btn_layout.addWidget(btn_save)

        main_layout.addLayout(btn_layout)

    def _create_save_location_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        # Group 1: Default Save Directory
        grp_dir = QGroupBox("Screenshots Save Directory", tab)
        dir_layout = QVBoxLayout(grp_dir)
        dir_layout.setSpacing(8)

        lbl_dir_info = QLabel("Choose where screenshots are stored by default when using Quick Save or auto-save:")
        lbl_dir_info.setStyleSheet("color: #a0a8b4; font-size: 12px;")
        dir_layout.addWidget(lbl_dir_info)

        row_dir = QHBoxLayout()
        row_dir.setSpacing(8)
        self.txt_save_dir = QLineEdit(self)
        self.txt_save_dir.setPlaceholderText("/home/user/Pictures/Screenshots")
        row_dir.addWidget(self.txt_save_dir, 1)

        btn_browse = QPushButton("Browse...", self)
        btn_browse.setStyleSheet("padding: 6px 14px; background-color: #262b35; border: 1px solid #3e444c; border-radius: 5px;")
        btn_browse.clicked.connect(self._browse_save_directory)
        row_dir.addWidget(btn_browse)

        dir_layout.addLayout(row_dir)
        layout.addWidget(grp_dir)

        # Group 2: Filename & Format
        grp_file = QGroupBox("Filename Template && Image Format", tab)
        file_layout = QVBoxLayout(grp_file)
        file_layout.setSpacing(10)

        form_file = QFormLayout()
        form_file.setSpacing(8)

        self.txt_template = QLineEdit(self)
        self.txt_template.textChanged.connect(self._update_filename_preview)
        form_file.addRow("Filename Template:", self.txt_template)

        self.cbo_format = QComboBox(self)
        self.cbo_format.addItems(["PNG (Lossless - Recommended)", "JPG (High Quality Compressed)", "WEBP (Modern Compressed)"])
        form_file.addRow("Default Image Format:", self.cbo_format)

        file_layout.addLayout(form_file)

        # Live Preview
        self.lbl_preview = QLabel("", self)
        self.lbl_preview.setStyleSheet("color: #3daee9; font-weight: bold; background: #1a1e24; padding: 6px 10px; border-radius: 4px; border: 1px dashed #2c313a;")
        file_layout.addWidget(self.lbl_preview)

        lbl_hints = QLabel("Template variables: %Y = Year (2026), %m = Month, %d = Day, %H = Hour, %M = Minute, %S = Second")
        lbl_hints.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        file_layout.addWidget(lbl_hints)

        layout.addWidget(grp_file)

        # Group 3: Workflow & Clipboard
        grp_workflow = QGroupBox("Capture && Clipboard Workflow", tab)
        wf_layout = QVBoxLayout(grp_workflow)
        wf_layout.setSpacing(8)

        self.chk_copy_on_save = QCheckBox("Automatically copy image to clipboard when saving screenshot file")
        wf_layout.addWidget(self.chk_copy_on_save)

        self.chk_copy_on_capture = QCheckBox("Copy image to clipboard immediately upon capture")
        self.chk_copy_on_capture.setToolTip("Puts captured image onto system clipboard right away while keeping editor open")
        wf_layout.addWidget(self.chk_copy_on_capture)

        self.chk_notify_on_save = QCheckBox("Display desktop notification when screenshot is saved")
        wf_layout.addWidget(self.chk_notify_on_save)

        layout.addWidget(grp_workflow)
        layout.addStretch()
        return tab

    def _create_shortcuts_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        # Info Banner
        banner = QFrame(tab)
        banner.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 120, 215, 0.12);
                border: 1px solid rgba(0, 120, 215, 0.35);
                border-radius: 6px;
                padding: 10px;
            }
        """)
        b_layout = QVBoxLayout(banner)
        b_layout.setContentsMargins(8, 6, 8, 6)
        b_title = QLabel("⚡ KDE Plasma 6 Wayland Global Shortcuts")
        b_title.setStyleSheet("font-weight: bold; color: #3daee9; font-size: 13px;")
        b_layout.addWidget(b_title)
        b_desc = QLabel(
            "OmniShot seamlessly syncs these shortcuts with KDE Plasma's kglobalaccel daemon. "
            "Click on any field and press your desired key combination to assign."
        )
        b_desc.setWordWrap(True)
        b_desc.setStyleSheet("color: #d8dce2; font-size: 12px;")
        b_layout.addWidget(b_desc)
        layout.addWidget(banner)

        # Shortcuts Form
        grp_keys = QGroupBox("Configured Global Hotkeys", tab)
        form_keys = QFormLayout(grp_keys)
        form_keys.setSpacing(10)
        form_keys.setContentsMargins(12, 16, 12, 12)

        self.key_launch = QKeySequenceEdit(self)
        form_keys.addRow("Launch OmniShot Floating Pill:", self.key_launch)

        self.key_scrolling = QKeySequenceEdit(self)
        form_keys.addRow("Trigger Scrolling Capture (Auto):", self.key_scrolling)

        self.key_region = QKeySequenceEdit(self)
        form_keys.addRow("Capture Rectangular Region:", self.key_region)

        self.key_fullscreen = QKeySequenceEdit(self)
        form_keys.addRow("Capture Entire Desktop:", self.key_fullscreen)

        self.key_window = QKeySequenceEdit(self)
        form_keys.addRow("Capture Active Window:", self.key_window)

        layout.addWidget(grp_keys)

        # Shortcut Helper Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        btn_reset_defaults = QPushButton("🔄 Reset Shortcuts to Defaults", self)
        btn_reset_defaults.setStyleSheet("padding: 7px 16px; background-color: #262b35; border: 1px solid #3e444c; border-radius: 6px;")
        btn_reset_defaults.clicked.connect(self._reset_shortcuts_to_defaults)
        btn_box.addWidget(btn_reset_defaults)

        btn_apply_kde = QPushButton("⚡ Sync Directly to KDE Plasma", self)
        btn_apply_kde.setStyleSheet("padding: 7px 16px; background-color: #1e824c; border: 1px solid #27ae60; border-radius: 6px; font-weight: bold; color: #ffffff;")
        btn_apply_kde.clicked.connect(self._apply_kde_shortcuts_now)
        btn_box.addWidget(btn_apply_kde)

        btn_box.addStretch()
        layout.addLayout(btn_box)

        layout.addStretch()
        return tab

    def _create_scrolling_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        grp_scroll = QGroupBox("Wayland Scrolling Capture Engine Parameters", tab)
        grp_layout = QVBoxLayout(grp_scroll)
        grp_layout.setSpacing(12)
        grp_layout.setContentsMargins(14, 16, 14, 14)

        form_scroll = QFormLayout()
        form_scroll.setSpacing(10)

        self.spin_scroll_step = QSpinBox(self)
        self.spin_scroll_step.setRange(40, 500)
        self.spin_scroll_step.setSingleStep(10)
        self.spin_scroll_step.setSuffix(" px")
        form_scroll.addRow("Scroll Step Distance (per movement):", self.spin_scroll_step)

        self.spin_scroll_delay = QSpinBox(self)
        self.spin_scroll_delay.setRange(50, 1000)
        self.spin_scroll_delay.setSingleStep(25)
        self.spin_scroll_delay.setSuffix(" ms")
        form_scroll.addRow("Frame Settle Delay (rendering pause):", self.spin_scroll_delay)

        self.spin_scrollbar_margin = QSpinBox(self)
        self.spin_scrollbar_margin.setRange(0, 80)
        self.spin_scrollbar_margin.setSuffix(" px")
        form_scroll.addRow("Right Scrollbar Exclusion Margin:", self.spin_scrollbar_margin)

        self.spin_max_frames = QSpinBox(self)
        self.spin_max_frames.setRange(10, 300)
        self.spin_max_frames.setSuffix(" frames")
        form_scroll.addRow("Maximum Total Capture Frames:", self.spin_max_frames)

        grp_layout.addLayout(form_scroll)

        self.chk_auto_detect_end = QCheckBox("Auto-detect bottom of page / end of document scroll")
        grp_layout.addWidget(self.chk_auto_detect_end)

        layout.addWidget(grp_scroll)

        lbl_desc = QLabel(
            "OmniShot features automated vertical scrolling capture for Wayland using normalized cross-correlation "
            "and sub-pixel template matching to seamlessly stitch document or web page segments."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #a0a8b4; font-size: 12px; padding: 6px 4px;")
        layout.addWidget(lbl_desc)

        layout.addStretch()
        return tab

    def _create_about_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        icon_lbl = QLabel()
        icon_path = Path(__file__).parent.parent.parent / "omnishot.svg"
        if icon_path.exists():
            pix = QIcon(str(icon_path)).pixmap(72, 72)
            icon_lbl.setPixmap(pix)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        title = QLabel("OmniShot")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #3daee9;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("KDE Plasma 6 Native Wayland Screenshot & Scrolling Suite")
        subtitle.setStyleSheet("font-size: 13px; color: #a0a8b4;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        version = QLabel("Version 1.0.5 (CachyOS Edition)")
        version.setStyleSheet("font-size: 12px; color: #7f8c8d; font-family: monospace;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        desc = QLabel(
            "Built specifically for CachyOS on KDE Plasma 6.8+ (Wayland).\n"
            "Features High-DPI crystal clear 1:1 hardware pixel capture, automated vertical scrolling capture,\n"
            "professional vector annotation studio, and native system integration."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #eff0f1; font-size: 12px; margin-top: 10px; line-height: 1.4;")
        layout.addWidget(desc)

        layout.addStretch()
        return tab

    def _load_config_values(self):
        # Save dir & files
        self.txt_save_dir.setText(self.config.save_directory)
        self.txt_template.setText(self.config.filename_template)
        
        fmt = self.config.default_format.lower()
        if fmt == "jpg" or fmt == "jpeg":
            self.cbo_format.setCurrentIndex(1)
        elif fmt == "webp":
            self.cbo_format.setCurrentIndex(2)
        else:
            self.cbo_format.setCurrentIndex(0)

        self.chk_copy_on_save.setChecked(self.config.copy_to_clipboard_on_save)
        self.chk_copy_on_capture.setChecked(self.config.copy_to_clipboard_on_capture)
        self.chk_notify_on_save.setChecked(self.config.notify_on_save)

        # Shortcuts
        self.key_launch.setKeySequence(QKeySequence(self.config.shortcut_launch))
        self.key_scrolling.setKeySequence(QKeySequence(self.config.shortcut_scrolling))
        self.key_region.setKeySequence(QKeySequence(self.config.shortcut_region))
        self.key_fullscreen.setKeySequence(QKeySequence(self.config.shortcut_fullscreen))
        self.key_window.setKeySequence(QKeySequence(self.config.shortcut_window))

        # Scrolling
        self.spin_scroll_step.setValue(self.config.scroll_step_pixels)
        self.spin_scroll_delay.setValue(self.config.scroll_delay_ms)
        self.spin_scrollbar_margin.setValue(self.config.scrollbar_margin_right)
        self.spin_max_frames.setValue(self.config.scroll_max_frames)
        self.chk_auto_detect_end.setChecked(self.config.auto_detect_end_of_scroll)

        self._update_filename_preview()

    def _update_filename_preview(self):
        tpl = self.txt_template.text().strip() or "OmniShot_%Y%m%d_%H%M%S.png"
        try:
            preview_name = datetime.now().strftime(tpl)
        except Exception:
            preview_name = "Invalid timestamp format"
        self.lbl_preview.setText(f"Live Preview: {preview_name}")

    def _browse_save_directory(self):
        curr = self.txt_save_dir.text().strip() or str(Path.home() / "Pictures" / "Screenshots")
        selected_dir = QFileDialog.getExistingDirectory(self, "Select Screenshots Save Directory", curr)
        if selected_dir:
            self.txt_save_dir.setText(selected_dir)

    def _reset_shortcuts_to_defaults(self):
        self.key_launch.setKeySequence(QKeySequence("Meta+Shift+S"))
        self.key_scrolling.setKeySequence(QKeySequence("Meta+Shift+C"))
        self.key_region.setKeySequence(QKeySequence("Meta+Shift+R"))
        self.key_fullscreen.setKeySequence(QKeySequence("Print"))
        self.key_window.setKeySequence(QKeySequence("Meta+Print"))
        self.lbl_status.setText("Shortcuts reset to defaults.")

    def _apply_kde_shortcuts_now(self):
        self._sync_shortcuts_to_config()
        self.config.apply_kde_shortcuts()
        self.lbl_status.setText("✓ KDE Plasma Shortcuts successfully updated!")

    def _sync_shortcuts_to_config(self):
        self.config.shortcut_launch = self.key_launch.keySequence().toString() or "Meta+Shift+S"
        self.config.shortcut_scrolling = self.key_scrolling.keySequence().toString() or "Meta+Shift+C"
        self.config.shortcut_region = self.key_region.keySequence().toString() or "Meta+Shift+R"
        self.config.shortcut_fullscreen = self.key_fullscreen.keySequence().toString() or "Print"
        self.config.shortcut_window = self.key_window.keySequence().toString() or "Meta+Print"

    def _save_and_apply(self):
        # 1. Update save directory & files
        save_dir = self.txt_save_dir.text().strip()
        if save_dir:
            try:
                Path(save_dir).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            self.config.save_directory = save_dir

        tpl = self.txt_template.text().strip()
        if tpl:
            self.config.filename_template = tpl

        idx = self.cbo_format.currentIndex()
        if idx == 1:
            self.config.default_format = "jpg"
        elif idx == 2:
            self.config.default_format = "webp"
        else:
            self.config.default_format = "png"

        self.config.copy_to_clipboard_on_save = self.chk_copy_on_save.isChecked()
        self.config.copy_to_clipboard_on_capture = self.chk_copy_on_capture.isChecked()
        self.config.notify_on_save = self.chk_notify_on_save.isChecked()

        # 2. Update shortcuts
        self._sync_shortcuts_to_config()

        # 3. Update scrolling parameters
        self.config.scroll_step_pixels = self.spin_scroll_step.value()
        self.config.scroll_delay_ms = self.spin_scroll_delay.value()
        self.config.scrollbar_margin_right = self.spin_scrollbar_margin.value()
        self.config.scroll_max_frames = self.spin_max_frames.value()
        self.config.auto_detect_end_of_scroll = self.chk_auto_detect_end.isChecked()

        # 4. Save to JSON and apply to KDE
        self.config.save()
        self.config.apply_kde_shortcuts()

        self.settingsSaved.emit()
        self.accept()
