"""
Main window for RSPS Color Bot v3
"""
import logging
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QStatusBar, QLabel, QPushButton
)
from PyQt5.QtCore import QTimer, Qt

from .panels import (
    ControlPanel, DetectionPanel, CombatPanel,
    ProfilesPanel, LogsPanel
)
from .panels.teleport_panel import TeleportPanel
from .panels.potion_panel import PotionPanel
from .panels.instance_panel import InstancePanel
from .panels.stats_panel import StatsPanel
from .visualization.debug_overlay import DebugOverlayWindow

# Get module logger
logger = logging.getLogger('rspsbot.gui.main_window')

class MainWindow(QMainWindow):
    """
    Main window of the application with tab-based interface
    """
    
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
        self.setMinimumSize(1000, 700)
        
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
        # Main control tab
        self.control_tab = ControlPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(self.control_tab, "Main")
        
        # Detection settings tab
        self.detection_tab = DetectionPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(self.detection_tab, "Detection Settings")
        
        # Combat settings tab
        self.combat_tab = CombatPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(self.combat_tab, "Combat Settings")
        
        # Teleport settings tab
        self.teleport_tab = TeleportPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(self.teleport_tab, "Teleport Settings")
        
        # Potion settings tab
        self.potion_tab = PotionPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(self.potion_tab, "Potion Settings")
        
        # Instance settings tab
        self.instance_tab = InstancePanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(self.instance_tab, "Instance Settings")
        
        # Statistics tab
        self.stats_tab = StatsPanel(self.config_manager, self.bot_controller)
        self.tab_widget.addTab(self.stats_tab, "Statistics")
        
        # Profiles tab
        self.profiles_tab = ProfilesPanel(self.config_manager)
        self.tab_widget.addTab(self.profiles_tab, "Profiles")
        
        # Logs tab
        self.logs_tab = LogsPanel(self.config_manager)
        self.tab_widget.addTab(self.logs_tab, "Logs & Debug")
    
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

        # Sync overlay visibility
        if self.debug_overlay is not None:
            try:
                enabled = bool(self.config_manager.get('debug_overlay', False))
                if enabled and not self.debug_overlay.isVisible():
                    self.debug_overlay.show()
                    self.debug_overlay.raise_()
                elif not enabled and self.debug_overlay.isVisible():
                    self.debug_overlay.hide()
            except Exception:
                pass
    
    def update_button_states(self):
        """Update button states based on bot state"""
        is_running = self.bot_controller.is_running()
        is_paused = self.bot_controller.is_paused()
        is_stopped = self.bot_controller.is_stopped()
        
        self.start_button.setEnabled(is_stopped or is_paused)
        self.pause_button.setEnabled(is_running)
        self.stop_button.setEnabled(is_running or is_paused)
        
        # Update pause button text
        if is_paused:
            self.pause_button.setText("Resume")
        else:
            self.pause_button.setText("Pause")
    
    def on_start_clicked(self):
        """Handle start button click"""
        if self.bot_controller.is_paused():
            logger.info("Resuming bot")
            self.bot_controller.resume()
        else:
            logger.info("Starting bot")
            self.bot_controller.start()
        
        self.update_button_states()
    
    def on_pause_clicked(self):
        """Handle pause button click"""
        if self.bot_controller.is_running():
            logger.info("Pausing bot")
            self.bot_controller.pause()
        elif self.bot_controller.is_paused():
            logger.info("Resuming bot")
            self.bot_controller.resume()
        
        self.update_button_states()
    
    def on_stop_clicked(self):
        """Handle stop button click"""
        logger.info("Stopping bot")
        self.bot_controller.stop()
        self.update_button_states()
    
    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("Closing main window")
        
        # Stop the bot if it's running
        if self.bot_controller.is_running() or self.bot_controller.is_paused():
            self.bot_controller.stop()
        
        # Stop timers
        self.status_timer.stop()

        # Close overlay
        try:
            if self.debug_overlay is not None:
                self.debug_overlay.close()
        except Exception:
            pass
        
        # Accept the close event
        event.accept()