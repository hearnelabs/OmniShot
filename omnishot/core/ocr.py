"""
OmniShot OCR (Optical Character Recognition) Integration
Uses system tesseract engine to extract text from screenshots.
"""

import subprocess
from typing import Optional
from PySide6.QtGui import QImage
from PySide6.QtCore import QBuffer, QIODevice

class OCREngine:
    @staticmethod
    def is_available() -> bool:
        try:
            res = subprocess.run(["which", "tesseract"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return res.returncode == 0
        except Exception:
            return False

    @staticmethod
    def extract_text(image: QImage, lang: str = "eng") -> Optional[str]:
        """Extracts text from a QImage using tesseract."""
        if image.isNull() or image.width() <= 0 or image.height() <= 0:
            return None

        # Convert QImage to PNG bytes in memory
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        png_bytes = bytes(buffer.data())
        buffer.close()

        try:
            cmd = ["tesseract", "stdin", "stdout", "-l", lang, "--psm", "3"]
            proc = subprocess.run(
                cmd,
                input=png_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            if proc.returncode == 0:
                text = proc.stdout.decode("utf-8", errors="replace").strip()
                return text
            else:
                err = proc.stderr.decode("utf-8", errors="replace")
                print(f"[OmniShot OCR] Tesseract error: {err}")
                return None
        except Exception as e:
            print(f"[OmniShot OCR] Failed running tesseract: {e}")
            return None
