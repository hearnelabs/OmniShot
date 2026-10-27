"""
OmniShot Region Selection Overlay (Wayland Native)
Features loupe magnifier, selection handles, coordinate badges,
and one-click initiation of either Snapshot or Scrolling Capture.
"""

from typing import Optional
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QFrame
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QMouseEvent, QKeyEvent, QPaintEvent, QImage
)
from PySide6.QtCore import Qt, QPoint, QRect, Signal

class FloatingSnipToolbar(QFrame):
    snapshotClicked = Signal()
    autoScrollClicked = Signal()
    manualScrollClicked = Signal()
    cancelClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(28, 32, 38, 235);
                border: 1px solid #3daee9;
                border-radius: 8px;
                padding: 4px;
            }
            QPushButton {
                background-color: #31363b;
                color: #eff0f1;
                border: 1px solid #474e54;
                border-radius: 5px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3daee9;
                color: #ffffff;
            }
            QPushButton#primaryAction {
                background-color: #1d6fa5;
                border: 1px solid #3daee9;
                color: #ffffff;
            }
            QPushButton#scrollAction {
                background-color: #27ae60;
                border: 1px solid #2ecc71;
                color: #ffffff;
            }
            QPushButton#cancelAction {
                background-color: #7f8c8d;
                border: none;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        self.btn_snapshot = QPushButton("📸 Snapshot (Enter)", self)
        self.btn_snapshot.setObjectName("primaryAction")
        self.btn_snapshot.clicked.connect(self.snapshotClicked.emit)

        self.btn_auto_scroll = QPushButton("📜 Auto-Scroll (A)", self)
        self.btn_auto_scroll.setObjectName("scrollAction")
        self.btn_auto_scroll.clicked.connect(self.autoScrollClicked.emit)

        self.btn_manual_scroll = QPushButton("🖱️ Manual Scroll (M)", self)
        self.btn_manual_scroll.clicked.connect(self.manualScrollClicked.emit)

        self.btn_cancel = QPushButton("✕ Cancel (Esc)", self)
        self.btn_cancel.setObjectName("cancelAction")
        self.btn_cancel.clicked.connect(self.cancelClicked.emit)

        layout.addWidget(self.btn_snapshot)
        layout.addWidget(self.btn_auto_scroll)
        layout.addWidget(self.btn_manual_scroll)
        layout.addWidget(self.btn_cancel)


