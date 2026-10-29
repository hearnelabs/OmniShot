"""
OmniShot Vector-Based Annotation Canvas
OmniShot Image Editor capabilities:
Interactive vector annotations, selection handles, resizing, dragging,
drop shadows, speech balloons, step badges, blur, pixelate, magnify, and full undo/redo.
"""

import math
from typing import Optional, List, Dict, Any, Tuple
from PySide6.QtWidgets import QWidget, QInputDialog, QMenu
from PySide6.QtGui import (
    QImage, QPixmap, QPainter, QPen, QBrush, QColor, QFont,
    QPolygonF, QMouseEvent, QPaintEvent, QWheelEvent, QKeyEvent,
    QPainterPath, QCursor
)
from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QRectF, Signal

class ToolType:
    POINTER = "pointer"
    RECTANGLE = "rectangle"
    ROUNDED_RECT = "rounded_rect"
    ELLIPSE = "ellipse"
    LINE = "line"
    ARROW = "arrow"
    PEN = "pen"
    HIGHLIGHTER = "highlighter"
    TEXT = "text"
    SPEECH_BALLOON = "speech_balloon"
    STEP_BADGE = "step_badge"
    BLUR = "blur"
    PIXELATE = "pixelate"
    MAGNIFY = "magnify"
    CROP = "crop"
    IMAGE = "image"

# Handle identifiers for resizing
HANDLE_NONE = -1
HANDLE_TL = 0
HANDLE_TR = 1
HANDLE_BR = 2
HANDLE_BL = 3
HANDLE_TOP = 4
HANDLE_RIGHT = 5
HANDLE_BOTTOM = 6
HANDLE_LEFT = 7
HANDLE_SIZE = 8

def point_to_segment_distance(p: QPointF, a: QPointF, b: QPointF) -> float:
    ab = b - a
    l2 = ab.x() * ab.x() + ab.y() * ab.y()
    if l2 == 0.0:
        return math.hypot(p.x() - a.x(), p.y() - a.y())
    t = max(0.0, min(1.0, ((p.x() - a.x()) * ab.x() + (p.y() - a.y()) * ab.y()) / l2))
    proj = a + ab * t
    return math.hypot(p.x() - proj.x(), p.y() - proj.y())

