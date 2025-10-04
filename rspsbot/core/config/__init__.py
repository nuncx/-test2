"""
Configuration management for RSPS Color Bot v3
"""
import os
import json
import logging
from typing import Any, Dict, Optional, List, Union
from dataclasses import dataclass, field, asdict

# Get module logger
logger = logging.getLogger('rspsbot.core.config')

# Track warnings so we only log certain messages once per process to avoid spam
_warn_once_flags = {
    'tol_rgb_recommended': False,
    'tol_h_recommended': False,
    'tol_s_recommended': False,
    'tol_v_recommended': False,
    'tol_rgb_clamped': False,
    'tol_h_clamped': False,
    'tol_s_clamped': False,
    'tol_v_clamped': False,
}

@dataclass
class ColorSpec:
    """
    Color specification with tolerance settings
    
    Attributes:
        rgb: RGB color tuple (0-255 for each channel)
        tol_rgb: Tolerance for RGB color matching (0-50 recommended)
        use_hsv: Whether to use HSV color space for detection
        tol_h: Hue tolerance for HSV matching (0-20 recommended)
        tol_s: Saturation tolerance for HSV matching (0-100)
        tol_v: Value tolerance for HSV matching (0-100)
    """
    rgb: tuple[int, int, int]
    tol_rgb: int = 8
    use_hsv: bool = True
    tol_h: int = 4
    tol_s: int = 30
    tol_v: int = 30
    
    def __post_init__(self):
        """Validate color specification parameters"""
        # Validate RGB tuple format
        if not isinstance(self.rgb, tuple):
            raise TypeError("RGB must be a tuple")
        
        if len(self.rgb) != 3:
            raise TypeError(f"RGB tuple must have exactly 3 elements, got {len(self.rgb)}")
        
        # Validate RGB values
        if not all(isinstance(c, int) for c in self.rgb):
            raise TypeError("RGB values must be integers")
            
        if not all(0 <= c <= 255 for c in self.rgb):
            raise ValueError(f"RGB values must be between 0 and 255, got {self.rgb}")
        
        # Clamp tolerance values to safe absolute ranges to avoid invalid configs
        # Absolute caps: RGB tol 0-100, H tol 0-60, S/V 0-100
        if self.tol_rgb < 0 or self.tol_rgb > 100:
            original = self.tol_rgb
            self.tol_rgb = max(0, min(100, self.tol_rgb))
            if not _warn_once_flags['tol_rgb_clamped']:
                logger.warning(
                    f"tol_rgb value {original} clamped to {self.tol_rgb} (allowed 0-100)"
                )
                _warn_once_flags['tol_rgb_clamped'] = True
        if self.tol_h < 0 or self.tol_h > 60:
            original = self.tol_h
            self.tol_h = max(0, min(60, self.tol_h))
            if not _warn_once_flags['tol_h_clamped']:
                logger.warning(
                    f"tol_h value {original} clamped to {self.tol_h} (allowed 0-60)"
                )
                _warn_once_flags['tol_h_clamped'] = True
        if self.tol_s < 0 or self.tol_s > 100:
            original = self.tol_s
            self.tol_s = max(0, min(100, self.tol_s))
            if not _warn_once_flags['tol_s_clamped']:
                logger.warning(
                    f"tol_s value {original} clamped to {self.tol_s} (allowed 0-100)"
                )
                _warn_once_flags['tol_s_clamped'] = True
        if self.tol_v < 0 or self.tol_v > 100:
            original = self.tol_v
            self.tol_v = max(0, min(100, self.tol_v))
            if not _warn_once_flags['tol_v_clamped']:
                logger.warning(
                    f"tol_v value {original} clamped to {self.tol_v} (allowed 0-100)"
                )
                _warn_once_flags['tol_v_clamped'] = True

        # Recommend practical ranges (log once to prevent spam during tuning)
        if not 0 <= self.tol_rgb <= 50 and not _warn_once_flags['tol_rgb_recommended']:
            logger.warning("tol_rgb outside recommended range 0-50; higher values can increase false positives")
            _warn_once_flags['tol_rgb_recommended'] = True
        if not 0 <= self.tol_h <= 20 and not _warn_once_flags['tol_h_recommended']:
            logger.warning("tol_h outside recommended range 0-20; consider keeping near target hue range")
            _warn_once_flags['tol_h_recommended'] = True
        if not 0 <= self.tol_s <= 100 and not _warn_once_flags['tol_s_recommended']:
            logger.warning("tol_s outside recommended 0-100")
            _warn_once_flags['tol_s_recommended'] = True
        if not 0 <= self.tol_v <= 100 and not _warn_once_flags['tol_v_recommended']:
            logger.warning("tol_v outside recommended 0-100")
            _warn_once_flags['tol_v_recommended'] = True

