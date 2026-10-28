"""
OmniShot Python Stitching Controller
Manages frame capture buffers, translation detection via libomnishot_stitch.so,
multi-zone correlation, floating widget rejection, and seamless vertical stitching.
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

        self._initial_frame: Optional[QImage] = None
        self._body_canvas: Optional[QImage] = None
        self._last_frame: Optional[QImage] = None
        self._prev_frame: Optional[QImage] = None
        self._margins_detected: bool = False
        self._frame_count: int = 0
        self._identical_count: int = 0
        # Require at least 25 consecutive identical frames before considering end-of-scroll
        self._max_identical_before_stop: int = 25

    def _load_native_library(self):
        so_path = Path(__file__).parent / "libomnishot_stitch.so"
        if not so_path.exists():
            # Attempt automatic on-the-fly compilation for seamless portability on fresh CachyOS installs
            candidates = [
                Path(__file__).parent / "stitcher.c",
                Path(__file__).parent.parent.parent / "native" / "stitcher.c"
            ]
            c_source = None
            for cand in candidates:
                if cand.exists():
                    c_source = cand
                    break
            
            if c_source:
                import subprocess
                print(f"[OmniShot] Building native acceleration library from {c_source}...")
                try:
                    subprocess.run(
                        ["gcc", "-O3", "-march=native", "-fPIC", "-shared", str(c_source), "-o", str(so_path), "-lm"],
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    print(f"[OmniShot] Successfully built {so_path}")
                except Exception as build_err:
                    # Fallback without -march=native if host architecture flags complain
                    try:
                        subprocess.run(
                            ["gcc", "-O3", "-fPIC", "-shared", str(c_source), "-o", str(so_path), "-lm"],
                            check=True,
                            capture_output=True,
                            text=True
                        )
                        print(f"[OmniShot] Successfully built {so_path} (standard flags)")
                    except Exception:
                        raise FileNotFoundError(
                            f"Native stitcher library missing and auto-compilation failed: {build_err}. "
                            "Please run 'gcc -O3 -fPIC -shared native/stitcher.c -o omnishot/core/libomnishot_stitch.so -lm'."
                        )
            else:
                raise FileNotFoundError(f"Native stitcher library not found at: {so_path}")

        self._lib = ctypes.CDLL(str(so_path))
        self._lib.omnishot_find_vertical_offset.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_double, ctypes.POINTER(CStitchResult)
        ]
        self._lib.omnishot_find_vertical_offset.restype = ctypes.c_int

        self._lib.omnishot_detect_static_margins.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
        ]
        self._lib.omnishot_detect_static_margins.restype = None

    def reset(self):
        """Clears current stitch buffer."""
        self._initial_frame = None
        self._body_canvas = None
        self._last_frame = None
        self._prev_frame = None
        self._margins_detected = False
        self._frame_count = 0
        self._identical_count = 0

    def start(self, initial_frame: QImage):
        """Initializes stitching session with the first captured frame."""
        self.reset()
        if initial_frame.format() not in (QImage.Format.Format_RGBX8888, QImage.Format.Format_RGBA8888, QImage.Format.Format_ARGB32):
            converted = initial_frame.convertToFormat(QImage.Format.Format_RGBX8888)
        else:
            converted = initial_frame.copy()
        
        self._initial_frame = converted
        self._prev_frame = converted.copy()
        self._last_frame = converted.copy()
        self._frame_count = 1

    def is_active(self) -> bool:
        return self._initial_frame is not None

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def current_height(self) -> int:
        img = self.get_stitched_image()
        return img.height() if img else 0

    @property
    def current_width(self) -> int:
        return self._initial_frame.width() if self._initial_frame else 0

    def add_frame(self, new_frame: QImage) -> Tuple[bool, int, str]:
        """
        Processes a newly captured frame, detects vertical shift, and stitches.
        Returns: (success, offset_y, status_message)
          - success=True, offset_y > 0: frame stitched successfully
          - success=True, offset_y == 0: page stationary
          - success=False: failed to find reliable match
        """
        if self._initial_frame is None or self._prev_frame is None:
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
            # On first displacement, detect static margins (header and footer/floating buttons)
            if not self._margins_detected:
                c_hdr = ctypes.c_int(0)
                c_ftr = ctypes.c_int(0)
                self._lib.omnishot_detect_static_margins(
                    ptr_prev, ptr_curr, w, h,
                    self.margin_x_left, self.margin_x_right,
                    ctypes.byref(c_hdr), ctypes.byref(c_ftr)
                )
                if self.margin_y_top == 0 and c_hdr.value > 0:
                    self.margin_y_top = c_hdr.value
                if self.margin_y_bottom == 0 and c_ftr.value > 0:
                    self.margin_y_bottom = c_ftr.value

                if self.margin_y_bottom >= h - 100:
                    self.margin_y_bottom = 0
                if self.margin_y_top >= h / 3:
                    self.margin_y_top = 0

                self._margins_detected = True

                # Initialize body canvas with initial frame up to (h - margin_y_bottom)
                cut_bottom = h - self.margin_y_bottom
                self._body_canvas = self._initial_frame.copy(0, 0, w, cut_bottom)

            cut_bottom = h - self.margin_y_bottom
            # Newly revealed content slice: from row (cut_bottom - d) to cut_bottom
            # This row range is strictly ABOVE any floating buttons or footer!
            new_slice = frame.copy(0, cut_bottom - d, w, d)

            old_h = self._body_canvas.height()
            new_canvas = QImage(w, old_h + d, QImage.Format.Format_RGBX8888)
            painter = QPainter(new_canvas)
            painter.drawImage(0, 0, self._body_canvas)
            painter.drawImage(0, old_h, new_slice)
            painter.end()

            self._body_canvas = new_canvas
            self._prev_frame = frame.copy()
            self._last_frame = frame.copy()
            self._frame_count += 1
            return True, d, f"Stitched +{d}px (confidence: {result.confidence:.2f})"

        return False, -1, f"No overlap match found (mean diff: {result.mean_diff:.1f})"

    def get_stitched_image(self) -> Optional[QImage]:
        """Returns the fully composed composite image, seamlessly attaching the final footer."""
        if not self._initial_frame:
            return None

        if self._body_canvas is None:
            return self._initial_frame

        if self.margin_y_bottom > 0 and self._last_frame:
            cut_bottom = self._last_frame.height() - self.margin_y_bottom
            footer_slice = self._last_frame.copy(0, cut_bottom, self._last_frame.width(), self.margin_y_bottom)

            final_img = QImage(self._body_canvas.width(), self._body_canvas.height() + self.margin_y_bottom, QImage.Format.Format_RGBX8888)
            painter = QPainter(final_img)
            painter.drawImage(0, 0, self._body_canvas)
            painter.drawImage(0, self._body_canvas.height(), footer_slice)
            painter.end()
            return final_img

        return self._body_canvas

    def get_preview_thumbnail(self, max_height: int = 240) -> Optional[QImage]:
        """Returns a scaled thumbnail for the live HUD."""
        img = self.get_stitched_image()
        if not img or img.height() <= 0:
            return None
        return img.scaledToHeight(max_height, Qt.TransformationMode.SmoothTransformation)
