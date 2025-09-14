"""
Humanized action sequences for RSPS Color Bot v3
"""
import logging
import time
import random
from typing import List, Dict, Any, Optional, Callable, Tuple, Union

from .humanized_mouse import HumanizedMouse, MouseMovementProfile
from .humanized_keyboard import HumanizedKeyboard, KeyboardProfile

# Get module logger
logger = logging.getLogger('rspsbot.core.action.action_sequence')

class ActionType:
    """Action type constants"""
    MOUSE_MOVE = "mouse_move"
    MOUSE_CLICK = "mouse_click"
    MOUSE_DRAG = "mouse_drag"
    KEY_PRESS = "key_press"
    KEY_HOTKEY = "key_hotkey"
    TYPE_TEXT = "type_text"
    WAIT = "wait"
    THINK = "think"
    CUSTOM = "custom"

class ActionSequenceProfile:
    """
    Profile for customizing action sequence characteristics
    """
    
    def __init__(
        self,
        action_delay_factor: float = 1.0,
        action_delay_variability: float = 1.0,
        think_probability: float = 0.1,
        think_duration_factor: float = 1.0,
        fatigue_rate: float = 0.0,
        mouse_profile: Optional[Union[MouseMovementProfile, str]] = None,
        keyboard_profile: Optional[Union[KeyboardProfile, str]] = None
    ):
        """
        Initialize action sequence profile
        
        Args:
            action_delay_factor: Factor affecting delay between actions (higher = longer delays)
            action_delay_variability: Factor affecting variability in delays (higher = more variable)
            think_probability: Probability of adding thinking pauses between actions
            think_duration_factor: Factor affecting thinking pause duration (higher = longer)
            fatigue_rate: Rate at which delays increase over time (0.0 = no fatigue)
            mouse_profile: Mouse movement profile or profile type
            keyboard_profile: Keyboard profile or profile type
        """
        self.action_delay_factor = max(0.1, min(5.0, action_delay_factor))
        self.action_delay_variability = max(0.1, min(5.0, action_delay_variability))
        self.think_probability = max(0.0, min(0.5, think_probability))
        self.think_duration_factor = max(0.1, min(5.0, think_duration_factor))
        self.fatigue_rate = max(0.0, min(0.1, fatigue_rate))
        
        # Set mouse profile
        if isinstance(mouse_profile, MouseMovementProfile):
            self.mouse_profile = mouse_profile
        elif isinstance(mouse_profile, str):
            self.mouse_profile = MouseMovementProfile.create_profile(mouse_profile)
        else:
            self.mouse_profile = MouseMovementProfile.create_profile('human')
        
        # Set keyboard profile
        if isinstance(keyboard_profile, KeyboardProfile):
            self.keyboard_profile = keyboard_profile
        elif isinstance(keyboard_profile, str):
            self.keyboard_profile = KeyboardProfile.create_profile(keyboard_profile)
        else:
            self.keyboard_profile = KeyboardProfile.create_profile('human')
    
    @classmethod
    def create_profile(cls, profile_type: str) -> 'ActionSequenceProfile':
        """
        Create a predefined action sequence profile
        
        Args:
            profile_type: Profile type ('human', 'fast', 'precise', 'erratic', 'tired')
        
        Returns:
            ActionSequenceProfile instance
        """
        if profile_type == 'human':
            return cls(
                action_delay_factor=1.0,
                action_delay_variability=1.0,
                think_probability=0.1,
                think_duration_factor=1.0,
                fatigue_rate=0.001,
                mouse_profile='human',
                keyboard_profile='human'
            )
        elif profile_type == 'fast':
            return cls(
                action_delay_factor=0.5,
                action_delay_variability=0.7,
                think_probability=0.05,
                think_duration_factor=0.5,
                fatigue_rate=0.0005,
                mouse_profile='fast',
                keyboard_profile='fast'
            )
        elif profile_type == 'precise':
            return cls(
                action_delay_factor=1.2,
                action_delay_variability=0.5,
                think_probability=0.02,
                think_duration_factor=0.7,
                fatigue_rate=0.0,
                mouse_profile='precise',
                keyboard_profile='precise'
            )
        elif profile_type == 'erratic':
            return cls(
                action_delay_factor=0.8,
                action_delay_variability=2.0,
                think_probability=0.2,
                think_duration_factor=1.5,
                fatigue_rate=0.002,
                mouse_profile='erratic',
                keyboard_profile='erratic'
            )
        elif profile_type == 'tired':
            return cls(
                action_delay_factor=1.5,
                action_delay_variability=1.8,
                think_probability=0.15,
                think_duration_factor=2.0,
                fatigue_rate=0.005,
                mouse_profile='human',
                keyboard_profile='slow'
            )
        else:
            logger.warning(f"Unknown profile type: {profile_type}, using 'human' profile")
            return cls.create_profile('human')

