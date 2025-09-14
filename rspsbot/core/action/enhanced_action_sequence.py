"""
Enhanced humanized action sequences for RSPS Color Bot v3

This module provides advanced humanization features for action sequences,
including fatigue simulation, context-aware timing, and realistic break patterns.
"""
import logging
import time
import random
import math
from typing import List, Dict, Any, Optional, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from .enhanced_mouse import EnhancedHumanizedMouse, MousePersonality, MouseFatigue
from .enhanced_keyboard import EnhancedHumanizedKeyboard, TypingPersonality, KeyboardFatigue, TypingContext

# Get module logger
logger = logging.getLogger('rspsbot.core.action.enhanced_action_sequence')

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
    BREAK = "break"
    CUSTOM = "custom"

class TaskType(Enum):
    """Task type constants for context-aware behavior"""
    COMBAT = "combat"
    NAVIGATION = "navigation"
    INVENTORY = "inventory"
    BANKING = "banking"
    DIALOGUE = "dialogue"
    SKILLING = "skilling"
    TRADING = "trading"
    GENERAL = "general"

@dataclass
class ActionFatigue:
    """
    Action fatigue model for simulating human tiredness over time
    """
    base_level: float = 0.0  # Base fatigue level (0.0 to 1.0)
    current_level: float = 0.0  # Current fatigue level (0.0 to 1.0)
    accumulation_rate: float = 0.005  # Rate of fatigue accumulation per minute
    recovery_rate: float = 0.05  # Rate of fatigue recovery per minute during rest
    last_update_time: float = field(default_factory=time.time)  # Last update timestamp
    activity_intensity: float = 1.0  # Current activity intensity multiplier
    
    # Fatigue effects
    delay_factor: float = 1.0  # Current delay factor due to fatigue
    error_factor: float = 1.0  # Current error factor due to fatigue
    
    # Second wind tracking
    second_wind_active: bool = False  # Whether second wind is active
    second_wind_start_time: float = 0.0  # When second wind started
    second_wind_duration: float = 0.0  # How long second wind lasts
    
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
        
        # Check if second wind is active
        if self.second_wind_active:
            # Check if second wind has expired
            if current_time - self.second_wind_start_time > self.second_wind_duration:
                self.second_wind_active = False
                logger.debug("Second wind has expired")
            else:
                # During second wind, fatigue effects are reduced
                self.delay_factor = 0.7
                self.error_factor = 0.7
        
        # Calculate fatigue change
        if activity_intensity > 0.1:
            # Accumulate fatigue during activity
            fatigue_increase = elapsed_minutes * self.accumulation_rate * activity_intensity
            self.current_level = min(1.0, self.current_level + fatigue_increase)
        else:
            # Recover during rest
            fatigue_decrease = elapsed_minutes * self.recovery_rate
            self.current_level = max(self.base_level, self.current_level - fatigue_decrease)
        
        # Update fatigue effects
        if not self.second_wind_active:
            self.delay_factor = 1.0 + (self.current_level * 0.5)
            self.error_factor = 1.0 + (self.current_level * 1.0)
        
        # Check for second wind trigger
        # Second wind can occur when fatigue is high and there's a period of rest
        if (self.current_level > 0.7 and 
            activity_intensity < 0.3 and 
            not self.second_wind_active and 
            random.random() < 0.1):
            self._trigger_second_wind()
        
        # Update timestamp
        self.last_update_time = current_time
        
        return self.current_level
    
    def _trigger_second_wind(self):
        """Trigger a second wind effect"""
        self.second_wind_active = True
        self.second_wind_start_time = time.time()
        
        # Duration depends on current fatigue level (higher fatigue = shorter second wind)
        base_duration = random.uniform(2.0, 5.0)  # 2-5 minutes
        self.second_wind_duration = base_duration * (1.0 - self.current_level * 0.3) * 60  # Convert to seconds
        
        # Reduce current fatigue level slightly
        self.current_level = max(0.5, self.current_level - 0.2)
        
        logger.debug(f"Second wind triggered! Duration: {self.second_wind_duration/60:.1f} minutes")
    
    def get_delay_factor(self) -> float:
        """
        Get current delay factor due to fatigue
        
        Returns:
            Delay factor (1.0 or higher, higher = more delay)
        """
        return self.delay_factor
    
    def get_error_factor(self) -> float:
        """
        Get current error factor due to fatigue
        
        Returns:
            Error factor (1.0 or higher, higher = more errors)
        """
        return self.error_factor
    
    def reset(self):
        """Reset fatigue to base level"""
        self.current_level = self.base_level
        self.last_update_time = time.time()
        self.second_wind_active = False
        self.delay_factor = 1.0
        self.error_factor = 1.0

