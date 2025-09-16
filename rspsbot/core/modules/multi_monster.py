"""
Multi Monster Mode module for RSPS Color Bot v3
"""
import time
import logging
import random
from typing import Dict, List, Tuple, Optional, Any

from ..config import ConfigManager
from ..detection.multi_monster_detector import MultiMonsterDetector
from ..action.mouse import MouseController
from ..action.keyboard import KeyboardController

# Get module logger
logger = logging.getLogger('rspsbot.core.modules.multi_monster')

class MultiMonsterModule:
    """
    Module for handling Multi Monster Mode
    """
    
    def __init__(self, config_manager: ConfigManager, mouse_controller: MouseController, keyboard_controller: KeyboardController, detector: MultiMonsterDetector):
        """
        Initialize the Multi Monster Module
        
        Args:
            config_manager: Configuration manager
            mouse_controller: Mouse controller
            keyboard_controller: Keyboard controller
            detector: Multi Monster detector
        """
        self.config_manager = config_manager
        self.mouse_controller = mouse_controller
        self.keyboard_controller = keyboard_controller
        self.detector = detector
        
        # State variables
        self.enabled = False
        self.in_combat = False
        self.last_combat_end_time = 0
        self.last_weapon_switch_time = 0
        self.current_style = None
        self.current_target = None
        
        # Load configuration
        self.load_config()
    
    def load_config(self):
        """Load configuration settings"""
        self.enabled = self.config_manager.get('multi_monster_mode_enabled', False)
        self.post_attack_wait = self.config_manager.get('multi_monster_post_attack_wait', 2.0)
    
    def update_config(self):
        """Update configuration settings"""
        self.load_config()
    
    def process_cycle(self, frame, base_roi: Dict[str, int]) -> Dict[str, Any]:
        """
        Process a detection cycle in Multi Monster Mode
        
        Args:
            frame: Captured frame
            base_roi: Base region of interest
            
        Returns:
            Dictionary with detection results and actions taken
        """
        if not self.enabled:
            return {'enabled': False, 'action': None}
        
        # Check if in combat
        self.in_combat = self.detector.is_in_combat()
        
        # If in combat, wait for it to end
        if self.in_combat:
            return {'enabled': True, 'in_combat': True, 'action': 'wait_combat'}
        
        # If we just finished combat, wait for post-combat delay
        if self.last_combat_end_time > 0:
            time_since_combat = time.time() - self.last_combat_end_time
            if time_since_combat < self.post_attack_wait:
                return {'enabled': True, 'in_combat': False, 'action': 'post_combat_wait'}
            else:
                self.last_combat_end_time = 0
        
        # Process multi monster detection
        result = self.detector.process_multi_monster_mode(frame, base_roi)
        
        # If no monsters detected, return
        if not result['monsters']:
            return {'enabled': True, 'in_combat': False, 'monsters': 0, 'action': 'no_monsters'}
        
        # Get target and required style
        target = result['target']
        required_style = result['required_style']
        current_style = result['current_style']
        
        # Update current style
        self.current_style = current_style
        self.current_target = target
        
        # Determine action
        if result['action'] == 'switch_weapon':
            # Need to switch weapon
            weapon_position = self.detector.get_weapon_position(required_style)
            if weapon_position:
                self.mouse_controller.move_and_click(weapon_position['x'], weapon_position['y'])
                self.last_weapon_switch_time = time.time()
                return {
                    'enabled': True,
                    'in_combat': False,
                    'monsters': len(result['monsters']),
                    'target': target,
                    'current_style': current_style,
                    'required_style': required_style,
                    'action': 'switch_weapon'
                }
        elif result['action'] == 'attack':
            # Attack monster
            if target and 'center_x' in target and 'center_y' in target:
                self.mouse_controller.move_and_click(target['center_x'], target['center_y'])
                return {
                    'enabled': True,
                    'in_combat': False,
                    'monsters': len(result['monsters']),
                    'target': target,
                    'current_style': current_style,
                    'required_style': required_style,
                    'action': 'attack'
                }
        
        # Default return
        return {
            'enabled': True,
            'in_combat': False,
            'monsters': len(result['monsters']),
            'action': 'none'
        }
    
    def on_combat_end(self):
        """Handle combat end event"""
        self.last_combat_end_time = time.time()
    
    def is_enabled(self) -> bool:
        """Check if Multi Monster Mode is enabled"""
        return self.enabled