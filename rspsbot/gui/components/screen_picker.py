"""
Reusable dialogs to pick points, rectangles (ROI), and colors from a live screenshot.
Adds zoomable screenshot-based pickers that capture the focused client window.
"""
from PyQt5.QtCore import Qt, QRect, QPoint, QRectF
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QPixmap, QGuiApplication, QCursor, QImage
)
from PyQt5.QtWidgets import (
    QDialog, QLabel, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsRectItem, QVBoxLayout, QHBoxLayout, QPushButton, QDialogButtonBox, QWidget
)
from typing import Tuple
import numpy as np
import cv2

try:
    # Optional import inside module; used by zoom pickers
    from ...core.detection.capture import CaptureService
except Exception:  # pragma: no cover
    CaptureService = None


def grab_full_screenshot() -> QPixmap:
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return QPixmap()
    # Grab the entire virtual desktop
    return screen.grabWindow(0)


class BaseOverlayDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowState(self.windowState() | Qt.WindowFullScreen)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.screenshot = grab_full_screenshot()
        self.bg_label = QLabel(self)
        self.bg_label.setPixmap(self.screenshot)
        self.bg_label.setGeometry(0, 0, self.screenshot.width(), self.screenshot.height())


class PointPickerDialog(BaseOverlayDialog):
    """Full-screen overlay to select a single point."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_point = None
        self.setCursor(QCursor(Qt.CrossCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected_point = event.globalPos()
            self.accept()
        elif event.button() == Qt.RightButton:
            self.reject()


class RoiPickerDialog(BaseOverlayDialog):
    """Full-screen overlay to select a rectangle by click-drag."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.origin = None
        self.current = None
        self.result_rect = None
        self.setCursor(QCursor(Qt.CrossCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.globalPos()
            self.current = self.origin
            self.update()
        elif event.button() == Qt.RightButton:
            self.reject()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.current = event.globalPos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.origin is not None:
            rect = QRect(self.origin, event.globalPos()).normalized()
            self.result_rect = rect
            self.accept()

    def paintEvent(self, event):
        if self.origin is None or self.current is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # Dim overlay
        painter.fillRect(self.rect(), QBrush(QColor(0, 0, 0, 80)))
        # Draw selection rect
        pen = QPen(QColor(0, 200, 255), 2, Qt.SolidLine)
        painter.setPen(pen)
        painter.setBrush(QBrush(Qt.NoBrush))
        rect = QRect(self.mapFromGlobal(self.origin), self.mapFromGlobal(self.current)).normalized()
        painter.drawRect(rect)
        painter.end()


class ColorPickerDialog(BaseOverlayDialog):
    """Full-screen overlay to pick a color at the clicked pixel."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_color = None
        self.setCursor(QCursor(Qt.CrossCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Map to screenshot coordinates and sample color
            pos = event.pos()  # position in widget coordinates
            if not self.screenshot.isNull():
                img = self.screenshot.toImage()
                x = max(0, min(img.width() - 1, pos.x()))
                y = max(0, min(img.height() - 1, pos.y()))
                qcolor = img.pixelColor(x, y)
                self.selected_color = (qcolor.red(), qcolor.green(), qcolor.blue())
            self.accept()
        elif event.button() == Qt.RightButton:
            self.reject()


# ---------- Zoomable pickers based on focused window screenshot ----------

def _np_to_qpixmap(bgr: np.ndarray) -> QPixmap:
    if bgr is None or bgr.size == 0:
        return QPixmap()
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    bytes_per_line = ch * w
    qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def grab_focused_window_pixmap(config_manager=None) -> Tuple[QPixmap, dict]:
    """Capture the focused client (or configured window) and return QPixmap and bbox.
    If CaptureService is unavailable, fall back to primary screen.
    """
    if CaptureService is None:
        pm = grab_full_screenshot()
        return pm, {"left": 0, "top": 0, "width": pm.width(), "height": pm.height()}
    cs = CaptureService()
    # Try to focus configured window if present
    try:
        if config_manager is not None:
            title = config_manager.get('window_title', '')
            if title:
                cs.focus_window(title, retries=1, sleep_s=0.1, exact=False)
    except Exception:
        pass
    bbox = cs.get_window_bbox()
    img = cs.capture(bbox)
    pm = _np_to_qpixmap(img)
    return pm, bbox


class ZoomImageView(QGraphicsView):
    """Zoomable/pannable image view with optional selection rectangle."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pix_item = None
        self._rect_item = None
        self._dragging_rect = False
        self._origin_scene = None
        self._scale = 1.0
        self.setDragMode(QGraphicsView.NoDrag)

    def set_image(self, pixmap: QPixmap):
        self._scene.clear()
        self._pix_item = QGraphicsPixmapItem(pixmap)
        self._scene.addItem(self._pix_item)
        self._rect_item = QGraphicsRectItem()
        pen = QPen(QColor(0, 200, 255))
        pen.setWidth(2)
        self._rect_item.setPen(pen)
        self._rect_item.setBrush(QBrush(Qt.NoBrush))
        self._rect_item.setVisible(False)
        self._scene.addItem(self._rect_item)
        self.fitInView(self._pix_item, Qt.KeepAspectRatio)
        self._scale = 1.0

    def wheelEvent(self, event):
        if self._pix_item is None:
            return
        angle = event.angleDelta().y()
        factor = 1.15 if angle > 0 else 1/1.15
        self._scale *= factor
        self._scale = max(0.1, min(8.0, self._scale))
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._pix_item is not None:
            self._dragging_rect = True
            self._origin_scene = self.mapToScene(event.pos())
            self._rect_item.setRect(QRectF(self._origin_scene, self._origin_scene))
            self._rect_item.setVisible(True)
        elif event.button() == Qt.RightButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging_rect and self._origin_scene is not None:
            current = self.mapToScene(event.pos())
            rect = QRectF(self._origin_scene, current).normalized()
            self._rect_item.setRect(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging_rect:
            self._dragging_rect = False
        elif event.button() == Qt.RightButton:
            self.setDragMode(QGraphicsView.NoDrag)
            super().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)

    def selected_rect_in_image(self) -> QRect:
        if self._rect_item is None or not self._rect_item.isVisible():
            return QRect()
        rectf = self._rect_item.rect().normalized()
        # Clamp to image bounds
        img_rect = self._pix_item.boundingRect()
        rectf = rectf.intersected(img_rect)
        return QRect(int(rectf.x()), int(rectf.y()), int(rectf.width()), int(rectf.height()))


class ZoomRoiPickerDialog(QDialog):
    """Dialog to select ROI on a zoomable screenshot of the focused client."""
    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pick ROI from Screenshot")
        self.resize(900, 600)
        self._config = config_manager
        self.result_rect = None  # global QRect

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.zoom_in_btn = QPushButton("+")
        self.zoom_out_btn = QPushButton("-")
        self.info_label = QLabel("Left-drag to select. Right-drag to pan. Wheel to zoom.")
        self.info_label.setStyleSheet("color: #666")
        top.addWidget(self.zoom_in_btn)
        top.addWidget(self.zoom_out_btn)
        top.addStretch()
        top.addWidget(self.info_label)
        layout.addLayout(top)

        self.view = ZoomImageView()
        layout.addWidget(self.view)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        self.zoom_in_btn.clicked.connect(lambda: self.view.scale(1.15, 1.15))
        self.zoom_out_btn.clicked.connect(lambda: self.view.scale(1/1.15, 1/1.15))

        # Load screenshot
        pm, self._bbox = grab_focused_window_pixmap(self._config)
        self.view.set_image(pm)

    def _on_accept(self):
        rect_img = self.view.selected_rect_in_image()
        if rect_img.isNull():
            self.reject()
            return
        # Map image rect to global using window bbox
        left = self._bbox.get('left', 0) + rect_img.left()
        top = self._bbox.get('top', 0) + rect_img.top()
        self.result_rect = QRect(left, top, rect_img.width(), rect_img.height())
        self.accept()


class ZoomColorPickerDialog(QDialog):
    """Dialog to pick a color from a zoomable screenshot of the focused client."""
    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pick Color from Screenshot")
        self.resize(900, 600)
        self._config = config_manager
        self.selected_color = None  # (r,g,b)

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.zoom_in_btn = QPushButton("+")
        self.zoom_out_btn = QPushButton("-")
        self.preview = QLabel(" ")
        self.preview.setFixedSize(40, 20)
        self.preview.setStyleSheet("border: 1px solid #888;")
        self.info_label = QLabel("Click a pixel to select. Right-drag to pan. Wheel to zoom.")
        self.info_label.setStyleSheet("color: #666")
        top.addWidget(self.zoom_in_btn)
        top.addWidget(self.zoom_out_btn)
        top.addStretch()
        top.addWidget(QLabel("Preview:"))
        top.addWidget(self.preview)
        top.addStretch()
        top.addWidget(self.info_label)
        layout.addLayout(top)

        self.view = ZoomImageView()
        layout.addWidget(self.view)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.zoom_in_btn.clicked.connect(lambda: self.view.scale(1.15, 1.15))
        self.zoom_out_btn.clicked.connect(lambda: self.view.scale(1/1.15, 1/1.15))

        # Load screenshot and hook clicks
        pm, self._bbox = grab_focused_window_pixmap(self._config)
        self.view.set_image(pm)
        # Install event filter on the view to catch clicks in scene
        self.view.viewport().installEventFilter(self)
        self._image = pm.toImage()

    def eventFilter(self, obj, event):
        if obj is self.view.viewport() and event.type() == event.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                scene_pos = self.view.mapToScene(event.pos())
                x = int(scene_pos.x())
                y = int(scene_pos.y())
                # Bounds check
                x = max(0, min(self._image.width() - 1, x))
                y = max(0, min(self._image.height() - 1, y))
                qc = self._image.pixelColor(x, y)
                self.selected_color = (qc.red(), qc.green(), qc.blue())
                self.preview.setStyleSheet(f"background: rgb({self.selected_color[0]}, {self.selected_color[1]}, {self.selected_color[2]}); border: 1px solid #888;")
                return True
        return super().eventFilter(obj, event)


class ZoomPointPickerDialog(QDialog):
    """Dialog to pick a single point from a zoomable screenshot of the focused client.
    Returns global coordinates mapped using CaptureService bbox.
    """
    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pick Point from Screenshot")
        self.resize(900, 600)
        self._config = config_manager
        self.selected_point = None  # (x, y) global

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.zoom_in_btn = QPushButton("+")
        self.zoom_out_btn = QPushButton("-")
        self.info_label = QLabel("Click to select point. Right-drag to pan. Wheel to zoom.")
        self.info_label.setStyleSheet("color: #666")
        top.addWidget(self.zoom_in_btn)
        top.addWidget(self.zoom_out_btn)
        top.addStretch()
        top.addWidget(self.info_label)
        layout.addLayout(top)

        self.view = ZoomImageView()
        layout.addWidget(self.view)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        self.zoom_in_btn.clicked.connect(lambda: self.view.scale(1.15, 1.15))
        self.zoom_out_btn.clicked.connect(lambda: self.view.scale(1/1.15, 1/1.15))

        # Load screenshot and hook clicks
        pm, self._bbox = grab_focused_window_pixmap(self._config)
        self.view.set_image(pm)
        self.view.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.view.viewport() and event.type() == event.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                scene_pos = self.view.mapToScene(event.pos())
                x = int(scene_pos.x())
                y = int(scene_pos.y())
                # Map to global via bbox
                gx = self._bbox.get('left', 0) + max(0, x)
                gy = self._bbox.get('top', 0) + max(0, y)
                self.selected_point = (gx, gy)
                # Visual feedback: small rect
                return True
        return super().eventFilter(obj, event)

    def _on_accept(self):
        if not self.selected_point:
            self.reject()
            return
        self.accept()
