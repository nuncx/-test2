"""
Instance-Only Mode detector for RSPS Color Bot v3
"""
import time
import logging
import numpy as np
import cv2
from typing import Dict, Any, Optional, Tuple

from ..config import ConfigManager, ColorSpec, ROI, Coordinate
from .capture import CaptureService
from .color_detector import build_mask

# Get module logger
logger = logging.getLogger('rspsbot.core.detection.instance_only_detector')

class InstanceOnlyDetector:
    """
    Specialized detector for Instance-Only Mode
    
    This detector focuses only on aggro potion and HP bar detection,
    skipping tile and monster detection entirely.
    """
    
    def __init__(self, config_manager: ConfigManager, capture_service: CaptureService):
        """
        Initialize the Instance-Only Mode detector
        
        Args:
            config_manager: Configuration manager
            capture_service: Capture service
        """
        self.config_manager = config_manager
        self.capture_service = capture_service
        
        # State tracking
        self.last_hp_seen_time = 0
        self.last_aggro_check_time = 0
        self.aggro_active = False
        self.in_combat = False
        
        logger.info("Instance-Only Mode detector initialized")
    
    def detect_cycle(self) -> Dict[str, Any]:
        """
        Perform a detection cycle for Instance-Only Mode
        
        Returns:
            Dictionary with detection results
        """
        # Start timing
        start_time = time.time()
        
        # Check HP bar first to determine combat status
        hp_bar_visible = self.check_hp_bar_visibility()
        
        # Update combat status
        if hp_bar_visible:
            self.in_combat = True
            self.last_hp_seen_time = time.time()
        else:
            # Only consider not in combat if HP bar has been invisible for a while
            hp_timeout = self.config_manager.get('instance_hp_timeout', 30.0)
            if time.time() - self.last_hp_seen_time > hp_timeout:
                self.in_combat = False
        
        # Check aggro potion if not in combat or if it's been a while since last check
        aggro_check_interval = self.config_manager.get('aggro_check_interval', 60.0)
        if (not self.in_combat or 
            time.time() - self.last_aggro_check_time > aggro_check_interval):
            self.aggro_active = self.check_aggro_potion()
            self.last_aggro_check_time = time.time()
        
        # Calculate detection time
        detection_time_ms = (time.time() - start_time) * 1000
        
        # Prepare result
        result = {
            'instance_only_mode': True,
            'in_combat': self.in_combat,
            'hp_seen': hp_bar_visible,
            'aggro_active': self.aggro_active,
            'last_hp_seen_time': self.last_hp_seen_time,
            'hp_timeout': self.config_manager.get('instance_hp_timeout', 30.0),
            'instance_empty': not self.in_combat,
            'timestamp': time.time(),
            'detection_time_ms': detection_time_ms
        }
        
        return result
    
    def check_hp_bar_visibility(self) -> bool:
        """
        Check if the HP bar is visible
        
        Returns:
            bool: True if HP bar is visible, False otherwise
        """
        # Get HP bar ROI
        hp_bar_roi = self.config_manager.get_roi('instance_hp_bar_roi')
        if not hp_bar_roi:
            logger.warning("HP bar ROI not configured for Instance-Only Mode")
            return False
        
        # Get HP bar color
        hp_bar_color = self.config_manager.get_color_spec('instance_hp_bar_color')
        if not hp_bar_color:
            logger.warning("HP bar color not configured for Instance-Only Mode")
            return False
        
        # Capture HP bar region
        frame = self.capture_service.capture_region(hp_bar_roi)
        if frame is None:
            logger.warning("Failed to capture HP bar region")
            return False
        
        # Create mask for HP bar color
        mask = build_mask(frame, hp_bar_color)
        
        # Count non-zero pixels
        non_zero_count = cv2.countNonZero(mask)
        
        # Get minimum pixel count from config
        min_pixel_count = self.config_manager.get('instance_hp_min_pixels', 50)
        
        # HP bar is visible if there are enough matching pixels
        is_visible = non_zero_count >= min_pixel_count
        
        if is_visible:
            logger.debug(f"HP bar detected with {non_zero_count} matching pixels")
        
        return is_visible
    
    def check_aggro_potion(self) -> bool:
        """
        Check if aggro potion is active
        
        Returns:
            bool: True if aggro potion is active, False otherwise
        """
        # Check if visual check is enabled
        visual_check = self.config_manager.get('instance_aggro_visual_check', True)
        if not visual_check:
            # If visual check is disabled, use time-based check
            aggro_duration = self.config_manager.get('aggro_duration', 300.0)
            last_aggro_time = self.config_manager.get('last_aggro_time', 0)
            
            return time.time() - last_aggro_time < aggro_duration
        
        # Get aggro effect ROI
        aggro_roi = self.config_manager.get_roi('instance_aggro_effect_roi')
        if not aggro_roi:
            logger.warning("Aggro effect ROI not configured for Instance-Only Mode")
            return False
        
        # Get aggro effect color
        aggro_color = self.config_manager.get_color_spec('instance_aggro_effect_color')
        if not aggro_color:
            logger.warning("Aggro effect color not configured for Instance-Only Mode")
            return False
        
        # Capture aggro effect region
        frame = self.capture_service.capture_region(aggro_roi)
        if frame is None:
            logger.warning("Failed to capture aggro effect region")
            return False
        
        # Create mask for aggro effect color
        mask = build_mask(frame, aggro_color)
        
        # Count non-zero pixels
        non_zero_count = cv2.countNonZero(mask)
        
        # Get minimum pixel count from config
        min_pixel_count = self.config_manager.get('instance_aggro_min_pixels', 50)
        
        # Aggro is active if there are enough matching pixels
        is_active = non_zero_count >= min_pixel_count
        
        if is_active:
            logger.debug(f"Aggro effect detected with {non_zero_count} matching pixels")
            # Update last aggro time
            self.config_manager.set('last_aggro_time', time.time())
        
        return is_active
    
    def should_use_aggro_potion(self) -> bool:
        """
        Check if aggro potion should be used
        
        Returns:
            bool: True if aggro potion should be used, False otherwise
        """
        return not self.aggro_active
    
    def should_teleport_to_instance(self) -> bool:
        """
        Check if should teleport to instance
        
        Returns:
            bool: True if should teleport to instance, False otherwise
        """
        # If not in combat for longer than timeout, teleport to instance
        hp_timeout = self.config_manager.get('instance_hp_timeout', 30.0)
        return not self.in_combat and time.time() - self.last_hp_seen_time > hp_timeout
    
    def get_aggro_potion_location(self) -> Optional[Coordinate]:
        """
        Get the location of the aggro potion
        
        Returns:
            Coordinate: Aggro potion location, or None if not configured
        """
        return self.config_manager.get_coordinate('instance_aggro_potion_location')
    
    def get_instance_token_location(self) -> Optional[Coordinate]:
        """
        Get the location of the instance token
        
        Returns:
            Coordinate: Instance token location, or None if not configured
        """
        return self.config_manager.get_coordinate('instance_token_location')
    
    def get_instance_teleport_location(self) -> Optional[Coordinate]:
        """
        Get the location of the instance teleport
        
        Returns:
            Coordinate: Instance teleport location, or None if not configured
        """
        return self.config_manager.get_coordinate('instance_teleport_location')
    
    def get_instance_token_delay(self) -> float:
        """
        Get the delay between clicking instance token and teleport
        
        Returns:
            float: Delay in seconds
        """
        return self.config_manager.get('instance_token_delay', 2.0)