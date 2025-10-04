"""
Bot controller for RSPS Color Bot v3 - CLEANED VERSION

Removed unused features:
- Teleport manager (not used in main loop)
- Potion manager (not used in main loop)
- Instance manager (not used in main loop)
- Related event handlers
- Related statistics
"""
import time
import random
import threading
import logging
from enum import Enum, auto
from typing import Dict, Any, Optional

from ..action import ActionManager

# Get module logger
logger = logging.getLogger('rspsbot.core.state')

class BotState(Enum):
    """Enum representing the possible states of the bot"""
    STOPPED = auto()
    RUNNING = auto()
    PAUSED = auto()
    ERROR = auto()

class EventType(Enum):
    """
    Enum representing the types of events that can be triggered
    
    CLEANED: Removed unused event types:
    - TELEPORT_USED
    - POTION_USED
    - BOOST_USED
    - INSTANCE_ENTERED
    - AGGRO_USED
    """
    STATE_CHANGED = auto()
    MONSTER_FOUND = auto()
    MONSTER_KILLED = auto()
    COMBAT_STARTED = auto()
    COMBAT_ENDED = auto()
    ERROR_OCCURRED = auto()
    TIMEOUT_OCCURRED = auto()
    DETECTION_COMPLETED = auto()

class EventSystem:
    """
    Event system for communication between components
    
    This class implements a simple publish-subscribe pattern for events.
    Components can subscribe to events and be notified when they occur.
    """
    
    def __init__(self):
        """Initialize the event system"""
        self._subscribers = {}
        self._lock = threading.RLock()
    
    def subscribe(self, event_type: EventType, callback):
        """
        Subscribe to an event
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event occurs
        """
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: EventType, callback):
        """
        Unsubscribe from an event
        
        Args:
            event_type: Type of event to unsubscribe from
            callback: Function to unsubscribe
        """
        with self._lock:
            if event_type in self._subscribers:
                if callback in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(callback)
    
    def publish(self, event_type: EventType, data: Dict[str, Any] = None):
        """
        Publish an event
        
        Args:
            event_type: Type of event to publish
            data: Data to pass to subscribers
        """
        if data is None:
            data = {}
        
        # Add timestamp to event data
        data['timestamp'] = time.time()
        
        with self._lock:
            if event_type in self._subscribers:
                for callback in self._subscribers[event_type]:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"Error in event subscriber: {e}")

