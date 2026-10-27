"""
OmniShot Core Package
"""
from .config import OmniShotConfig
from .capture import get_capture_backend, KWinCaptureBackend
from .uinput_mouse import UInputScroller
from .stitcher import ScrollingStitcher
from .ocr import OCREngine

__all__ = [
    "OmniShotConfig",
    "get_capture_backend",
    "KWinCaptureBackend",
    "UInputScroller",
    "ScrollingStitcher",
    "OCREngine"
]
