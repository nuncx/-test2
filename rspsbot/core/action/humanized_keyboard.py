"""
Enhanced humanized keyboard input for RSPS Color Bot v3
"""
import logging
import time
import random
import string
from typing import Dict, List, Optional, Tuple, Union, Any

# Get module logger
logger = logging.getLogger('rspsbot.core.action.humanized_keyboard')

class KeyboardProfile:
    """
    Profile for customizing keyboard input characteristics
    """
    
    def __init__(
        self,
        typing_speed: float = 1.0,
        typing_variability: float = 1.0,
        error_rate: float = 0.0,
        key_hold_time: float = 0.05,
        key_hold_variability: float = 1.0,
        adjacent_keys: Dict[str, List[str]] = None
    ):
        """
        Initialize keyboard profile
        
        Args:
            typing_speed: Base typing speed factor (higher = faster)
            typing_variability: Variability in typing speed (higher = more variable)
            error_rate: Probability of typing errors (0.0 to 0.1)
            key_hold_time: Base key hold time in seconds
            key_hold_variability: Variability in key hold time (higher = more variable)
            adjacent_keys: Dictionary mapping keys to their adjacent keys on keyboard
        """
        self.typing_speed = max(0.1, min(5.0, typing_speed))
        self.typing_variability = max(0.1, min(5.0, typing_variability))
        self.error_rate = max(0.0, min(0.1, error_rate))
        self.key_hold_time = max(0.01, min(0.2, key_hold_time))
        self.key_hold_variability = max(0.1, min(5.0, key_hold_variability))
        
        # Initialize adjacent keys for QWERTY keyboard if not provided
        if adjacent_keys is None:
            self.adjacent_keys = self._init_qwerty_adjacent_keys()
        else:
            self.adjacent_keys = adjacent_keys
    
    @classmethod
    def create_profile(cls, profile_type: str) -> 'KeyboardProfile':
        """
        Create a predefined keyboard profile
        
        Args:
            profile_type: Profile type ('human', 'fast', 'precise', 'erratic', 'slow')
        
        Returns:
            KeyboardProfile instance
        """
        if profile_type == 'human':
            return cls(
                typing_speed=1.0,
                typing_variability=1.0,
                error_rate=0.03,
                key_hold_time=0.05,
                key_hold_variability=1.0
            )
        elif profile_type == 'fast':
            return cls(
                typing_speed=2.0,
                typing_variability=0.7,
                error_rate=0.05,
                key_hold_time=0.03,
                key_hold_variability=0.7
            )
        elif profile_type == 'precise':
            return cls(
                typing_speed=0.9,
                typing_variability=0.5,
                error_rate=0.0,
                key_hold_time=0.05,
                key_hold_variability=0.5
            )
        elif profile_type == 'erratic':
            return cls(
                typing_speed=1.2,
                typing_variability=2.0,
                error_rate=0.08,
                key_hold_time=0.04,
                key_hold_variability=2.0
            )
        elif profile_type == 'slow':
            return cls(
                typing_speed=0.5,
                typing_variability=1.5,
                error_rate=0.02,
                key_hold_time=0.08,
                key_hold_variability=1.2
            )
        else:
            logger.warning(f"Unknown profile type: {profile_type}, using 'human' profile")
            return cls.create_profile('human')
    
    def _init_qwerty_adjacent_keys(self) -> Dict[str, List[str]]:
        """
        Initialize adjacent keys for QWERTY keyboard
        
        Returns:
            Dictionary mapping keys to their adjacent keys
        """
        # Define keyboard rows
        row1 = list("`1234567890-=")
        row2 = list("qwertyuiop[]\&quot;)
        row3 = list("asdfghjkl;'")
        row4 = list("zxcvbnm,./")
        
        # Create dictionary of adjacent keys
        adjacent_keys = {}
        
        # Helper function to get adjacent keys
        def get_adjacent(row: List[str], idx: int) -> List[str]:
            adjacent = []
            
            # Same row
            if idx > 0:
                adjacent.append(row[idx - 1])
            if idx < len(row) - 1:
                adjacent.append(row[idx + 1])
            
            return adjacent
        
        # Process each row
        for row_idx, row in enumerate([row1, row2, row3, row4]):
            for key_idx, key in enumerate(row):
                adjacent = get_adjacent(row, key_idx)
                
                # Add keys from row above
                if row_idx > 0:
                    above_row = [row1, row2, row3, row4][row_idx - 1]
                    # Find closest keys in above row
                    rel_pos = key_idx / len(row)
                    above_idx = min(len(above_row) - 1, int(rel_pos * len(above_row)))
                    adjacent.extend(get_adjacent(above_row, above_idx))
                    adjacent.append(above_row[above_idx])
                
                # Add keys from row below
                if row_idx < 3:
                    below_row = [row1, row2, row3, row4][row_idx + 1]
                    # Find closest keys in below row
                    rel_pos = key_idx / len(row)
                    below_idx = min(len(below_row) - 1, int(rel_pos * len(below_row)))
                    adjacent.extend(get_adjacent(below_row, below_idx))
                    adjacent.append(below_row[below_idx])
                
                adjacent_keys[key] = adjacent
                
                # Add uppercase version
                if key in string.ascii_lowercase:
                    adjacent_keys[key.upper()] = [adj.upper() if adj in string.ascii_lowercase else adj 
                                                for adj in adjacent]
        
        # Add space bar adjacent to bottom row
        for key in row4:
            if key not in adjacent_keys:
                adjacent_keys[key] = []
            adjacent_keys[key].append(' ')
        
        # Space bar is adjacent to all bottom row keys
        adjacent_keys[' '] = row4
        
        return adjacent_keys

class HumanizedKeyboard:
    """
    Enhanced humanized keyboard input implementation
    """
    
    def __init__(self, pyautogui_module=None):
        """
        Initialize humanized keyboard
        
        Args:
            pyautogui_module: PyAutoGUI module (for testing with mock)
        """
        # Import here to avoid circular imports
        if pyautogui_module is None:
            import pyautogui
            self.pyautogui = pyautogui
        else:
            self.pyautogui = pyautogui_module
        
        # Default profile
        self.profile = KeyboardProfile.create_profile('human')
        
        # Typing state
        self.last_key = None
        self.last_key_time = 0
    
    def set_profile(self, profile: Union[KeyboardProfile, str]):
        """
        Set keyboard profile
        
        Args:
            profile: KeyboardProfile instance or profile type string
        """
        if isinstance(profile, str):
            self.profile = KeyboardProfile.create_profile(profile)
        else:
            self.profile = profile
        
        logger.debug(f"Keyboard profile set: speed={self.profile.typing_speed}, "
                    f"variability={self.profile.typing_variability}, "
                    f"error_rate={self.profile.error_rate}, "
                    f"hold_time={self.profile.key_hold_time}, "
                    f"hold_variability={self.profile.key_hold_variability}")
    
    def _get_key_delay(self, key: str) -> float:
        """
        Calculate delay before pressing a key
        
        Args:
            key: Key to press
        
        Returns:
            Delay in seconds
        """
        # Base delay (lower = faster typing)
        base_delay = 0.1 / self.profile.typing_speed
        
        # Adjust delay based on key and previous key
        if self.last_key is not None:
            # Faster for repeated keys
            if key == self.last_key:
                base_delay *= 0.7
            
            # Faster for alternating hands (simplified)
            left_hand = "qwertasdfgzxcvb"
            right_hand = "yuiophjklnm"
            
            if (key.lower() in left_hand and self.last_key.lower() in right_hand) or \
               (key.lower() in right_hand and self.last_key.lower() in left_hand):
                base_delay *= 0.9
            
            # Slower for same finger on different rows
            if key.lower() in self.profile.adjacent_keys.get(self.last_key.lower(), []):
                base_delay *= 1.2
        
        # Add variability
        variability_factor = random.uniform(
            1.0 - 0.3 * self.profile.typing_variability,
            1.0 + 0.3 * self.profile.typing_variability
        )
        
        return base_delay * variability_factor
    
    def _get_key_hold_time(self) -> float:
        """
        Calculate key hold time
        
        Returns:
            Hold time in seconds
        """
        # Base hold time
        base_hold_time = self.profile.key_hold_time
        
        # Add variability
        variability_factor = random.uniform(
            1.0 - 0.3 * self.profile.key_hold_variability,
            1.0 + 0.3 * self.profile.key_hold_variability
        )
        
        return base_hold_time * variability_factor
    
    def _should_make_error(self) -> bool:
        """
        Determine if a typing error should be made
        
        Returns:
            True if error should be made
        """
        return random.random() < self.profile.error_rate
    
    def _get_error_key(self, intended_key: str) -> str:
        """
        Get an error key for the intended key
        
        Args:
            intended_key: The key that was intended to be pressed
        
        Returns:
            Error key
        """
        # Get adjacent keys
        adjacent_keys = self.profile.adjacent_keys.get(intended_key, [])
        
        if adjacent_keys:
            # 80% chance to use an adjacent key
            if random.random() < 0.8:
                return random.choice(adjacent_keys)
        
        # Otherwise use a random key
        return random.choice(string.ascii_lowercase + string.digits + " ")
    
    def press_key(self, key: str, hold_time: Optional[float] = None) -> bool:
        """
        Press a single key with humanized timing
        
        Args:
            key: Key to press
            hold_time: Key hold time in seconds (None for automatic)
        
        Returns:
            True if key press was successful
        """
        try:
            # Calculate delay before pressing key
            delay = self._get_key_delay(key)
            
            # Wait before pressing
            time.sleep(delay)
            
            # Calculate hold time if not specified
            if hold_time is None:
                hold_time = self._get_key_hold_time()
            
            # Press key
            self.pyautogui.keyDown(key)
            time.sleep(hold_time)
            self.pyautogui.keyUp(key)
            
            # Update state
            self.last_key = key
            self.last_key_time = time.time()
            
            return True
        
        except Exception as e:
            logger.error(f"Error in humanized key press: {e}")
            # Ensure key is released
            try:
                self.pyautogui.keyUp(key)
            except:
                pass
            return False
    
    def press_hotkey(self, keys: str) -> bool:
        """
        Press a hotkey combination with humanized timing
        
        Args:
            keys: Keys to press (e.g., 'ctrl+c')
        
        Returns:
            True if hotkey press was successful
        """
        try:
            # Split keys
            key_list = keys.split('+')
            
            # Press modifier keys first
            for key in key_list[:-1]:
                self.pyautogui.keyDown(key)
                # Small delay between modifier keys
                time.sleep(random.uniform(0.03, 0.08))
            
            # Press and release the final key
            self.press_key(key_list[-1])
            
            # Release modifier keys in reverse order
            for key in reversed(key_list[:-1]):
                self.pyautogui.keyUp(key)
                # Small delay between releasing modifier keys
                time.sleep(random.uniform(0.02, 0.05))
            
            # Update state
            self.last_key = key_list[-1]
            self.last_key_time = time.time()
            
            return True
        
        except Exception as e:
            logger.error(f"Error in humanized hotkey press: {e}")
            # Ensure all keys are released
            try:
                for key in key_list:
                    self.pyautogui.keyUp(key)
            except:
                pass
            return False
    
    def type_string(self, text: str, error_correction: bool = True) -> bool:
        """
        Type a string with humanized timing and optional errors
        
        Args:
            text: Text to type
            error_correction: Whether to simulate error correction
        
        Returns:
            True if typing was successful
        """
        try:
            i = 0
            while i < len(text):
                # Check if we should make an error
                if error_correction and self._should_make_error():
                    # Type an error key
                    error_key = self._get_error_key(text[i])
                    self.press_key(error_key)
                    
                    # 70% chance to notice and correct immediately
                    if random.random() < 0.7:
                        # Press backspace after a short delay
                        time.sleep(random.uniform(0.1, 0.3))
                        self.press_key('backspace')
                    else:
                        # Continue typing a few more characters before noticing
                        chars_before_correction = min(3, len(text) - i)
                        for j in range(chars_before_correction):
                            if i + j < len(text):
                                self.press_key(text[i + j])
                        
                        # Notice error and correct
                        time.sleep(random.uniform(0.3, 0.7))
                        
                        # Press backspace multiple times
                        for _ in range(chars_before_correction + 1):  # +1 for the error
                            self.press_key('backspace')
                            time.sleep(random.uniform(0.05, 0.15))
                        
                        # Continue from where we were
                        continue
                
                # Type the correct character
                self.press_key(text[i])
                i += 1
            
            return True
        
        except Exception as e:
            logger.error(f"Error in humanized typing: {e}")
            return False