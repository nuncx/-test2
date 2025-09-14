"""
Enhanced humanized keyboard input for RSPS Color Bot v3

This module provides advanced humanization features for keyboard input,
including typing rhythm patterns, context-aware typing, and enhanced error correction.
"""
import logging
import time
import random
import string
import math
from typing import Dict, List, Optional, Tuple, Union, Any, Set
from dataclasses import dataclass, field
from enum import Enum

# Get module logger
logger = logging.getLogger('rspsbot.core.action.enhanced_keyboard')

class TypingContext(Enum):
    """Typing context types"""
    USERNAME = "username"
    PASSWORD = "password"
    CHAT = "chat"
    COMMAND = "command"
    SEARCH = "search"
    GENERAL = "general"

class KeyCategory(Enum):
    """Key categories for typing rhythm patterns"""
    LETTER = "letter"
    NUMBER = "number"
    SYMBOL = "symbol"
    SPACE = "space"
    MODIFIER = "modifier"
    FUNCTION = "function"
    NAVIGATION = "navigation"
    SPECIAL = "special"

@dataclass
class TypingError:
    """
    Typing error model for simulating human typing mistakes
    """
    adjacent_key: float = 0.6  # Probability of hitting an adjacent key
    double_key: float = 0.2    # Probability of hitting a key twice
    skip_key: float = 0.1      # Probability of skipping a key
    swap_key: float = 0.1      # Probability of swapping two keys
    
    # Error correction patterns
    immediate_correction: float = 0.7  # Probability of correcting immediately
    delayed_correction: float = 0.25   # Probability of delayed correction
    no_correction: float = 0.05        # Probability of not correcting
    
    # Correction behavior
    max_correction_delay: int = 5      # Maximum number of characters before delayed correction
    backspace_pause: float = 0.2       # Pause before pressing backspace (seconds)
    correction_pause: float = 0.3      # Pause after correction (seconds)

