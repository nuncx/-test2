"""
Teleport module for RSPS Color Bot v3

This module provides teleport functionality for the bot.
"""
import logging
import time
from typing import Dict, List, Optional, Tuple, Any, Callable

from ..config import ConfigManager, Coordinate
from ..action import ActionManager
from ..state import EventSystem, EventType

# Get module logger
logger = logging.getLogger('rspsbot.core.modules.teleport')

class TeleportLocation:
    """
    Represents a teleport location with coordinates and metadata
    """
    
    def __init__(
        self,
        name: str,
        coordinate: Optional[Coordinate] = None,
        hotkey: Optional[str] = None,
        cooldown: float = 5.0,
        is_emergency: bool = False
    ):
        """
        Initialize a teleport location
        
        Args:
            name: Name of the teleport location
            coordinate: Coordinate for clicking (if hotkey not used)
            hotkey: Hotkey for teleporting (optional)
            cooldown: Cooldown time in seconds
            is_emergency: Whether this is an emergency teleport
        """
        self.name = name
        self.coordinate = coordinate
        self.hotkey = hotkey
        self.cooldown = cooldown
        self.is_emergency = is_emergency
        self.last_used = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "name": self.name,
            "coordinate": self.coordinate.to_dict() if self.coordinate else None,
            "hotkey": self.hotkey,
            "cooldown": self.cooldown,
            "is_emergency": self.is_emergency
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TeleportLocation':
        """Create from dictionary"""
        coordinate_data = data.get("coordinate")
        coordinate = Coordinate.from_dict(coordinate_data) if coordinate_data else None
        
        return cls(
            name=data.get("name", ""),
            coordinate=coordinate,
            hotkey=data.get("hotkey"),
            cooldown=data.get("cooldown", 5.0),
            is_emergency=data.get("is_emergency", False)
        )
    
    def is_on_cooldown(self) -> bool:
        """Check if teleport is on cooldown"""
        return time.time() - self.last_used < self.cooldown
    
    def get_cooldown_remaining(self) -> float:
        """Get remaining cooldown time in seconds"""
        if not self.is_on_cooldown():
            return 0.0
        
        return max(0.0, self.cooldown - (time.time() - self.last_used))
    
    def reset_cooldown(self) -> None:
        """Reset cooldown timer"""
        self.last_used = 0.0
    
    def __str__(self) -> str:
        return f"TeleportLocation({self.name}, {'hotkey' if self.hotkey else 'coordinate'}, emergency={self.is_emergency})"

