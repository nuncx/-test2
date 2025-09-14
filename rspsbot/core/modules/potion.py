"""
Potion module for RSPS Color Bot v3

This module provides potion management functionality for the bot.
"""
import logging
import time
from typing import Dict, List, Optional, Tuple, Any, Callable

from ..config import ConfigManager, Coordinate
from ..action import ActionManager
from ..state import EventSystem, EventType

# Get module logger
logger = logging.getLogger('rspsbot.core.modules.potion')

class PotionType:
    """
    Enum-like class for potion types
    """
    HEALTH = "health"
    PRAYER = "prayer"
    COMBAT = "combat"
    SPECIAL = "special"
    OTHER = "other"
    
    @classmethod
    def get_all_types(cls) -> List[str]:
        """Get all potion types"""
        return [cls.HEALTH, cls.PRAYER, cls.COMBAT, cls.SPECIAL, cls.OTHER]
    
    @classmethod
    def get_display_name(cls, potion_type: str) -> str:
        """Get display name for potion type"""
        display_names = {
            cls.HEALTH: "Health",
            cls.PRAYER: "Prayer",
            cls.COMBAT: "Combat",
            cls.SPECIAL: "Special",
            cls.OTHER: "Other"
        }
        
        return display_names.get(potion_type, potion_type)

class Potion:
    """
    Represents a potion with coordinates and metadata
    """
    
    def __init__(
        self,
        name: str,
        potion_type: str,
        coordinate: Coordinate,
        hotkey: Optional[str] = None,
        cooldown: float = 30.0,
        duration: float = 0.0,
        threshold: int = 0,
        auto_use: bool = False
    ):
        """
        Initialize a potion
        
        Args:
            name: Name of the potion
            potion_type: Type of potion (health, prayer, combat, special, other)
            coordinate: Coordinate for clicking (if hotkey not used)
            hotkey: Hotkey for using potion (optional)
            cooldown: Cooldown time in seconds
            duration: Duration of potion effect in seconds (0 for instant)
            threshold: Threshold for auto-use (e.g., HP level for health potions)
            auto_use: Whether to automatically use the potion
        """
        self.name = name
        self.potion_type = potion_type
        self.coordinate = coordinate
        self.hotkey = hotkey
        self.cooldown = cooldown
        self.duration = duration
        self.threshold = threshold
        self.auto_use = auto_use
        
        # Runtime state
        self.last_used = 0.0
        self.effect_end_time = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "name": self.name,
            "potion_type": self.potion_type,
            "coordinate": self.coordinate.to_dict() if self.coordinate else None,
            "hotkey": self.hotkey,
            "cooldown": self.cooldown,
            "duration": self.duration,
            "threshold": self.threshold,
            "auto_use": self.auto_use
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Potion':
        """Create from dictionary"""
        coordinate_data = data.get("coordinate")
        coordinate = Coordinate.from_dict(coordinate_data) if coordinate_data else None
        
        return cls(
            name=data.get("name", ""),
            potion_type=data.get("potion_type", PotionType.OTHER),
            coordinate=coordinate,
            hotkey=data.get("hotkey"),
            cooldown=data.get("cooldown", 30.0),
            duration=data.get("duration", 0.0),
            threshold=data.get("threshold", 0),
            auto_use=data.get("auto_use", False)
        )
    
    def is_on_cooldown(self) -> bool:
        """Check if potion is on cooldown"""
        return time.time() - self.last_used < self.cooldown
    
    def get_cooldown_remaining(self) -> float:
        """Get remaining cooldown time in seconds"""
        if not self.is_on_cooldown():
            return 0.0
        
        return max(0.0, self.cooldown - (time.time() - self.last_used))
    
    def is_effect_active(self) -> bool:
        """Check if potion effect is active"""
        if self.duration <= 0:
            return False
        
        return time.time() < self.effect_end_time
    
    def get_effect_remaining(self) -> float:
        """Get remaining effect time in seconds"""
        if not self.is_effect_active():
            return 0.0
        
        return max(0.0, self.effect_end_time - time.time())
    
    def reset_cooldown(self) -> None:
        """Reset cooldown timer"""
        self.last_used = 0.0
    
    def __str__(self) -> str:
        return f"Potion({self.name}, {self.potion_type}, {'hotkey' if self.hotkey else 'coordinate'}, auto={self.auto_use})"

