"""
OmniShot Comprehensive Test Suite
Validates all core subsystems:
1. Native C Stitching Engine
2. KWin Wayland ScreenShot2 Backend
3. /dev/uinput Virtual Scroll Controller
4. Tesseract OCR Text Extraction
5. CLI Argument Parsing
"""

import os
import sys
import unittest
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor
from omnishot.core.config import OmniShotConfig
from omnishot.core.stitcher import ScrollingStitcher
from omnishot.core.uinput_mouse import UInputScroller
from omnishot.core.capture import KWinCaptureBackend
from omnishot.core.ocr import OCREngine
from omnishot.cli import build_parser

class TestOmniShot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize offscreen Qt application for image and widget tests
        cls.app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])

    def test_01_config_defaults(self):
        cfg = OmniShotConfig()
        self.assertTrue(cfg.save_directory.endswith("Pictures/Screenshots"))
        self.assertEqual(cfg.scroll_step_pixels, 120)
        self.assertEqual(cfg.scrollbar_margin_right, 24)

    def test_02_stitcher_exact_displacements(self):
        """Simulate vertical scrolling through a 1500px image with multiple variable slices."""
        width = 400
        height = 1500
        doc = QImage(width, height, QImage.Format.Format_RGBX8888)
        doc.fill(QColor(240, 242, 245))

        painter = QPainter(doc)
        for i in range(30):
            y = 40 + i * 45
            painter.fillRect(20, y, 100, 15, QColor(50 + (i * 11) % 180, 80, 200))
            painter.fillRect(160, y, 80, 15, QColor(220, 40 + (i * 17) % 150, 60))
        painter.end()

        view_h = 400
        scroll_offsets = [0, 60, 135, 220, 310, 415, 520, 630]

        frames = []
        for y in scroll_offsets:
            slice_img = doc.copy(0, y, width, view_h)
            frames.append(slice_img)

        stitcher = ScrollingStitcher(margin_x_left=10, margin_x_right=20)
        stitcher.start(frames[0])

        for i in range(1, len(frames)):
            expected_d = scroll_offsets[i] - scroll_offsets[i - 1]
            success, d, msg = stitcher.add_frame(frames[i])
            self.assertTrue(success, f"Frame {i} should stitch successfully")
            self.assertEqual(d, expected_d, f"Frame {i}: expected offset {expected_d}, detected {d}")

        expected_total_h = scroll_offsets[-1] + view_h
        self.assertEqual(stitcher.current_height, expected_total_h)
        self.assertEqual(stitcher.frame_count, len(frames))

    def test_03_uinput_controller(self):
        scroller = UInputScroller()
        self.assertTrue(scroller.is_available(), "/dev/uinput should be accessible to user in uinput group")
        opened = scroller.open()
        self.assertTrue(opened, "uinput virtual scroll device should initialize successfully")
        success = scroller.scroll_down(steps=1)
        self.assertTrue(success, "scroll_down event should emit without error")
        scroller.close()

    def test_04_kwin_capture_backend(self):
        backend = KWinCaptureBackend()
        # Test capturing small 50x50 area at native physical resolution (1.25x scale -> 63x63 px)
        img = backend.capture_area(0, 0, 50, 50)
        self.assertIsNotNone(img, "KWin ScreenShot2 should capture area successfully")
        self.assertGreaterEqual(img.width(), 50, "Captured image must preserve full native physical pixels")
        self.assertGreaterEqual(img.height(), 50, "Captured image must preserve full native physical pixels")

    def test_05_ocr_engine_available(self):
        self.assertTrue(OCREngine.is_available(), "Tesseract OCR engine should be installed on CachyOS")

    def test_06_cli_parser(self):
        parser = build_parser()
        args = parser.parse_args(["-S", "-d", "500"])
        self.assertTrue(args.scroll)
        self.assertEqual(args.delay, 500)

    def test_07_omnishot_vector_annotations_and_tools(self):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QRectF, QPointF
        from omnishot.ui.canvas import (
            AnnotationCanvas, ToolType, RectAnnotation, ArrowAnnotation,
            LineAnnotation, TextAnnotation, SpeechBalloonAnnotation,
            StepBadgeAnnotation, CropAnnotation
        )
        app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])
        canvas = AnnotationCanvas()
        img = QImage(300, 200, QImage.Format.Format_RGBX8888)
        img.fill(QColor(40, 40, 40))
        canvas.set_image(img)

        # Test tool activation
        canvas.set_active_tool(ToolType.RECTANGLE)
        self.assertEqual(canvas.current_tool, ToolType.RECTANGLE)

        canvas.set_active_tool(ToolType.ARROW)
        self.assertEqual(canvas.current_tool, ToolType.ARROW)

        # Add OmniShot vector items
        r = RectAnnotation(is_rounded=True)
        r.rect = QRectF(10, 10, 50, 40)
        self.assertTrue(r.hit_test(QPointF(25, 25)))
        self.assertFalse(r.hit_test(QPointF(100, 100)))
        canvas.annotations.append(r)

        a = ArrowAnnotation()
        a.p1 = QPointF(80, 20)
        a.p2 = QPointF(150, 60)
        self.assertTrue(a.hit_test(QPointF(115, 40)))
        canvas.annotations.append(a)

        t = TextAnnotation("OmniShot Text")
        t.rect = QRectF(20, 80, 100, 30)
        canvas.annotations.append(t)

        s = StepBadgeAnnotation(1)
        s.rect = QRectF(180, 80, 30, 30)
        self.assertTrue(s.hit_test(s.rect.center()))
        canvas.annotations.append(s)

        sb = SpeechBalloonAnnotation("Bubble")
        sb.rect = QRectF(20, 130, 80, 40)
        canvas.annotations.append(sb)

        comp = canvas.render_composite_image()
        self.assertIsNotNone(comp)
        self.assertEqual(comp.width(), 300)
        self.assertEqual(comp.height(), 200)

        # Test cropping
        crop = CropAnnotation()
        crop.rect = QRectF(10, 10, 100, 100)
        canvas._creating_annotation = crop
        canvas.apply_crop()
        self.assertEqual(canvas.get_image().width(), 100)
        self.assertEqual(canvas.get_image().height(), 100)

    def test_08_spectacle_launch_overlay(self):
        from omnishot.ui.launch_overlay import SpectacleLaunchOverlay
        bg = QImage(800, 600, QImage.Format.Format_RGBX8888)
        bg.fill(QColor(30, 35, 42))

        overlay = SpectacleLaunchOverlay(bg)
        overlay.resize(800, 600)
        
        self.assertIsNotNone(overlay.bottom_pill)
        self.assertEqual(overlay.bottom_pill.btn_scroll.text(), "Scrolling Capture")
        self.assertEqual(overlay.top_pill.text(), "OmniShot - Ready")
        
        # Simulate selection
        from PySide6.QtCore import QRect
        overlay._selected_rect = QRect(50, 50, 200, 150)
        overlay._position_selection_strip(overlay._selected_rect)
        self.assertFalse(overlay.selection_strip.isHidden())
        self.assertEqual(overlay._selected_rect.width(), 200)
        overlay.close()

    def test_09_opacity_modulations_and_selection_sync(self):
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor
        from omnishot.ui.canvas import AnnotationCanvas, FreehandAnnotation, TextAnnotation, StepBadgeAnnotation
        from omnishot.ui.main_window import OmniShotMainWindow

        canvas = AnnotationCanvas()
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        img.fill(QColor(255, 255, 255))
        canvas.set_image(img)

        hl = FreehandAnnotation(is_highlighter=True)
        hl.add_point(QPointF(10, 10))
        hl.add_point(QPointF(100, 100))
        hl.opacity = 0.42
        canvas.annotations.append(hl)

        txt = TextAnnotation("Sample")
        txt.rect = QRectF(10, 20, 80, 30)
        txt.opacity = 0.75
        canvas.annotations.append(txt)

        win = OmniShotMainWindow()
        win.set_captured_image(img)

        # Test selecting highlighter syncs opacity slider to 42%
        win.canvas.selected_annotation = hl
        win._on_annotation_selection_changed(hl)
        self.assertEqual(win.sidebar.slider_opac.value(), 42)
        self.assertEqual(win.sidebar.lbl_opac_val.text(), "42%")

        # Test changing slider updates selected annotation
        win._on_opacity_changed(60)
        self.assertAlmostEqual(hl.opacity, 0.60, places=2)

        # Test changing color updates selected annotation
        win._on_color_selected(QColor("#2ecc71"))
        self.assertEqual(hl.stroke_color.name(), "#2ecc71")
        win.close()

    def test_10_settings_dialog_preferences_and_shortcuts(self):
        from omnishot.ui.settings_dialog import OmniShotSettingsDialog
        cfg = OmniShotConfig()
        dlg = OmniShotSettingsDialog(config=cfg)
        
        # Test editing save location
        dlg.txt_save_dir.setText("/home/test/Screenshots")
        dlg.txt_template.setText("Test_%Y%m%d.png")
        dlg.key_launch.setKeySequence("Meta+Shift+S")
        dlg.key_scrolling.setKeySequence("Meta+Shift+C")
        dlg.spin_scroll_step.setValue(140)
        dlg._save_and_apply()

        self.assertEqual(cfg.save_directory, "/home/test/Screenshots")
        self.assertEqual(cfg.filename_template, "Test_%Y%m%d.png")
        self.assertEqual(cfg.shortcut_scrolling, "Meta+Shift+C")
        self.assertEqual(cfg.scroll_step_pixels, 140)
        # Verify "Open in Dolphin" button is completely removed
        self.assertFalse(hasattr(dlg, "btn_open_dolphin"), "Open in Dolphin button should be removed")
        dlg.close()

    def test_11_main_window_resizability(self):
        """Verify the main annotation window is fully resizable down to compact viewports."""
        from omnishot.ui.main_window import OmniShotMainWindow
        win = OmniShotMainWindow()
        test_img = QImage(800, 600, QImage.Format.Format_RGB32)
        test_img.fill(QColor(30, 30, 30))
        win.set_captured_image(test_img)

        # Minimum size should be compact
        self.assertLessEqual(win.minimumWidth(), 500)
        self.assertLessEqual(win.minimumHeight(), 400)

        # Test resizing to compact dimensions
        win.resize(600, 450)
        self.app.processEvents()
        self.assertEqual(win.width(), 600)
        self.assertEqual(win.height(), 450)

        # Test resizing to widescreen
        win.resize(1600, 900)
        self.app.processEvents()
        self.assertEqual(win.width(), 1600)
        self.assertEqual(win.height(), 900)
        win.close()

if __name__ == "__main__":
    unittest.main()