class TeleportManager:
    """
    Manages teleport locations and teleport actions
    """
    
    def __init__(
        self,
        config_manager: ConfigManager,
        action_manager: ActionManager,
        event_system: EventSystem
    ):
        """
        Initialize the teleport manager
        
        Args:
            config_manager: Configuration manager
            action_manager: Action manager
            event_system: Event system
        """
        self.config_manager = config_manager
        self.action_manager = action_manager
        self.event_system = event_system
        
        # Teleport locations
        self.teleport_locations: Dict[str, TeleportLocation] = {}
        
        # Load teleport locations from config
        self._load_teleport_locations()
        
        # Register emergency teleport hotkey
        self._register_emergency_teleport()
        
        logger.info("Teleport manager initialized")
    
    def _load_teleport_locations(self) -> None:
        """Load teleport locations from config"""
        teleport_locations_data = self.config_manager.get('teleport_locations', [])
        
        for location_data in teleport_locations_data:
            try:
                location = TeleportLocation.from_dict(location_data)
                self.teleport_locations[location.name] = location
                logger.debug(f"Loaded teleport location: {location}")
            except Exception as e:
                logger.error(f"Error loading teleport location: {e}")
    
    def _save_teleport_locations(self) -> None:
        """Save teleport locations to config"""
        teleport_locations_data = [
            location.to_dict() for location in self.teleport_locations.values()
        ]
        
        self.config_manager.set('teleport_locations', teleport_locations_data)
        logger.debug(f"Saved {len(teleport_locations_data)} teleport locations")
    
    def _register_emergency_teleport(self) -> None:
        """Register emergency teleport hotkey"""
        emergency_hotkey = self.config_manager.get('emergency_teleport_hotkey', 'ctrl+h')
        
        if emergency_hotkey:
            self.action_manager.register_key_action(
                name="emergency_teleport",
                key=emergency_hotkey,
                cooldown=1.0,
                priority=100,  # High priority
                post_action=lambda: self._on_emergency_teleport()
            )
            
            logger.info(f"Registered emergency teleport hotkey: {emergency_hotkey}")
    
    def _on_emergency_teleport(self) -> bool:
        """Handle emergency teleport action"""
        logger.info("Emergency teleport triggered")
        
        # Find emergency teleport location
        emergency_locations = [
            loc for loc in self.teleport_locations.values() 
            if loc.is_emergency and not loc.is_on_cooldown()
        ]
        
        if not emergency_locations:
            logger.warning("No available emergency teleport locations")
            return False
        
        # Use first available emergency teleport
        location = emergency_locations[0]
        success = self.teleport_to(location.name)
        
        if success:
            # Publish teleport event
            self.event_system.publish(
                EventType.TELEPORT_USED,
                {
                    'location': location.name,
                    'emergency': True
                }
            )
        
        return success
    
    def add_teleport_location(
        self,
        name: str,
        coordinate: Optional[Coordinate] = None,
        hotkey: Optional[str] = None,
        cooldown: float = 5.0,
        is_emergency: bool = False
    ) -> bool:
        """
        Add a new teleport location
        
        Args:
            name: Name of the teleport location
            coordinate: Coordinate for clicking (if hotkey not used)
            hotkey: Hotkey for teleporting (optional)
            cooldown: Cooldown time in seconds
            is_emergency: Whether this is an emergency teleport
        
        Returns:
            True if location was added, False otherwise
        """
        # Validate parameters
        if not name:
            logger.error("Teleport location name cannot be empty")
            return False
        
        if name in self.teleport_locations:
            logger.warning(f"Teleport location '{name}' already exists")
            return False
        
        if not coordinate and not hotkey:
            logger.error("Teleport location must have either coordinate or hotkey")
            return False
        
        # Create teleport location
        location = TeleportLocation(
            name=name,
            coordinate=coordinate,
            hotkey=hotkey,
            cooldown=cooldown,
            is_emergency=is_emergency
        )
        
        # Add to locations
        self.teleport_locations[name] = location
        
        # Save to config
        self._save_teleport_locations()
        
        logger.info(f"Added teleport location: {location}")
        return True
    
    def remove_teleport_location(self, name: str) -> bool:
        """
        Remove a teleport location
        
        Args:
            name: Name of the teleport location
        
        Returns:
            True if location was removed, False otherwise
        """
        if name not in self.teleport_locations:
            logger.warning(f"Teleport location '{name}' not found")
            return False
        
        # Remove from locations
        del self.teleport_locations[name]
        
        # Save to config
        self._save_teleport_locations()
        
        logger.info(f"Removed teleport location: {name}")
        return True
    
    def get_teleport_locations(self) -> List[TeleportLocation]:
        """
        Get all teleport locations
        
        Returns:
            List of teleport locations
        """
        return list(self.teleport_locations.values())
    
    def get_teleport_location(self, name: str) -> Optional[TeleportLocation]:
        """
        Get a teleport location by name
        
        Args:
            name: Name of the teleport location
        
        Returns:
            Teleport location or None if not found
        """
        return self.teleport_locations.get(name)
    
    def teleport_to(self, name: str) -> bool:
        """
        Teleport to a location
        
        Args:
            name: Name of the teleport location
        
        Returns:
            True if teleport was successful, False otherwise
        """
        # Check feature toggle
        if not self.config_manager.get('enable_teleport', True):
            logger.info("Teleport feature disabled; skipping teleport")
            return False

        # Get teleport location
        location = self.get_teleport_location(name)
        
        if not location:
            logger.warning(f"Teleport location '{name}' not found")
            return False
        
        # Check cooldown
        if location.is_on_cooldown():
            remaining = location.get_cooldown_remaining()
            logger.warning(f"Teleport '{name}' is on cooldown for {remaining:.1f}s")
            return False
        
        # Execute teleport
        success = False
        
        if location.hotkey:
            # Use hotkey
            logger.info(f"Teleporting to '{name}' using hotkey {location.hotkey}")
            success = self.action_manager.register_key_action(
                name=f"teleport_{name}",
                key=location.hotkey,
                cooldown=location.cooldown,
                priority=50
            )
            
            if success:
                success = self.action_manager.execute_action(f"teleport_{name}")
        
        elif location.coordinate:
            # Use coordinate; treat as window-relative when within current window bounds, else legacy absolute
            try:
                from ..detection.capture import CaptureService  # type: ignore
                bbox = CaptureService().get_window_bbox()
                win_w = int(bbox.get('width', 0))
                win_h = int(bbox.get('height', 0))
                cx = int(location.coordinate.x)
                cy = int(location.coordinate.y)
                if 0 <= cx <= win_w and 0 <= cy <= win_h:
                    abs_x = int(bbox.get('left', 0)) + cx
                    abs_y = int(bbox.get('top', 0)) + cy
                else:
                    # Assume legacy absolute
                    abs_x = cx
                    abs_y = cy
            except Exception:
                abs_x = int(location.coordinate.x)
                abs_y = int(location.coordinate.y)
            logger.info(f"Teleporting to '{name}' using coordinate (abs) {abs_x}, {abs_y}")
            # Perform deterministic click: bypass anti-overclick guard and ROI clamping
            success = self.action_manager.mouse_controller.move_and_click(
                abs_x,
                abs_y,
                enforce_guard=False,
                clamp_to_search_roi=False
            )
        
        else:
            logger.error(f"Teleport location '{name}' has no hotkey or coordinate")
            return False
        
        # Update last used time
        if success:
            location.last_used = time.time()
            
            # Publish teleport event
            self.event_system.publish(
                EventType.TELEPORT_USED,
                {
                    'location': name,
                    'emergency': location.is_emergency
                }
            )
            
            logger.info(f"Teleported to '{name}' successfully")
        else:
            logger.error(f"Failed to teleport to '{name}'")
        
        return success
    
    def emergency_teleport(self) -> bool:
        """
        Execute emergency teleport
        
        Returns:
            True if emergency teleport was successful, False otherwise
        """
        # Find emergency teleport location
        emergency_locations = [
            loc for loc in self.teleport_locations.values() 
            if loc.is_emergency and not loc.is_on_cooldown()
        ]
        
        if not emergency_locations:
            logger.warning("No available emergency teleport locations")
            return False
        
        # Sort by priority (is_emergency first, then by name)
        emergency_locations.sort(key=lambda loc: (not loc.is_emergency, loc.name))
        
        # Use first available emergency teleport
        location = emergency_locations[0]
        return self.teleport_to(location.name)