class PotionManager:
    """
    Manages potions and potion actions
    """
    
    def __init__(
        self,
        config_manager: ConfigManager,
        action_manager: ActionManager,
        event_system: EventSystem
    ):
        """
        Initialize the potion manager
        
        Args:
            config_manager: Configuration manager
            action_manager: Action manager
            event_system: Event system
        """
        self.config_manager = config_manager
        self.action_manager = action_manager
        self.event_system = event_system
        
        # Potions
        self.potions: Dict[str, Potion] = {}
        
        # Load potions from config
        self._load_potions()
        
        logger.info("Potion manager initialized")
    
    def _load_potions(self) -> None:
        """Load potions from config"""
        potions_data = self.config_manager.get('potions', [])
        
        for potion_data in potions_data:
            try:
                potion = Potion.from_dict(potion_data)
                self.potions[potion.name] = potion
                logger.debug(f"Loaded potion: {potion}")
            except Exception as e:
                logger.error(f"Error loading potion: {e}")
    
    def _save_potions(self) -> None:
        """Save potions to config"""
        potions_data = [
            potion.to_dict() for potion in self.potions.values()
        ]
        
        self.config_manager.set('potions', potions_data)
        logger.debug(f"Saved {len(potions_data)} potions")
    
    def add_potion(
        self,
        name: str,
        potion_type: str,
        coordinate: Coordinate,
        hotkey: Optional[str] = None,
        cooldown: float = 30.0,
        duration: float = 0.0,
        threshold: int = 0,
        auto_use: bool = False
    ) -> bool:
        """
        Add a new potion
        
        Args:
            name: Name of the potion
            potion_type: Type of potion (health, prayer, combat, special, other)
            coordinate: Coordinate for clicking (if hotkey not used)
            hotkey: Hotkey for using potion (optional)
            cooldown: Cooldown time in seconds
            duration: Duration of potion effect in seconds (0 for instant)
            threshold: Threshold for auto-use (e.g., HP level for health potions)
            auto_use: Whether to automatically use the potion
        
        Returns:
            True if potion was added, False otherwise
        """
        # Validate parameters
        if not name:
            logger.error("Potion name cannot be empty")
            return False
        
        if name in self.potions:
            logger.warning(f"Potion '{name}' already exists")
            return False
        
        if not coordinate and not hotkey:
            logger.error("Potion must have either coordinate or hotkey")
            return False
        
        if potion_type not in PotionType.get_all_types():
            logger.warning(f"Unknown potion type: {potion_type}, using 'other'")
            potion_type = PotionType.OTHER
        
        # Create potion
        potion = Potion(
            name=name,
            potion_type=potion_type,
            coordinate=coordinate,
            hotkey=hotkey,
            cooldown=cooldown,
            duration=duration,
            threshold=threshold,
            auto_use=auto_use
        )
        
        # Add to potions
        self.potions[name] = potion
        
        # Save to config
        self._save_potions()
        
        logger.info(f"Added potion: {potion}")
        return True
    
    def remove_potion(self, name: str) -> bool:
        """
        Remove a potion
        
        Args:
            name: Name of the potion
        
        Returns:
            True if potion was removed, False otherwise
        """
        if name not in self.potions:
            logger.warning(f"Potion '{name}' not found")
            return False
        
        # Remove from potions
        del self.potions[name]
        
        # Save to config
        self._save_potions()
        
        logger.info(f"Removed potion: {name}")
        return True
    
    def get_potions(self) -> List[Potion]:
        """
        Get all potions
        
        Returns:
            List of potions
        """
        return list(self.potions.values())
    
    def get_potions_by_type(self, potion_type: str) -> List[Potion]:
        """
        Get potions by type
        
        Args:
            potion_type: Type of potion
        
        Returns:
            List of potions of the specified type
        """
        return [p for p in self.potions.values() if p.potion_type == potion_type]
    
    def get_potion(self, name: str) -> Optional[Potion]:
        """
        Get a potion by name
        
        Args:
            name: Name of the potion
        
        Returns:
            Potion or None if not found
        """
        return self.potions.get(name)
    
    def use_potion(self, name: str) -> bool:
        """
        Use a potion
        
        Args:
            name: Name of the potion
        
        Returns:
            True if potion was used successfully, False otherwise
        """
        # Check feature toggle
        if not self.config_manager.get('enable_potions', True):
            logger.info("Potions feature disabled; skipping potion use")
            return False

        # Get potion
        potion = self.get_potion(name)
        
        if not potion:
            logger.warning(f"Potion '{name}' not found")
            return False
        
        # Check cooldown
        if potion.is_on_cooldown():
            remaining = potion.get_cooldown_remaining()
            logger.warning(f"Potion '{name}' is on cooldown for {remaining:.1f}s")
            return False
        
        # Execute potion use
        success = False
        
        if potion.hotkey:
            # Use hotkey
            logger.info(f"Using potion '{name}' with hotkey {potion.hotkey}")
            success = self.action_manager.register_key_action(
                name=f"potion_{name}",
                key=potion.hotkey,
                cooldown=potion.cooldown,
                priority=60
            )
            
            if success:
                success = self.action_manager.execute_action(f"potion_{name}")
        
        elif potion.coordinate:
            # Use coordinate
            logger.info(f"Using potion '{name}' at coordinate {potion.coordinate.x}, {potion.coordinate.y}")
            success = self.action_manager.register_coordinate_action(
                name=f"potion_{name}",
                coordinate=potion.coordinate,
                cooldown=potion.cooldown,
                priority=60
            )
            
            if success:
                success = self.action_manager.execute_action(f"potion_{name}")
        
        else:
            logger.error(f"Potion '{name}' has no hotkey or coordinate")
            return False
        
        # Update potion state
        if success:
            potion.last_used = time.time()
            
            if potion.duration > 0:
                potion.effect_end_time = time.time() + potion.duration
            
            # Publish potion event
            self.event_system.publish(
                EventType.POTION_USED,
                {
                    'name': name,
                    'type': potion.potion_type
                }
            )
            
            logger.info(f"Used potion '{name}' successfully")
        else:
            logger.error(f"Failed to use potion '{name}'")
        
        return success
    
    def check_auto_potions(self, hp_level: int = 0, prayer_level: int = 0) -> bool:
        """
        Check and use auto-potions if needed
        
        Args:
            hp_level: Current HP level (for health potions)
            prayer_level: Current prayer level (for prayer potions)
        
        Returns:
            True if any potion was used, False otherwise
        """
        used_any = False
        
        # Check health potions
        if hp_level > 0:
            health_potions = self.get_potions_by_type(PotionType.HEALTH)
            
            for potion in health_potions:
                if (potion.auto_use and 
                    not potion.is_on_cooldown() and 
                    hp_level <= potion.threshold):
                    
                    if self.use_potion(potion.name):
                        used_any = True
                        break
        
        # Check prayer potions
        if prayer_level > 0:
            prayer_potions = self.get_potions_by_type(PotionType.PRAYER)
            
            for potion in prayer_potions:
                if (potion.auto_use and 
                    not potion.is_on_cooldown() and 
                    prayer_level <= potion.threshold):
                    
                    if self.use_potion(potion.name):
                        used_any = True
                        break
        
        # Check other auto-use potions
        for potion_type in [PotionType.COMBAT, PotionType.SPECIAL, PotionType.OTHER]:
            potions = self.get_potions_by_type(potion_type)
            
            for potion in potions:
                if (potion.auto_use and 
                    not potion.is_on_cooldown() and 
                    not potion.is_effect_active()):
                    
                    if self.use_potion(potion.name):
                        used_any = True
        
        return used_any
    
    def get_active_effects(self) -> List[Tuple[str, float]]:
        """
        Get active potion effects
        
        Returns:
            List of (potion_name, remaining_time) tuples
        """
        active_effects = []
        
        for potion in self.potions.values():
            if potion.is_effect_active():
                remaining = potion.get_effect_remaining()
                active_effects.append((potion.name, remaining))
        
        return active_effects