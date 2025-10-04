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
        self._last_non_null_roi: Optional[Dict[str, int]] = None  # cache to reduce flicker when result lacks roi
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
            roi_val = result.get('roi')
            if roi_val:
                self._roi = roi_val
                self._last_non_null_roi = roi_val
            else:
                # retain previous non-null ROI to prevent fullscreen flicker
                self._roi = None
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

        # Determine ROI to show: ONLY search ROI (detector ROI). Do not fall back to other ROIs.
        roi_to_draw = self._roi or self._last_non_null_roi
        if roi_to_draw is None:
            roi_to_draw = self.config_manager.get('search_roi') or None
        # It's okay if roi_to_draw is None here; we'll continue to draw other requested overlays

        # Decide what to draw
        mode = self.config_manager.get('overlay_mode', 'tile')

        # Draw ROI if available (primary search/detection ROI)
        if roi_to_draw is not None:
            self._draw_roi(painter, roi_to_draw, offset=(off_x, off_y))

        # Draw HP ROI outline (second allowed ROI)
        hp_roi = self.config_manager.get('hpbar_roi')
        if hp_roi:
            try:
                # Draw filled translucent highlight with dashed border and label
                self._draw_hpbar_highlight(painter, hp_roi, offset=(off_x, off_y))
            except Exception:
                # Fallback simple outline
                self._draw_roi(painter, hp_roi, color=QColor(255, 220, 0, 220), offset=(off_x, off_y))
        # Suppress any other ROI drawings (style/weapon/etc.) to prevent flicker/confusion.

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

        # Draw compact Multi Monster HUD (required, visible, current, action)
        try:
            if bool(self.config_manager.get('show_multi_monster_hud', True)):
                self._draw_mm_hud(painter, offset=(off_x, off_y))
        except Exception:
            pass

        painter.end()

    def _draw_mm_hud(self, painter: QPainter, offset: Tuple[int, int] = (0, 0)):
        """Compact HUD with MM decision context: required, visible, current, action."""
        try:
            hud = self.config_manager.get('multi_monster_last_cycle') or {}
        except Exception:
            hud = {}
        required = hud.get('required_style')
        visible = hud.get('visible_styles') or []
        current = hud.get('current_style')
        action = hud.get('action')
        # Compose a single line HUD
        parts = []
        if required is not None:
            parts.append(f"req:{required}")
        if visible:
            parts.append(f"vis:{','.join(visible)}")
        if current is not None:
            parts.append(f"cur:{current}")
        if action is not None:
            parts.append(f"act:{action}")
        if not parts:
            return
        text = "  ".join(parts)
        # Decide position: top-left inside search ROI if available; else fixed margin
        ox, oy = offset
        roi = self.config_manager.get('search_roi') or {}
        try:
            roi = self._normalize_roi_to_absolute(roi) if roi else None
        except Exception:
            roi = None
        margin = 10
        if roi:
            x = max(roi['left'] - ox + margin, margin)
            y = max(roi['top'] - oy + margin, margin)
        else:
            x, y = margin, margin
        # Draw a small translucent box with monospaced font
        font = QFont("Consolas")
        font.setPointSize(10)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        w = metrics.horizontalAdvance(text) + 12
        h = metrics.height() + 8
        # Use explicit enum class for better stub compatibility
        # Some stubs flag Qt.NoPen; use a zero-width transparent pen instead
        transparent_pen = QPen(QColor(0, 0, 0, 0))
        transparent_pen.setWidth(0)
        painter.setPen(transparent_pen)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.drawRect(x, y, w, h)
        painter.setPen(QColor(220, 255, 220, 240))
        painter.drawText(x + 6, y + h - 6, text)

    def _draw_hpbar_highlight(self, painter: QPainter, roi_like, offset: Tuple[int, int] = (0, 0)):
        """Draw the HP bar ROI with a distinct style and optional last test stats.

        Style:
            - Semi-transparent amber fill
            - Dashed bright border
            - Small label above (or inside if clipped) showing 'HP ROI' and last test metrics
        """
        # Normalize ROI
        roi = roi_like.to_dict() if hasattr(roi_like, 'to_dict') else dict(roi_like)
        roi = self._normalize_roi_to_absolute(roi)
        ox, oy = offset
        rect = QRect(roi['left'] - ox, roi['top'] - oy, roi['width'], roi['height'])

        # Fill
        fill = QColor(255, 200, 0, 55)
        painter.fillRect(rect, fill)

        # Border (solid, wider stroke)
        pen = QPen(QColor(255, 230, 120, 240))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawRect(rect)

        # Build label text with cached last test stats if available
        label_lines: List[str] = ["HP ROI"]
        try:
            last = self.config_manager.get('hpbar_last_test') or {}
            # Expect keys: matches, contours, largest_area, detected
            if last:
                matches = last.get('matches')
                detected = last.get('detected')
                la = last.get('largest_area')
                if matches is not None:
                    label_lines.append(f"px:{int(matches)}")
                if la is not None:
                    label_lines.append(f"A:{int(la)}")
                if detected is not None:
                    label_lines.append("OK" if detected else "--")
        except Exception:
            pass
        label = "  ".join(label_lines)

        # Draw label box
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        w = metrics.horizontalAdvance(label) + 10
        h = metrics.height() + 6
        lx = rect.left()
        ly = rect.top() - h - 2
        if ly < 0:
            ly = rect.top() + 2
        painter.setPen(QPen(QColor(255, 240, 200, 230)))
        painter.setBrush(QColor(20, 15, 0, 160))
        painter.drawRect(lx, ly, w, h)
        painter.setPen(QColor(255, 240, 200, 240))
        painter.drawText(lx + 5, ly + h - 5, label)

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
            # Cache a single window bbox per paint cycle to avoid repeated CaptureService construction
            if not hasattr(self, '_cached_bbox_ts') or (time.time() - getattr(self, '_cached_bbox_ts', 0)) > 0.2:
                from ...core.detection.capture import CaptureService
                cs = CaptureService()
                title = self.config_manager.get('window_title', '')
                if title:
                    try:
                        cs.focus_window(title, retries=1, sleep_s=0.05, exact=False)
                    except Exception:
                        pass
                self._cached_bbox = cs.get_window_bbox()
                self._cached_bbox_ts = time.time()
            bbox = getattr(self, '_cached_bbox', {'left':0,'top':0,'width':0,'height':0})
            # If explicitly relative/percent, translate/scale accordingly
            if mode in ('relative', 'percent'):
                if mode == 'percent':
                    lf = float(l); tf = float(t); wf = float(w); hf = float(h)
                    return {
                        'left': int(bbox['left'] + lf * bbox['width']),
                        'top': int(bbox['top'] + tf * bbox['height']),
                        'width': int(max(1, wf * bbox['width'])),
                        'height': int(max(1, hf * bbox['height'])),
                    }
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
            # Reuse cached bbox if available
            if not hasattr(self, '_cached_bbox'):
                from ...core.detection.capture import CaptureService
                cs = CaptureService()
                title = self.config_manager.get('window_title', '')
                if title:
                    try:
                        cs.focus_window(title, retries=1, sleep_s=0.05, exact=False)
                    except Exception:
                        pass
                self._cached_bbox = cs.get_window_bbox()
                self._cached_bbox_ts = time.time()
            bbox = getattr(self, '_cached_bbox', {'left':0,'top':0,'width':0,'height':0})
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

    def _draw_multi_monster_hud(self, painter: QPainter, offset: Tuple[int, int] = (0, 0)):
        """Draw summary of multi monster mode (last cycle + last test)."""
        try:
            data = self.config_manager.get('multi_monster_last_cycle') or {}
            test = self.config_manager.get('multi_monster_last_test') or {}
            if not data and not test:
                return
            ox, oy = offset
            # Choose anchor below style HUD or top-left fallback
            base_x, base_y = 16, 120
            # Compose lines
            line1 = f"MM: mons={data.get('monsters','-')} act={data.get('action','-')} style={data.get('required_style','-')}"
            vis = data.get('visible_styles', [])
            line2 = f"Visible: {','.join(vis) if vis else '-'} req_vis={data.get('required_visible', False)}"
            if test:
                line3 = f"LastTest row={test.get('row','-')} cnt={test.get('count','-')} style={test.get('style','-')}"
            else:
                line3 = "LastTest: none"
            font = QFont()
            font.setPointSize(9)
            painter.setFont(font)
            metrics = QFontMetrics(font)
            w = max(metrics.horizontalAdvance(line1), metrics.horizontalAdvance(line2), metrics.horizontalAdvance(line3)) + 12
            h = metrics.height() * 3 + 10
            painter.setPen(QPen(QColor(255, 255, 255, 210)))
            painter.setBrush(QColor(0, 0, 0, 140))
            painter.drawRect(base_x - 6, base_y - 6, w, h)
            painter.setPen(QColor(255, 255, 255, 235))
            painter.drawText(base_x, base_y + metrics.ascent(), line1)
            painter.drawText(base_x, base_y + metrics.height() + metrics.ascent(), line2)
            painter.drawText(base_x, base_y + metrics.height()*2 + metrics.ascent(), line3)
        except Exception:
            pass

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
