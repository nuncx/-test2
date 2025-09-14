"""
Action management for RSPS Color Bot v3
"""
import time
import logging
import threading
from typing import Dict, List, Any, Optional, Callable, Tuple

from ..config import ConfigManager, Coordinate
from .mouse_controller import MouseController
from .keyboard_controller import KeyboardController

# Get module logger
logger = logging.getLogger('rspsbot.core.action.action_manager')

class Action:
    """
    Base class for actions
    
    Actions represent operations that can be performed by the bot,
    such as clicking, moving, or using keyboard shortcuts.
    """
    
    def __init__(self, name: str, priority: int = 0):
        """
        Initialize an action
        
        Args:
            name: Action name
            priority: Action priority (higher values = higher priority)
        """
        self.name = name
        self.priority = priority
        self.last_execution_time = 0
        self.cooldown = 0
        self.success_count = 0
        self.failure_count = 0
    
    def can_execute(self) -> bool:
        """
        Check if action can be executed
        
        Returns:
            True if action can be executed, False otherwise
        """
        # Check cooldown
        if self.cooldown > 0 and time.time() - self.last_execution_time < self.cooldown:
            return False
        
        return True
    
    def execute(self) -> bool:
        """
        Execute the action
        
        Returns:
            True if action was executed successfully, False otherwise
        """
        # This method should be overridden by subclasses
        raise NotImplementedError("Subclasses must implement execute()")
    
    def get_cooldown_remaining(self) -> float:
        """
        Get remaining cooldown time in seconds
        
        Returns:
            Remaining cooldown time in seconds (0 if no cooldown)
        """
        if self.cooldown <= 0:
            return 0
        
        remaining = self.cooldown - (time.time() - self.last_execution_time)
        return max(0, remaining)
    
    def reset_cooldown(self):
        """Reset cooldown timer"""
        self.last_execution_time = 0
    
    def __str__(self) -> str:
        return f"Action({self.name}, priority={self.priority})"

class ClickAction(Action):
    """Action that clicks at a specific position"""
    
    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        button: str = 'left',
        clicks: int = 1,
        cooldown: float = 0,
        priority: int = 0,
        pre_action: Optional[Callable[[], bool]] = None,
        post_action: Optional[Callable[[], bool]] = None
    ):
        """
        Initialize a click action
        
        Args:
            name: Action name
            x, y: Click coordinates
            button: Mouse button ('left', 'right', 'middle')
            clicks: Number of clicks
            cooldown: Cooldown time in seconds
            priority: Action priority
            pre_action: Function to call before executing action
            post_action: Function to call after executing action
        """
        super().__init__(name, priority)
        self.x = x
        self.y = y
        self.button = button
        self.clicks = clicks
        self.cooldown = cooldown
        self.pre_action = pre_action
        self.post_action = post_action
    
    def execute(self, mouse_controller: MouseController) -> bool:
        """
        Execute the click action
        
        Args:
            mouse_controller: Mouse controller to use
        
        Returns:
            True if action was executed successfully, False otherwise
        """
        # Check if action can be executed
        if not self.can_execute():
            logger.debug(f"Action {self.name} is on cooldown")
            return False
        
        # Execute pre-action if any
        if self.pre_action:
            try:
                if not self.pre_action():
                    logger.debug(f"Pre-action for {self.name} failed")
                    self.failure_count += 1
                    return False
            except Exception as e:
                logger.error(f"Error in pre-action for {self.name}: {e}")
                self.failure_count += 1
                return False
        
        # Execute click
        success = mouse_controller.move_and_click(
            self.x,
            self.y,
            button=self.button,
            clicks=self.clicks
        )
        
        # Update execution time and counters
        self.last_execution_time = time.time()
        
        if success:
            self.success_count += 1
            
            # Execute post-action if any
            if self.post_action:
                try:
                    if not self.post_action():
                        logger.warning(f"Post-action for {self.name} failed")
                except Exception as e:
                    logger.error(f"Error in post-action for {self.name}: {e}")
        else:
            self.failure_count += 1
        
        return success

