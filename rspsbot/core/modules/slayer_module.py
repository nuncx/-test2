"""
Slayer Mode module: orchestrates a tile->monster->HP verified combat loop with a fallback Slayer task sequence.

Responsibilities
- Read settings from ConfigManager (colors, hotkeys, coords)
- Use DetectionEngine to run ROI -> tiles -> monsters -> HP
- Attack nearest-to-tile monster when not in combat
- If after attack no HP is seen within timeout, execute Slayer task sequence:
  ctrl+s -> click task1 -> click task2 -> ctrl+s -> click slayer monster -> click teleport
- All UI clicks use window-relative storage, converted to absolute at click-time, bypassing guard/clamp

This module is designed to be invoked from a GUI timer loop.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import time
import logging

from ..config import ConfigManager
from ..detection.detector import DetectionEngine
from ..state import EventType
from ..action.mouse_controller import MouseController
from ..action.keyboard_controller import KeyboardController

logger = logging.getLogger('rspsbot.core.modules.slayer')


class SlayerModule:
    def __init__(self, config: ConfigManager, engine: DetectionEngine, mouse: MouseController, keyboard: KeyboardController, event_system):
        self.config = config
        self.engine = engine
        self.mouse = mouse
        self.keyboard = keyboard
        self.events = event_system
        self._last_attack_ts: float = 0.0
        self._hp_verify_deadline: float = 0.0
        self._last_click_pos: Optional[Tuple[int, int]] = None

    def update_config(self) -> None:
        """Sync dynamic settings for Slayer mode before each cycle.

        - If 'slayer_monster_colors' is configured, inject it into the generic
          'monster_colors' list so the detection engine uses these 8 task-specific
          colors while Slayer mode is running.
        - Ensure Multi-Monster mode is disabled to avoid overriding color sources.
        """
        try:
            colors = self.config.get('slayer_monster_colors', []) or []
            if isinstance(colors, list) and colors:
                # Normalize entries to dicts expected by ConfigManager ColorSpec loader
                norm: List[dict] = []
                for cs in colors:
                    if isinstance(cs, dict):
                        norm.append(cs)
                    else:
                        try:
                            norm.append(getattr(cs, '__dict__', {}))
                        except Exception:
                            continue
                if norm:
                    self.config.set('monster_colors', norm)
                    # Explicitly disable MM for Slayer dedicated flow
                    self.config.set('mm_enabled', False)
        except Exception:
            pass

    def start(self) -> None:
        self._last_attack_ts = 0.0
        self._hp_verify_deadline = 0.0
        self._last_click_pos = None
        logger.info("SlayerModule started")

    def stop(self) -> None:
        logger.info("SlayerModule stopped")

    # --- utilities ---
    def _to_absolute(self, x: int, y: int) -> Tuple[int, int]:
        """Convert window-relative (if so) to absolute screen coordinates."""
        try:
            from ..detection.capture import CaptureService  # lazy import
            bbox = CaptureService().get_window_bbox()
            if 0 <= int(x) <= int(bbox.get('width', 0)) and 0 <= int(y) <= int(bbox.get('height', 0)):
                return int(bbox.get('left', 0)) + int(x), int(bbox.get('top', 0)) + int(y)
        except Exception:
            pass
        return int(x), int(y)

    def _click_coord_key(self, key: str, label: str) -> bool:
        c = self.config.get_coordinate(key)
        if not c:
            logger.warning(f"Slayer: missing coordinate for {label} ({key})")
            return False
        ax, ay = self._to_absolute(int(c.x), int(c.y))
        return bool(self.mouse.move_and_click(ax, ay, enforce_guard=False, clamp_to_search_roi=False))

    def _attack_nearest_to_tile(self, monsters: List[Dict[str, Any]], roi: Dict[str, int]) -> Optional[Tuple[int, int]]:
        if not monsters:
            return None
        def d2(p, q):
            return (float(p[0]) - float(q[0]))**2 + (float(p[1]) - float(q[1]))**2
        with_tile = [m for m in monsters if m.get('tile_center') is not None]
        try:
            target = min(with_tile, key=lambda m: d2(m['position'], m['tile_center'])) if with_tile else min(monsters, key=lambda m: d2(m['position'], (roi['left']+roi['width']//2, roi['top']+roi['height']//2)))
        except Exception:
            target = monsters[0]
        x, y = target['position']
        if self.mouse.move_and_click(x, y, enforce_guard=False, clamp_to_search_roi=True):
            self._last_attack_ts = time.time()
            self._last_click_pos = (x, y)
            tmo = float(self.config.get('slayer_hp_verify_timeout_s', 3.0))
            self._hp_verify_deadline = self._last_attack_ts + max(0.5, tmo)
            logger.info(f"Slayer: attacked at ({x},{y}); waiting {tmo:.1f}s for HP bar")
            return (x, y)
        return None

    def _run_slayer_sequence(self) -> None:
        # ctrl+s open
        hotkey = str(self.config.get('slayer_panel_hotkey', 'ctrl+s'))
        self.keyboard.press_hotkey(hotkey)
        time.sleep(0.15)
        # click task 1
        self._click_coord_key('slayer_task1_xy', 'task1')
        time.sleep(0.15)
        # click task 2
        self._click_coord_key('slayer_task2_xy', 'task2')
        time.sleep(0.15)
        # ctrl+s close
        self.keyboard.press_hotkey(hotkey)
        time.sleep(0.15)
        # click slayer monster entry
        self._click_coord_key('slayer_monster_button_xy', 'slayer monster')
        time.sleep(0.15)
        # click teleport
        if not self._click_coord_key('slayer_teleport_xy', 'teleport'):
            # Optional fallback to generic teleport hotkey if provided
            hk = str(self.config.get('return_teleport_hotkey', ''))
            if hk:
                self.keyboard.press_hotkey(hk)
        self.events.publish(EventType.TELEPORT_USED, {'location': 'slayer', 'emergency': False})
        logger.info("Slayer: sequence executed (task select + teleport)")

    def process_cycle(self) -> Dict[str, Any]:
        """One loop iteration. Returns last detection result for overlays."""
        res = self.engine.detect_cycle()
        in_combat = bool(res.get('in_combat', False))
        hp_seen = bool(res.get('hp_seen', False))
        monsters = res.get('monsters', [])
        roi = res.get('roi', {})

        # If HP is seen, clear verify timer and idle
        if hp_seen:
            if self._hp_verify_deadline > 0.0:
                logger.info("Slayer: HP seen -> clearing verify timer")
            self._hp_verify_deadline = 0.0
            return res

        # HP not seen. If a verify window expired after an attack, run sequence
        now = time.time()
        if self._hp_verify_deadline > 0.0 and now >= self._hp_verify_deadline:
            logger.info("Slayer: HP not detected after attack -> running Slayer sequence")
            self._hp_verify_deadline = 0.0
            self._run_slayer_sequence()
            return res

        # Not in combat and no deadline active -> try to attack a monster
        if (not in_combat) and monsters:
            self._attack_nearest_to_tile(monsters, roi)
            return res

        return res
