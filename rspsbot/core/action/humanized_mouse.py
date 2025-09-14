"""
Enhanced humanized mouse movement for RSPS Color Bot v3
"""
import logging
import time
import random
import math
import numpy as np
from typing import Tuple, List, Optional, Dict, Any, Union

# Get module logger
logger = logging.getLogger('rspsbot.core.action.humanized_mouse')

class BezierCurve:
    """
    Bezier curve implementation for generating human-like mouse movement paths
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
        return BezierCurve.binomial(n, i) * (t ** i) * ((1 - t) ** (n - i))
    
    @staticmethod
    def bezier_curve(control_points: List[Tuple[float, float]], num_points: int = 50) -> List[Tuple[int, int]]:
        """
        Generate points along a Bezier curve
        
        Args:
            control_points: List of control points (x, y)
            num_points: Number of points to generate
        
        Returns:
            List of points along the curve
        """
        n = len(control_points) - 1
        curve_points = []
        
        for i in range(num_points):
            t = i / (num_points - 1)
            x = 0
            y = 0
            
            for j in range(n + 1):
                bernstein = BezierCurve.bernstein_polynomial(j, n, t)
                x += bernstein * control_points[j][0]
                y += bernstein * control_points[j][1]
            
            curve_points.append((int(round(x)), int(round(y))))
        
        return curve_points

class MouseMovementProfile:
    """
    Profile for customizing mouse movement characteristics
    """
    
    def __init__(
        self,
        speed_factor: float = 1.0,
        jitter_factor: float = 1.0,
        overshoot_factor: float = 1.0,
        acceleration_factor: float = 1.0,
        smoothness: int = 50
    ):
        """
        Initialize mouse movement profile
        
        Args:
            speed_factor: Factor affecting movement speed (higher = faster)
            jitter_factor: Factor affecting movement jitter (higher = more jitter)
            overshoot_factor: Factor affecting overshoot probability (higher = more overshooting)
            acceleration_factor: Factor affecting acceleration/deceleration (higher = more variation)
            smoothness: Number of points to generate along the curve (higher = smoother)
        """
        self.speed_factor = max(0.1, min(5.0, speed_factor))
        self.jitter_factor = max(0.0, min(5.0, jitter_factor))
        self.overshoot_factor = max(0.0, min(5.0, overshoot_factor))
        self.acceleration_factor = max(0.1, min(5.0, acceleration_factor))
        self.smoothness = max(10, min(200, smoothness))
    
    @classmethod
    def create_profile(cls, profile_type: str) -> 'MouseMovementProfile':
        """
        Create a predefined mouse movement profile
        
        Args:
            profile_type: Profile type ('human', 'fast', 'precise', 'erratic', 'smooth')
        
        Returns:
            MouseMovementProfile instance
        """
        if profile_type == 'human':
            return cls(
                speed_factor=1.0,
                jitter_factor=1.0,
                overshoot_factor=1.0,
                acceleration_factor=1.0,
                smoothness=50
            )
        elif profile_type == 'fast':
            return cls(
                speed_factor=2.0,
                jitter_factor=0.7,
                overshoot_factor=1.2,
                acceleration_factor=1.5,
                smoothness=30
            )
        elif profile_type == 'precise':
            return cls(
                speed_factor=0.8,
                jitter_factor=0.3,
                overshoot_factor=0.2,
                acceleration_factor=0.7,
                smoothness=80
            )
        elif profile_type == 'erratic':
            return cls(
                speed_factor=1.5,
                jitter_factor=2.5,
                overshoot_factor=2.0,
                acceleration_factor=2.0,
                smoothness=40
            )
        elif profile_type == 'smooth':
            return cls(
                speed_factor=0.9,
                jitter_factor=0.2,
                overshoot_factor=0.1,
                acceleration_factor=0.5,
                smoothness=100
            )
        else:
            logger.warning(f"Unknown profile type: {profile_type}, using 'human' profile")
            return cls.create_profile('human')

class HumanizedMouse:
    """
    Enhanced humanized mouse movement implementation
    """
    
    def __init__(self, pyautogui_module=None):
        """
        Initialize humanized mouse
        
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
        self.profile = MouseMovementProfile.create_profile('human')
        
        # Movement state
        self.last_position = self.get_position()
        self.last_move_time = time.time()
    
    def set_profile(self, profile: Union[MouseMovementProfile, str]):
        """
        Set mouse movement profile
        
        Args:
            profile: MouseMovementProfile instance or profile type string
        """
        if isinstance(profile, str):
            self.profile = MouseMovementProfile.create_profile(profile)
        else:
            self.profile = profile
        
        logger.debug(f"Mouse profile set: speed={self.profile.speed_factor}, "
                    f"jitter={self.profile.jitter_factor}, "
                    f"overshoot={self.profile.overshoot_factor}, "
                    f"acceleration={self.profile.acceleration_factor}, "
                    f"smoothness={self.profile.smoothness}")
    
    def get_position(self) -> Tuple[int, int]:
        """
        Get current mouse position
        
        Returns:
            Current (x, y) position
        """
        return self.pyautogui.position()
    
    def _generate_control_points(
        self,
        start_point: Tuple[int, int],
        end_point: Tuple[int, int]
    ) -> List[Tuple[float, float]]:
        """
        Generate control points for Bezier curve
        
        Args:
            start_point: Starting point (x, y)
            end_point: Ending point (x, y)
        
        Returns:
            List of control points
        """
        # Calculate distance and angle
        dx = end_point[0] - start_point[0]
        dy = end_point[1] - start_point[1]
        distance = math.sqrt(dx * dx + dy * dy)
        angle = math.atan2(dy, dx)
        
        # Determine number of control points based on distance
        num_control_points = min(5, max(3, int(distance / 300) + 3))
        
        # Start and end points
        control_points = [
            (float(start_point[0]), float(start_point[1])),
            (float(end_point[0]), float(end_point[1]))
        ]
        
        # Generate intermediate control points
        if num_control_points > 2:
            # Calculate perpendicular direction for control points
            perp_angle = angle + math.pi / 2
            
            # Calculate maximum deviation based on distance and jitter factor
            max_deviation = min(100, distance * 0.4 * self.profile.jitter_factor)
            
            # Insert control points at the beginning
            for i in range(num_control_points - 2):
                # Position along the line (0 to 1)
                t = (i + 1) / (num_control_points - 1)
                
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
                
                # Insert at position i+1 (between start and end)
                control_points.insert(i + 1, (control_x, control_y))
        
        return control_points
    
    def _apply_acceleration_profile(
        self,
        points: List[Tuple[int, int]],
        start_speed: float,
        end_speed: float
    ) -> List[Tuple[int, int, float]]:
        """
        Apply acceleration profile to movement points
        
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
        base_delay = 0.005 / self.profile.speed_factor
        
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
        
        for i in range(1, num_points):
            # Position along the path (0 to 1)
            t = (i - 1) / (num_points - 2) if num_points > 2 else 0.5
            
            # Apply acceleration curve
            if t < 0.5:
                # Accelerating phase
                speed_factor = start_speed + (1.0 - start_speed) * (t * 2) ** accel_factor
            else:
                # Decelerating phase
                speed_factor = 1.0 + (end_speed - 1.0) * ((t - 0.5) * 2) ** accel_factor
            
            # Calculate delay based on distance and speed
            distance_factor = distances[i-1] / (total_distance / (num_points - 1))
            delay = base_delay * distance_factor / speed_factor
            
            # Add some randomness to the delay
            delay *= random.uniform(0.9, 1.1)
            
            timed_points.append((points[i][0], points[i][1], delay))
        
        return timed_points
    
    def _should_overshoot(self, distance: float) -> bool:
        """
        Determine if movement should overshoot
        
        Args:
            distance: Movement distance
        
        Returns:
            True if movement should overshoot
        """
        # Base probability increases with distance
        base_prob = min(0.3, distance / 500)
        
        # Adjust based on overshoot factor
        prob = base_prob * self.profile.overshoot_factor
        
        return random.random() < prob
    
    def _generate_overshoot_point(
        self,
        start_point: Tuple[int, int],
        end_point: Tuple[int, int]
    ) -> Tuple[int, int]:
        """
        Generate overshoot point
        
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
        
        # Calculate overshoot distance (5-15% of total distance)
        overshoot_distance = distance * random.uniform(0.05, 0.15)
        
        # Add some perpendicular deviation
        perp_x, perp_y = -dy, dx  # Perpendicular to direction vector
        perp_distance = random.uniform(-0.1, 0.1) * distance
        
        # Calculate overshoot point
        overshoot_x = end_point[0] + dx * overshoot_distance + perp_x * perp_distance
        overshoot_y = end_point[1] + dy * overshoot_distance + perp_y * perp_distance
        
        return (int(round(overshoot_x)), int(round(overshoot_y)))
    
    def move_to(
        self,
        x: int,
        y: int,
        duration: Optional[float] = None,
        start_speed: float = 0.8,
        end_speed: float = 0.7
    ) -> bool:
        """
        Move mouse to position with humanized movement
        
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
            
            return True
        
        except Exception as e:
            logger.error(f"Error in humanized mouse movement: {e}")
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
        Execute a single mouse movement
        
        Args:
            start_point: Starting point (x, y)
            end_point: Ending point (x, y)
            duration: Movement duration in seconds (None for automatic)
            start_speed: Starting speed factor
            end_speed: Ending speed factor
        """
        # Generate control points for Bezier curve
        control_points = self._generate_control_points(start_point, end_point)
        
        # Generate points along the curve
        points = BezierCurve.bezier_curve(control_points, self.profile.smoothness)
        
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
        Move to position and click with humanized movement
        
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
                interval = random.uniform(0.05, 0.15)
            
            # Perform clicks
            for i in range(clicks):
                # Add small random movement before click (subtle jitter)
                jitter_amount = min(3, max(1, self.profile.jitter_factor))
                jitter_x = x + random.randint(-int(jitter_amount), int(jitter_amount))
                jitter_y = y + random.randint(-int(jitter_amount), int(jitter_amount))
                
                # Move to jittered position
                self.pyautogui.moveTo(jitter_x, jitter_y)
                
                # Click
                self.pyautogui.click(button=button)
                
                # Wait between clicks
                if i < clicks - 1:
                    # Add some randomness to interval
                    actual_interval = interval * random.uniform(0.9, 1.1)
                    time.sleep(actual_interval)
            
            return True
        
        except Exception as e:
            logger.error(f"Error in humanized mouse click: {e}")
            return False
    
    def drag_to(
        self,
        x: int,
        y: int,
        button: str = 'left',
        duration: Optional[float] = None
    ) -> bool:
        """
        Drag mouse to position with humanized movement
        
        Args:
            x: Target x coordinate
            y: Target y coordinate
            button: Mouse button ('left', 'right', 'middle')
            duration: Movement duration in seconds (None for automatic)
        
        Returns:
            True if drag was successful
        """
        try:
            # Get current position
            start_x, start_y = self.get_position()
            
            # Press mouse button
            self.pyautogui.mouseDown(button=button)
            
            # Move to target position
            result = self.move_to(x, y, duration)
            
            # Release mouse button
            self.pyautogui.mouseUp(button=button)
            
            return result
        
        except Exception as e:
            logger.error(f"Error in humanized mouse drag: {e}")
            # Ensure mouse button is released
            try:
                self.pyautogui.mouseUp(button=button)
            except:
                pass
            return False