@dataclass
class BreakPattern:
    """
    Break pattern model for simulating human breaks during long sessions
    """
    micro_break_interval: Tuple[float, float] = (5.0, 15.0)  # Minutes between micro breaks
    short_break_interval: Tuple[float, float] = (20.0, 40.0)  # Minutes between short breaks
    long_break_interval: Tuple[float, float] = (60.0, 120.0)  # Minutes between long breaks
    
    micro_break_duration: Tuple[float, float] = (5.0, 15.0)  # Seconds for micro break
    short_break_duration: Tuple[float, float] = (30.0, 120.0)  # Seconds for short break
    long_break_duration: Tuple[float, float] = (300.0, 900.0)  # Seconds for long break
    
    break_probability_factor: float = 1.0  # Factor affecting break probability
    
    last_micro_break: float = field(default_factory=time.time)  # Last micro break time
    last_short_break: float = field(default_factory=time.time)  # Last short break time
    last_long_break: float = field(default_factory=time.time)  # Last long break time
    
    session_start_time: float = field(default_factory=time.time)  # Session start time
    
    def should_take_break(self, fatigue_level: float) -> Tuple[bool, str, float]:
        """
        Determine if a break should be taken
        
        Args:
            fatigue_level: Current fatigue level (0.0 to 1.0)
        
        Returns:
            Tuple of (should_break, break_type, duration)
        """
        current_time = time.time()
        
        # Calculate elapsed time since last breaks
        minutes_since_micro = (current_time - self.last_micro_break) / 60.0
        minutes_since_short = (current_time - self.last_short_break) / 60.0
        minutes_since_long = (current_time - self.last_long_break) / 60.0
        
        # Calculate session duration
        session_hours = (current_time - self.session_start_time) / 3600.0
        
        # Adjust break intervals based on fatigue and session duration
        # Higher fatigue and longer sessions = more frequent breaks
        fatigue_factor = 1.0 + fatigue_level
        session_factor = 1.0 + min(1.0, session_hours / 4.0)  # Caps at 5 hours
        
        # Calculate break probabilities
        micro_break_threshold = self.micro_break_interval[0] / (fatigue_factor * session_factor)
        short_break_threshold = self.short_break_interval[0] / (fatigue_factor * session_factor)
        long_break_threshold = self.long_break_interval[0] / (fatigue_factor * session_factor)
        
        # Check for long break first (highest priority)
        if minutes_since_long > long_break_threshold:
            # Calculate probability based on how far past threshold
            probability = min(0.8, (minutes_since_long - long_break_threshold) / 
                             (self.long_break_interval[1] - self.long_break_interval[0]))
            probability *= self.break_probability_factor
            
            if random.random() < probability:
                duration = random.uniform(self.long_break_duration[0], self.long_break_duration[1])
                return True, "long", duration
        
        # Check for short break
        if minutes_since_short > short_break_threshold:
            # Calculate probability based on how far past threshold
            probability = min(0.5, (minutes_since_short - short_break_threshold) / 
                             (self.short_break_interval[1] - self.short_break_interval[0]))
            probability *= self.break_probability_factor
            
            if random.random() < probability:
                duration = random.uniform(self.short_break_duration[0], self.short_break_duration[1])
                return True, "short", duration
        
        # Check for micro break
        if minutes_since_micro > micro_break_threshold:
            # Calculate probability based on how far past threshold
            probability = min(0.3, (minutes_since_micro - micro_break_threshold) / 
                             (self.micro_break_interval[1] - self.micro_break_interval[0]))
            probability *= self.break_probability_factor
            
            if random.random() < probability:
                duration = random.uniform(self.micro_break_duration[0], self.micro_break_duration[1])
                return True, "micro", duration
        
        # No break needed
        return False, "", 0.0
    
    def record_break(self, break_type: str):
        """
        Record that a break was taken
        
        Args:
            break_type: Type of break taken ("micro", "short", "long")
        """
        current_time = time.time()
        
        if break_type == "micro":
            self.last_micro_break = current_time
        elif break_type == "short":
            self.last_micro_break = current_time  # Reset micro break timer too
            self.last_short_break = current_time
        elif break_type == "long":
            self.last_micro_break = current_time  # Reset all break timers
            self.last_short_break = current_time
            self.last_long_break = current_time
    
    def reset(self):
        """Reset break pattern to initial state"""
        current_time = time.time()
        self.last_micro_break = current_time
        self.last_short_break = current_time
        self.last_long_break = current_time
        self.session_start_time = current_time

