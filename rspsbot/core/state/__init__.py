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
    
    def publish(self, event_type: EventType, data: Optional[Dict[str, Any]] = None) -> None:
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
            if self.action_manager is not None:
                self.teleport_manager = TeleportManager(self.config_manager, self.action_manager, self.event_system)
                logger.info("Teleport manager initialized")
            else:
                self.teleport_manager = None
                logger.error("Action manager unavailable; teleport manager disabled")
        except Exception as e:
            logger.error(f"Failed to initialize teleport manager: {e}")
            self.teleport_manager = None

        try:
            # Local import to avoid circular import during module initialization
            from ..modules.potion import PotionManager
            if self.action_manager is not None:
                self.potion_manager = PotionManager(self.config_manager, self.action_manager, self.event_system)
                logger.info("Potion manager initialized")
            else:
                self.potion_manager = None
                logger.error("Action manager unavailable; potion manager disabled")
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

        # Chat watcher (OCR-based)
        self.chat_watcher = None
        try:
            if self.capture_service is not None and self.action_manager is not None:
                from ..modules.chat_watcher import ChatWatcher
                self.chat_watcher = ChatWatcher(self.config_manager, self.capture_service, self.action_manager, self.event_system)
        except Exception as e:
            logger.error(f"Failed to initialize ChatWatcher: {e}")

        # Multi Monster Mode integration (lazy components)
        self._multi_monster_detector = None
        self._multi_monster_module = None
        
        # Simple runtime guards
        self._last_monster_click_time: float = 0.0
        self._last_monster_click_pos: Optional[tuple] = None
        # Combat timing (normal mode)
        self._combat_timers = {
            'attack_grace_until': 0.0,          # after we click a monster, wait at least this long before any new attack
            'post_combat_cooldown_until': 0.0,  # after combat ends (HP not visible), wait before searching/attacking again
            'was_in_combat': False,
        }

        # Post-attack verification (HP bar check and optional one-time retry of weapon switch)
        self._post_attack_verify_deadline: float = 0.0
        self._post_attack_retry_done: bool = False

        # Global hotkey (F8) to toggle pause/resume
        self._hotkey_listener_thread = threading.Thread(target=self._install_hotkeys, daemon=True)
        self._hotkey_listener_thread.start()
        # 1 Tele 1 Kill mode runtime state
        self._one_tele_runtime = {
            'hp_verify_deadline': 0.0,
            'last_attack_time': 0.0,
        }
    
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

            # Start chat watcher thread if enabled
            try:
                if self.chat_watcher and bool(self.config_manager.get('chat_enabled', False)):
                    if not self.chat_watcher.is_alive():
                        self.chat_watcher = type(self.chat_watcher)(self.config_manager, self.capture_service, self.action_manager, self.event_system)
                        self.chat_watcher.start()
            except Exception as e:
                logger.error(f"Failed to start ChatWatcher: {e}")
            
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

            # Stop chat watcher
            try:
                if self.chat_watcher and self.chat_watcher.is_alive():
                    self.chat_watcher.stop()
            except Exception:
                pass
            
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
            # Add Instance-Only Mode indicator if enabled
            if self.config_manager.get('instance_only_mode', False):
                return "Running (Instance-Only Mode)"
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

    def get_break_countdown(self):
        """Return a dict with next break countdown or break remaining.

        Returns None if humanization is disabled or scheduling not available.
        Shape: {'on_break': bool, 'seconds': float}
        """
        try:
            if not bool(self.config_manager.get('humanize_on', True)):
                return None
            mgr = getattr(self, '_instance_manager', None)
            if not mgr:
                return None
            now = time.time()
            if mgr.get('break_active', False):
                sec = max(0.0, float(mgr.get('break_until', 0.0)) - now)
                return {'on_break': True, 'seconds': sec}
            nbt = mgr.get('next_break_time')
            if nbt is None:
                return None
            return {'on_break': False, 'seconds': max(0.0, float(nbt) - now)}
        except Exception:
            return None

    def get_aggro_remaining_seconds(self) -> Optional[float]:
        """Return seconds remaining until next aggro click in Instance Mode.

        Returns None if Instance Mode is disabled or schedule unknown.
        """
        try:
            if not bool(self.config_manager.get('instance_only_mode', False)):
                return None
            # Determine next time from instance manager if available
            mgr = getattr(self, '_instance_manager', None)
            now = time.time()
            # Compute interval from config
            try:
                interval_min = float(self.config_manager.get('instance_aggro_interval_min', 15.0))
            except Exception:
                interval_min = 15.0
            interval_s = max(10.0, interval_min * 60.0)

            if mgr is None:
                # Not yet initialized; pretend full interval remaining
                return interval_s
            nxt = mgr.get('next_aggro_time')
            if nxt is None:
                return interval_s
            return max(0.0, nxt - now)
        except Exception:
            return None
    
    def _main_loop(self):
        """Main bot loop"""
        logger.info("Main bot loop started")
        
        # Initialize instance manager if needed
        self._instance_manager = None
        
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
                
                # Check if Instance-Only Mode is enabled
                instance_only_mode = self.config_manager.get('instance_only_mode', False)
                multi_monster_enabled = bool(self.config_manager.get('multi_monster_mode_enabled', False))
                one_tele_enabled = bool(self.config_manager.get('one_tele_one_kill_enabled', False))

                # 1 Tele 1 Kill override takes highest priority
                if one_tele_enabled:
                    try:
                        base_roi = self.detection_engine.roi_manager.get_active_roi()
                        if not base_roi:
                            time.sleep(max(0.01, float(self.config_manager.get('scan_interval', 0.2))))
                            continue
                        # Use the standard detection cycle (SEARCH ROI -> TILE -> MONSTER by colors)
                        result = self.detection_engine.detect_cycle()
                        in_combat = bool(result.get('in_combat', False))
                        hp_seen = bool(result.get('hp_seen', False))
                        monsters = result.get('monsters', [])
                        roi = result.get('roi', {})
                        # Current timestamp for deadline checks
                        now_ts = time.time()

                        # If a post-combat teleport deadline is set and reached, perform teleport immediately (takes precedence)
                        try:
                            deadline = float(self._one_tele_runtime.get('hp_verify_deadline', 0.0))
                        except Exception:
                            deadline = 0.0
                        if deadline > 0.0 and now_ts >= deadline:
                            ok = False
                            abs_x = abs_y = 0
                            # Prefer ROI if enabled
                            try:
                                use_roi = bool(self.config_manager.get('one_tele_use_roi', False))
                                roi = self.config_manager.get_roi('one_tele_one_kill_teleport_roi') if use_roi else None
                            except Exception:
                                roi = None
                            if self.action_manager and self.action_manager.mouse_controller:
                                try:
                                    if roi is not None:
                                        from ..detection.capture import CaptureService  # type: ignore
                                        import random as _rand
                                        bbox = CaptureService().get_window_bbox()
                                        mode = str(getattr(roi, 'mode', 'absolute')).lower()
                                        if mode == 'percent':
                                            L = int(bbox['left'] + float(roi.left) * bbox['width'])
                                            T = int(bbox['top'] + float(roi.top) * bbox['height'])
                                            W = int(max(1, float(roi.width) * bbox['width']))
                                            H = int(max(1, float(roi.height) * bbox['height']))
                                        elif mode == 'relative':
                                            L = int(bbox['left'] + int(roi.left))
                                            T = int(bbox['top'] + int(roi.top))
                                            W = int(roi.width)
                                            H = int(roi.height)
                                        else:
                                            L = int(roi.left); T = int(roi.top); W = int(roi.width); H = int(roi.height)
                                        abs_x = _rand.randint(L, L + max(0, W - 1))
                                        abs_y = _rand.randint(T, T + max(0, H - 1))
                                    else:
                                        coord = self.config_manager.get_coordinate('one_tele_one_kill_teleport_xy')
                                        if coord is not None:
                                            abs_x, abs_y = int(coord.x), int(coord.y)
                                            try:
                                                from ..detection.capture import CaptureService  # type: ignore
                                                bbox = CaptureService().get_window_bbox()
                                                if 0 <= int(coord.x) <= int(bbox.get('width', 0)) and 0 <= int(coord.y) <= int(bbox.get('height', 0)):
                                                    abs_x = int(bbox.get('left', 0)) + int(coord.x)
                                                    abs_y = int(bbox.get('top', 0)) + int(coord.y)
                                            except Exception:
                                                pass
                                    if abs_x or abs_y:
                                        ok = self.action_manager.mouse_controller.move_and_click(abs_x, abs_y, enforce_guard=False, clamp_to_search_roi=False)
                                except Exception as e:
                                    logger.error(f"1T1K teleport click (deadline) failed: {e}")
                            if ok:
                                self.event_system.publish(EventType.TELEPORT_USED, {'location': '1T1K', 'coordinate': (abs_x, abs_y), 'emergency': False})
                                logger.info(f"1T1K: Teleport clicked at ({abs_x}, {abs_y}) after HP timeout")
                                # Optional post-teleport hotkey
                                try:
                                    if bool(self.config_manager.get('one_tele_post_hotkey_enabled', False)) and self.action_manager and self.action_manager.keyboard_controller:
                                        hk = str(self.config_manager.get('one_tele_post_hotkey', '2'))
                                        delay = float(self.config_manager.get('one_tele_post_hotkey_delay', 0.15))
                                        time.sleep(max(0.0, delay))
                                        if '+' in hk:
                                            self.action_manager.keyboard_controller.press_hotkey(hk)
                                        else:
                                            self.action_manager.keyboard_controller.press_key(hk)
                                        logger.info(f"1T1K: Post-teleport hotkey '{hk}' sent")
                                except Exception as e:
                                    logger.warning(f"1T1K: Failed to send post-teleport hotkey: {e}")
                            else:
                                logger.warning("1T1K: Teleport click failed or action manager unavailable")
                            # Reset and settle
                            self._one_tele_runtime['hp_verify_deadline'] = 0.0
                            self._one_tele_runtime['was_in_combat'] = False
                            self._one_tele_runtime['post_combat_waiting'] = False
                            time.sleep(0.6)
                            continue

                        # If HP bar is seen, clear verification timer and idle (do not rely on in_combat alone)
                        if hp_seen:
                            # If we're in post-combat waiting state, do NOT clear the deadline; we're committed to teleport after timeout
                            if not bool(self._one_tele_runtime.get('post_combat_waiting', False)):
                                if float(self._one_tele_runtime.get('hp_verify_deadline', 0.0)) > 0.0:
                                    logger.info("1T1K: HP bar seen -> clearing verify timer")
                                self._one_tele_runtime['hp_verify_deadline'] = 0.0
                                # Track that we are in combat; we'll arm post-combat on disappearance
                                self._one_tele_runtime['was_in_combat'] = True
                            time.sleep(max(0.01, float(self.config_manager.get('scan_interval', 0.2))))
                            continue

                        # now_ts already captured above for consistency
                        was_in_combat = bool(self._one_tele_runtime.get('was_in_combat', False))
                        # If combat just ended (HP bar disappeared), arm the verify timer instead of immediate teleport
                        if was_in_combat and not hp_seen:
                            try:
                                tmo = float(self.config_manager.get('one_tele_one_kill_hp_timeout_s', 5.0))
                            except Exception:
                                tmo = 5.0
                            deadline = float(self._one_tele_runtime.get('hp_verify_deadline', 0.0))
                            if deadline <= 0.0:
                                self._one_tele_runtime['hp_verify_deadline'] = time.time() + max(0.5, tmo)
                                logger.info(f"1T1K: HP bar disappeared; arming post-combat teleport in {tmo:.1f}s")
                            # Enter post-combat waiting state so timer won't be cleared by transient HP detections
                            self._one_tele_runtime['post_combat_waiting'] = True
                            # Do not teleport immediately; wait for deadline branch to handle it
                            time.sleep(max(0.01, float(self.config_manager.get('scan_interval', 0.2))))
                            continue

                        deadline = float(self._one_tele_runtime.get('hp_verify_deadline', 0.0))
                        if deadline > 0.0 and now_ts >= deadline:
                            # Verification failed -> teleport (ROI if enabled)
                            ok = False
                            abs_x = abs_y = 0
                            try:
                                use_roi = bool(self.config_manager.get('one_tele_use_roi', False))
                                roi = self.config_manager.get_roi('one_tele_one_kill_teleport_roi') if use_roi else None
                            except Exception:
                                roi = None
                            if self.action_manager and self.action_manager.mouse_controller:
                                try:
                                    if roi is not None:
                                        from ..detection.capture import CaptureService  # type: ignore
                                        import random as _rand
                                        bbox = CaptureService().get_window_bbox()
                                        mode = str(getattr(roi, 'mode', 'absolute')).lower()
                                        if mode == 'percent':
                                            L = int(bbox['left'] + float(roi.left) * bbox['width'])
                                            T = int(bbox['top'] + float(roi.top) * bbox['height'])
                                            W = int(max(1, float(roi.width) * bbox['width']))
                                            H = int(max(1, float(roi.height) * bbox['height']))
                                        elif mode == 'relative':
                                            L = int(bbox['left'] + int(roi.left))
                                            T = int(bbox['top'] + int(roi.top))
                                            W = int(roi.width)
                                            H = int(roi.height)
                                        else:
                                            L = int(roi.left); T = int(roi.top); W = int(roi.width); H = int(roi.height)
                                        abs_x = _rand.randint(L, L + max(0, W - 1))
                                        abs_y = _rand.randint(T, T + max(0, H - 1))
                                    else:
                                        coord = self.config_manager.get_coordinate('one_tele_one_kill_teleport_xy')
                                        if coord is None:
                                            logger.warning("1T1K: Teleport target not set; cannot teleport. Disabling verify window.")
                                            self._one_tele_runtime['hp_verify_deadline'] = 0.0
                                        else:
                                            abs_x, abs_y = int(coord.x), int(coord.y)
                                            try:
                                                from ..detection.capture import CaptureService  # type: ignore
                                                bbox = CaptureService().get_window_bbox()
                                                if 0 <= int(coord.x) <= int(bbox.get('width', 0)) and 0 <= int(coord.y) <= int(bbox.get('height', 0)):
                                                    abs_x = int(bbox.get('left', 0)) + int(coord.x)
                                                    abs_y = int(bbox.get('top', 0)) + int(coord.y)
                                            except Exception:
                                                pass
                                    if abs_x or abs_y:
                                        ok = self.action_manager.mouse_controller.move_and_click(abs_x, abs_y, enforce_guard=False, clamp_to_search_roi=False)
                                except Exception as e:
                                    logger.error(f"1T1K teleport click failed: {e}")
                            if ok:
                                self.event_system.publish(EventType.TELEPORT_USED, {'location': '1T1K', 'coordinate': (abs_x, abs_y), 'emergency': False})
                                logger.info(f"1T1K: Teleport clicked at ({abs_x}, {abs_y}) after HP timeout")
                                # Optional post-teleport hotkey
                                try:
                                    if bool(self.config_manager.get('one_tele_post_hotkey_enabled', False)) and self.action_manager and self.action_manager.keyboard_controller:
                                        hk = str(self.config_manager.get('one_tele_post_hotkey', '2'))
                                        delay = float(self.config_manager.get('one_tele_post_hotkey_delay', 0.15))
                                        time.sleep(max(0.0, delay))
                                        if '+' in hk:
                                            self.action_manager.keyboard_controller.press_hotkey(hk)
                                        else:
                                            self.action_manager.keyboard_controller.press_key(hk)
                                        logger.info(f"1T1K: Post-teleport hotkey '{hk}' sent")
                                except Exception as e:
                                    logger.warning(f"1T1K: Failed to send post-teleport hotkey: {e}")
                            else:
                                logger.warning("1T1K: Teleport click failed or action manager unavailable")
                                # Reset timer regardless to avoid loops
                                self._one_tele_runtime['hp_verify_deadline'] = 0.0
                                self._one_tele_runtime['was_in_combat'] = False
                                self._one_tele_runtime['post_combat_waiting'] = False
                                # Small settle pause after teleport
                                time.sleep(0.6)
                                continue

                        # Not in combat: if a deadline is armed, wait without clicking to avoid random clicks
                        try:
                            deadline = float(self._one_tele_runtime.get('hp_verify_deadline', 0.0))
                        except Exception:
                            deadline = 0.0
                        if deadline > 0.0:
                            # Waiting for post-combat teleport; do not click monsters
                            time.sleep(max(0.01, float(self.config_manager.get('scan_interval', 0.2))))
                            continue

                        # No deadline active -> attempt attack if a monster is present
                        if monsters:
                            try:
                                # Helper for squared distance
                                def _dist2(p, q):
                                    return (float(p[0]) - float(q[0]))**2 + (float(p[1]) - float(q[1]))**2

                                # Compute ROI center (used only for fallback + logging)
                                center_x = roi['left'] + roi['width'] // 2 if roi else 0
                                center_y = roi['top'] + roi['height'] // 2 if roi else 0

                                # Keep low-confidence stats for logging, but do NOT use them for selection
                                lowconf_enabled = bool(self.config_manager.get('low_confidence_click_enabled', True))
                                area_thr = float(self.config_manager.get('low_confidence_area_threshold', 220.0))
                                min_count = int(self.config_manager.get('low_conf_min_count', 3))
                                largest_area = 0.0
                                for m in monsters:
                                    try:
                                        a = float(m.get('area', 0.0))
                                        if a > largest_area:
                                            largest_area = a
                                    except Exception:
                                        pass
                                is_lowconf = lowconf_enabled and (len(monsters) < min_count or largest_area < area_thr)

                                # 1T1K selection override: pick the monster closest to its tile center when available
                                with_tile = [m for m in monsters if m.get('tile_center') is not None]
                                target = None
                                if with_tile:
                                    try:
                                        target = min(with_tile, key=lambda m: _dist2(m['position'], m['tile_center']))
                                    except Exception:
                                        target = None
                                # Fallbacks when tile center is missing for all
                                if target is None:
                                    # previous heuristic fallback: nearest to ROI center (ignore sticky/area for simplicity)
                                    try:
                                        target = min(monsters, key=lambda m: _dist2(m['position'], (center_x, center_y)))
                                    except Exception:
                                        target = monsters[0]

                                x, y = target['position']

                                # Respect basic cooldown
                                now_click = time.time()
                                if (now_click - self._last_monster_click_time) >= float(self.config_manager.get('min_monster_click_cooldown_s', 0.8)):
                                    if self.action_manager and self.action_manager.mouse_controller.move_and_click(x, y, button='left', clicks=1, enforce_guard=False):
                                        self._last_monster_click_time = now_click
                                        self._last_monster_click_pos = (x, y)
                                        # Arm HP verification timer
                                        try:
                                            tmo = float(self.config_manager.get('one_tele_one_kill_hp_timeout_s', 5.0))
                                        except Exception:
                                            tmo = 5.0
                                        self._one_tele_runtime['hp_verify_deadline'] = time.time() + max(0.5, tmo)
                                        logger.info(f"1T1K: Clicked monster at ({x},{y}); waiting up to {tmo:.1f}s for HP bar before teleport (lowconf={is_lowconf}, area_max={largest_area:.1f}, strategy=nearest_tile)")
                                        # Optional small sleep to allow target selection
                                        time.sleep(self.config_manager.get('click_after_found_sleep', 0.3))
                                    else:
                                        logger.debug("1T1K: Monster click suppressed by cooldown or controller not ready")
                            except Exception as e:
                                logger.error(f"1T1K attack error: {e}")

                        time.sleep(max(0.01, float(self.config_manager.get('scan_interval', 0.2))))
                        continue
                    except Exception as e:
                        logger.error(f"1T1K mode cycle error: {e}")
                        # if failure, fall through to other modes

                # If Multi Monster Mode enabled, ensure module initialized and run its cycle instead of normal detection loop
                if multi_monster_enabled:
                    try:
                        if self._multi_monster_detector is None and self.capture_service is not None:
                            from ..detection.multi_monster_detector import MultiMonsterDetector
                            self._multi_monster_detector = MultiMonsterDetector(self.config_manager, self.capture_service)
                            logger.info("MultiMonsterDetector initialized")
                        if self._multi_monster_module is None and self._multi_monster_detector is not None and self.action_manager is not None:
                            from ..modules.multi_monster import MultiMonsterModule
                            self._multi_monster_module = MultiMonsterModule(
                                self.config_manager,
                                self.action_manager.mouse_controller,
                                self.action_manager.keyboard_controller,
                                self._multi_monster_detector
                            )
                            logger.info("MultiMonsterModule initialized")
                        # If module is still unavailable, fall back to normal detection
                        if self._multi_monster_module is None:
                            time.sleep(max(0.01, float(self.config_manager.get('scan_interval', 0.2))))
                            continue
                        # Refresh config each cycle (cheap) to catch panel changes
                        self._multi_monster_module.update_config()
                        # Acquire base ROI (search window / active ROI) similar to normal loop
                        base_roi = self.detection_engine.roi_manager.get_active_roi() if self.detection_engine else None
                        if base_roi and self.capture_service is not None and self._multi_monster_module is not None:
                            frame_mm = self.capture_service.capture_region(base_roi)
                            mm_result = self._multi_monster_module.process_cycle(frame_mm, base_roi)
                            # Lightweight logging (INFO for visibility)
                            if mm_result.get('action'):
                                reason = mm_result.get('reason')
                                if reason:
                                    logger.info(
                                        "MM: action=%s monsters=%s req=%s in_combat=%s reason=%s",
                                        mm_result.get('action'),
                                        mm_result.get('monsters'),
                                        mm_result.get('required_style'),
                                        mm_result.get('in_combat'),
                                        reason
                                    )
                                else:
                                    logger.info(
                                        "MM: action=%s monsters=%s req=%s in_combat=%s", 
                                        mm_result.get('action'),
                                        mm_result.get('monsters'),
                                        mm_result.get('required_style'),
                                        mm_result.get('in_combat')
                                    )
                        # Sleep per scan interval when in multi mode
                        time.sleep(max(0.01, float(self.config_manager.get('scan_interval', 0.2))))
                        continue  # Skip normal detection path
                    except Exception as e:
                        logger.error(f"Multi Monster Mode cycle error: {e}")
                        # Fall through to normal detection if failure
                
                cycle_start = time.time()
                result = self.detection_engine.detect_cycle()
                
                # Handle Instance-Only Mode
                if instance_only_mode:
                    self._process_instance_only_mode(result)
                    continue
                
                # Normal mode processing
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

                # Update combat timers based on state transitions (HP/in_combat)
                now_ts2 = time.time()
                was_in = bool(self._combat_timers.get('was_in_combat', False))
                if was_in and not in_combat:
                    # Combat ended -> start post-combat cooldown in [min, max]
                    try:
                        import random as _rand
                        min_s = float(self.config_manager.get('post_combat_delay_min_s', 1.0))
                        max_s = float(self.config_manager.get('post_combat_delay_max_s', 3.0))
                        if max_s < min_s:
                            max_s = min_s
                        wait_s = min_s if max_s == min_s else (min_s + (max_s - min_s) * _rand.random())
                        self._combat_timers['post_combat_cooldown_until'] = now_ts2 + max(0.0, wait_s)
                        logger.info(f"Post-combat cooldown started for {wait_s:.1f}s")
                        # Reset last click reference so min-distance gate doesn't suppress the first re-attack
                        self._last_monster_click_pos = None
                    except Exception:
                        # Fallback: use min only
                        min_s = float(self.config_manager.get('post_combat_delay_min_s', 1.0))
                        self._combat_timers['post_combat_cooldown_until'] = now_ts2 + max(0.0, min_s)
                # Track last seen state
                self._combat_timers['was_in_combat'] = bool(in_combat)
                
                # If we recently attacked but HP bar isn't visible yet, and the feature is enabled,
                # attempt a one-time weapon/style click retry (using detected style) before attacking again.
                # Legacy combat_style_enforce flow disabled; Multi Monster Mode owns weapon switching/decision
                if False and (not in_combat) and (not hp_seen) and bool(self.config_manager.get('combat_style_enforce', False)):
                    now_chk = time.time()
                    # Verification window active
                    if 0.0 < self._post_attack_verify_deadline and now_chk <= self._post_attack_verify_deadline:
                        if not self._post_attack_retry_done:
                            try:
                                if self.detection_engine is not None:
                                    logger.info("Post-attack verify window active; attempting one-time weapon/style retry")
                                    # Detect current style, then try switching to its weapon/style color again
                                    cur_style = self.detection_engine.detect_combat_style()
                                    if not cur_style:
                                        logger.info("Post-attack retry: style not detected in Style ROI; will continue to monitor")
                                    else:
                                        pt = self.detection_engine.detect_weapon_for_style(cur_style)
                                        if pt is not None and self.action_manager:
                                            logger.info(f"Post-attack retry: switching for style '{cur_style}' at ({pt[0]}, {pt[1]})")
                                            self.action_manager.mouse_controller.move_and_click(pt[0], pt[1])
                                            # Allow immediate re-attack by clearing attack grace
                                            self._combat_timers['attack_grace_until'] = time.time()
                                            self._post_attack_retry_done = True
                                            time.sleep(0.15)
                                        else:
                                            logger.info("Post-attack retry: linked weapon/style color not visible in Weapon ROI")
                            except Exception as e:
                                logger.debug(f"Post-attack retry skipped due to error: {e}")
                    # If the window expired, clear state and log
                    elif self._post_attack_verify_deadline > 0.0 and now_chk > self._post_attack_verify_deadline:
                        logger.info("Post-attack verify window expired without HP bar; proceeding with normal cycle")
                        self._post_attack_verify_deadline = 0.0
                        self._post_attack_retry_done = False

                # Click target monster only when not in combat (HP bar not visible)
                if (not in_combat) and monsters:
                    # Optional: enforce combat style before attacking using Weapon ROI
                    try:
                        if False and bool(self.config_manager.get('combat_style_enforce', False)) and self.detection_engine is not None:
                            # Simple cooldown to avoid spamming style clicks
                            if not hasattr(self, '_style_enforce_until'):
                                self._style_enforce_until = 0.0  # type: ignore[attr-defined]
                            now_enf = time.time()
                            if now_enf >= float(self._style_enforce_until):
                                # Detect current style; if detected, search Weapon ROI for the linked weapon color and click once
                                current_style = self.detection_engine.detect_combat_style() or None
                                if current_style is None:
                                    logger.info("Combat Style: enabled - style not detected in Style ROI; skipping weapon switch this cycle")
                                else:
                                    logger.info(f"Combat Style: enabled - detected style '{current_style}'")
                                    pt = self.detection_engine.detect_weapon_for_style(current_style)
                                    if pt is not None and self.action_manager:
                                        logger.info(f"Combat Style: switching at ({pt[0]}, {pt[1]}) for style '{current_style}'")
                                        ok = self.action_manager.mouse_controller.move_and_click(pt[0], pt[1])
                                        if ok:
                                            # Small grace before attacking to let the style settle
                                            self._style_enforce_until = time.time() + 1.0
                                            time.sleep(0.15)
                                        else:
                                            logger.info("Combat Style: switch click failed (mouse controller returned False)")
                                    else:
                                        # Weapon color not visible in ROI -> attack without switching
                                        logger.info("Combat Style: linked weapon/style color not visible in Weapon ROI; proceeding to attack")
                            else:
                                rem = max(0.0, float(self._style_enforce_until) - now_enf)
                                logger.info(f"Combat Style: cooldown active ({rem:.1f}s); skipping enforcement this cycle")
                    except Exception as e:
                        logger.debug(f"Weapon ROI style enforce skipped due to error: {e}")
                    # Respect attack grace (immediately after an attack) and post-combat cooldown
                    now_click2 = time.time()
                    attack_grace_until = float(self._combat_timers.get('attack_grace_until', 0.0))
                    post_cc_until = float(self._combat_timers.get('post_combat_cooldown_until', 0.0))
                    if now_click2 < attack_grace_until:
                        rem = max(0.0, attack_grace_until - now_click2)
                        logger.info(f"Attack grace active: {rem:.1f}s remaining; skipping target click")
                        time.sleep(max(0.01, float(self.config_manager.get('scan_interval', 0.2))))
                        continue
                    if now_click2 < post_cc_until:
                        rem = max(0.0, post_cc_until - now_click2)
                        logger.info(f"Post-combat cooldown: {rem:.1f}s remaining; skipping target click")
                        time.sleep(max(0.01, float(self.config_manager.get('scan_interval', 0.2))))
                        continue
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
                        min_dist_enabled = bool(self.config_manager.get('min_monster_click_distance_enabled', True))
                        min_dist = int(self.config_manager.get('min_monster_click_distance_px', 12))
                        far_enough = True
                        if min_dist_enabled and self._last_monster_click_pos is not None:
                            dx = x - self._last_monster_click_pos[0]
                            dy = y - self._last_monster_click_pos[1]
                            far_enough = (dx*dx + dy*dy) ** 0.5 >= min_dist

                        if (now - self._last_monster_click_time) >= min_cd and far_enough:
                            if self.action_manager:
                                # For monster attacks, rely on our own Attack Grace timer and bypass the mouse anti-overclick guard
                                # to avoid first-click suppression immediately after startup.
                                if self.action_manager.mouse_controller.move_and_click(
                                    x, y,
                                    button='left',
                                    clicks=1,
                                    enforce_guard=False,  # state-managed attack grace handles pacing
                                    clamp_to_search_roi=True
                                ):
                                    self._last_monster_click_time = now
                                    self._last_monster_click_pos = (x, y)
                                    # After ATTACK, apply Attack Grace wait
                                    try:
                                        # Attack grace: short pause after an attack before next attack attempt
                                        # Do NOT couple this to post-combat cooldown; use a dedicated setting with a sane default
                                        grace_s = float(self.config_manager.get('attack_grace_s', 0.6))
                                    except Exception:
                                        grace_s = 0.6
                                    self._combat_timers['attack_grace_until'] = time.time() + max(0.0, grace_s)
                                    # Arm post-attack verification window (HP bar should appear within 5s)
                                    if bool(self.config_manager.get('combat_style_enforce', False)):
                                        self._post_attack_verify_deadline = time.time() + 5.0
                                        self._post_attack_retry_done = False
                                        logger.info("Post-attack verify window armed for 5.0s (waiting for HP bar)")
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
                                    logger.debug("Monster click suppressed by controller (possibly cooldown); will retry next cycle")
                        else:
                            # Cooldown or too close; emit detailed reason
                            try:
                                rem_cd = max(0.0, min_cd - (now - self._last_monster_click_time))
                            except Exception:
                                rem_cd = 0.0
                            if min_dist_enabled and not far_enough:
                                try:
                                    dx = x - (self._last_monster_click_pos[0] if self._last_monster_click_pos else x)
                                    dy = y - (self._last_monster_click_pos[1] if self._last_monster_click_pos else y)
                                    dist = (dx*dx + dy*dy) ** 0.5
                                except Exception:
                                    dist = 0.0
                                logger.info(f"Monster click skipped: min-distance gate (dist={dist:.1f}px < min={min_dist}px)")
                            elif rem_cd > 0.0:
                                logger.info(f"Monster click skipped: cooldown gate (remaining={rem_cd:.1f}s >= min={min_cd:.1f}s)")
                            else:
                                logger.info("Monster click skipped due to gating (unknown reason)")
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

    def _process_instance_only_mode(self, result):
        """
        Process Instance-Only Mode detection results
        
        Args:
            result: Detection result from instance_only_detector
        """
        # Initialize instance manager if needed
        if not hasattr(self, '_instance_manager') or self._instance_manager is None:
            self._instance_manager = {
                'last_teleport_time': 0,
                'teleport_cooldown': 5.0,  # Cooldown between teleport attempts
                # Post-teleport wait/retry state
                'post_teleport_active': False,
                'post_teleport_wait_until': 0.0,
                'post_teleport_retry_count': 0,
                # Aggro state
                'next_aggro_time': None,
                'aggro_timer_phase': 'interval',  # 'start_delay' or 'interval'
                # Humanization: simple scheduled breaks
                'next_break_time': None,
                'break_active': False,
                'break_until': 0.0,
                # Post-aggro wait: observe HP bar/in_combat after clicking aggro
                'post_aggro_active': False,
                'post_aggro_wait_until': 0.0,
                # Aggro click cooldown
                'last_aggro_click_time': 0.0,
                # Legacy timer: ensure an initial click as soon as script starts
                'legacy_initial_clicked': False,
            }

        # Extract result data
        in_combat = result.get('in_combat', False)
        hp_seen = result.get('hp_seen', False)
        # We no longer rely on visual aggro detection; use timer-based logic instead
        instance_empty = result.get('instance_empty', False)

        # Log status (throttled to avoid log spam)
        try:
            status_interval = float(self.config_manager.get('instance_status_log_interval', 1.0))
        except Exception:
            status_interval = 1.0
        now_ts = time.time()
        last_status = self._instance_manager.get('last_status_log_time', 0.0)
        if now_ts - last_status >= max(0.1, status_interval):
            logger.info(f"Instance-Only Mode - HP bar seen: {'Y' if hp_seen else 'N'}; InCombat: {in_combat}")
            logger.info(f"Instance-Only Mode - Instance empty: {'Y' if instance_empty else 'N'}")
            self._instance_manager['last_status_log_time'] = now_ts

        # Humanization: scheduled breaks (applies only when enabled)
        try:
            humanize_on = bool(self.config_manager.get('humanize_on', True))
            break_every_s = float(self.config_manager.get('break_every_s', 0.0))
            break_duration_s = float(self.config_manager.get('break_duration_s', 0.0))
        except Exception:
            humanize_on, break_every_s, break_duration_s = True, 0.0, 0.0

        now_for_breaks = time.time()
        mgr = self._instance_manager
        if humanize_on and break_every_s > 0 and break_duration_s > 0:
            # Jitter settings from config
            try:
                jitter_on = bool(self.config_manager.get('humanize_jitter_enabled', True))
            except Exception:
                jitter_on = True
            try:
                jitter_pct = float(self.config_manager.get('humanize_jitter_percent', 10.0))
            except Exception:
                jitter_pct = 10.0
            jitter_pct = max(0.0, min(50.0, jitter_pct))  # clamp 0..50
            jitter_span = (jitter_pct / 100.0) * 2.0  # e.g., 10% -> span 0.2 around 1.0

            # Initialize next break if needed (with randomized interval and duration hint)
            if mgr.get('next_break_time') is None:
                try:
                    import random as _rand
                    if jitter_on and jitter_span > 0:
                        rand_factor_every = 1.0 + (jitter_span * (_rand.random() - 0.5))
                        rand_factor_duration = 1.0 + (jitter_span * (_rand.random() - 0.5))
                    else:
                        rand_factor_every = 1.0
                        rand_factor_duration = 1.0
                    eff_break_every_s = max(1.0, break_every_s * rand_factor_every)
                    eff_break_duration_s = max(0.5, break_duration_s * rand_factor_duration)
                except Exception:
                    eff_break_every_s = break_every_s
                    eff_break_duration_s = break_duration_s
                mgr['next_break_time'] = now_for_breaks + eff_break_every_s
                logger.info(
                    f"Humanization: scheduling first break in {eff_break_every_s:.1f}s (duration {eff_break_duration_s:.1f}s)"
                )

            # If a break is currently active, continue to wait and skip actions
            if mgr.get('break_active', False):
                remaining = max(0.0, float(mgr.get('break_until', 0.0)) - now_for_breaks)
                if remaining > 0:
                    # Log occasionally (throttled by status log interval above)
                    logger.info(f"Humanization: on break, {remaining:.1f}s remaining")
                    return
                else:
                    # End break and schedule the next one with randomized interval
                    try:
                        import random as _rand
                        if jitter_on and jitter_span > 0:
                            rand_factor_every = 1.0 + (jitter_span * (_rand.random() - 0.5))
                        else:
                            rand_factor_every = 1.0
                        eff_break_every_s = max(1.0, break_every_s * rand_factor_every)
                    except Exception:
                        eff_break_every_s = break_every_s
                    mgr['break_active'] = False
                    mgr['break_until'] = 0.0
                    mgr['next_break_time'] = time.time() + eff_break_every_s
                    logger.info("Humanization: break ended; scheduling next break; resuming aggro bar checks")

            # Start a new break when due
            nbt = mgr.get('next_break_time')
            if nbt is not None and now_for_breaks >= float(nbt):
                # Randomize duration on each break
                try:
                    import random as _rand
                    if jitter_on and jitter_span > 0:
                        rand_factor_duration = 1.0 + (jitter_span * (_rand.random() - 0.5))
                    else:
                        rand_factor_duration = 1.0
                    eff_break_duration_s = max(0.5, break_duration_s * rand_factor_duration)
                except Exception:
                    eff_break_duration_s = break_duration_s
                mgr['break_active'] = True
                mgr['break_until'] = now_for_breaks + eff_break_duration_s
                logger.info(f"Humanization: starting break for {eff_break_duration_s:.1f}s")
                return

        # Ensure aggro stays active based on selected strategy: 'bar', 'timer', or 'hybrid'
        mgr = self._instance_manager
        detector = None
        try:
            if self.detection_engine is not None:
                detector = self.detection_engine.instance_only_detector
        except Exception:
            detector = None
        if detector is not None and not mgr.get('post_aggro_active', False) and not mgr.get('break_active', False) and not mgr.get('post_teleport_active', False):
            # Determine strategy
            try:
                strategy = str(self.config_manager.get('instance_aggro_strategy', 'bar')).lower()
            except Exception:
                strategy = 'bar'

            # Legacy Timer: initial click immediately when script starts
            if strategy == 'timer' and not bool(mgr.get('legacy_initial_clicked', False)) and self.action_manager:
                potion = detector.get_aggro_potion_location() if detector is not None else None
                # Convert potion coordinate to absolute
                potion_abs = None
                try:
                    if potion is not None:
                        from ..detection.capture import CaptureService  # type: ignore
                        bbox = CaptureService().get_window_bbox()
                        potion_abs = (int(bbox['left']) + int(potion.x), int(bbox['top']) + int(potion.y))
                except Exception:
                    potion_abs = None
                if potion is not None and potion_abs is not None:
                    logger.info(f"Legacy timer: initial aggro click at ({potion_abs[0]}, {potion_abs[1]})")
                    if self.action_manager.mouse_controller.move_and_click(potion_abs[0], potion_abs[1], enforce_guard=False, clamp_to_search_roi=False):
                        self.event_system.publish(EventType.AGGRO_USED, {'position': (potion_abs[0], potion_abs[1])})
                        # Post-aggro wait
                        try:
                            wait_s = float(self.config_manager.get('instance_post_aggro_hp_wait', 8.0))
                        except Exception:
                            wait_s = 8.0
                        mgr['post_aggro_active'] = True
                        mgr['post_aggro_wait_until'] = time.time() + max(0.5, wait_s)
                        mgr['last_aggro_click_time'] = time.time()
                        mgr['legacy_initial_clicked'] = True
                        # Schedule next: start delay first, then interval
                        try:
                            start_delay_s = float(self.config_manager.get('instance_aggro_start_delay_s', 5.0))
                        except Exception:
                            start_delay_s = 5.0
                        if start_delay_s > 0.0:
                            mgr['aggro_timer_phase'] = 'start_delay'
                            mgr['next_aggro_time'] = time.time() + start_delay_s
                            try:
                                self.config_manager.set('instance_aggro_timer_phase', 'start_delay')
                                self.config_manager.set('instance_next_aggro_time_epoch', float(mgr['next_aggro_time']))
                            except Exception:
                                pass
                            logger.info(f"Aggro timer: start delay scheduled in {start_delay_s:.1f}s")
                        else:
                            # schedule interval
                            try:
                                interval_min = float(self.config_manager.get('instance_aggro_interval_min', 15.0))
                            except Exception:
                                interval_min = 15.0
                            try:
                                jitter_on = bool(self.config_manager.get('instance_aggro_jitter_enabled', True))
                            except Exception:
                                jitter_on = True
                            try:
                                jitter_pct = float(self.config_manager.get('instance_aggro_jitter_percent', 10.0))
                            except Exception:
                                jitter_pct = 10.0
                            jitter_pct = max(0.0, min(50.0, jitter_pct))
                            eff_interval_s = max(1.0, interval_min * 60.0)
                            try:
                                import random as _rand
                                if jitter_on and jitter_pct > 0.0:
                                    span = (jitter_pct / 100.0) * 2.0
                                    factor = 1.0 + (span * (_rand.random() - 0.5))
                                else:
                                    factor = 1.0
                                eff_interval_s *= factor
                            except Exception:
                                pass
                            mgr['aggro_timer_phase'] = 'interval'
                            mgr['next_aggro_time'] = time.time() + eff_interval_s
                            try:
                                self.config_manager.set('instance_aggro_timer_phase', 'interval')
                                self.config_manager.set('instance_next_aggro_time_epoch', float(mgr['next_aggro_time']))
                            except Exception:
                                pass
                            logger.info(f"Aggro timer: next click scheduled in {eff_interval_s:.1f}s")
                        logger.info(f"Waiting up to {wait_s:.1f}s for HP bar after aggro click.")
                        return

            # Evaluate aggro bar only if strategy requires it
            aggro_bar_ok = True  # assume OK unless we check and find absent
            if strategy in ('bar', 'hybrid'):
                try:
                    aggro_bar_ok = bool(detector.detect_aggro_bar_present())
                except Exception:
                    aggro_bar_ok = False

            # Manage legacy timer schedule if strategy includes timer
            now_click = time.time()
            timer_due = False
            if strategy in ('timer', 'hybrid'):
                # External reset trigger from UI
                try:
                    if bool(self.config_manager.get('instance_aggro_timer_reset_now', False)):
                        self.config_manager.set('instance_aggro_timer_reset_now', False)
                        mgr['next_aggro_time'] = None
                        mgr['aggro_timer_phase'] = 'start_delay'
                        logger.info("Aggro timer reset requested: will start with Start Delay phase")
                except Exception:
                    pass
                # Ensure next_aggro_time is scheduled
                if mgr.get('next_aggro_time') is None:
                    # Determine whether to start with a start delay or go straight into interval
                    try:
                        start_delay_s = float(self.config_manager.get('instance_aggro_start_delay_s', 5.0))
                    except Exception:
                        start_delay_s = 5.0
                    if start_delay_s > 0.0:
                        mgr['aggro_timer_phase'] = 'start_delay'
                        mgr['next_aggro_time'] = now_click + start_delay_s
                        try:
                            self.config_manager.set('instance_aggro_timer_phase', 'start_delay')
                            self.config_manager.set('instance_next_aggro_time_epoch', float(mgr['next_aggro_time']))
                        except Exception:
                            pass
                        logger.info(f"Aggro timer: start delay scheduled in {start_delay_s:.1f}s")
                    else:
                        mgr['aggro_timer_phase'] = 'interval'
                        try:
                            interval_min = float(self.config_manager.get('instance_aggro_interval_min', 15.0))
                        except Exception:
                            interval_min = 15.0
                        try:
                            jitter_on = bool(self.config_manager.get('instance_aggro_jitter_enabled', True))
                        except Exception:
                            jitter_on = True
                        try:
                            jitter_pct = float(self.config_manager.get('instance_aggro_jitter_percent', 10.0))
                        except Exception:
                            jitter_pct = 10.0
                        jitter_pct = max(0.0, min(50.0, jitter_pct))
                        eff_interval_s = max(1.0, interval_min * 60.0)
                        try:
                            import random as _rand
                            if jitter_on and jitter_pct > 0.0:
                                span = (jitter_pct / 100.0) * 2.0
                                factor = 1.0 + (span * (_rand.random() - 0.5))
                            else:
                                factor = 1.0
                            eff_interval_s *= factor
                        except Exception:
                            pass
                        mgr['next_aggro_time'] = now_click + eff_interval_s
                        try:
                            self.config_manager.set('instance_aggro_timer_phase', 'interval')
                            self.config_manager.set('instance_next_aggro_time_epoch', float(mgr['next_aggro_time']))
                        except Exception:
                            pass
                        logger.info(f"Aggro timer: scheduling next click in {eff_interval_s:.1f}s")
                # Check if due
                try:
                    next_t = float(mgr.get('next_aggro_time') or 0.0)
                except Exception:
                    next_t = 0.0
                timer_due = now_click >= next_t and next_t > 0
                # If due while in start_delay phase, advance to interval phase without clicking
                if timer_due and mgr.get('aggro_timer_phase') == 'start_delay':
                    try:
                        interval_min = float(self.config_manager.get('instance_aggro_interval_min', 15.0))
                    except Exception:
                        interval_min = 15.0
                    try:
                        jitter_on = bool(self.config_manager.get('instance_aggro_jitter_enabled', True))
                    except Exception:
                        jitter_on = True
                    try:
                        jitter_pct = float(self.config_manager.get('instance_aggro_jitter_percent', 10.0))
                    except Exception:
                        jitter_pct = 10.0
                    jitter_pct = max(0.0, min(50.0, jitter_pct))
                    eff_interval_s = max(1.0, interval_min * 60.0)
                    try:
                        import random as _rand
                        if jitter_on and jitter_pct > 0.0:
                            span = (jitter_pct / 100.0) * 2.0
                            factor = 1.0 + (span * (_rand.random() - 0.5))
                        else:
                            factor = 1.0
                        eff_interval_s *= factor
                    except Exception:
                        pass
                    mgr['aggro_timer_phase'] = 'interval'
                    mgr['next_aggro_time'] = time.time() + eff_interval_s
                    try:
                        self.config_manager.set('instance_aggro_timer_phase', 'interval')
                        self.config_manager.set('instance_next_aggro_time_epoch', float(mgr['next_aggro_time']))
                    except Exception:
                        pass
                    logger.info(f"Aggro timer: start delay completed; next click in {eff_interval_s:.1f}s")
                    timer_due = False

            # Cooldown logic applies only to the aggro bar path; legacy timer has no cooldown
            # Determine cooldown settings (minutes preferred, fallback to seconds)
            try:
                cooldown_min = float(self.config_manager.get('instance_aggro_click_cooldown_min', 0.0))
            except Exception:
                cooldown_min = 0.0
            if cooldown_min and cooldown_min > 0:
                cooldown_s = cooldown_min * 60.0
            else:
                try:
                    cooldown_s = float(self.config_manager.get('instance_aggro_click_cooldown', 7.0))
                except Exception:
                    cooldown_s = 7.0

            phase = mgr.get('cooldown_phase')
            cd_until = float(mgr.get('cooldown_until', 0.0))
            bar_cooldown_active = phase in ('start_delay', 'cooldown') and now_click < cd_until

            # Decide triggers
            should_click_timer = (strategy in ('timer', 'hybrid')) and bool(timer_due)
            should_click_bar = (strategy in ('bar', 'hybrid')) and (not aggro_bar_ok)

            # Timer/hybrid (timer due) click path – no cooldown gating
            if should_click_timer and self.action_manager:
                potion = detector.get_aggro_potion_location() if detector is not None else None
                # Convert potion coordinate to absolute
                potion_abs = None
                try:
                    if potion is not None:
                        from ..detection.capture import CaptureService  # type: ignore
                        bbox = CaptureService().get_window_bbox()
                        potion_abs = (int(bbox['left']) + int(potion.x), int(bbox['top']) + int(potion.y))
                except Exception:
                    potion_abs = None
                if potion is not None and potion_abs is not None:
                    logger.info(f"Aggro timer due; clicking aggro potion at ({potion_abs[0]}, {potion_abs[1]})")
                    if self.action_manager.mouse_controller.move_and_click(potion_abs[0], potion_abs[1], enforce_guard=False, clamp_to_search_roi=False):
                        self.event_system.publish(EventType.AGGRO_USED, {'position': (potion_abs[0], potion_abs[1])})
                        try:
                            wait_s = float(self.config_manager.get('instance_post_aggro_hp_wait', 8.0))
                        except Exception:
                            wait_s = 8.0
                        mgr['post_aggro_active'] = True
                        mgr['post_aggro_wait_until'] = time.time() + max(0.5, wait_s)
                        mgr['last_aggro_click_time'] = now_click

                        # Schedule next click for timer: start delay then interval
                        try:
                            start_delay_s = float(self.config_manager.get('instance_aggro_start_delay_s', 5.0))
                        except Exception:
                            start_delay_s = 5.0
                        if start_delay_s > 0.0:
                            mgr['aggro_timer_phase'] = 'start_delay'
                            mgr['next_aggro_time'] = time.time() + start_delay_s
                            try:
                                self.config_manager.set('instance_aggro_timer_phase', 'start_delay')
                                self.config_manager.set('instance_next_aggro_time_epoch', float(mgr['next_aggro_time']))
                            except Exception:
                                pass
                            logger.info(f"Aggro timer: start delay scheduled in {start_delay_s:.1f}s")
                        else:
                            try:
                                interval_min = float(self.config_manager.get('instance_aggro_interval_min', 15.0))
                            except Exception:
                                interval_min = 15.0
                            try:
                                jitter_on = bool(self.config_manager.get('instance_aggro_jitter_enabled', True))
                            except Exception:
                                jitter_on = True
                            try:
                                jitter_pct = float(self.config_manager.get('instance_aggro_jitter_percent', 10.0))
                            except Exception:
                                jitter_pct = 10.0
                            jitter_pct = max(0.0, min(50.0, jitter_pct))
                            eff_interval_s = max(1.0, interval_min * 60.0)
                            try:
                                import random as _rand
                                if jitter_on and jitter_pct > 0.0:
                                    span = (jitter_pct / 100.0) * 2.0
                                    factor = 1.0 + (span * (_rand.random() - 0.5))
                                else:
                                    factor = 1.0
                                eff_interval_s *= factor
                            except Exception:
                                pass
                            mgr['aggro_timer_phase'] = 'interval'
                            mgr['next_aggro_time'] = time.time() + eff_interval_s
                            try:
                                self.config_manager.set('instance_aggro_timer_phase', 'interval')
                                self.config_manager.set('instance_next_aggro_time_epoch', float(mgr['next_aggro_time']))
                            except Exception:
                                pass
                            logger.info(f"Aggro timer: next click scheduled in {eff_interval_s:.1f}s")
                        logger.info(f"Waiting up to {wait_s:.1f}s for HP bar after aggro click.")
                        return

            # Bar/hybrid (bar missing) click path – apply cooldown gating
            if should_click_bar and self.action_manager:
                if bar_cooldown_active:
                    remaining = max(0.0, cd_until - now_click)
                    phase_str = (phase or '').replace('_', ' ')
                    logger.info(f"Aggro bar missing but {phase_str} active: {remaining:.1f}s remaining before next click")
                else:
                    potion = detector.get_aggro_potion_location() if detector is not None else None
                    potion_abs = None
                    try:
                        if potion is not None:
                            from ..detection.capture import CaptureService  # type: ignore
                            bbox = CaptureService().get_window_bbox()
                            potion_abs = (int(bbox['left']) + int(potion.x), int(bbox['top']) + int(potion.y))
                    except Exception:
                        potion_abs = None
                    if potion is not None and potion_abs is not None:
                        logger.info(f"Aggro bar not present; clicking aggro potion at ({potion_abs[0]}, {potion_abs[1]})")
                        if self.action_manager.mouse_controller.move_and_click(potion_abs[0], potion_abs[1], enforce_guard=False, clamp_to_search_roi=False):
                            self.event_system.publish(EventType.AGGRO_USED, {'position': (potion_abs[0], potion_abs[1])})
                            try:
                                wait_s = float(self.config_manager.get('instance_post_aggro_hp_wait', 8.0))
                            except Exception:
                                wait_s = 8.0
                            mgr['post_aggro_active'] = True
                            mgr['post_aggro_wait_until'] = time.time() + max(0.5, wait_s)
                            mgr['last_aggro_click_time'] = time.time()

                            # Set cooldown gating for bar path
                            try:
                                start_delay_s = float(self.config_manager.get('instance_aggro_start_delay_s', 5.0))
                            except Exception:
                                start_delay_s = 5.0
                            if start_delay_s > 0.0:
                                mgr['cooldown_phase'] = 'start_delay'
                                mgr['cooldown_until'] = time.time() + start_delay_s
                                logger.info(f"Aggro start delay engaged for {start_delay_s:.1f}s")
                            else:
                                mgr['cooldown_phase'] = 'cooldown'
                                mgr['cooldown_until'] = time.time() + max(0.0, cooldown_s)
                                logger.info(f"Aggro cooldown engaged for {cooldown_s:.1f}s")

                            logger.info(f"Waiting up to {wait_s:.1f}s for HP bar after aggro click.")
                            return

        # If we are in a post-aggro waiting window, check for HP bar/in_combat and pause other actions
        mgr = self._instance_manager
        if mgr.get('post_aggro_active', False):
            if hp_seen or in_combat:
                logger.info("HP bar seen after aggro; combat confirmed. Ending post-aggro wait.")
                mgr['post_aggro_active'] = False
                mgr['post_aggro_wait_until'] = 0.0
                # If we were in fallback verification mode, clear the flag and continue
                if mgr.get('fallback_after_max_retries', False):
                    mgr['fallback_after_max_retries'] = False
                # Continue normal loop
            else:
                now_wait = time.time()
                wait_until = float(mgr.get('post_aggro_wait_until', 0.0))
                if now_wait < wait_until:
                    remaining = max(0.0, wait_until - now_wait)
                    logger.info(f"Waiting for HP after aggro: {remaining:.1f}s remaining")
                    return
                else:
                    # Timeout expired; end wait
                    mgr['post_aggro_active'] = False
                    mgr['post_aggro_wait_until'] = 0.0
                    # If this was the fallback verification window, stop the bot
                    if mgr.get('fallback_after_max_retries', False):
                        logger.error("Fallback verification window expired without HP bar; stopping bot.")
                        mgr['fallback_after_max_retries'] = False
                        self.stop()
                        return
                    else:
                        logger.info("Post-aggro wait expired without HP bar; continuing.")

        # Check post-teleport wait/retry flow first
        try:
            hp_wait_s = float(self.config_manager.get('instance_post_teleport_hp_wait', 8.0))
        except Exception:
            hp_wait_s = 8.0

        mgr = self._instance_manager
        now = time.time()
        if mgr.get('post_teleport_active', False):
            # If HP bar becomes visible during the waiting window, success: reset retry state
            if hp_seen or in_combat:
                logger.info("HP bar seen after teleport; instance resumed. Resetting retry counter.")
                mgr['post_teleport_active'] = False
                mgr['post_teleport_wait_until'] = 0.0
                mgr['post_teleport_retry_count'] = 0
                # Continue normal loop
                return

            # Still waiting for HP bar to appear?
            wait_until = float(mgr.get('post_teleport_wait_until', 0.0))
            if now < wait_until:
                remaining = max(0.0, wait_until - now)
                logger.info(f"Waiting for HP after teleport: {remaining:.1f}s remaining")
                return  # defer other actions while waiting

            # Wait expired and no HP bar; retry entering the instance
            retries = int(mgr.get('post_teleport_retry_count', 0))
            max_retries = int(self.config_manager.get('instance_teleport_max_retries', 5))
            if retries >= max_retries:
                # After max retries, perform one-time fallback: click aggro potion, start timers, and wait for HP verification
                if not mgr.get('fallback_used', False):
                    logger.warning(
                        f"Instance restart failed after {retries} attempts. Invoking fallback: click aggro potion and verify HP."
                    )
                    # Acquire aggro potion location
                    potion = None
                    try:
                        if self.detection_engine is not None and self.detection_engine.instance_only_detector is not None:
                            potion = self.detection_engine.instance_only_detector.get_aggro_potion_location()
                    except Exception:
                        potion = None
                    # Convert to absolute
                    potion_abs = None
                    try:
                        if potion is not None:
                            from ..detection.capture import CaptureService  # type: ignore
                            bbox = CaptureService().get_window_bbox()
                            potion_abs = (int(bbox['left']) + int(potion.x), int(bbox['top']) + int(potion.y))
                    except Exception:
                        potion_abs = None
                    if potion is not None and potion_abs is not None and self.action_manager is not None:
                        logger.info(f"Fallback: clicking aggro potion at ({potion_abs[0]}, {potion_abs[1]})")
                        if self.action_manager.mouse_controller.move_and_click(
                            potion_abs[0], potion_abs[1], enforce_guard=False, clamp_to_search_roi=False
                        ):
                            # Mark fallback in-progress and schedule verification window
                            try:
                                wait_s = float(self.config_manager.get('instance_post_aggro_hp_wait', 8.0))
                            except Exception:
                                wait_s = 8.0
                            mgr['fallback_used'] = True
                            mgr['fallback_after_max_retries'] = True
                            # Engage post-aggro verification window
                            mgr['post_aggro_active'] = True
                            mgr['post_aggro_wait_until'] = time.time() + max(0.5, wait_s)
                            mgr['last_aggro_click_time'] = time.time()
                            # Reset/start aggro timer schedule: start delay phase then interval
                            try:
                                start_delay_s = float(self.config_manager.get('instance_aggro_start_delay_s', 5.0))
                            except Exception:
                                start_delay_s = 5.0
                            if start_delay_s > 0.0:
                                mgr['aggro_timer_phase'] = 'start_delay'
                                mgr['next_aggro_time'] = time.time() + start_delay_s
                                try:
                                    self.config_manager.set('instance_aggro_timer_phase', 'start_delay')
                                    self.config_manager.set('instance_next_aggro_time_epoch', float(mgr['next_aggro_time']))
                                except Exception:
                                    pass
                                logger.info(f"Fallback: aggro timer start delay scheduled in {start_delay_s:.1f}s")
                            else:
                                try:
                                    interval_min = float(self.config_manager.get('instance_aggro_interval_min', 15.0))
                                except Exception:
                                    interval_min = 15.0
                                try:
                                    jitter_on = bool(self.config_manager.get('instance_aggro_jitter_enabled', True))
                                except Exception:
                                    jitter_on = True
                                try:
                                    jitter_pct = float(self.config_manager.get('instance_aggro_jitter_percent', 10.0))
                                except Exception:
                                    jitter_pct = 10.0
                                jitter_pct = max(0.0, min(50.0, jitter_pct))
                                eff_interval_s = max(1.0, interval_min * 60.0)
                                try:
                                    import random as _rand
                                    if jitter_on and jitter_pct > 0.0:
                                        span = (jitter_pct / 100.0) * 2.0
                                        factor = 1.0 + (span * (_rand.random() - 0.5))
                                    else:
                                        factor = 1.0
                                    eff_interval_s *= factor
                                except Exception:
                                    pass
                                mgr['aggro_timer_phase'] = 'interval'
                                mgr['next_aggro_time'] = time.time() + eff_interval_s
                                try:
                                    self.config_manager.set('instance_aggro_timer_phase', 'interval')
                                    self.config_manager.set('instance_next_aggro_time_epoch', float(mgr['next_aggro_time']))
                                except Exception:
                                    pass
                                logger.info(f"Fallback: aggro timer next click scheduled in {eff_interval_s:.1f}s")
                            logger.info(f"Fallback: waiting up to {wait_s:.1f}s for HP bar after aggro click.")
                            # Leave retry flow and allow post-aggro wait handler to manage continuation
                            mgr['post_teleport_active'] = False
                            mgr['post_teleport_wait_until'] = 0.0
                            return
                        else:
                            logger.error("Fallback: aggro potion click failed; stopping bot.")
                            self.stop()
                            return
                    else:
                        logger.error("Fallback: aggro potion coordinate not set; stopping bot.")
                        self.stop()
                        return
                else:
                    # Fallback already used once; stop to avoid looping
                    logger.error(
                        f"Instance restart failed after {retries} attempts and fallback already used; stopping bot."
                    )
                    self.stop()
                    return

            # Attempt retry: click token -> wait -> click teleport
            detector = None
            try:
                if self.detection_engine is not None:
                    detector = self.detection_engine.instance_only_detector
            except Exception:
                detector = None
            token_location = detector.get_instance_token_location() if detector is not None else None
            teleport_location = detector.get_instance_teleport_location() if detector is not None else None
            # Convert window-relative coordinates to absolute using current bbox
            try:
                if token_location is not None and teleport_location is not None:
                    from ..detection.capture import CaptureService  # type: ignore
                    bbox = CaptureService().get_window_bbox()
                    token_abs = (int(bbox['left']) + int(token_location.x), int(bbox['top']) + int(token_location.y))
                    tele_abs = (int(bbox['left']) + int(teleport_location.x), int(bbox['top']) + int(teleport_location.y))
                else:
                    token_abs = None; tele_abs = None
            except Exception:
                token_abs = None; tele_abs = None
            token_delay = detector.get_instance_token_delay() if detector is not None else float(self.config_manager.get('instance_token_delay', 2.0))

            if token_abs and tele_abs and self.action_manager:
                if now - mgr['last_teleport_time'] >= mgr['teleport_cooldown']:
                    logger.info(f"Retrying instance entry (attempt {retries+1}/{max_retries})")
                    # Bypass anti-overclick guard for deterministic instance entry clicks
                    if self.action_manager.mouse_controller.move_and_click(token_abs[0], token_abs[1], enforce_guard=False, clamp_to_search_roi=False):
                        time.sleep(token_delay)
                        if self.action_manager.mouse_controller.move_and_click(tele_abs[0], tele_abs[1], enforce_guard=False, clamp_to_search_roi=False):
                            mgr['last_teleport_time'] = now
                            mgr['post_teleport_retry_count'] = retries + 1
                            mgr['post_teleport_wait_until'] = time.time() + hp_wait_s
                            mgr['post_teleport_active'] = True
                            # After clicking teleport, reset combat flag to allow fresh detection
                            try:
                                if self.detection_engine is not None:
                                    self.detection_engine.instance_only_detector.in_combat = False
                            except Exception:
                                pass
                            logger.info(
                                f"Waiting up to {hp_wait_s:.1f}s for HP bar after retry (attempt {mgr['post_teleport_retry_count']})."
                            )
                            return
                        else:
                            logger.warning("Retry: teleport click failed (move_and_click returned False)")
                    else:
                        logger.warning("Retry: token click failed (move_and_click returned False)")
                else:
                    # Still under teleport cooldown; wait a bit
                    cd_left = (mgr['teleport_cooldown'] - (now - mgr['last_teleport_time']))
                    logger.info(f"Teleport retry cooling down: {cd_left:.1f}s left")
                    return
            else:
                logger.warning("Token/Teleport coordinates not set; cannot retry instance entry.")
                return

        # Check if we need to teleport to instance (initial attempt)
        if instance_empty:
            # Enforce: only teleport if there has been NO combat for at least HP BAR TIMEOUT seconds
            try:
                hp_timeout_s = float(self.config_manager.get('instance_hp_timeout', 30.0))
            except Exception:
                hp_timeout_s = 30.0
            last_hp_seen_time = float(result.get('last_hp_seen_time', 0.0))
            seconds_since_combat = max(0.0, now - last_hp_seen_time)
            has_recent_combat = seconds_since_combat < hp_timeout_s

            if has_recent_combat:
                # Do not start instance token/teleport sequence if combat was flagged within timeout window
                logger.info(
                    f"Teleport blocked: combat seen {seconds_since_combat:.1f}s ago (< {hp_timeout_s:.0f}s timeout)"
                )
                return

            # Get instance token and teleport locations
            detector = None
            try:
                if self.detection_engine is not None:
                    detector = self.detection_engine.instance_only_detector
            except Exception:
                detector = None
            token_location = detector.get_instance_token_location() if detector is not None else None
            teleport_location = detector.get_instance_teleport_location() if detector is not None else None
            # Convert window-relative coordinates to absolute using current bbox
            try:
                if token_location is not None and teleport_location is not None:
                    from ..detection.capture import CaptureService  # type: ignore
                    bbox = CaptureService().get_window_bbox()
                    token_abs = (int(bbox['left']) + int(token_location.x), int(bbox['top']) + int(token_location.y))
                    tele_abs = (int(bbox['left']) + int(teleport_location.x), int(bbox['top']) + int(teleport_location.y))
                else:
                    token_abs = None; tele_abs = None
            except Exception:
                token_abs = None; tele_abs = None
            token_delay = detector.get_instance_token_delay() if detector is not None else float(self.config_manager.get('instance_token_delay', 2.0))
            
            if token_abs and tele_abs and self.action_manager:
                # Check cooldown
                if now - mgr['last_teleport_time'] >= mgr['teleport_cooldown']:
                    logger.info(
                        f"No combat for {seconds_since_combat:.1f}s (>= {hp_timeout_s:.0f}s). Teleporting to instance."
                    )
                    
                    # Click instance token
                    logger.info(f"Clicking instance token at ({token_abs[0]}, {token_abs[1]})")
                    if self.action_manager.mouse_controller.move_and_click(token_abs[0], token_abs[1], enforce_guard=False, clamp_to_search_roi=False):
                        # Wait for token delay
                        time.sleep(token_delay)
                        
                        # Click teleport location
                        logger.info(f"Clicking teleport at ({tele_abs[0]}, {tele_abs[1]})")
                        if self.action_manager.mouse_controller.move_and_click(tele_abs[0], tele_abs[1], enforce_guard=False, clamp_to_search_roi=False):
                            mgr['last_teleport_time'] = now
                            # Publish event
                            self.event_system.publish(EventType.INSTANCE_ENTERED, {
                                'token_position': (token_abs[0], token_abs[1]),
                                'teleport_position': (tele_abs[0], tele_abs[1]),
                                'timestamp': now
                            })
                            
                            # Reset combat status after teleporting
                            try:
                                if self.detection_engine is not None:
                                    self.detection_engine.instance_only_detector.in_combat = False
                            except Exception:
                                pass
                            # Start post-teleport waiting window
                            mgr['post_teleport_active'] = True
                            mgr['post_teleport_wait_until'] = time.time() + hp_wait_s
                            # Reset retries for a fresh sequence
                            mgr['post_teleport_retry_count'] = 0
                            logger.info(f"Waiting up to {hp_wait_s:.1f}s for HP bar to appear after teleport.")
                        else:
                            logger.warning("Teleport click failed (move_and_click returned False)")
                    else:
                        logger.warning("Token click failed (move_and_click returned False)")

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