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
        self.last_detected_style = None
        self.last_style_change_time = 0
        self.load_monster_configs()
    
    def load_monster_configs(self):
        """Load monster configurations from config"""
        monster_configs = self.config_manager.get('multi_monster_configs', [])
        self.monster_style_map = {}
        
        for config in monster_configs:
            if 'color' in config and 'style' in config:
                color_key = tuple(config['color']['rgb'])
                self.monster_style_map[color_key] = config['style']
    
    def detect_monsters_with_styles(self, frame: np.ndarray, base_roi: Dict[str, int]) -> List[Dict[str, Any]]:
        """
        Detect monsters and assign combat styles based on monster color
        
        Args:
            frame: Captured frame
            base_roi: Base region of interest
            
        Returns:
            List of detected monsters with their positions and assigned combat styles
        """
        # First, detect tiles
        tiles = self.detect_tiles(frame, base_roi)
        if not tiles:
            # If no tiles found, try using the tile search ROI if configured
            tile_search_roi = self.config_manager.get_roi('tile_search_roi')
            if tile_search_roi:
                logger.debug("No tiles found in base ROI, trying tile search ROI")
                tiles = self.detect_tiles(frame, tile_search_roi)
        
        if not tiles:
            logger.debug("No tiles found")
            return []
        
        # Detect monsters near tiles
        monsters = []
        for tile in tiles:
            tile_center = (tile['center_x'], tile['center_y'])
            monsters_near_tile = self.detect_monsters_near_tile(frame, base_roi, tile_center)
            
            for monster in monsters_near_tile:
                # Assign combat style based on monster color
                monster_color = monster.get('color_rgb')
                if monster_color:
                    monster_color_tuple = tuple(monster_color)
                    if monster_color_tuple in self.monster_style_map:
                        monster['combat_style'] = self.monster_style_map[monster_color_tuple]
                    else:
                        # Find closest color match
                        closest_color = self._find_closest_color(monster_color_tuple)
                        if closest_color:
                            monster['combat_style'] = self.monster_style_map[closest_color]
                        else:
                            monster['combat_style'] = 'melee'  # Default to melee if no match
                
                monsters.append(monster)
        
        return monsters
    
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
            
            # Get lab tolerance from config
            lab_tolerance = self.config_manager.get('weapon_lab_tolerance', 10)
            
            # Configure detection parameters
            config = {
                'combat_lab_tolerance': lab_tolerance,
                'combat_sat_min': self.config_manager.get('multi_monster_sat_min', 50),
                'combat_val_min': self.config_manager.get('multi_monster_val_min', 50),
                'combat_morph_open_iters': self.config_manager.get('multi_monster_morph_open_iters', 1),
                'combat_morph_close_iters': self.config_manager.get('multi_monster_morph_close_iters', 2),
            }
            
            counts = {}
            for style, spec in specs.items():
                mask, _ = build_mask_precise_small(weapon_frame, spec, config, step=1, min_area=0)
                counts[style] = int(cv2.countNonZero(mask))
            
            # Get minimum pixel threshold
            min_pixels = int(self.config_manager.get('weapon_min_pixels', 40))
            
            # Determine detected weapon
            eligible = [k for k in counts.keys() if counts[k] >= min_pixels]
            if not eligible:
                return None
            elif len(eligible) == 1:
                return eligible[0]
            else:
                return max(eligible, key=lambda k: counts[k])
        
        except Exception as e:
            logger.error(f"Error detecting weapon: {e}")
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
            logger.debug("In combat, skipping detection")
            return result
        
        # Detect monsters with styles
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
        
        # Detect current weapon
        current_style = self.detect_weapon(frame)
        result['current_style'] = current_style
        
        # Check if weapon matches required style
        weapon_match = current_style == required_style
        result['weapon_match'] = weapon_match
        
        # Determine action
        if weapon_match:
            # Weapon matches, attack monster
            result['action'] = 'attack'
        else:
            # Weapon doesn't match, switch weapon
            result['action'] = 'switch_weapon'
        
        return result
    
    def get_weapon_position(self, style: str) -> Optional[Dict[str, int]]:
        """
        Get the position of the weapon for the specified style
        
        Args:
            style: Combat style ('melee', 'ranged', 'magic')
            
        Returns:
            Dictionary with x, y coordinates or None if not configured
        """
        weapon_key = f'multi_monster_{style}_weapon_position'
        position = self.config_manager.get(weapon_key)
        if position and 'x' in position and 'y' in position:
            return {'x': position['x'], 'y': position['y']}
        return None