class BaseAnnotation:
    def __init__(self):
        self.tool_type: str = ToolType.RECTANGLE
        self.rect: QRectF = QRectF()
        self.stroke_color: QColor = QColor("#ff0000") # OmniShot default red
        self.fill_color: QColor = QColor(0, 0, 0, 0) # transparent by default
        self.stroke_width: int = 4
        self.opacity: float = 1.0
        self.has_shadow: bool = True
        self.is_selected: bool = False

    @property
    def stroke_qcolor(self) -> QColor:
        return self.stroke_color if isinstance(self.stroke_color, QColor) else QColor(self.stroke_color)

    @property
    def fill_qcolor(self) -> QColor:
        return self.fill_color if isinstance(self.fill_color, QColor) else QColor(self.fill_color)

    def normalized_rect(self) -> QRectF:
        return self.rect.normalized()

    def hit_test(self, pt: QPointF) -> bool:
        r = self.normalized_rect()
        margin = max(6.0, float(self.stroke_width))
        return r.adjusted(-margin, -margin, margin, margin).contains(pt)

    def get_handles(self) -> Dict[int, QPointF]:
        r = self.normalized_rect()
        return {
            HANDLE_TL: r.topLeft(),
            HANDLE_TR: r.topRight(),
            HANDLE_BR: r.bottomRight(),
            HANDLE_BL: r.bottomLeft(),
            HANDLE_TOP: QPointF(r.center().x(), r.top()),
            HANDLE_RIGHT: QPointF(r.right(), r.center().y()),
            HANDLE_BOTTOM: QPointF(r.center().x(), r.bottom()),
            HANDLE_LEFT: QPointF(r.left(), r.center().y()),
        }

    def get_handle_at(self, pt: QPointF, tolerance: float = 8.0) -> int:
        for handle_id, handle_pt in self.get_handles().items():
            if math.hypot(pt.x() - handle_pt.x(), pt.y() - handle_pt.y()) <= tolerance:
                return handle_id
        return HANDLE_NONE

    def move_by(self, dx: float, dy: float):
        self.rect.translate(dx, dy)

    def resize_by_handle(self, handle_id: int, new_pt: QPointF):
        r = self.rect
        x1, y1, x2, y2 = r.left(), r.top(), r.right(), r.bottom()

        if handle_id == HANDLE_TL:
            x1, y1 = new_pt.x(), new_pt.y()
        elif handle_id == HANDLE_TR:
            x2, y1 = new_pt.x(), new_pt.y()
        elif handle_id == HANDLE_BR:
            x2, y2 = new_pt.x(), new_pt.y()
        elif handle_id == HANDLE_BL:
            x1, y2 = new_pt.x(), new_pt.y()
        elif handle_id == HANDLE_TOP:
            y1 = new_pt.y()
        elif handle_id == HANDLE_RIGHT:
            x2 = new_pt.x()
        elif handle_id == HANDLE_BOTTOM:
            y2 = new_pt.y()
        elif handle_id == HANDLE_LEFT:
            x1 = new_pt.x()

        self.rect = QRectF(x1, y1, x2 - x1, y2 - y1)

    def draw(self, painter: QPainter, base_image: Optional[QImage] = None):
        pass

    def draw_selection_outline(self, painter: QPainter):
        if not self.is_selected:
            return
        r = self.normalized_rect()
        painter.save()
        painter.setOpacity(1.0)
        
        # Dashed selection box
        pen = QPen(QColor(255, 255, 255), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(r.adjusted(-3, -3, 3, 3))

        # Circular handles
        painter.setPen(QPen(QColor(0, 120, 215), 1.5))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        for pt in self.get_handles().values():
            painter.drawEllipse(pt, HANDLE_SIZE / 2, HANDLE_SIZE / 2)

        painter.restore()

    def clone(self) -> 'BaseAnnotation':
        """Creates an independent deep copy of this annotation for undo/redo snapshots."""
        if hasattr(self, 'image'):
            c = self.__class__(self.image.copy() if self.image else None)
        elif hasattr(self, 'is_rounded'):
            c = self.__class__(self.is_rounded)
        else:
            c = self.__class__()
        c.tool_type = self.tool_type
        c.rect = QRectF(self.rect)
        c.stroke_color = QColor(self.stroke_color)
        c.fill_color = QColor(self.fill_color)
        c.stroke_width = self.stroke_width
        c.opacity = self.opacity
        c.has_shadow = self.has_shadow
        c.is_selected = self.is_selected

        for attr in ('text', 'font_size', 'is_bold', 'is_italic', 'is_underline', 'points', 'step_number', 'blur_radius', 'corner_radius', 'tail_pos', 'image'):
            if hasattr(self, attr):
                val = getattr(self, attr)
                if isinstance(val, QImage):
                    setattr(c, attr, val.copy())
                elif isinstance(val, list):
                    setattr(c, attr, [QPointF(pt) if isinstance(pt, QPointF) else pt for pt in val])
                elif isinstance(val, QPointF):
                    setattr(c, attr, QPointF(val))
                else:
                    setattr(c, attr, val)
        return c


class RectAnnotation(BaseAnnotation):
    def __init__(self, is_rounded: bool = False):
        super().__init__()
        self.tool_type = ToolType.ROUNDED_RECT if is_rounded else ToolType.RECTANGLE
        self.is_rounded = is_rounded
        self.corner_radius: float = 12.0

    def draw(self, painter: QPainter, base_image: Optional[QImage] = None):
        r = self.normalized_rect()
        if r.width() < 1 or r.height() < 1:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self.opacity)

        if self.has_shadow:
            painter.setPen(QPen(QColor(0, 0, 0, 90), self.stroke_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            sr = r.translated(2.5, 2.5)
            if self.is_rounded:
                painter.drawRoundedRect(sr, self.corner_radius, self.corner_radius)
            else:
                painter.drawRect(sr)

        pen = QPen(self.stroke_qcolor, self.stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(QBrush(self.fill_qcolor) if self.fill_qcolor.alpha() > 0 else Qt.BrushStyle.NoBrush)

        if self.is_rounded:
            painter.drawRoundedRect(r, self.corner_radius, self.corner_radius)
        else:
            painter.drawRect(r)

        painter.restore()


class EllipseAnnotation(BaseAnnotation):
    def __init__(self):
        super().__init__()
        self.tool_type = ToolType.ELLIPSE

    def draw(self, painter: QPainter, base_image: Optional[QImage] = None):
        r = self.normalized_rect()
        if r.width() < 1 or r.height() < 1:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self.opacity)

        if self.has_shadow:
            painter.setPen(QPen(QColor(0, 0, 0, 90), self.stroke_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(r.translated(2.5, 2.5))

        pen = QPen(self.stroke_qcolor, self.stroke_width, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(QBrush(self.fill_qcolor) if self.fill_qcolor.alpha() > 0 else Qt.BrushStyle.NoBrush)
        painter.drawEllipse(r)
        painter.restore()


class LineAnnotation(BaseAnnotation):
    def __init__(self):
        super().__init__()
        self.tool_type = ToolType.LINE
        self.p1: QPointF = QPointF()
        self.p2: QPointF = QPointF()

    def normalized_rect(self) -> QRectF:
        return QRectF(
            min(self.p1.x(), self.p2.x()),
            min(self.p1.y(), self.p2.y()),
            abs(self.p2.x() - self.p1.x()),
            abs(self.p2.y() - self.p1.y())
        )

    def move_by(self, dx: float, dy: float):
        self.p1 += QPointF(dx, dy)
        self.p2 += QPointF(dx, dy)

    def get_handles(self) -> Dict[int, QPointF]:
        return {
            HANDLE_TL: self.p1,
            HANDLE_BR: self.p2
        }

    def resize_by_handle(self, handle_id: int, new_pt: QPointF):
        if handle_id == HANDLE_TL:
            self.p1 = new_pt
        elif handle_id == HANDLE_BR:
            self.p2 = new_pt

    def hit_test(self, pt: QPointF) -> bool:
        margin = max(8.0, float(self.stroke_width) * 1.5)
        return point_to_segment_distance(pt, self.p1, self.p2) <= margin

    def draw(self, painter: QPainter, base_image: Optional[QImage] = None):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self.opacity)

        if self.has_shadow:
            painter.setPen(QPen(QColor(0, 0, 0, 90), self.stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(self.p1 + QPointF(2, 2), self.p2 + QPointF(2, 2))

        painter.setPen(QPen(self.stroke_qcolor, self.stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(self.p1, self.p2)
        painter.restore()


class ArrowAnnotation(BaseAnnotation):
    def __init__(self):
        super().__init__()
        self.tool_type = ToolType.ARROW
        self.p1: QPointF = QPointF()
        self.p2: QPointF = QPointF()

    def normalized_rect(self) -> QRectF:
        return QRectF(
            min(self.p1.x(), self.p2.x()),
            min(self.p1.y(), self.p2.y()),
            abs(self.p2.x() - self.p1.x()),
            abs(self.p2.y() - self.p1.y())
        )

    def move_by(self, dx: float, dy: float):
        self.p1 += QPointF(dx, dy)
        self.p2 += QPointF(dx, dy)

    def get_handles(self) -> Dict[int, QPointF]:
        return {
            HANDLE_TL: self.p1,
            HANDLE_BR: self.p2
        }

    def resize_by_handle(self, handle_id: int, new_pt: QPointF):
        if handle_id == HANDLE_TL:
            self.p1 = new_pt
        elif handle_id == HANDLE_BR:
            self.p2 = new_pt

    def hit_test(self, pt: QPointF) -> bool:
        margin = max(8.0, float(self.stroke_width) * 1.5)
        return point_to_segment_distance(pt, self.p1, self.p2) <= margin

    def draw(self, painter: QPainter, base_image: Optional[QImage] = None):
        dx = self.p2.x() - self.p1.x()
        dy = self.p2.y() - self.p1.y()
        length = math.hypot(dx, dy)
        if length < 5:
            return

        angle = math.atan2(dy, dx)
        head_len = min(36.0, max(14.0, length * 0.25))
        head_angle = math.pi / 6.0

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self.opacity)

        # Drop shadow
        if self.has_shadow:
            s_offset = QPointF(2.5, 2.5)
            painter.setPen(QPen(QColor(0, 0, 0, 90), self.stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(self.p1 + s_offset, self.p2 + s_offset)
            
            p2_s = self.p2 + s_offset
            a1 = angle + math.pi - head_angle
            a2 = angle + math.pi + head_angle
            pt1 = QPointF(p2_s.x() + head_len * math.cos(a1), p2_s.y() + head_len * math.sin(a1))
            pt2 = QPointF(p2_s.x() + head_len * math.cos(a2), p2_s.y() + head_len * math.sin(a2))
            painter.setBrush(QBrush(QColor(0, 0, 0, 90)))
            painter.drawPolygon(QPolygonF([p2_s, pt1, pt2]))

        # Arrow shaft
        painter.setPen(QPen(self.stroke_qcolor, self.stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(self.p1, self.p2)

        # Arrowhead
        a1 = angle + math.pi - head_angle
        a2 = angle + math.pi + head_angle
        pt_head1 = QPointF(self.p2.x() + head_len * math.cos(a1), self.p2.y() + head_len * math.sin(a1))
        pt_head2 = QPointF(self.p2.x() + head_len * math.cos(a2), self.p2.y() + head_len * math.sin(a2))

        painter.setBrush(QBrush(self.stroke_qcolor))
        painter.drawPolygon(QPolygonF([self.p2, pt_head1, pt_head2]))
        painter.restore()


class FreehandAnnotation(BaseAnnotation):
    def __init__(self, is_highlighter: bool = False):
        super().__init__()
        self.tool_type = ToolType.HIGHLIGHTER if is_highlighter else ToolType.PEN
        self.is_highlighter = is_highlighter
        self.points: List[QPointF] = []

    def add_point(self, pt: QPointF):
        self.points.append(pt)
        if len(self.points) == 1:
            self.rect = QRectF(pt.x() - 5, pt.y() - 5, 10, 10)
        else:
            self.rect = self.rect.united(QRectF(pt.x() - 5, pt.y() - 5, 10, 10))

    def move_by(self, dx: float, dy: float):
        for i in range(len(self.points)):
            self.points[i] += QPointF(dx, dy)
        self.rect.translate(dx, dy)

    def hit_test(self, pt: QPointF) -> bool:
        if len(self.points) < 2:
            return False
        margin = max(8.0, float(self.stroke_width) * 1.5)
        for i in range(len(self.points) - 1):
            if point_to_segment_distance(pt, self.points[i], self.points[i+1]) <= margin:
                return True
        return False

    def draw(self, painter: QPainter, base_image: Optional[QImage] = None):
        if len(self.points) < 2:
            return

        if self.is_highlighter:
            # Single-pass scratch buffer prevents overlapping segment joint alpha accumulation,
            # ensuring crystal-clear text readability even across hundreds of mouse sample points.
            stroke_w = max(8.0, float(self.stroke_width) * 3.5)
            effective_opacity = max(0.03, min(0.65, self.opacity * 0.45))

            min_x = min(pt.x() for pt in self.points)
            max_x = max(pt.x() for pt in self.points)
            min_y = min(pt.y() for pt in self.points)
            max_y = max(pt.y() for pt in self.points)
            pad = int(stroke_w + 6)

            bw = int(max(1, max_x - min_x + pad * 2))
            bh = int(max(1, max_y - min_y + pad * 2))
            tl = QPointF(min_x - pad, min_y - pad)

            scratch = QImage(bw, bh, QImage.Format.Format_ARGB32_Premultiplied)
            scratch.fill(0)

            sp = QPainter(scratch)
            sp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            solid_color = QColor(self.stroke_qcolor)
            solid_color.setAlpha(255)
            sp.setPen(QPen(solid_color, stroke_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            local_pts = [pt - tl for pt in self.points]
            sp.drawPolyline(local_pts)
            sp.end()

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setOpacity(effective_opacity)
            painter.drawImage(tl, scratch)
            painter.restore()
        else:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setOpacity(self.opacity)
            if self.has_shadow:
                painter.setPen(QPen(QColor(0, 0, 0, 80), self.stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                shadow_pts = [p + QPointF(2, 2) for p in self.points]
                painter.drawPolyline(shadow_pts)

            pen = QPen(self.stroke_qcolor, self.stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPolyline(self.points)
            painter.restore()


class TextAnnotation(BaseAnnotation):
    def __init__(self, text: str = "OmniShot Text"):
        super().__init__()
        self.tool_type = ToolType.TEXT
        self.text: str = text
        self.font_family: str = "Noto Sans"
        self.font_size: int = 24
        self.is_bold: bool = True
        self.is_italic: bool = False
        self.is_underline: bool = False
        self.text_color: QColor = QColor("#ffffff")
        self.outline_color: QColor = QColor("#ff0000") # OmniShot red outline
        self.fill_color: QColor = QColor(0, 0, 0, 0)
        self.draw_outline: bool = True

    def calculate_bounds(self, font: QFont) -> QRectF:
        metrics = QPainter().fontMetrics() if not QPainter.fontMetrics else None
        # Approximate size
        tw = len(self.text) * self.font_size * 0.7 + 20
        th = self.font_size * 1.5 + 10
        return QRectF(self.rect.topLeft(), QPointF(self.rect.left() + tw, self.rect.top() + th))

    def draw(self, painter: QPainter, base_image: Optional[QImage] = None):
        if not self.text:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self.opacity)

        font = QFont(self.font_family, self.font_size)
        font.setBold(self.is_bold)
        font.setItalic(self.is_italic)
        font.setUnderline(self.is_underline)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        tw = metrics.horizontalAdvance(self.text) + 16
        th = metrics.height() + 10
        self.rect = QRectF(self.rect.left(), self.rect.top(), tw, th)

        pos = QPointF(self.rect.left() + 8, self.rect.top() + metrics.ascent() + 4)

        # Background fill if enabled
        if self.fill_color.alpha() > 0:
            painter.fillRect(self.rect, self.fill_color)

        path = QPainterPath()
        path.addText(pos, font, self.text)

        # Shadow
        if self.has_shadow:
            painter.strokePath(path, QPen(QColor(0, 0, 0, 140), 6))

        # Thick colorful outline (OmniShot signature style)
        if self.draw_outline:
            outline_pen = QPen(self.outline_color, 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.strokePath(path, outline_pen)

        # Text fill
        painter.fillPath(path, QBrush(self.text_color))
        painter.restore()


class SpeechBalloonAnnotation(BaseAnnotation):
    def __init__(self, text: str = "Comment"):
        super().__init__()
        self.tool_type = ToolType.SPEECH_BALLOON
        self.text: str = text
        self.font_size: int = 14
        self.stroke_color = QColor("#3daee9")
        self.fill_color = QColor(25, 30, 38, 230)
        self.text_color = QColor("#ffffff")

    def draw(self, painter: QPainter, base_image: Optional[QImage] = None):
        r = self.normalized_rect()
        if r.width() < 30 or r.height() < 25:
            r = QRectF(r.left(), r.top(), max(80.0, r.width()), max(40.0, r.height()))
            self.rect = r

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self.opacity)

        # Create speech bubble with pointing tail
        path = QPainterPath()
        body_r = QRectF(r.left(), r.top(), r.width(), r.height() - 14)
        path.addRoundedRect(body_r, 8, 8)

        # Add tail polygon
        tx = r.left() + 20
        ty = body_r.bottom()
        tail = QPolygonF([QPointF(tx, ty), QPointF(tx + 16, ty), QPointF(tx + 4, r.bottom())])
        path.addPolygon(tail)

        # Shadow
        if self.has_shadow:
            painter.fillPath(path.translated(2.5, 2.5), QBrush(QColor(0, 0, 0, 90)))

        # Fill & Border
        painter.fillPath(path, QBrush(self.fill_qcolor))
        painter.strokePath(path, QPen(self.stroke_qcolor, self.stroke_width))

        # Text
        font = QFont("Noto Sans", self.font_size, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(self.text_color)
        painter.drawText(body_r, Qt.AlignmentFlag.AlignCenter, self.text)

        painter.restore()


class StepBadgeAnnotation(BaseAnnotation):
    def __init__(self, number: int = 1):
        super().__init__()
        self.tool_type = ToolType.STEP_BADGE
        self.number: int = number
        self.badge_color: QColor = QColor("#0078d4") # vibrant blue badge
        self.text_color: QColor = QColor("#ffffff")
        self.radius: float = 16.0

    def normalized_rect(self) -> QRectF:
        c = self.rect.center()
        return QRectF(c.x() - self.radius, c.y() - self.radius, self.radius * 2, self.radius * 2)

    def hit_test(self, pt: QPointF) -> bool:
        c = self.rect.center()
        return math.hypot(pt.x() - c.x(), pt.y() - c.y()) <= (self.radius + 6.0)

    def draw(self, painter: QPainter, base_image: Optional[QImage] = None):
        c = self.rect.center()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self.opacity)

        # Drop shadow
        if self.has_shadow:
            painter.setBrush(QBrush(QColor(0, 0, 0, 90)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(c + QPointF(2, 2), self.radius, self.radius)

        # Badge circle fill
        painter.setBrush(QBrush(self.badge_color))
        painter.setPen(QPen(QColor(255, 255, 255), 2.5))
        painter.drawEllipse(c, self.radius, self.radius)

        # Number text
        painter.setPen(self.text_color)
        font = QFont("Noto Sans", int(self.radius * 0.75), QFont.Weight.Bold)
        painter.setFont(font)
        badge_rect = QRectF(c.x() - self.radius, c.y() - self.radius, self.radius * 2, self.radius * 2)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, str(self.number))

        painter.restore()


class RedactAnnotation(BaseAnnotation):
    def __init__(self, is_pixelate: bool = False):
        super().__init__()
        self.tool_type = ToolType.PIXELATE if is_pixelate else ToolType.BLUR
        self.is_pixelate = is_pixelate
        self.block_size: int = 10

    def draw(self, painter: QPainter, base_image: Optional[QImage] = None):
        if not base_image or base_image.isNull():
            return

        r = self.normalized_rect().toRect()
        rx = max(0, r.x())
        ry = max(0, r.y())
        rw = min(base_image.width() - rx, r.width())
        rh = min(base_image.height() - ry, r.height())
        if rw <= 4 or rh <= 4:
            return

        sub = base_image.copy(rx, ry, rw, rh)
        painter.save()
        painter.setOpacity(self.opacity)
        if self.is_pixelate:
            dw = max(1, rw // self.block_size)
            dh = max(1, rh // self.block_size)
            down = sub.scaled(dw, dh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            up = down.scaled(rw, rh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            painter.drawImage(rx, ry, up)
        else:
            # Gaussian / box blur simulation via repeated scaling
            dw = max(1, rw // 8)
            dh = max(1, rh // 8)
            down = sub.scaled(dw, dh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            up = down.scaled(rw, rh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter.drawImage(rx, ry, up)
        painter.restore()


class MagnifyAnnotation(BaseAnnotation):
    def __init__(self):
        super().__init__()
        self.tool_type = ToolType.MAGNIFY
        self.zoom_factor: float = 2.0
        self.stroke_color = QColor("#0078d4")
        self.stroke_width = 3

    def draw(self, painter: QPainter, base_image: Optional[QImage] = None):
        if not base_image or base_image.isNull():
            return

        r = self.normalized_rect()
        if r.width() < 10 or r.height() < 10:
            return

        # Zoom into the center of this area
        cx = r.center().x()
        cy = r.center().y()
        sw = r.width() / self.zoom_factor
        sh = r.height() / self.zoom_factor
        sx = max(0, int(cx - sw / 2))
        sy = max(0, int(cy - sh / 2))

        sub = base_image.copy(sx, sy, int(sw), int(sh))
        zoomed = sub.scaled(int(r.width()), int(r.height()), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self.opacity)

        if self.has_shadow:
            painter.fillRect(r.translated(3, 3), QColor(0, 0, 0, 90))

        painter.drawImage(r.topLeft(), zoomed)
        painter.setPen(QPen(self.stroke_qcolor, self.stroke_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(r)
        painter.restore()


class CropAnnotation(BaseAnnotation):
    def __init__(self):
        super().__init__()
        self.tool_type = ToolType.CROP
        self.stroke_color = QColor("#3daee9")
        self.stroke_width = 2
        self.has_shadow = False

    def draw(self, painter: QPainter, base_image: Optional[QImage] = None):
        r = self.normalized_rect()
        if r.width() < 2 or r.height() < 2:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Dim areas outside crop rect
        if base_image and not base_image.isNull():
            dim = QColor(0, 0, 0, 140)
            img_w = float(base_image.width())
            img_h = float(base_image.height())
            painter.fillRect(QRectF(0, 0, img_w, r.top()), dim)
            painter.fillRect(QRectF(0, r.bottom(), img_w, img_h - r.bottom()), dim)
            painter.fillRect(QRectF(0, r.top(), r.left(), r.height()), dim)
            painter.fillRect(QRectF(r.right(), r.top(), img_w - r.right(), r.height()), dim)

        # Dashed crop border
        pen = QPen(QColor("#3daee9"), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(r)

        # 8 Resize handles
        painter.setPen(QPen(QColor("#3daee9"), 1.5))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        for pt in self.get_handles().values():
            painter.drawRect(QRectF(pt.x() - 4, pt.y() - 4, 8, 8))

        # Dimension pill badge
        dim_text = f"Crop: {int(r.width())} × {int(r.height())} px  |  Enter: Apply  •  Esc: Cancel"
        painter.setFont(QFont("Noto Sans", 11, QFont.Weight.Bold))
        metrics = painter.fontMetrics()
        bw = metrics.horizontalAdvance(dim_text) + 18
        bh = metrics.height() + 8
        bx = r.left() + 6
        by = r.top() - bh - 6
        if by < 10:
            by = r.top() + 6
        badge_rect = QRectF(bx, by, bw, bh)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(20, 24, 30, 230)))
        painter.drawRoundedRect(badge_rect, 5, 5)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, dim_text)

        painter.restore()


class ImageAnnotation(BaseAnnotation):
    """Movable and resizable vector image sticker annotation."""
    def __init__(self, image: QImage, rect: Optional[QRectF] = None):
        super().__init__()
        self.tool_type = ToolType.IMAGE
        self.image = image
        if rect:
            self.rect = rect
        else:
            self.rect = QRectF(0, 0, image.width(), image.height())
        self.has_shadow = True
        self.opacity = 1.0

    def draw(self, painter: QPainter, base_image: Optional[QImage] = None):
        if not self.image or self.image.isNull() or self.rect.isEmpty():
            return
        painter.save()
        r = self.normalized_rect()
        painter.setOpacity(self.opacity)

        if self.has_shadow:
            shadow_rect = r.translated(3, 4)
            painter.fillRect(shadow_rect, QColor(0, 0, 0, 90))

        painter.drawImage(r, self.image)
        painter.restore()


class AnnotationCanvas(QWidget):
    imageChanged = Signal()
    zoomChanged = Signal(float)
    statusMessage = Signal(str)
    selectionChanged = Signal(object) # emits currently selected BaseAnnotation or None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._base_image: Optional[QImage] = None
        self._zoom: float = 1.0

        # Vector annotations
        self.annotations: List[BaseAnnotation] = []
        self.selected_annotation: Optional[BaseAnnotation] = None
        self._history_stack: List[Tuple[List[BaseAnnotation], Optional[QImage]]] = []
        self._redo_stack: List[Tuple[List[BaseAnnotation], Optional[QImage]]] = []
        self._max_history = 35

        # Current tool & properties
        self.current_tool: str = ToolType.POINTER
        self.current_stroke_color: QColor = QColor("#ff0000") # OmniShot red
        self.current_fill_color: QColor = QColor(0, 0, 0, 0) # transparent
        self.current_stroke_width: int = 4
        self.current_opacity: float = 1.0
        self.current_font_size: int = 24
        self.is_bold: bool = True
        self.is_italic: bool = False
        self.is_underline: bool = False
        self.has_shadow: bool = True
        self.step_counter: int = 1

        # Interactive mouse state
        self._dragging = False
        self._active_handle: int = HANDLE_NONE
        self._drag_start_pos = QPointF()
        self._current_mouse_pos = QPointF()
        self._creating_annotation: Optional[BaseAnnotation] = None

        # Determine physical-to-logical display scale factor for 1:1 hardware pixel mapping
        self._display_scale: float = 1.25
        try:
            from ..core.capture import get_capture_backend
            self._display_scale = get_capture_backend().get_display_scale()
        except Exception:
            self._display_scale = 1.25

        # Panning
        self._panning = False
        self._pan_start = QPoint()

    def set_image(self, image: QImage):
        self._base_image = image.copy()
        try:
            from ..core.capture import get_capture_backend
            self._display_scale = get_capture_backend().get_display_scale()
        except Exception:
            pass
        self.annotations.clear()
        self.selected_annotation = None
        self._history_stack.clear()
        self._redo_stack.clear()
        self._push_history()
        self.step_counter = 1
        self._update_canvas_size()
        self.imageChanged.emit()

    def get_image(self) -> Optional[QImage]:
        return self._base_image

    def render_composite_image(self) -> Optional[QImage]:
        """Bakes all vector annotations down onto the base image."""
        if not self._base_image or self._base_image.isNull():
            return None

        result = self._base_image.copy()
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for ann in self.annotations:
            ann.draw(painter, self._base_image)
        painter.end()
        return result

    def _push_history(self):
        # Store snapshot of both vector annotations and base image
        img_copy = self._base_image.copy() if (self._base_image and not self._base_image.isNull()) else None
        anns_copy = [ann.clone() for ann in self.annotations]
        self._history_stack.append((anns_copy, img_copy))
        if len(self._history_stack) > self._max_history:
            self._history_stack.pop(0)
        self._redo_stack.clear()
        self.imageChanged.emit()

    def can_undo(self) -> bool:
        return len(self._history_stack) > 1

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def undo(self):
        if self.can_undo():
            cur = self._history_stack.pop()
            self._redo_stack.append(cur)
            prev_anns, prev_img = self._history_stack[-1]
            self.annotations = [ann.clone() for ann in prev_anns]
            if prev_img is not None:
                self._base_image = prev_img.copy()
            self.selected_annotation = None
            if self.step_counter > 1:
                self.step_counter -= 1
            self._update_canvas_size()
            self.update()
            self.imageChanged.emit()

    def redo(self):
        if self.can_redo():
            nxt = self._redo_stack.pop()
            self._history_stack.append(nxt)
            nxt_anns, nxt_img = nxt
            self.annotations = [ann.clone() for ann in nxt_anns]
            if nxt_img is not None:
                self._base_image = nxt_img.copy()
            self.selected_annotation = None
            self.step_counter += 1
            self._update_canvas_size()
            self.update()
            self.imageChanged.emit()

    def expand_canvas_with_image(
        self,
        pasted_img: QImage,
        direction: str,
        gap: int = 0,
        alignment: str = "center",
        bg_color: Optional[QColor] = None
    ):
        """
        Expands the current canvas with a pasted image in the specified direction:
        'right', 'down', 'left', or 'up'.
        Existing annotations are automatically shifted to stay aligned with the original screenshot.
        """
        if not pasted_img or pasted_img.isNull():
            return
        if not self._base_image or self._base_image.isNull():
            self.set_image(pasted_img)
            return

        bg_color = bg_color or QColor(0, 0, 0, 0)
        gap = max(0, gap)

        w1, h1 = self._base_image.width(), self._base_image.height()
        w2, h2 = pasted_img.width(), pasted_img.height()

        direction = direction.lower()
        if direction in ("right", "east"):
            new_w = w1 + gap + w2
            new_h = max(h1, h2)

            # Vertical alignment
            if alignment == "top":
                y1 = 0
                y2 = 0
            elif alignment == "bottom":
                y1 = new_h - h1
                y2 = new_h - h2
            else:  # center
                y1 = (new_h - h1) // 2
                y2 = (new_h - h2) // 2

            x1 = 0
            x2 = w1 + gap
            ann_dx = 0
            ann_dy = y1

        elif direction in ("left", "west"):
            new_w = w2 + gap + w1
            new_h = max(h1, h2)

            if alignment == "top":
                y1 = 0
                y2 = 0
            elif alignment == "bottom":
                y1 = new_h - h1
                y2 = new_h - h2
            else:  # center
                y1 = (new_h - h1) // 2
                y2 = (new_h - h2) // 2

            x2 = 0
            x1 = w2 + gap
            ann_dx = x1
            ann_dy = y1

        elif direction in ("down", "bottom", "south"):
            new_w = max(w1, w2)
            new_h = h1 + gap + h2

            # Horizontal alignment
            if alignment == "left":
                x1 = 0
                x2 = 0
            elif alignment == "right":
                x1 = new_w - w1
                x2 = new_w - w2
            else:  # center
                x1 = (new_w - w1) // 2
                x2 = (new_w - w2) // 2

            y1 = 0
            y2 = h1 + gap
            ann_dx = x1
            ann_dy = 0

        elif direction in ("up", "top", "north"):
            new_w = max(w1, w2)
            new_h = h2 + gap + h1

            if alignment == "left":
                x1 = 0
                x2 = 0
            elif alignment == "right":
                x1 = new_w - w1
                x2 = new_w - w2
            else:  # center
                x1 = (new_w - w1) // 2
                x2 = (new_w - w2) // 2

            y2 = 0
            y1 = h2 + gap
            ann_dx = x1
            ann_dy = y1
        else:
            return

        self._push_history()

        combined = QImage(new_w, new_h, QImage.Format.Format_ARGB32_Premultiplied)
        combined.fill(bg_color)

        painter = QPainter(combined)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(x1, y1, self._base_image)
        painter.drawImage(x2, y2, pasted_img)
        painter.end()

        # Shift existing annotations to match current image's new placement
        if ann_dx != 0 or ann_dy != 0:
            for ann in self.annotations:
                ann.move_by(float(ann_dx), float(ann_dy))

        self._base_image = combined
        self._update_canvas_size()
        self.update()
        self.imageChanged.emit()

    def insert_image_annotation(self, pasted_img: QImage, pos: Optional[QPointF] = None):
        """Inserts an image onto the canvas as an interactive vector annotation (sticker)."""
        if not pasted_img or pasted_img.isNull() or not self._base_image:
            return

        self._push_history()

        bw, bh = self._base_image.width(), self._base_image.height()
        iw, ih = pasted_img.width(), pasted_img.height()

        # If pasted image is larger than 75% of canvas, proportionally scale initial rect
        max_w = bw * 0.75
        max_h = bh * 0.75
        scale = min(1.0, min(max_w / max(1, iw), max_h / max(1, ih)))
        target_w = max(20.0, iw * scale)
        target_h = max(20.0, ih * scale)

        if pos is not None:
            tl_x = pos.x() - target_w / 2
            tl_y = pos.y() - target_h / 2
        else:
            # Center on base image
            tl_x = (bw - target_w) / 2
            tl_y = (bh - target_h) / 2

        ann = ImageAnnotation(pasted_img, QRectF(tl_x, tl_y, target_w, target_h))
        self.annotations.append(ann)
        self.selected_annotation = ann
        ann.is_selected = True
        self.set_active_tool(ToolType.POINTER)
        self.update()
        self.imageChanged.emit()
        self.selectionChanged.emit(ann)

    def delete_selected(self):
        if self.selected_annotation and self.selected_annotation in self.annotations:
            self._push_history()
            self.annotations.remove(self.selected_annotation)
            self.selected_annotation = None
            self.selectionChanged.emit(None)
            self.update()

    def set_zoom(self, zoom: float):
        zoom = max(0.1, min(5.0, zoom))
        if abs(self._zoom - zoom) > 0.001:
            self._zoom = zoom
            self._update_canvas_size()
            self.update()
            self.zoomChanged.emit(self._zoom)

    def zoom_in(self):
        self.set_zoom(self._zoom * 1.25)

    def zoom_out(self):
        self.set_zoom(self._zoom / 1.25)

    def zoom_reset(self):
        self.set_zoom(1.0)

    def _update_canvas_size(self):
        if not self._base_image:
            self.resize(800, 600)
            return
        scale = self._display_scale if self._display_scale > 0 else 1.25
        w = int((self._base_image.width() / scale) * self._zoom)
        h = int((self._base_image.height() / scale) * self._zoom)
        self.setFixedSize(max(100, w), max(100, h))

    def _to_image_coords(self, pt: QPointF) -> QPointF:
        scale = (self._zoom / self._display_scale) if self._display_scale > 0 else self._zoom
        if scale <= 0:
            return pt
        return QPointF(pt.x() / scale, pt.y() / scale)

    def set_active_tool(self, tool_type: str):
        """Sets the active OmniShot annotation tool and updates canvas state/cursor."""
        self.current_tool = tool_type

        # If switching away from pointer, deselect currently selected annotation
        if tool_type != ToolType.POINTER and self.selected_annotation:
            self.selected_annotation.is_selected = False
            self.selected_annotation = None
            self.selectionChanged.emit(None)

        # Update cursor according to tool
        if tool_type == ToolType.POINTER:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif tool_type == ToolType.TEXT:
            self.setCursor(Qt.CursorShape.IBeamCursor)
        elif tool_type in (ToolType.PEN, ToolType.HIGHLIGHTER, ToolType.LINE, ToolType.ARROW):
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif tool_type == ToolType.CROP:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()

    def apply_crop(self):
        """Applies crop rectangle to base image and shifts annotations."""
        crop_ann = None
        if self._creating_annotation and self._creating_annotation.tool_type == ToolType.CROP:
            crop_ann = self._creating_annotation
        elif self.selected_annotation and self.selected_annotation.tool_type == ToolType.CROP:
            crop_ann = self.selected_annotation
        
        if not crop_ann or not self._base_image or self._base_image.isNull():
            return

        r = crop_ann.normalized_rect().toRect()
        cr = r.intersected(self._base_image.rect())
        if cr.width() < 10 or cr.height() < 10:
            return

        self._push_history()
        self._base_image = self._base_image.copy(cr)
        dx = -float(cr.left())
        dy = -float(cr.top())
        remaining = []
        for ann in self.annotations:
            if ann == crop_ann:
                continue
            ann.move_by(dx, dy)
            if ann.normalized_rect().intersects(QRectF(0, 0, cr.width(), cr.height())):
                remaining.append(ann)
        self.annotations = remaining
        self._creating_annotation = None
        self.selected_annotation = None
        self.set_active_tool(ToolType.POINTER)
        self._update_canvas_size()
        self.update()
        self.imageChanged.emit()
        self.selectionChanged.emit(None)

    def cancel_crop(self):
        """Cancels active crop selection."""
        if self._creating_annotation and self._creating_annotation.tool_type == ToolType.CROP:
            self._creating_annotation = None
            self.set_active_tool(ToolType.POINTER)
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Double click to apply crop or edit text/balloon annotations."""
        if self._creating_annotation and self._creating_annotation.tool_type == ToolType.CROP:
            self.apply_crop()
            return

        img_pos = self._to_image_coords(event.position())
        for ann in reversed(self.annotations):
            if ann.hit_test(img_pos):
                if isinstance(ann, TextAnnotation):
                    text, ok = QInputDialog.getText(self, "Edit Text", "Text:", text=ann.text)
                    if ok and text:
                        self._push_history()
                        ann.text = text
                        self.update()
                        self.imageChanged.emit()
                    return
                elif isinstance(ann, SpeechBalloonAnnotation):
                    text, ok = QInputDialog.getText(self, "Edit Balloon", "Comment:", text=ann.text)
                    if ok and text:
                        self._push_history()
                        ann.text = text
                        self.update()
                        self.imageChanged.emit()
                    return

    def mousePressEvent(self, event: QMouseEvent):
        if not self._base_image:
            return

        img_pos = self._to_image_coords(event.position())
        self._drag_start_pos = img_pos
        self._current_mouse_pos = img_pos

        if event.button() == Qt.MouseButton.MiddleButton or (event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.button() == Qt.MouseButton.LeftButton and self.current_tool == ToolType.POINTER):
            self._panning = True
            self._pan_start = event.pos()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            # Check if interacting with active crop box handles
            if self._creating_annotation and self._creating_annotation.tool_type == ToolType.CROP:
                handle = self._creating_annotation.get_handle_at(img_pos)
                if handle != HANDLE_NONE:
                    self._active_handle = handle
                    self._dragging = True
                    return
                elif self._creating_annotation.normalized_rect().contains(img_pos):
                    return
                else:
                    self.cancel_crop()

            # 1. Pointer Mode: Select or grab handle of an existing annotation
            if self.current_tool == ToolType.POINTER:
                if self.selected_annotation:
                    handle = self.selected_annotation.get_handle_at(img_pos)
                    if handle != HANDLE_NONE:
                        self._active_handle = handle
                        self._dragging = True
                        return

                # Hit test annotations from top to bottom
                clicked_ann = None
                for ann in reversed(self.annotations):
                    if ann.hit_test(img_pos):
                        clicked_ann = ann
                        break

                for ann in self.annotations:
                    ann.is_selected = (ann == clicked_ann)

                self.selected_annotation = clicked_ann
                self.selectionChanged.emit(clicked_ann)

                if clicked_ann:
                    self._dragging = True
                    self._active_handle = HANDLE_NONE
                self.update()
                return

            # 2. Annotation Creation Mode
            self._creating_annotation = self._instantiate_tool(img_pos)
            if self._creating_annotation:
                self._dragging = True

                # Instant one-click tools
                if self.current_tool == ToolType.STEP_BADGE:
                    self._creating_annotation.number = self.step_counter
                    self.step_counter += 1
                    self._push_history()
                    self.annotations.append(self._creating_annotation)
                    self._dragging = False
                    self._creating_annotation = None
                    self.update()
                elif self.current_tool == ToolType.TEXT:
                    text, ok = QInputDialog.getText(self, "Insert Text", "Enter text:")
                    if ok and text:
                        self._creating_annotation.text = text
                        self._push_history()
                        self.annotations.append(self._creating_annotation)
                    self._dragging = False
                    self._creating_annotation = None
                    self.update()
                elif self.current_tool == ToolType.SPEECH_BALLOON:
                    text, ok = QInputDialog.getText(self, "Speech Balloon", "Enter comment:")
                    if ok and text:
                        self._creating_annotation.text = text
                        self._push_history()
                        self.annotations.append(self._creating_annotation)
                    self._dragging = False
                    self._creating_annotation = None
                    self.update()

    def _instantiate_tool(self, pos: QPointF) -> Optional[BaseAnnotation]:
        t = self.current_tool
        ann = None
        if t == ToolType.RECTANGLE:
            ann = RectAnnotation(is_rounded=False)
            ann.rect = QRectF(pos, pos)
        elif t == ToolType.ROUNDED_RECT:
            ann = RectAnnotation(is_rounded=True)
            ann.rect = QRectF(pos, pos)
        elif t == ToolType.ELLIPSE:
            ann = EllipseAnnotation()
            ann.rect = QRectF(pos, pos)
        elif t == ToolType.LINE:
            ann = LineAnnotation()
            ann.p1 = pos
            ann.p2 = pos
        elif t == ToolType.ARROW:
            ann = ArrowAnnotation()
            ann.p1 = pos
            ann.p2 = pos
        elif t in (ToolType.PEN, ToolType.HIGHLIGHTER):
            ann = FreehandAnnotation(is_highlighter=(t == ToolType.HIGHLIGHTER))
            ann.add_point(pos)
        elif t == ToolType.TEXT:
            ann = TextAnnotation()
            ann.rect = QRectF(pos, pos)
            ann.font_size = self.current_font_size
            ann.is_bold = self.is_bold
            ann.is_italic = self.is_italic
            ann.is_underline = self.is_underline
            ann.outline_color = self.current_stroke_color
            ann.text_color = QColor("#ffffff")
        elif t == ToolType.SPEECH_BALLOON:
            ann = SpeechBalloonAnnotation()
            ann.rect = QRectF(pos, pos)
            ann.stroke_color = self.current_stroke_color
        elif t == ToolType.STEP_BADGE:
            ann = StepBadgeAnnotation()
            ann.rect = QRectF(pos, pos)
            ann.badge_color = self.current_stroke_color
        elif t == ToolType.BLUR:
            ann = RedactAnnotation(is_pixelate=False)
            ann.rect = QRectF(pos, pos)
        elif t == ToolType.PIXELATE:
            ann = RedactAnnotation(is_pixelate=True)
            ann.rect = QRectF(pos, pos)
        elif t == ToolType.MAGNIFY:
            ann = MagnifyAnnotation()
            ann.rect = QRectF(pos, pos)
            ann.stroke_color = self.current_stroke_color
        elif t == ToolType.CROP:
            ann = CropAnnotation()
            ann.rect = QRectF(pos, pos)

        if ann:
            ann.stroke_color = self.current_stroke_color
            ann.fill_color = self.current_fill_color
            ann.stroke_width = self.current_stroke_width
            ann.opacity = self.current_opacity
            ann.has_shadow = self.has_shadow

        return ann

    def mouseMoveEvent(self, event: QMouseEvent):
        img_pos = self._to_image_coords(event.position())
        self._current_mouse_pos = img_pos
        self.statusMessage.emit(f"X: {int(img_pos.x())} px  Y: {int(img_pos.y())} px  |  Zoom: {int(self._zoom * 100)}%")

        if self._dragging:
            # Resizing selected annotation via handle
            if self.selected_annotation and self._active_handle != HANDLE_NONE:
                self.selected_annotation.resize_by_handle(self._active_handle, img_pos)
                self.update()
                return

            # Resizing creating crop annotation via handle
            if self._creating_annotation and self._creating_annotation.tool_type == ToolType.CROP and self._active_handle != HANDLE_NONE:
                self._creating_annotation.resize_by_handle(self._active_handle, img_pos)
                self.update()
                return

            # Moving selected annotation
            if self.selected_annotation and self._active_handle == HANDLE_NONE and self.current_tool == ToolType.POINTER:
                dx = img_pos.x() - self._drag_start_pos.x()
                dy = img_pos.y() - self._drag_start_pos.y()
                self.selected_annotation.move_by(dx, dy)
                self._drag_start_pos = img_pos
                self.update()
                return

            # Dragging new creation
            if self._creating_annotation:
                t = self._creating_annotation.tool_type
                if t in (ToolType.PEN, ToolType.HIGHLIGHTER):
                    self._creating_annotation.add_point(img_pos)
                elif t in (ToolType.LINE, ToolType.ARROW):
                    self._creating_annotation.p2 = img_pos
                else:
                    self._creating_annotation.rect = QRectF(
                        min(self._drag_start_pos.x(), img_pos.x()),
                        min(self._drag_start_pos.y(), img_pos.y()),
                        abs(img_pos.x() - self._drag_start_pos.x()),
                        abs(img_pos.y() - self._drag_start_pos.y())
                    )
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            return

        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._active_handle = HANDLE_NONE

            if self._creating_annotation:
                if self._creating_annotation.tool_type == ToolType.CROP:
                    r = self._creating_annotation.normalized_rect()
                    if r.width() < 10 or r.height() < 10:
                        self._creating_annotation = None
                    self.update()
                    return

                r = self._creating_annotation.normalized_rect()
                # Accept if has minimum size or points
                if r.width() > 4 or r.height() > 4 or getattr(self._creating_annotation, "points", []):
                    self._push_history()
                    self.annotations.append(self._creating_annotation)
                    # Automatically select created item
                    for a in self.annotations:
                        a.is_selected = False
                    self._creating_annotation.is_selected = True
                    self.selected_annotation = self._creating_annotation
                    self.selectionChanged.emit(self.selected_annotation)
                self._creating_annotation = None
                self.update()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._creating_annotation and self._creating_annotation.tool_type == ToolType.CROP:
                self.apply_crop()
                return
        elif key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
        elif key == Qt.Key.Key_Escape:
            if self._creating_annotation and self._creating_annotation.tool_type == ToolType.CROP:
                self.cancel_crop()
                return
            if self.selected_annotation:
                self.selected_annotation.is_selected = False
                self.selected_annotation = None
                self.selectionChanged.emit(None)
                self.update()
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Z:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.redo()
                else:
                    self.undo()
            elif key == Qt.Key.Key_Y:
                self.redo()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if not self._base_image or self._base_image.isNull():
            painter.fillRect(self.rect(), QColor("#1e1e1e"))
            painter.setPen(QColor("#7f8c8d"))
            font = QFont("Noto Sans", 14)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No screenshot open\nClick 'New Capture' or 'Scrolling Capture' to start")
            return

        # 1. Dark transparency checkerboard pattern
        self._draw_checkerboard(painter)

        # 2. Draw base screenshot scaled by zoom and mapped 1:1 to hardware pixels
        scale = (self._zoom / self._display_scale) if self._display_scale > 0 else self._zoom

        painter.save()
        painter.scale(scale, scale)

        painter.drawImage(0, 0, self._base_image)

        # 3. Draw placed vector annotations in order
        for ann in self.annotations:
            ann.draw(painter, self._base_image)
            if ann.is_selected:
                ann.draw_selection_outline(painter)

        # 4. Draw actively creating annotation preview
        if self._creating_annotation:
            self._creating_annotation.draw(painter, self._base_image)

        painter.restore()

    def _draw_checkerboard(self, painter: QPainter):
        tile_size = 16
        w = self.width()
        h = self.height()
        c1 = QColor("#1e1e1e")
        c2 = QColor("#282828")
        painter.fillRect(self.rect(), c1)
        for y in range(0, h, tile_size):
            for x in range(0, w, tile_size):
                if ((x // tile_size) + (y // tile_size)) % 2 == 1:
                    painter.fillRect(x, y, tile_size, tile_size, c2)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)