@dataclass
class TypingRhythm:
    """
    Typing rhythm model for simulating human typing patterns
    """
    base_speed: float = 1.0            # Base typing speed (characters per second)
    consistency: float = 0.8           # Consistency of typing rhythm (0.0 to 1.0)
    word_pause: float = 0.2            # Pause between words (seconds)
    sentence_pause: float = 0.5        # Pause between sentences (seconds)
    punctuation_pause: float = 0.3     # Pause after punctuation (seconds)
    
    # Key-specific timing
    key_timing: Dict[KeyCategory, float] = field(default_factory=dict)
    
    # Finger-based timing
    finger_timing: Dict[str, float] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize default values if not provided"""
        if not self.key_timing:
            self.key_timing = {
                KeyCategory.LETTER: 1.0,
                KeyCategory.NUMBER: 1.2,
                KeyCategory.SYMBOL: 1.3,
                KeyCategory.SPACE: 0.8,
                KeyCategory.MODIFIER: 1.1,
                KeyCategory.FUNCTION: 1.4,
                KeyCategory.NAVIGATION: 1.1,
                KeyCategory.SPECIAL: 1.2
            }
        
        if not self.finger_timing:
            # Relative timing factors for different fingers
            # Index fingers are fastest, pinky fingers are slowest
            self.finger_timing = {
                'left_pinky': 1.2,
                'left_ring': 1.1,
                'left_middle': 1.0,
                'left_index': 0.9,
                'right_index': 0.9,
                'right_middle': 1.0,
                'right_ring': 1.1,
                'right_pinky': 1.2,
                'thumb': 0.8
            }

@dataclass
class KeyboardFatigue:
    """
    Keyboard fatigue model for simulating human tiredness over time
    """
    base_level: float = 0.0  # Base fatigue level (0.0 to 1.0)
    current_level: float = 0.0  # Current fatigue level (0.0 to 1.0)
    accumulation_rate: float = 0.01  # Rate of fatigue accumulation per minute
    recovery_rate: float = 0.05  # Rate of fatigue recovery per minute during rest
    last_update_time: float = field(default_factory=time.time)  # Last update timestamp
    activity_intensity: float = 1.0  # Current activity intensity multiplier
    
    def update(self, activity_intensity: float = 1.0) -> float:
        """
        Update fatigue level based on elapsed time and activity
        
        Args:
            activity_intensity: Intensity of current activity (higher = more fatiguing)
        
        Returns:
            Current fatigue level (0.0 to 1.0)
        """
        current_time = time.time()
        elapsed_minutes = (current_time - self.last_update_time) / 60.0
        
        # Store activity intensity
        self.activity_intensity = activity_intensity
        
        # Calculate fatigue change
        if activity_intensity > 0.1:
            # Accumulate fatigue during activity
            fatigue_increase = elapsed_minutes * self.accumulation_rate * activity_intensity
            self.current_level = min(1.0, self.current_level + fatigue_increase)
        else:
            # Recover during rest
            fatigue_decrease = elapsed_minutes * self.recovery_rate
            self.current_level = max(self.base_level, self.current_level - fatigue_decrease)
        
        # Update timestamp
        self.last_update_time = current_time
        
        return self.current_level
    
    def get_error_factor(self) -> float:
        """
        Calculate error factor based on current fatigue
        
        Returns:
            Error factor (1.0 to 3.0, higher = more errors)
        """
        # Base error factor increases with fatigue
        base_factor = 1.0 + (self.current_level * 2.0)
        
        # Add random variation
        variation = random.uniform(0.8, 1.2)
        
        # Increase errors with activity intensity
        intensity_factor = 1.0 + (self.activity_intensity * 0.3)
        
        return base_factor * variation * intensity_factor
    
    def get_speed_factor(self) -> float:
        """
        Calculate speed factor based on current fatigue
        
        Returns:
            Speed factor (0.5 to 1.0, lower = slower)
        """
        # Speed decreases with fatigue
        return max(0.5, 1.0 - (self.current_level * 0.5))
    
    def get_consistency_factor(self) -> float:
        """
        Calculate consistency factor based on current fatigue
        
        Returns:
            Consistency factor (0.5 to 1.0, lower = less consistent)
        """
        # Consistency decreases with fatigue
        return max(0.5, 1.0 - (self.current_level * 0.5))
    
    def reset(self):
        """Reset fatigue to base level"""
        self.current_level = self.base_level
        self.last_update_time = time.time()

class TypingPersonality:
    """
    Typing personality model for consistent behavior patterns
    """
    
    def __init__(
        self,
        name: str = "default",
        accuracy: float = 0.95,
        speed: float = 1.0,
        consistency: float = 0.8,
        hesitation: float = 0.5,
        correction_thoroughness: float = 0.9,
        capitalization_accuracy: float = 0.95,
        punctuation_accuracy: float = 0.9
    ):
        """
        Initialize typing personality
        
        Args:
            name: Personality name
            accuracy: Base typing accuracy (0.0 to 1.0, higher = fewer errors)
            speed: Base typing speed (0.5 to 2.0, higher = faster)
            consistency: Consistency of typing rhythm (0.0 to 1.0, higher = more consistent)
            hesitation: Tendency to hesitate on complex words (0.0 to 1.0)
            correction_thoroughness: Thoroughness in correcting errors (0.0 to 1.0)
            capitalization_accuracy: Accuracy in capitalization (0.0 to 1.0)
            punctuation_accuracy: Accuracy in punctuation (0.0 to 1.0)
        """
        self.name = name
        self.accuracy = max(0.5, min(1.0, accuracy))
        self.speed = max(0.5, min(2.0, speed))
        self.consistency = max(0.1, min(1.0, consistency))
        self.hesitation = max(0.0, min(1.0, hesitation))
        self.correction_thoroughness = max(0.0, min(1.0, correction_thoroughness))
        self.capitalization_accuracy = max(0.5, min(1.0, capitalization_accuracy))
        self.punctuation_accuracy = max(0.5, min(1.0, punctuation_accuracy))
        
        # Derived characteristics
        self.patience = 1.0 - (speed * 0.4)
        self.attention_to_detail = (accuracy + correction_thoroughness) / 2.0
    
    @classmethod
    def create_personality(cls, personality_type: str) -> 'TypingPersonality':
        """
        Create a predefined typing personality
        
        Args:
            personality_type: Personality type ('casual', 'precise', 'fast', 'careful', 'sloppy')
        
        Returns:
            TypingPersonality instance
        """
        if personality_type == 'casual':
            return cls(
                name="casual",
                accuracy=0.92,
                speed=1.0,
                consistency=0.7,
                hesitation=0.5,
                correction_thoroughness=0.8,
                capitalization_accuracy=0.9,
                punctuation_accuracy=0.85
            )
        elif personality_type == 'precise':
            return cls(
                name="precise",
                accuracy=0.98,
                speed=0.9,
                consistency=0.9,
                hesitation=0.3,
                correction_thoroughness=0.95,
                capitalization_accuracy=0.98,
                punctuation_accuracy=0.98
            )
        elif personality_type == 'fast':
            return cls(
                name="fast",
                accuracy=0.9,
                speed=1.5,
                consistency=0.6,
                hesitation=0.2,
                correction_thoroughness=0.7,
                capitalization_accuracy=0.9,
                punctuation_accuracy=0.85
            )
        elif personality_type == 'careful':
            return cls(
                name="careful",
                accuracy=0.95,
                speed=0.8,
                consistency=0.85,
                hesitation=0.6,
                correction_thoroughness=0.95,
                capitalization_accuracy=0.95,
                punctuation_accuracy=0.95
            )
        elif personality_type == 'sloppy':
            return cls(
                name="sloppy",
                accuracy=0.85,
                speed=1.2,
                consistency=0.5,
                hesitation=0.3,
                correction_thoroughness=0.6,
                capitalization_accuracy=0.8,
                punctuation_accuracy=0.7
            )
        else:
            logger.warning(f"Unknown personality type: {personality_type}, using 'casual' personality")
            return cls.create_personality('casual')

class EnhancedKeyboardProfile:
    """
    Enhanced profile for customizing keyboard input characteristics
    """
    
    def __init__(
        self,
        typing_speed: float = 1.0,
        typing_variability: float = 1.0,
        error_rate: float = 0.03,
        key_hold_time: float = 0.05,
        key_hold_variability: float = 1.0,
        typing_rhythm: Optional[TypingRhythm] = None,
        typing_error: Optional[TypingError] = None,
        personality: Optional[TypingPersonality] = None,
        fatigue: Optional[KeyboardFatigue] = None,
        adjacent_keys: Dict[str, List[str]] = None
    ):
        """
        Initialize enhanced keyboard profile
        
        Args:
            typing_speed: Base typing speed factor (higher = faster)
            typing_variability: Variability in typing speed (higher = more variable)
            error_rate: Base probability of typing errors (0.0 to 0.1)
            key_hold_time: Base key hold time in seconds
            key_hold_variability: Variability in key hold time (higher = more variable)
            typing_rhythm: Typing rhythm model
            typing_error: Typing error model
            personality: Typing personality model
            fatigue: Keyboard fatigue model
            adjacent_keys: Dictionary mapping keys to their adjacent keys on keyboard
        """
        self.typing_speed = max(0.1, min(5.0, typing_speed))
        self.typing_variability = max(0.1, min(5.0, typing_variability))
        self.error_rate = max(0.0, min(0.1, error_rate))
        self.key_hold_time = max(0.01, min(0.2, key_hold_time))
        self.key_hold_variability = max(0.1, min(5.0, key_hold_variability))
        
        # Set typing rhythm
        if typing_rhythm is None:
            self.typing_rhythm = TypingRhythm()
        else:
            self.typing_rhythm = typing_rhythm
        
        # Set typing error model
        if typing_error is None:
            self.typing_error = TypingError()
        else:
            self.typing_error = typing_error
        
        # Set personality
        if personality is None:
            self.personality = TypingPersonality()
        else:
            self.personality = personality
        
        # Set fatigue
        if fatigue is None:
            self.fatigue = KeyboardFatigue()
        else:
            self.fatigue = fatigue
        
        # Initialize adjacent keys for QWERTY keyboard if not provided
        if adjacent_keys is None:
            self.adjacent_keys = self._init_qwerty_adjacent_keys()
        else:
            self.adjacent_keys = adjacent_keys
        
        # Initialize key category mapping
        self.key_categories = self._init_key_categories()
        
        # Initialize finger mapping
        self.key_to_finger = self._init_finger_mapping()
        
        # Apply personality traits to profile parameters
        self._apply_personality()
    
    def _apply_personality(self):
        """Apply personality traits to profile parameters"""
        # Typing speed is influenced by personality speed
        self.typing_speed *= self.personality.speed
        
        # Error rate is influenced by personality accuracy
        self.error_rate *= (1.0 - self.personality.accuracy) * 2.0
        
        # Typing variability is influenced by personality consistency
        self.typing_variability *= (1.0 - self.personality.consistency) * 2.0
        
        # Typing rhythm consistency is influenced by personality consistency
        self.typing_rhythm.consistency = self.personality.consistency
    
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
    
    def _init_key_categories(self) -> Dict[str, KeyCategory]:
        """
        Initialize key category mapping
        
        Returns:
            Dictionary mapping keys to their categories
        """
        key_categories = {}
        
        # Letters
        for letter in string.ascii_lowercase + string.ascii_uppercase:
            key_categories[letter] = KeyCategory.LETTER
        
        # Numbers
        for number in string.digits:
            key_categories[number] = KeyCategory.NUMBER
        
        # Symbols
        for symbol in string.punctuation:
            key_categories[symbol] = KeyCategory.SYMBOL
        
        # Space
        key_categories[' '] = KeyCategory.SPACE
        
        # Modifiers
        for modifier in ['shift', 'ctrl', 'alt', 'meta', 'command', 'option']:
            key_categories[modifier] = KeyCategory.MODIFIER
        
        # Function keys
        for i in range(1, 13):
            key_categories[f'f{i}'] = KeyCategory.FUNCTION
        
        # Navigation keys
        for nav in ['up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown']:
            key_categories[nav] = KeyCategory.NAVIGATION
        
        # Special keys
        for special in ['enter', 'backspace', 'delete', 'tab', 'escape', 'esc']:
            key_categories[special] = KeyCategory.SPECIAL
        
        return key_categories
    
    def _init_finger_mapping(self) -> Dict[str, str]:
        """
        Initialize finger mapping for QWERTY keyboard
        
        Returns:
            Dictionary mapping keys to fingers
        """
        finger_mapping = {}
        
        # Left pinky
        for key in ['`', '1', 'q', 'a', 'z']:
            finger_mapping[key] = 'left_pinky'
            if key in string.ascii_lowercase:
                finger_mapping[key.upper()] = 'left_pinky'
        
        # Left ring
        for key in ['2', 'w', 's', 'x']:
            finger_mapping[key] = 'left_ring'
            if key in string.ascii_lowercase:
                finger_mapping[key.upper()] = 'left_ring'
        
        # Left middle
        for key in ['3', 'e', 'd', 'c']:
            finger_mapping[key] = 'left_middle'
            if key in string.ascii_lowercase:
                finger_mapping[key.upper()] = 'left_middle'
        
        # Left index
        for key in ['4', '5', 'r', 't', 'f', 'g', 'v', 'b']:
            finger_mapping[key] = 'left_index'
            if key in string.ascii_lowercase:
                finger_mapping[key.upper()] = 'left_index'
        
        # Right index
        for key in ['6', '7', 'y', 'u', 'h', 'j', 'n', 'm']:
            finger_mapping[key] = 'right_index'
            if key in string.ascii_lowercase:
                finger_mapping[key.upper()] = 'right_index'
        
        # Right middle
        for key in ['8', 'i', 'k', ',']:
            finger_mapping[key] = 'right_middle'
            if key in string.ascii_lowercase:
                finger_mapping[key.upper()] = 'right_middle'
        
        # Right ring
        for key in ['9', 'o', 'l', '.']:
            finger_mapping[key] = 'right_ring'
            if key in string.ascii_lowercase:
                finger_mapping[key.upper()] = 'right_ring'
        
        # Right pinky
        for key in ['0', '-', '=', 'p', '[', ']', '\\', ';', "'", '/']:
            finger_mapping[key] = 'right_pinky'
            if key in string.ascii_lowercase:
                finger_mapping[key.upper()] = 'right_pinky'
        
        # Thumb
        finger_mapping[' '] = 'thumb'
        
        return finger_mapping
    
    @classmethod
    def create_profile(cls, profile_type: str) -> 'EnhancedKeyboardProfile':
        """
        Create a predefined enhanced keyboard profile
        
        Args:
            profile_type: Profile type ('human', 'fast', 'precise', 'erratic', 'slow', 'casual')
        
        Returns:
            EnhancedKeyboardProfile instance
        """
        if profile_type == 'human':
            return cls(
                typing_speed=1.0,
                typing_variability=1.0,
                error_rate=0.03,
                key_hold_time=0.05,
                key_hold_variability=1.0,
                personality=TypingPersonality.create_personality('casual'),
                fatigue=KeyboardFatigue(accumulation_rate=0.01)
            )
        elif profile_type == 'fast':
            return cls(
                typing_speed=2.0,
                typing_variability=0.7,
                error_rate=0.05,
                key_hold_time=0.03,
                key_hold_variability=0.7,
                personality=TypingPersonality.create_personality('fast'),
                fatigue=KeyboardFatigue(accumulation_rate=0.015)
            )
        elif profile_type == 'precise':
            return cls(
                typing_speed=0.9,
                typing_variability=0.5,
                error_rate=0.01,
                key_hold_time=0.05,
                key_hold_variability=0.5,
                personality=TypingPersonality.create_personality('precise'),
                fatigue=KeyboardFatigue(accumulation_rate=0.008)
            )
        elif profile_type == 'erratic':
            return cls(
                typing_speed=1.2,
                typing_variability=2.0,
                error_rate=0.08,
                key_hold_time=0.04,
                key_hold_variability=2.0,
                personality=TypingPersonality.create_personality('sloppy'),
                fatigue=KeyboardFatigue(accumulation_rate=0.012)
            )
        elif profile_type == 'slow':
            return cls(
                typing_speed=0.5,
                typing_variability=1.5,
                error_rate=0.02,
                key_hold_time=0.08,
                key_hold_variability=1.2,
                personality=TypingPersonality.create_personality('careful'),
                fatigue=KeyboardFatigue(accumulation_rate=0.005)
            )
        elif profile_type == 'casual':
            return cls(
                typing_speed=1.1,
                typing_variability=1.2,
                error_rate=0.04,
                key_hold_time=0.05,
                key_hold_variability=1.0,
                personality=TypingPersonality.create_personality('casual'),
                fatigue=KeyboardFatigue(accumulation_rate=0.01)
            )
        else:
            logger.warning(f"Unknown profile type: {profile_type}, using 'human' profile")
            return cls.create_profile('human')
    
    def update_fatigue(self, activity_intensity: float = 1.0) -> float:
        """
        Update fatigue level
        
        Args:
            activity_intensity: Intensity of current activity (higher = more fatiguing)
        
        Returns:
            Current fatigue level (0.0 to 1.0)
        """
        return self.fatigue.update(activity_intensity)
    
    def get_current_error_rate(self) -> float:
        """
        Get current error rate based on base error rate and fatigue
        
        Returns:
            Current error rate
        """
        fatigue_error = self.fatigue.get_error_factor()
        return min(0.2, self.error_rate * fatigue_error)
    
    def get_current_typing_speed(self) -> float:
        """
        Get current typing speed based on base speed and fatigue
        
        Returns:
            Current typing speed factor
        """
        fatigue_speed = self.fatigue.get_speed_factor()
        return self.typing_speed * fatigue_speed
    
    def get_current_consistency(self) -> float:
        """
        Get current consistency based on base consistency and fatigue
        
        Returns:
            Current consistency factor
        """
        fatigue_consistency = self.fatigue.get_consistency_factor()
        return self.typing_rhythm.consistency * fatigue_consistency

class EnhancedHumanizedKeyboard:
    """
    Enhanced humanized keyboard input implementation
    """
    
    def __init__(self, pyautogui_module=None):
        """
        Initialize enhanced humanized keyboard
        
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
        self.profile = EnhancedKeyboardProfile.create_profile('human')
        
        # Typing state
        self.last_key = None
        self.last_key_time = 0
        self.current_context = TypingContext.GENERAL
        self.keys_pressed = set()  # Currently pressed keys
        
        # Typing history
        self.key_history = []  # List of (key, event_type, timestamp) tuples
        self.max_history_size = 100
        
        # Error tracking
        self.error_positions = []  # List of positions where errors were made
        self.last_activity_time = time.time()
        self.activity_level = 0.0  # Current activity level (0.0 to 1.0)
    
    def set_profile(self, profile: Union[EnhancedKeyboardProfile, str]):
        """
        Set keyboard profile
        
        Args:
            profile: EnhancedKeyboardProfile instance or profile type string
        """
        if isinstance(profile, str):
            self.profile = EnhancedKeyboardProfile.create_profile(profile)
        else:
            self.profile = profile
        
        logger.debug(f"Enhanced keyboard profile set: speed={self.profile.typing_speed}, "
                    f"variability={self.profile.typing_variability}, "
                    f"error_rate={self.profile.error_rate}, "
                    f"personality={self.profile.personality.name}")
    
    def set_context(self, context: TypingContext):
        """
        Set typing context
        
        Args:
            context: Typing context
        """
        self.current_context = context
        logger.debug(f"Typing context set to: {context.value}")
    
    def _update_activity_level(self, intensity: float = 1.0):
        """
        Update activity level based on recent actions
        
        Args:
            intensity: Intensity of current action (higher = more active)
        """
        current_time = time.time()
        elapsed_seconds = current_time - self.last_activity_time
        
        # Activity level decays over time
        decay_factor = max(0.0, 1.0 - (elapsed_seconds / 10.0))  # Decay over 10 seconds
        self.activity_level = self.activity_level * decay_factor
        
        # Add new activity
        self.activity_level = min(1.0, self.activity_level + (intensity * 0.2))
        
        # Update fatigue based on activity level
        self.profile.update_fatigue(self.activity_level)
        
        # Update timestamp
        self.last_activity_time = current_time
    
    def _add_to_history(self, key: str, event_type: str):
        """
        Add key event to history
        
        Args:
            key: Key
            event_type: Event type ('down' or 'up')
        """
        self.key_history.append((key, event_type, time.time()))
        
        # Limit history size
        if len(self.key_history) > self.max_history_size:
            self.key_history = self.key_history[-self.max_history_size:]
    
    def _get_key_category(self, key: str) -> KeyCategory:
        """
        Get category for a key
        
        Args:
            key: Key
        
        Returns:
            Key category
        """
        return self.profile.key_categories.get(key, KeyCategory.SPECIAL)
    
    def _get_finger_for_key(self, key: str) -> str:
        """
        Get finger used for a key
        
        Args:
            key: Key
        
        Returns:
            Finger name
        """
        return self.profile.key_to_finger.get(key, 'right_index')  # Default to right index finger
    
    def _get_key_delay(self, key: str) -> float:
        """
        Calculate delay before pressing a key with enhanced features
        
        Args:
            key: Key to press
        
        Returns:
            Delay in seconds
        """
        # Base delay (lower = faster typing)
        current_speed = self.profile.get_current_typing_speed()
        base_delay = 0.1 / current_speed
        
        # Get key category and finger
        category = self._get_key_category(key)
        finger = self._get_finger_for_key(key)
        
        # Apply category factor
        category_factor = self.profile.typing_rhythm.key_timing.get(category, 1.0)
        
        # Apply finger factor
        finger_factor = self.profile.typing_rhythm.finger_timing.get(finger, 1.0)
        
        # Adjust delay based on key and previous key
        if self.last_key is not None:
            # Faster for repeated keys
            if key == self.last_key:
                base_delay *= 0.7
            
            # Faster for alternating hands
            last_finger = self._get_finger_for_key(self.last_key)
            if 'left' in finger and 'right' in last_finger or 'right' in finger and 'left' in last_finger:
                base_delay *= 0.9
            
            # Slower for same finger on different keys
            elif finger == last_finger and key != self.last_key:
                base_delay *= 1.3
        
        # Context-specific adjustments
        if self.current_context == TypingContext.PASSWORD:
            # Passwords are typically typed more carefully
            base_delay *= 1.2
        elif self.current_context == TypingContext.COMMAND:
            # Commands are typically typed more precisely
            base_delay *= 1.1
        elif self.current_context == TypingContext.CHAT:
            # Chat is typically more casual and faster
            base_delay *= 0.9
        
        # Apply category and finger factors
        base_delay *= category_factor * finger_factor
        
        # Add variability
        current_consistency = self.profile.get_current_consistency()
        variability_range = 1.0 - current_consistency
        variability_factor = random.uniform(
            1.0 - variability_range,
            1.0 + variability_range
        )
        
        return base_delay * variability_factor
    
    def _get_key_hold_time(self, key: str) -> float:
        """
        Calculate key hold time with enhanced features
        
        Args:
            key: Key to press
        
        Returns:
            Hold time in seconds
        """
        # Base hold time
        base_hold_time = self.profile.key_hold_time
        
        # Get key category
        category = self._get_key_category(key)
        
        # Adjust hold time based on category
        if category == KeyCategory.MODIFIER:
            # Modifier keys are held longer
            base_hold_time *= 1.5
        elif category == KeyCategory.SPECIAL:
            # Special keys like Enter are held slightly longer
            base_hold_time *= 1.2
        elif category == KeyCategory.SPACE:
            # Space is typically pressed quickly
            base_hold_time *= 0.8
        
        # Context-specific adjustments
        if self.current_context == TypingContext.COMMAND:
            # Commands often have more deliberate key presses
            base_hold_time *= 1.1
        
        # Fatigue increases hold time
        fatigue_factor = 1.0 + (self.profile.fatigue.current_level * 0.5)
        base_hold_time *= fatigue_factor
        
        # Add variability
        variability_factor = random.uniform(
            1.0 - 0.3 * self.profile.key_hold_variability,
            1.0 + 0.3 * self.profile.key_hold_variability
        )
        
        return base_hold_time * variability_factor
    
    def _should_make_error(self) -> bool:
        """
        Determine if a typing error should be made with enhanced features
        
        Returns:
            True if error should be made
        """
        # Get current error rate
        current_error_rate = self.profile.get_current_error_rate()
        
        # Context-specific adjustments
        if self.current_context == TypingContext.PASSWORD:
            # Passwords are typically typed more carefully
            current_error_rate *= 0.7
        elif self.current_context == TypingContext.COMMAND:
            # Commands are typically typed more precisely
            current_error_rate *= 0.8
        elif self.current_context == TypingContext.CHAT:
            # Chat is typically more casual with more errors
            current_error_rate *= 1.2
        
        return random.random() < current_error_rate
    
    def _get_error_key(self, intended_key: str) -> str:
        """
        Get an error key for the intended key with enhanced features
        
        Args:
            intended_key: The key that was intended to be pressed
        
        Returns:
            Error key
        """
        error_type = random.random()
        
        # Adjacent key error (most common)
        if error_type < self.profile.typing_error.adjacent_key:
            # Get adjacent keys
            adjacent_keys = self.profile.adjacent_keys.get(intended_key, [])
            
            if adjacent_keys:
                return random.choice(adjacent_keys)
        
        # Double key error
        elif error_type < self.profile.typing_error.adjacent_key + self.profile.typing_error.double_key:
            return intended_key  # Press the same key twice
        
        # Skip key error - return a special marker
        elif error_type < self.profile.typing_error.adjacent_key + self.profile.typing_error.double_key + self.profile.typing_error.skip_key:
            return "__SKIP__"  # Special marker to indicate skipping a key
        
        # Swap key error - handle in the typing method
        # This is handled in the type_string method
        
        # Default to a random key
        return random.choice(string.ascii_lowercase + string.digits + " ")
    
    def _get_correction_behavior(self) -> str:
        """
        Determine error correction behavior
        
        Returns:
            Correction behavior ('immediate', 'delayed', 'none')
        """
        # Base probabilities
        immediate_prob = self.profile.typing_error.immediate_correction
        delayed_prob = self.profile.typing_error.delayed_correction
        
        # Adjust based on personality and context
        if self.current_context == TypingContext.PASSWORD or self.current_context == TypingContext.COMMAND:
            # More likely to correct immediately for passwords and commands
            immediate_prob += 0.1
            delayed_prob -= 0.05
        elif self.current_context == TypingContext.CHAT:
            # Less likely to correct for chat
            immediate_prob -= 0.1
            delayed_prob -= 0.05
        
        # Adjust based on personality thoroughness
        thoroughness = self.profile.personality.correction_thoroughness
        immediate_prob *= thoroughness
        delayed_prob *= thoroughness
        
        # Determine behavior
        r = random.random()
        if r < immediate_prob:
            return 'immediate'
        elif r < immediate_prob + delayed_prob:
            return 'delayed'
        else:
            return 'none'
    
    def press_key(self, key: str, hold_time: Optional[float] = None) -> bool:
        """
        Press a single key with enhanced humanized timing
        
        Args:
            key: Key to press
            hold_time: Key hold time in seconds (None for automatic)
        
        Returns:
            True if key press was successful
        """
        try:
            # Update activity level
            self._update_activity_level(1.0)
            
            # Calculate delay before pressing key
            delay = self._get_key_delay(key)
            
            # Wait before pressing
            time.sleep(delay)
            
            # Calculate hold time if not specified
            if hold_time is None:
                hold_time = self._get_key_hold_time(key)
            
            # Press key
            self.pyautogui.keyDown(key)
            self._add_to_history(key, 'down')
            self.keys_pressed.add(key)
            
            time.sleep(hold_time)
            
            self.pyautogui.keyUp(key)
            self._add_to_history(key, 'up')
            self.keys_pressed.discard(key)
            
            # Update state
            self.last_key = key
            self.last_key_time = time.time()
            
            return True
        
        except Exception as e:
            logger.error(f"Error in enhanced humanized key press: {e}")
            # Ensure key is released
            try:
                if key in self.keys_pressed:
                    self.pyautogui.keyUp(key)
                    self._add_to_history(key, 'up')
                    self.keys_pressed.discard(key)
            except:
                pass
            return False
    
    def press_hotkey(self, keys: str) -> bool:
        """
        Press a hotkey combination with enhanced humanized timing
        
        Args:
            keys: Keys to press (e.g., 'ctrl+c')
        
        Returns:
            True if hotkey press was successful
        """
        try:
            # Update activity level (hotkeys are more intense)
            self._update_activity_level(1.5)
            
            # Split keys
            key_list = keys.split('+')
            
            # Press modifier keys first
            for key in key_list[:-1]:
                # Calculate delay before pressing
                delay = self._get_key_delay(key) * 0.7  # Slightly faster for modifiers in sequence
                time.sleep(delay)
                
                # Press key
                self.pyautogui.keyDown(key)
                self._add_to_history(key, 'down')
                self.keys_pressed.add(key)
                
                # Small delay between modifier keys
                time.sleep(random.uniform(0.03, 0.08))
            
            # Press and release the final key
            self.press_key(key_list[-1])
            
            # Release modifier keys in reverse order
            for key in reversed(key_list[:-1]):
                # Small delay before releasing
                time.sleep(random.uniform(0.02, 0.05))
                
                # Release key
                self.pyautogui.keyUp(key)
                self._add_to_history(key, 'up')
                self.keys_pressed.discard(key)
            
            # Update state
            self.last_key = key_list[-1]
            self.last_key_time = time.time()
            
            return True
        
        except Exception as e:
            logger.error(f"Error in enhanced humanized hotkey press: {e}")
            # Ensure all keys are released
            try:
                for key in key_list:
                    if key in self.keys_pressed:
                        self.pyautogui.keyUp(key)
                        self._add_to_history(key, 'up')
                        self.keys_pressed.discard(key)
            except:
                pass
            return False
    
    def _is_complex_word(self, word: str) -> bool:
        """
        Determine if a word is complex (likely to cause hesitation)
        
        Args:
            word: Word to check
        
        Returns:
            True if word is complex
        """
        # Words are complex if they are long
        if len(word) > 8:
            return True
        
        # Words with mixed case are complex
        if any(c.isupper() for c in word[1:]):
            return True
        
        # Words with numbers and letters are complex
        if any(c.isdigit() for c in word) and any(c.isalpha() for c in word):
            return True
        
        # Words with multiple symbols are complex
        symbols = sum(1 for c in word if c in string.punctuation)
        if symbols > 1:
            return True
        
        return False
    
    def _should_hesitate(self, text: str, position: int) -> bool:
        """
        Determine if typing should hesitate at the current position
        
        Args:
            text: Text being typed
            position: Current position in text
        
        Returns:
            True if typing should hesitate
        """
        # Extract current word
        word_start = text.rfind(' ', 0, position) + 1
        word_end = text.find(' ', position)
        if word_end == -1:
            word_end = len(text)
        
        current_word = text[word_start:word_end]
        
        # Check if word is complex
        is_complex = self._is_complex_word(current_word)
        
        # Calculate hesitation probability
        hesitation_prob = self.profile.personality.hesitation * 0.5
        
        if is_complex:
            hesitation_prob *= 2.0
        
        # Increase hesitation with fatigue
        hesitation_prob *= (1.0 + self.profile.fatigue.current_level)
        
        return random.random() < hesitation_prob
    
    def _get_hesitation_duration(self) -> float:
        """
        Calculate hesitation duration
        
        Returns:
            Hesitation duration in seconds
        """
        # Base duration
        base_duration = random.uniform(0.3, 0.8)
        
        # Increase with fatigue
        fatigue_factor = 1.0 + (self.profile.fatigue.current_level * 0.5)
        
        # Increase with hesitation tendency
        hesitation_factor = 1.0 + (self.profile.personality.hesitation * 0.5)
        
        return base_duration * fatigue_factor * hesitation_factor
    
    def _should_pause_after_char(self, char: str, next_char: Optional[str]) -> bool:
        """
        Determine if typing should pause after a character
        
        Args:
            char: Current character
            next_char: Next character (or None if at end)
        
        Returns:
            True if typing should pause
        """
        # Pause after punctuation
        if char in '.,:;!?':
            return True
        
        # Pause at end of sentence
        if char in '.!?' and (next_char is None or next_char.isspace()):
            return True
        
        # Pause at end of clause
        if char in ',;:' and (next_char is None or next_char.isspace()):
            return True
        
        # Pause after space (end of word)
        if char.isspace() and random.random() < 0.1:
            return True
        
        return False
    
    def _get_pause_duration(self, char: str) -> float:
        """
        Calculate pause duration after a character
        
        Args:
            char: Character that triggered the pause
        
        Returns:
            Pause duration in seconds
        """
        # Base duration depends on character
        if char in '.!?':
            # End of sentence
            base_duration = self.profile.typing_rhythm.sentence_pause
        elif char in ',;:':
            # End of clause
            base_duration = self.profile.typing_rhythm.punctuation_pause
        elif char.isspace():
            # End of word
            base_duration = self.profile.typing_rhythm.word_pause
        else:
            # Default
            base_duration = 0.1
        
        # Add variability
        variability_factor = random.uniform(0.8, 1.2)
        
        # Increase with fatigue
        fatigue_factor = 1.0 + (self.profile.fatigue.current_level * 0.3)
        
        return base_duration * variability_factor * fatigue_factor
    
    def type_string(self, text: str, error_correction: bool = True, context: Optional[TypingContext] = None) -> bool:
        """
        Type a string with enhanced humanized timing and features
        
        Args:
            text: Text to type
            error_correction: Whether to simulate error correction
            context: Typing context (None for current context)
        
        Returns:
            True if typing was successful
        """
        try:
            # Set context if provided
            if context is not None:
                self.set_context(context)
            
            # Reset error positions
            self.error_positions = []
            
            # Process text with enhanced features
            i = 0
            while i < len(text):
                # Update activity level periodically
                if i % 10 == 0:
                    self._update_activity_level(1.0)
                
                # Check if we should hesitate
                if self._should_hesitate(text, i):
                    hesitation_time = self._get_hesitation_duration()
                    time.sleep(hesitation_time)
                
                # Check if we should make an error
                if error_correction and self._should_make_error():
                    # Get error key
                    error_key = self._get_error_key(text[i])
                    
                    # Handle different error types
                    if error_key == "__SKIP__":
                        # Skip key error - move to next character without typing
                        i += 1
                        continue
                    elif i < len(text) - 1 and random.random() < self.profile.typing_error.swap_key:
                        # Swap key error - swap current and next character
                        self.press_key(text[i+1])
                        self.press_key(text[i])
                        
                        # Record error position
                        self.error_positions.append(i)
                        
                        # Move past both characters
                        i += 2
                        
                        # Determine correction behavior
                        correction_behavior = self._get_correction_behavior()
                        
                        if correction_behavior == 'immediate':
                            # Press backspace twice
                            time.sleep(self.profile.typing_error.backspace_pause)
                            self.press_key('backspace')
                            self.press_key('backspace')
                            
                            # Retype correctly
                            self.press_key(text[i-2])
                            self.press_key(text[i-1])
                        elif correction_behavior == 'delayed':
                            # Continue typing a few more characters before correcting
                            chars_before_correction = min(
                                random.randint(1, self.profile.typing_error.max_correction_delay),
                                len(text) - i
                            )
                            
                            # Type the next few characters
                            for j in range(i, min(i + chars_before_correction, len(text))):
                                self.press_key(text[j])
                            
                            # Press backspace multiple times
                            time.sleep(self.profile.typing_error.backspace_pause)
                            for _ in range(chars_before_correction + 2):
                                self.press_key('backspace')
                            
                            # Retype correctly
                            self.press_key(text[i-2])
                            self.press_key(text[i-1])
                            
                            # Retype the characters we deleted
                            for j in range(i, min(i + chars_before_correction, len(text))):
                                self.press_key(text[j])
                            
                            # Update position
                            i += chars_before_correction
                        
                        continue
                    else:
                        # Type the error key
                        self.press_key(error_key)
                        
                        # Record error position
                        self.error_positions.append(i)
                        
                        # Determine correction behavior
                        correction_behavior = self._get_correction_behavior()
                        
                        if correction_behavior == 'immediate':
                            # Press backspace after a short delay
                            time.sleep(self.profile.typing_error.backspace_pause)
                            self.press_key('backspace')
                            
                            # Type the correct character
                            self.press_key(text[i])
                        elif correction_behavior == 'delayed':
                            # Continue typing a few more characters before correcting
                            chars_before_correction = min(
                                random.randint(1, self.profile.typing_error.max_correction_delay),
                                len(text) - i - 1
                            )
                            
                            # Type the next few characters
                            for j in range(i + 1, min(i + 1 + chars_before_correction, len(text))):
                                self.press_key(text[j])
                            
                            # Press backspace multiple times
                            time.sleep(self.profile.typing_error.backspace_pause)
                            for _ in range(chars_before_correction + 1):
                                self.press_key('backspace')
                            
                            # Retype correctly
                            self.press_key(text[i])
                            
                            # Retype the characters we deleted
                            for j in range(i + 1, min(i + 1 + chars_before_correction, len(text))):
                                self.press_key(text[j])
                            
                            # Update position
                            i += chars_before_correction
                        
                        # If no correction, just continue with next character
                        i += 1
                        continue
                
                # Type the correct character
                self.press_key(text[i])
                
                # Check if we should pause after this character
                next_char = text[i+1] if i < len(text) - 1 else None
                if self._should_pause_after_char(text[i], next_char):
                    pause_time = self._get_pause_duration(text[i])
                    time.sleep(pause_time)
                
                i += 1
            
            return True
        
        except Exception as e:
            logger.error(f"Error in enhanced humanized typing: {e}")
            return False
    
    def get_typing_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about recent typing
        
        Returns:
            Dictionary with typing statistics
        """
        stats = {
            'fatigue_level': self.profile.fatigue.current_level,
            'activity_level': self.activity_level,
            'error_rate': self.profile.get_current_error_rate(),
            'typing_speed': self.profile.get_current_typing_speed(),
            'consistency': self.profile.get_current_consistency(),
            'personality': self.profile.personality.name,
            'context': self.current_context.value
        }
        
        # Calculate key press statistics if we have enough history
        if len(self.key_history) >= 2:
            # Calculate key press intervals
            intervals = []
            for i in range(1, len(self.key_history)):
                if self.key_history[i-1][1] == 'down' and self.key_history[i][1] == 'down':
                    interval = self.key_history[i][2] - self.key_history[i-1][2]
                    intervals.append(interval)
            
            if intervals:
                stats['avg_key_interval'] = sum(intervals) / len(intervals)
                stats['min_key_interval'] = min(intervals)
                stats['max_key_interval'] = max(intervals)
            
            # Calculate key hold times
            hold_times = []
            for i in range(1, len(self.key_history)):
                if (self.key_history[i-1][1] == 'down' and 
                    self.key_history[i][1] == 'up' and 
                    self.key_history[i-1][0] == self.key_history[i][0]):
                    hold_time = self.key_history[i][2] - self.key_history[i-1][2]
                    hold_times.append(hold_time)
            
            if hold_times:
                stats['avg_hold_time'] = sum(hold_times) / len(hold_times)
                stats['min_hold_time'] = min(hold_times)
                stats['max_hold_time'] = max(hold_times)
        
        # Error statistics
        stats['error_count'] = len(self.error_positions)
        
        return stats
    
    def reset_fatigue(self):
        """Reset fatigue to base level"""
        self.profile.fatigue.reset()
        logger.info("Reset keyboard fatigue to base level")