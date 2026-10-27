"""
OmniShot Annotation Canvas
Supports interactive annotation tools, blur/pixelate obfuscation,
step badges, undo/redo history, zoom, and panning.
"""

import math
from typing import Optional, List, Dict, Any
from PySide6.QtWidgets import QWidget, QInputDialog
from PySide6.QtGui import (
    QImage, QPixmap, QPainter, QPen, QBrush, QColor, QFont,
    QPolygonF, QMouseEvent, QPaintEvent, QWheelEvent
)
from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QRectF, Signal

class AnnotationTool:
    SELECT = "select"
    PEN = "pen"
    HIGHLIGHTER = "highlighter"
    ARROW = "arrow"
    LINE = "line"
    RECTANGLE = "rectangle"
    ELLIPSE = "ellipse"
    NUMBER_BADGE = "number_badge"
    TEXT = "text"
    BLUR = "blur"
    CROP = "crop"

class AnnotationItem:
    def __init__(self, tool: str, color: QColor, stroke_width: int):
        self.tool = tool
        self.color = color
        self.stroke_width = stroke_width
        self.points: List[QPointF] = []
        self.rect: QRectF = QRectF()
        self.text: str = ""
        self.badge_number: int = 1
        self.cached_pixmap: Optional[QPixmap] = None