class ActionSequencePersonality:
    """
    Action sequence personality model for consistent behavior patterns
    """
    
    def __init__(
        self,
        name: str = "default",
        patience: float = 0.5,
        thoroughness: float = 0.7,
        consistency: float = 0.6,
        multitasking: float = 0.5,
        risk_taking: float = 0.5,
        adaptability: float = 0.6,
        break_frequency: float = 0.5
    ):
        """
        Initialize action sequence personality
        
        Args:
            name: Personality name
            patience: Patience level (0.0 to 1.0, higher = more patient)
            thoroughness: Thoroughness level (0.0 to 1.0, higher = more thorough)
            consistency: Consistency level (0.0 to 1.0, higher = more consistent)
            multitasking: Multitasking ability (0.0 to 1.0, higher = better multitasking)
            risk_taking: Risk-taking tendency (0.0 to 1.0, higher = more risk-taking)
            adaptability: Adaptability level (0.0 to 1.0, higher = more adaptable)
            break_frequency: Break frequency (0.0 to 1.0, higher = more frequent breaks)
        """
        self.name = name
        self.patience = max(0.1, min(1.0, patience))
        self.thoroughness = max(0.1, min(1.0, thoroughness))
        self.consistency = max(0.1, min(1.0, consistency))
        self.multitasking = max(0.1, min(1.0, multitasking))
        self.risk_taking = max(0.1, min(1.0, risk_taking))
        self.adaptability = max(0.1, min(1.0, adaptability))
        self.break_frequency = max(0.1, min(1.0, break_frequency))
        
        # Derived characteristics
        self.attention_span = (self.patience + self.thoroughness) / 2.0
        self.error_recovery = (self.adaptability + self.thoroughness) / 2.0
    
    @classmethod
    def create_personality(cls, personality_type: str) -> 'ActionSequencePersonality':
        """
        Create a predefined action sequence personality
        
        Args:
            personality_type: Personality type ('balanced', 'efficient', 'careful', 'impatient', 'adaptive')
        
        Returns:
            ActionSequencePersonality instance
        """
        if personality_type == 'balanced':
            return cls(
                name="balanced",
                patience=0.6,
                thoroughness=0.6,
                consistency=0.6,
                multitasking=0.5,
                risk_taking=0.5,
                adaptability=0.6,
                break_frequency=0.5
            )
        elif personality_type == 'efficient':
            return cls(
                name="efficient",
                patience=0.4,
                thoroughness=0.7,
                consistency=0.8,
                multitasking=0.7,
                risk_taking=0.6,
                adaptability=0.5,
                break_frequency=0.4
            )
        elif personality_type == 'careful':
            return cls(
                name="careful",
                patience=0.8,
                thoroughness=0.9,
                consistency=0.7,
                multitasking=0.3,
                risk_taking=0.2,
                adaptability=0.5,
                break_frequency=0.6
            )
        elif personality_type == 'impatient':
            return cls(
                name="impatient",
                patience=0.3,
                thoroughness=0.4,
                consistency=0.5,
                multitasking=0.6,
                risk_taking=0.7,
                adaptability=0.7,
                break_frequency=0.3
            )
        elif personality_type == 'adaptive':
            return cls(
                name="adaptive",
                patience=0.5,
                thoroughness=0.6,
                consistency=0.5,
                multitasking=0.7,
                risk_taking=0.6,
                adaptability=0.9,
                break_frequency=0.5
            )
        else:
            logger.warning(f"Unknown personality type: {personality_type}, using 'balanced' personality")
            return cls.create_personality('balanced')

