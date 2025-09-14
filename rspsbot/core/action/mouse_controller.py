"""
Mouse controller for RSPS Color Bot v3
"""
import time
import random
import math
import logging
from typing import Tuple, Optional, Callable

import pyautogui

# Get module logger
logger = logging.getLogger('rspsbot.core.action.mouse_controller')

# Configure PyAutoGUI
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01  # Minimum delay between PyAutoGUI commands

class MouseController:
    """
    Controller for mouse movements and clicks
    
    This class provides methods for moving the mouse and clicking with
    humanized movements and timing.
    """
    
    def __init__(self, config_manager):
        """
        Initialize the mouse controller
        
        Args:
            config_manager: Configuration manager
        """
        self.config_manager = config_manager
        
        # Anti-overclick protection
        self._last_click_time = 0.0
        self._last_click_pos = None
        
        logger.info("Mouse controller initialized")
    
    def move_to(self, x: int, y: int, duration: Optional[float] = None) -> bool:
        """
        Move mouse to position with humanized movement
        
        Args:
            x, y: Target coordinates
            duration: Movement duration in seconds (None for automatic)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Determine duration
            if duration is None:
                humanize = self.config_manager.get('humanize_on', True)
                duration = self._rand_between(0.04, 0.10) if humanize else 0.05
            
            # Move mouse
            pyautogui.moveTo(x, y, duration=duration)
            return True
        
        except Exception as e:
            logger.error(f"Error moving mouse to ({x}, {y}): {e}")
            return False
    
    def click(self, button: str = 'left', clicks: int = 1, interval: Optional[float] = None) -> bool:
        """
        Click at current mouse position
        
        Args:
            button: Mouse button ('left', 'right', 'middle')
            clicks: Number of clicks
            interval: Interval between clicks (None for automatic)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Determine interval
            if interval is None:
                humanize = self.config_manager.get('humanize_on', True)
                interval = self._rand_between(0.05, 0.15) if humanize else 0.1
            
            # Click
            pyautogui.click(button=button, clicks=clicks, interval=interval)
            return True
        
        except Exception as e:
            logger.error(f"Error clicking mouse: {e}")
            return False
    
    def move_and_click(
        self,
        x: int,
        y: int,
        button: str = 'left',
        clicks: int = 1,
        move_duration: Optional[float] = None,
        click_delay: Optional[float] = None,
        post_click_sleep: Optional[float] = None
    ) -> bool:
        """
        Move mouse to position and click
        
        Args:
            x, y: Target coordinates
            button: Mouse button ('left', 'right', 'middle')
            clicks: Number of clicks
            move_duration: Movement duration in seconds (None for automatic)
            click_delay: Delay before clicking (None for automatic)
            post_click_sleep: Sleep after clicking (None for automatic)
        
        Returns:
            True if successful, False otherwise
        """
        # Check anti-overclick
        if not self._check_click_allowed(x, y):
            logger.debug(f"Click at ({x}, {y}) blocked by anti-overclick")
            return False
        
        try:
            # Move mouse
            if not self.move_to(x, y, duration=move_duration):
                return False
            
            # Delay before click
            if click_delay is None:
                click_delay = self.config_manager.get('click_delay', 0.05)
            
            self._human_pause(click_delay)
            
            # Click
            pyautogui.mouseDown(button=button)
            self._human_pause(0.02)
            pyautogui.mouseUp(button=button)
            
            # Additional clicks
            for _ in range(1, clicks):
                self._human_pause(0.05)
                pyautogui.mouseDown(button=button)
                self._human_pause(0.02)
                pyautogui.mouseUp(button=button)
            
            # Update anti-overclick
            self._last_click_time = time.time()
            self._last_click_pos = (x, y)
            
            # Sleep after click
            if post_click_sleep is None:
                post_click_sleep = self.config_manager.get('click_after_found_sleep', 0.4)
            
            self._human_pause(post_click_sleep)
            
            return True
        
        except Exception as e:
            logger.error(f"Error moving and clicking at ({x}, {y}): {e}")
            return False
    
    def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: Optional[float] = None,
        button: str = 'left'
    ) -> bool:
        """
        Drag mouse from start to end position
        
        Args:
            start_x, start_y: Start coordinates
            end_x, end_y: End coordinates
            duration: Drag duration in seconds (None for automatic)
            button: Mouse button ('left', 'right', 'middle')
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Move to start position
            if not self.move_to(start_x, start_y):
                return False
            
            # Determine duration
            if duration is None:
                humanize = self.config_manager.get('humanize_on', True)
                duration = self._rand_between(0.2, 0.5) if humanize else 0.3
            
            # Drag
            pyautogui.dragTo(end_x, end_y, duration=duration, button=button)
            
            # Update anti-overclick
            self._last_click_time = time.time()
            self._last_click_pos = (end_x, end_y)
            
            return True
        
        except Exception as e:
            logger.error(f"Error dragging from ({start_x}, {start_y}) to ({end_x}, {end_y}): {e}")
            return False
    
    def _check_click_allowed(self, x: int, y: int) -> bool:
        """
        Check if click is allowed by anti-overclick protection
        
        Args:
            x, y: Target coordinates
        
        Returns:
            True if click is allowed, False otherwise
        """
        # Check cooldown
        now = time.time()
        cooldown = self.config_manager.get('min_monster_click_cooldown_s', 0.8)
        
        if now - self._last_click_time < cooldown:
            return False
        
        # Check distance
        if self._last_click_pos is not None:
            min_distance = self.config_manager.get('min_monster_click_distance_px', 12)
            dx = x - self._last_click_pos[0]
            dy = y - self._last_click_pos[1]
            
            if math.hypot(dx, dy) < min_distance:
                return False
        
        return True
    
    def _rand_between(self, a: float, b: float) -> float:
        """
        Generate random number between a and b
        
        Args:
            a, b: Range bounds
        
        Returns:
            Random float between a and b
        """
        return a + (b - a) * random.random()
    
    def _human_pause(self, base: float, jitter: float = 0.15):
        """
        Pause for a humanized duration
        
        Args:
            base: Base duration in seconds
            jitter: Jitter factor (0.0 - 1.0)
        """
        if not self.config_manager.get('humanize_on', True):
            time.sleep(base)
            return
        
        jitter_amount = base * jitter
        time.sleep(max(0.0, base + random.uniform(-jitter_amount, jitter_amount)))