class AnnotationCanvas(QWidget):
    imageChanged = Signal()
    zoomChanged = Signal(float)
    statusMessage = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._base_image: Optional[QImage] = None
        self._rendered_image: Optional[QImage] = None
        self._zoom: float = 1.0
        
        # Tools state
        self.current_tool: str = AnnotationTool.PEN
        self.current_color: QColor = QColor("#e74c3c")
        self.current_stroke_width: int = 4
        self.current_font_size: int = 16
        self.step_counter: int = 1

        # History for undo/redo
        self._history_stack: List[QImage] = []
        self._redo_stack: List[QImage] = []
        self._max_history = 30

        # Mouse interaction
        self._drawing = False
        self._start_pos = QPointF()
        self._current_pos = QPointF()
        self._current_item: Optional[AnnotationItem] = None

        # Panning
        self._panning = False
        self._pan_start = QPoint()

    def set_image(self, image: QImage):
        """Sets a new base image and clears history."""
        self._base_image = image.copy()
        self._history_stack.clear()
        self._redo_stack.clear()
        self._history_stack.append(self._base_image.copy())
        self.step_counter = 1
        self._update_rendered_canvas()
        self.imageChanged.emit()

    def get_image(self) -> Optional[QImage]:
        return self._base_image

    def can_undo(self) -> bool:
        return len(self._history_stack) > 1

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def undo(self):
        if self.can_undo():
            current = self._history_stack.pop()
            self._redo_stack.append(current)
            self._base_image = self._history_stack[-1].copy()
            if self.step_counter > 1:
                self.step_counter -= 1
            self._update_rendered_canvas()
            self.imageChanged.emit()

    def redo(self):
        if self.can_redo():
            nxt = self._redo_stack.pop()
            self._history_stack.append(nxt)
            self._base_image = nxt.copy()
            self.step_counter += 1
            self._update_rendered_canvas()
            self.imageChanged.emit()

    def _push_history(self):
        if self._base_image is None:
            return
        self._history_stack.append(self._base_image.copy())
        if len(self._history_stack) > self._max_history:
            self._history_stack.pop(0)
        self._redo_stack.clear()
        self.imageChanged.emit()

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
        w = int(self._base_image.width() * self._zoom)
        h = int(self._base_image.height() * self._zoom)
        self.setFixedSize(max(100, w), max(100, h))

    def _update_rendered_canvas(self):
        self._update_canvas_size()
        self.update()

    def _to_image_coords(self, pt: QPointF) -> QPointF:
        if self._zoom <= 0:
            return pt
        return QPointF(pt.x() / self._zoom, pt.y() / self._zoom)

    def mousePressEvent(self, event: QMouseEvent):
        if not self._base_image:
            return

        # Middle button pans
        if event.button() == Qt.MouseButton.MiddleButton or (event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.button() == Qt.MouseButton.LeftButton and self.current_tool == AnnotationTool.SELECT):
            self._panning = True
            self._pan_start = event.pos()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            img_pos = self._to_image_coords(event.position())
            self._drawing = True
            self._start_pos = img_pos
            self._current_pos = img_pos

            item = AnnotationItem(self.current_tool, self.current_color, self.current_stroke_width)
            item.points.append(img_pos)
            self._current_item = item

            # Handle instant click tools
            if self.current_tool == AnnotationTool.NUMBER_BADGE:
                item.badge_number = self.step_counter
                self.step_counter += 1
                self._apply_item_to_base(item)
                self._drawing = False
                self._current_item = None
            elif self.current_tool == AnnotationTool.TEXT:
                self._handle_text_tool(img_pos)
                self._drawing = False
                self._current_item = None

            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self._base_image:
            return

        img_pos = self._to_image_coords(event.position())
        self.statusMessage.emit(f"X: {int(img_pos.x())} px  Y: {int(img_pos.y())} px  |  Zoom: {int(self._zoom * 100)}%")

        if self._drawing and self._current_item:
            self._current_pos = img_pos
            if self.current_tool in (AnnotationTool.PEN, AnnotationTool.HIGHLIGHTER):
                self._current_item.points.append(img_pos)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            return

        if event.button() == Qt.MouseButton.LeftButton and self._drawing and self._current_item:
            self._drawing = False
            img_pos = self._to_image_coords(event.position())
            self._current_pos = img_pos

            # Finalize shape rect
            rect = QRectF(
                min(self._start_pos.x(), self._current_pos.x()),
                min(self._start_pos.y(), self._current_pos.y()),
                abs(self._current_pos.x() - self._start_pos.x()),
                abs(self._current_pos.y() - self._start_pos.y())
            )
            self._current_item.rect = rect

            if self.current_tool == AnnotationTool.CROP:
                self._apply_crop(rect)
            else:
                self._apply_item_to_base(self._current_item)

            self._current_item = None
            self.update()

    def _handle_text_tool(self, pos: QPointF):
        text, ok = QInputDialog.getText(self, "Add Text Annotation", "Enter text:")
        if ok and text:
            item = AnnotationItem(AnnotationTool.TEXT, self.current_color, self.current_stroke_width)
            item.text = text
            item.points.append(pos)
            self._apply_item_to_base(item)

    def _apply_crop(self, rect: QRectF):
        if not self._base_image:
            return
        rx = max(0, int(rect.x()))
        ry = max(0, int(rect.y()))
        rw = min(self._base_image.width() - rx, int(rect.width()))
        rh = min(self._base_image.height() - ry, int(rect.height()))

        if rw > 10 and rh > 10:
            self._push_history()
            cropped = self._base_image.copy(rx, ry, rw, rh)
            self._base_image = cropped
            self._update_rendered_canvas()

    def _apply_item_to_base(self, item: AnnotationItem):
        if not self._base_image:
            return

        self._push_history()
        painter = QPainter(self._base_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._render_item(painter, item)
        painter.end()
        self._update_rendered_canvas()

    def _render_item(self, painter: QPainter, item: AnnotationItem):
        tool = item.tool
        color = item.color
        width = item.stroke_width

        if tool == AnnotationTool.PEN:
            if len(item.points) < 2:
                return
            pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            for i in range(len(item.points) - 1):
                painter.drawLine(item.points[i], item.points[i+1])

        elif tool == AnnotationTool.HIGHLIGHTER:
            if len(item.points) < 2:
                return
            hl_color = QColor(color)
            hl_color.setAlpha(90) # semi-transparent
            pen = QPen(hl_color, width * 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.BevelJoin)
            painter.setPen(pen)
            for i in range(len(item.points) - 1):
                painter.drawLine(item.points[i], item.points[i+1])

        elif tool == AnnotationTool.LINE:
            if len(item.points) >= 1:
                p1 = item.points[0]
                p2 = self._current_pos if self._drawing else (item.points[-1] if len(item.points) > 1 else p1)
                pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.drawLine(p1, p2)

        elif tool == AnnotationTool.ARROW:
            p1 = item.points[0]
            p2 = self._current_pos if self._drawing else (item.points[-1] if len(item.points) > 1 else p1)
            self._draw_arrow(painter, p1, p2, color, width)

        elif tool == AnnotationTool.RECTANGLE:
            rect = item.rect if not self._drawing else QRectF(
                min(self._start_pos.x(), self._current_pos.x()),
                min(self._start_pos.y(), self._current_pos.y()),
                abs(self._current_pos.x() - self._start_pos.x()),
                abs(self._current_pos.y() - self._start_pos.y())
            )
            pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, 4, 4)

        elif tool == AnnotationTool.ELLIPSE:
            rect = item.rect if not self._drawing else QRectF(
                min(self._start_pos.x(), self._current_pos.x()),
                min(self._start_pos.y(), self._current_pos.y()),
                abs(self._current_pos.x() - self._start_pos.x()),
                abs(self._current_pos.y() - self._start_pos.y())
            )
            pen = QPen(color, width, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect)

        elif tool == AnnotationTool.NUMBER_BADGE:
            if not item.points:
                return
            center = item.points[0]
            radius = 16
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(center, radius, radius)
            # White border
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius, radius)
            # Badge number text
            painter.setPen(QColor(255, 255, 255))
            font = QFont("Noto Sans", 11, QFont.Weight.Bold)
            painter.setFont(font)
            text_rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, str(item.badge_number))

        elif tool == AnnotationTool.TEXT:
            if not item.points or not item.text:
                return
            pos = item.points[0]
            font = QFont("Noto Sans", self.current_font_size, QFont.Weight.Bold)
            painter.setFont(font)
            # Background pill for readability
            metrics = painter.fontMetrics()
            tw = metrics.horizontalAdvance(item.text) + 12
            th = metrics.height() + 6
            bg_rect = QRectF(pos.x() - 4, pos.y() - th + 4, tw, th)
            painter.fillRect(bg_rect, QColor(0, 0, 0, 160))
            painter.setPen(color)
            painter.drawText(pos, item.text)

        elif tool == AnnotationTool.BLUR:
            rect = item.rect if not self._drawing else QRectF(
                min(self._start_pos.x(), self._current_pos.x()),
                min(self._start_pos.y(), self._current_pos.y()),
                abs(self._current_pos.x() - self._start_pos.x()),
                abs(self._current_pos.y() - self._start_pos.y())
            )
            if self._base_image and rect.width() > 4 and rect.height() > 4:
                self._draw_pixelate(painter, rect)

    def _draw_pixelate(self, painter: QPainter, rect: QRectF):
        rx = max(0, int(rect.x()))
        ry = max(0, int(rect.y()))
        rw = min(self._base_image.width() - rx, int(rect.width()))
        rh = min(self._base_image.height() - ry, int(rect.height()))
        if rw <= 4 or rh <= 4:
            return

        sub = self._base_image.copy(rx, ry, rw, rh)
        # Pixelate by downsampling by factor of 10 and upsampling
        down_w = max(1, rw // 10)
        down_h = max(1, rh // 10)
        downsampled = sub.scaled(down_w, down_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        pixelated = downsampled.scaled(rw, rh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        painter.drawImage(rx, ry, pixelated)

    def _draw_arrow(self, painter: QPainter, p1: QPointF, p2: QPointF, color: QColor, width: int):
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.hypot(dx, dy)
        if length < 5:
            return

        angle = math.atan2(dy, dx)
        head_len = min(28.0, max(14.0, length * 0.25))
        head_angle = math.pi / 6.0 # 30 degrees

        pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(p1, p2)

        # Arrow head polygon
        a1 = angle + math.pi - head_angle
        a2 = angle + math.pi + head_angle
        pt_head1 = QPointF(p2.x() + head_len * math.cos(a1), p2.y() + head_len * math.sin(a1))
        pt_head2 = QPointF(p2.x() + head_len * math.cos(a2), p2.y() + head_len * math.sin(a2))

        poly = QPolygonF([p2, pt_head1, pt_head2])
        painter.setBrush(QBrush(color))
        painter.drawPolygon(poly)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if not self._base_image:
            # Draw placeholder
            painter.fillRect(self.rect(), QColor("#1e222a"))
            painter.setPen(QColor("#7f8c8d"))
            font = QFont("Noto Sans", 14)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No screenshot captured yet\nClick 'New Screenshot' or 'Scrolling Capture' to start")
            return

        # Background grid / shadow
        painter.fillRect(self.rect(), QColor("#1a1c1e"))

        # Draw scaled base image
        target_rect = QRectF(0, 0, self._base_image.width() * self._zoom, self._base_image.height() * self._zoom)
        source_rect = QRectF(0, 0, self._base_image.width(), self._base_image.height())
        painter.drawImage(target_rect, self._base_image, source_rect)

        # If currently dragging/drawing, overlay active item
        if self._drawing and self._current_item:
            painter.save()
            painter.scale(self._zoom, self._zoom)
            self._render_item(painter, self._current_item)
            painter.restore()

        # If crop tool active and dragging, draw crop guide lines
        if self._drawing and self.current_tool == AnnotationTool.CROP:
            crop_rect = QRectF(
                min(self._start_pos.x(), self._current_pos.x()) * self._zoom,
                min(self._start_pos.y(), self._current_pos.y()) * self._zoom,
                abs(self._current_pos.x() - self._start_pos.x()) * self._zoom,
                abs(self._current_pos.y() - self._start_pos.y()) * self._zoom
            )
            pen = QPen(QColor(255, 255, 255), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(crop_rect)

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
