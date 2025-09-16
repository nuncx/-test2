"""
Transparent debug overlay to visualize detection results (ROI, tiles, monsters).

Usage:
- Instantiate with ConfigManager and EventSystem
- It subscribes to DETECTION_COMPLETED events and repaints accordingly
- Respects config keys: debug_overlay (visibility) and overlay_mode (tile|monster|both)
"""
import logging
import time
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
        # Combat style debug
        self._style: Optional[str] = None
        self._style_counts: Dict[str, int] = {}
        self._style_thr: Dict[str, int] = {}
        # Debug throttle for ROI logging
        self._last_roi_log_ts = 0.0

        # Proxy for cross-thread event delivery
        self._proxy = _OverlayProxy(self)
        self._proxy.detectionUpdated.connect(self._apply_detection_update)

        # Window configuration (set flags individually for compatibility)
        for name in ('FramelessWindowHint', 'Tool', 'WindowStaysOnTopHint', 'X11BypassWindowManagerHint'):
            flag = getattr(Qt, name, None)
            if flag is not None:
                try:
                    self.setWindowFlag(flag, True)
                except Exception:
                    pass
        for attr_name in ('WA_TranslucentBackground', 'WA_TransparentForMouseEvents'):
            attr = getattr(Qt, attr_name, None)
            if attr is not None:
                try:
                    self.setAttribute(attr, True)
                except Exception:
                    pass

        # Cover the full desktop. Note: primary screen only on some setups; good enough as minimal overlay.
        try:
            desk = QApplication.desktop()
            if desk is not None:
                geom = desk.geometry()
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
            # Style debug
            self._style = result.get('combat_style')
            self._style_counts = result.get('combat_style_counts', {}) or {}
            self._style_thr = result.get('combat_style_thresholds', {}) or {}
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
        # It's okay if roi_to_draw is None here; we'll continue to draw other requested overlays

        # Decide what to draw
        mode = self.config_manager.get('overlay_mode', 'tile')

        # Draw ROI if available (primary search/detection ROI)
        if roi_to_draw is not None:
            self._draw_roi(painter, roi_to_draw, offset=(off_x, off_y))

        # Also draw HP ROI outline in a distinct color if present
        hp_roi = self.config_manager.get('hpbar_roi')
        if hp_roi:
            self._draw_roi(painter, hp_roi, color=QColor(255, 220, 0, 220), offset=(off_x, off_y))

        # Draw Combat ROIs if requested via config flags
        try:
            if bool(self.config_manager.get('overlay_show_combat_style_roi', False)):
                s_roi = self.config_manager.get_roi('combat_style_roi')
                if s_roi:
                    self._draw_labeled_roi(
                        painter, s_roi, label="Style ROI",
                        color=QColor(255, 0, 255, 220),  # magenta
                        offset=(off_x, off_y)
                    )
                    # Debug log normalized coords and window bbox
                    self._maybe_log_roi_debug("Style ROI", s_roi)
            if bool(self.config_manager.get('overlay_show_combat_weapon_roi', False)):
                w_roi = self.config_manager.get_roi('combat_weapon_roi')
                if w_roi:
                    self._draw_labeled_roi(
                        painter, w_roi, label="Weapon ROI",
                        color=QColor(0, 200, 255, 220),  # cyan
                        offset=(off_x, off_y)
                    )
                    self._maybe_log_roi_debug("Weapon ROI", w_roi)
        except Exception:
            pass

        # Draw tiles and/or monsters
        if mode in ('tile', 'both'):
            self._draw_tiles(painter, self._tiles, offset=(off_x, off_y))
        if mode in ('monster', 'both'):
            self._draw_monsters(painter, self._monsters, offset=(off_x, off_y))

        # Optional: draw small status indicator for combat
        self._draw_status(painter, self._in_combat, self._hp_seen)

        # Draw counts as text labels near the ROI (if enabled)
        if roi_to_draw is not None and bool(self.config_manager.get('show_overlay_counts', True)):
            try:
                tiles_count = len(self._tiles)
                monsters_count = len(self._monsters)
                self._draw_counts_label(painter, roi_to_draw, tiles_count, monsters_count, offset=(off_x, off_y))
            except Exception:
                pass

        # Draw combat style HUD (if data present)
        try:
            self._draw_style_hud(painter, offset=(off_x, off_y))
        except Exception:
            pass

        painter.end()

    def _draw_roi(self, painter: QPainter, roi: Dict[str, int], color: Optional[QColor] = None, offset: Tuple[int, int] = (0, 0)):
        # Normalize ROI to absolute screen-space if it looks window-relative
        roi = self._normalize_roi_to_absolute(roi)
        pen = QPen(color or QColor(0, 200, 255, 200))  # cyan-ish by default
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QColor(0, 0, 0, 0))
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
        painter.setBrush(QColor(0, 0, 0, 0))
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

    def _draw_labeled_roi(self, painter: QPainter, roi: Dict[str, int], label: str, color: QColor, offset: Tuple[int, int] = (0, 0)):
        # Normalize first to absolute screen coords
        roi = self._normalize_roi_to_absolute(roi)
        # Draw filled, outlined ROI with center crosshair and a small label
        ox, oy = offset
        rect = QRect(roi['left'] - ox, roi['top'] - oy, roi['width'], roi['height'])
        # Fill
        fill = QColor(color)
        fill.setAlpha(60)
        painter.fillRect(rect, fill)
        # Border
        pen = QPen(QColor(color))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawRect(rect)
        # Crosshair
        cx = rect.left() + max(0, rect.width() // 2)
        cy = rect.top() + max(0, rect.height() // 2)
        xhair = QPen(QColor(255, 255, 0, 230))
        xhair.setWidth(2)
        painter.setPen(xhair)
        painter.drawLine(cx - 6, cy, cx + 6, cy)
        painter.drawLine(cx, cy - 6, cx, cy + 6)
        # Label box
        try:
            font = QFont()
            font.setPointSize(9)
            painter.setFont(font)
            metrics = QFontMetrics(font)
            w = metrics.horizontalAdvance(label) + 8
            h = metrics.height() + 4
            lx = rect.left()
            ly = rect.top() - h - 2
            # If above would be off-screen relative to overlay window, place inside
            if ly < 0:
                ly = rect.top() + 2
            painter.setPen(QPen(QColor(255, 255, 255, 220)))
            painter.setBrush(QColor(0, 0, 0, 150))
            painter.drawRect(lx, ly, w, h)
            painter.setPen(QColor(255, 255, 255, 230))
            painter.drawText(lx + 4, ly + h - 4, label)
        except Exception:
            pass

    def _normalize_roi_to_absolute(self, roi: Dict[str, int]) -> Dict[str, int]:
        """Ensure ROI is in absolute screen coordinates. If it appears window-relative, translate by window bbox."""
        try:
            # Accept ROI as dict-like; if dataclass provided, convert
            if hasattr(roi, 'to_dict'):
                roi = roi.to_dict()  # type: ignore[assignment]
            l = int(roi.get('left', 0)); t = int(roi.get('top', 0))
            w = int(roi.get('width', 0)); h = int(roi.get('height', 0))
            mode = str(roi.get('mode', 'absolute')).lower()
            # Use CaptureService to get focused window bbox
            from ...core.detection.capture import CaptureService
            cs = CaptureService()
            title = self.config_manager.get('window_title', '')
            if title:
                try:
                    cs.focus_window(title, retries=1, sleep_s=0.05, exact=False)
                except Exception:
                    pass
            bbox = cs.get_window_bbox()
            # If explicitly relative, always translate
            if mode == 'relative':
                return {
                    'left': bbox['left'] + l,
                    'top': bbox['top'] + t,
                    'width': w,
                    'height': h,
                }
            # Otherwise, heuristic fallback
            within_abs_window = (
                l >= bbox['left'] - 2 and l <= bbox['left'] + bbox['width'] + 2 and
                t >= bbox['top'] - 2 and t <= bbox['top'] + bbox['height'] + 2
            )
            looks_relative = (l < bbox['width'] and t < bbox['height'] and w <= bbox['width'] and h <= bbox['height'])
            if not within_abs_window and looks_relative:
                return {
                    'left': bbox['left'] + l,
                    'top': bbox['top'] + t,
                    'width': w,
                    'height': h,
                }
        except Exception:
            pass
        return roi

    def _maybe_log_roi_debug(self, label: str, roi_like):
        """Log normalized ROI and window bbox at most once every ~2s."""
        try:
            now = time.time()
            if now - self._last_roi_log_ts < 2.0:
                return
            self._last_roi_log_ts = now
            # Normalize ROI
            roi = roi_like.to_dict() if hasattr(roi_like, 'to_dict') else dict(roi_like)
            roi_abs = self._normalize_roi_to_absolute(roi)
            # Get window bbox
            from ...core.detection.capture import CaptureService
            cs = CaptureService()
            title = self.config_manager.get('window_title', '')
            if title:
                try:
                    cs.focus_window(title, retries=1, sleep_s=0.05, exact=False)
                except Exception:
                    pass
            bbox = cs.get_window_bbox()
            logger.debug(f"{label}: roi={roi} -> normalized={roi_abs} | window_bbox={bbox}")
        except Exception:
            pass

    def _draw_style_hud(self, painter: QPainter, offset: Tuple[int, int] = (0, 0)):
        """Draw current combat style and per-style counts/thresholds near the Style ROI if available, else top-left."""
        if self._style is None and not self._style_counts:
            return
        # Compose lines
        style_label = self._style if self._style else 'false'
        melee_txt = f"M:{int(self._style_counts.get('melee', 0))}/{self._style_thr.get('melee', '-')}"
        ranged_txt = f"R:{int(self._style_counts.get('ranged', 0))}/{self._style_thr.get('ranged', '-')}"
        magic_txt = f"Mg:{int(self._style_counts.get('magic', 0))}/{self._style_thr.get('magic', '-')}"
        title = f"Style: {style_label}"
        details = f"{melee_txt}  {ranged_txt}  {magic_txt}"

        # Determine anchor rect: prefer combat_style_roi
        ox, oy = offset
        anchor = self.config_manager.get_roi('combat_style_roi') or None
        if anchor:
            try:
                anchor_abs = self._normalize_roi_to_absolute(anchor)
            except Exception:
                anchor_abs = anchor
            ax = int(anchor_abs['left']) - ox + 8
            ay = int(anchor_abs['top']) - oy + 8
        else:
            ax, ay = 16, 40

        # Measure
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        w = max(metrics.horizontalAdvance(title), metrics.horizontalAdvance(details)) + 12
        h = metrics.height() * 2 + 10

        # Box
        painter.setPen(QPen(QColor(255, 255, 255, 200)))
        painter.setBrush(QColor(0, 0, 0, 140))
        painter.drawRect(ax - 6, ay - 6, w, h)

        # Text
        painter.setPen(QColor(255, 255, 255, 230))
        painter.drawText(ax, ay + metrics.ascent(), title)
        painter.drawText(ax, ay + metrics.height() + metrics.ascent(), details)

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