class SnipSelectionOverlay(QWidget):
    snapshotConfirmed = Signal(QRect)
    scrollCaptureConfirmed = Signal(QRect, bool) # (rect, is_auto)
    overlayCancelled = Signal()

    def __init__(self, background_screen: QImage, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._bg_image: QImage = background_screen
        self._start_pos: Optional[QPoint] = None
        self._current_pos: Optional[QPoint] = None
        self._selected_rect: Optional[QRect] = None
        self._is_selecting = False

        # Floating toolbar
        self._toolbar = FloatingSnipToolbar(self)
        self._toolbar.hide()
        self._toolbar.snapshotClicked.connect(self._on_snapshot_clicked)
        self._toolbar.autoScrollClicked.connect(lambda: self._on_scroll_clicked(True))
        self._toolbar.manualScrollClicked.connect(lambda: self._on_scroll_clicked(False))
        self._toolbar.cancelClicked.connect(self._on_cancel_clicked)

        # Show fullscreen
        if self._bg_image and not self._bg_image.isNull():
            self.resize(self._bg_image.width(), self._bg_image.height())

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._on_cancel_clicked()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if self._selected_rect and self._selected_rect.width() > 10 and self._selected_rect.height() > 10:
                self._on_snapshot_clicked()
        elif key in (Qt.Key.Key_A, Qt.Key.Key_S):
            if self._selected_rect and self._selected_rect.width() > 10 and self._selected_rect.height() > 10:
                self._on_scroll_clicked(True)
        elif key == Qt.Key.Key_M:
            if self._selected_rect and self._selected_rect.width() > 10 and self._selected_rect.height() > 10:
                self._on_scroll_clicked(False)
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicked inside toolbar
            if self._toolbar.isVisible() and self._toolbar.geometry().contains(event.pos()):
                return
            self._is_selecting = True
            self._start_pos = event.pos()
            self._current_pos = event.pos()
            self._selected_rect = None
            self._toolbar.hide()
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        self._current_pos = event.pos()
        if self._is_selecting and self._start_pos:
            self._selected_rect = QRect(
                min(self._start_pos.x(), self._current_pos.x()),
                min(self._start_pos.y(), self._current_pos.y()),
                abs(self._current_pos.x() - self._start_pos.x()),
                abs(self._current_pos.y() - self._start_pos.y())
            )
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_selecting:
            self._is_selecting = False
            if self._start_pos and self._current_pos:
                rect = QRect(
                    min(self._start_pos.x(), self._current_pos.x()),
                    min(self._start_pos.y(), self._current_pos.y()),
                    abs(self._current_pos.x() - self._start_pos.x()),
                    abs(self._current_pos.y() - self._start_pos.y())
                )
                if rect.width() > 20 and rect.height() > 20:
                    self._selected_rect = rect
                    self._position_toolbar(rect)
                else:
                    self._selected_rect = None
                    self._toolbar.hide()
            self.update()

    def _position_toolbar(self, rect: QRect):
        self._toolbar.adjustSize()
        tw = self._toolbar.width()
        th = self._toolbar.height()

        # Center horizontally below selection
        tx = rect.center().x() - tw // 2
        tx = max(10, min(self.width() - tw - 10, tx))

        # Position below, or above if close to bottom
        ty = rect.bottom() + 12
        if ty + th > self.height() - 10:
            ty = rect.top() - th - 12
        ty = max(10, min(self.height() - th - 10, ty))

        self._toolbar.move(tx, ty)
        self._toolbar.show()

    def _on_snapshot_clicked(self):
        if self._selected_rect:
            rect = self._selected_rect
            self.close()
            self.snapshotConfirmed.emit(rect)

    def _on_scroll_clicked(self, is_auto: bool):
        if self._selected_rect:
            rect = self._selected_rect
            self.close()
            self.scrollCaptureConfirmed.emit(rect, is_auto)

    def _on_cancel_clicked(self):
        self.close()
        self.overlayCancelled.emit()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 1. Draw base desktop image
        if self._bg_image and not self._bg_image.isNull():
            painter.drawImage(0, 0, self._bg_image)

        # 2. Draw semi-transparent dimming mask (45% dark)
        dim_color = QColor(0, 0, 0, 110)
        
        if not self._selected_rect or self._selected_rect.isEmpty():
            painter.fillRect(self.rect(), dim_color)
        else:
            # Mask around selection: top, bottom, left, right
            r = self._selected_rect
            # Top
            painter.fillRect(0, 0, self.width(), r.top(), dim_color)
            # Bottom
            painter.fillRect(0, r.bottom() + 1, self.width(), self.height() - r.bottom() - 1, dim_color)
            # Left
            painter.fillRect(0, r.top(), r.left(), r.height() + 1, dim_color)
            # Right
            painter.fillRect(r.right() + 1, r.top(), self.width() - r.right() - 1, r.height() + 1, dim_color)

            # High-contrast selection border
            border_pen = QPen(QColor("#3daee9"), 2, Qt.PenStyle.SolidLine)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)

            # Handles on corners
            handle_size = 8
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(QPen(QColor("#3daee9"), 1))
            corners = [
                QPoint(r.left(), r.top()),
                QPoint(r.right(), r.top()),
                QPoint(r.left(), r.bottom()),
                QPoint(r.right(), r.bottom()),
                QPoint(r.center().x(), r.top()),
                QPoint(r.center().x(), r.bottom()),
                QPoint(r.left(), r.center().y()),
                QPoint(r.right(), r.center().y()),
            ]
            for c in corners:
                painter.drawRect(c.x() - handle_size // 2, c.y() - handle_size // 2, handle_size, handle_size)

            # Dimension badge
            dim_text = f"{r.width()} × {r.height()} px"
            painter.setFont(QFont("Noto Sans", 11, QFont.Weight.Bold))
            metrics = painter.fontMetrics()
            bw = metrics.horizontalAdvance(dim_text) + 16
            bh = metrics.height() + 8
            bx = r.left() + 6
            by = r.top() - bh - 6
            if by < 10:
                by = r.top() + 6
            badge_rect = QRect(bx, by, bw, bh)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(24, 28, 34, 220)))
            painter.drawRoundedRect(badge_rect, 4, 4)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, dim_text)

        # 3. Draw Loupe Magnifier if selecting or mouse moving
        if self._current_pos and (not self._toolbar.isVisible() or self._is_selecting):
            self._draw_loupe(painter, self._current_pos)

    def _draw_loupe(self, painter: QPainter, pos: QPoint):
        if not self._bg_image or self._bg_image.isNull():
            return

        loupe_radius = 55
        zoom_factor = 4
        sample_w = int(loupe_radius * 2 / zoom_factor)
        sample_h = sample_w

        sx = pos.x() - sample_w // 2
        sy = pos.y() - sample_h // 2

        # Extract sub-image
        cropped = self._bg_image.copy(sx, sy, sample_w, sample_h)
        if cropped.isNull():
            return

        # Position loupe offset from cursor
        lx = pos.x() + 30
        ly = pos.y() + 30
        if lx + loupe_radius * 2 > self.width() - 20:
            lx = pos.x() - loupe_radius * 2 - 30
        if ly + loupe_radius * 2 > self.height() - 20:
            ly = pos.y() - loupe_radius * 2 - 30

        center = QPoint(lx + loupe_radius, ly + loupe_radius)

        # Draw circular zoomed crop
        painter.save()
        loupe_path = painter.clipPath()
        painter.setClipRect(QRect(lx, ly, loupe_radius * 2, loupe_radius * 2))
        zoomed = cropped.scaled(loupe_radius * 2, loupe_radius * 2, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        painter.drawImage(lx, ly, zoomed)

        # Loupe border
        painter.setPen(QPen(QColor("#3daee9"), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, loupe_radius, loupe_radius)

        # Crosshair at center
        painter.setPen(QPen(QColor(255, 0, 0, 200), 1))
        painter.drawLine(center.x() - 8, center.y(), center.x() + 8, center.y())
        painter.drawLine(center.x(), center.y() - 8, center.x(), center.y() + 8)

        # Coordinate and color text
        pixel_color = self._bg_image.pixelColor(min(self._bg_image.width() - 1, max(0, pos.x())), min(self._bg_image.height() - 1, max(0, pos.y())))
        coord_text = f"{pos.x()},{pos.y()} {pixel_color.name()}"
        painter.setFont(QFont("Noto Sans", 9))
        painter.fillRect(lx, ly + loupe_radius * 2 + 2, loupe_radius * 2, 18, QColor(0, 0, 0, 180))
        painter.setPen(QColor("#eff0f1"))
        painter.drawText(QRect(lx, ly + loupe_radius * 2 + 2, loupe_radius * 2, 18), Qt.AlignmentFlag.AlignCenter, coord_text)

        painter.restore()
