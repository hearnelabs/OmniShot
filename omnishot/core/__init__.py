"""
OmniShot Core Package
"""
from .config import OmniShotConfig
from .capture import get_capture_backend, KWinCaptureBackend
from .uinput_mouse import UInputScroller
from .stitcher import ScrollingStitcher
from .ocr import OCREngine
from .clipboard import copy_image_to_clipboard, get_clipboard_image, ClipboardPersistenceKeeper

__all__ = [
    "OmniShotConfig",
    "get_capture_backend",
    "KWinCaptureBackend",
    "UInputScroller",
    "ScrollingStitcher",
    "OCREngine",
    "copy_image_to_clipboard",
    "get_clipboard_image",
    "ClipboardPersistenceKeeper"
]