class KeyAction(Action):
    """Action that presses a key or hotkey"""
    
    def __init__(
        self,
        name: str,
        key: str,
        hold_time: Optional[float] = None,
        cooldown: float = 0,
        priority: int = 0,
        pre_action: Optional[Callable[[], bool]] = None,
        post_action: Optional[Callable[[], bool]] = None
    ):
        """
        Initialize a key action
        
        Args:
            name: Action name
            key: Key or hotkey to press
            hold_time: Time to hold key in seconds (None for default)
            cooldown: Cooldown time in seconds
            priority: Action priority
            pre_action: Function to call before executing action
            post_action: Function to call after executing action
        """
        super().__init__(name, priority)
        self.key = key
        self.hold_time = hold_time
        self.cooldown = cooldown
        self.pre_action = pre_action
        self.post_action = post_action
    
    def execute(self, keyboard_controller: KeyboardController) -> bool:
        """
        Execute the key action
        
        Args:
            keyboard_controller: Keyboard controller to use
        
        Returns:
            True if action was executed successfully, False otherwise
        """
        # Check if action can be executed
        if not self.can_execute():
            logger.debug(f"Action {self.name} is on cooldown")
            return False
        
        # Execute pre-action if any
        if self.pre_action:
            try:
                if not self.pre_action():
                    logger.debug(f"Pre-action for {self.name} failed")
                    self.failure_count += 1
                    return False
            except Exception as e:
                logger.error(f"Error in pre-action for {self.name}: {e}")
                self.failure_count += 1
                return False
        
        # Execute key press
        if '+' in self.key:
            # Hotkey
            success = keyboard_controller.press_hotkey(self.key)
        else:
            # Single key
            success = keyboard_controller.press_key(self.key, self.hold_time)
        
        # Update execution time and counters
        self.last_execution_time = time.time()
        
        if success:
            self.success_count += 1
            
            # Execute post-action if any
            if self.post_action:
                try:
                    if not self.post_action():
                        logger.warning(f"Post-action for {self.name} failed")
                except Exception as e:
                    logger.error(f"Error in post-action for {self.name}: {e}")
        else:
            self.failure_count += 1
        
        return success

class SequenceAction(Action):
    """Action that executes a sequence of other actions"""
    
    def __init__(
        self,
        name: str,
        actions: List[Action],
        cooldown: float = 0,
        priority: int = 0,
        pre_action: Optional[Callable[[], bool]] = None,
        post_action: Optional[Callable[[], bool]] = None
    ):
        """
        Initialize a sequence action
        
        Args:
            name: Action name
            actions: List of actions to execute in sequence
            cooldown: Cooldown time in seconds
            priority: Action priority
            pre_action: Function to call before executing action
            post_action: Function to call after executing action
        """
        super().__init__(name, priority)
        self.actions = actions
        self.cooldown = cooldown
        self.pre_action = pre_action
        self.post_action = post_action
    
    def execute(self, action_manager) -> bool:
        """
        Execute the sequence of actions
        
        Args:
            action_manager: Action manager to use
        
        Returns:
            True if all actions were executed successfully, False otherwise
        """
        # Check if action can be executed
        if not self.can_execute():
            logger.debug(f"Action {self.name} is on cooldown")
            return False
        
        # Execute pre-action if any
        if self.pre_action:
            try:
                if not self.pre_action():
                    logger.debug(f"Pre-action for {self.name} failed")
                    self.failure_count += 1
                    return False
            except Exception as e:
                logger.error(f"Error in pre-action for {self.name}: {e}")
                self.failure_count += 1
                return False
        
        # Execute actions in sequence
        success = True
        
        for action in self.actions:
            if not action_manager.execute_action(action):
                success = False
                break
        
        # Update execution time and counters
        self.last_execution_time = time.time()
        
        if success:
            self.success_count += 1
            
            # Execute post-action if any
            if self.post_action:
                try:
                    if not self.post_action():
                        logger.warning(f"Post-action for {self.name} failed")
                except Exception as e:
                    logger.error(f"Error in post-action for {self.name}: {e}")
        else:
            self.failure_count += 1
        
        return success

