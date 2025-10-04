"""
Multi Monster Mode detector for RSPS Color Bot v3
"""
import time
import logging
import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional, Any

from ..config import ConfigManager, ColorSpec, ROI
from .capture import CaptureService
from .color_detector import build_mask, build_mask_multi, contours_to_screen_points
from .color_detector import build_mask_precise_small
from .color_detector import closest_contour_to_point, largest_contour, random_contour
from .detector import DetectionEngine

# Get module logger
logger = logging.getLogger('rspsbot.core.detection.multi_monster_detector')

class MultiMonsterDetector(DetectionEngine):
    """
    Multi Monster Mode detector that handles different monster types with different combat styles
    """
    
    def __init__(self, config_manager: ConfigManager, capture_service: CaptureService):
        """
        Initialize the multi monster detector
        
        Args:
            config_manager: Configuration manager
            capture_service: Capture service
        """
        super().__init__(config_manager, capture_service)
        self.monster_style_map = {}  # Maps monster colors to combat styles
        # Detailed specs list: [{'rgb':(r,g,b), 'tol':tol_rgb, 'style':style}]
        self.monster_specs: List[Dict[str, Any]] = []
        self.last_detected_style = None
        self.last_style_change_time = 0
        self._last_monster_config_reload = 0.0  # epoch timestamp of last successful (or attempted) load
        self.load_monster_configs()
        # Cache for weapon templates (loaded lazily)
        self._weapon_templates = { 'melee': None, 'ranged': None, 'magic': None }
    
    # --- Combat state wrapper ---
    def is_in_combat(self) -> bool:  # type: ignore[override]
        """Return combat state using underlying generic combat detector.
        DetectionEngine maintains a CombatDetector instance at self.combat_detector.
        We expose a thin wrapper so multi monster logic can call self.is_in_combat()
        just like the generic detection cycle without re‑implementing HP logic.
        """
        try:
            cd = getattr(self, 'combat_detector', None)
            if cd is None:
                return False
            return bool(cd.is_in_combat())
        except Exception:
            return False
    
    def load_monster_configs(self):
        """Load monster configurations from config"""
        monster_configs = self.config_manager.get('multi_monster_configs', [])
        self.monster_style_map = {}
        self.monster_specs = []
        
        for config in monster_configs:
            if 'color' in config and 'style' in config:
                try:
                    rgb = tuple(config['color']['rgb'])
                    color_key = rgb
                    self.monster_style_map[color_key] = config['style']
                    tol_rgb = int(config['color'].get('tol_rgb', 15)) if isinstance(config['color'], dict) else 15
                    self.monster_specs.append({
                        'rgb': rgb,
                        'tol': tol_rgb,
                        'style': config['style']
                    })
                    # Include optional alternates list for this style
                    alts = config.get('alternates', []) or []
                    if isinstance(alts, list):
                        for alt in alts:
                            try:
                                alt_rgb_list = alt.get('rgb') if isinstance(alt, dict) else None
                                if not alt_rgb_list or len(alt_rgb_list) != 3:
                                    continue
                                alt_rgb = tuple(int(v) for v in alt_rgb_list)
                                alt_tol = int(alt.get('tol_rgb', tol_rgb)) if isinstance(alt, dict) else tol_rgb
                                # Map exact alternate color to the same style for strict matching
                                self.monster_style_map[alt_rgb] = config['style']
                                # Add to specs so build_mask_multi ORs them during detection
                                self.monster_specs.append({
                                    'rgb': alt_rgb,
                                    'tol': alt_tol,
                                    'style': config['style']
                                })
                            except Exception:
                                continue
                except Exception:
                    pass

        # Fallback: derive from legacy 'monster_colors' if no explicit multi_monster_configs were set
        if not self.monster_specs:
            try:
                legacy = self.config_manager.get('monster_colors', []) or []
                if isinstance(legacy, list) and legacy:
                    style_order = ['melee', 'ranged', 'magic']
                    derived_count = 0
                    for idx, cdict in enumerate(legacy):
                        try:
                            rgb = tuple(cdict.get('rgb') or [])
                            if len(rgb) != 3:
                                continue
                            tol_rgb = int(cdict.get('tol_rgb', 15))
                            style = style_order[idx] if idx < len(style_order) else f"style_{idx}"
                            self.monster_style_map[rgb] = style
                            self.monster_specs.append({'rgb': rgb, 'tol': tol_rgb, 'style': style})
                            derived_count += 1
                        except Exception:
                            continue
                    if derived_count:
                        logger.warning(f"[MultiMonster][Config] Using fallback monster_colors to derive {derived_count} monster style mappings. Configure 'Monster Configuration' in the GUI and click Apply to persist exact colors/styles.")
            except Exception:
                pass
        self._last_monster_config_reload = time.time()

    def _maybe_reload_monster_configs(self):
        """Reload monster configs if none loaded or a refresh interval elapsed.
        This allows dynamic GUI edits (Apply button) to take effect without recreating the detector.
        Lightweight: only touches in-memory list every few seconds.
        """
        try:
            now = time.time()
            # Always reload if >5s since last attempt OR list empty (unconditional periodic refresh)
            if (now - getattr(self, '_last_monster_config_reload', 0) > 5.0) or (not self.monster_specs):
                before = len(self.monster_specs)
                self.load_monster_configs()
                after = len(self.monster_specs)
                logger.debug(f"[MultiMonster][Reload] Monster specs reload (prev={before} new={after})")
        except Exception:
            pass

    # --- Matching helpers ---
    def _match_monster_color(self, color: Tuple[int, int, int]) -> Optional[str]:
        """Return style if color matches a configured monster color under its tolerance.
        Matching rule: per-channel abs diff <= tol, AND optional Euclidean distance <= tol*1.5 (loose gate) to reduce false positives.
        Returns style string or None if no match.
        """
        try:
            if not self.monster_specs:
                return None
            best_style = None
            best_score = 1e9
            for spec in self.monster_specs:
                rgb = spec.get('rgb')
                tol = spec.get('tol', 15)
                if not rgb:
                    continue
                # Per channel check first
                if any(abs(int(c1) - int(c2)) > tol for c1, c2 in zip(color, rgb)):
                    continue
                # Euclidean distance score
                dist = sum((int(c1) - int(c2)) ** 2 for c1, c2 in zip(color, rgb)) ** 0.5
                # Loose gate to prevent near-threshold multi matches
                if dist > (tol * 1.5):
                    continue
                if dist < best_score:
                    best_score = dist
                    best_style = spec.get('style')
            return best_style
        except Exception:
            return None
    
    def detect_monsters_with_styles(self, frame: np.ndarray, base_roi: Dict[str, int]) -> List[Dict[str, Any]]:
        """
        Detect monsters and assign combat styles based on monster color
        
        Args:
            frame: Captured frame
            base_roi: Base region of interest
            
        Returns:
            List of detected monsters with their positions and assigned combat styles
        """
        # Ensure we have up-to-date monster color specs
        self._maybe_reload_monster_configs()

        # First, detect tiles
        tiles = self.detect_tiles(frame, base_roi)
        if not tiles:
            logger.debug("[MultiMonster] No tiles found")
            return []
        
        strict = bool(self.config_manager.get('multi_monster_strict_colors', True))

        # Build ColorSpec list from configured monster specs
        color_specs: List[ColorSpec] = []
        for spec in self.monster_specs:
            try:
                rgb_val = spec.get('rgb') or (0, 0, 0)
                # Ensure exactly length-3 int tuple for type safety
                if isinstance(rgb_val, (list, tuple)):
                    rgb_list = list(rgb_val)[:3] + [0, 0, 0]
                    rgb = (int(rgb_list[0]), int(rgb_list[1]), int(rgb_list[2]))
                else:
                    rgb = (0, 0, 0)
                tol = int(spec.get('tol', 15))
                # Build a tolerant ColorSpec to avoid missing detections
                color_specs.append(ColorSpec(
                    rgb=rgb,
                    tol_rgb=max(10, tol),
                    use_hsv=True,
                    tol_h=6,
                    tol_s=45,
                    tol_v=45
                ))
            except Exception:
                continue
        if not color_specs:
            logger.debug("[MultiMonster] No configured monster color specs available")
            return []

        # Detection parameters (overridden by Multi Monster tile settings)
        step = 1
        use_precise = True
        min_area = int(self.config_manager.get('multi_monster_monster_min_area', 10))
        # Strict distance gating: single radius from UI; override other tile distance settings
        around_radius = int(self.config_manager.get('multi_monster_tile_radius', 120))

        monsters_all: List[Dict[str, Any]] = []
        monsters_kept: List[Dict[str, Any]] = []
        # Iterate tiles, build a ROI around each with the fixed radius, and detect color blobs
        for tile in tiles:
            tile_center = (tile['center_x'], tile['center_y'])
            radius = around_radius
            # Form ROI
            roi_left = max(base_roi['left'], tile_center[0] - radius)
            roi_top = max(base_roi['top'], tile_center[1] - radius)
            roi_right = min(base_roi['left'] + base_roi['width'], tile_center[0] + radius)
            roi_bottom = min(base_roi['top'] + base_roi['height'], tile_center[1] + radius)
            roi_w = roi_right - roi_left
            roi_h = roi_bottom - roi_top
            if roi_w <= 4 or roi_h <= 4:
                continue
            roi_frame = frame[
                roi_top - base_roi['top']:roi_top - base_roi['top'] + roi_h,
                roi_left - base_roi['left']:roi_left - base_roi['left'] + roi_w
            ]
            try:
                _, contours = build_mask_multi(
                    roi_frame,
                    color_specs,
                    step,
                    use_precise,
                    min_area,
                    {
                        'monster_sat_min': self.config_manager.get('multi_monster_sat_min', 50),
                        'monster_val_min': self.config_manager.get('multi_monster_val_min', 50),
                        'monster_exclude_tile_color': False,
                        'monster_exclude_tile_dilate': 0,
                        'monster_morph_open_iters': self.config_manager.get('multi_monster_morph_open_iters', 1),
                        'monster_morph_close_iters': self.config_manager.get('multi_monster_morph_close_iters', 2),
                        'monster_use_lab_assist': True,
                        'monster_lab_tolerance': self.config_manager.get('multi_monster_lab_tolerance', 15),
                        'tile_color': None
                    }
                )
            except Exception as e:
                logger.error(f"[MultiMonster] Error building mask_multi: {e}")
                contours = []
            # Convert contours with strict distance gating (<= radius)
            local_monsters: List[Dict[str, Any]] = []
            for cnt in contours:
                M = cv2.moments(cnt)
                if M['m00'] == 0:
                    x, y, w, h = cv2.boundingRect(cnt)
                    cx_small, cy_small = x + w // 2, y + h // 2
                else:
                    cx_small = int(M['m10'] / M['m00'])
                    cy_small = int(M['m01'] / M['m00'])
                area = cv2.contourArea(cnt)
                x, y, w, h = cv2.boundingRect(cnt)
                screen_x = roi_left + cx_small * step
                screen_y = roi_top + cy_small * step
                dist = ((screen_x - tile_center[0]) ** 2 + (screen_y - tile_center[1]) ** 2) ** 0.5
                if dist > radius:
                    continue
                monster = {
                    'position': (screen_x, screen_y),
                    'center_x': screen_x,
                    'center_y': screen_y,
                    'area': area * step * step,
                    'width': w * step,
                    'height': h * step,
                    'tile_center': tile_center,
                    'distance': dist,
                    'expansion_level': 0
                }
                local_monsters.append(monster)
            # Style assignment & filtering
            for monster in local_monsters:
                # Sample a representative pixel color from frame (guard bounds)
                sx, sy = monster['center_x'], monster['center_y']
                try:
                    if base_roi['left'] <= sx < base_roi['left'] + base_roi['width'] and base_roi['top'] <= sy < base_roi['top'] + base_roi['height']:
                        px = frame[sy - base_roi['top'], sx - base_roi['left']]
                        color_rgb = (int(px[2]), int(px[1]), int(px[0]))  # BGR -> RGB
                        monster['color_rgb'] = list(color_rgb)
                except Exception:
                    monster['color_rgb'] = None
                monsters_all.append(monster)
                ctuple = tuple(monster.get('color_rgb') or [])
                matched_style = None
                if ctuple in self.monster_style_map:
                    matched_style = self.monster_style_map[ctuple]
                else:
                    if strict:
                        matched_style = self._match_monster_color(ctuple) if ctuple else None
                    else:
                        if ctuple:
                            closest = self._find_closest_color(ctuple)
                            if closest:
                                matched_style = self.monster_style_map.get(closest)
                if matched_style:
                    monster['combat_style'] = matched_style
                    monsters_kept.append(monster)
        # Log summary with the enforced radius
        logger.debug('[MultiMonster] tiles=%d raw_monsters=%d kept=%d strict=%s radius=%d', len(tiles), len(monsters_all), len(monsters_kept), strict, around_radius)

        # Strict fallback logic: if strict enabled, no kept monsters but raw detections exist
        # Re-run style assignment in non-strict approximate mode (closest color) when enabled by config gate
        if strict and not monsters_kept and monsters_all and self.config_manager.get('multi_monster_strict_fallback', True):
            try:
                logger.debug('[MultiMonster][Fallback] Strict mode yielded 0 monsters; attempting relaxed closest-color matching')
                relaxed_kept: List[Dict[str, Any]] = []
                for monster in monsters_all:
                    ctuple = tuple(monster.get('color_rgb') or [])
                    if not ctuple:
                        continue
                    closest = self._find_closest_color(ctuple)
                    if closest:
                        style = self.monster_style_map.get(closest)
                        if style:
                            monster['combat_style'] = style
                            relaxed_kept.append(monster)
                if relaxed_kept:
                    logger.debug(f"[MultiMonster][Fallback] Recovered {len(relaxed_kept)} monsters via relaxed matching")
                    return relaxed_kept
                else:
                    logger.debug('[MultiMonster][Fallback] No monsters recovered under relaxed matching')
            except Exception as e:
                logger.debug(f'[MultiMonster][Fallback] Error during relaxed matching: {e}')
        return monsters_kept

    # --- Tile bridging ---
    def detect_tiles(self, frame: np.ndarray, roi: Dict[str, int]):
        """Bridge method for tile detection used by legacy calls inside this detector.
        DetectionEngine normally exposes tile detection via self.tile_detector.
        Provide a thin wrapper so multi-monster specific test paths (panel) can call
        detector.detect_tiles(...) without attribute errors.
        Returns list of tile dicts with 'center_x','center_y'.
        """
        try:
            # DetectionEngine (parent) may have tile_detector attribute
            td = getattr(self, 'tile_detector', None)
            if td is None:
                logger.debug("[MultiMonsterDetector] No tile_detector present; returning empty tile list (bridge)")
                return []
            points = td.detect_tiles(frame, roi)
            # Convert simple (x,y) tuples -> dicts for downstream compatibility
            out = []
            for p in points:
                try:
                    x, y = p
                    out.append({'center_x': int(x), 'center_y': int(y)})
                except Exception:
                    pass
            return out
        except Exception as e:
            logger.error(f"Error in detect_tiles bridge: {e}")
            return []
    
    def _find_closest_color(self, color: Tuple[int, int, int]) -> Optional[Tuple[int, int, int]]:
        """
        Find the closest color match in the monster style map
        
        Args:
            color: RGB color tuple
            
        Returns:
            Closest matching color tuple or None if no colors in map
        """
        if not self.monster_style_map:
            return None
        
        closest_color = None
        min_distance = float('inf')
        
        for map_color in self.monster_style_map.keys():
            # Calculate Euclidean distance in RGB space
            distance = sum((c1 - c2) ** 2 for c1, c2 in zip(color, map_color)) ** 0.5
            if distance < min_distance:
                min_distance = distance
                closest_color = map_color
        
        return closest_color
    
    def detect_weapon(self, frame: np.ndarray) -> Optional[str]:
        """
        Detect the currently equipped weapon based on color
        
        Args:
            frame: Captured frame
            
        Returns:
            Detected weapon type ('melee', 'ranged', 'magic') or None if not detected
        """
        try:
            roi = self.config_manager.get_roi('weapon_roi')
            if not roi:
                return None
            
            weapon_frame = self.capture_service.capture_region(roi)
            if weapon_frame is None:
                return None
            
            specs = {
                'melee': self.config_manager.get_color_spec('multi_monster_melee_weapon_color'),
                'ranged': self.config_manager.get_color_spec('multi_monster_ranged_weapon_color'),
                'magic': self.config_manager.get_color_spec('multi_monster_magic_weapon_color'),
            }
            
            # Filter out None values
            specs = {k: v for k, v in specs.items() if v is not None}
            
            # Get lab tolerance from config (clamp to a reasonable minimum)
            lab_tolerance = max(int(self.config_manager.get('weapon_lab_tolerance', 15)), 12)

            # Allow independent S/V minima for weapon ROI (icons often desaturated)
            weapon_sat_min = int(self.config_manager.get('weapon_sat_min', 20))
            weapon_val_min = int(self.config_manager.get('weapon_val_min', 30))
            
            # Configure detection parameters
            config = {
                'combat_lab_tolerance': lab_tolerance,
                'combat_sat_min': weapon_sat_min,
                'combat_val_min': weapon_val_min,
                'combat_morph_open_iters': self.config_manager.get('multi_monster_morph_open_iters', 1),
                'combat_morph_close_iters': self.config_manager.get('multi_monster_morph_close_iters', 2),
            }
            
            counts = {}
            debug_details = {}
            for style, spec in specs.items():
                try:
                    # Optionally loosen gating for melee if configured (dark/low-chroma icons)
                    if style == 'melee' and self.config_manager.get('weapon_melee_loosen', True):
                        melee_config = dict(config)
                        melee_config['combat_lab_tolerance'] = max(lab_tolerance, int(self.config_manager.get('weapon_melee_lab_min', 18)))
                        melee_config['combat_sat_min'] = 0
                        melee_config['combat_val_min'] = 0
                        mask, _ = build_mask_precise_small(weapon_frame, spec, melee_config, step=1, min_area=0)
                    else:
                        mask, _ = build_mask_precise_small(weapon_frame, spec, config, step=1, min_area=0)
                    cnt = int(cv2.countNonZero(mask))
                    counts[style] = cnt
                    debug_details[style] = {
                        'rgb': spec.rgb,
                        'tol_rgb': spec.tol_rgb,
                        'tol_h': spec.tol_h,
                        'tol_s': spec.tol_s,
                        'tol_v': spec.tol_v,
                        'pixels': cnt
                    }
                except Exception as e:
                    counts[style] = 0
                    debug_details[style] = {'error': str(e)}

            # Optional template-assist path to help detect very dark/low-chroma icons
            try:
                if self.config_manager.get('weapon_template_enable', True):
                    # Determine a search subwindow inside weapon_frame if a click position is available
                    search_win_px = int(self.config_manager.get('weapon_template_window', 0) or 0)
                    # Build simple per-style bbox around configured click positions if present
                    def style_search_roi(base_img: np.ndarray, style_key: str) -> np.ndarray:
                        if search_win_px <= 0:
                            return base_img
                        pos_key = f'multi_monster_{style_key}_weapon_position'
                        pos = self.config_manager.get(pos_key)
                        if not pos or 'x' not in pos or 'y' not in pos:
                            return base_img
                        # Convert absolute click position to local ROI coords
                        # weapon_frame is an absolute capture of roi; compute local offsets
                        try:
                            wr = self.config_manager.get_roi('weapon_roi')
                            if not wr:
                                return base_img
                            left = int(getattr(wr, 'left', 0))
                            top = int(getattr(wr, 'top', 0))
                            x_local = int(pos['x'] - left)
                            y_local = int(pos['y'] - top)
                            h, w = base_img.shape[:2]
                            half = int(max(8, search_win_px // 2))
                            x0 = max(0, x_local - half)
                            y0 = max(0, y_local - half)
                            x1 = min(w, x_local + half)
                            y1 = min(h, y_local + half)
                            if (x1 - x0) >= 8 and (y1 - y0) >= 8:
                                return base_img[y0:y1, x0:x1]
                        except Exception:
                            pass
                        return base_img

                    def load_template(style_key: str) -> Optional[np.ndarray]:
                        # Cache loaded templates
                        if style_key in self._weapon_templates and self._weapon_templates[style_key] is not None:
                            return self._weapon_templates[style_key]
                        path_key = f'weapon_{style_key}_template_path'
                        tpath = self.config_manager.get(path_key)
                        if not tpath:
                            self._weapon_templates[style_key] = None
                            return None
                        try:
                            tmpl = cv2.imread(str(tpath), cv2.IMREAD_UNCHANGED)
                            if tmpl is None:
                                logger.warning(f"[MultiMonster][Template] Failed to read template at {tpath} for {style_key}")
                                self._weapon_templates[style_key] = None
                                return None
                            # Convert to BGR and optionally keep alpha mask
                            if tmpl.ndim == 2:
                                tmpl_bgr = cv2.cvtColor(tmpl, cv2.COLOR_GRAY2BGR)
                                alpha = None
                            elif tmpl.shape[2] == 4:
                                bgr = tmpl[:, :, :3]
                                alpha = tmpl[:, :, 3]
                                tmpl_bgr = bgr
                            else:
                                tmpl_bgr = tmpl
                                alpha = None
                            # For edge mode, precompute edges
                            mode = str(self.config_manager.get('weapon_template_mode', 'edge')).lower()
                            if mode == 'edge':
                                tmpl_gray = cv2.cvtColor(tmpl_bgr, cv2.COLOR_BGR2GRAY)
                                t_edges = cv2.Canny(tmpl_gray, 50, 150)
                                self._weapon_templates[style_key] = t_edges  # type: ignore[assignment]
                            else:
                                self._weapon_templates[style_key] = cv2.cvtColor(tmpl_bgr, cv2.COLOR_BGR2GRAY)  # type: ignore[assignment]
                            return self._weapon_templates[style_key]
                        except Exception as e:
                            logger.debug(f"[MultiMonster][Template] Error loading template for {style_key}: {e}")
                            self._weapon_templates[style_key] = None
                            return None

                    # Run template matching where color counts are low
                    mode = str(self.config_manager.get('weapon_template_mode', 'edge')).lower()
                    thr = float(self.config_manager.get('weapon_template_threshold', 0.58))
                    for style in list(specs.keys()):
                        # Only attempt if counts look too small to pass thresholds
                        if counts.get(style, 0) >= int(self.config_manager.get('weapon_min_pixels', 20)):
                            continue
                        tmpl = load_template(style)
                        if tmpl is None:
                            continue
                        # Prepare search image
                        search_img = weapon_frame.copy()
                        search_img = style_search_roi(search_img, style)
                        if search_img is None or search_img.size == 0:
                            continue
                        try:
                            if mode == 'edge':
                                gray = cv2.cvtColor(search_img, cv2.COLOR_BGR2GRAY)
                                edges = cv2.Canny(gray, 50, 150)
                                hay = edges
                                needle = tmpl
                            else:
                                hay = cv2.cvtColor(search_img, cv2.COLOR_BGR2GRAY)
                                needle = tmpl
                            if hay.shape[0] < needle.shape[0] or hay.shape[1] < needle.shape[1]:
                                continue
                            res = cv2.matchTemplate(hay, needle, cv2.TM_CCOEFF_NORMED)
                            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                            debug_details.setdefault(style, {})['template_score'] = float(max_val)
                            if max_val >= thr:
                                # Optionally influence equipped detection if enabled
                                if bool(self.config_manager.get('weapon_template_affects_equipped', False)):
                                    min_pix = int(self.config_manager.get('weapon_min_pixels', 20))
                                    # Make sure templated style wins over others by a small margin
                                    max_other = 0
                                    if counts:
                                        max_other = max(v for k, v in counts.items() if k != style) if any(k != style for k in counts.keys()) else 0
                                    target = max(min_pix, max_other + 1)
                                    counts[style] = max(counts.get(style, 0), target)
                                    debug_details.setdefault(style, {})['template_assisted'] = True
                                else:
                                    # Record the score but don't change counts
                                    debug_details.setdefault(style, {})['template_assisted'] = True
                        except Exception:
                            pass
            except Exception:
                pass

            # If we got absolutely nothing, try a relaxed retry: looser Lab, no S/V gating
            if counts and sum(counts.values()) == 0:
                relaxed_config = {
                    'combat_lab_tolerance': max(lab_tolerance, 18),
                    'combat_sat_min': 0,
                    'combat_val_min': 0,
                    'combat_morph_open_iters': config.get('combat_morph_open_iters', 1),
                    'combat_morph_close_iters': config.get('combat_morph_close_iters', 2),
                }
                relaxed_counts = {}
                try:
                    for style, spec in specs.items():
                        mask, _ = build_mask_precise_small(weapon_frame, spec, relaxed_config, step=1, min_area=0)
                        relaxed_counts[style] = int(cv2.countNonZero(mask))
                except Exception:
                    relaxed_counts = {}
                if relaxed_counts and sum(relaxed_counts.values()) > 0:
                    logger.debug(f"[MultiMonster][WeaponDetect][Relaxed] Recovered signal with relaxed gating counts={relaxed_counts} from zero initial counts; lab_tol={relaxed_config['combat_lab_tolerance']}")
                    counts = relaxed_counts
            
            # Get minimum pixel threshold (lower default to 20 for equipped detection)
            min_pixels = int(self.config_manager.get('weapon_min_pixels', 20))
            # Soft floor ratio + absolute adaptive floor for low-signal UIs
            soft_ratio = float(self.config_manager.get('weapon_soft_floor_ratio', 0.4))  # e.g. 40% of min_pixels
            adaptive_floor = int(self.config_manager.get('weapon_adaptive_min_pixels', 5))  # reuse same key as visible styles
            persistence_seconds = float(self.config_manager.get('weapon_persistence_seconds', 1.5))

            # Determine detected weapon (primary hard threshold path)
            eligible = [k for k in counts.keys() if counts[k] >= min_pixels]
            chosen: Optional[str] = None
            reason = None
            if eligible:
                if len(eligible) == 1:
                    chosen = eligible[0]
                    reason = f">=min_pixels({min_pixels})"
                else:
                    chosen = max(eligible, key=lambda k: counts[k])
                    reason = f"multi>=min_pixels({min_pixels})"
            else:
                # Adaptive acceptance: accept top style if it reaches soft_ratio*min_pixels OR absolute adaptive_floor
                if counts:
                    best = max(counts, key=lambda k: counts[k])
                    best_val = counts[best]
                    soft_floor = max(adaptive_floor, int(min_pixels * soft_ratio))
                    if best_val >= soft_floor:
                        chosen = best
                        reason = f"soft_floor({soft_floor}) counts={counts}"
                    else:
                        logger.debug(f"[MultiMonster][WeaponDetect] No style above thresholds min_pixels={min_pixels} soft_floor={soft_floor} counts={counts} details={debug_details} sat_min={config['combat_sat_min']} val_min={config['combat_val_min']} lab_tol={lab_tolerance}")
                else:
                    logger.debug(f"[MultiMonster][WeaponDetect] Empty counts map (no specs?)")

            # Inference fallback: if exactly two styles are visible (via visible_weapon_styles) and one is missing,
            # infer the equipped style as the missing one (common when the equipped icon is dark/low-chroma).
            if not chosen and self.config_manager.get('weapon_infer_current_from_missing', True):
                try:
                    vis = self.visible_weapon_styles(frame)
                    if isinstance(vis, dict):
                        present = set(vis.keys())
                        all_styles = set(specs.keys())
                        missing = list(all_styles - present)
                        if len(present) >= 2 and len(missing) == 1:
                            chosen = missing[0]
                            reason = f"inferred_from_missing_visible({sorted(present)})"
                except Exception:
                    pass

            # Short-term persistence: if nothing chosen THIS frame but we recently had a style, keep it to prevent jitter
            now_ts = time.time()
            if not chosen and self.last_detected_style and (now_ts - self.last_style_change_time) < persistence_seconds:
                chosen = self.last_detected_style
                reason = f"persistence({self.last_detected_style},{round(now_ts - self.last_style_change_time,2)}s)"

            if chosen:
                if chosen != self.last_detected_style:
                    self.last_detected_style = chosen
                    self.last_style_change_time = now_ts
                logger.debug(f"[MultiMonster][WeaponDetect] equipped={chosen} reason={reason} counts={counts} min_pixels={min_pixels} soft_ratio={soft_ratio} adaptive_floor={adaptive_floor}")
                return chosen
            return None
        
        except Exception as e:
            logger.error(f"Error detecting weapon: {e}")
            return None

    def visible_weapon_styles(self, frame: np.ndarray) -> Dict[str, int]:
        """Return dict of weapon styles whose color is currently VISIBLE in weapon ROI.
        This represents styles AVAILABLE to click (i.e., NOT currently equipped) under the
        user's specified semantic model where an equipped style's color becomes hidden.
        Returns empty dict on failure.
        """
        out: Dict[str, int] = {}
        try:
            roi = self.config_manager.get_roi('weapon_roi')
            if not roi:
                logger.debug("[MultiMonster][WeaponStyles] weapon_roi not set")
                return out
            weapon_frame = self.capture_service.capture_region(roi)
            if weapon_frame is None:
                logger.debug("[MultiMonster][WeaponStyles] capture_region returned None")
                return out
            specs = {
                'melee': self.config_manager.get_color_spec('multi_monster_melee_weapon_color'),
                'ranged': self.config_manager.get_color_spec('multi_monster_ranged_weapon_color'),
                'magic': self.config_manager.get_color_spec('multi_monster_magic_weapon_color'),
            }
            specs = {k: v for k, v in specs.items() if v is not None}
            if not specs:
                logger.debug("[MultiMonster][WeaponStyles] No weapon color specs configured")
            lab_tolerance = max(int(self.config_manager.get('weapon_lab_tolerance', 15)), 12)
            weapon_sat_min = int(self.config_manager.get('weapon_sat_min', 20))
            weapon_val_min = int(self.config_manager.get('weapon_val_min', 30))
            config = {
                'combat_lab_tolerance': lab_tolerance,
                'combat_sat_min': weapon_sat_min,
                'combat_val_min': weapon_val_min,
                'combat_morph_open_iters': self.config_manager.get('multi_monster_morph_open_iters', 1),
                'combat_morph_close_iters': self.config_manager.get('multi_monster_morph_close_iters', 2),
            }
            # Visibility acceptance rules (separate from equipped detection)
            min_pixels = int(self.config_manager.get('weapon_visible_min_pixels', 13))
            adaptive_enable = True
            adaptive_ratio = float(self.config_manager.get('weapon_visible_ratio', 0.40))
            adaptive_floor = int(self.config_manager.get('weapon_visible_floor', 5))
            adaptive_secondary = True
            debug_counts = {}
            debug_specs = {}
            for style, spec in specs.items():
                try:
                    mask, _ = build_mask_precise_small(weapon_frame, spec, config, step=1, min_area=0)
                    cnt = int(cv2.countNonZero(mask))
                    debug_counts[style] = cnt
                    debug_specs[style] = {'rgb': spec.rgb, 'tol_rgb': spec.tol_rgb, 'tol_h': spec.tol_h, 'tol_s': spec.tol_s, 'tol_v': spec.tol_v}
                    if cnt >= min_pixels:
                        out[style] = cnt
                except Exception as e:
                    debug_counts[style] = 0
                    debug_specs[style] = {'error': str(e)}

            # If zero across the board, attempt a relaxed retry to seed adaptive logic
            if debug_counts and sum(debug_counts.values()) == 0:
                relaxed_config = {
                    'combat_lab_tolerance': max(lab_tolerance, 18),
                    'combat_sat_min': 0,
                    'combat_val_min': 0,
                    'combat_morph_open_iters': config.get('combat_morph_open_iters', 1),
                    'combat_morph_close_iters': config.get('combat_morph_close_iters', 2),
                }
                relaxed_counts = {}
                try:
                    for style, spec in specs.items():
                        mask, _ = build_mask_precise_small(weapon_frame, spec, relaxed_config, step=1, min_area=0)
                        relaxed_counts[style] = int(cv2.countNonZero(mask))
                except Exception:
                    relaxed_counts = {}
                if relaxed_counts and sum(relaxed_counts.values()) > 0:
                    logger.debug(f"[MultiMonster][WeaponStyles][Relaxed] Recovered signal with relaxed gating counts={relaxed_counts} from zero initial counts; lab_tol={relaxed_config['combat_lab_tolerance']}")
                    debug_counts = relaxed_counts
                    # Re-apply absolute acceptance on relaxed counts
                    for k, v in relaxed_counts.items():
                        if v >= min_pixels:
                            out[k] = v
            # Adaptive acceptance: add styles within ratio*max and above floor.
            if adaptive_enable and debug_counts and (adaptive_secondary or not out):
                max_style = max(debug_counts, key=lambda k: debug_counts[k])
                max_val = debug_counts[max_style]
                if max_val >= adaptive_floor:
                    # Accept any style whose count is within ratio * max_val
                    adaptive_selected = {k: v for k, v in debug_counts.items() if v >= adaptive_ratio * max_val and v >= adaptive_floor}
                    if adaptive_selected:
                        # If some styles already passed absolute min, only add new ones from adaptive to avoid duplicates
                        added = {k: v for k, v in adaptive_selected.items() if k not in out}
                        if added:
                            out.update(added)
                            logger.debug(f"[MultiMonster][WeaponStyles][Adaptive{'-Secondary' if adaptive_secondary else ''}] ratio={adaptive_ratio} floor={adaptive_floor} max_val={max_val} added={added}")
            # Template assist for visible styles: if a template PASS occurs for a style below color thresholds, mark it visible
            try:
                if self.config_manager.get('weapon_template_enable', True):
                    mode = str(self.config_manager.get('weapon_template_mode', 'edge')).lower()
                    thr = float(self.config_manager.get('weapon_template_threshold', 0.58))
                    search_win_px = int(self.config_manager.get('weapon_template_window', 0) or 0)

                    def _style_search_img(base_img: np.ndarray, style_key: str) -> np.ndarray:
                        if search_win_px <= 0:
                            return base_img
                        pos_key = f'multi_monster_{style_key}_weapon_position'
                        pos = self.config_manager.get(pos_key)
                        try:
                            wr = self.config_manager.get_roi('weapon_roi')
                        except Exception:
                            wr = None
                        if not pos or not wr:
                            return base_img
                        try:
                            left = int(getattr(wr, 'left', 0))
                            top = int(getattr(wr, 'top', 0))
                            x_local = int(pos['x'] - left)
                            y_local = int(pos['y'] - top)
                            h, w = base_img.shape[:2]
                            half = int(max(8, search_win_px // 2))
                            x0 = max(0, x_local - half)
                            y0 = max(0, y_local - half)
                            x1 = min(w, x_local + half)
                            y1 = min(h, y_local + half)
                            if (x1 - x0) >= 8 and (y1 - y0) >= 8:
                                return base_img[y0:y1, x0:x1]
                        except Exception:
                            pass
                        return base_img

                    def _load_tmpl(style_key: str) -> Optional[np.ndarray]:
                        path_key = f'weapon_{style_key}_template_path'
                        tpath = self.config_manager.get(path_key)
                        if not tpath:
                            return None
                        try:
                            t = cv2.imread(str(tpath), cv2.IMREAD_UNCHANGED)
                            if t is None:
                                return None
                            if t.ndim == 2:
                                gray = t
                            else:
                                gray = cv2.cvtColor(t[:, :, :3], cv2.COLOR_BGR2GRAY)
                            if mode == 'edge':
                                return cv2.Canny(gray, 50, 150)
                            return gray
                        except Exception:
                            return None

                    for style in list(specs.keys()):
                        # Skip if already visible
                        if style in out:
                            continue
                        tmpl = _load_tmpl(style)
                        if tmpl is None:
                            continue
                        search = _style_search_img(weapon_frame.copy(), style)
                        if search is None or search.size == 0:
                            continue
                        hay = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
                        if mode == 'edge':
                            hay = cv2.Canny(hay, 50, 150)
                        if hay.shape[0] < tmpl.shape[0] or hay.shape[1] < tmpl.shape[1]:
                            continue
                        try:
                            res = cv2.matchTemplate(hay, tmpl, cv2.TM_CCOEFF_NORMED)
                            _, max_val, _, _ = cv2.minMaxLoc(res)
                            if max_val >= thr:
                                out[style] = max(min_pixels, debug_counts.get(style, 0))
                                logger.debug(f"[MultiMonster][WeaponStyles][Template] Added visible style via template PASS: {style} score={max_val:.3f} thr={thr}")
                        except Exception:
                            continue
            except Exception:
                pass
            # Magic lenient inclusion: include magic if above magic_visible_floor even when below thresholds
            try:
                magic_floor = int(self.config_manager.get('weapon_magic_visible_floor', 8))
                magic_lenient = bool(self.config_manager.get('weapon_magic_lenient_visible', True))
                if magic_lenient and 'magic' in debug_counts and debug_counts.get('magic', 0) >= magic_floor:
                    if 'magic' not in out:
                        out['magic'] = debug_counts['magic']
                        logger.debug(f"[MultiMonster][WeaponStyles][MagicLenient] Included magic at {debug_counts['magic']} >= floor {magic_floor}")
            except Exception:
                pass
            # ROI object may be a dataclass or simple dict; extract safely for logging
            try:
                if isinstance(roi, dict):
                    rl = roi.get('left'); rt = roi.get('top'); rw = roi.get('width'); rh = roi.get('height')
                else:
                    rl = getattr(roi, 'left', None); rt = getattr(roi, 'top', None); rw = getattr(roi, 'width', None); rh = getattr(roi, 'height', None)
                # Compute ROI mean color for context
                try:
                    mean_bgr = weapon_frame.mean(axis=(0,1))
                    mean_rgb = (int(mean_bgr[2]), int(mean_bgr[1]), int(mean_bgr[0]))
                except Exception:
                    mean_rgb = None
                logger.debug(f"[MultiMonster][WeaponStyles] roi=({rl},{rt},{rw},{rh}) min_pixels={min_pixels} counts={debug_counts} visible={out} specs={debug_specs} mean_rgb={mean_rgb} sat_min={weapon_sat_min} val_min={weapon_val_min} lab_tol={lab_tolerance} adaptive_enable={adaptive_enable} ratio={adaptive_ratio} floor={adaptive_floor}")
            except Exception:
                logger.debug(f"[MultiMonster][WeaponStyles] min_pixels={min_pixels} counts={debug_counts} visible={out} specs={debug_specs} adaptive_enable={adaptive_enable}")
        except Exception as e:
            logger.error(f"Error computing visible weapon styles: {e}")
        return out

    def get_click_point_for_style(self, style: str) -> Optional[Dict[str, int]]:
        """Compute a click point inside weapon_roi for the given style.
        Tries color-mask largest contour centroid; falls back to template match center.
        Returns absolute screen coordinates {x, y} or None if unavailable.
        """
        try:
            roi = self.config_manager.get_roi('weapon_roi')
            if not roi:
                return None
            # Normalize ROI to absolute coordinates to match capture_region behavior
            def _roi_abs_ltwh(_roi):
                try:
                    rdict = _roi.to_dict() if hasattr(_roi, 'to_dict') else dict(_roi)
                except Exception:
                    rdict = {
                        'left': int(getattr(_roi, 'left', 0)),
                        'top': int(getattr(_roi, 'top', 0)),
                        'width': int(getattr(_roi, 'width', 0)),
                        'height': int(getattr(_roi, 'height', 0)),
                        'mode': getattr(_roi, 'mode', 'absolute') if hasattr(_roi, 'mode') else 'absolute'
                    }
                l = int(rdict.get('left', 0)); t = int(rdict.get('top', 0))
                w = int(rdict.get('width', 0)); h = int(rdict.get('height', 0))
                mode = str(rdict.get('mode', 'absolute'))
                try:
                    bbox = self.capture_service.get_window_bbox()
                    within_abs_window = (
                        l >= bbox['left'] - 2 and l <= bbox['left'] + bbox['width'] + 2 and
                        t >= bbox['top'] - 2 and t <= bbox['top'] + bbox['height'] + 2
                    )
                    looks_relative = (l < bbox['width'] and t < bbox['height'] and w <= bbox['width'] and h <= bbox['height'])
                    if mode == 'relative' or (not within_abs_window and looks_relative):
                        l = bbox['left'] + l
                        t = bbox['top'] + t
                except Exception:
                    pass
                return l, t, w, h
            rl, rt, rw, rh = _roi_abs_ltwh(roi)
            weapon_frame = self.capture_service.capture_region(roi)
            if weapon_frame is None:
                return None
            spec_map = {
                'melee': self.config_manager.get_color_spec('multi_monster_melee_weapon_color'),
                'ranged': self.config_manager.get_color_spec('multi_monster_ranged_weapon_color'),
                'magic': self.config_manager.get_color_spec('multi_monster_magic_weapon_color'),
            }
            spec = spec_map.get(style)
            if spec is None:
                return None
            # Use same gating as visibility for consistency
            lab_tolerance = max(int(self.config_manager.get('weapon_lab_tolerance', 15)), 12)
            weapon_sat_min = int(self.config_manager.get('weapon_sat_min', 20))
            weapon_val_min = int(self.config_manager.get('weapon_val_min', 30))
            config = {
                'combat_lab_tolerance': lab_tolerance,
                'combat_sat_min': weapon_sat_min,
                'combat_val_min': weapon_val_min,
                'combat_morph_open_iters': self.config_manager.get('multi_monster_morph_open_iters', 1),
                'combat_morph_close_iters': self.config_manager.get('multi_monster_morph_close_iters', 2),
            }
            try:
                mask, _ = build_mask_precise_small(weapon_frame, spec, config, step=1, min_area=0)
                # Find largest contour
                contours, _hier = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    largest = max(contours, key=cv2.contourArea)
                    x, y, w, h = cv2.boundingRect(largest)
                    cx = rl + x + w // 2
                    cy = rt + y + h // 2
                    # Clamp to ROI bounds as a safety
                    cx = max(rl, min(rl + (rw - 1 if rw > 0 else 0), int(cx)))
                    cy = max(rt, min(rt + (rh - 1 if rh > 0 else 0), int(cy)))
                    return {'x': int(cx), 'y': int(cy)}
                else:
                    # Relaxed retry: loosen Lab tolerance and remove S/V gating to recover low-chroma icons
                    relaxed_config = {
                        'combat_lab_tolerance': max(lab_tolerance, int(self.config_manager.get('weapon_click_relaxed_lab_min', 20))),
                        'combat_sat_min': 0,
                        'combat_val_min': 0,
                        'combat_morph_open_iters': config.get('combat_morph_open_iters', 1),
                        'combat_morph_close_iters': config.get('combat_morph_close_iters', 2),
                    }
                    try:
                        rmask, _ = build_mask_precise_small(weapon_frame, spec, relaxed_config, step=1, min_area=0)
                        rcontours, _ = cv2.findContours(rmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        if rcontours:
                            largest = max(rcontours, key=cv2.contourArea)
                            x, y, w, h = cv2.boundingRect(largest)
                            cx = rl + x + w // 2
                            cy = rt + y + h // 2
                            cx = max(rl, min(rl + (rw - 1 if rw > 0 else 0), int(cx)))
                            cy = max(rt, min(rt + (rh - 1 if rh > 0 else 0), int(cy)))
                            return {'x': int(cx), 'y': int(cy)}
                    except Exception:
                        pass
            except Exception:
                pass
            # Fallback: template center if available
            try:
                if self.config_manager.get('weapon_template_enable', True):
                    mode = str(self.config_manager.get('weapon_template_mode', 'edge')).lower()
                    thr = float(self.config_manager.get('weapon_template_threshold', 0.58))
                    # Optional multi-scale support to tolerate UI scaling
                    scales_cfg = self.config_manager.get('weapon_template_scales')
                    if isinstance(scales_cfg, (list, tuple)) and scales_cfg:
                        scales = [float(s) for s in scales_cfg if isinstance(s, (int, float))]
                    else:
                        scales = [1.0, 0.95, 1.05, 0.9, 1.1]
                    # Load template via the helper used earlier
                    def _load_tmpl(style_key: str) -> Optional[np.ndarray]:
                        path_key = f'weapon_{style_key}_template_path'
                        tpath = self.config_manager.get(path_key)
                        if not tpath:
                            return None
                        t = cv2.imread(str(tpath), cv2.IMREAD_UNCHANGED)
                        if t is None:
                            return None
                        if t.ndim == 2:
                            gray = t
                        else:
                            gray = cv2.cvtColor(t[:, :, :3], cv2.COLOR_BGR2GRAY)
                        if mode == 'edge':
                            return cv2.Canny(gray, 50, 150)
                        return gray
                    tmpl = _load_tmpl(style)
                    if tmpl is not None and weapon_frame.size > 0:
                        hay_full = cv2.cvtColor(weapon_frame, cv2.COLOR_BGR2GRAY)
                        if mode == 'edge':
                            hay_full = cv2.Canny(hay_full, 50, 150)
                        best_score = -1.0
                        best_center = None
                        for s in scales:
                            try:
                                if abs(s - 1.0) < 1e-3:
                                    needle = tmpl
                                else:
                                    new_w = max(8, int(tmpl.shape[1] * s))
                                    new_h = max(8, int(tmpl.shape[0] * s))
                                    needle = cv2.resize(tmpl, (new_w, new_h), interpolation=cv2.INTER_AREA)
                                if hay_full.shape[0] < needle.shape[0] or hay_full.shape[1] < needle.shape[1]:
                                    continue
                                res = cv2.matchTemplate(hay_full, needle, cv2.TM_CCOEFF_NORMED)
                                _min_v, max_v, _min_l, max_l = cv2.minMaxLoc(res)
                                if max_v > best_score:
                                    best_score = float(max_v)
                                    tx, ty = max_l
                                    cx = rl + tx + needle.shape[1] // 2
                                    cy = rt + ty + needle.shape[0] // 2
                                    best_center = (int(cx), int(cy))
                            except Exception:
                                continue
                        if best_center is not None and best_score >= thr:
                            cx, cy = best_center
                            # Clamp to ROI bounds as a safety
                            cx = max(rl, min(rl + (rw - 1 if rw > 0 else 0), int(cx)))
                            cy = max(rt, min(rt + (rh - 1 if rh > 0 else 0), int(cy)))
                            return {'x': int(cx), 'y': int(cy)}
            except Exception:
                pass
        except Exception:
            return None
        return None
    
    def process_multi_monster_mode(self, frame: np.ndarray, base_roi: Dict[str, int]) -> Dict[str, Any]:
        """
        Process the multi monster mode detection cycle
        
        Args:
            frame: Captured frame
            base_roi: Base region of interest
            
        Returns:
            Dictionary with detection results
        """
        result = {
            'in_combat': False,
            'monsters': [],
            'target': None,
            'current_style': None,
            'required_style': None,
            'weapon_match': False,
            'action': None
        }
        
        # Check if in combat
        result['in_combat'] = self.is_in_combat()
        if result['in_combat']:
            logger.debug("[MultiMonsterDetector] Combat state true (HP bar detected); skipping monster logic")
        
        if result['in_combat']:
            logger.debug("In combat, skipping detection")
            return result
        
    # Detect monsters with styles (already filtered strictly if multi_monster_strict_colors True)
        monsters = self.detect_monsters_with_styles(frame, base_roi)
        result['monsters'] = monsters
        
        if not monsters:
            logger.debug("No monsters detected")
            return result
        
        # Select target (largest monster)
        target = max(monsters, key=lambda m: m.get('area', 0))
        result['target'] = target
        
        # Get required combat style for target
        required_style = target.get('combat_style', 'melee')
        result['required_style'] = required_style

        # Diagnostic: style distribution across detected monsters
        try:
            style_counts = {}
            for m in monsters:
                s = m.get('combat_style')
                if s:
                    style_counts[s] = style_counts.get(s, 0) + 1
            logger.debug(f"[MultiMonster] style_counts={style_counts} required_style={required_style}")
        except Exception:
            pass
        
        # Detect current equipped weapon style for observability only (not used for decision)
        current_style = self.detect_weapon(frame)
        result['current_style'] = current_style
        # Compute visible styles strictly within the Weapon ROI
        visible = self.visible_weapon_styles(frame)
        result['visible_weapon_styles'] = visible
        required_visible = required_style in visible
        result['required_style_visible'] = required_visible
        # Expose whether the weapon for required style appears clickable within the Weapon ROI
        result['weapon_found'] = bool(required_visible)

        # Pure visibility-based decision as requested:
        # If required_style is visible in the Weapon ROI → switch_weapon (assume not equipped yet)
        # If not visible → attack (assume it is already equipped)
        if required_visible:
            action = 'switch_weapon'
            reason = 'required_style_visible_switch'
        else:
            action = 'attack'
            reason = 'required_style_not_visible_attack'
        result['action'] = action
        logger.debug(
            f"[MultiMonster][Decision] required={required_style} visible={list(visible.keys())} required_visible={required_visible} action={action} reason={reason}; equipped(observe-only)={current_style}"
        )
        
        return result
    
    def get_weapon_position(self, style: str) -> Optional[Dict[str, int]]:
        """
        Deprecated: Positional weapon clicks are no longer used. Weapon switching relies on
        dynamic search within the Weapon ROI each cycle (color + template assist).
        """
        return None