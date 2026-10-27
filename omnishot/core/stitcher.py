"""
OmniShot Python Stitching Controller
Manages frame capture buffers, translation detection via libomnishot_stitch.so,
and seamless vertical stitching.
"""

import os
import ctypes
from pathlib import Path
from typing import Optional, Tuple
from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import Qt

class CStitchResult(ctypes.Structure):
    _fields_ = [
        ("offset_y", ctypes.c_int),
        ("offset_x", ctypes.c_int),
        ("confidence", ctypes.c_double),
        ("mean_diff", ctypes.c_double),
        ("is_identical", ctypes.c_int),
    ]

class ScrollingStitcher:
    def __init__(
        self,
        margin_x_left: int = 10,
        margin_x_right: int = 24, # exclude scrollbar
        margin_y_top: int = 0,
        margin_y_bottom: int = 0,
        max_allowed_diff: float = 30.0,
        is_manual: bool = False
    ):
        self.margin_x_left = margin_x_left
        self.margin_x_right = margin_x_right
        self.margin_y_top = margin_y_top
        self.margin_y_bottom = margin_y_bottom
        self.max_allowed_diff = max_allowed_diff
        self.is_manual = is_manual

        self._lib = None
        self._load_native_library()

        self._stitched: Optional[QImage] = None
        self._prev_frame: Optional[QImage] = None
        self._frame_count: int = 0
        self._identical_count: int = 0
        # Require at least 25 consecutive identical frames before considering end-of-scroll
        self._max_identical_before_stop: int = 25

    def _load_native_library(self):
        so_path = Path(__file__).parent / "libomnishot_stitch.so"
        if not so_path.exists():
            raise FileNotFoundError(f"Native stitcher library not found at: {so_path}")

        self._lib = ctypes.CDLL(str(so_path))
        self._lib.omnishot_find_vertical_offset.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_double, ctypes.POINTER(CStitchResult)
        ]
        self._lib.omnishot_find_vertical_offset.restype = ctypes.c_int

    def reset(self):
        """Clears current stitch buffer."""
        self._stitched = None
        self._prev_frame = None
        self._frame_count = 0
        self._identical_count = 0

    def start(self, initial_frame: QImage):
        """Initializes stitching session with the first captured frame."""
        self.reset()
        if initial_frame.format() not in (QImage.Format.Format_RGBX8888, QImage.Format.Format_RGBA8888, QImage.Format.Format_ARGB32):
            self._stitched = initial_frame.convertToFormat(QImage.Format.Format_RGBX8888)
        else:
            self._stitched = initial_frame.copy()
        
        self._prev_frame = self._stitched.copy()
        self._frame_count = 1

    def is_active(self) -> bool:
        return self._stitched is not None

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def current_height(self) -> int:
        return self._stitched.height() if self._stitched else 0

    @property
    def current_width(self) -> int:
        return self._stitched.width() if self._stitched else 0

    def add_frame(self, new_frame: QImage) -> Tuple[bool, int, str]:
        """
        Processes a newly captured frame, detects vertical shift, and stitches.
        Returns: (success, offset_y, status_message)
          - success=True, offset_y > 0: frame stitched successfully
          - success=True, offset_y == 0: page stationary
          - success=False: failed to find reliable match
        """
        if self._stitched is None or self._prev_frame is None:
            self.start(new_frame)
            return True, 0, "Started"

        if new_frame.width() != self._prev_frame.width() or new_frame.height() != self._prev_frame.height():
            return False, -1, "Frame dimension mismatch"

        frame = new_frame
        if frame.format() != QImage.Format.Format_RGBX8888:
            frame = frame.convertToFormat(QImage.Format.Format_RGBX8888)

        w = frame.width()
        h = frame.height()

        b_prev = self._prev_frame.bits()
        b_curr = frame.bits()
        ptr_prev = ctypes.addressof(ctypes.c_char.from_buffer(b_prev))
        ptr_curr = ctypes.addressof(ctypes.c_char.from_buffer(b_curr))

        min_d = 2
        max_d = int(h * 0.90)

        result = CStitchResult()
        d = self._lib.omnishot_find_vertical_offset(
            ptr_prev, ptr_curr, w, h,
            min_d, max_d,
            self.margin_x_left, self.margin_x_right,
            self.margin_y_top, self.margin_y_bottom,
            self.max_allowed_diff, ctypes.byref(result)
        )

        if result.is_identical or d == 0:
            self._identical_count += 1
            # In manual mode, NEVER auto-abort on identical frames. The user is in control.
            # In auto mode, only auto-abort if we have already successfully stitched several frames (frame_count >= 3).
            if not self.is_manual and self._frame_count >= 3 and self._identical_count >= self._max_identical_before_stop:
                return True, 0, "End of scroll detected (content reached bottom)"
            return True, 0, "No scroll movement detected"

        self._identical_count = 0

        if d > 0:
            # Stitch the new d rows to the bottom of the composite canvas
            old_h = self._stitched.height()
            new_h = old_h + d
            
            new_canvas = QImage(w, new_h, QImage.Format.Format_RGBX8888)
            painter = QPainter(new_canvas)
            painter.drawImage(0, 0, self._stitched)
            # Slice the bottom d rows from new_frame: from row (h - d) to h
            new_slice = frame.copy(0, h - d, w, d)
            painter.drawImage(0, old_h, new_slice)
            painter.end()

            self._stitched = new_canvas
            self._prev_frame = frame.copy()
            self._frame_count += 1
            return True, d, f"Stitched +{d}px (confidence: {result.confidence:.2f})"

        return False, -1, f"No overlap match found (mean diff: {result.mean_diff:.1f})"

    def get_stitched_image(self) -> Optional[QImage]:
        return self._stitched

    def get_preview_thumbnail(self, max_height: int = 240) -> Optional[QImage]:
        """Returns a scaled thumbnail for the live HUD."""
        if not self._stitched or self._stitched.height() <= 0:
            return None
        return self._stitched.scaledToHeight(max_height, Qt.TransformationMode.SmoothTransformation)