class EnhancedActionSequenceProfile:
    """
    Enhanced profile for customizing action sequence characteristics
    """
    
    def __init__(
        self,
        action_delay_factor: float = 1.0,
        action_delay_variability: float = 1.0,
        think_probability: float = 0.1,
        think_duration_factor: float = 1.0,
        fatigue_rate: float = 0.005,
        mouse_profile: Optional[Union[str, Dict]] = None,
        keyboard_profile: Optional[Union[str, Dict]] = None,
        personality: Optional[ActionSequencePersonality] = None,
        fatigue: Optional[ActionFatigue] = None,
        break_pattern: Optional[BreakPattern] = None
    ):
        """
        Initialize enhanced action sequence profile
        
        Args:
            action_delay_factor: Factor affecting delay between actions (higher = longer delays)
            action_delay_variability: Factor affecting variability in delays (higher = more variable)
            think_probability: Probability of adding thinking pauses between actions
            think_duration_factor: Factor affecting thinking pause duration (higher = longer)
            fatigue_rate: Rate at which fatigue accumulates (0.0 = no fatigue)
            mouse_profile: Mouse profile type or configuration dictionary
            keyboard_profile: Keyboard profile type or configuration dictionary
            personality: Action sequence personality
            fatigue: Action fatigue model
            break_pattern: Break pattern model
        """
        self.action_delay_factor = max(0.1, min(5.0, action_delay_factor))
        self.action_delay_variability = max(0.1, min(5.0, action_delay_variability))
        self.think_probability = max(0.0, min(0.5, think_probability))
        self.think_duration_factor = max(0.1, min(5.0, think_duration_factor))
        self.fatigue_rate = max(0.0, min(0.1, fatigue_rate))
        
        # Set personality
        if personality is None:
            self.personality = ActionSequencePersonality()
        else:
            self.personality = personality
        
        # Set fatigue model
        if fatigue is None:
            self.fatigue = ActionFatigue(accumulation_rate=fatigue_rate)
        else:
            self.fatigue = fatigue
        
        # Set break pattern
        if break_pattern is None:
            self.break_pattern = BreakPattern()
        else:
            self.break_pattern = break_pattern
        
        # Set mouse profile
        if isinstance(mouse_profile, str):
            self.mouse_profile_type = mouse_profile
            self.mouse_profile_config = None
        elif isinstance(mouse_profile, dict):
            self.mouse_profile_type = mouse_profile.get('type', 'human')
            self.mouse_profile_config = mouse_profile
        else:
            self.mouse_profile_type = 'human'
            self.mouse_profile_config = None
        
        # Set keyboard profile
        if isinstance(keyboard_profile, str):
            self.keyboard_profile_type = keyboard_profile
            self.keyboard_profile_config = None
        elif isinstance(keyboard_profile, dict):
            self.keyboard_profile_type = keyboard_profile.get('type', 'human')
            self.keyboard_profile_config = keyboard_profile
        else:
            self.keyboard_profile_type = 'human'
            self.keyboard_profile_config = None
        
        # Apply personality traits to profile parameters
        self._apply_personality()
    
    def _apply_personality(self):
        """Apply personality traits to profile parameters"""
        # Action delay is influenced by personality patience
        self.action_delay_factor *= 0.5 + self.personality.patience
        
        # Delay variability is influenced by personality consistency (inverse)
        self.action_delay_variability *= 0.5 + (1.0 - self.personality.consistency)
        
        # Think probability is influenced by personality thoroughness
        self.think_probability *= 0.5 + self.personality.thoroughness
        
        # Think duration is influenced by personality patience
        self.think_duration_factor *= 0.5 + self.personality.patience
        
        # Break pattern is influenced by personality break frequency
        self.break_pattern.break_probability_factor = self.personality.break_frequency
    
    @classmethod
    def create_profile(cls, profile_type: str) -> 'EnhancedActionSequenceProfile':
        """
        Create a predefined enhanced action sequence profile
        
        Args:
            profile_type: Profile type ('human', 'fast', 'precise', 'erratic', 'tired')
        
        Returns:
            EnhancedActionSequenceProfile instance
        """
        if profile_type == 'human':
            return cls(
                action_delay_factor=1.0,
                action_delay_variability=1.0,
                think_probability=0.1,
                think_duration_factor=1.0,
                fatigue_rate=0.005,
                mouse_profile='human',
                keyboard_profile='human',
                personality=ActionSequencePersonality.create_personality('balanced'),
                fatigue=ActionFatigue(accumulation_rate=0.005),
                break_pattern=BreakPattern()
            )
        elif profile_type == 'fast':
            return cls(
                action_delay_factor=0.5,
                action_delay_variability=0.7,
                think_probability=0.05,
                think_duration_factor=0.5,
                fatigue_rate=0.008,
                mouse_profile='fast',
                keyboard_profile='fast',
                personality=ActionSequencePersonality.create_personality('efficient'),
                fatigue=ActionFatigue(accumulation_rate=0.008),
                break_pattern=BreakPattern(break_probability_factor=0.7)
            )
        elif profile_type == 'precise':
            return cls(
                action_delay_factor=1.2,
                action_delay_variability=0.5,
                think_probability=0.15,
                think_duration_factor=0.7,
                fatigue_rate=0.004,
                mouse_profile='precise',
                keyboard_profile='precise',
                personality=ActionSequencePersonality.create_personality('careful'),
                fatigue=ActionFatigue(accumulation_rate=0.004),
                break_pattern=BreakPattern(break_probability_factor=0.8)
            )
        elif profile_type == 'erratic':
            return cls(
                action_delay_factor=0.8,
                action_delay_variability=2.0,
                think_probability=0.2,
                think_duration_factor=1.5,
                fatigue_rate=0.007,
                mouse_profile='erratic',
                keyboard_profile='erratic',
                personality=ActionSequencePersonality.create_personality('impatient'),
                fatigue=ActionFatigue(accumulation_rate=0.007),
                break_pattern=BreakPattern(break_probability_factor=0.6)
            )
        elif profile_type == 'tired':
            return cls(
                action_delay_factor=1.5,
                action_delay_variability=1.8,
                think_probability=0.15,
                think_duration_factor=2.0,
                fatigue_rate=0.01,
                mouse_profile='smooth',
                keyboard_profile='slow',
                personality=ActionSequencePersonality.create_personality('balanced'),
                fatigue=ActionFatigue(base_level=0.5, accumulation_rate=0.01),
                break_pattern=BreakPattern(break_probability_factor=1.2)
            )
        else:
            logger.warning(f"Unknown profile type: {profile_type}, using 'human' profile")
            return cls.create_profile('human')

