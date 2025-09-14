"""
Instance module for RSPS Color Bot v3

This module provides instance management functionality for the bot.
"""
import logging
import time
from typing import Dict, List, Optional, Tuple, Any, Callable

import numpy as np

from ..config import ConfigManager, Coordinate, ColorSpec, ROI
from ..action import ActionManager
from ..state import EventSystem, EventType
from ..detection import DetectionEngine

# Get module logger
logger = logging.getLogger('rspsbot.core.modules.instance')

class InstanceManager:
    """
    Manages instance-related functionality, such as tokens and aggro potions
    """
    
    def __init__(
        self,
        config_manager: ConfigManager,
        action_manager: ActionManager,
        event_system: EventSystem,
        detection_engine: Optional[DetectionEngine] = None
    ):
        """
        Initialize the instance manager
        
        Args:
            config_manager: Configuration manager
            action_manager: Action manager
            event_system: Event system
            detection_engine: Detection engine (optional)
        """
        self.config_manager = config_manager
        self.action_manager = action_manager
        self.event_system = event_system
        self.detection_engine = detection_engine
        
        # Instance state
        self.in_instance = False
        self.instance_entry_time = 0.0
        
        # Aggro state
        self.aggro_active = False
        self.aggro_end_time = 0.0
        
        # Register actions
        self._register_actions()
        
        logger.info("Instance manager initialized")
    
    def _register_actions(self) -> None:
        """Register instance-related actions"""
        # Instance token action
        token_coord = self.config_manager.get_coordinate('instance_token_location')
        if token_coord:
            self.action_manager.register_coordinate_action(
                name="instance_token",
                coordinate=token_coord,
                cooldown=2.0,
                priority=40
            )
            logger.debug(f"Registered instance token action at {token_coord.x}, {token_coord.y}")
        
        # Instance teleport action
        teleport_coord = self.config_manager.get_coordinate('instance_teleport_location')
        if teleport_coord:
            self.action_manager.register_coordinate_action(
                name="instance_teleport",
                coordinate=teleport_coord,
                cooldown=5.0,
                priority=40
            )
            logger.debug(f"Registered instance teleport action at {teleport_coord.x}, {teleport_coord.y}")
        
        # Aggro potion action
        aggro_coord = self.config_manager.get_coordinate('aggro_potion_location')
        if aggro_coord:
            self.action_manager.register_coordinate_action(
                name="aggro_potion",
                coordinate=aggro_coord,
                cooldown=self.config_manager.get('aggro_duration', 300),
                priority=30,
                post_action=lambda: self._on_aggro_used()
            )
            logger.debug(f"Registered aggro potion action at {aggro_coord.x}, {aggro_coord.y}")
    
    def _on_aggro_used(self) -> bool:
        """Callback for when aggro potion is used"""
        self.aggro_active = True
        duration = self.config_manager.get('aggro_duration', 300)
        self.aggro_end_time = time.time() + duration
        
        logger.info(f"Aggro effect active for {duration} seconds")
        
        # Publish event
        self.event_system.publish(
            EventType.AGGRO_USED,
            {
                'duration': duration
            }
        )
        
        return True
    
    def enter_instance(self) -> bool:
        """
        Enter an instance
        
        Returns:
            True if instance was entered successfully, False otherwise
        """
        # Check feature toggle
        if not self.config_manager.get('enable_instance', True):
            logger.info("Instance feature disabled; skipping instance entry")
            return False

        logger.info("Attempting to enter instance")
        
        # Check if token action is registered
        if not self.action_manager.get_action("instance_token"):
            logger.error("Instance token action not registered")
            return False
        
        # Check if teleport action is registered
        if not self.action_manager.get_action("instance_teleport"):
            logger.error("Instance teleport action not registered")
            return False
        
        # Use instance token
        logger.info("Using instance token")
        if not self.action_manager.execute_action("instance_token"):
            logger.error("Failed to use instance token")
            return False
        
        # Wait for token dialog
        token_delay = self.config_manager.get('instance_token_delay', 1.0)
        time.sleep(token_delay)
        
        # Use instance teleport
        logger.info("Using instance teleport")
        if not self.action_manager.execute_action("instance_teleport"):
            logger.error("Failed to use instance teleport")
            return False
        
        # Update instance state
        self.in_instance = True
        self.instance_entry_time = time.time()
        
        # Publish event
        self.event_system.publish(
            EventType.INSTANCE_ENTERED,
            {
                'timestamp': self.instance_entry_time
            }
        )
        
        logger.info("Instance entered successfully")
        return True
    
    def use_aggro_potion(self) -> bool:
        """
        Use aggro potion
        
        Returns:
            True if aggro potion was used successfully, False otherwise
        """
        # Check feature toggle
        if not self.config_manager.get('enable_instance', True):
            logger.info("Instance feature disabled; skipping aggro potion")
            return False

        # Check if already active
        if self.is_aggro_active():
            logger.info("Aggro effect already active")
            return True
        
        # Check if action is registered
        if not self.action_manager.get_action("aggro_potion"):
            logger.error("Aggro potion action not registered")
            return False
        
        # Use aggro potion
        logger.info("Using aggro potion")
        return self.action_manager.execute_action("aggro_potion")
    
    def is_aggro_active(self) -> bool:
        """
        Check if aggro effect is active
        
        Returns:
            True if aggro effect is active, False otherwise
        """
        # Check timer first (faster)
        if self.aggro_active and time.time() < self.aggro_end_time:
            return True
        
        # If timer expired or not active, check visually if detection engine is available
        if self.detection_engine and self.config_manager.get('aggro_visual_check', True):
            roi_data = self.config_manager.get('aggro_effect_roi')
            if roi_data:
                try:
                    # Create ROI object
                    roi = ROI(
                        left=roi_data['left'],
                        top=roi_data['top'],
                        width=roi_data['width'],
                        height=roi_data['height']
                    )
                    
                    # Capture region
                    frame = self.detection_engine.capture_service.capture_region(roi.to_dict())
                    
                    # Get aggro effect color
                    color_spec = self.config_manager.get_color_spec('aggro_effect_color')
                    if color_spec:
                        # Check for color in frame
                        is_active = self._detect_aggro_effect(frame, color_spec)
                        
                        # Update state if detected
                        if is_active:
                            self.aggro_active = True
                            self.aggro_end_time = time.time() + self.config_manager.get('aggro_duration', 300)
                            return True
                
                except Exception as e:
                    logger.error(f"Error in visual aggro check: {e}")
        
        # If timer expired and visual check failed or not available, aggro is not active
        if self.aggro_active and time.time() >= self.aggro_end_time:
            self.aggro_active = False
        
        return self.aggro_active
    
    def _detect_aggro_effect(self, frame: np.ndarray, color_spec: ColorSpec) -> bool:
        """
        Detect aggro effect in frame
        
        Args:
            frame: Frame to check
            color_spec: Color specification for aggro effect
        
        Returns:
            True if aggro effect is detected, False otherwise
        """
        try:
            # Import here to avoid circular imports
            from ..detection.color_detector import build_mask
            
            # Build mask for color
            mask, contours = build_mask(
                frame,
                color_spec,
                step=1,
                precise=True,
                min_area=10
            )
            
            # Check if any contours were found
            return len(contours) > 0
        
        except Exception as e:
            logger.error(f"Error detecting aggro effect: {e}")
            return False
    
    def get_aggro_remaining(self) -> float:
        """
        Get remaining aggro time in seconds
        
        Returns:
            Remaining aggro time in seconds (0 if not active)
        """
        if not self.is_aggro_active():
            return 0.0
        
        return max(0.0, self.aggro_end_time - time.time())
    
    def set_instance_token_location(self, coordinate: Coordinate) -> bool:
        """
        Set instance token location
        
        Args:
            coordinate: Coordinate for instance token
        
        Returns:
            True if location was set successfully, False otherwise
        """
        try:
            # Save to config
            self.config_manager.set_coordinate('instance_token_location', coordinate)
            
            # Re-register action
            self.action_manager.unregister_action("instance_token")
            self.action_manager.register_coordinate_action(
                name="instance_token",
                coordinate=coordinate,
                cooldown=2.0,
                priority=40
            )
            
            logger.info(f"Set instance token location to {coordinate.x}, {coordinate.y}")
            return True
        
        except Exception as e:
            logger.error(f"Error setting instance token location: {e}")
            return False
    
    def set_instance_teleport_location(self, coordinate: Coordinate) -> bool:
        """
        Set instance teleport location
        
        Args:
            coordinate: Coordinate for instance teleport
        
        Returns:
            True if location was set successfully, False otherwise
        """
        try:
            # Save to config
            self.config_manager.set_coordinate('instance_teleport_location', coordinate)
            
            # Re-register action
            self.action_manager.unregister_action("instance_teleport")
            self.action_manager.register_coordinate_action(
                name="instance_teleport",
                coordinate=coordinate,
                cooldown=5.0,
                priority=40
            )
            
            logger.info(f"Set instance teleport location to {coordinate.x}, {coordinate.y}")
            return True
        
        except Exception as e:
            logger.error(f"Error setting instance teleport location: {e}")
            return False
    
    def set_aggro_potion_location(self, coordinate: Coordinate) -> bool:
        """
        Set aggro potion location
        
        Args:
            coordinate: Coordinate for aggro potion
        
        Returns:
            True if location was set successfully, False otherwise
        """
        try:
            # Save to config
            self.config_manager.set_coordinate('aggro_potion_location', coordinate)
            
            # Re-register action
            self.action_manager.unregister_action("aggro_potion")
            self.action_manager.register_coordinate_action(
                name="aggro_potion",
                coordinate=coordinate,
                cooldown=self.config_manager.get('aggro_duration', 300),
                priority=30,
                post_action=lambda: self._on_aggro_used()
            )
            
            logger.info(f"Set aggro potion location to {coordinate.x}, {coordinate.y}")
            return True
        
        except Exception as e:
            logger.error(f"Error setting aggro potion location: {e}")
            return False
    
    def set_aggro_effect_roi(self, roi: ROI) -> bool:
        """
        Set aggro effect ROI
        
        Args:
            roi: ROI for aggro effect detection
        
        Returns:
            True if ROI was set successfully, False otherwise
        """
        try:
            # Save to config
            self.config_manager.set_roi('aggro_effect_roi', roi)
            
            logger.info(f"Set aggro effect ROI to {roi.left}, {roi.top}, {roi.width}, {roi.height}")
            return True
        
        except Exception as e:
            logger.error(f"Error setting aggro effect ROI: {e}")
            return False
    
    def set_aggro_effect_color(self, color_spec: ColorSpec) -> bool:
        """
        Set aggro effect color
        
        Args:
            color_spec: Color specification for aggro effect
        
        Returns:
            True if color was set successfully, False otherwise
        """
        try:
            # Save to config
            self.config_manager.set_color_spec('aggro_effect_color', color_spec)
            
            logger.info(f"Set aggro effect color to {color_spec.rgb}")
            return True
        
        except Exception as e:
            logger.error(f"Error setting aggro effect color: {e}")
            return False
    
    def set_aggro_duration(self, duration: float) -> bool:
        """
        Set aggro duration
        
        Args:
            duration: Duration in seconds
        
        Returns:
            True if duration was set successfully, False otherwise
        """
        try:
            # Save to config
            self.config_manager.set('aggro_duration', duration)
            
            # Re-register action with new cooldown
            aggro_coord = self.config_manager.get_coordinate('aggro_potion_location')
            if aggro_coord:
                self.action_manager.unregister_action("aggro_potion")
                self.action_manager.register_coordinate_action(
                    name="aggro_potion",
                    coordinate=aggro_coord,
                    cooldown=duration,
                    priority=30,
                    post_action=lambda: self._on_aggro_used()
                )
            
            logger.info(f"Set aggro duration to {duration} seconds")
            return True
        
        except Exception as e:
            logger.error(f"Error setting aggro duration: {e}")
            return False