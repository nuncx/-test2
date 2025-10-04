"""
Detection engine for RSPS Color Bot v3
"""
import time
import logging
import threading
import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional, Any

from ..config import ConfigManager, ColorSpec, ROI
from .capture import CaptureService
from .color_detector import build_mask, build_mask_multi, contours_to_screen_points
from .color_detector import build_mask_precise_small
from .color_detector import closest_contour_to_point, largest_contour, random_contour

# Import InstanceOnlyDetector (will be imported when needed)
# from .instance_only_detector import InstanceOnlyDetector

# Get module logger
logger = logging.getLogger('rspsbot.core.detection.detector')

class DetectionEngine:

    def detect_combat_style_counts(self) -> Optional[Dict[str, Any]]:
        """
        Compute per-style pixel counts within the Style Indicator ROI using the configured ColorSpecs and
        thresholds. Returns a dict with counts and the selected style (or None if none exceed thresholds).

        Returns:
            {
              'counts': {'melee': int, 'ranged': int, 'magic': int},
              'thresholds': {'melee': int, 'ranged': int, 'magic': int, 'global': int},
              'style': Optional[str]
            } | None if ROI/frame not available
        """
        try:
            roi = self.config_manager.get_roi('combat_style_roi')
            if not roi:
                return None
            frame = self.capture_service.capture_region(roi)
            if frame is None:
                return None

            specs: Dict[str, Optional[ColorSpec]] = {
                'melee': self.config_manager.get_color_spec('combat_style_melee_color'),
                'ranged': self.config_manager.get_color_spec('combat_style_ranged_color'),
                'magic': self.config_manager.get_color_spec('combat_style_magic_color'),
            }
            global_min = int(self.config_manager.get('combat_style_min_pixels', 40))
            thr = {
                'melee': int(self.config_manager.get('combat_style_min_pixels_melee', 0) or 0) or global_min,
                'ranged': int(self.config_manager.get('combat_style_min_pixels_ranged', 0) or 0) or global_min,
                'magic': int(self.config_manager.get('combat_style_min_pixels_magic', 0) or 0) or global_min,
                'global': global_min,
            }
            use_precise_small = bool(self.config_manager.get('combat_precise_mode', True))
            cm_cfg = {
                'combat_lab_tolerance': self.config_manager.get('combat_lab_tolerance', 18),
                'combat_sat_min': self.config_manager.get('combat_sat_min', 40),
                'combat_val_min': self.config_manager.get('combat_val_min', 40),
                'combat_morph_open_iters': self.config_manager.get('combat_morph_open_iters', 1),
                'combat_morph_close_iters': self.config_manager.get('combat_morph_close_iters', 1),
            }

            counts: Dict[str, int] = {'melee': 0, 'ranged': 0, 'magic': 0}

            for key, spec in specs.items():
                if not spec:
                    counts[key] = 0
                    continue
                from typing import cast as _cast
                if use_precise_small:
                    mask, _ = build_mask_precise_small(frame, _cast(ColorSpec, spec), cm_cfg, step=1, min_area=0)
                else:
                    mask, _ = build_mask(frame, _cast(ColorSpec, spec), step=1, precise=True, min_area=0)
                counts[key] = int(cv2.countNonZero(mask))

            # Determine selected style among those that exceed threshold
            eligible = [k for k in counts.keys() if counts[k] >= thr[k]]
            if not eligible:
                sel = None
            elif len(eligible) == 1:
                sel = eligible[0]
            else:
                sel = max(eligible, key=lambda k: counts[k])

            return {'counts': counts, 'thresholds': thr, 'style': sel}
        except Exception:
            return None

    def detect_combat_style(self) -> Optional[str]:
        """
        Detect the current combat style by color presence within a configured ROI.

        Config keys:
          - combat_style_roi: ROI where a style indicator appears
          - combat_style_melee_color / _ranged_color / _magic_color: ColorSpec for each style
          - combat_style_min_pixels: minimum pixels to count as present

        Returns: 'melee' | 'ranged' | 'magic' | None
        """
        try:
            roi = self.config_manager.get_roi('combat_style_roi')
            if not roi:
                return None
            frame = self.capture_service.capture_region(roi)
            if frame is None:
                return None

            global_min_pix = int(self.config_manager.get('combat_style_min_pixels', 40))
            specs: Dict[str, Optional[ColorSpec]] = {
                'melee': self.config_manager.get_color_spec('combat_style_melee_color'),
                'ranged': self.config_manager.get_color_spec('combat_style_ranged_color'),
                'magic': self.config_manager.get_color_spec('combat_style_magic_color'),
            }
            present = []
            use_precise_small = bool(self.config_manager.get('combat_precise_mode', True))
            cm_cfg = {
                'combat_lab_tolerance': self.config_manager.get('combat_lab_tolerance', 18),
                'combat_sat_min': self.config_manager.get('combat_sat_min', 40),
                'combat_val_min': self.config_manager.get('combat_val_min', 40),
                'combat_morph_open_iters': self.config_manager.get('combat_morph_open_iters', 1),
                'combat_morph_close_iters': self.config_manager.get('combat_morph_close_iters', 1),
            }
            for key, spec in specs.items():
                if not spec:
                    continue
                try:
                    # Per-style threshold with fallback to global
                    if key == 'melee':
                        style_min = int(self.config_manager.get('combat_style_min_pixels_melee', 0) or 0)
                    elif key == 'ranged':
                        style_min = int(self.config_manager.get('combat_style_min_pixels_ranged', 0) or 0)
                    else:
                        style_min = int(self.config_manager.get('combat_style_min_pixels_magic', 0) or 0)
                    min_pix = style_min if style_min > 0 else global_min_pix
                    # Spec is ensured non-None above; cast for type checkers
                    from typing import cast as _cast
                    if use_precise_small:
                        mask, _ = build_mask_precise_small(frame, _cast(ColorSpec, spec), cm_cfg, step=1, min_area=0)
                    else:
                        mask, _ = build_mask(frame, _cast(ColorSpec, spec), step=1, precise=True, min_area=0)
                    if cv2.countNonZero(mask) >= min_pix:
                        present.append(key)
                except Exception:
                    continue
            if not present:
                return None
            # If multiple present, choose the one with largest pixel count
            if len(present) == 1:
                return present[0]
            best_key = None
            best_count = -1
            for key in present:
                try:
                    spec = specs[key]
                    from typing import cast as _cast
                    if use_precise_small:
                        mask, _ = build_mask_precise_small(frame, _cast(ColorSpec, spec), cm_cfg, step=1, min_area=0)
                    else:
                        mask, _ = build_mask(frame, _cast(ColorSpec, spec), step=1, precise=True, min_area=0)
                    cnt = int(cv2.countNonZero(mask))
                    if cnt > best_count:
                        best_key = key
                        best_count = cnt
                except Exception:
                    pass
            return best_key
        except Exception:
            return None

    def detect_weapon_for_style(self, style: Optional[str]) -> Optional[Tuple[int, int]]:
        """
        Locate a clickable weapon/style icon in the Weapon ROI using the given style's color.
        If found, return a screen (x, y) point; else None.

        style: 'melee'|'ranged'|'magic'|None. If None, uses preferred style from config.
        """
        try:
            roi = self.config_manager.get_roi('combat_weapon_roi')
            if not roi:
                return None
            frame = self.capture_service.capture_region(roi)
            if frame is None:
                return None

            st = (style or str(self.config_manager.get('combat_style_preferred', 'melee'))).lower()
            # Prefer weapon-specific color spec, fallback to style color
            if st.startswith('melee'):
                spec = self.config_manager.get_color_spec('combat_weapon_melee_color') or self.config_manager.get_color_spec('combat_style_melee_color')
            elif st.startswith('rang'):
                spec = self.config_manager.get_color_spec('combat_weapon_ranged_color') or self.config_manager.get_color_spec('combat_style_ranged_color')
            else:
                spec = self.config_manager.get_color_spec('combat_weapon_magic_color') or self.config_manager.get_color_spec('combat_style_magic_color')
            if not spec:
                return None

            from typing import cast as _cast
            use_precise_small = bool(self.config_manager.get('combat_precise_mode', True))
            cm_cfg = {
                'combat_lab_tolerance': self.config_manager.get('combat_lab_tolerance', 18),
                'combat_sat_min': self.config_manager.get('combat_sat_min', 40),
                'combat_val_min': self.config_manager.get('combat_val_min', 40),
                'combat_morph_open_iters': self.config_manager.get('combat_morph_open_iters', 1),
                'combat_morph_close_iters': self.config_manager.get('combat_morph_close_iters', 1),
            }
            if use_precise_small:
                mask, contours = build_mask_precise_small(frame, _cast(ColorSpec, spec), cm_cfg, step=1, min_area=0)
            else:
                mask, contours = build_mask(frame, _cast(ColorSpec, spec), step=1, precise=True, min_area=0)
            # Per-style threshold with fallback to global
            global_min = int(self.config_manager.get('combat_weapon_min_pixels', 30))
            if st.startswith('melee'):
                style_min = int(self.config_manager.get('combat_weapon_min_pixels_melee', 0) or 0)
            elif st.startswith('rang'):
                style_min = int(self.config_manager.get('combat_weapon_min_pixels_ranged', 0) or 0)
            else:
                style_min = int(self.config_manager.get('combat_weapon_min_pixels_magic', 0) or 0)
            min_pix = style_min if style_min > 0 else global_min
            if int(cv2.countNonZero(mask)) < min_pix:
                return None

            # Choose largest contour as target; convert to screen point
            cnt = largest_contour(contours)
            if cnt is None or len(cnt) == 0:
                ys, xs = np.where(mask > 0)
                if xs.size == 0:
                    return None
                cx = int(xs.mean())
                cy = int(ys.mean())
            else:
                M = cv2.moments(cnt)
                if M.get('m00', 0) == 0:
                    x, y, w, h = cv2.boundingRect(cnt)
                    cx = x + w // 2
                    cy = y + h // 2
                else:
                    cx = int(M['m10'] / M['m00'])
                    cy = int(M['m01'] / M['m00'])

            # Translate ROI-local point to screen coordinates
            try:
                left = int(roi.left)  # type: ignore[attr-defined]
                top = int(roi.top)    # type: ignore[attr-defined]
            except Exception:
                try:
                    rdict = roi.to_dict() if hasattr(roi, 'to_dict') else (dict(roi) if isinstance(roi, dict) else {})
                    left = int(rdict.get('left', 0))
                    top = int(rdict.get('top', 0))
                except Exception:
                    left, top = 0, 0
            return (int(left + cx), int(top + cy))
        except Exception:
            return None

    def detect_weapon_for_preferred_style(self) -> Optional[Tuple[int, int]]:
        """Backward-compatible wrapper using the configured preferred style."""
        return self.detect_weapon_for_style(None)
    """
    Central detection engine that coordinates detection of tiles, monsters, and combat status
    
    This class uses optimizations like regional processing and caching to improve performance.
    """
    
    def __init__(self, config_manager: ConfigManager, capture_service: CaptureService):
        """
        Initialize the detection engine
        
        Args:
            config_manager: Configuration manager
            capture_service: Capture service
        """
        self.config_manager = config_manager
        self.capture_service = capture_service
        
        # Detection components
        self.roi_manager = ROIManager(config_manager, capture_service)
        self.tile_detector = TileDetector(config_manager)
        self.monster_detector = MonsterDetector(config_manager)
        self.combat_detector = CombatDetector(config_manager, capture_service)
        
        # Instance-Only Mode detector (lazy-loaded when needed)
        self._instance_only_detector = None
        
        # Performance optimizations
        self._cache = {}
        self._cache_lock = threading.RLock()
        self._last_detection_time = 0
        self._last_detection_result = None
        
        # Detection statistics
        self._stats = {
            'tile_detections': 0,
            'monster_detections': 0,
            'combat_detections': 0,
            'detection_time_ms': 0,
            'detection_count': 0
        }

        # Temporal persistence (smooth out flicker)
        self._persist_tiles: List[Tuple[int, int]] = []
        self._persist_tiles_ts: float = 0.0
        self._persist_monsters: List[Dict[str, Any]] = []
        self._persist_monsters_ts: float = 0.0
        
        logger.info("Detection engine initialized")
    
    @property
    def instance_only_detector(self):
        """
        Lazy-load the instance-only detector when needed
        
        Returns:
            InstanceOnlyDetector: Instance-only detector
        """
        if self._instance_only_detector is None:
            # Import here to avoid circular imports
            from .instance_only_detector import InstanceOnlyDetector
            self._instance_only_detector = InstanceOnlyDetector(self.config_manager, self.capture_service)
        return self._instance_only_detector
    
    def detect_cycle(self) -> Dict[str, Any]:
        """
        Perform a full detection cycle: ROI > Tiles > Monsters > Combat
        
        Returns:
            Dictionary with detection results
        """
        # Check if Instance-Only Mode is enabled
        if self.config_manager.get('instance_only_mode', False):
            return self.instance_only_detector.detect_cycle()
        
        # Check cache for recent results
        current_time = time.time()
        cache_ttl = self.config_manager.get('detection_cache_ttl', 0.1)
        
        if (
            self._last_detection_result is not None
            and (current_time - self._last_detection_time) < cache_ttl
        ):
            return self._last_detection_result.copy()
        
        # Start timing
        start_time = time.time()
        
        # Get active ROI
        roi = self.roi_manager.get_active_roi()
        
        # Early combat check: if configured, skip tile/monster detection while in combat
        in_combat_init = self.combat_detector.is_in_combat()
        hp_seen_init = getattr(self.combat_detector, 'last_hp_seen', False)
        if in_combat_init and self.config_manager.get('skip_detection_when_in_combat', True):
            detection_time_ms = (time.time() - start_time) * 1000
            result = {
                'tiles': [],
                'monsters': [],
                'in_combat': True,
                'hp_seen': hp_seen_init,
                'monsters_by_tile': [],
                'timestamp': current_time,
                'detection_time_ms': detection_time_ms,
                'roi': roi
            }
            # Attach combat style debug info even in early-return path
            try:
                style_dbg = self.detect_combat_style_counts()
            except Exception:
                style_dbg = None
            if style_dbg:
                try:
                    result['combat_style'] = style_dbg.get('style')
                    result['combat_style_counts'] = style_dbg.get('counts', {})
                    result['combat_style_thresholds'] = style_dbg.get('thresholds', {})
                except Exception:
                    pass
            self._last_detection_result = result.copy()
            self._last_detection_time = current_time
            return result
        
        # Capture frame for detection
        frame = self.capture_service.capture_region(roi)
        
    # Detect tiles within SEARCH ROI only
        tiles = self.tile_detector.detect_tiles(frame, roi)
        self._stats['tile_detections'] += 1
        
        # If no tiles found, try adaptive search
        if not tiles and self.config_manager.get('adaptive_search', True):
            tiles = self.tile_detector.detect_tiles_adaptive(frame, roi)

        # Apply tile persistence (if enabled) when no tiles were found
        tile_persist_ms = int(self.config_manager.get('tile_persistence_ms', 0))
        now = current_time
        if not tiles and tile_persist_ms > 0:
            age_ms = (now - self._persist_tiles_ts) * 1000.0
            if self._persist_tiles and age_ms <= tile_persist_ms:
                logger.debug(f"Using persisted tiles ({len(self._persist_tiles)}) age={age_ms:.0f}ms")
                tiles = list(self._persist_tiles)
        else:
            # Update persistence store when we have fresh detections
            if tiles:
                self._persist_tiles = list(tiles)
                self._persist_tiles_ts = now
        
    # Detect monsters near each tile (still within SEARCH ROI via local ROI windows)
        monsters = []
        monsters_by_tile: List[Tuple[Tuple[int, int], int]] = []
        for tile in tiles:
            tile_monsters = self.monster_detector.detect_monsters_near_tile(frame, roi, tile)
            monsters.extend(tile_monsters)
            monsters_by_tile.append((tile, len(tile_monsters)))
        
        self._stats['monster_detections'] += 1

        # If still nothing, optionally fall back to scanning the entire search ROI
        if not monsters and self.config_manager.get('enable_monster_full_fallback', False):
            logger.debug("Monster full fallback enabled and no monsters found near tiles -> scanning full ROI")
            global_monsters = self.monster_detector.detect_monsters_in_bbox(frame, roi)
            monsters.extend(global_monsters)
            if global_monsters:
                roi_cx = roi['left'] + roi['width'] // 2
                roi_cy = roi['top'] + roi['height'] // 2
                monsters_by_tile.append(((roi_cx, roi_cy), len(global_monsters)))

        # Apply monster persistence (if enabled) when no monsters were found
        mon_persist_ms = int(self.config_manager.get('monster_persistence_ms', 0))
        if not monsters and mon_persist_ms > 0:
            age_ms = (now - self._persist_monsters_ts) * 1000.0
            if self._persist_monsters and age_ms <= mon_persist_ms:
                logger.debug(f"Using persisted monsters ({len(self._persist_monsters)}) age={age_ms:.0f}ms")
                monsters = list(self._persist_monsters)
        else:
            # Update persistence store when we have fresh detections
            if monsters:
                self._persist_monsters = list(monsters)
                self._persist_monsters_ts = now
        
        # Check combat status
        # Determine combat state; CombatDetector captures HP ROI internally
        in_combat = self.combat_detector.is_in_combat()
        hp_seen = getattr(self.combat_detector, 'last_hp_seen', False)
        self._stats['combat_detections'] += 1
        
        # Calculate detection time
        detection_time_ms = (time.time() - start_time) * 1000
        # Accumulate as float separately to avoid type noise; store rounded in stats
        self._stats['detection_time_ms'] = int(self._stats['detection_time_ms'] + detection_time_ms)
        self._stats['detection_count'] += 1
        
        # Create result
        result = {
            'tiles': tiles,
            'monsters': monsters,
            'in_combat': in_combat,
            'hp_seen': hp_seen,
            'monsters_by_tile': monsters_by_tile,
            'timestamp': current_time,
            'detection_time_ms': detection_time_ms,
            'roi': roi
        }

        # Also compute combat style debug info (lightweight; skips gracefully if ROI/specs missing)
        try:
            style_dbg = self.detect_combat_style_counts()
        except Exception:
            style_dbg = None
        if style_dbg:
            try:
                result['combat_style'] = style_dbg.get('style')
                result['combat_style_counts'] = style_dbg.get('counts', {})
                result['combat_style_thresholds'] = style_dbg.get('thresholds', {})
            except Exception:
                # Best-effort only; ignore on error
                pass
        
        # Cache result
        self._last_detection_result = result.copy()
        self._last_detection_time = current_time
        
        # Log detection stats periodically
        if self._stats['detection_count'] % 100 == 0:
            avg_time = self._stats['detection_time_ms'] / max(1, self._stats['detection_count'])
            logger.debug(f"Detection stats: avg_time={avg_time:.1f}ms, tiles={self._stats['tile_detections']}, monsters={self._stats['monster_detections']}")
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detection statistics"""
        stats = self._stats.copy()
        # Calculate averages (do not mutate int keys with floats)
        if stats['detection_count'] > 0:
            avg_ms = stats['detection_time_ms'] / max(1, stats['detection_count'])
        else:
            avg_ms = 0
        stats_out = stats.copy()
        # Keep stats dict typed as ints; expose rounded average
        stats_out['avg_detection_time_ms'] = int(avg_ms)
        return stats_out
    
    def reset_stats(self):
        """Reset detection statistics"""
        self._stats = {
            'tile_detections': 0,
            'monster_detections': 0,
            'combat_detections': 0,
            'detection_time_ms': 0,
            'detection_count': 0
        }
    
    def clear_cache(self):
        """Clear detection cache"""
        self._last_detection_time = 0
        self._last_detection_result = None
        self.capture_service.clear_cache()

class ROIManager:
    """
    Manages regions of interest for detection
    """
    
    def __init__(self, config_manager: ConfigManager, capture_service: CaptureService):
        """
        Initialize the ROI manager
        
        Args:
            config_manager: Configuration manager
        """
        self.config_manager = config_manager
        self.capture_service = capture_service
        self._last_logged_roi = None  # track last ROI dict for change logging
    
    def get_active_roi(self) -> Dict[str, int]:
        """
        Get the active region of interest
        
        Returns:
            Dictionary with left, top, width, height
        """
        # Simplified: only respect search_roi; ignore tile_roi concept
        try:
            search_roi = self.config_manager.get_roi('search_roi')
            if search_roi:
                # Normalize ROI to absolute screen coordinates to keep base_roi consistent
                roi_dict = search_roi.to_dict()
                try:
                    mode = str(roi_dict.get('mode', 'absolute')).lower()
                    from .capture import CaptureService  # type: ignore
                    bbox = CaptureService().get_window_bbox()
                    l = int(roi_dict.get('left', 0)); t = int(roi_dict.get('top', 0))
                    w = int(roi_dict.get('width', 0)); h = int(roi_dict.get('height', 0))
                    if mode == 'percent':
                        lf = float(roi_dict.get('left', 0.0)); tf = float(roi_dict.get('top', 0.0))
                        wf = float(roi_dict.get('width', 0.0)); hf = float(roi_dict.get('height', 0.0))
                        roi_dict = {
                            'left': int(bbox['left'] + lf * bbox['width']),
                            'top': int(bbox['top'] + tf * bbox['height']),
                            'width': int(max(1, wf * bbox['width'])),
                            'height': int(max(1, hf * bbox['height']))
                        }
                    elif mode == 'relative':
                        roi_dict = {
                            'left': int(bbox['left']) + l,
                            'top': int(bbox['top']) + t,
                            'width': w,
                            'height': h
                        }
                    else:
                        # Heuristic fallback if mode absent but values look client-relative
                        within_abs_window = (
                            l >= bbox['left'] - 2 and l <= bbox['left'] + bbox['width'] + 2 and
                            t >= bbox['top'] - 2 and t <= bbox['top'] + bbox['height'] + 2
                        )
                        looks_relative = (l < bbox['width'] and t < bbox['height'] and w <= bbox['width'] and h <= bbox['height'])
                        if not within_abs_window and looks_relative:
                            roi_dict = {
                                'left': int(bbox['left']) + l,
                                'top': int(bbox['top']) + t,
                                'width': w,
                                'height': h
                            }
                except Exception:
                    # If normalization fails, continue with raw dict
                    pass
                # Log once at startup and on change
                try:
                    if self._last_logged_roi != roi_dict:
                        logger.info(
                            f"Active Search ROI set to left={roi_dict['left']} top={roi_dict['top']} width={roi_dict['width']} height={roi_dict['height']}"
                        )
                        self._last_logged_roi = dict(roi_dict)
                except Exception:
                    pass
                return roi_dict
        except Exception:
            pass
        
        # Fallback to focused window bbox via capture service
        try:
            bbox = self.capture_service.get_window_bbox()
            roi_dict = {
                'left': int(bbox['left']),
                'top': int(bbox['top']),
                'width': int(bbox['width']),
                'height': int(bbox['height'])
            }
            if self._last_logged_roi != roi_dict:
                logger.info(
                    f"Active Search ROI not set; using window bbox left={roi_dict['left']} top={roi_dict['top']} width={roi_dict['width']} height={roi_dict['height']}"
                )
                self._last_logged_roi = dict(roi_dict)
            return roi_dict
        except Exception:
            roi_dict = {
                'left': 0,
                'top': 0,
                'width': 800,
                'height': 600
            }
            if self._last_logged_roi != roi_dict:
                logger.info(
                    f"Active Search ROI fallback default used left={roi_dict['left']} top={roi_dict['top']} width={roi_dict['width']} height={roi_dict['height']}"
                )
                self._last_logged_roi = dict(roi_dict)
            return roi_dict
    
    def get_detection_bbox(self, base_bbox: Dict[str, int]) -> Dict[str, int]:
        """
        Get detection bbox based on search ROI and base bbox
        
        Args:
            base_bbox: Base bounding box
        
        Returns:
            Detection bounding box
        """
        # If search ROI is set, restrict detection to it
        search_roi = self.config_manager.get_roi('search_roi')
        
        if search_roi:
            wl, wt = base_bbox['left'], base_bbox['top']
            ww, wh = base_bbox['width'], base_bbox['height']
            
            r = search_roi
            l = int(max(int(wl), int(r.left)))
            t = int(max(int(wt), int(r.top)))
            rgt = int(min(int(wl) + int(ww), int(r.left) + int(r.width)))
            btm = int(min(int(wt) + int(wh), int(r.top) + int(r.height)))
            
            if rgt > l and btm > t:
                return {
                    'left': l,
                    'top': t,
                    'width': rgt - l,
                    'height': btm - t
                }
        
        return base_bbox

class TileDetector:
    """
    Detects tiles in the game
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the tile detector
        
        Args:
            config_manager: Configuration manager
        """
        self.config_manager = config_manager
        self._empty_streak = 0  # consecutive zero-detection cycles
    
    def detect_tiles(self, frame: np.ndarray, roi: Dict[str, int]) -> List[Tuple[int, int]]:
        """
        Detect tiles in a frame
        
        Args:
            frame: Input frame
            roi: Region of interest
        
        Returns:
            List of tile center points (x, y)
        """
        # Check if tile detection is enabled
        if not self.config_manager.get('detect_tiles', True):
            return []
        
        # Get tile color and parameters
        tile_color = self.config_manager.get_color_spec('tile_color')
        if not tile_color:
            logger.warning("Tile color not configured")
            return []
        
        search_step = self.config_manager.get('search_step', 2)
        use_precise = self.config_manager.get('use_precise_mode', True)
        tile_min_area = self.config_manager.get('tile_min_area', 30)
        
        try:
            # Build mask and find contours
            mask, contours = build_mask(
                frame,
                tile_color,
                search_step,
                use_precise,
                tile_min_area
            )
            
            # Convert contours to screen points
            points = contours_to_screen_points(contours, roi, search_step)
            
            if points:
                logger.debug(f"Detected {len(points)} tiles (step={search_step}, precise={use_precise})")
                self._empty_streak = 0
            else:
                # Try a quick precise fallback at step=1 if nothing found
                if search_step > 1:
                    mask2, cnt2 = build_mask(
                        frame,
                        tile_color,
                        1,
                        True,
                        max(5, int(tile_min_area * 0.7))
                    )
                    points2 = contours_to_screen_points(cnt2, roi, 1)
                    if points2:
                        logger.debug("Fallback tile detection hit (step=1 precise)")
                        self._empty_streak = 0
                        return points2
                self._empty_streak += 1
                if self._empty_streak in (3, 10, 25):
                    try:
                        nonzero = int(np.count_nonzero(mask))
                        logger.warning(
                            f"Tile detection empty streak={self._empty_streak}; mask_nonzero={nonzero}; step={search_step}; precise={use_precise}; area_min={tile_min_area}"
                        )
                        if bool(self.config_manager.get('debug_save_snapshots', False)):
                            import os, time as _t
                            outdir = str(self.config_manager.get('debug_output_dir', 'outputs'))
                            os.makedirs(outdir, exist_ok=True)
                            ts = int(_t.time())
                            try:
                                cv2.imwrite(os.path.join(outdir, f"tile_mask_{ts}.png"), mask)
                            except Exception:
                                pass
                    except Exception:
                        pass
            return points
        
        except Exception as e:
            logger.error(f"Error detecting tiles: {e}")
            return []
    
    def detect_tiles_adaptive(self, frame: np.ndarray, roi: Dict[str, int]) -> List[Tuple[int, int]]:
        """
        Detect tiles with adaptive parameters for difficult cases
        
        Args:
            frame: Input frame
            roi: Region of interest
        
        Returns:
            List of tile center points (x, y)
        """
        # Get tile color
        tile_color_dict = self.config_manager.get('tile_color')
        if not tile_color_dict:
            logger.warning("Tile color not configured")
            return []
        
        # Create a more tolerant color spec
        try:
            tile_color = ColorSpec(
                rgb=tuple(tile_color_dict['rgb']),
                tol_rgb=min(60, int(tile_color_dict.get('tol_rgb', 8)) + 12),
                use_hsv=tile_color_dict.get('use_hsv', True),
                tol_h=min(30, int(tile_color_dict.get('tol_h', 4)) + 6),
                tol_s=min(120, int(tile_color_dict.get('tol_s', 30)) + 25),
                tol_v=min(120, int(tile_color_dict.get('tol_v', 30)) + 25)
            )
            
            # Use step 1 for more precise detection
            search_step = 1
            use_precise = True
            tile_min_area = max(5, int(self.config_manager.get('tile_min_area', 30) * 0.7))
            
            # Build mask and find contours
            _, contours = build_mask(
                frame,
                tile_color,
                search_step,
                use_precise,
                tile_min_area
            )
            
            # Convert contours to screen points
            points = contours_to_screen_points(contours, roi, search_step)
            
            if points:
                logger.debug(f"Adaptive detection found {len(points)} tiles")
            
            return points
        
        except Exception as e:
            logger.error(f"Error in adaptive tile detection: {e}")
            return []

class MonsterDetector:
    """
    Detects monsters in the game
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the monster detector
        
        Args:
            config_manager: Configuration manager
        """
        self.config_manager = config_manager
        # Cache last-built specs timestamp to allow cheap refresh if GUI updates occur
        self._mm_like_specs_cache: List[ColorSpec] = []
        self._mm_like_specs_last_build: float = 0.0

    # --- Shared helpers to mirror Multi Monster color logic ---
    def _build_mm_like_monster_specs(self) -> List[ColorSpec]:
        """
    Build monster ColorSpec list using the same rules as Multi Monster mode:
    - Prefer 'multi_monster_configs' entries with optional 'alternates'
    - Fallback to legacy 'monster_colors' list
        - Use HSV with tol_h=6, tol_s=45, tol_v=45 and tol_rgb >= 10
        Returns a fresh list each call.
        """
        try:
            import time as _time
            # Rebuild at most every ~2s to pick up GUI changes without overhead
            if (not self._mm_like_specs_cache) or (_time.time() - self._mm_like_specs_last_build > 2.0):
                specs: List[ColorSpec] = []
                # Prefer Multi Monster configs (with alternates), else fallback to legacy monster_colors
                mm_cfgs = self.config_manager.get('multi_monster_configs', []) or []
                if isinstance(mm_cfgs, list) and mm_cfgs:
                    for cfg in mm_cfgs:
                        try:
                            col = cfg.get('color') if isinstance(cfg, dict) else None
                            if not isinstance(col, dict):
                                continue
                            rgb_list = col.get('rgb')
                            if not rgb_list or len(rgb_list) != 3:
                                continue
                            rgb = (int(rgb_list[0]), int(rgb_list[1]), int(rgb_list[2]))
                            tol = int(col.get('tol_rgb', 15))
                            specs.append(ColorSpec(
                                rgb=rgb,
                                tol_rgb=max(10, tol),
                                use_hsv=True,
                                tol_h=6, tol_s=45, tol_v=45
                            ))
                            # Alternates
                            alts = cfg.get('alternates', []) or []
                            if isinstance(alts, list):
                                for alt in alts:
                                    try:
                                        if not isinstance(alt, dict):
                                            continue
                                        a_rgb = alt.get('rgb')
                                        if not a_rgb or len(a_rgb) != 3:
                                            continue
                                        a = (int(a_rgb[0]), int(a_rgb[1]), int(a_rgb[2]))
                                        a_tol = int(alt.get('tol_rgb', tol))
                                        specs.append(ColorSpec(
                                            rgb=a,
                                            tol_rgb=max(10, a_tol),
                                            use_hsv=True,
                                            tol_h=6, tol_s=45, tol_v=45
                                        ))
                                    except Exception:
                                        continue
                        except Exception:
                            continue
                else:
                    # Fallback to legacy monster_colors
                    legacy = self.config_manager.get('monster_colors', []) or []
                    if isinstance(legacy, list):
                        for cdict in legacy:
                            try:
                                if not isinstance(cdict, dict):
                                    continue
                                rgb_list = cdict.get('rgb')
                                if not rgb_list or len(rgb_list) != 3:
                                    continue
                                rgb = (int(rgb_list[0]), int(rgb_list[1]), int(rgb_list[2]))
                                tol = int(cdict.get('tol_rgb', 15))
                                specs.append(ColorSpec(
                                    rgb=rgb,
                                    tol_rgb=max(10, tol),
                                    use_hsv=True,
                                    tol_h=6, tol_s=45, tol_v=45
                                ))
                            except Exception:
                                continue
                self._mm_like_specs_cache = specs
                self._mm_like_specs_last_build = _time.time()
            return list(self._mm_like_specs_cache)
        except Exception:
            return []

    # --- Normal (non-Multi Monster) helpers: use Detection Settings strictly ---
    def _build_normal_monster_specs(self) -> List[ColorSpec]:
        """
        Build monster ColorSpec list from Detection Settings only (monster_colors).
        Do NOT include multi-monster alternates or overrides.
        """
        specs: List[ColorSpec] = []
        try:
            # Use legacy detection colors from Detection panel
            legacy = self.config_manager.get('monster_colors', []) or []
            if isinstance(legacy, list):
                for cdict in legacy:
                    try:
                        if not isinstance(cdict, dict):
                            continue
                        rgb_list = cdict.get('rgb')
                        if not rgb_list or len(rgb_list) != 3:
                            continue
                        rgb = (int(rgb_list[0]), int(rgb_list[1]), int(rgb_list[2]))
                        tol_rgb = int(cdict.get('tol_rgb', 15))
                        use_hsv = bool(cdict.get('use_hsv', False))
                        tol_h = int(cdict.get('tol_h', 6))
                        tol_s = int(cdict.get('tol_s', 45))
                        tol_v = int(cdict.get('tol_v', 45))
                        specs.append(ColorSpec(
                            rgb=rgb,
                            tol_rgb=max(1, tol_rgb),
                            use_hsv=use_hsv,
                            tol_h=tol_h, tol_s=tol_s, tol_v=tol_v
                        ))
                    except Exception:
                        continue
        except Exception:
            pass
        return specs

    def _normal_config(self) -> Dict[str, Any]:
        """
        Build the mask config dict using Detection Settings only.
        """
        return {
            'monster_sat_min': self.config_manager.get('monster_sat_min', 50),
            'monster_val_min': self.config_manager.get('monster_val_min', 50),
            'monster_exclude_tile_color': bool(self.config_manager.get('monster_exclude_tile_color', True)),
            'monster_exclude_tile_dilate': int(self.config_manager.get('monster_exclude_tile_dilate', 0)),
            'monster_morph_open_iters': self.config_manager.get('monster_morph_open_iters', 1),
            'monster_morph_close_iters': self.config_manager.get('monster_morph_close_iters', 2),
            'monster_use_lab_assist': bool(self.config_manager.get('monster_use_lab_assist', False)),
            'monster_lab_tolerance': self.config_manager.get('monster_lab_tolerance', 20),
            'tile_color': None
        }

    def _mm_like_config(self) -> Dict[str, Any]:
        """
        Build the mask config dict mirroring Multi Monster defaults, with sensible fallbacks.
        """
        return {
            'monster_sat_min': self.config_manager.get('multi_monster_sat_min', self.config_manager.get('monster_sat_min', 50)),
            'monster_val_min': self.config_manager.get('multi_monster_val_min', self.config_manager.get('monster_val_min', 50)),
            # In Multi Monster we do not exclude tile color from monster mask
            'monster_exclude_tile_color': False,
            'monster_exclude_tile_dilate': 0,
            'monster_morph_open_iters': self.config_manager.get('multi_monster_morph_open_iters', self.config_manager.get('monster_morph_open_iters', 1)),
            'monster_morph_close_iters': self.config_manager.get('multi_monster_morph_close_iters', self.config_manager.get('monster_morph_close_iters', 2)),
            'monster_use_lab_assist': True,
            'monster_lab_tolerance': self.config_manager.get('multi_monster_lab_tolerance', self.config_manager.get('monster_lab_tolerance', 20)),
            'tile_color': None
        }
    
    def detect_monsters_near_tile(
        self,
        frame: np.ndarray,
        base_roi: Dict[str, int],
        tile_center: Tuple[int, int]
    ) -> List[Dict[str, Any]]:
        """
        Detect monsters near a tile with progressive ROI expansion
        
        Args:
            frame: Input frame
            base_roi: Base region of interest
            tile_center: Tile center point (x, y)
        
        Returns:
            List of monster dictionaries with position and metadata
        """
        # Check if monster detection is enabled
        if not self.config_manager.get('detect_monsters', True):
            return []
        
    # Get monster detection parameters (preserve ROI strategy but choose color/config by mode)
        base_radius = self.config_manager.get('around_tile_radius', 120)
        max_expansion = self.config_manager.get('roi_max_expansion', 3)
        expansion_factor = self.config_manager.get('roi_expansion_factor', 1.2)
        
        # Try detection with progressively larger ROIs
        monsters = []
        expansion_level = 0
        
        while not monsters and expansion_level <= max_expansion:
            # Calculate expanded radius
            radius = int(base_radius * (expansion_factor ** expansion_level))
            
            # Create ROI with expanded radius
            roi_bbox = self._create_detection_roi_with_radius(tile_center, base_roi, radius)
            
            if roi_bbox['width'] <= 0 or roi_bbox['height'] <= 0:
                break
            
            # Choose color/spec behavior based on Multi Monster Mode toggle
            mm_enabled = bool(self.config_manager.get('multi_monster_mode_enabled', False))
            if mm_enabled:
                monster_colors = self._build_mm_like_monster_specs()
            else:
                monster_colors = self._build_normal_monster_specs()

            if not monster_colors:
                logger.warning("No valid monster colors configured")
                return []
            
            # Capture ROI
            roi_frame = frame[
                roi_bbox['top'] - base_roi['top']:roi_bbox['top'] - base_roi['top'] + roi_bbox['height'],
                roi_bbox['left'] - base_roi['left']:roi_bbox['left'] - base_roi['left'] + roi_bbox['width']
            ]
            
            # Detection parameters: depend on mode
            step = 1
            use_precise = True
            if mm_enabled:
                monster_min_area = self.config_manager.get('multi_monster_monster_min_area', self.config_manager.get('monster_min_area', 15))
                config_dict = self._mm_like_config()
            else:
                monster_min_area = self.config_manager.get('monster_min_area', 15)
                config_dict = self._normal_config()
            
            try:
                # Build mask and find contours
                _, contours = build_mask_multi(
                    roi_frame,
                    monster_colors,
                    step,
                    use_precise,
                    monster_min_area,
                    config_dict
                )
                
                # If no contours found, try adaptive detection
                if not contours and self.config_manager.get('adaptive_monster_detection', True):
                    contours = self._adaptive_monster_detection(roi_frame, monster_colors, config_dict)
                
                # Convert contours to screen points and create monster objects
                monsters = []
                
                for cnt in contours:
                    # Calculate centroid
                    M = cv2.moments(cnt)
                    
                    if M["m00"] == 0:
                        # Fallback to bounding rect center
                        x, y, w, h = cv2.boundingRect(cnt)
                        cx_small, cy_small = x + w // 2, y + h // 2
                    else:
                        # Use centroid
                        cx_small = int(M["m10"] / M["m00"])
                        cy_small = int(M["m01"] / M["m00"])
                    
                    # Convert to screen coordinates
                    screen_x = roi_bbox['left'] + cx_small * step
                    screen_y = roi_bbox['top'] + cy_small * step
                    
                    # Calculate area and size
                    area = cv2.contourArea(cnt)
                    x, y, w, h = cv2.boundingRect(cnt)
                    
                    # Create monster object
                    monster = {
                        'position': (screen_x, screen_y),
                        'area': area * step * step,
                        'width': w * step,
                        'height': h * step,
                        'tile_center': tile_center,
                        'distance': ((screen_x - tile_center[0]) ** 2 + (screen_y - tile_center[1]) ** 2) ** 0.5,
                        'expansion_level': expansion_level  # Track which expansion level found this monster
                    }
                    
                    monsters.append(monster)
                
                # If monsters found, break the loop
                if monsters:
                    if expansion_level > 0:
                        logger.debug(f"Found {len(monsters)} monsters at expansion level {expansion_level}")
                    break
                
                # Otherwise, try with a larger radius
                expansion_level += 1
                logger.debug(f"No monsters found at expansion level {expansion_level-1}, trying level {expansion_level}")
                
            except Exception as e:
                logger.error(f"Error detecting monsters near tile: {e}")
                return []
        
        if monsters:
            logger.debug(f"Detected {len(monsters)} monsters near tile {tile_center}")
        
        return monsters

    def detect_monsters_in_bbox(
        self,
        frame: np.ndarray,
        base_roi: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """
        Detect monsters across the entire provided ROI (global fallback)

        Args:
            frame: Frame corresponding to base_roi (already cropped by caller)
            base_roi: Absolute bounding box of the frame

        Returns:
            List of monster dictionaries with position and metadata
        """
        # Choose color/spec behavior based on Multi Monster Mode toggle
        mm_enabled = bool(self.config_manager.get('multi_monster_mode_enabled', False))
        if mm_enabled:
            monster_colors = self._build_mm_like_monster_specs()
        else:
            monster_colors = self._build_normal_monster_specs()

        if not monster_colors:
            logger.warning("No valid monster colors configured")
            return []

        # Detection parameters: depend on mode
        step = 1
        use_precise = True
        if mm_enabled:
            monster_min_area = self.config_manager.get('multi_monster_monster_min_area', self.config_manager.get('monster_min_area', 15))
            config_dict = self._mm_like_config()
        else:
            monster_min_area = self.config_manager.get('monster_min_area', 15)
            config_dict = self._normal_config()

        try:
            # Build mask and find contours over full ROI frame
            _, contours = build_mask_multi(
                frame,
                monster_colors,
                step,
                use_precise,
                monster_min_area,
                config_dict
            )

            monsters: List[Dict[str, Any]] = []
            for cnt in contours:
                M = cv2.moments(cnt)
                if M["m00"] == 0:
                    x, y, w, h = cv2.boundingRect(cnt)
                    cx_small, cy_small = x + w // 2, y + h // 2
                else:
                    cx_small = int(M["m10"] / M["m00"])
                    cy_small = int(M["m01"] / M["m00"])

                screen_x = base_roi['left'] + cx_small * step
                screen_y = base_roi['top'] + cy_small * step
                area = cv2.contourArea(cnt)
                x, y, w, h = cv2.boundingRect(cnt)

                monster = {
                    'position': (screen_x, screen_y),
                    'area': area * step * step,
                    'width': w * step,
                    'height': h * step,
                    'tile_center': None,
                    'distance': 0.0
                }
                monsters.append(monster)

            if monsters:
                logger.debug(f"Global ROI detection found {len(monsters)} monsters")

            return monsters

        except Exception as e:
            logger.error(f"Error in global monster detection: {e}")
            return []
    
    def _create_detection_roi(
        self,
        center: Tuple[int, int],
        base_roi: Dict[str, int],
        monster_type: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Create a region of interest around a center point
        
        Args:
            center: Center point (x, y)
            base_roi: Base region of interest
            monster_type: Type of monster to adjust ROI size
        
        Returns:
            ROI dictionary
        """
        cx, cy = center
        
        # Get base radius from config
        base_radius = self.config_manager.get('around_tile_radius', 120)
        
        # Adjust radius based on monster type
        if monster_type == 'important':
            radius = int(base_radius * 1.5)
        elif monster_type == 'small':
            radius = int(base_radius * 0.7)
        else:
            radius = base_radius
        
        return self._create_detection_roi_with_radius(center, base_roi, radius)
    
    def _create_detection_roi_with_radius(
        self,
        center: Tuple[int, int],
        base_roi: Dict[str, int],
        radius: int
    ) -> Dict[str, int]:
        """
        Create a region of interest around a center point with a specific radius
        
        Args:
            center: Center point (x, y)
            base_roi: Base region of interest
            radius: Radius around center point
        
        Returns:
            ROI dictionary
        """
        cx, cy = center
        
        left = base_roi['left']
        top = base_roi['top']
        width = base_roi['width']
        height = base_roi['height']
        
        # Calculate ROI bounds with proper boundary handling
        x0 = max(left, cx - radius)
        y0 = max(top, cy - radius)
        x1 = min(left + width, cx + radius)
        y1 = min(top + height, cy + radius)
        
        return {
            'left': x0,
            'top': y0,
            'width': max(0, x1 - x0),
            'height': max(0, y1 - y0)
        }
    
    def _adaptive_monster_detection(
        self,
        frame: np.ndarray,
        monster_colors: List[ColorSpec],
        config_dict: Dict
    ) -> List:
        """
        Adaptive monster detection with more tolerant parameters
        
        Args:
            frame: Input frame
            monster_colors: List of monster color specs
            config_dict: Configuration dictionary
        
        Returns:
            List of contours
        """
        # Create more tolerant color specs
        adaptive_colors = []
        
        for spec in monster_colors:
            adaptive_spec = ColorSpec(
                rgb=spec.rgb,
                tol_rgb=min(60, spec.tol_rgb + 12),
                use_hsv=spec.use_hsv,
                tol_h=min(30, spec.tol_h + 6),
                tol_s=min(120, spec.tol_s + 25),
                tol_v=min(120, spec.tol_v + 25)
            )
            adaptive_colors.append(adaptive_spec)
        
        # Use step 1 for more precise detection
        step = 1
        use_precise = True
        monster_min_area = max(5, int(self.config_manager.get('monster_min_area', 15) * 0.7))
        
        # Build mask and find contours
        _, contours = build_mask_multi(
            frame,
            adaptive_colors,
            step,
            use_precise,
            monster_min_area,
            config_dict
        )
        
        if contours:
            logger.debug(f"Adaptive detection found {len(contours)} monsters")
        
        return contours