class BotController:
    """
    Controller for the bot
    
    CLEANED VERSION - Removed unused features:
    - Teleport manager
    - Potion manager
    - Instance manager
    - Related event handlers
    - Related statistics
    
    This class manages the state of the bot and provides methods to control it.
    It also maintains statistics and handles events.
    """
    
    def __init__(self, config_manager):
        """
        Initialize the bot controller
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.event_system = EventSystem()
        
        # State management
        self._state = BotState.STOPPED
        self._state_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        
        # Statistics (CLEANED: removed teleport_count, potion_count, boost_count, instance_count, aggro_count)
        self._stats = {
            'start_time': None,
            'pause_time': None,
            'total_pause_time': 0,
            'monster_count': 0,
            'error_count': 0,
        }
        
        # Main thread
        self._main_thread = None
        
        # Register event handlers (CLEANED: removed unused event handlers)
        self._register_event_handlers()
        
        # Core action manager (mouse/keyboard)
        try:
            self.action_manager = ActionManager(self.config_manager)
            logger.info("Action manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize action manager: {e}")
            self.action_manager = None

        # Initialize statistics tracker
        try:
            from ..stats import StatisticsTracker
            self.stats_tracker = StatisticsTracker(self.event_system)
            logger.info("Statistics tracker initialized")
        except Exception as e:
            logger.error(f"Failed to initialize statistics tracker: {e}")
            self.stats_tracker = None
        
        logger.info("Bot controller initialized (cleaned version)")
        
        # Detection services
        try:
            from ..detection.capture import CaptureService
            from ..detection.detector import DetectionEngine
            self.capture_service = CaptureService()
            self.detection_engine = DetectionEngine(self.config_manager, self.capture_service)
            logger.info("Detection engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize detection engine: {e}")
            self.capture_service = None
            self.detection_engine = None
        
        # Simple runtime guards
        self._last_monster_click_time: float = 0.0
        self._last_monster_click_pos: Optional[tuple] = None

        # Power management: keep system awake while running
        self._keep_awake = None

        # Combat transition tracking (for post-combat delay)
        self._was_in_combat: bool = False
        self._post_combat_until: float = 0.0

        # Global hotkey (F8) to toggle pause/resume
        self._hotkey_listener_thread = threading.Thread(target=self._install_hotkeys, daemon=True)
        self._hotkey_listener_thread.start()
    
    def _register_event_handlers(self):
        """
        Register handlers for events
        
        CLEANED: Only register handlers for events that are actually used
        """
        self.event_system.subscribe(EventType.MONSTER_KILLED, self._on_monster_killed)
        self.event_system.subscribe(EventType.ERROR_OCCURRED, self._on_error_occurred)
    
    def _on_monster_killed(self, data):
        """Handle monster killed event"""
        self._stats['monster_count'] += 1
    
    def _on_error_occurred(self, data):
        """Handle error occurred event"""
        self._stats['error_count'] += 1
        
        # Log error
        error = data.get('error')
        if error:
            logger.error(f"Bot error: {error}")
        
        # Stop bot on critical errors
        if data.get('critical', False):
            logger.error("Critical error occurred, stopping bot")
            self.stop()
    
    def start(self):
        """Start the bot"""
        with self._state_lock:
            if self._state == BotState.RUNNING:
                logger.warning("Bot is already running")
                return
            
            # Reset events
            self._stop_event.clear()
            self._pause_event.clear()
            
            # Update state
            self._state = BotState.RUNNING
            
            # Update statistics
            self._stats['start_time'] = time.time()
            self._stats['pause_time'] = None
            
            # Start main thread
            self._main_thread = threading.Thread(target=self._main_loop, daemon=True)
            self._main_thread.start()

            # Enable KeepAwake if configured
            try:
                if self.config_manager.get("keep_awake_enabled", True):
                    from ...utils.power import KeepAwake
                    self._keep_awake = KeepAwake(
                        keep_display_awake=self.config_manager.get("keep_display_awake", False)
                    )
                    self._keep_awake.start()
                    logger.info(
                        "KeepAwake enabled (display_awake=%s)",
                        self.config_manager.get("keep_display_awake", False),
                    )
            except Exception as e:
                logger.warning(f"KeepAwake setup failed: {e}")
            
            # Publish event
            self.event_system.publish(EventType.STATE_CHANGED, {'state': self._state})
            
            logger.info("Bot started")
    
    def stop(self):
        """Stop the bot"""
        with self._state_lock:
            if self._state == BotState.STOPPED:
                logger.warning("Bot is already stopped")
                return
            
            # Set stop event
            self._stop_event.set()
            
            # Update state
            self._state = BotState.STOPPED
            
            # Reset statistics
            self._stats['start_time'] = None
            self._stats['pause_time'] = None
            
            # Publish event
            self.event_system.publish(EventType.STATE_CHANGED, {'state': self._state})
            
            logger.info("Bot stopped")

        # Disable KeepAwake outside the lock to avoid deadlocks on Windows
        try:
            if self._keep_awake is not None:
                self._keep_awake.stop()
                self._keep_awake = None
                logger.info("KeepAwake disabled")
        except Exception as e:
            logger.debug(f"KeepAwake disable error: {e}")
    
    def pause(self):
        """Pause the bot"""
        with self._state_lock:
            if self._state != BotState.RUNNING:
                logger.warning("Bot is not running, cannot pause")
                return
            
            # Set pause event
            self._pause_event.set()
            
            # Update state
            self._state = BotState.PAUSED
            
            # Update statistics
            self._stats['pause_time'] = time.time()
            
            # Publish event
            self.event_system.publish(EventType.STATE_CHANGED, {'state': self._state})
            
            logger.info("Bot paused")
    
    def resume(self):
        """Resume the bot"""
        with self._state_lock:
            if self._state != BotState.PAUSED:
                logger.warning("Bot is not paused, cannot resume")
                return
            
            # Clear pause event
            self._pause_event.clear()
            
            # Update state
            self._state = BotState.RUNNING
            
            # Update statistics
            if self._stats['pause_time'] is not None:
                self._stats['total_pause_time'] += time.time() - self._stats['pause_time']
                self._stats['pause_time'] = None
            
            # Publish event
            self.event_system.publish(EventType.STATE_CHANGED, {'state': self._state})
            
            logger.info("Bot resumed")
    
    def toggle_pause(self):
        """Toggle pause state"""
        if self._state == BotState.PAUSED:
            self.resume()
        elif self._state == BotState.RUNNING:
            self.pause()
    
    def is_running(self):
        """Check if bot is running"""
        return self._state == BotState.RUNNING
    
    def is_paused(self):
        """Check if bot is paused"""
        return self._state == BotState.PAUSED
    
    def is_stopped(self):
        """Check if bot is stopped"""
        return self._state == BotState.STOPPED
    
    def get_state(self):
        """Get current state"""
        return self._state
    
    def get_runtime(self):
        """
        Get total runtime in seconds
        
        Returns:
            float: Runtime in seconds or 0 if not started
        """
        if self._stats['start_time'] is None:
            return 0
        
        total_time = time.time() - self._stats['start_time']
        
        # Subtract pause time
        if self._state == BotState.PAUSED and self._stats['pause_time'] is not None:
            pause_time = time.time() - self._stats['pause_time']
        else:
            pause_time = 0
        
        return total_time - self._stats['total_pause_time'] - pause_time
    
    def get_monster_count(self):
        """Get number of monsters killed"""
        return self._stats['monster_count']
    
    def get_status(self):
        """Get status string"""
        if self._state == BotState.RUNNING:
            return "Running"
        elif self._state == BotState.PAUSED:
            return "Paused"
        elif self._state == BotState.STOPPED:
            return "Stopped"
        elif self._state == BotState.ERROR:
            return "Error"
        else:
            return "Unknown"
    

    def _should_execute_telekill_cycle(self) -> bool:\n        """Check if we should execute a 1 Tele 1 Kill cycle"""\n        if not self.config_manager.get('enable_telekill', False):\n            return False\n        \n        # Check if enough time has passed since last cycle\n        now = time.time()\n        cycle_delay = self.config_manager.get('telekill_cycle_delay_s', 5.0)\n        \n        # Use a simple timer - you could make this more sophisticated\n        if not hasattr(self, '_last_telekill_time'):\n            self._last_telekill_time = 0.0\n        \n        if now - self._last_telekill_time < cycle_delay:\n            return False\n        \n        return True\n    \n    def _execute_telekill_cycle(self) -> bool:\n        """Execute a complete 1 Tele 1 Kill cycle"""\n        logger.info("Starting 1 Tele 1 Kill cycle")\n        self._last_telekill_time = time.time()\n        \n        try:\n            # Step 1: Get teleport ROI and hotkey\n            tele_roi = self.config_manager.get('telekill_teleport_roi')\n            hotkey = self.config_manager.get('telekill_hotkey', 'ctrl+t')\n            \n            if not tele_roi or not hotkey:\n                logger.warning("1 Tele 1 Kill: Missing ROI or hotkey configuration")\n                return False\n            \n            # Step 2: Click teleport\n            center_x = tele_roi['left'] + tele_roi['width'] // 2\n            center_y = tele_roi['top'] + tele_roi['height'] // 2\n            \n            if self.action_manager.mouse_controller.move_and_click(center_x, center_y, button='left', clicks=1):\n                logger.info(f"1 Tele 1 Kill: Clicked teleport at ({center_x}, {center_y})")\n            else:\n                logger.error("1 Tele 1 Kill: Failed to click teleport")\n                return False\n            \n            # Step 3: Press hotkey\n            if self.action_manager.keyboard_controller.press_key(hotkey):\n                logger.info(f"1 Tele 1 Kill: Pressed hotkey {hotkey}")\n            else:\n                logger.error("1 Tele 1 Kill: Failed to press hotkey")\n                return False\n            \n            # Step 4: Wait and search for monster with delay\n            search_delay_min = self.config_manager.get('telekill_search_delay_min_s', 0.5)\n            search_delay_max = self.config_manager.get('telekill_search_delay_max_s', 2.0)\n            search_delay = random.uniform(search_delay_min, search_delay_max)\n            \n            logger.debug(f"1 Tele 1 Kill: Waiting {search_delay:.2f}s before searching")\n            time.sleep(search_delay)\n            \n            # Step 5: Find and attack monster\n            detection_result = self.detection_engine.detect_cycle()\n            monsters = detection_result.get('monsters', [])\n            \n            if not monsters:\n                logger.info("1 Tele 1 Kill: No monsters found")\n                return False\n            \n            # Select best monster and attack\n            target = monsters[0]  # Simple: use first monster\n            x, y = target['position']\n            \n            if self.action_manager.mouse_controller.move_and_click(x, y, button='left', clicks=1):\n                logger.info(f"1 Tele 1 Kill: Clicked monster at ({x}, {y})")\n            else:\n                logger.error("1 Tele 1 Kill: Failed to click monster")\n                return False\n            \n            # Step 6: Verify kill (HP bar disappeared)\n            verification_delay = 0.5\n            time.sleep(verification_delay)\n            \n            new_result = self.detection_engine.detect_cycle()\n            if not new_result.get('in_combat', False):\n                logger.info("1 Tele 1 Kill: HP bar disappeared - kill verified!")\n                return True\n            else:\n                logger.info("1 Tele 1 Kill: HP bar still visible - kill not verified")\n                return False\n                \n        except Exception as e:\n            logger.error(f"Error in 1 Tele 1 Kill cycle: {e}", exc_info=True)\n            return False
    def get_stats(self):
        """Get statistics"""
        return self._stats.copy()
    
    def _main_loop(self):
        """Main bot loop - UNCHANGED (already only uses detection/clicking)"""
        logger.info("Main bot loop started")
        
        try:
            while not self._stop_event.is_set():
                # Check if paused
                if self._pause_event.is_set():
                    time.sleep(0.1)
                    continue
                
                # If detection engine unavailable, idle
                if self.detection_engine is None:
                    time.sleep(0.2)
                    continue
                
                cycle_start = time.time()
                result = self.detection_engine.detect_cycle()
                tiles = result.get('tiles', [])
                monsters = result.get('monsters', [])
                in_combat = result.get('in_combat', False)
                roi = result.get('roi', {})
                hp_seen = result.get('hp_seen', False)
                monsters_by_tile = result.get('monsters_by_tile', [])
                
                # Logging for visibility
                if roi:
                    logger.info(f"ROI: {roi['left']},{roi['top']} {roi['width']}x{roi['height']}")
                logger.info(f"HP bar seen: {'Y' if hp_seen else 'N'}; InCombat: {in_combat}")

                   # Check if 1 Tele 1 Kill mode is enabled and should execute\n                   if self.config_manager.get('enable_telekill', False) and self._should_execute_telekill_cycle():\n                       logger.info("Executing 1 Tele 1 Kill cycle")\n                       telekill_success = self._execute_telekill_cycle()\n                       if telekill_success:\n                           logger.info("1 Tele 1 Kill cycle completed successfully")\n                           continue  # Skip normal monster detection this cycle\n                       else:\n                           logger.warning("1 Tele 1 Kill cycle failed, continuing with normal detection")
                if tiles:
                    logger.info(f"Tiles found: {len(tiles)}; e.g., {tiles[0]}")
                else:
                    logger.info("Tiles found: 0")
                if monsters_by_tile:
                    sample = ", ".join([f"tile {t} -> {c}" for t, c in monsters_by_tile[:3]])
                    logger.info(f"Monsters by tile: {sample}")
                else:
                    logger.info(f"Monsters found: {len(monsters)}")
                
                # Detect transition: combat -> not in combat
                try:
                    if self._was_in_combat and not in_combat:
                        dmin = float(self.config_manager.get('post_combat_delay_min_s', 1.0))
                        dmax = float(self.config_manager.get('post_combat_delay_max_s', 3.0))
                        delay = dmin if dmax <= dmin else random.uniform(dmin, dmax)
                        self._post_combat_until = time.time() + max(0.0, delay)
                        logger.info(f"Post-combat delay scheduled: {delay:.2f}s")
                except Exception as e:
                    logger.debug(f"Post-combat scheduling error: {e}")
                finally:
                    self._was_in_combat = bool(in_combat)

                # Compute remaining post-combat delay
                try:
                    remaining_delay = max(0.0, getattr(self, '_post_combat_until', 0.0) - time.time())
                    result['post_combat_remaining_s'] = float(remaining_delay)
                except Exception:
                    pass

                # Publish detection event
                self.event_system.publish(EventType.DETECTION_COMPLETED, {
                    'success': len(monsters) > 0,
                    'execution_time': time.time() - cycle_start,
                    'result': result,
                })
                
                # Click target monster only when not in combat
                now_ts = time.time()
                within_post_delay = now_ts < getattr(self, '_post_combat_until', 0.0)
                
                if within_post_delay:
                    remaining = self._post_combat_until - now_ts
                    logger.info(f"Waiting post-combat delay: {remaining:.2f}s remaining")
                
                if (not in_combat) and monsters and (not within_post_delay):
                    try:
                        # Selection strategy
                        low_enabled = bool(self.config_manager.get('low_confidence_click_enabled', True))
                        area_thresh = float(self.config_manager.get('low_confidence_area_threshold', 220.0))
                        min_count = int(self.config_manager.get('low_conf_min_count', 3))

                        center_x = roi['left'] + roi['width'] // 2 if roi else 0
                        center_y = roi['top'] + roi['height'] // 2 if roi else 0

                        use_low_conf = False
                        if low_enabled:
                            try:
                                max_area = max(float(m.get('area', 0.0)) for m in monsters)
                            except Exception:
                                max_area = 0.0
                            if len(monsters) < min_count or max_area < area_thresh:
                                use_low_conf = True

                        if use_low_conf:
                            monsters_sorted = sorted(monsters, key=lambda m: float(m.get('area', 0.0)), reverse=True)
                        else:
                            monsters_sorted = sorted(
                                monsters,
                                key=lambda m: (m['position'][0]-center_x)**2 + (m['position'][1]-center_y)**2
                            )

                        target = monsters_sorted[0]
                        x, y = target['position']

                        # Respect min click distance and cooldown
                        now = time.time()
                        min_cd = float(self.config_manager.get('min_monster_click_cooldown_s', 0.8))
                        min_dist = int(self.config_manager.get('min_monster_click_distance_px', 12))
                        far_enough = True
                        if self._last_monster_click_pos is not None:
                            dx = x - self._last_monster_click_pos[0]
                            dy = y - self._last_monster_click_pos[1]
                            far_enough = (dx*dx + dy*dy) ** 0.5 >= min_dist

                        if (now - self._last_monster_click_time) >= min_cd and far_enough:
                            if self.action_manager:
                                if self.action_manager.mouse_controller.move_and_click(x, y, button='left', clicks=1):
                                    self._last_monster_click_time = now
                                    self._last_monster_click_pos = (x, y)
                                    logger.info(f"Click monster at: ({x}, {y})")
                                    time.sleep(self.config_manager.get('click_after_found_sleep', 0.4))
                    except Exception as e:
                        logger.error(f"Error clicking monster: {e}")
                
                # Sleep based on configured scan interval
                time.sleep(max(0.01, float(self.config_manager.get('scan_interval', 0.2))))
        
        except Exception as e:
            logger.error(f"Error in main bot loop: {e}", exc_info=True)
            self.event_system.publish(EventType.ERROR_OCCURRED, {
                'error': str(e),
                'critical': True
            })
            
            # Update state
            with self._state_lock:
                self._state = BotState.ERROR
                self.event_system.publish(EventType.STATE_CHANGED, {'state': self._state})
        
        finally:
            logger.info("Main bot loop ended")
    
    def _install_hotkeys(self):
        """Install a global F8 hotkey to toggle pause/resume."""
        try:
            # Prefer 'keyboard' library if available
            kb = None
            try:
                import keyboard as _kb
                kb = _kb
            except Exception:
                kb = None

            if kb is not None:
                kb.add_hotkey('f8', lambda: self.toggle_pause())
                logger.info("Hotkey registered: F8 to pause/resume")
                kb.wait()  # keep thread alive
                return
            
            # Fallback to pynput
            try:
                from pynput import keyboard as pk
            except Exception:
                logger.warning("No hotkey backend available (keyboard/pynput missing)")
                return
            
            def on_press(key):
                try:
                    if key == pk.Key.f8:
                        self.toggle_pause()
                except Exception:
                    pass
            
            with pk.Listener(on_press=on_press) as listener:
                logger.info("Hotkey registered (pynput): F8 to pause/resume")
                listener.join()
        except Exception as e:
            logger.error(f"Hotkey listener error: {e}")


class StateMachine:
    """
    State machine for bot behavior
    
    NOTE: This class is defined but not currently used in the bot.
    Consider removing if not needed.
    """
    
    def __init__(self, config_manager, event_system):
        """
        Initialize the state machine
        
        Args:
            config_manager: Configuration manager instance
            event_system: Event system instance
        """
        self.config_manager = config_manager
        self.event_system = event_system
        
        # Current state
        self._current_state = None
        
        # State handlers
        self._state_handlers = {}
        
        # State transitions
        self._state_transitions = {}
        
        logger.info("State machine initialized")
    
    def register_state(self, state_name: str, handler):
        """
        Register a state handler
        
        Args:
            state_name: Name of the state
            handler: Function to call when in this state
        """
        self._state_handlers[state_name] = handler
        logger.debug(f"Registered state handler: {state_name}")
    
    def register_transition(self, from_state: str, to_state: str, condition):
        """
        Register a state transition
        
        Args:
            from_state: Source state
            to_state: Target state
            condition: Function that returns True if transition should occur
        """
        if from_state not in self._state_transitions:
            self._state_transitions[from_state] = []
        
        self._state_transitions[from_state].append((to_state, condition))
        logger.debug(f"Registered transition: {from_state} -> {to_state}")
    
    def set_initial_state(self, state_name: str):
        """
        Set the initial state
        
        Args:
            state_name: Name of the initial state
        """
        if state_name not in self._state_handlers:
            raise ValueError(f"Unknown state: {state_name}")
        
        self._current_state = state_name
        logger.info(f"Initial state set to: {state_name}")
    
    def update(self):
        """
        Update the state machine
        
        This method should be called regularly to update the state machine.
        It checks for transitions and executes the current state handler.
        """
        if self._current_state is None:
            logger.warning("State machine not initialized with initial state")
            return
        
        # Check for transitions
        if self._current_state in self._state_transitions:
            for to_state, condition in self._state_transitions[self._current_state]:
                try:
                    if condition():
                        logger.debug(f"Transition: {self._current_state} -> {to_state}")
                        self._current_state = to_state
                        break
                except Exception as e:
                    logger.error(f"Error in transition condition: {e}")
        
        # Execute current state handler
        if self._current_state in self._state_handlers:
            try:
                self._state_handlers[self._current_state]()
            except Exception as e:
                logger.error(f"Error in state handler {self._current_state}: {e}")
                self.event_system.publish(EventType.ERROR_OCCURRED, {
                    'error': f"Error in state {self._current_state}: {e}",
                    'critical': False
                })
    
    def get_current_state(self):
        """Get current state name"""
        return self._current_state