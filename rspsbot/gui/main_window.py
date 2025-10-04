"""
Main window for RSPS Color Bot v3
"""
import logging
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QLabel, QPushButton, QScrollArea
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal

from .panels import (
    ControlPanel, DetectionPanel, CombatPanel,
    ProfilesPanel, LogsPanel
)
from .panels.teleport_panel import TeleportPanel
from .panels.potion_panel import PotionPanel
from .panels.instance_panel import InstancePanel
from .panels.stats_panel import StatsPanel
from .panels.multi_monster_panel import MultiMonsterPanel
from .visualization.debug_overlay import DebugOverlayWindow
from .panels.chat_panel import ChatPanel

# Get module logger
logger = logging.getLogger('rspsbot.gui.main_window')

class MainWindow(QMainWindow):
    """
    Main window of the application with tab-based interface
    """
    # Signal emitted before saving a profile so panels can flush unsaved UI into config
    beforeProfileSave = pyqtSignal()
    
    def __init__(self, config_manager, bot_controller):
        """
        Initialize the main window
        
        Args:
            config_manager: Configuration manager
            bot_controller: Bot controller
        """
        super().__init__()
        self.config_manager = config_manager
        self.bot_controller = bot_controller
        
        # Set window properties
        self.setWindowTitle("RSPS Color Bot v3")
        # Expanded default + minimum to reduce initial crowding
        self.resize(1300, 900)
        self.setMinimumSize(1100, 750)
        try:
            # Restore previous geometry if stored
            last_size = self.config_manager.get('ui_main_window_size')
            if isinstance(last_size, (list, tuple)) and len(last_size) == 2:
                self.resize(int(last_size[0]), int(last_size[1]))
            last_pos = self.config_manager.get('ui_main_window_pos')
            if isinstance(last_pos, (list, tuple)) and len(last_pos) == 2:
                self.move(int(last_pos[0]), int(last_pos[1]))
        except Exception:
            pass
        
        # Create central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Initialize UI components
        self.init_control_panel()
        self.init_tabs()
        self.init_status_bar()
        
        # Set up timers
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second
        
        # Create debug overlay window (hidden by default, toggled by config)
        try:
            self.debug_overlay = DebugOverlayWindow(self.config_manager, self.bot_controller.event_system)
            self.debug_overlay.hide()
        except Exception as e:
            self.debug_overlay = None
            logger.error(f"Failed to initialize debug overlay: {e}")

        logger.info("Main window initialized")
    
    def init_control_panel(self):
        """Initialize the control panel"""
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        
        # Start button
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.on_start_clicked)
        control_layout.addWidget(self.start_button)
        
        # Pause button
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.on_pause_clicked)
        self.pause_button.setEnabled(False)
        control_layout.addWidget(self.pause_button)
        
        # Stop button
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.on_stop_clicked)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)
        
        # Add spacer
        control_layout.addStretch()
        
        # Add control panel to main layout
        self.main_layout.addWidget(control_panel)
    
    def init_tabs(self):
        """Initialize tabs"""
        # Helper to wrap large content widgets with a scroll area (vertical scroll only)
        def make_scrollable(widget: QWidget, name: str):
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            # Use Qt.ScrollBarAlwaysOff constant; some type checkers may not resolve attribute on Qt alias
            try:
                sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            except Exception:
                from PyQt5 import QtCore
                sa.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            sa.setWidget(widget)
            sa.setObjectName(f"scroll_{name}")
            return sa

        # Main control tab (lightweight – no scroll needed)
        self.control_tab = ControlPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(self.control_tab, "Main")
        # Detection settings tab (heavy)
        self.detection_tab = DetectionPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(make_scrollable(self.detection_tab, "detection"), "Detection Settings")

        # Combat settings tab
        self.combat_tab = CombatPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(make_scrollable(self.combat_tab, "combat"), "Combat Settings")

        # Multi Monster Mode tab
        self.multi_monster_tab = MultiMonsterPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(make_scrollable(self.multi_monster_tab, "multi_monster"), "Multi Monster Mode")

        # Teleport settings tab
        self.teleport_tab = TeleportPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(make_scrollable(self.teleport_tab, "teleport"), "Teleport Settings")

        # Potion settings tab
        self.potion_tab = PotionPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(make_scrollable(self.potion_tab, "potion"), "Potion Settings")

        # Instance settings tab (entry/teleport basics)
        self.instance_tab = InstancePanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(make_scrollable(self.instance_tab, "instance"), "Instance Settings")

        # Instance Mode main tab (new, reorganized)
        from .panels.instance_panel import InstanceModePanel
        self.instance_mode_tab = InstanceModePanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(make_scrollable(self.instance_mode_tab, "instance_mode"), "Instance Mode")

        # Statistics tab (small enough left unwrapped)
        self.stats_tab = StatsPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(self.stats_tab, "Statistics")

        # Profiles tab (can grow vertically depending on content)
        self.profiles_tab = ProfilesPanel(self.config_manager)
        self.tab_widget.addTab(make_scrollable(self.profiles_tab, "profiles"), "Profiles")

        # Chat tab
        self.chat_tab = ChatPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(make_scrollable(self.chat_tab, "chat"), "Chat")

        # Connect pre-save hook: before profiles panel saves, flush edits from key tabs so all UI state lands in config
        try:
            orig_on_save = self.profiles_tab.on_save_clicked
            orig_on_save_as = self.profiles_tab.on_save_as_clicked
            orig_on_load = self.profiles_tab.on_load_clicked

            def wrapped_on_save():
                try:
                    # Instance Mode composite settings
                    if hasattr(self, 'instance_mode_tab') and hasattr(self.instance_mode_tab, 'save_instance_mode_settings'):
                        self.instance_mode_tab.save_instance_mode_settings(silent=True)
                    # Instance basic tab (token/teleport)
                    if hasattr(self, 'instance_tab') and hasattr(self.instance_tab, 'on_apply_clicked'):
                        self.instance_tab.on_apply_clicked()
                    # Multi Monster: save all sub-sections silently
                    if hasattr(self, 'multi_monster_tab') and hasattr(self.multi_monster_tab, 'save_all_settings'):
                        self.multi_monster_tab.save_all_settings(silent=True)
                    else:
                        # Fallback: call individual apply methods if present
                        if hasattr(self.multi_monster_tab, 'on_apply_clicked'):
                            self.multi_monster_tab.on_apply_clicked(silent=True)
                        if hasattr(self.multi_monster_tab, 'on_monsters_apply_clicked'):
                            self.multi_monster_tab.on_monsters_apply_clicked(silent=True)
                        if hasattr(self.multi_monster_tab, 'on_weapons_apply_clicked'):
                            self.multi_monster_tab.on_weapons_apply_clicked(silent=True)
                    # Combat tab general apply if available
                    if hasattr(self, 'combat_tab') and hasattr(self.combat_tab, 'on_apply_clicked'):
                        # Some panels may not accept silent; try with kw if supported, else no-arg
                        try:
                            self.combat_tab.on_apply_clicked(silent=True)
                        except TypeError:
                            self.combat_tab.on_apply_clicked()
                    # Ensure HP bar color and Tile color editors flush their state before save
                    try:
                        if hasattr(self, 'combat_tab') and hasattr(self.combat_tab, 'hpbar_color_editor'):
                            spec = self.combat_tab.hpbar_color_editor.get_color_spec()
                            if spec is not None:
                                self.config_manager.set_color_spec('hpbar_color', spec)
                    except Exception:
                        pass
                    try:
                        if hasattr(self, 'detection_tab') and hasattr(self.detection_tab, 'tile_color_editor'):
                            spec = self.detection_tab.tile_color_editor.get_color_spec()
                            if spec is not None:
                                self.config_manager.set_color_spec('tile_color', spec)
                    except Exception:
                        pass
                except Exception:
                    pass
                self.beforeProfileSave.emit()
                return orig_on_save()

            def wrapped_on_save_as():
                try:
                    if hasattr(self, 'instance_mode_tab') and hasattr(self.instance_mode_tab, 'save_instance_mode_settings'):
                        self.instance_mode_tab.save_instance_mode_settings(silent=True)
                    if hasattr(self, 'instance_tab') and hasattr(self.instance_tab, 'on_apply_clicked'):
                        self.instance_tab.on_apply_clicked()
                    if hasattr(self, 'multi_monster_tab') and hasattr(self.multi_monster_tab, 'save_all_settings'):
                        self.multi_monster_tab.save_all_settings(silent=True)
                    else:
                        if hasattr(self.multi_monster_tab, 'on_apply_clicked'):
                            self.multi_monster_tab.on_apply_clicked(silent=True)
                        if hasattr(self.multi_monster_tab, 'on_monsters_apply_clicked'):
                            self.multi_monster_tab.on_monsters_apply_clicked(silent=True)
                        if hasattr(self.multi_monster_tab, 'on_weapons_apply_clicked'):
                            self.multi_monster_tab.on_weapons_apply_clicked(silent=True)
                    if hasattr(self, 'combat_tab') and hasattr(self.combat_tab, 'on_apply_clicked'):
                        try:
                            self.combat_tab.on_apply_clicked(silent=True)
                        except TypeError:
                            self.combat_tab.on_apply_clicked()
                    # Ensure HP bar color and Tile color editors flush their state before save-as
                    try:
                        if hasattr(self, 'combat_tab') and hasattr(self.combat_tab, 'hpbar_color_editor'):
                            spec = self.combat_tab.hpbar_color_editor.get_color_spec()
                            if spec is not None:
                                self.config_manager.set_color_spec('hpbar_color', spec)
                    except Exception:
                        pass
                    try:
                        if hasattr(self, 'detection_tab') and hasattr(self.detection_tab, 'tile_color_editor'):
                            spec = self.detection_tab.tile_color_editor.get_color_spec()
                            if spec is not None:
                                self.config_manager.set_color_spec('tile_color', spec)
                    except Exception:
                        pass
                except Exception:
                    pass
                self.beforeProfileSave.emit()
                return orig_on_save_as()

            self.profiles_tab.on_save_clicked = wrapped_on_save
            self.profiles_tab.on_save_as_clicked = wrapped_on_save_as
            
            def wrapped_on_load():
                # Let the original handler perform the load (and show messages)
                res = orig_on_load()
                # After a successful load, refresh key tabs to reflect new config
                try:
                    if hasattr(self, 'multi_monster_tab') and hasattr(self.multi_monster_tab, 'reload_from_config'):
                        self.multi_monster_tab.reload_from_config()
                except Exception:
                    pass
                return res

            self.profiles_tab.on_load_clicked = wrapped_on_load
        except Exception as e:
            logger.error(f"Failed to wire profile pre-save hook: {e}")

        # Logs tab
        self.logs_tab = LogsPanel(self.config_manager)
        self.tab_widget.addTab(make_scrollable(self.logs_tab, "logs"), "Logs & Debug")
    
    def init_status_bar(self):
        """Initialize the status bar"""
        # Status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        
        # Add permanent widgets
        self.runtime_label = QLabel("Runtime: 00:00:00")
        self.status_bar.addPermanentWidget(self.runtime_label)
        
        self.monster_count_label = QLabel("Monsters: 0")
        self.status_bar.addPermanentWidget(self.monster_count_label)

        # Aggro remaining-time label
        self.aggro_status_label = QLabel("Aggro: --:--")
        self.status_bar.addPermanentWidget(self.aggro_status_label)
    
    def update_status(self):
        """Update status information"""
        # Update runtime
        if self.bot_controller.is_running() or self.bot_controller.is_paused():
            runtime = self.bot_controller.get_runtime()
            hours, remainder = divmod(runtime, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.runtime_label.setText(f"Runtime: {int(hours):02}:{int(minutes):02}:{int(seconds):02}")
        
        # Update monster count
        monster_count = self.bot_controller.get_monster_count()
        self.monster_count_label.setText(f"Monsters: {monster_count}")
        
        # Update status label
        status = self.bot_controller.get_status()
        self.status_label.setText(status)
        
        # Update button states
        self.update_button_states()

        # Update aggro remaining time (Instance Mode)
        try:
            remaining = self.bot_controller.get_aggro_remaining_seconds()
            if remaining is None:
                self.aggro_status_label.setText("Aggro: n/a")
            else:
                remaining = max(0, int(remaining))
                m, s = divmod(remaining, 60)
                if m >= 60:
                    h, rem = divmod(m, 60)
                    self.aggro_status_label.setText(f"Aggro: {int(h):02}:{int(rem):02}:{int(s):02}")
                else:
                    self.aggro_status_label.setText(f"Aggro: {int(m):02}:{int(s):02}")
        except Exception as e:
            logger.error(f"Error updating aggro status: {e}")
            self.aggro_status_label.setText("Aggro: error")

        # Update debug overlay if enabled
        try:
            if self.debug_overlay is not None:
                # Use the same key the Control Panel toggles and the overlay reads
                debug_enabled = bool(self.config_manager.get('debug_overlay', False))
                if debug_enabled and not self.debug_overlay.isVisible():
                    self.debug_overlay.show()
                elif not debug_enabled and self.debug_overlay.isVisible():
                    self.debug_overlay.hide()
        except Exception as e:
            logger.error(f"Error updating debug overlay: {e}")
    
    def update_button_states(self):
        """Update button states based on bot status"""
        if self.bot_controller.is_running():
            self.start_button.setEnabled(False)
            self.pause_button.setEnabled(True)
            self.stop_button.setEnabled(True)
        elif self.bot_controller.is_paused():
            self.start_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.stop_button.setEnabled(True)
        else:
            self.start_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.stop_button.setEnabled(False)
    
    def on_start_clicked(self):
        """Handle start button click"""
        if self.bot_controller.is_paused():
            self.bot_controller.resume()
        else:
            self.bot_controller.start()
        self.update_button_states()
    
    def on_pause_clicked(self):
        """Handle pause button click"""
        self.bot_controller.pause()
        self.update_button_states()
    
    def on_stop_clicked(self):
        """Handle stop button click"""
        self.bot_controller.stop()
        self.update_button_states()
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop the bot if running
        if self.bot_controller.is_running() or self.bot_controller.is_paused():
            self.bot_controller.stop()
        
        # Hide debug overlay if visible
        if self.debug_overlay is not None and self.debug_overlay.isVisible():
            self.debug_overlay.hide()

        # Persist window geometry for next launch
        try:
            size = self.size()
            pos = self.pos()
            self.config_manager.set('ui_main_window_size', [size.width(), size.height()])
            self.config_manager.set('ui_main_window_pos', [pos.x(), pos.y()])
        except Exception:
            pass
        
        # Accept the event
        event.accept()