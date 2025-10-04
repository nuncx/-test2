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
from .color_detector import largest_contour

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
        # Initialize to now so "seconds since combat" starts at ~0 on boot
        self.last_hp_seen_time = time.time()
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
            hp_timeout = float(self.config_manager.get('instance_hp_timeout', self.config_manager.get('instance_hp_timeout_s', 30.0)))
            # If uninitialized or too old, set a baseline to avoid absurd large values
            if self.last_hp_seen_time <= 0:
                self.last_hp_seen_time = time.time()
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
            'hp_timeout': self.config_manager.get('instance_hp_timeout', self.config_manager.get('instance_hp_timeout_s', 30.0)),
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
        # Always use the global HP bar ROI to keep behavior consistent across modes
        hp_bar_roi = self.config_manager.get_roi('hpbar_roi')
        if not hp_bar_roi:
            logger.warning("Global HP bar ROI ('hpbar_roi') not configured")
            return False
        
        # Always use the global HP bar color
        hp_bar_color = self.config_manager.get_color_spec('hpbar_color')
        if not hp_bar_color:
            logger.warning("Global HP bar color ('hpbar_color') not configured")
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
    
    
    def detect_aggro_and_point(self) -> Tuple[bool, Optional[Tuple[int, int]]]:
        """
        Detect aggro potion presence using three colors within an ROI and suggest a click point.

        Returns:
            (present, (x, y)) where present indicates all three colors exceed their pixel threshold
            and (x, y) is a centroid within the combined mask in absolute screen coordinates.
        """
        # ROI
        aggro_roi = self.config_manager.get_roi('instance_aggro_roi')
        if not aggro_roi:
            logger.debug("Aggro ROI not set")
            return False, None
        # Colors
        c1 = self.config_manager.get_color_spec('instance_aggro_color1')
        c2 = self.config_manager.get_color_spec('instance_aggro_color2')
        c3 = self.config_manager.get_color_spec('instance_aggro_color3')
        if not (c1 and c2 and c3):
            logger.debug("Aggro colors not fully configured (need 3)")
            return False, None
        try:
            min_pix = int(self.config_manager.get('instance_aggro_min_pixels_per_color', 30))
        except Exception:
            min_pix = 30

        # Capture ROI image
        frame = self.capture_service.capture_region(aggro_roi)
        if frame is None:
            return False, None

        try:
            # Build masks for each color
            m1, _ = build_mask(frame, c1, step=1, precise=True, min_area=0)
            m2, _ = build_mask(frame, c2, step=1, precise=True, min_area=0)
            m3, _ = build_mask(frame, c3, step=1, precise=True, min_area=0)

            import cv2 as _cv
            ok1 = _cv.countNonZero(m1) >= min_pix
            ok2 = _cv.countNonZero(m2) >= min_pix
            ok3 = _cv.countNonZero(m3) >= min_pix

            if not (ok1 and ok2 and ok3):
                return False, None

            # Combine masks and find a centroid to click
            combo = _cv.bitwise_or(_cv.bitwise_or(m1, m2), m3)
            contours, _ = _cv.findContours(combo, _cv.RETR_EXTERNAL, _cv.CHAIN_APPROX_SIMPLE)
            if not contours:
                # Fallback: click center of ROI
                cx = int(aggro_roi.left + aggro_roi.width // 2)
                cy = int(aggro_roi.top + aggro_roi.height // 2)
                return True, (cx, cy)

            cnt = largest_contour(list(contours)) or list(contours)[0]
            M = _cv.moments(cnt)
            if M.get('m00', 0) != 0:
                cx_small = int(M['m10'] / M['m00'])
                cy_small = int(M['m01'] / M['m00'])
            else:
                x, y, w, h = _cv.boundingRect(cnt)
                cx_small = x + w // 2
                cy_small = y + h // 2

            # Convert to absolute screen coords (step=1)
            cx = int(aggro_roi.left + cx_small)
            cy = int(aggro_roi.top + cy_small)
            return True, (cx, cy)
        except Exception as e:
            logger.error(f"Error detecting aggro: {e}")
            return False, None

    def detect_aggro_bar_present(self) -> bool:
        """Return True if all three aggro bar colors exceed the pixel threshold within the aggro bar ROI."""
        aggro_roi = self.config_manager.get_roi('instance_aggro_bar_roi')
        if not aggro_roi:
            # Fallback to legacy key to avoid hard break
            aggro_roi = self.config_manager.get_roi('instance_aggro_roi')
        if not aggro_roi:
            return False
        c1 = self.config_manager.get_color_spec('instance_aggro_bar_color1') or self.config_manager.get_color_spec('instance_aggro_color1')
        c2 = self.config_manager.get_color_spec('instance_aggro_bar_color2') or self.config_manager.get_color_spec('instance_aggro_color2')
        c3 = self.config_manager.get_color_spec('instance_aggro_bar_color3') or self.config_manager.get_color_spec('instance_aggro_color3')
        if not (c1 and c2 and c3):
            return False
        try:
            min_pix = int(self.config_manager.get('instance_aggro_bar_min_pixels_per_color', self.config_manager.get('instance_aggro_min_pixels_per_color', 30)))
        except Exception:
            min_pix = 30
        frame = self.capture_service.capture_region(aggro_roi)
        if frame is None:
            return False
        try:
            m1, _ = build_mask(frame, c1, step=1, precise=True, min_area=0)
            m2, _ = build_mask(frame, c2, step=1, precise=True, min_area=0)
            m3, _ = build_mask(frame, c3, step=1, precise=True, min_area=0)
            import cv2 as _cv
            ok1 = _cv.countNonZero(m1) >= min_pix
            ok2 = _cv.countNonZero(m2) >= min_pix
            ok3 = _cv.countNonZero(m3) >= min_pix
            return bool(ok1 and ok2 and ok3)
        except Exception:
            return False
    
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

    # ---------------- Overlay helpers -----------------
    def compute_aggro_bar_centroid(self) -> Optional[Tuple[int, int]]:
        """Compute a click point within the Aggro Bar ROI based on combined mask centroid.

        Returns absolute screen coordinates (x, y) or None if unavailable.
        """
        try:
            aggro_roi = self.config_manager.get_roi('instance_aggro_bar_roi')
            if not aggro_roi:
                aggro_roi = self.config_manager.get_roi('instance_aggro_roi')
            if not aggro_roi:
                return None
            c1 = self.config_manager.get_color_spec('instance_aggro_bar_color1') or self.config_manager.get_color_spec('instance_aggro_color1')
            c2 = self.config_manager.get_color_spec('instance_aggro_bar_color2') or self.config_manager.get_color_spec('instance_aggro_color2')
            c3 = self.config_manager.get_color_spec('instance_aggro_bar_color3') or self.config_manager.get_color_spec('instance_aggro_color3')
            if not (c1 and c2 and c3):
                # Return center of ROI as fallback so overlay can still show a point
                return (
                    int(aggro_roi.left + aggro_roi.width // 2),
                    int(aggro_roi.top + aggro_roi.height // 2),
                )
            frame = self.capture_service.capture_region(aggro_roi)
            if frame is None:
                return None
            m1, _ = build_mask(frame, c1, step=1, precise=True, min_area=0)
            m2, _ = build_mask(frame, c2, step=1, precise=True, min_area=0)
            m3, _ = build_mask(frame, c3, step=1, precise=True, min_area=0)
            import cv2 as _cv
            combo = _cv.bitwise_or(_cv.bitwise_or(m1, m2), m3)
            contours, _ = _cv.findContours(combo, _cv.RETR_EXTERNAL, _cv.CHAIN_APPROX_SIMPLE)
            if not contours:
                # Fallback to center of ROI
                return (
                    int(aggro_roi.left + aggro_roi.width // 2),
                    int(aggro_roi.top + aggro_roi.height // 2),
                )
            cnt = largest_contour(list(contours)) or list(contours)[0]
            M = _cv.moments(cnt)
            if M.get('m00', 0) != 0:
                cx_small = int(M['m10'] / M['m00'])
                cy_small = int(M['m01'] / M['m00'])
            else:
                x, y, w, h = _cv.boundingRect(cnt)
                cx_small = x + w // 2
                cy_small = y + h // 2
            # Convert to absolute
            cx = int(aggro_roi.left + cx_small)
            cy = int(aggro_roi.top + cy_small)
            return (cx, cy)
        except Exception:
            return None