class CombatDetector:
    """
    Detects combat status based on HP bar
    """
    
    def __init__(self, config_manager: ConfigManager, capture_service: CaptureService):
        """
        Initialize the combat detector
        
        Args:
            config_manager: Configuration manager
            capture_service: Capture service for grabbing HP ROI
        """
        self.config_manager = config_manager
        self.capture_service = capture_service
        
        # Combat state tracking
        self.in_combat = False
        self.last_combat_time = 0.0
        # Use configured timeout key with sensible fallback
        self.combat_timeout = float(
            self.config_manager.get('combat_not_seen_timeout_s', self.config_manager.get('combat_timeout', 10.0))
        )
        self.leave_immediately = bool(self.config_manager.get('combat_leave_immediately', True))
    
    def is_in_combat(self) -> bool:
        """
        Detect if player is in combat based on HP bar
        
        Returns:
            True if in combat, False otherwise
        """
        # Check if HP bar detection is enabled
        if not self.config_manager.get('hpbar_detect_enabled', True):
            return False
        
        # Get HP bar ROI
        hp_roi = self.config_manager.get_roi('hpbar_roi')
        if not hp_roi:
            return False
        
        # Detect HP bar in current screen
        hp_detected = self._detect_hp_bar(hp_roi)
        
        # Update combat state
        current_time = time.time()
        if hp_detected:
            self.last_hp_seen = True
            if not self.in_combat:
                logger.debug("HP bar detected -> entering combat")
            self.in_combat = True
            self.last_combat_time = current_time
        else:
            self.last_hp_seen = False
            if self.in_combat:
                if self.leave_immediately:
                    logger.debug("HP bar not seen -> leaving combat immediately")
                    self.in_combat = False
                elif (current_time - self.last_combat_time > self.combat_timeout):
                    logger.debug("HP bar not seen for timeout -> leaving combat")
                    self.in_combat = False
        
        return self.in_combat
    
    def _detect_hp_bar(self, hp_roi: ROI) -> bool:
        """
        Detect HP bar in the configured ROI using color thresholding
        
        Returns:
            True if HP bar detected, False otherwise
        """
        try:
            # Get color spec and thresholds
            color_spec = self.config_manager.get_color_spec('hpbar_color')
            if not color_spec:
                logger.warning("HP bar color not configured")
                return False
            min_area = int(self.config_manager.get('hpbar_min_area', 50))
            min_pixels = int(self.config_manager.get('hpbar_min_pixel_matches', 150))
            
            # Capture region
            frame = self.capture_service.capture_region(hp_roi)
            mask, contours = build_mask(frame, color_spec, step=1, precise=True, min_area=min_area)

            # Quick pixel threshold test
            pixel_matches = int((mask > 0).sum())
            detected = False
            if pixel_matches >= min_pixels and len(contours) > 0:
                detected = True

            # Optional verbose debug logging
            if self.config_manager.get('hpbar_debug_logging', False):
                largest_area = 0.0
                if contours:
                    try:
                        import cv2
                        largest_area = max(cv2.contourArea(c) for c in contours)
                    except Exception:
                        pass
                logger.info(
                    f"HPBarCycle roi=({hp_roi.left},{hp_roi.top},{hp_roi.width}x{hp_roi.height}) matches={pixel_matches} contours={len(contours)} min_px={min_pixels} min_area={min_area} largest_area={largest_area:.1f} detected={detected}"
                )
            return detected
        except Exception as e:
            logger.error(f"Error detecting HP bar: {e}")
            return False