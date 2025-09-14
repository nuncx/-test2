"""
Enhanced humanized mouse movement for RSPS Color Bot v3

This module provides advanced humanization features for mouse movements,
including fatigue simulation, personality profiles, and realistic physics.
"""
import logging
import time
import random
import math
import numpy as np
from typing import Tuple, List, Optional, Dict, Any, Union
from dataclasses import dataclass, field

# Get module logger
logger = logging.getLogger('rspsbot.core.action.enhanced_mouse')

@dataclass
class MouseFatigue:
    """
    Mouse fatigue model for simulating human tiredness over time
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
        
        # Store activity intensity for tremor calculations
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
    
    def get_tremor_factor(self) -> float:
        """
        Calculate tremor factor based on current fatigue
        
        Returns:
            Tremor factor (0.0 to 2.0)
        """
        # Base tremor increases with fatigue
        base_tremor = self.current_level * 1.5
        
        # Add random variation
        variation = random.uniform(0.7, 1.3)
        
        # Increase tremor with activity intensity
        intensity_factor = 1.0 + (self.activity_intensity * 0.5)
        
        return base_tremor * variation * intensity_factor
    
    def get_speed_factor(self) -> float:
        """
        Calculate speed factor based on current fatigue
        
        Returns:
            Speed factor (0.5 to 1.0, lower = slower)
        """
        # Speed decreases with fatigue
        return max(0.5, 1.0 - (self.current_level * 0.5))
    
    def get_accuracy_factor(self) -> float:
        """
        Calculate accuracy factor based on current fatigue
        
        Returns:
            Accuracy factor (0.5 to 1.0, lower = less accurate)
        """
        # Accuracy decreases with fatigue
        return max(0.5, 1.0 - (self.current_level * 0.5))
    
    def reset(self):
        """Reset fatigue to base level"""
        self.current_level = self.base_level
        self.last_update_time = time.time()

class MousePersonality:
    """
    Mouse personality model for consistent behavior patterns
    """
    
    def __init__(
        self,
        name: str = "default",
        accuracy: float = 0.8,
        speed_preference: float = 0.8,
        jitter_tendency: float = 0.5,
        overshoot_tendency: float = 0.5,
        corner_cutting: float = 0.5,
        acceleration_preference: float = 0.5,
        reaction_time: float = 0.2
    ):
        """
        Initialize mouse personality
        
        Args:
            name: Personality name
            accuracy: Base accuracy (0.0 to 1.0, higher = more accurate)
            speed_preference: Preferred movement speed (0.0 to 1.0, higher = faster)
            jitter_tendency: Tendency to have jittery movements (0.0 to 1.0)
            overshoot_tendency: Tendency to overshoot targets (0.0 to 1.0)
            corner_cutting: Tendency to cut corners in curved paths (0.0 to 1.0)
            acceleration_preference: Preference for acceleration vs. constant speed (0.0 to 1.0)
            reaction_time: Base reaction time in seconds
        """
        self.name = name
        self.accuracy = max(0.1, min(1.0, accuracy))
        self.speed_preference = max(0.1, min(1.0, speed_preference))
        self.jitter_tendency = max(0.0, min(1.0, jitter_tendency))
        self.overshoot_tendency = max(0.0, min(1.0, overshoot_tendency))
        self.corner_cutting = max(0.0, min(1.0, corner_cutting))
        self.acceleration_preference = max(0.0, min(1.0, acceleration_preference))
        self.reaction_time = max(0.05, min(0.5, reaction_time))
        
        # Derived characteristics
        self.consistency = 1.0 - (jitter_tendency * 0.5)
        self.smoothness = 1.0 - (jitter_tendency * 0.7)
        self.patience = 1.0 - (speed_preference * 0.5)
    
    @classmethod
    def create_personality(cls, personality_type: str) -> 'MousePersonality':
        """
        Create a predefined mouse personality
        
        Args:
            personality_type: Personality type ('casual', 'precise', 'gamer', 'erratic', 'relaxed')
        
        Returns:
            MousePersonality instance
        """
        if personality_type == 'casual':
            return cls(
                name="casual",
                accuracy=0.7,
                speed_preference=0.6,
                jitter_tendency=0.4,
                overshoot_tendency=0.5,
                corner_cutting=0.6,
                acceleration_preference=0.5,
                reaction_time=0.25
            )
        elif personality_type == 'precise':
            return cls(
                name="precise",
                accuracy=0.95,
                speed_preference=0.5,
                jitter_tendency=0.1,
                overshoot_tendency=0.1,
                corner_cutting=0.2,
                acceleration_preference=0.3,
                reaction_time=0.15
            )
        elif personality_type == 'gamer':
            return cls(
                name="gamer",
                accuracy=0.85,
                speed_preference=0.9,
                jitter_tendency=0.3,
                overshoot_tendency=0.4,
                corner_cutting=0.7,
                acceleration_preference=0.8,
                reaction_time=0.1
            )
        elif personality_type == 'erratic':
            return cls(
                name="erratic",
                accuracy=0.6,
                speed_preference=0.7,
                jitter_tendency=0.8,
                overshoot_tendency=0.7,
                corner_cutting=0.8,
                acceleration_preference=0.6,
                reaction_time=0.3
            )
        elif personality_type == 'relaxed':
            return cls(
                name="relaxed",
                accuracy=0.75,
                speed_preference=0.4,
                jitter_tendency=0.2,
                overshoot_tendency=0.3,
                corner_cutting=0.4,
                acceleration_preference=0.3,
                reaction_time=0.3
            )
        else:
            logger.warning(f"Unknown personality type: {personality_type}, using 'casual' personality")
            return cls.create_personality('casual')

class EnhancedBezierCurve:
    """
    Enhanced Bezier curve implementation with advanced features
    """
    
    @staticmethod
    def binomial(n: int, k: int) -> int:
        """
        Calculate binomial coefficient (n choose k)
        
        Args:
            n: Total number of items
            k: Number of items to choose
        
        Returns:
            Binomial coefficient
        """
        if k < 0 or k > n:
            return 0
        if k == 0 or k == n:
            return 1
        
        # Calculate using multiplicative formula
        result = 1
        for i in range(1, k + 1):
            result *= (n - (i - 1))
            result //= i
        
        return result
    
    @staticmethod
    def bernstein_polynomial(i: int, n: int, t: float) -> float:
        """
        Calculate Bernstein polynomial value
        
        Args:
            i: Index
            n: Degree of polynomial
            t: Parameter value (0 to 1)
        
        Returns:
            Bernstein polynomial value
        """
        return EnhancedBezierCurve.binomial(n, i) * (t ** i) * ((1 - t) ** (n - i))
    
    @staticmethod
    def bezier_curve(
        control_points: List[Tuple[float, float]],
        num_points: int = 50,
        corner_cutting: float = 0.5,
        jitter_factor: float = 0.0,
        tremor_factor: float = 0.0
    ) -> List[Tuple[int, int]]:
        """
        Generate points along a Bezier curve with enhanced features
        
        Args:
            control_points: List of control points (x, y)
            num_points: Number of points to generate
            corner_cutting: Corner cutting factor (0.0 to 1.0)
            jitter_factor: Jitter factor for micro-deviations (0.0 to 1.0)
            tremor_factor: Tremor factor for hand tremors (0.0 to 2.0)
        
        Returns:
            List of points along the curve
        """
        # Apply corner cutting if enabled
        if corner_cutting > 0.0 and len(control_points) > 3:
            # Create new control points with corner cutting
            new_control_points = [control_points[0]]
            
            for i in range(1, len(control_points) - 1):
                prev_point = control_points[i - 1]
                current_point = control_points[i]
                next_point = control_points[i + 1]
                
                # Calculate direction vectors
                dir1_x = current_point[0] - prev_point[0]
                dir1_y = current_point[1] - prev_point[1]
                dir2_x = next_point[0] - current_point[0]
                dir2_y = next_point[1] - current_point[1]
                
                # Calculate angle between directions
                dot_product = dir1_x * dir2_x + dir1_y * dir2_y
                mag1 = math.sqrt(dir1_x * dir1_x + dir1_y * dir1_y)
                mag2 = math.sqrt(dir2_x * dir2_x + dir2_y * dir2_y)
                
                if mag1 > 0 and mag2 > 0:
                    angle = math.acos(max(-1.0, min(1.0, dot_product / (mag1 * mag2))))
                    
                    # Apply more corner cutting for sharper angles
                    angle_factor = angle / math.pi  # 0.0 for straight line, 1.0 for 180 degree turn
                    cut_factor = corner_cutting * angle_factor
                    
                    # Calculate new point with corner cutting
                    if cut_factor > 0.05:  # Only apply if angle is significant
                        # Calculate point before corner
                        before_x = current_point[0] - dir1_x * cut_factor
                        before_y = current_point[1] - dir1_y * cut_factor
                        
                        # Calculate point after corner
                        after_x = current_point[0] + dir2_x * cut_factor
                        after_y = current_point[1] + dir2_y * cut_factor
                        
                        # Add both points instead of the corner
                        new_control_points.append((before_x, before_y))
                        new_control_points.append((after_x, after_y))
                        continue
                
                # If no corner cutting applied, use original point
                new_control_points.append(current_point)
            
            # Add last point
            new_control_points.append(control_points[-1])
            control_points = new_control_points
        
        # Generate basic Bezier curve
        n = len(control_points) - 1
        curve_points = []
        
        for i in range(num_points):
            t = i / (num_points - 1)
            x = 0
            y = 0
            
            for j in range(n + 1):
                bernstein = EnhancedBezierCurve.bernstein_polynomial(j, n, t)
                x += bernstein * control_points[j][0]
                y += bernstein * control_points[j][1]
            
            # Apply jitter if enabled
            if jitter_factor > 0.0:
                # Calculate maximum jitter based on distance to next point
                if i < num_points - 1:
                    next_t = (i + 1) / (num_points - 1)
                    next_x = 0
                    next_y = 0
                    
                    for j in range(n + 1):
                        bernstein = EnhancedBezierCurve.bernstein_polynomial(j, n, next_t)
                        next_x += bernstein * control_points[j][0]
                        next_y += bernstein * control_points[j][1]
                    
                    # Calculate distance to next point
                    dx = next_x - x
                    dy = next_y - y
                    distance = math.sqrt(dx * dx + dy * dy)
                    
                    # Calculate jitter amount (proportional to distance)
                    jitter_amount = min(2.0, distance * 0.1) * jitter_factor
                else:
                    jitter_amount = 1.0 * jitter_factor
                
                # Apply jitter
                x += random.uniform(-jitter_amount, jitter_amount)
                y += random.uniform(-jitter_amount, jitter_amount)
            
            # Apply tremor if enabled
            if tremor_factor > 0.0:
                # Tremor increases with higher t values (end of movement)
                tremor_scale = tremor_factor * (0.5 + t * 0.5)
                
                # Calculate tremor
                tremor_x = random.uniform(-tremor_scale, tremor_scale)
                tremor_y = random.uniform(-tremor_scale, tremor_scale)
                
                # Apply tremor
                x += tremor_x
                y += tremor_y
            
            curve_points.append((int(round(x)), int(round(y))))
        
        return curve_points

class EnhancedMouseMovementProfile:
    """
    Enhanced profile for customizing mouse movement characteristics
    """
    
    def __init__(
        self,
        speed_factor: float = 1.0,
        jitter_factor: float = 1.0,
        overshoot_factor: float = 1.0,
        acceleration_factor: float = 1.0,
        smoothness: int = 50,
        corner_cutting: float = 0.5,
        momentum_factor: float = 0.5,
        friction_factor: float = 0.5,
        tremor_base: float = 0.0,
        drift_factor: float = 0.2,
        personality: Optional[MousePersonality] = None,
        fatigue: Optional[MouseFatigue] = None
    ):
        """
        Initialize enhanced mouse movement profile
        
        Args:
            speed_factor: Factor affecting movement speed (higher = faster)
            jitter_factor: Factor affecting movement jitter (higher = more jitter)
            overshoot_factor: Factor affecting overshoot probability (higher = more overshooting)
            acceleration_factor: Factor affecting acceleration/deceleration (higher = more variation)
            smoothness: Number of points to generate along the curve (higher = smoother)
            corner_cutting: Factor affecting corner cutting behavior (higher = more cutting)
            momentum_factor: Factor affecting movement momentum (higher = more momentum)
            friction_factor: Factor affecting movement friction (higher = more friction)
            tremor_base: Base tremor amount (higher = more tremor)
            drift_factor: Factor affecting cursor drift during pauses (higher = more drift)
            personality: Mouse personality instance
            fatigue: Mouse fatigue instance
        """
        self.speed_factor = max(0.1, min(5.0, speed_factor))
        self.jitter_factor = max(0.0, min(5.0, jitter_factor))
        self.overshoot_factor = max(0.0, min(5.0, overshoot_factor))
        self.acceleration_factor = max(0.1, min(5.0, acceleration_factor))
        self.smoothness = max(10, min(200, smoothness))
        self.corner_cutting = max(0.0, min(1.0, corner_cutting))
        self.momentum_factor = max(0.0, min(1.0, momentum_factor))
        self.friction_factor = max(0.0, min(1.0, friction_factor))
        self.tremor_base = max(0.0, min(1.0, tremor_base))
        self.drift_factor = max(0.0, min(1.0, drift_factor))
        
        # Set personality
        if personality is None:
            self.personality = MousePersonality()
        else:
            self.personality = personality
        
        # Set fatigue
        if fatigue is None:
            self.fatigue = MouseFatigue()
        else:
            self.fatigue = fatigue
        
        # Apply personality traits to profile parameters
        self._apply_personality()
    
    def _apply_personality(self):
        """Apply personality traits to profile parameters"""
        # Speed is influenced by personality speed preference
        self.speed_factor *= 0.5 + self.personality.speed_preference
        
        # Jitter is influenced by personality jitter tendency
        self.jitter_factor *= self.personality.jitter_tendency
        
        # Overshoot is influenced by personality overshoot tendency
        self.overshoot_factor *= self.personality.overshoot_tendency
        
        # Acceleration is influenced by personality acceleration preference
        self.acceleration_factor *= 0.5 + self.personality.acceleration_preference
        
        # Smoothness is influenced by personality smoothness
        self.smoothness = int(self.smoothness * (0.5 + self.personality.smoothness * 0.5))
        
        # Corner cutting is influenced by personality corner cutting
        self.corner_cutting *= self.personality.corner_cutting
        
        # Tremor is influenced by personality jitter tendency
        self.tremor_base *= self.personality.jitter_tendency
    
    @classmethod
    def create_profile(cls, profile_type: str) -> 'EnhancedMouseMovementProfile':
        """
        Create a predefined enhanced mouse movement profile
        
        Args:
            profile_type: Profile type ('human', 'fast', 'precise', 'erratic', 'smooth', 'gamer')
        
        Returns:
            EnhancedMouseMovementProfile instance
        """
        if profile_type == 'human':
            return cls(
                speed_factor=1.0,
                jitter_factor=1.0,
                overshoot_factor=1.0,
                acceleration_factor=1.0,
                smoothness=50,
                corner_cutting=0.5,
                momentum_factor=0.5,
                friction_factor=0.5,
                tremor_base=0.2,
                drift_factor=0.2,
                personality=MousePersonality.create_personality('casual'),
                fatigue=MouseFatigue(accumulation_rate=0.01)
            )
        elif profile_type == 'fast':
            return cls(
                speed_factor=2.0,
                jitter_factor=0.7,
                overshoot_factor=1.2,
                acceleration_factor=1.5,
                smoothness=30,
                corner_cutting=0.7,
                momentum_factor=0.7,
                friction_factor=0.3,
                tremor_base=0.3,
                drift_factor=0.1,
                personality=MousePersonality.create_personality('gamer'),
                fatigue=MouseFatigue(accumulation_rate=0.02)
            )
        elif profile_type == 'precise':
            return cls(
                speed_factor=0.8,
                jitter_factor=0.3,
                overshoot_factor=0.2,
                acceleration_factor=0.7,
                smoothness=80,
                corner_cutting=0.2,
                momentum_factor=0.3,
                friction_factor=0.7,
                tremor_base=0.1,
                drift_factor=0.1,
                personality=MousePersonality.create_personality('precise'),
                fatigue=MouseFatigue(accumulation_rate=0.005)
            )
        elif profile_type == 'erratic':
            return cls(
                speed_factor=1.5,
                jitter_factor=2.5,
                overshoot_factor=2.0,
                acceleration_factor=2.0,
                smoothness=40,
                corner_cutting=0.8,
                momentum_factor=0.8,
                friction_factor=0.4,
                tremor_base=0.5,
                drift_factor=0.4,
                personality=MousePersonality.create_personality('erratic'),
                fatigue=MouseFatigue(accumulation_rate=0.015)
            )
        elif profile_type == 'smooth':
            return cls(
                speed_factor=0.9,
                jitter_factor=0.2,
                overshoot_factor=0.1,
                acceleration_factor=0.5,
                smoothness=100,
                corner_cutting=0.3,
                momentum_factor=0.4,
                friction_factor=0.6,
                tremor_base=0.1,
                drift_factor=0.1,
                personality=MousePersonality.create_personality('relaxed'),
                fatigue=MouseFatigue(accumulation_rate=0.008)
            )
        elif profile_type == 'gamer':
            return cls(
                speed_factor=1.8,
                jitter_factor=0.5,
                overshoot_factor=0.8,
                acceleration_factor=1.2,
                smoothness=40,
                corner_cutting=0.6,
                momentum_factor=0.6,
                friction_factor=0.4,
                tremor_base=0.2,
                drift_factor=0.1,
                personality=MousePersonality.create_personality('gamer'),
                fatigue=MouseFatigue(accumulation_rate=0.012)
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
    
    def get_current_tremor(self) -> float:
        """
        Get current tremor amount based on base tremor and fatigue
        
        Returns:
            Current tremor amount
        """
        fatigue_tremor = self.fatigue.get_tremor_factor()
        return self.tremor_base + (fatigue_tremor * self.tremor_base)
    
    def get_current_speed_factor(self) -> float:
        """
        Get current speed factor based on base speed and fatigue
        
        Returns:
            Current speed factor
        """
        fatigue_speed = self.fatigue.get_speed_factor()
        return self.speed_factor * fatigue_speed
    
    def get_current_accuracy(self) -> float:
        """
        Get current accuracy based on personality accuracy and fatigue
        
        Returns:
            Current accuracy (0.0 to 1.0)
        """
        fatigue_accuracy = self.fatigue.get_accuracy_factor()
        return self.personality.accuracy * fatigue_accuracy

class EnhancedHumanizedMouse:
    """
    Enhanced humanized mouse movement implementation
    """
    
    def __init__(self, pyautogui_module=None):
        """
        Initialize enhanced humanized mouse
        
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
        self.profile = EnhancedMouseMovementProfile.create_profile('human')
        
        # Movement state
        self.last_position = self.get_position()
        self.last_move_time = time.time()
        self.velocity = (0.0, 0.0)  # Current velocity vector
        self.last_activity_time = time.time()
        self.activity_level = 0.0  # Current activity level (0.0 to 1.0)
        
        # Movement history
        self.position_history = []  # List of (x, y, timestamp) tuples
        self.max_history_size = 100
        
        # Initialize position history with current position
        current_pos = self.get_position()
        self.position_history.append((current_pos[0], current_pos[1], time.time()))
    
    def set_profile(self, profile: Union[EnhancedMouseMovementProfile, str]):
        """
        Set mouse movement profile
        
        Args:
            profile: EnhancedMouseMovementProfile instance or profile type string
        """
        if isinstance(profile, str):
            self.profile = EnhancedMouseMovementProfile.create_profile(profile)
        else:
            self.profile = profile
        
        logger.debug(f"Enhanced mouse profile set: speed={self.profile.speed_factor}, "
                    f"jitter={self.profile.jitter_factor}, "
                    f"overshoot={self.profile.overshoot_factor}, "
                    f"acceleration={self.profile.acceleration_factor}, "
                    f"smoothness={self.profile.smoothness}, "
                    f"personality={self.profile.personality.name}")
    
    def get_position(self) -> Tuple[int, int]:
        """
        Get current mouse position
        
        Returns:
            Current (x, y) position
        """
        return self.pyautogui.position()
    
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
    
    def _add_to_history(self, x: int, y: int):
        """
        Add position to history
        
        Args:
            x: X coordinate
            y: Y coordinate
        """
        self.position_history.append((x, y, time.time()))
        
        # Limit history size
        if len(self.position_history) > self.max_history_size:
            self.position_history = self.position_history[-self.max_history_size:]
    
    def _calculate_velocity(self) -> Tuple[float, float]:
        """
        Calculate current velocity based on recent movements
        
        Returns:
            Velocity vector (vx, vy) in pixels per second
        """
        if len(self.position_history) < 2:
            return (0.0, 0.0)
        
        # Get last two positions
        x1, y1, t1 = self.position_history[-2]
        x2, y2, t2 = self.position_history[-1]
        
        # Calculate time difference
        dt = t2 - t1
        
        if dt > 0:
            # Calculate velocity
            vx = (x2 - x1) / dt
            vy = (y2 - y1) / dt
            return (vx, vy)
        else:
            return (0.0, 0.0)
    
    def _apply_momentum(
        self,
        start_point: Tuple[int, int],
        end_point: Tuple[int, int]
    ) -> List[Tuple[float, float]]:
        """
        Apply momentum to control points
        
        Args:
            start_point: Starting point (x, y)
            end_point: Ending point (x, y)
        
        Returns:
            List of control points with momentum applied
        """
        # Calculate basic direction vector
        dx = end_point[0] - start_point[0]
        dy = end_point[1] - start_point[1]
        distance = math.sqrt(dx * dx + dy * dy)
        
        if distance == 0:
            return [start_point, end_point]
        
        # Normalize direction vector
        dx /= distance
        dy /= distance
        
        # Get current velocity
        vx, vy = self.velocity
        
        # Calculate velocity magnitude
        v_mag = math.sqrt(vx * vx + vy * vy)
        
        # Calculate momentum influence
        momentum_factor = self.profile.momentum_factor
        
        if v_mag > 0:
            # Normalize velocity vector
            vx_norm = vx / v_mag
            vy_norm = vy / v_mag
            
            # Calculate dot product between velocity and direction
            dot_product = dx * vx_norm + dy * vy_norm
            
            # Adjust momentum factor based on alignment
            # If velocity is aligned with direction, apply more momentum
            # If velocity is opposing direction, apply less momentum
            alignment_factor = 0.5 + (dot_product * 0.5)  # 0.0 to 1.0
            momentum_factor *= alignment_factor
        
        # Calculate control points with momentum
        control_points = []
        
        # Start point
        control_points.append((float(start_point[0]), float(start_point[1])))
        
        # Add intermediate control points based on momentum
        if momentum_factor > 0.1 and v_mag > 10:
            # Calculate momentum influence point
            momentum_distance = min(distance * 0.5, v_mag * 0.2)
            momentum_x = start_point[0] + vx_norm * momentum_distance
            momentum_y = start_point[1] + vy_norm * momentum_distance
            
            # Add momentum control point
            control_points.append((momentum_x, momentum_y))
        
        # Add intermediate control point
        mid_x = start_point[0] + dx * distance * 0.5
        mid_y = start_point[1] + dy * distance * 0.5
        
        # Add random deviation to intermediate point
        deviation = distance * 0.2 * self.profile.jitter_factor
        mid_x += random.uniform(-deviation, deviation)
        mid_y += random.uniform(-deviation, deviation)
        
        control_points.append((mid_x, mid_y))
        
        # End point
        control_points.append((float(end_point[0]), float(end_point[1])))
        
        return control_points
    
    def _generate_control_points(
        self,
        start_point: Tuple[int, int],
        end_point: Tuple[int, int]
    ) -> List[Tuple[float, float]]:
        """
        Generate control points for Bezier curve with enhanced features
        
        Args:
            start_point: Starting point (x, y)
            end_point: Ending point (x, y)
        
        Returns:
            List of control points
        """
        # Apply momentum to get initial control points
        control_points = self._apply_momentum(start_point, end_point)
        
        # Calculate distance and angle
        dx = end_point[0] - start_point[0]
        dy = end_point[1] - start_point[1]
        distance = math.sqrt(dx * dx + dy * dy)
        angle = math.atan2(dy, dx)
        
        # Determine number of control points based on distance and accuracy
        accuracy = self.profile.get_current_accuracy()
        base_points = min(5, max(3, int(distance / 300) + 3))
        num_control_points = max(3, int(base_points * (1.0 + (1.0 - accuracy))))
        
        # If we already have enough control points, return them
        if len(control_points) >= num_control_points:
            return control_points
        
        # Generate additional intermediate control points
        result_points = [control_points[0]]  # Start with first point
        
        # Calculate perpendicular direction for control points
        perp_angle = angle + math.pi / 2
        
        # Calculate maximum deviation based on distance, jitter factor, and accuracy
        max_deviation = min(100, distance * 0.4 * self.profile.jitter_factor * (1.0 + (1.0 - accuracy)))
        
        # Insert additional control points
        for i in range(1, num_control_points - 1):
            # Position along the line (0 to 1)
            t = i / (num_control_points - 1)
            
            # Base point along the straight line
            base_x = start_point[0] + t * dx
            base_y = start_point[1] + t * dy
            
            # Random deviation perpendicular to the line
            deviation = random.uniform(-max_deviation, max_deviation)
            dev_x = deviation * math.cos(perp_angle)
            dev_y = deviation * math.sin(perp_angle)
            
            # Add some randomness to the point's position along the line
            along_deviation = random.uniform(-0.1, 0.1) * distance
            along_dev_x = along_deviation * math.cos(angle)
            along_dev_y = along_deviation * math.sin(angle)
            
            # Final control point
            control_x = base_x + dev_x + along_dev_x
            control_y = base_y + dev_y + along_dev_y
            
            result_points.append((control_x, control_y))
        
        # Add end point
        result_points.append(control_points[-1])
        
        return result_points
    
    def _apply_acceleration_profile(
        self,
        points: List[Tuple[int, int]],
        start_speed: float,
        end_speed: float
    ) -> List[Tuple[int, int, float]]:
        """
        Apply acceleration profile to movement points with enhanced physics
        
        Args:
            points: List of points along the path
            start_speed: Starting speed factor
            end_speed: Ending speed factor
        
        Returns:
            List of points with timing information (x, y, delay)
        """
        num_points = len(points)
        if num_points < 2:
            return [(points[0][0], points[0][1], 0.0)]
        
        # Base delay between points (lower = faster)
        current_speed_factor = self.profile.get_current_speed_factor()
        base_delay = 0.005 / current_speed_factor
        
        # Calculate point-to-point distances
        distances = []
        total_distance = 0
        
        for i in range(1, num_points):
            dx = points[i][0] - points[i-1][0]
            dy = points[i][1] - points[i-1][1]
            distance = math.sqrt(dx * dx + dy * dy)
            distances.append(distance)
            total_distance += distance
        
        # Apply acceleration profile
        timed_points = [(points[0][0], points[0][1], 0.0)]
        
        # Acceleration parameters
        accel_factor = self.profile.acceleration_factor
        friction_factor = self.profile.friction_factor
        
        # Current speed (pixels per second)
        current_speed = start_speed
        
        for i in range(1, num_points):
            # Position along the path (0 to 1)
            t = (i - 1) / (num_points - 2) if num_points > 2 else 0.5
            
            # Calculate target speed based on position
            if t < 0.5:
                # Accelerating phase
                target_speed = start_speed + (1.0 - start_speed) * (t * 2) ** accel_factor
            else:
                # Decelerating phase
                target_speed = 1.0 + (end_speed - 1.0) * ((t - 0.5) * 2) ** accel_factor
            
            # Apply friction to gradually change speed
            speed_diff = target_speed - current_speed
            current_speed += speed_diff * friction_factor
            
            # Calculate delay based on distance and speed
            distance_factor = distances[i-1] / (total_distance / (num_points - 1))
            delay = base_delay * distance_factor / current_speed
            
            # Add some randomness to the delay
            delay *= random.uniform(0.9, 1.1)
            
            timed_points.append((points[i][0], points[i][1], delay))
        
        return timed_points
    
    def _should_overshoot(self, distance: float) -> bool:
        """
        Determine if movement should overshoot based on distance and personality
        
        Args:
            distance: Movement distance
        
        Returns:
            True if movement should overshoot
        """
        # Base probability increases with distance
        base_prob = min(0.3, distance / 500)
        
        # Adjust based on overshoot factor and personality
        prob = base_prob * self.profile.overshoot_factor
        
        # Fatigue increases overshoot probability
        fatigue_level = self.profile.fatigue.current_level
        prob *= (1.0 + fatigue_level * 0.5)
        
        return random.random() < prob
    
    def _generate_overshoot_point(
        self,
        start_point: Tuple[int, int],
        end_point: Tuple[int, int]
    ) -> Tuple[int, int]:
        """
        Generate overshoot point with enhanced realism
        
        Args:
            start_point: Starting point (x, y)
            end_point: Target point (x, y)
        
        Returns:
            Overshoot point (x, y)
        """
        # Calculate direction vector
        dx = end_point[0] - start_point[0]
        dy = end_point[1] - start_point[1]
        distance = math.sqrt(dx * dx + dy * dy)
        
        # Normalize direction vector
        if distance > 0:
            dx /= distance
            dy /= distance
        
        # Calculate overshoot distance based on distance, accuracy, and fatigue
        accuracy = self.profile.get_current_accuracy()
        fatigue_level = self.profile.fatigue.current_level
        
        # More fatigue and less accuracy = more overshoot
        overshoot_factor = (1.0 - accuracy) * (1.0 + fatigue_level)
        overshoot_distance = distance * random.uniform(0.05, 0.15) * (1.0 + overshoot_factor)
        
        # Add some perpendicular deviation
        perp_x, perp_y = -dy, dx  # Perpendicular to direction vector
        perp_distance = random.uniform(-0.1, 0.1) * distance
        
        # Calculate overshoot point
        overshoot_x = end_point[0] + dx * overshoot_distance + perp_x * perp_distance
        overshoot_y = end_point[1] + dy * overshoot_distance + perp_y * perp_distance
        
        return (int(round(overshoot_x)), int(round(overshoot_y)))
    
    def _add_drift(self, x: int, y: int) -> Tuple[int, int]:
        """
        Add cursor drift during pauses
        
        Args:
            x: X coordinate
            y: Y coordinate
        
        Returns:
            New position with drift (x, y)
        """
        # Calculate drift amount based on drift factor and fatigue
        drift_amount = self.profile.drift_factor * (1.0 + self.profile.fatigue.current_level)
        
        # Calculate drift
        drift_x = random.uniform(-drift_amount, drift_amount)
        drift_y = random.uniform(-drift_amount, drift_amount)
        
        # Apply drift
        new_x = int(round(x + drift_x))
        new_y = int(round(y + drift_y))
        
        return (new_x, new_y)
    
    def move_to(
        self,
        x: int,
        y: int,
        duration: Optional[float] = None,
        start_speed: float = 0.8,
        end_speed: float = 0.7
    ) -> bool:
        """
        Move mouse to position with enhanced humanized movement
        
        Args:
            x: Target x coordinate
            y: Target y coordinate
            duration: Movement duration in seconds (None for automatic)
            start_speed: Starting speed factor (0.5-1.5)
            end_speed: Ending speed factor (0.5-1.5)
        
        Returns:
            True if movement was successful
        """
        try:
            # Update activity level
            self._update_activity_level(1.0)
            
            # Get current position
            start_x, start_y = self.get_position()
            start_point = (start_x, start_y)
            end_point = (x, y)
            
            # Calculate distance
            dx = x - start_x
            dy = y - start_y
            distance = math.sqrt(dx * dx + dy * dy)
            
            # Skip if already at target position
            if distance < 5:
                # Add small drift if at target
                if self.profile.drift_factor > 0:
                    drift_x, drift_y = self._add_drift(x, y)
                    self.pyautogui.moveTo(drift_x, drift_y)
                    self._add_to_history(drift_x, drift_y)
                return True
            
            # Update last position
            self.last_position = start_point
            self.last_move_time = time.time()
            
            # Check if we should overshoot
            should_overshoot = self._should_overshoot(distance)
            
            if should_overshoot:
                # Generate overshoot point
                overshoot_point = self._generate_overshoot_point(start_point, end_point)
                
                # First move to overshoot point
                self._execute_move(start_point, overshoot_point, duration, start_speed, 1.0)
                
                # Then move to actual target
                self._execute_move(overshoot_point, end_point, duration * 0.3 if duration else None, 0.5, end_speed)
            else:
                # Direct movement to target
                self._execute_move(start_point, end_point, duration, start_speed, end_speed)
            
            # Update last position
            self.last_position = (x, y)
            self.last_move_time = time.time()
            
            # Calculate and store velocity
            self.velocity = self._calculate_velocity()
            
            return True
        
        except Exception as e:
            logger.error(f"Error in enhanced humanized mouse movement: {e}")
            return False
    
    def _execute_move(
        self,
        start_point: Tuple[int, int],
        end_point: Tuple[int, int],
        duration: Optional[float],
        start_speed: float,
        end_speed: float
    ):
        """
        Execute a single mouse movement with enhanced features
        
        Args:
            start_point: Starting point (x, y)
            end_point: Ending point (x, y)
            duration: Movement duration in seconds (None for automatic)
            start_speed: Starting speed factor
            end_speed: Ending speed factor
        """
        # Generate control points for Bezier curve
        control_points = self._generate_control_points(start_point, end_point)
        
        # Get current tremor amount
        tremor = self.profile.get_current_tremor()
        
        # Generate points along the curve with enhanced features
        points = EnhancedBezierCurve.bezier_curve(
            control_points,
            self.profile.smoothness,
            corner_cutting=self.profile.corner_cutting,
            jitter_factor=self.profile.jitter_factor,
            tremor_factor=tremor
        )
        
        # Apply acceleration profile
        timed_points = self._apply_acceleration_profile(points, start_speed, end_speed)
        
        # Calculate total movement time based on delays
        total_delay = sum(point[2] for point in timed_points[1:])
        
        # Adjust delays if duration is specified
        if duration is not None and total_delay > 0:
            delay_factor = duration / total_delay
            timed_points = [(p[0], p[1], p[2] * delay_factor) for p in timed_points]
        
        # Execute movement
        for x, y, delay in timed_points:
            self.pyautogui.moveTo(x, y)
            self._add_to_history(x, y)
            if delay > 0:
                time.sleep(delay)
    
    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = 'left',
        clicks: int = 1,
        interval: Optional[float] = None,
        move_duration: Optional[float] = None
    ) -> bool:
        """
        Move to position and click with enhanced humanized movement
        
        Args:
            x: Target x coordinate (None for current position)
            y: Target y coordinate (None for current position)
            button: Mouse button ('left', 'right', 'middle')
            clicks: Number of clicks
            interval: Interval between clicks in seconds (None for automatic)
            move_duration: Movement duration in seconds (None for automatic)
        
        Returns:
            True if click was successful
        """
        try:
            # Update activity level (clicking is more intense than moving)
            self._update_activity_level(1.5)
            
            # Get current position if x or y is None
            if x is None or y is None:
                current_x, current_y = self.get_position()
                x = x if x is not None else current_x
                y = y if y is not None else current_y
            
            # Move to position
            if not self.move_to(x, y, move_duration):
                return False
            
            # Determine click interval
            if interval is None:
                # Random interval between 0.05 and 0.15 seconds
                # Adjust based on fatigue (more fatigue = slower clicks)
                fatigue_factor = 1.0 + self.profile.fatigue.current_level
                interval = random.uniform(0.05, 0.15) * fatigue_factor
            
            # Perform clicks
            for i in range(clicks):
                # Add small random movement before click (subtle jitter)
                jitter_amount = min(3, max(1, self.profile.jitter_factor))
                
                # Increase jitter with fatigue
                fatigue_jitter = self.profile.fatigue.get_tremor_factor()
                jitter_amount *= (1.0 + fatigue_jitter)
                
                jitter_x = x + random.randint(-int(jitter_amount), int(jitter_amount))
                jitter_y = y + random.randint(-int(jitter_amount), int(jitter_amount))
                
                # Move to jittered position
                self.pyautogui.moveTo(jitter_x, jitter_y)
                self._add_to_history(jitter_x, jitter_y)
                
                # Click
                self.pyautogui.click(button=button)
                
                # Wait between clicks
                if i < clicks - 1:
                    # Add some randomness to interval
                    # More fatigue = more variable intervals
                    variability = 0.1 + (self.profile.fatigue.current_level * 0.2)
                    actual_interval = interval * random.uniform(1.0 - variability, 1.0 + variability)
                    time.sleep(actual_interval)
            
            return True
        
        except Exception as e:
            logger.error(f"Error in enhanced humanized mouse click: {e}")
            return False
    
    def drag_to(
        self,
        x: int,
        y: int,
        button: str = 'left',
        duration: Optional[float] = None
    ) -> bool:
        """
        Drag mouse to position with enhanced humanized movement
        
        Args:
            x: Target x coordinate
            y: Target y coordinate
            button: Mouse button ('left', 'right', 'middle')
            duration: Movement duration in seconds (None for automatic)
        
        Returns:
            True if drag was successful
        """
        try:
            # Update activity level (dragging is more intense than moving)
            self._update_activity_level(2.0)
            
            # Get current position
            start_x, start_y = self.get_position()
            
            # Press mouse button
            self.pyautogui.mouseDown(button=button)
            
            # Move to target position with slower speed
            # Dragging is typically slower and more precise than regular movement
            result = self.move_to(
                x, y,
                duration,
                start_speed=0.6,  # Slower start speed for dragging
                end_speed=0.5     # Slower end speed for dragging
            )
            
            # Release mouse button
            self.pyautogui.mouseUp(button=button)
            
            return result
        
        except Exception as e:
            logger.error(f"Error in enhanced humanized mouse drag: {e}")
            # Ensure mouse button is released
            try:
                self.pyautogui.mouseUp(button=button)
            except:
                pass
            return False
    
    def get_movement_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about recent mouse movements
        
        Returns:
            Dictionary with movement statistics
        """
        stats = {
            'fatigue_level': self.profile.fatigue.current_level,
            'activity_level': self.activity_level,
            'tremor_factor': self.profile.get_current_tremor(),
            'speed_factor': self.profile.get_current_speed_factor(),
            'accuracy': self.profile.get_current_accuracy(),
            'personality': self.profile.personality.name
        }
        
        # Calculate velocity statistics if we have enough history
        if len(self.position_history) >= 2:
            velocities = []
            for i in range(1, len(self.position_history)):
                x1, y1, t1 = self.position_history[i-1]
                x2, y2, t2 = self.position_history[i]
                
                dt = t2 - t1
                if dt > 0:
                    vx = (x2 - x1) / dt
                    vy = (y2 - y1) / dt
                    v_mag = math.sqrt(vx * vx + vy * vy)
                    velocities.append(v_mag)
            
            if velocities:
                stats['avg_velocity'] = sum(velocities) / len(velocities)
                stats['max_velocity'] = max(velocities)
                stats['current_velocity'] = math.sqrt(self.velocity[0]**2 + self.velocity[1]**2)
        
        return stats
    
    def reset_fatigue(self):
        """Reset fatigue to base level"""
        self.profile.fatigue.reset()
        logger.info("Reset mouse fatigue to base level")