class EnhancedActionSequence:
    """
    Enhanced humanized action sequence implementation
    
    This class coordinates sequences of actions with advanced humanization features,
    including fatigue simulation, context-aware timing, and realistic break patterns.
    """
    
    def __init__(
        self,
        profile: Optional[Union[EnhancedActionSequenceProfile, str]] = None,
        pyautogui_module=None
    ):
        """
        Initialize enhanced action sequence
        
        Args:
            profile: Enhanced action sequence profile or profile type
            pyautogui_module: PyAutoGUI module (for testing with mock)
        """
        # Set profile
        if isinstance(profile, EnhancedActionSequenceProfile):
            self.profile = profile
        elif isinstance(profile, str):
            self.profile = EnhancedActionSequenceProfile.create_profile(profile)
        else:
            self.profile = EnhancedActionSequenceProfile.create_profile('human')
        
        # Create enhanced humanized controllers
        self.mouse = EnhancedHumanizedMouse(pyautogui_module)
        self.keyboard = EnhancedHumanizedKeyboard(pyautogui_module)
        
        # Apply profiles
        self.mouse.set_profile(self.profile.mouse_profile_type)
        self.keyboard.set_profile(self.profile.keyboard_profile_type)
        
        # Sequence state
        self.sequence_start_time = 0
        self.last_action_time = 0
        self.action_count = 0
        self.current_task_type = TaskType.GENERAL
        self.task_start_time = 0
        self.task_action_count = 0
        
        # Learning state
        self.task_durations = {}  # Average duration for each task type
        self.task_action_counts = {}  # Average action count for each task type
        
        # Initialize session
        self.start_session()
    
    def start_session(self):
        """Start a new session"""
        current_time = time.time()
        self.session_start_time = current_time
        self.profile.break_pattern.session_start_time = current_time
        self.profile.fatigue.reset()
        logger.info("Started new enhanced action sequence session")
    
    def set_profile(self, profile: Union[EnhancedActionSequenceProfile, str]):
        """
        Set action sequence profile
        
        Args:
            profile: EnhancedActionSequenceProfile instance or profile type string
        """
        if isinstance(profile, str):
            self.profile = EnhancedActionSequenceProfile.create_profile(profile)
        else:
            self.profile = profile
        
        # Apply profiles to controllers
        self.mouse.set_profile(self.profile.mouse_profile_type)
        self.keyboard.set_profile(self.profile.keyboard_profile_type)
        
        logger.debug(f"Enhanced action sequence profile set: delay_factor={self.profile.action_delay_factor}, "
                    f"variability={self.profile.action_delay_variability}, "
                    f"think_prob={self.profile.think_probability}, "
                    f"fatigue_rate={self.profile.fatigue_rate}, "
                    f"personality={self.profile.personality.name}")
    
    def set_task_type(self, task_type: TaskType):
        """
        Set current task type for context-aware behavior
        
        Args:
            task_type: Task type
        """
        # If changing task type, record stats for previous task
        if self.current_task_type != task_type and self.task_action_count > 0:
            self._record_task_stats()
        
        # Set new task type
        self.current_task_type = task_type
        self.task_start_time = time.time()
        self.task_action_count = 0
        
        logger.debug(f"Task type set to: {task_type.value}")
    
    def _record_task_stats(self):
        """Record statistics for the current task"""
        if self.task_action_count == 0:
            return
        
        task_type = self.current_task_type.value
        task_duration = time.time() - self.task_start_time
        
        # Update task duration stats
        if task_type not in self.task_durations:
            self.task_durations[task_type] = task_duration
            self.task_action_counts[task_type] = self.task_action_count
        else:
            # Exponential moving average
            alpha = 0.2  # Weight for new data
            self.task_durations[task_type] = (1 - alpha) * self.task_durations[task_type] + alpha * task_duration
            self.task_action_counts[task_type] = (1 - alpha) * self.task_action_counts[task_type] + alpha * self.task_action_count
        
        logger.debug(f"Recorded task stats for {task_type}: {task_duration:.2f}s, {self.task_action_count} actions")
    
    def _get_action_delay(self, action_type: str) -> float:
        """
        Calculate delay before executing an action with enhanced features
        
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
        
        # Apply fatigue factor
        base_delay *= self.profile.fatigue.get_delay_factor()
        
        # Apply task-specific adjustments
        if self.current_task_type == TaskType.COMBAT:
            if action_type == ActionType.MOUSE_CLICK:
                # Combat clicks are often more urgent
                base_delay *= 0.8
        elif self.current_task_type == TaskType.BANKING:
            if action_type == ActionType.MOUSE_CLICK:
                # Banking clicks are often more deliberate
                base_delay *= 1.2
        
        # Apply variability
        variability_factor = random.uniform(
            1.0 - 0.3 * self.profile.action_delay_variability,
            1.0 + 0.3 * self.profile.action_delay_variability
        )
        
        # Apply learning effect
        # Actions get slightly faster with repetition in the same task
        if self.task_action_count > 5:
            learning_factor = max(0.7, 1.0 - (self.task_action_count / 100.0))
            base_delay *= learning_factor
        
        return base_delay * variability_factor
    
    def _should_add_thinking_pause(self) -> bool:
        """
        Determine if a thinking pause should be added with enhanced features
        
        Returns:
            True if thinking pause should be added
        """
        # Base probability
        base_prob = self.profile.think_probability
        
        # Adjust based on task type
        if self.current_task_type == TaskType.BANKING or self.current_task_type == TaskType.INVENTORY:
            # More thinking during inventory management
            base_prob *= 1.3
        elif self.current_task_type == TaskType.COMBAT:
            # Less thinking during combat
            base_prob *= 0.7
        
        # Adjust based on fatigue
        fatigue_factor = 1.0 + (self.profile.fatigue.current_level * 0.5)
        base_prob *= fatigue_factor
        
        # Adjust based on action count in current task
        # More thinking at the start of a task
        if self.task_action_count < 3:
            base_prob *= 1.5
        
        return random.random() < base_prob
    
    def _get_thinking_duration(self) -> float:
        """
        Calculate thinking pause duration with enhanced features
        
        Returns:
            Thinking duration in seconds
        """
        # Base thinking duration (0.5 to 2.0 seconds)
        base_duration = random.uniform(0.5, 2.0)
        
        # Apply profile factor
        base_duration *= self.profile.think_duration_factor
        
        # Apply fatigue factor
        base_duration *= self.profile.fatigue.get_delay_factor()
        
        # Adjust based on task type
        if self.current_task_type == TaskType.BANKING or self.current_task_type == TaskType.INVENTORY:
            # Longer thinking during inventory management
            base_duration *= 1.3
        elif self.current_task_type == TaskType.DIALOGUE:
            # Longer thinking during dialogue (reading)
            base_duration *= 1.5
        elif self.current_task_type == TaskType.COMBAT:
            # Shorter thinking during combat
            base_duration *= 0.7
        
        # Adjust based on personality
        patience_factor = 0.7 + (self.profile.personality.patience * 0.6)
        base_duration *= patience_factor
        
        return base_duration
    
    def _should_take_break(self) -> Tuple[bool, str, float]:
        """
        Determine if a break should be taken
        
        Returns:
            Tuple of (should_break, break_type, duration)
        """
        return self.profile.break_pattern.should_take_break(self.profile.fatigue.current_level)
    
    def start_sequence(self):
        """Start a new action sequence"""
        self.sequence_start_time = time.time()
        self.last_action_time = self.sequence_start_time
        self.action_count = 0
        
        logger.debug("Starting new enhanced action sequence")
    
    def end_sequence(self):
        """End the current action sequence"""
        if self.sequence_start_time > 0:
            elapsed_time = time.time() - self.sequence_start_time
            logger.debug(f"Ending enhanced action sequence: {self.action_count} actions in {elapsed_time:.2f}s")
        
        self.sequence_start_time = 0
        self.last_action_time = 0
        self.action_count = 0
    
    def execute_action(self, action: Dict[str, Any]) -> bool:
        """
        Execute a single action with enhanced humanized timing
        
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
            
            # Update fatigue based on action type
            activity_intensity = 1.0
            if action_type == ActionType.MOUSE_DRAG:
                activity_intensity = 1.5  # Dragging is more intense
            elif action_type == ActionType.TYPE_TEXT:
                activity_intensity = 1.2  # Typing is more intense
            
            self.profile.fatigue.update(activity_intensity)
            
            # Check if we should take a break
            should_break, break_type, break_duration = self._should_take_break()
            if should_break:
                logger.info(f"Taking a {break_type} break for {break_duration:.1f} seconds")
                
                # Record the break
                self.profile.break_pattern.record_break(break_type)
                
                # Execute break
                time.sleep(break_duration)
                
                # Update fatigue (breaks reduce fatigue)
                self.profile.fatigue.update(0.0)
            
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
                # Set typing context if provided
                context = action.get('context')
                if context:
                    if isinstance(context, str):
                        try:
                            context = TypingContext(context)
                        except ValueError:
                            context = TypingContext.GENERAL
                    self.keyboard.set_context(context)
                
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
            
            elif action_type == ActionType.BREAK:
                duration = action.get('duration', 5.0)
                break_type = action.get('break_type', 'micro')
                
                # Record the break
                self.profile.break_pattern.record_break(break_type)
                
                # Execute break
                time.sleep(duration)
                
                # Update fatigue (breaks reduce fatigue)
                self.profile.fatigue.update(0.0)
                
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
            self.task_action_count += 1
            
            return result
        
        except Exception as e:
            logger.error(f"Error executing enhanced action: {e}")
            return False
    
    def execute_sequence(self, actions: List[Dict[str, Any]], task_type: Optional[TaskType] = None) -> bool:
        """
        Execute a sequence of actions with enhanced humanized timing
        
        Args:
            actions: List of action dictionaries
            task_type: Task type for context-aware behavior
        
        Returns:
            True if all actions were executed successfully
        """
        try:
            # Set task type if provided
            if task_type is not None:
                self.set_task_type(task_type)
            
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
            logger.error(f"Error executing enhanced action sequence: {e}")
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
    
    def type_string(
        self,
        text: str,
        error_correction: bool = True,
        context: Optional[Union[TypingContext, str]] = None
    ) -> bool:
        """
        Type a string
        
        Args:
            text: Text to type
            error_correction: Whether to simulate error correction
            context: Typing context
        
        Returns:
            True if typing was successful
        """
        action = {
            'type': ActionType.TYPE_TEXT,
            'text': text,
            'error_correction': error_correction,
            'context': context
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
    
    def take_break(self, duration: Optional[float] = None, break_type: str = 'micro') -> bool:
        """
        Take a break
        
        Args:
            duration: Break duration in seconds (None for automatic)
            break_type: Type of break ('micro', 'short', 'long')
        
        Returns:
            True if break was successful
        """
        if duration is None:
            # Set default duration based on break type
            if break_type == 'micro':
                duration = random.uniform(5.0, 15.0)
            elif break_type == 'short':
                duration = random.uniform(30.0, 120.0)
            elif break_type == 'long':
                duration = random.uniform(300.0, 900.0)
            else:
                duration = 30.0
        
        action = {
            'type': ActionType.BREAK,
            'duration': duration,
            'break_type': break_type
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
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the current session
        
        Returns:
            Dictionary with session statistics
        """
        current_time = time.time()
        session_duration = current_time - self.session_start_time
        
        stats = {
            'session_duration': session_duration,
            'action_count': self.action_count,
            'fatigue_level': self.profile.fatigue.current_level,
            'second_wind_active': self.profile.fatigue.second_wind_active,
            'personality': self.profile.personality.name,
            'current_task': self.current_task_type.value,
            'task_action_count': self.task_action_count,
            'mouse_stats': self.mouse.get_movement_statistics(),
            'keyboard_stats': self.keyboard.get_typing_statistics(),
            'task_durations': self.task_durations,
            'task_action_counts': self.task_action_counts
        }
        
        return stats
    
    def reset_fatigue(self):
        """Reset fatigue to base level"""
        self.profile.fatigue.reset()
        self.mouse.reset_fatigue()
        self.keyboard.reset_fatigue()
        logger.info("Reset all fatigue to base level")