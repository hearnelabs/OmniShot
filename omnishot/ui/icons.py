"""
OmniShot Vector Icon Factory
Provides high-DPI crisp vector QIcons for all annotation tools,
capture modes, and ribbon actions, matching KDE Plasma 6 Breeze Dark and OmniShot Pro.
"""

from PySide6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QPolygonF
)
from PySide6.QtCore import Qt, QRectF, QPointF

def _create_pixmap(size: int = 32) -> (QPixmap, QPainter):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pm, p

def get_tool_icon(tool_name: str) -> QIcon:
    """Returns a pristine high-DPI vector QIcon for any tool."""
    # Check theme first for standard desktop icons
    theme_map = {
        "pointer": "edit-select",
        "crop": "transform-crop",
        "dropper": "color-picker",
        "paste": "edit-paste",
        "copy": "edit-copy",
    }
    if tool_name in theme_map:
        ic = QIcon.fromTheme(theme_map[tool_name])
        if not ic.isNull():
            return ic

    pm, p = _create_pixmap(32)

    if tool_name == "pointer":
        p.setPen(QPen(QColor("#0078d4"), 1.5))
        p.setBrush(QBrush(QColor("#ffffff")))
        poly = QPolygonF([QPointF(6, 6), QPointF(6, 26), QPointF(12, 20), QPointF(18, 26), QPointF(21, 23), QPointF(15, 17), QPointF(23, 17)])
        p.drawPolygon(poly)

    elif tool_name == "pen":
        p.setPen(QPen(QColor("#3daee9"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(7, 25), QPointF(23, 9))
        p.setBrush(QBrush(QColor("#3daee9")))
        p.drawPolygon(QPolygonF([QPointF(5, 27), QPointF(9, 23), QPointF(5, 23)]))

    elif tool_name == "arrow":
        p.setPen(QPen(QColor("#3daee9"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(7, 25), QPointF(22, 10))
        p.setBrush(QBrush(QColor("#3daee9")))
        p.drawPolygon(QPolygonF([QPointF(24, 8), QPointF(15, 9), QPointF(23, 17)]))

    elif tool_name == "highlighter":
        p.setPen(QPen(QColor("#f1c40f"), 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap))
        p.drawLine(QPointF(8, 24), QPointF(24, 8))
        p.setPen(QPen(QColor("#d4ac0d"), 1.5))
        p.setBrush(QBrush(QColor("#f39c12")))
        p.drawRect(QRectF(19, 5, 8, 8))

    elif tool_name in ("rectangle", "box"):
        p.setPen(QPen(QColor("#3daee9"), 2.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(5, 7, 22, 18))

    elif tool_name == "rounded_rect":
        p.setPen(QPen(QColor("#3daee9"), 2.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(5, 7, 22, 18), 5, 5)

    elif tool_name in ("ellipse", "circle"):
        p.setPen(QPen(QColor("#3daee9"), 2.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(5, 5, 22, 22))

    elif tool_name == "blur":
        # Water droplet with soft blur rings
        p.setPen(QPen(QColor("#29b6f6"), 2))
        p.setBrush(QBrush(QColor(41, 182, 246, 120)))
        path = QPainterPath()
        path.moveTo(16, 5)
        path.cubicTo(23, 14, 25, 20, 25, 23)
        path.arcTo(QRectF(7, 13, 18, 16), 0, -180)
        path.cubicTo(7, 20, 9, 14, 16, 5)
        p.drawPath(path)

    elif tool_name == "pixelate":
        # Checkered 3x3 pixel mosaic
        colors = [QColor("#3daee9"), QColor("#1e2227"), QColor("#64b5f6"),
                  QColor("#1e2227"), QColor("#3daee9"), QColor("#1e2227"),
                  QColor("#64b5f6"), QColor("#1e2227"), QColor("#3daee9")]
        for idx, col in enumerate(colors):
            x = 6 + (idx % 3) * 7
            y = 6 + (idx // 3) * 7
            p.fillRect(QRectF(x, y, 6, 6), col)
        p.setPen(QPen(QColor("#474e54"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(5, 5, 22, 22))

    elif tool_name in ("blackout", "solid_box"):
        p.setPen(QPen(QColor("#eff0f1"), 1))
        p.setBrush(QBrush(QColor("#000000")))
        p.drawRoundedRect(QRectF(5, 7, 22, 18), 3, 3)

    elif tool_name in ("step_badge", "step"):
        # Primary circle with '1' and mini circles '2', '3'
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#0078d4")))
        p.drawEllipse(QRectF(4, 8, 18, 18))
        p.setPen(QColor("#ffffff"))
        font = QFont("Noto Sans", 10, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QRectF(4, 8, 18, 18), Qt.AlignmentFlag.AlignCenter, "1")
        # Mini badge '2'
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#2980b9")))
        p.drawEllipse(QRectF(19, 4, 10, 10))
        # Mini badge '3'
        p.drawEllipse(QRectF(19, 18, 10, 10))

    elif tool_name in ("speech_balloon", "speech"):
        path = QPainterPath()
        path.addRoundedRect(QRectF(4, 5, 24, 17), 5, 5)
        path.addPolygon(QPolygonF([QPointF(10, 22), QPointF(18, 22), QPointF(7, 28)]))
        p.setPen(QPen(QColor("#3daee9"), 1.8))
        p.setBrush(QBrush(QColor(61, 174, 233, 40)))
        p.drawPath(path)

    elif tool_name == "text":
        p.setPen(QColor("#ffffff"))
        font = QFont("Noto Sans", 17, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QRectF(0, 0, 32, 32), Qt.AlignmentFlag.AlignCenter, "T")

    elif tool_name == "copy":
        p.setPen(QPen(QColor("#3daee9"), 1.8))
        p.setBrush(QBrush(QColor(61, 174, 233, 40)))
        p.drawRoundedRect(QRectF(11, 6, 15, 18), 2, 2)
        p.setPen(QPen(QColor("#ffffff"), 1.8))
        p.setBrush(QBrush(QColor(255, 255, 255, 30)))
        p.drawRoundedRect(QRectF(6, 10, 15, 18), 2, 2)

    elif tool_name == "paste":
        # Clipboard board with sheet of paper
        p.setPen(QPen(QColor("#8a93a0"), 1.8))
        p.setBrush(QBrush(QColor(40, 44, 52, 200)))
        p.drawRoundedRect(QRectF(5, 7, 22, 21), 2, 2)
        # Top metal clip
        p.setPen(QPen(QColor("#3daee9"), 1.5))
        p.setBrush(QBrush(QColor("#3daee9")))
        p.drawRoundedRect(QRectF(11, 4, 10, 5), 1, 1)
        # Paged document overlay
        p.setPen(QPen(QColor("#ffffff"), 1.5))
        p.setBrush(QBrush(QColor(255, 255, 255, 50)))
        p.drawRoundedRect(QRectF(9, 11, 14, 15), 1, 1)
        # Content lines on page
        p.setPen(QPen(QColor("#00f0ff"), 1.2))
        p.drawLine(QPointF(12, 16), QPointF(20, 16))
        p.drawLine(QPointF(12, 20), QPointF(18, 20))

    elif tool_name in ("save", "quick_save"):
        p.setPen(QPen(QColor("#3daee9"), 1.8))
        p.setBrush(QBrush(QColor(61, 174, 233, 35)))
        p.drawRoundedRect(QRectF(5, 5, 22, 22), 2, 2)
        p.fillRect(QRectF(9, 5, 14, 7), QColor("#ffffff"))
        p.fillRect(QRectF(11, 7, 3, 4), QColor("#121519"))
        p.fillRect(QRectF(8, 16, 16, 10), QColor("#ffffff"))

    elif tool_name == "save_as":
        p.setPen(QPen(QColor("#3daee9"), 1.8))
        p.setBrush(QBrush(QColor(61, 174, 233, 35)))
        p.drawRoundedRect(QRectF(5, 5, 20, 20), 2, 2)
        p.fillRect(QRectF(8, 5, 12, 6), QColor("#ffffff"))
        p.setPen(QPen(QColor("#00f0ff"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(17, 26), QPointF(27, 16))

    elif tool_name in ("scrolling_capture", "scroll"):
        # Glowing emerald scroll page
        p.setPen(QPen(QColor("#2ecc71"), 1.8))
        p.setBrush(QBrush(QColor(46, 204, 113, 35)))
        p.drawRoundedRect(QRectF(7, 4, 18, 24), 3, 3)
        # Horizontal lines
        p.setPen(QPen(QColor("#58d68d"), 1.5))
        p.drawLine(QPointF(11, 9), QPointF(21, 9))
        p.drawLine(QPointF(11, 13), QPointF(21, 13))
        p.drawLine(QPointF(11, 17), QPointF(21, 17))
        # Downward scroll arrow
        p.setPen(QPen(QColor("#ffffff"), 1.5))
        p.drawLine(QPointF(16, 20), QPointF(16, 25))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawPolygon(QPolygonF([QPointF(16, 26), QPointF(13, 23), QPointF(19, 23)]))

    elif tool_name == "ocr":
        # Viewfinder corners
        p.setPen(QPen(QColor("#3daee9"), 2.0))
        p.drawLine(QPointF(5, 10), QPointF(5, 5))
        p.drawLine(QPointF(5, 5), QPointF(10, 5))
        p.drawLine(QPointF(27, 10), QPointF(27, 5))
        p.drawLine(QPointF(27, 5), QPointF(22, 5))
        p.drawLine(QPointF(5, 22), QPointF(5, 27))
        p.drawLine(QPointF(5, 27), QPointF(10, 27))
        p.drawLine(QPointF(27, 22), QPointF(27, 27))
        p.drawLine(QPointF(27, 27), QPointF(22, 27))
        # Letters 'Aa' inside
        p.setPen(QColor("#ffffff"))
        font = QFont("Noto Sans", 9, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QRectF(4, 6, 24, 20), Qt.AlignmentFlag.AlignCenter, "Aa")

    elif tool_name == "region":
        # Crosshair crop box
        p.setPen(QPen(QColor("#3daee9"), 1.8, Qt.PenStyle.DashLine))
        p.drawRect(QRectF(7, 7, 18, 18))
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.drawLine(QPointF(16, 3), QPointF(16, 8))
        p.drawLine(QPointF(16, 24), QPointF(16, 29))
        p.drawLine(QPointF(3, 16), QPointF(8, 16))
        p.drawLine(QPointF(24, 16), QPointF(29, 16))

    elif tool_name == "window":
        p.setPen(QPen(QColor("#3daee9"), 1.8))
        p.setBrush(QBrush(QColor(61, 174, 233, 40)))
        p.drawRoundedRect(QRectF(5, 6, 22, 20), 3, 3)
        p.fillRect(QRectF(5, 6, 22, 5), QColor("#3daee9"))

    elif tool_name == "fullscreen":
        # Monitor
        p.setPen(QPen(QColor("#3daee9"), 1.8))
        p.setBrush(QBrush(QColor(61, 174, 233, 30)))
        p.drawRoundedRect(QRectF(4, 5, 24, 17), 2, 2)
        p.drawLine(QPointF(16, 22), QPointF(16, 26))
        p.drawLine(QPointF(11, 26), QPointF(21, 26))

    p.end()
    return QIcon(pm)
