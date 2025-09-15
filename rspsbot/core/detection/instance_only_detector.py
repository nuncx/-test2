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
        
        # Calculate detection time
        detection_time_ms = (time.time() - start_time) * 1000
        
        # Prepare result
        result = {
            'instance_only_mode': True,
            'in_combat': self.in_combat,
            'hp_seen': hp_bar_visible,
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
        mask_out = build_mask(frame, hp_bar_color)
        # Be defensive: build_mask should return (mask, contours)
        if isinstance(mask_out, tuple) and len(mask_out) >= 1:
            mask = mask_out[0]
        else:
            mask = mask_out  # fallback
        
        # Ensure mask is a single-channel uint8 image before count
        try:
            import numpy as _np
            if mask is None:
                logger.warning("HP mask is None; treating as not visible")
                return False
            if isinstance(mask, (tuple, list)):
                # Unexpected structure; log and bail out safely
                logger.warning(f"HP mask has unexpected type {type(mask)}; treating as not visible")
                return False
            if isinstance(mask, _np.ndarray):
                if mask.ndim == 3:
                    # Convert 3-channel to grayscale
                    mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
                if mask.dtype != _np.uint8:
                    mask = mask.astype(_np.uint8)
            else:
                logger.warning(f"HP mask is not ndarray (type={type(mask)}); treating as not visible")
                return False
            
            # Count non-zero pixels
            non_zero_count = cv2.countNonZero(mask)
        except Exception as e:
            logger.error(f"Error processing HP mask: {e}")
            return False
        
        # Get minimum pixel count from config
        min_pixel_count = self.config_manager.get('instance_hp_min_pixels', 50)
        
        # HP bar is visible if there are enough matching pixels
        is_visible = non_zero_count >= min_pixel_count
        
        if is_visible:
            logger.debug(f"HP bar detected with {non_zero_count} matching pixels")
        
        return is_visible
    
    
    # Visual aggro checks removed; timer-based aggro is handled in controller
    
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