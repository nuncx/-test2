"""
State management for RSPS Color Bot v3
"""
import time
import threading
import logging
from enum import Enum, auto
from typing import Dict, Any, Optional, List, Callable

# Managers used by panels for quick actions
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
    """Enum representing the types of events that can be triggered"""
    STATE_CHANGED = auto()
    MONSTER_FOUND = auto()
    MONSTER_KILLED = auto()
    COMBAT_STARTED = auto()
    COMBAT_ENDED = auto()
    TELEPORT_USED = auto()
    POTION_USED = auto()
    BOOST_USED = auto()
    INSTANCE_ENTERED = auto()
    AGGRO_USED = auto()
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
    
    def subscribe(self, event_type: EventType, callback: Callable[[Dict[str, Any]], None]) -> None:
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
    
    def unsubscribe(self, event_type: EventType, callback: Callable[[Dict[str, Any]], None]) -> None:
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
    
    def publish(self, event_type: EventType, data: Dict[str, Any] = None) -> None:
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
        
        # Statistics
        self._stats = {
            'start_time': None,
            'pause_time': None,
            'total_pause_time': 0,
            'monster_count': 0,
            'teleport_count': 0,
            'potion_count': 0,
            'boost_count': 0,
            'instance_count': 0,
            'aggro_count': 0,
            'error_count': 0,
        }
        
        # Main thread
        self._main_thread = None
        
        # Register event handlers
        self._register_event_handlers()
        
        # Core action manager (mouse/keyboard)
        try:
            self.action_manager = ActionManager(self.config_manager)
            logger.info("Action manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize action manager: {e}")
            self.action_manager = None

        # Feature managers
        try:
            # Local import to avoid circular import during module initialization
            from ..modules.teleport import TeleportManager
            self.teleport_manager = TeleportManager(self.config_manager, self.action_manager, self.event_system)
            logger.info("Teleport manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize teleport manager: {e}")
            self.teleport_manager = None

        try:
            # Local import to avoid circular import during module initialization
            from ..modules.potion import PotionManager
            self.potion_manager = PotionManager(self.config_manager, self.action_manager, self.event_system)
            logger.info("Potion manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize potion manager: {e}")
            self.potion_manager = None

        # Initialize statistics tracker
        try:
            from ..stats import StatisticsTracker
            self.stats_tracker = StatisticsTracker(self.event_system)
            logger.info("Statistics tracker initialized")
        except Exception as e:
            logger.error(f"Failed to initialize statistics tracker: {e}")
            self.stats_tracker = None
        
        logger.info("Bot controller initialized")
        
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

        # Global hotkey (F8) to toggle pause/resume
        self._hotkey_listener_thread = threading.Thread(target=self._install_hotkeys, daemon=True)
        self._hotkey_listener_thread.start()
    
    def _register_event_handlers(self):
        """Register handlers for events"""
        self.event_system.subscribe(EventType.MONSTER_KILLED, self._on_monster_killed)
        self.event_system.subscribe(EventType.TELEPORT_USED, self._on_teleport_used)
        self.event_system.subscribe(EventType.POTION_USED, self._on_potion_used)
        self.event_system.subscribe(EventType.BOOST_USED, self._on_boost_used)
        self.event_system.subscribe(EventType.INSTANCE_ENTERED, self._on_instance_entered)
        self.event_system.subscribe(EventType.AGGRO_USED, self._on_aggro_used)
        self.event_system.subscribe(EventType.ERROR_OCCURRED, self._on_error_occurred)
    
    def _on_monster_killed(self, data):
        """Handle monster killed event"""
        self._stats['monster_count'] += 1
    
    def _on_teleport_used(self, data):
        """Handle teleport used event"""
        self._stats['teleport_count'] += 1
    
    def _on_potion_used(self, data):
        """Handle potion used event"""
        self._stats['potion_count'] += 1
    
    def _on_boost_used(self, data):
        """Handle boost used event"""
        self._stats['boost_count'] += 1
    
    def _on_instance_entered(self, data):
        """Handle instance entered event"""
        self._stats['instance_count'] += 1
    
    def _on_aggro_used(self, data):
        """Handle aggro used event"""
        self._stats['aggro_count'] += 1
    
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
    
    def get_stats(self):
        """Get statistics"""
        return self._stats.copy()
    
    def _main_loop(self):
        """Main bot loop"""
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
                
                # Logging for visibility (INFO so it's visible in Logs panel by default)
                if roi:
                    logger.info(f"ROI: {roi['left']},{roi['top']} {roi['width']}x{roi['height']}")
                logger.info(f"HP bar seen: {'Y' if hp_seen else 'N'}; InCombat: {in_combat}")
                if tiles:
                    logger.info(f"Tiles found: {len(tiles)}; e.g., {tiles[0]}")
                else:
                    logger.info("Tiles found: 0")
                if monsters_by_tile:
                    sample = ", ".join([f"tile {t} -> {c}" for t, c in monsters_by_tile[:3]])
                    logger.info(f"Monsters by tile: {sample}")
                else:
                    logger.info(f"Monsters found: {len(monsters)}")
                
                # Publish detection event including full result for overlay/stats
                self.event_system.publish(EventType.DETECTION_COMPLETED, {
                    'success': len(monsters) > 0,
                    'execution_time': time.time() - cycle_start,
                    'result': result,
                })
                
                # Click target monster only when not in combat (HP bar not visible)
                if (not in_combat) and monsters:
                    try:
                        # Selection strategy: default closest-to-center; optional low-confidence: largest-area
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
                            # Prefer the biggest solid target when detections are weak
                            monsters_sorted = sorted(monsters, key=lambda m: float(m.get('area', 0.0)), reverse=True)
                            strategy = 'largest-area (low-confidence)'
                        else:
                            # Normal mode: click closest to ROI center
                            monsters_sorted = sorted(
                                monsters,
                                key=lambda m: (m['position'][0]-center_x)**2 + (m['position'][1]-center_y)**2
                            )
                            strategy = 'nearest-to-center'

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
                                    if use_low_conf:
                                        try:
                                            area_val = float(target.get('area', 0.0))
                                            area_txt = f"{area_val:.1f}"
                                        except Exception:
                                            area_txt = "n/a"
                                        logger.info(f"Click monster (low-conf) at: ({x}, {y}), area={area_txt}")
                                    else:
                                        logger.info(f"Click monster at: ({x}, {y})")
                                    time.sleep(self.config_manager.get('click_after_found_sleep', 0.4))
                        else:
                            # Cooldown or too close; skip click
                            pass
                    except Exception as e:
                        logger.error(f"Error clicking monster: {e}")
                
                # Camera adjust placeholder logging if enabled (actual adjust logic may exist elsewhere)
                if self.config_manager.get('enable_cam_adjust', True):
                    # In a real flow, log when adjustments happen. Here we emit periodic intent.
                    pass
                
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
    
    This class manages the behavior of the bot based on its current state.
    It defines transitions between states and actions to take in each state.
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
    
    def register_state(self, state_name: str, handler: Callable[[], None]):
        """
        Register a state handler
        
        Args:
            state_name: Name of the state
            handler: Function to call when in this state
        """
        self._state_handlers[state_name] = handler
        logger.debug(f"Registered state handler: {state_name}")
    
    def register_transition(self, from_state: str, to_state: str, condition: Callable[[], bool]):
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