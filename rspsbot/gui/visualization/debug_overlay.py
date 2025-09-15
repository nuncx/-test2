"""
Transparent debug overlay to visualize detection results (ROI, tiles, monsters).

Usage:
- Instantiate with ConfigManager and EventSystem
- It subscribes to DETECTION_COMPLETED events and repaints accordingly
- Respects config keys: debug_overlay (visibility) and overlay_mode (tile|monster|both)
"""
import logging
from typing import Dict, Any, List, Tuple, Optional

from PyQt5.QtCore import Qt, QRect, QPoint, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics
from PyQt5.QtWidgets import QWidget, QApplication

from ...core.state import EventType

logger = logging.getLogger('rspsbot.gui.visualization.debug_overlay')


class _OverlayProxy(QObject):
    """Thread-safe signal proxy to relay detection events into the GUI thread."""
    detectionUpdated = pyqtSignal(dict)


class DebugOverlayWindow(QWidget):
    """
    A frameless, click-through, always-on-top transparent window that paints
    the current ROI, tile centers, and monster boxes.
    """

    def __init__(self, config_manager, event_system):
        super().__init__(None)
        self.config_manager = config_manager
        self.event_system = event_system

        # Latest detection data cached for painting (screen-space coordinates)
        self._roi: Optional[Dict[str, int]] = None
        self._tiles: List[Tuple[int, int]] = []
        self._monsters: List[Dict[str, Any]] = []
        self._in_combat: bool = False
        self._hp_seen: bool = False
        self._post_combat_remaining_s: float = 0.0

        # Proxy for cross-thread event delivery
        self._proxy = _OverlayProxy(self)
        self._proxy.detectionUpdated.connect(self._apply_detection_update)

        # Window configuration
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # Cover the full desktop. Note: primary screen only on some setups; good enough as minimal overlay.
        try:
            geom = QApplication.desktop().geometry()
            self.setGeometry(geom)
        except Exception:
            pass

        # Subscribe to detection events
        try:
            self.event_system.subscribe(EventType.DETECTION_COMPLETED, self._on_detection_event)
        except Exception as e:
            logger.error(f"Failed to subscribe to detection events: {e}")

        # Periodically sync visibility from config
        self._vis_timer = QTimer(self)
        self._vis_timer.timeout.connect(self._sync_overlay_state)
        self._vis_timer.start(300)

        self._sync_overlay_state()

    # ---- Event handling ----
    def _on_detection_event(self, data: Dict[str, Any]):
        """EventSystem callback (likely from a worker thread). Relay to GUI thread."""
        try:
            # We're interested in the 'result' dict if provided
            result = data.get('result') or {}
            # Emit to GUI thread
            self._proxy.detectionUpdated.emit(result)
        except Exception as e:
            logger.debug(f"Overlay event relay error: {e}")

    def _apply_detection_update(self, result: Dict[str, Any]):
        """Runs on GUI thread. Update cached data and repaint."""
        try:
            self._roi = result.get('roi')
            self._tiles = result.get('tiles', [])
            self._monsters = result.get('monsters', [])
            self._in_combat = bool(result.get('in_combat', False))
            self._hp_seen = bool(result.get('hp_seen', False))
            self._post_combat_remaining_s = float(result.get('post_combat_remaining_s', 0.0) or 0.0)
            self.update()
        except Exception as e:
            logger.error(f"Overlay update error: {e}")

    # ---- Painting ----
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Compute offset so absolute screen coordinates map to local widget space
        try:
            g = self.geometry()
            off_x, off_y = g.left(), g.top()
        except Exception:
            off_x, off_y = 0, 0

        # Determine ROI to show: prefer last detection ROI; fallback to configured ROIs
        roi_to_draw = self._roi
        if roi_to_draw is None:
            # Fallback to search_roi from config
            roi_to_draw = self.config_manager.get('search_roi') or None
            if roi_to_draw is None:
                # As a last resort, show hpbar_roi so there is at least something visible
                roi_to_draw = self.config_manager.get('hpbar_roi') or None
            if roi_to_draw is None:
                return

        # Decide what to draw
        mode = self.config_manager.get('overlay_mode', 'tile')

        # Draw ROI
        self._draw_roi(painter, roi_to_draw, offset=(off_x, off_y))

        # Also draw HP ROI outline in a distinct color if present
        hp_roi = self.config_manager.get('hpbar_roi')
        if hp_roi:
            self._draw_roi(painter, hp_roi, color=QColor(255, 220, 0, 220), offset=(off_x, off_y))

        # Draw tiles and/or monsters
        if mode in ('tile', 'both'):
            self._draw_tiles(painter, self._tiles, offset=(off_x, off_y))
        if mode in ('monster', 'both'):
            self._draw_monsters(painter, self._monsters, offset=(off_x, off_y))

        # Optional: draw small status indicator for combat
        self._draw_status(painter, self._in_combat, self._hp_seen)

        # Draw counts as text labels near the ROI (if enabled)
        if bool(self.config_manager.get('show_overlay_counts', True)):
            try:
                tiles_count = len(self._tiles)
                monsters_count = len(self._monsters)
                self._draw_counts_label(painter, roi_to_draw, tiles_count, monsters_count, offset=(off_x, off_y))
            except Exception:
                pass

        # Draw remaining post-combat delay if any
        try:
            if self._post_combat_remaining_s and self._post_combat_remaining_s > 0.01:
                self._draw_delay_label(painter, roi_to_draw, self._post_combat_remaining_s, offset=(off_x, off_y))
        except Exception:
            pass

        painter.end()

    def _draw_roi(self, painter: QPainter, roi: Dict[str, int], color: Optional[QColor] = None, offset: Tuple[int, int] = (0, 0)):
        pen = QPen(color or QColor(0, 200, 255, 200))  # cyan-ish by default
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        ox, oy = offset
        rect = QRect(roi['left'] - ox, roi['top'] - oy, roi['width'], roi['height'])
        painter.drawRect(rect)

    def _draw_tiles(self, painter: QPainter, tiles: List[Tuple[int, int]], offset: Tuple[int, int] = (0, 0)):
        pen = QPen(QColor(0, 255, 0, 220))  # green
        pen.setWidth(2)
        painter.setPen(pen)
        ox, oy = offset
        for x, y in tiles:
            # small cross
            painter.drawLine(x - ox - 6, y - oy, x - ox + 6, y - oy)
            painter.drawLine(x - ox, y - oy - 6, x - ox, y - oy + 6)

    def _draw_monsters(self, painter: QPainter, monsters: List[Dict[str, Any]], offset: Tuple[int, int] = (0, 0)):
        pen = QPen(QColor(255, 60, 60, 220))  # red
        pen.setWidth(2)
        painter.setPen(pen)
        ox, oy = offset
        for m in monsters:
            x, y = m.get('position', (0, 0))
            w = int(m.get('width', 0))
            h = int(m.get('height', 0))
            if w > 0 and h > 0:
                # Draw bounding box centered on (x,y)
                rect = QRect(int(x - ox - w / 2), int(y - oy - h / 2), w, h)
                painter.drawRect(rect)
            else:
                # Fallback point marker
                painter.drawEllipse(QPoint(x - ox, y - oy), 5, 5)

    def _draw_status(self, painter: QPainter, in_combat: bool, hp_seen: bool):
        # Draw a tiny indicator in the top-left corner: green idle, red combat
        color = QColor(255, 80, 80, 180) if in_combat or hp_seen else QColor(80, 255, 120, 180)
        pen = QPen(color)
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPoint(20, 20), 8, 8)

    def _draw_counts_label(self, painter: QPainter, roi: Dict[str, int], tiles_count: int, monsters_count: int, offset: Tuple[int, int] = (0, 0)):
        # Compose label text
        text = f"Tiles: {tiles_count}  |  Monsters: {monsters_count}"
        # Position: top-left inside ROI with small margin
        ox, oy = offset
        x = roi['left'] - ox + 8
        y = roi['top'] - oy + 20
        # Measure text
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        w = metrics.horizontalAdvance(text) + 10
        h = metrics.height() + 6
        # Background box
        bg_color = QColor(0, 0, 0, 120)
        pen = QPen(QColor(255, 255, 255, 180))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(bg_color)
        painter.drawRect(x - 5, y - h + 5, w, h)
        # Text
        painter.setPen(QColor(255, 255, 255, 230))
        painter.drawText(x, y, text)

    def _draw_delay_label(self, painter: QPainter, roi: Dict[str, int], remaining_s: float, offset: Tuple[int, int] = (0, 0)):
        # Compose label text
        text = f"Wait: {remaining_s:.1f}s"
        # Position: below counts label (top-left inside ROI) with margin
        ox, oy = offset
        x = roi['left'] - ox + 8
        y = roi['top'] - oy + 40  # a bit lower than counts label default 20
        # Measure text
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        w = metrics.horizontalAdvance(text) + 10
        h = metrics.height() + 6
        # Background box with amber color to stand out
        bg_color = QColor(60, 40, 0, 140)
        pen = QPen(QColor(255, 220, 120, 220))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(bg_color)
        painter.drawRect(x - 5, y - h + 5, w, h)
        # Text
        painter.setPen(QColor(255, 220, 120, 240))
        painter.drawText(x, y, text)

    # ---- Visibility / lifecycle ----
    def _sync_overlay_state(self):
        enabled = bool(self.config_manager.get('debug_overlay', False))
        if enabled and not self.isVisible():
            self.show()
        elif not enabled and self.isVisible():
            self.hide()
        # Follow window if enabled
        try:
            if self.isVisible() and bool(self.config_manager.get('overlay_follow_window', False)):
                from ...core.detection.capture import CaptureService
                cs = CaptureService()
                title = self.config_manager.get('window_title', '')
                if title:
                    try:
                        cs.focus_window(title, retries=1, sleep_s=0.05, exact=False)
                    except Exception:
                        pass
                clip_to_roi = bool(self.config_manager.get('overlay_clip_to_roi', False))
                if clip_to_roi:
                    roi = self.config_manager.get('search_roi') or None
                    if roi:
                        self.setGeometry(roi['left'], roi['top'], roi['width'], roi['height'])
                    else:
                        # Fallback to full window if ROI not set
                        bbox = cs.get_window_bbox()
                        self.setGeometry(bbox['left'], bbox['top'], bbox['width'], bbox['height'])
                else:
                    bbox = cs.get_window_bbox()
                    self.setGeometry(bbox['left'], bbox['top'], bbox['width'], bbox['height'])
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            self.event_system.unsubscribe(EventType.DETECTION_COMPLETED, self._on_detection_event)
        except Exception:
            pass
        super().closeEvent(event)
