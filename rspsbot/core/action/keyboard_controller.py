"""
Keyboard controller for RSPS Color Bot v3
"""
import time
import logging
from typing import List, Optional, Union, Tuple

# Get module logger
logger = logging.getLogger('rspsbot.core.action.keyboard_controller')

class KeyboardController:
    """
    Controller for keyboard input
    
    This class provides methods for keyboard input with support for
    different keyboard libraries and humanized timing.
    """
    
    def __init__(self, config_manager):
        """
        Initialize the keyboard controller
        
        Args:
            config_manager: Configuration manager
        """
        self.config_manager = config_manager
        
        # Try to import keyboard libraries
        self.keyboard_lib = None
        self.pynput_keyboard = None
        
        # Try to import keyboard
        try:
            import keyboard
            self.keyboard_lib = keyboard
            logger.info("Using 'keyboard' library for keyboard input")
        except ImportError:
            logger.debug("'keyboard' library not available")
        
        # Try to import pynput as fallback
        if self.keyboard_lib is None:
            try:
                from pynput import keyboard
                self.pynput_keyboard = keyboard
                logger.info("Using 'pynput' library for keyboard input")
            except ImportError:
                logger.debug("'pynput' library not available")
        
        # Try to import pyautogui as fallback
        if self.keyboard_lib is None and self.pynput_keyboard is None:
            try:
                import pyautogui
                self.pyautogui = pyautogui
                logger.info("Using 'pyautogui' library for keyboard input")
            except ImportError:
                logger.warning("No keyboard library available")
                self.pyautogui = None
        else:
            self.pyautogui = None
        
        logger.info("Keyboard controller initialized")
    
    def press_key(self, key: str, hold_time: Optional[float] = None) -> bool:
        """
        Press and release a key
        
        Args:
            key: Key to press
            hold_time: Time to hold key in seconds (None for default)
        
        Returns:
            True if successful, False otherwise
        """
        if hold_time is None:
            hold_time = self.config_manager.get('key_press_hold_time', 0.1)
        
        try:
            # Use keyboard library if available
            if self.keyboard_lib:
                self.keyboard_lib.press(key)
                time.sleep(hold_time)
                self.keyboard_lib.release(key)
                return True
            
            # Use pynput as fallback
            elif self.pynput_keyboard:
                controller = self.pynput_keyboard.Controller()
                
                # Convert string key to pynput key
                pynput_key = self._string_to_pynput_key(key)
                if pynput_key is None:
                    logger.error(f"Invalid key for pynput: {key}")
                    return False
                
                controller.press(pynput_key)
                time.sleep(hold_time)
                controller.release(pynput_key)
                return True
            
            # Use pyautogui as fallback
            elif self.pyautogui:
                self.pyautogui.keyDown(key)
                time.sleep(hold_time)
                self.pyautogui.keyUp(key)
                return True
            
            else:
                logger.error("No keyboard library available")
                return False
        
        except Exception as e:
            logger.error(f"Error pressing key {key}: {e}")
            return False
    
    def press_keys(self, keys: List[str], interval: Optional[float] = None) -> bool:
        """
        Press multiple keys in sequence
        
        Args:
            keys: List of keys to press
            interval: Interval between key presses (None for default)
        
        Returns:
            True if all keys were pressed successfully, False otherwise
        """
        if interval is None:
            interval = self.config_manager.get('key_press_interval', 0.05)
        
        success = True
        
        for key in keys:
            if not self.press_key(key):
                success = False
            
            time.sleep(interval)
        
        return success
    
    def press_hotkey(self, hotkey: str) -> bool:
        """
        Press a hotkey combination (e.g., 'ctrl+c')
        
        Args:
            hotkey: Hotkey combination (e.g., 'ctrl+c', 'alt+f4')
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use keyboard library if available
            if self.keyboard_lib:
                self.keyboard_lib.press_and_release(hotkey)
                return True
            
            # Use pynput as fallback
            elif self.pynput_keyboard:
                controller = self.pynput_keyboard.Controller()
                
                # Parse hotkey string
                keys = hotkey.split('+')
                pynput_keys = []
                
                for key in keys:
                    pynput_key = self._string_to_pynput_key(key.strip())
                    if pynput_key is None:
                        logger.error(f"Invalid key for pynput: {key}")
                        return False
                    
                    pynput_keys.append(pynput_key)
                
                # Press all keys in sequence
                for key in pynput_keys:
                    controller.press(key)
                
                # Release in reverse order
                for key in reversed(pynput_keys):
                    controller.release(key)
                
                return True
            
            # Use pyautogui as fallback
            elif self.pyautogui:
                self.pyautogui.hotkey(*hotkey.split('+'))
                return True
            
            else:
                logger.error("No keyboard library available")
                return False
        
        except Exception as e:
            logger.error(f"Error pressing hotkey {hotkey}: {e}")
            return False
    
    def type_text(self, text: str, interval: Optional[float] = None) -> bool:
        """
        Type text
        
        Args:
            text: Text to type
            interval: Interval between key presses (None for default)
        
        Returns:
            True if successful, False otherwise
        """
        if interval is None:
            interval = self.config_manager.get('key_press_interval', 0.05)
        
        try:
            # Use keyboard library if available
            if self.keyboard_lib:
                self.keyboard_lib.write(text, delay=interval)
                return True
            
            # Use pynput as fallback
            elif self.pynput_keyboard:
                controller = self.pynput_keyboard.Controller()
                
                for char in text:
                    controller.press(char)
                    controller.release(char)
                    time.sleep(interval)
                
                return True
            
            # Use pyautogui as fallback
            elif self.pyautogui:
                self.pyautogui.write(text, interval=interval)
                return True
            
            else:
                logger.error("No keyboard library available")
                return False
        
        except Exception as e:
            logger.error(f"Error typing text: {e}")
            return False
    
    def _string_to_pynput_key(self, key_str: str) -> Optional[Union[str, object]]:
        """
        Convert string key to pynput key
        
        Args:
            key_str: Key string
        
        Returns:
            Pynput key or None if invalid
        """
        if self.pynput_keyboard is None:
            return None
        
        # Special keys
        special_keys = {
            'alt': self.pynput_keyboard.Key.alt,
            'alt_l': self.pynput_keyboard.Key.alt_l,
            'alt_r': self.pynput_keyboard.Key.alt_r,
            'ctrl': self.pynput_keyboard.Key.ctrl,
            'ctrl_l': self.pynput_keyboard.Key.ctrl_l,
            'ctrl_r': self.pynput_keyboard.Key.ctrl_r,
            'shift': self.pynput_keyboard.Key.shift,
            'shift_l': self.pynput_keyboard.Key.shift_l,
            'shift_r': self.pynput_keyboard.Key.shift_r,
            'enter': self.pynput_keyboard.Key.enter,
            'return': self.pynput_keyboard.Key.enter,
            'space': self.pynput_keyboard.Key.space,
            'tab': self.pynput_keyboard.Key.tab,
            'esc': self.pynput_keyboard.Key.esc,
            'escape': self.pynput_keyboard.Key.esc,
            'backspace': self.pynput_keyboard.Key.backspace,
            'delete': self.pynput_keyboard.Key.delete,
            'insert': self.pynput_keyboard.Key.insert,
            'home': self.pynput_keyboard.Key.home,
            'end': self.pynput_keyboard.Key.end,
            'page_up': self.pynput_keyboard.Key.page_up,
            'page_down': self.pynput_keyboard.Key.page_down,
            'up': self.pynput_keyboard.Key.up,
            'down': self.pynput_keyboard.Key.down,
            'left': self.pynput_keyboard.Key.left,
            'right': self.pynput_keyboard.Key.right,
            'f1': self.pynput_keyboard.Key.f1,
            'f2': self.pynput_keyboard.Key.f2,
            'f3': self.pynput_keyboard.Key.f3,
            'f4': self.pynput_keyboard.Key.f4,
            'f5': self.pynput_keyboard.Key.f5,
            'f6': self.pynput_keyboard.Key.f6,
            'f7': self.pynput_keyboard.Key.f7,
            'f8': self.pynput_keyboard.Key.f8,
            'f9': self.pynput_keyboard.Key.f9,
            'f10': self.pynput_keyboard.Key.f10,
            'f11': self.pynput_keyboard.Key.f11,
            'f12': self.pynput_keyboard.Key.f12,
        }
        
        # Check if key is a special key
        key_str = key_str.lower()
        if key_str in special_keys:
            return special_keys[key_str]
        
        # Regular character
        if len(key_str) == 1:
            return key_str
        
        logger.warning(f"Unknown key: {key_str}")
        return None