class ActionManager:
    """
    Manages actions for the bot
    
    This class provides methods to register, prioritize, and execute actions.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the action manager
        
        Args:
            config_manager: Configuration manager
        """
        self.config_manager = config_manager
        
        # Controllers
        self.mouse_controller = MouseController(config_manager)
        self.keyboard_controller = KeyboardController(config_manager)
        
        # Actions
        self.actions = {}
        self._action_lock = threading.RLock()
        
        logger.info("Action manager initialized")
    
    def register_action(self, action: Action) -> bool:
        """
        Register an action
        
        Args:
            action: Action to register
        
        Returns:
            True if action was registered, False otherwise
        """
        with self._action_lock:
            if action.name in self.actions:
                logger.warning(f"Action {action.name} already registered")
                return False
            
            self.actions[action.name] = action
            logger.debug(f"Registered action: {action}")
            return True
    
    def register_click_action(
        self,
        name: str,
        x: int,
        y: int,
        button: str = 'left',
        clicks: int = 1,
        cooldown: float = 0,
        priority: int = 0,
        pre_action: Optional[Callable[[], bool]] = None,
        post_action: Optional[Callable[[], bool]] = None
    ) -> bool:
        """
        Register a click action
        
        Args:
            name: Action name
            x, y: Click coordinates
            button: Mouse button ('left', 'right', 'middle')
            clicks: Number of clicks
            cooldown: Cooldown time in seconds
            priority: Action priority
            pre_action: Function to call before executing action
            post_action: Function to call after executing action
        
        Returns:
            True if action was registered, False otherwise
        """
        action = ClickAction(name, x, y, button, clicks, cooldown, priority, pre_action, post_action)
        return self.register_action(action)
    
    def register_key_action(
        self,
        name: str,
        key: str,
        hold_time: Optional[float] = None,
        cooldown: float = 0,
        priority: int = 0,
        pre_action: Optional[Callable[[], bool]] = None,
        post_action: Optional[Callable[[], bool]] = None
    ) -> bool:
        """
        Register a key action
        
        Args:
            name: Action name
            key: Key or hotkey to press
            hold_time: Time to hold key in seconds (None for default)
            cooldown: Cooldown time in seconds
            priority: Action priority
            pre_action: Function to call before executing action
            post_action: Function to call after executing action
        
        Returns:
            True if action was registered, False otherwise
        """
        action = KeyAction(name, key, hold_time, cooldown, priority, pre_action, post_action)
        return self.register_action(action)
    
    def register_sequence_action(
        self,
        name: str,
        action_names: List[str],
        cooldown: float = 0,
        priority: int = 0,
        pre_action: Optional[Callable[[], bool]] = None,
        post_action: Optional[Callable[[], bool]] = None
    ) -> bool:
        """
        Register a sequence action
        
        Args:
            name: Action name
            action_names: List of action names to execute in sequence
            cooldown: Cooldown time in seconds
            priority: Action priority
            pre_action: Function to call before executing action
            post_action: Function to call after executing action
        
        Returns:
            True if action was registered, False otherwise
        """
        with self._action_lock:
            # Get actions by name
            actions = []
            
            for action_name in action_names:
                if action_name not in self.actions:
                    logger.warning(f"Action {action_name} not found")
                    return False
                
                actions.append(self.actions[action_name])
            
            # Create sequence action
            action = SequenceAction(name, actions, cooldown, priority, pre_action, post_action)
            return self.register_action(action)
    
    def register_coordinate_action(
        self,
        name: str,
        coordinate: Coordinate,
        button: str = 'left',
        clicks: int = 1,
        cooldown: float = 0,
        priority: int = 0,
        pre_action: Optional[Callable[[], bool]] = None,
        post_action: Optional[Callable[[], bool]] = None
    ) -> bool:
        """
        Register a click action at a coordinate
        
        Args:
            name: Action name
            coordinate: Coordinate to click
            button: Mouse button ('left', 'right', 'middle')
            clicks: Number of clicks
            cooldown: Cooldown time in seconds
            priority: Action priority
            pre_action: Function to call before executing action
            post_action: Function to call after executing action
        
        Returns:
            True if action was registered, False otherwise
        """
        action = ClickAction(name, coordinate.x, coordinate.y, button, clicks, cooldown, priority, pre_action, post_action)
        return self.register_action(action)
    
    def unregister_action(self, name: str) -> bool:
        """
        Unregister an action
        
        Args:
            name: Action name
        
        Returns:
            True if action was unregistered, False otherwise
        """
        with self._action_lock:
            if name not in self.actions:
                logger.warning(f"Action {name} not found")
                return False
            
            del self.actions[name]
            logger.debug(f"Unregistered action: {name}")
            return True
    
    def get_action(self, name: str) -> Optional[Action]:
        """
        Get an action by name
        
        Args:
            name: Action name
        
        Returns:
            Action or None if not found
        """
        return self.actions.get(name)
    
    def execute_action(self, action_or_name: Any) -> bool:
        """
        Execute an action
        
        Args:
            action_or_name: Action or action name
        
        Returns:
            True if action was executed successfully, False otherwise
        """
        # Get action by name if string
        if isinstance(action_or_name, str):
            action = self.get_action(action_or_name)
            if action is None:
                logger.warning(f"Action {action_or_name} not found")
                return False
        else:
            action = action_or_name
        
        # Execute action based on type
        if isinstance(action, ClickAction):
            return action.execute(self.mouse_controller)
        elif isinstance(action, KeyAction):
            return action.execute(self.keyboard_controller)
        elif isinstance(action, SequenceAction):
            return action.execute(self)
        else:
            logger.warning(f"Unknown action type: {type(action)}")
            return False
    
    def get_highest_priority_action(self) -> Optional[Action]:
        """
        Get the highest priority action that can be executed
        
        Returns:
            Highest priority action or None if no actions can be executed
        """
        with self._action_lock:
            executable_actions = [a for a in self.actions.values() if a.can_execute()]
            
            if not executable_actions:
                return None
            
            return max(executable_actions, key=lambda a: a.priority)
    
    def execute_highest_priority_action(self) -> bool:
        """
        Execute the highest priority action
        
        Returns:
            True if an action was executed successfully, False otherwise
        """
        action = self.get_highest_priority_action()
        
        if action is None:
            return False
        
        return self.execute_action(action)
    
    def is_action_on_cooldown(self, name: str) -> bool:
        """
        Check if an action is on cooldown
        
        Args:
            name: Action name
        
        Returns:
            True if action is on cooldown, False otherwise
        """
        action = self.get_action(name)
        
        if action is None:
            return False
        
        return not action.can_execute()
    
    def get_action_cooldown_remaining(self, name: str) -> float:
        """
        Get remaining cooldown time for an action
        
        Args:
            name: Action name
        
        Returns:
            Remaining cooldown time in seconds (0 if no cooldown or action not found)
        """
        action = self.get_action(name)
        
        if action is None:
            return 0
        
        return action.get_cooldown_remaining()
    
    def reset_action_cooldown(self, name: str) -> bool:
        """
        Reset cooldown for an action
        
        Args:
            name: Action name
        
        Returns:
            True if cooldown was reset, False if action not found
        """
        action = self.get_action(name)
        
        if action is None:
            return False
        
        action.reset_cooldown()
        return True
    
    def get_action_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for an action
        
        Args:
            name: Action name
        
        Returns:
            Dictionary with action statistics or None if action not found
        """
        action = self.get_action(name)
        
        if action is None:
            return None
        
        return {
            'name': action.name,
            'priority': action.priority,
            'cooldown': action.cooldown,
            'cooldown_remaining': action.get_cooldown_remaining(),
            'success_count': action.success_count,
            'failure_count': action.failure_count,
            'total_count': action.success_count + action.failure_count,
            'success_rate': action.success_count / max(1, action.success_count + action.failure_count)
        }
    
    def get_all_action_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all actions
        
        Returns:
            Dictionary with action statistics for all actions
        """
        return {name: self.get_action_stats(name) for name in self.actions}