class ActionSequence:
    """
    Humanized action sequence implementation
    
    This class coordinates sequences of actions with natural timing and variations.
    """
    
    def __init__(
        self,
        profile: Optional[Union[ActionSequenceProfile, str]] = None,
        pyautogui_module=None
    ):
        """
        Initialize action sequence
        
        Args:
            profile: Action sequence profile or profile type
            pyautogui_module: PyAutoGUI module (for testing with mock)
        """
        # Set profile
        if isinstance(profile, ActionSequenceProfile):
            self.profile = profile
        elif isinstance(profile, str):
            self.profile = ActionSequenceProfile.create_profile(profile)
        else:
            self.profile = ActionSequenceProfile.create_profile('human')
        
        # Create humanized controllers
        self.mouse = HumanizedMouse(pyautogui_module)
        self.keyboard = HumanizedKeyboard(pyautogui_module)
        
        # Apply profiles
        self.mouse.set_profile(self.profile.mouse_profile)
        self.keyboard.set_profile(self.profile.keyboard_profile)
        
        # Sequence state
        self.sequence_start_time = 0
        self.last_action_time = 0
        self.action_count = 0
    
    def set_profile(self, profile: Union[ActionSequenceProfile, str]):
        """
        Set action sequence profile
        
        Args:
            profile: ActionSequenceProfile instance or profile type string
        """
        if isinstance(profile, str):
            self.profile = ActionSequenceProfile.create_profile(profile)
        else:
            self.profile = profile
        
        # Apply profiles to controllers
        self.mouse.set_profile(self.profile.mouse_profile)
        self.keyboard.set_profile(self.profile.keyboard_profile)
        
        logger.debug(f"Action sequence profile set: delay_factor={self.profile.action_delay_factor}, "
                    f"variability={self.profile.action_delay_variability}, "
                    f"think_prob={self.profile.think_probability}, "
                    f"fatigue_rate={self.profile.fatigue_rate}")
    
    def _get_action_delay(self, action_type: str) -> float:
        """
        Calculate delay before executing an action
        
        Args:
            action_type: Type of action
        
        Returns:
            Delay in seconds
        """
        # Base delay based on action type
        if action_type == ActionType.MOUSE_MOVE:
            base_delay = 0.1
        elif action_type == ActionType.MOUSE_CLICK:
            base_delay = 0.2
        elif action_type == ActionType.MOUSE_DRAG:
            base_delay = 0.3
        elif action_type == ActionType.KEY_PRESS:
            base_delay = 0.15
        elif action_type == ActionType.KEY_HOTKEY:
            base_delay = 0.25
        elif action_type == ActionType.TYPE_TEXT:
            base_delay = 0.3
        else:
            base_delay = 0.2
        
        # Apply profile factor
        base_delay *= self.profile.action_delay_factor
        
        # Apply variability
        variability_factor = random.uniform(
            1.0 - 0.3 * self.profile.action_delay_variability,
            1.0 + 0.3 * self.profile.action_delay_variability
        )
        
        # Apply fatigue if enabled
        if self.profile.fatigue_rate > 0 and self.sequence_start_time > 0:
            elapsed_time = time.time() - self.sequence_start_time
            fatigue_factor = 1.0 + (elapsed_time / 60.0) * self.profile.fatigue_rate
            base_delay *= min(2.0, fatigue_factor)  # Cap at 2x slowdown
        
        return base_delay * variability_factor
    
    def _should_add_thinking_pause(self) -> bool:
        """
        Determine if a thinking pause should be added
        
        Returns:
            True if thinking pause should be added
        """
        return random.random() < self.profile.think_probability
    
    def _get_thinking_duration(self) -> float:
        """
        Calculate thinking pause duration
        
        Returns:
            Thinking duration in seconds
        """
        # Base thinking duration (0.5 to 2.0 seconds)
        base_duration = random.uniform(0.5, 2.0)
        
        # Apply profile factor
        base_duration *= self.profile.think_duration_factor
        
        # Apply fatigue if enabled
        if self.profile.fatigue_rate > 0 and self.sequence_start_time > 0:
            elapsed_time = time.time() - self.sequence_start_time
            fatigue_factor = 1.0 + (elapsed_time / 60.0) * self.profile.fatigue_rate * 2.0
            base_duration *= min(3.0, fatigue_factor)  # Cap at 3x longer thinking
        
        return base_duration
    
    def start_sequence(self):
        """Start a new action sequence"""
        self.sequence_start_time = time.time()
        self.last_action_time = self.sequence_start_time
        self.action_count = 0
        
        logger.debug("Starting new action sequence")
    
    def end_sequence(self):
        """End the current action sequence"""
        if self.sequence_start_time > 0:
            elapsed_time = time.time() - self.sequence_start_time
            logger.debug(f"Ending action sequence: {self.action_count} actions in {elapsed_time:.2f}s")
        
        self.sequence_start_time = 0
        self.last_action_time = 0
        self.action_count = 0
    
    def execute_action(self, action: Dict[str, Any]) -> bool:
        """
        Execute a single action with humanized timing
        
        Args:
            action: Action dictionary with type and parameters
        
        Returns:
            True if action was executed successfully
        """
        try:
            # Start sequence if not already started
            if self.sequence_start_time == 0:
                self.start_sequence()
            
            # Get action type
            action_type = action.get('type')
            if not action_type:
                logger.error("Action missing type")
                return False
            
            # Calculate delay before action
            delay = self._get_action_delay(action_type)
            
            # Add thinking pause if applicable
            if self.action_count > 0 and self._should_add_thinking_pause():
                think_duration = self._get_thinking_duration()
                logger.debug(f"Adding thinking pause: {think_duration:.2f}s")
                time.sleep(think_duration)
            
            # Wait before executing action
            time.sleep(delay)
            
            # Execute action based on type
            result = False
            
            if action_type == ActionType.MOUSE_MOVE:
                result = self.mouse.move_to(
                    action.get('x'),
                    action.get('y'),
                    action.get('duration')
                )
            
            elif action_type == ActionType.MOUSE_CLICK:
                result = self.mouse.click(
                    action.get('x'),
                    action.get('y'),
                    action.get('button', 'left'),
                    action.get('clicks', 1),
                    action.get('interval'),
                    action.get('duration')
                )
            
            elif action_type == ActionType.MOUSE_DRAG:
                result = self.mouse.drag_to(
                    action.get('x'),
                    action.get('y'),
                    action.get('button', 'left'),
                    action.get('duration')
                )
            
            elif action_type == ActionType.KEY_PRESS:
                result = self.keyboard.press_key(
                    action.get('key'),
                    action.get('hold_time')
                )
            
            elif action_type == ActionType.KEY_HOTKEY:
                result = self.keyboard.press_hotkey(
                    action.get('keys')
                )
            
            elif action_type == ActionType.TYPE_TEXT:
                result = self.keyboard.type_string(
                    action.get('text'),
                    action.get('error_correction', True)
                )
            
            elif action_type == ActionType.WAIT:
                duration = action.get('duration', 1.0)
                time.sleep(duration)
                result = True
            
            elif action_type == ActionType.THINK:
                duration = action.get('duration')
                if duration is None:
                    duration = self._get_thinking_duration()
                time.sleep(duration)
                result = True
            
            elif action_type == ActionType.CUSTOM:
                custom_func = action.get('function')
                if callable(custom_func):
                    args = action.get('args', [])
                    kwargs = action.get('kwargs', {})
                    result = custom_func(*args, **kwargs)
                else:
                    logger.error("Custom action missing function")
                    result = False
            
            else:
                logger.error(f"Unknown action type: {action_type}")
                result = False
            
            # Update state
            self.last_action_time = time.time()
            self.action_count += 1
            
            return result
        
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            return False
    
    def execute_sequence(self, actions: List[Dict[str, Any]]) -> bool:
        """
        Execute a sequence of actions with humanized timing
        
        Args:
            actions: List of action dictionaries
        
        Returns:
            True if all actions were executed successfully
        """
        try:
            # Start new sequence
            self.start_sequence()
            
            # Execute each action
            success = True
            for action in actions:
                if not self.execute_action(action):
                    success = False
                    break
            
            # End sequence
            self.end_sequence()
            
            return success
        
        except Exception as e:
            logger.error(f"Error executing action sequence: {e}")
            self.end_sequence()
            return False
    
    def move_to(self, x: int, y: int, duration: Optional[float] = None) -> bool:
        """
        Move mouse to position
        
        Args:
            x: Target x coordinate
            y: Target y coordinate
            duration: Movement duration in seconds (None for automatic)
        
        Returns:
            True if movement was successful
        """
        action = {
            'type': ActionType.MOUSE_MOVE,
            'x': x,
            'y': y,
            'duration': duration
        }
        return self.execute_action(action)
    
    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = 'left',
        clicks: int = 1,
        interval: Optional[float] = None,
        duration: Optional[float] = None
    ) -> bool:
        """
        Move to position and click
        
        Args:
            x: Target x coordinate (None for current position)
            y: Target y coordinate (None for current position)
            button: Mouse button ('left', 'right', 'middle')
            clicks: Number of clicks
            interval: Interval between clicks in seconds (None for automatic)
            duration: Movement duration in seconds (None for automatic)
        
        Returns:
            True if click was successful
        """
        action = {
            'type': ActionType.MOUSE_CLICK,
            'x': x,
            'y': y,
            'button': button,
            'clicks': clicks,
            'interval': interval,
            'duration': duration
        }
        return self.execute_action(action)
    
    def drag_to(
        self,
        x: int,
        y: int,
        button: str = 'left',
        duration: Optional[float] = None
    ) -> bool:
        """
        Drag mouse to position
        
        Args:
            x: Target x coordinate
            y: Target y coordinate
            button: Mouse button ('left', 'right', 'middle')
            duration: Movement duration in seconds (None for automatic)
        
        Returns:
            True if drag was successful
        """
        action = {
            'type': ActionType.MOUSE_DRAG,
            'x': x,
            'y': y,
            'button': button,
            'duration': duration
        }
        return self.execute_action(action)
    
    def press_key(self, key: str, hold_time: Optional[float] = None) -> bool:
        """
        Press a key
        
        Args:
            key: Key to press
            hold_time: Key hold time in seconds (None for automatic)
        
        Returns:
            True if key press was successful
        """
        action = {
            'type': ActionType.KEY_PRESS,
            'key': key,
            'hold_time': hold_time
        }
        return self.execute_action(action)
    
    def press_hotkey(self, keys: str) -> bool:
        """
        Press a hotkey combination
        
        Args:
            keys: Keys to press (e.g., 'ctrl+c')
        
        Returns:
            True if hotkey press was successful
        """
        action = {
            'type': ActionType.KEY_HOTKEY,
            'keys': keys
        }
        return self.execute_action(action)
    
    def type_string(self, text: str, error_correction: bool = True) -> bool:
        """
        Type a string
        
        Args:
            text: Text to type
            error_correction: Whether to simulate error correction
        
        Returns:
            True if typing was successful
        """
        action = {
            'type': ActionType.TYPE_TEXT,
            'text': text,
            'error_correction': error_correction
        }
        return self.execute_action(action)
    
    def wait(self, duration: float) -> bool:
        """
        Wait for specified duration
        
        Args:
            duration: Wait duration in seconds
        
        Returns:
            True if wait was successful
        """
        action = {
            'type': ActionType.WAIT,
            'duration': duration
        }
        return self.execute_action(action)
    
    def think(self, duration: Optional[float] = None) -> bool:
        """
        Add a thinking pause
        
        Args:
            duration: Thinking duration in seconds (None for automatic)
        
        Returns:
            True if thinking pause was successful
        """
        action = {
            'type': ActionType.THINK,
            'duration': duration
        }
        return self.execute_action(action)
    
    def custom_action(self, function: Callable, *args, **kwargs) -> bool:
        """
        Execute a custom action
        
        Args:
            function: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        
        Returns:
            True if custom action was successful
        """
        action = {
            'type': ActionType.CUSTOM,
            'function': function,
            'args': args,
            'kwargs': kwargs
        }
        return self.execute_action(action)