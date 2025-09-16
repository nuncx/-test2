"""
Overlay components for on-screen visualization.

Provides a transparent, always-on-top overlay that can draw the Aggro Bar ROI
and a computed click point to help tune detection settings.
"""
import logging
from typing import Optional, Tuple

from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import QGuiApplication


logger = logging.getLogger('rspsbot.gui.components.overlay')


class AggroOverlay(QWidget):
    """
    Transparent, click-through overlay that draws:
    - Aggro Bar ROI rectangle
    - Computed click point (centroid of combined aggro bar mask)

    The overlay auto-refreshes its content periodically using the detector.
    """

    def __init__(self, config_manager, bot_controller, refresh_ms: int = 500, compute_point: bool = True, roi_key: Optional[str] = None):
        super().__init__(None)
        self._config = config_manager
        self._controller = bot_controller
        self._enabled = False
        self._compute_point = bool(compute_point)
        self._roi_key: Optional[str] = roi_key
        self._roi = None  # ROI object with left, top, width, height
        self._point: Optional[Tuple[int, int]] = None  # absolute screen coordinates

        # Window flags: frameless, always on top, tool window to avoid taskbar
        try:
            # PyQt6 style
            flags = (
                getattr(Qt, 'WindowType').FramelessWindowHint
                | getattr(Qt, 'WindowType').WindowStaysOnTopHint
                | getattr(Qt, 'WindowType').Tool
            )
        except Exception:
            # PyQt5 style
            flags = (
                getattr(Qt, 'FramelessWindowHint')
                | getattr(Qt, 'WindowStaysOnTopHint')
                | getattr(Qt, 'Tool')
            )
        self.setWindowFlags(flags)
        # Transparent background and input pass-through
        try:
            wa = getattr(Qt, 'WidgetAttribute')
            self.setAttribute(wa.WA_TranslucentBackground, True)
            self.setAttribute(wa.WA_TransparentForMouseEvents, True)
        except Exception:
            # PyQt5 constants
            try:
                self.setAttribute(getattr(Qt, 'WA_TranslucentBackground'), True)
                self.setAttribute(getattr(Qt, 'WA_TransparentForMouseEvents'), True)
            except Exception:
                pass

        # Resize to cover the virtual desktop. Prefer Qt desktop().geometry() to match Qt's logical coordinates
        # used by our ROI pickers and UI, then fallback to MSS if needed.
        got_geom = False
        try:
            desk = QApplication.desktop()
            # geometry() of the desktop is the virtual bounding rect across all monitors
            geom = desk.geometry() if desk is not None else None
            if geom is not None:
                self._overlay_left = int(geom.left())
                self._overlay_top = int(geom.top())
                self._overlay_width = int(geom.width())
                self._overlay_height = int(geom.height())
                got_geom = True
        except Exception:
            got_geom = False
        if not got_geom:
            try:
                import mss  # type: ignore
                with mss.mss() as sct:
                    mon0 = sct.monitors[0]  # virtual screen bbox across all monitors
                    self._overlay_left = int(mon0.get('left', 0))
                    self._overlay_top = int(mon0.get('top', 0))
                    self._overlay_width = int(mon0.get('width', 1920))
                    self._overlay_height = int(mon0.get('height', 1080))
                    got_geom = True
            except Exception:
                got_geom = False
        if not got_geom:
            # Fallback to common 1920x1080 primary screen at (0,0)
            self._overlay_left = 0
            self._overlay_top = 0
            self._overlay_width = 1920
            self._overlay_height = 1080
        self.setGeometry(
            self._overlay_left,
            self._overlay_top,
            self._overlay_width,
            self._overlay_height,
        )

        # Auto refresh timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_refresh)
        self._timer.start(max(100, int(refresh_ms)))
        # Blink state to make tiny ROIs stand out
        self._blink = False

    # ----------------------- Public API -----------------------
    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)
        if self._enabled:
            try:
                # Avoid stealing focus but ensure visibility
                self.setAttribute(getattr(Qt, 'WA_ShowWithoutActivating'), True)
            except Exception:
                pass
            self.show()
            try:
                self.raise_()
            except Exception:
                pass
        else:
            self.hide()

    def set_roi(self, roi):
        """Set current ROI to draw. Accepts ROI dataclass or dict."""
        self._roi = roi
        self.update()

    def set_click_point(self, point: Optional[Tuple[int, int]]):
        self._point = point
        self.update()

    # ----------------------- Internals ------------------------
    def _screen_to_overlay(self, x: int, y: int) -> Tuple[int, int]:
        return x - self._overlay_left, y - self._overlay_top

    def _on_refresh(self):
        if not self._enabled:
            return
        # Toggle blink each refresh for visibility
        self._blink = not self._blink
        # Update/sync ROI from config if a key is provided (keeps overlay in sync with UI changes)
        if self._config is not None:
            try:
                key = self._roi_key or 'instance_aggro_bar_roi'
                roi = self._config.get_roi(key)
                # Fallbacks to ensure something visible if the requested ROI isn't set yet
                if roi is None:
                    # Try common alternatives depending on context
                    for alt in (
                        'combat_style_roi',
                        'combat_weapon_roi',
                        'instance_aggro_bar_roi',
                        'search_roi',
                    ):
                        try:
                            roi = self._config.get_roi(alt)
                        except Exception:
                            roi = None
                        if roi is not None:
                            break
                if roi is not None:
                    self._roi = roi
            except Exception:
                pass
        # Compute click point (centroid) using detector if available
        if self._compute_point:
            try:
                det = None
                if (
                    self._controller is not None
                    and hasattr(self._controller, 'detection_engine')
                    and self._controller.detection_engine is not None
                ):
                    det = self._controller.detection_engine.instance_only_detector
                if det is not None and hasattr(det, 'compute_aggro_bar_centroid'):
                    self._point = det.compute_aggro_bar_centroid()
            except Exception as e:
                logger.debug(f"overlay refresh calc error: {e}")
        self.update()

    def paintEvent(self, event):
        if not self._enabled:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Draw ROI rectangle
        roi = self._roi
        if roi:
            try:
                left = int(getattr(roi, 'left', roi.get('left')))
                top = int(getattr(roi, 'top', roi.get('top')))
                width = int(getattr(roi, 'width', roi.get('width')))
                height = int(getattr(roi, 'height', roi.get('height')))
                x0, y0 = self._screen_to_overlay(left, top)
                rect = QRect(x0, y0, width, height)
                # Translucent fill to make even tiny ROIs visible
                painter.fillRect(rect, QColor(255, 0, 0, 60))
                # Thick, blinking border (red/cyan) to improve visibility
                border_color = QColor(255, 0, 0, 230) if self._blink else QColor(0, 255, 255, 230)
                painter.setPen(QPen(border_color, 3))
                painter.drawRect(rect)
                # Center crosshair for orientation
                cx = x0 + max(0, width // 2)
                cy = y0 + max(0, height // 2)
                painter.setPen(QPen(QColor(255, 255, 0, 230), 2))
                size = 6
                painter.drawLine(cx - size, cy, cx + size, cy)
                painter.drawLine(cx, cy - size, cx, cy + size)
            except Exception:
                pass

        # Draw click point crosshair
        pt = self._point
        if pt and isinstance(pt, tuple) and len(pt) == 2:
            try:
                x, y = int(pt[0]), int(pt[1])
                x, y = self._screen_to_overlay(x, y)
                painter.setPen(QPen(QColor(0, 255, 0, 220), 2))
                size = 8
                painter.drawLine(x - size, y, x + size, y)
                painter.drawLine(x, y - size, x, y + size)
            except Exception:
                pass

        painter.end()