@dataclass
class ROI:
    """
    Region of interest on the screen

    Attributes:
        left: Left coordinate of the ROI. For mode 'absolute'/'relative': pixels. For 'percent': 0..1 fraction of window width
        top: Top coordinate of the ROI. For mode 'absolute'/'relative': pixels. For 'percent': 0..1 fraction of window height
        width: Width of the ROI. Pixels unless mode 'percent' (0..1 of window width)
        height: Height of the ROI. Pixels unless mode 'percent' (0..1 of window height)
        mode: 'absolute' (screen), 'relative' (client window pixels), or 'percent' (fractions of client window)
    """
    left: float
    top: float
    width: float
    height: float
    mode: str = 'absolute'  # 'absolute' | 'relative' | 'percent'

    def __post_init__(self):
        """Validate ROI parameters"""
        m = (self.mode or 'absolute').lower()
        if m == 'percent':
            # Allow tiny epsilons but clamp to [0,1]
            if not (0.0 <= float(self.left) <= 1.0 and 0.0 <= float(self.top) <= 1.0):
                raise ValueError(f"Percent ROI left/top must be within 0..1, got ({self.left},{self.top})")
            if not (0.0 < float(self.width) <= 1.0 and 0.0 < float(self.height) <= 1.0):
                raise ValueError(f"Percent ROI width/height must be within (0..1], got ({self.width}x{self.height})")
        else:
            # Pixels
            if int(self.width) <= 0:
                raise ValueError(f"ROI width must be positive, got {self.width}")
            if int(self.height) <= 0:
                raise ValueError(f"ROI height must be positive, got {self.height}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ROI to dictionary format"""
        return {
            "left": float(self.left) if self.mode == 'percent' else int(self.left),
            "top": float(self.top) if self.mode == 'percent' else int(self.top),
            "width": float(self.width) if self.mode == 'percent' else int(self.width),
            "height": float(self.height) if self.mode == 'percent' else int(self.height),
            "mode": self.mode
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ROI':
        """Create ROI from dictionary"""
        mode = str(data.get("mode", 'absolute')).lower()
        # Accept ints or floats
        l = data["left"]; t = data["top"]; w = data["width"]; h = data["height"]
        if mode == 'percent':
            return cls(left=float(l), top=float(t), width=float(w), height=float(h), mode=mode)
        return cls(left=int(l), top=int(t), width=int(w), height=int(h), mode=mode)

@dataclass
class Coordinate:
    """
    XY coordinate on the screen
    
    Attributes:
        x: X coordinate
        y: Y coordinate
        name: Optional name for the coordinate
    """
    x: int
    y: int
    name: str = ""
    
    def __post_init__(self):
        """Validate coordinate parameters"""
        if not isinstance(self.x, int) or not isinstance(self.y, int):
            raise TypeError("Coordinates must be integers")
        if self.x < 0 or self.y < 0:
            logger.warning(f"Negative coordinate values: ({self.x}, {self.y})")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert coordinate to dictionary format"""
        return {
            "x": self.x,
            "y": self.y,
            "name": self.name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Coordinate':
        """Create coordinate from dictionary"""
        return cls(
            x=data["x"],
            y=data["y"],
            name=data.get("name", "")
        )

class ConfigManager:
    """
    Manages configuration settings for the bot
    
    This class handles loading, saving, and accessing configuration settings.
    It also provides validation and default values for settings.
    """
    
    def __init__(self, config_dir: str = "profiles"):
        """
        Initialize the configuration manager
        
        Args:
            config_dir: Directory for configuration profiles
        """
        self.config_dir = config_dir
        os.makedirs(config_dir, exist_ok=True)
        
        # Default configuration
        self._config = self._get_default_config()
        
        # Current profile name
        self.current_profile = None
        
        logger.info("Configuration manager initialized")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values"""
        return {
            # Window settings
            "window_title": "Velador - Donikk",
            # Modes
            "instance_only_mode": False,
            
            # Detection settings
            "scan_interval": 0.2,
            "search_step": 2,
            "detect_tiles": True,
            "detect_monsters": True,
                # Default SEARCH ROI anchored to client window
                "search_roi": ROI(6, 28, 515, 338, mode='relative').to_dict(),
                # Default HP bar ROI anchored to client window
                "hpbar_roi": ROI(25, 79, 100, 17, mode='relative').to_dict(),
            "around_tile_radius": 120,
                # Quick-setup prompt disabled (we hardcode HP bar ROI)
                "roi_quick_setup_on_start": False,
            "monster_scan_step": 1,
            "enable_monster_full_fallback": False,
            "adaptive_search": True,
            "adaptive_monster_detection": True,
            # Temporal persistence (ms)
            "tile_persistence_ms": 300,
            "monster_persistence_ms": 250,
            "monster_sat_min": 40,
            "monster_val_min": 40,
            "monster_exclude_tile_color": True,
            "monster_exclude_tile_dilate": 1,
            "monster_morph_open_iters": 1,
            "monster_morph_close_iters": 2,
            "monster_use_lab_assist": False,
            "monster_lab_tolerance": 22,
            # Cache TTL
            "detection_cache_ttl": 0.08,
            
            # Colors
            "tile_color": asdict(ColorSpec((250, 0, 255), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60)),
            "monster_colors": [
                asdict(ColorSpec((0, 255, 0), tol_rgb=35, tol_h=14, tol_s=70, tol_v=70)),
                asdict(ColorSpec((255, 255, 0), tol_rgb=35, tol_h=14, tol_s=70, tol_v=70))
            ],
            "hpbar_color": asdict(ColorSpec((179, 36, 0), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60)),
            
            # ROIs (explicit defaults; window-anchored)
            "search_roi": ROI(6, 28, 515, 338, mode='relative').to_dict(),
            "hpbar_roi": ROI(25, 79, 100, 17, mode='relative').to_dict(),
            # Quick-setup prompt disabled (fixed ROIs applied automatically)
            "roi_quick_setup_on_start": False,
            # ROI behavior
            "hpbar_roi_follow_window": True,  # when true, store HP ROI as client-relative so it follows window
            
            # Combat settings
            "hpbar_detect_enabled": True,
            "hpbar_min_area": 50,
            "hpbar_min_pixel_matches": 150,
            "post_combat_delay_min_s": 1.0,
            "post_combat_delay_max_s": 3.0,
            "combat_not_seen_timeout_s": 10.0,
            "combat_leave_immediately": True,
            "skip_detection_when_in_combat": True,
            
            # Camera adjustment
            "enable_cam_adjust": True,
            "cam_adjust_keys": ["up", "down", "right"],
            "cam_adjust_hold_s": 0.08,
            "cam_adjust_gap_s": 0.03,
            "micro_adjust_keys": ["right"],
            "micro_adjust_hold_s": 0.04,
            "micro_adjust_gap_s": 0.03,
            "micro_adjust_every_loops": 8,
            
            # Click settings
            "click_delay": 0.05,
            "click_after_found_sleep": 0.4,
            "min_monster_click_cooldown_s": 0.8,
            "min_monster_click_distance_enabled": True,
            "min_monster_click_distance_px": 12,
            "attack_grace_s": 0.6,
            # Low-confidence click mode
            "low_confidence_click_enabled": True,
            "low_confidence_area_threshold": 220.0,
            "low_conf_min_count": 3,
            
            # Humanization
            "humanize_on": True,
            "break_every_s": 180.0,
            "break_duration_s": 4.0,
            "max_runtime_s": 0.0,
            
            # Debug settings
            "debug_overlay": False,
            "overlay_mode": "tile",
            "show_overlay_counts": True,
            "overlay_clip_to_roi": False,
            "overlay_follow_window": False,
            "debug_save_snapshots": False,
            "debug_output_dir": "outputs",

            # Chat watcher defaults
            "chat_enabled": False,
            # OCR language for Tesseract (e.g., 'eng', 'deu', or 'eng+por')
            "chat_ocr_lang": "eng",
            # Default Chat ROI anchored to client window (requested defaults)
            "chat_roi": ROI(5, 367, 510, 118, mode='relative').to_dict(),
            "chat_poll_ms": 600,
            "chat_min_confidence": 65,
            "chat_normalize_case": True,
            # Color verification thresholds for chat line matching (lowered for small text)
            "chat_color_verify_min_ratio": 0.01,   # 1% of bbox pixels must match target color
            "chat_color_verify_min_pixels": 15,    # or at least this many pixels
            "chat_debug_save": False,              # when true, save debug crops/masks of matched lines
            # Optional template verification (grayscale NCC); if a template path is set for a pattern,
            # the match must exceed the threshold in addition to color verification
            "chat_template_enable": False,
            "chat_template_threshold": 0.7,
            "chat_template_ybr_path": None,
            "chat_template_prayer_disabled_path": None,
            "chat_template_rebirth_disabled_path": None,
            # Simple trigger templates; users can edit in GUI
            "chat_triggers": [
                {"pattern": "Your prayers have been disabled!", "regex": False, "action": "enable_prayer"},
                {"pattern": "YOU BETTER RUN!", "regex": False, "action": "click_ybr_tile"},
                {"pattern": "Rebirth Demon disabled your prayers", "regex": False, "action": "enable_prayer"}
            ],
            # Action parameters: coordinates and colors used by chat actions
            # Coordinate is stored window-relative; converted to absolute at click time
            "chat_prayer_enable_xy": {"x": 747, "y": 99},
            # YBR clickable tile color spec (requested default)
            "chat_ybr_tile_color": asdict(ColorSpec((255, 212, 0), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60)),
            # Optional text color references for chat lines (not required by OCR but stored for clarity/tools)
            "chat_text_color_prayer_disabled": asdict(ColorSpec((255, 0, 0), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60)),
            "chat_text_color_ybr": asdict(ColorSpec((0, 0, 0), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60)),
            "chat_text_color_rebirth_disabled": asdict(ColorSpec((0, 0, 0), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60)),
            
            # New v3 settings
            # Combat precise small-ROI detection
            "combat_precise_mode": True,
            "combat_lab_tolerance": 18,   # ΔE76 threshold; lower is stricter
            "combat_sat_min": 40,         # HSV S minimum to suppress gray
            "combat_val_min": 40,         # HSV V minimum to suppress dark
            "combat_morph_open_iters": 1, # Morph open iterations for denoise
            "combat_morph_close_iters": 1,# Morph close iterations to connect
            
            # Teleport settings
            "teleport_locations": [],
            "emergency_teleport_hotkey": "ctrl+h",
            "return_teleport_hotkey": "ctrl+t",

            # 1 Tele 1 Kill mode
            # When enabled, overrides normal combat logic: search -> attack -> wait for HP; if not seen in timeout, teleport
            "one_tele_one_kill_enabled": False,
            "one_tele_one_kill_hp_timeout_s": 5.0,
            # Coordinate to click for teleport (selected in GUI)
            "one_tele_one_kill_teleport_xy": None,
            # New: ROI to click randomly inside to trigger teleport (if enabled)
            # Store as ROI object via set_roi/get_roi; typically use 'relative' mode to follow window.
            "one_tele_one_kill_teleport_roi": None,
            # Toggle to use ROI click instead of fixed coordinate (default off to preserve behavior)
            "one_tele_use_roi": False,
            # Optionally press a hotkey right after teleport click
            "one_tele_post_hotkey_enabled": False,
            # Default hotkey after teleport
            "one_tele_post_hotkey": "2",
            # Small delay before pressing the hotkey (seconds)
            "one_tele_post_hotkey_delay": 0.15,
            
            # Potion settings
            "potion_locations": [],
            
            # Boost settings
            "boost_locations": [],
            
            # Instance settings
            "instance_token_location": None,
            "instance_teleport_location": None,
            "aggro_potion_location": None,
            "aggro_effect_roi": None,
            "aggro_effect_color": asdict(ColorSpec((255, 0, 0))),
            "aggro_duration": 300,
            # Instance Mode: Aggro strategy and timer options
            # 'bar' (detect aggro bar), 'timer' (legacy fixed interval), 'hybrid' (either condition)
            "instance_aggro_strategy": "bar",
            # Legacy timer interval in minutes (float). Effective min 0.5 min (30s) enforced in code
            "instance_aggro_interval_min": 15.0,
            # Start delay seconds applied after each aggro click before the next interval countdown begins
            "instance_aggro_start_delay_s": 5.0,
            # Optional jitter for interval (%). When enabled, applies +/- percent randomness
            "instance_aggro_jitter_enabled": True,
            "instance_aggro_jitter_percent": 10.0,
            
            # Timeout settings
            "no_monster_timeout": 180,
            "camera_adjust_interval": 10,
            "emergency_teleport_threshold": 60,
            # Logging/throttling for instance status lines
            "instance_status_log_interval": 1.0,
            
            # ROI expansion settings
            "roi_max_expansion": 3,  # Maximum expansion levels
            "roi_expansion_factor": 1.2,  # Multiplier for each expansion level
            
            # Lab color matching settings (enhanced defaults)
            "combat_lab_tolerance": 15,  # Default Lab tolerance for combat style detection
            # Weapon detection gating (match requested normal counts lab=20, S>=20, V>=30)
            "weapon_lab_tolerance": 20,
            "weapon_sat_min": 20,
            "weapon_val_min": 30,
            # Weapon detection helpers
            "weapon_infer_current_from_missing": True,  # If two styles are visible, infer current as the missing one
            "weapon_melee_loosen": True,               # Loosen gating for melee (dark/low-chroma icons)
            "weapon_melee_lab_min": 18,                # Min Lab tolerance when loosening melee gating
            # Visible styles acceptance thresholds (for Visible list in UI/logic)
            # Base absolute acceptance for any style to be considered visible
            "weapon_visible_min_pixels": 13,
            # Adaptive acceptance relative to strongest style
            "weapon_visible_ratio": 0.40,
            # Absolute floor for adaptive acceptance
            "weapon_visible_floor": 5,
            # Magic-specific lenient visibility (to include very low counts like 9)
            "weapon_magic_lenient_visible": True,
            "weapon_magic_visible_floor": 8,
            # Legacy adaptive keys retained for backward compat (used by some tools)
            "weapon_adaptive_enable": True,
            "weapon_adaptive_ratio": 0.5,
            "weapon_adaptive_min_pixels": 5,
            "weapon_adaptive_secondary": True,  # Apply adaptive selection even if some styles already passed absolute threshold

            # Template-assist for low-chroma icons (e.g., melee)
            # When color detection is unreliable, optionally supply a small template image
            # and we'll use edge-based normalized cross-correlation to confirm presence.
            # Provide absolute file paths or paths relative to project root.
            "weapon_template_enable": True,
            "weapon_template_mode": "edge",        # 'edge' (Canny edges) or 'gray' (grayscale NCC)
            "weapon_template_threshold": 0.58,      # MatchTemplate score threshold (0..1)
            "weapon_melee_template_path": None,     # e.g., "profiles/examples/melee_icon.png"
            "weapon_ranged_template_path": None,
            "weapon_magic_template_path": None,
            # Optional search window around configured click positions (pixels)
            # If not set, full weapon ROI is searched.
            "weapon_template_window": 200,
            # Whether a template PASS should influence "equipped" detection counts.
            # Off by default: template primarily assists visibility; equipped should be inferred by absence.
            "weapon_template_affects_equipped": False,

            # Default Multi Monster weapon color specs (ensures all 3 are present by default)
            "multi_monster_melee_weapon_color": asdict(ColorSpec((5, 5, 10), tol_rgb=20, tol_h=3, tol_s=25, tol_v=25)),
            "multi_monster_ranged_weapon_color": asdict(ColorSpec((255, 0, 0), tol_rgb=20, tol_h=3, tol_s=25, tol_v=25)),
            "multi_monster_magic_weapon_color": asdict(ColorSpec((99, 35, 52), tol_rgb=20, tol_h=3, tol_s=25, tol_v=25)),
            # Multi Monster general defaults
            "multi_monster_mode_enabled": False,
            # Tile radius override for Multi Monster Mode (strict gating)
            "multi_monster_tile_radius": 120,
            # Weapon switching timings and verification
            "multi_monster_weapon_switch_cooldown_s": 0.6,
            # Delay after verified switch before attacking
            "multi_monster_weapon_switch_to_attack_delay_s": 0.5,
            # Retry logic for weapon switching: verify color disappears; retry if not
            "multi_monster_weapon_switch_max_retries": 5,
            "multi_monster_weapon_switch_retry_delay_s": 0.5,
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value
        
        Args:
            key: Configuration key
            default: Default value if key not found
        
        Returns:
            Configuration value or default
        """
        # Handle nested keys with dot notation
        if "." in key:
            parts = key.split(".")
            value = self._config
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            return value
        
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        # Normalize known structured types to JSON-serializable forms
        try:
            if isinstance(value, ROI):
                value = value.to_dict()
            elif isinstance(value, ColorSpec):
                value = asdict(value)
        except Exception:
            pass
        # Handle nested keys with dot notation
        if "." in key:
            parts = key.split(".")
            config = self._config
            for part in parts[:-1]:
                if part not in config:
                    config[part] = {}
                config = config[part]
            config[parts[-1]] = value
        else:
            self._config[key] = value
    
    def get_color_spec(self, key: str) -> Optional[ColorSpec]:
        """
        Get a color specification
        
        Args:
            key: Configuration key for color spec
        
        Returns:
            ColorSpec object or None if not found
        """
        color_dict = self.get(key)
        if not color_dict:
            return None
        
        try:
            return ColorSpec(
                rgb=tuple(color_dict["rgb"]),
                tol_rgb=color_dict.get("tol_rgb", 8),
                use_hsv=color_dict.get("use_hsv", True),
                tol_h=color_dict.get("tol_h", 4),
                tol_s=color_dict.get("tol_s", 30),
                tol_v=color_dict.get("tol_v", 30)
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error creating ColorSpec from {key}: {e}")
            return None
    
    def get_roi(self, key: str) -> Optional[ROI]:
        """
        Get a region of interest
        
        Args:
            key: Configuration key for ROI
        
        Returns:
            ROI object or None if not found
        """
        roi_val = self.get(key)
        if not roi_val:
            return None
        # Already ROI instance
        if isinstance(roi_val, ROI):
            return roi_val
        # Legacy stored as dict
        if isinstance(roi_val, dict):
            try:
                # Validate required keys
                if 'left' not in roi_val or 'top' not in roi_val or 'width' not in roi_val or 'height' not in roi_val:
                    raise ValueError(f"ROI missing required keys: {roi_val}")
                return ROI.from_dict(roi_val)
            except Exception as e:
                logger.error(f"Error creating ROI from {key}: {e}")
                return None
        logger.error(f"Unsupported ROI format for {key}: {type(roi_val)}")
        return None
    
    def get_coordinate(self, key: str) -> Optional[Coordinate]:
        """
        Get a coordinate
        
        Args:
            key: Configuration key for coordinate
        
        Returns:
            Coordinate object or None if not found
        """
        coord_dict = self.get(key)
        if not coord_dict:
            return None
        
        try:
            return Coordinate(
                x=coord_dict["x"],
                y=coord_dict["y"],
                name=coord_dict.get("name", "")
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error creating Coordinate from {key}: {e}")
            return None
    
    def get_coordinates_list(self, key: str) -> List[Coordinate]:
        """
        Get a list of coordinates
        
        Args:
            key: Configuration key for coordinates list
        
        Returns:
            List of Coordinate objects
        """
        coords_list = self.get(key, [])
        result = []
        
        for i, coord_dict in enumerate(coords_list):
            try:
                coord = Coordinate(
                    x=coord_dict["x"],
                    y=coord_dict["y"],
                    name=coord_dict.get("name", f"Coordinate {i+1}")
                )
                result.append(coord)
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Error creating Coordinate {i} from {key}: {e}")
        
        return result
    
    def set_color_spec(self, key: str, color_spec: ColorSpec) -> None:
        """
        Set a color specification
        
        Args:
            key: Configuration key for color spec
            color_spec: ColorSpec object
        """
        self.set(key, asdict(color_spec))
    
    def set_roi(self, key: str, roi: ROI) -> None:
        """
        Set a region of interest
        
        Args:
            key: Configuration key for ROI
            roi: ROI object
        """
        # Preserve explicitly set modes. Only apply heuristics when mode is missing/unknown.
        try:
            mode = (roi.mode or 'absolute').lower()
            if mode not in ('absolute', 'relative', 'percent'):
                # Heuristic fallback for legacy pickers with no mode info
                from ..detection.capture import CaptureService  # type: ignore
                cs = CaptureService()
                bbox = cs.get_window_bbox()
                looks_relative = (roi.left < bbox['width'] and roi.top < bbox['height'] and roi.width <= bbox['width'] and roi.height <= bbox['height'])
                if looks_relative:
                    roi = ROI(left=bbox['left'] + int(roi.left), top=bbox['top'] + int(roi.top), width=int(roi.width), height=int(roi.height), mode='absolute')
        except Exception:
            pass
        self.set(key, roi.to_dict())
    
    def set_coordinate(self, key: str, coordinate: Coordinate) -> None:
        """
        Set a coordinate
        
        Args:
            key: Configuration key for coordinate
            coordinate: Coordinate object
        """
        self.set(key, coordinate.to_dict())
    
    def set_coordinates_list(self, key: str, coordinates: List[Coordinate]) -> None:
        """
        Set a list of coordinates
        
        Args:
            key: Configuration key for coordinates list
            coordinates: List of Coordinate objects
        """
        self.set(key, [coord.to_dict() for coord in coordinates])
    
    def load_profile(self, profile_name: str) -> bool:
        """
        Load a configuration profile
        
        Args:
            profile_name: Name of the profile to load
        
        Returns:
            True if profile was loaded successfully, False otherwise
        """
        # Add .json extension if not present
        if not profile_name.endswith('.json'):
            profile_name += '.json'
        
        profile_path = os.path.join(self.config_dir, profile_name)
        
        if not os.path.exists(profile_path):
            logger.error(f"Profile not found: {profile_path}")
            return False
        
        try:
            with open(profile_path, 'r') as f:
                config_data = json.load(f)
            
            # Validate and merge with defaults
            self._config = {**self._get_default_config(), **config_data}

            # Deprecation guard: remove legacy tile_search_roi if present
            try:
                if 'tile_search_roi' in self._config:
                    if self._config.get('tile_search_roi'):
                        logger.warning("Deprecated config key 'tile_search_roi' found in profile and will be ignored. Use only 'search_roi'.")
                    # Purge key to avoid accidental downstream usage
                    self._config.pop('tile_search_roi', None)
            except Exception:
                pass

            # ROI migration: ensure hpbar_roi & search_roi stored as ROI dicts (preserve mode when present)
            for _rk in ('hpbar_roi', 'search_roi'):
                try:
                    rv = self._config.get(_rk)
                    if rv and isinstance(rv, dict) and all(k in rv for k in ('left','top','width','height')):
                        # Preserve explicit mode, default to 'absolute'
                        mode = str(rv.get('mode', 'absolute')).lower()
                        try:
                            if mode == 'percent':
                                l = float(rv.get('left', 0.0)); t = float(rv.get('top', 0.0)); w = float(rv.get('width', 0.0)); h = float(rv.get('height', 0.0))
                                self._config[_rk] = ROI(l, t, w, h, mode='percent').to_dict()
                            else:
                                l = int(rv.get('left', 0)); t = int(rv.get('top', 0)); w = int(rv.get('width', 0)); h = int(rv.get('height', 0))
                                if w > 0 and h > 0:
                                    self._config[_rk] = ROI(l, t, w, h, mode=mode if mode in ('absolute','relative') else 'absolute').to_dict()
                        except Exception:
                            continue
                except Exception:
                    continue
            # Optional auto-migration: if follow-window is enabled and hpbar ROI is absolute, convert to relative using current window bbox
            try:
                if bool(self._config.get('hpbar_roi_follow_window', False)):
                    rv = self._config.get('hpbar_roi')
                    if rv and isinstance(rv, dict) and str(rv.get('mode', 'absolute')).lower() == 'absolute':
                        from ..detection.capture import CaptureService  # type: ignore
                        cs = CaptureService()
                        bbox = cs.get_window_bbox()
                        l = int(rv.get('left', 0)) - int(bbox['left'])
                        t = int(rv.get('top', 0)) - int(bbox['top'])
                        w = int(rv.get('width', 0))
                        h = int(rv.get('height', 0))
                        if 0 <= l <= bbox['width'] and 0 <= t <= bbox['height']:
                            self._config['hpbar_roi'] = ROI(l, t, w, h, mode='relative').to_dict()
            except Exception:
                pass
            self.current_profile = profile_name
            
            logger.info(f"Profile loaded: {profile_name}")
            # Enforce standard HP bar ROI across existing profiles
            try:
                fixed_hp = ROI(25, 79, 100, 17, mode='relative').to_dict()
                self._config['hpbar_roi'] = fixed_hp
                self._config['hpbar_roi_follow_window'] = True
                # Persist immediately to keep profiles aligned
                try:
                    self.save_profile(profile_name)
                except Exception:
                    pass
            except Exception:
                pass
            # Enforce standard SEARCH ROI across existing profiles
            try:
                fixed_search = ROI(6, 28, 515, 338, mode='relative').to_dict()
                self._config['search_roi'] = fixed_search
                # Persist immediately to keep profiles aligned
                try:
                    self.save_profile(profile_name)
                except Exception:
                    pass
            except Exception:
                pass
            # Enforce default Tile and HP bar colors across existing profiles
            try:
                self._config['tile_color'] = asdict(ColorSpec((250, 0, 255), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60))
                self._config['hpbar_color'] = asdict(ColorSpec((179, 36, 0), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60))
                try:
                    self.save_profile(profile_name)
                except Exception:
                    pass
            except Exception:
                pass
            # Enforce chat watcher requested defaults across existing profiles
            try:
                self._config['chat_roi'] = ROI(5, 367, 510, 118, mode='relative').to_dict()
                self._config['chat_prayer_enable_xy'] = {"x": 747, "y": 99}
                self._config['chat_ybr_tile_color'] = asdict(ColorSpec((255, 212, 0), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60))
                self._config['chat_text_color_prayer_disabled'] = asdict(ColorSpec((255, 0, 0), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60))
                self._config['chat_text_color_ybr'] = asdict(ColorSpec((0, 0, 0), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60))
                self._config['chat_text_color_rebirth_disabled'] = asdict(ColorSpec((0, 0, 0), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60))
                try:
                    self.save_profile(profile_name)
                except Exception:
                    pass
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"Error loading profile {profile_name}: {e}")
            return False
    
    def save_profile(self, profile_name: str) -> bool:
        """
        Save current configuration to a profile
        
        Args:
            profile_name: Name of the profile to save
        
        Returns:
            True if profile was saved successfully, False otherwise
        """
        # Add .json extension if not present
        if not profile_name.endswith('.json'):
            profile_name += '.json'
        
        profile_path = os.path.join(self.config_dir, profile_name)
        
        try:
            # Prepare a JSON-serializable copy of the config (handle ROI, ColorSpec, tuples, etc.)
            def _to_jsonable(obj: Any) -> Any:
                try:
                    if isinstance(obj, ROI):
                        return obj.to_dict()
                except Exception:
                    pass
                try:
                    if isinstance(obj, ColorSpec):
                        return asdict(obj)
                except Exception:
                    pass
                if isinstance(obj, dict):
                    return {k: _to_jsonable(v) for k, v in obj.items()}
                if isinstance(obj, (list, tuple)):
                    return [_to_jsonable(v) for v in obj]
                # Basic types pass through
                return obj

            serializable_config = _to_jsonable(self._config)
            with open(profile_path, 'w') as f:
                json.dump(serializable_config, f, indent=2)
            
            self.current_profile = profile_name
            logger.info(f"Profile saved: {profile_name}")
            return True
        except Exception as e:
            logger.error(f"Error saving profile {profile_name}: {e}")
            return False
    
    def list_profiles(self) -> List[str]:
        """
        List available profiles
        
        Returns:
            List of profile names
        """
        try:
            profiles = [f for f in os.listdir(self.config_dir) if f.endswith('.json')]
            return profiles
        except Exception as e:
            logger.error(f"Error listing profiles: {e}")
            return []
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to default values"""
        self._config = self._get_default_config()
        self.current_profile = None
        logger.info("Configuration reset to defaults")