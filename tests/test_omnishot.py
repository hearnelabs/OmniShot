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
        # Test capturing small 50x50 area
        img = backend.capture_area(0, 0, 50, 50)
        self.assertIsNotNone(img, "KWin ScreenShot2 should capture area successfully")
        self.assertEqual(img.width(), 50)
        self.assertEqual(img.height(), 50)

    def test_05_ocr_engine_available(self):
        self.assertTrue(OCREngine.is_available(), "Tesseract OCR engine should be installed on CachyOS")

    def test_06_cli_parser(self):
        parser = build_parser()
        args = parser.parse_args(["-S", "-d", "500"])
        self.assertTrue(args.scroll)
        self.assertEqual(args.delay, 500)

    def test_07_sharex_vector_annotations(self):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QRectF, QPointF
        from omnishot.ui.canvas import (
            AnnotationCanvas, RectAnnotation, ArrowAnnotation,
            TextAnnotation, SpeechBalloonAnnotation, StepBadgeAnnotation
        )
        app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])
        canvas = AnnotationCanvas()
        img = QImage(300, 200, QImage.Format.Format_RGBX8888)
        img.fill(QColor(40, 40, 40))
        canvas.set_image(img)

        # Add ShareX vector items
        r = RectAnnotation(is_rounded=True)
        r.rect = QRectF(10, 10, 50, 40)
        canvas.annotations.append(r)

        a = ArrowAnnotation()
        a.p1 = QPointF(80, 20)
        a.p2 = QPointF(150, 60)
        canvas.annotations.append(a)

        t = TextAnnotation("ShareX Text")
        t.rect = QRectF(20, 80, 100, 30)
        canvas.annotations.append(t)

        s = StepBadgeAnnotation(1)
        s.rect = QRectF(180, 80, 30, 30)
        canvas.annotations.append(s)

        sb = SpeechBalloonAnnotation("Bubble")
        sb.rect = QRectF(20, 130, 80, 40)
        canvas.annotations.append(sb)

        comp = canvas.render_composite_image()
        self.assertIsNotNone(comp)
        self.assertEqual(comp.width(), 300)
        self.assertEqual(comp.height(), 200)

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

if __name__ == "__main__":
    unittest.main()

