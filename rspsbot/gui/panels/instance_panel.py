"""
Instance settings panel for RSPS Color Bot v3
"""
import logging
import time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox, QGridLayout,
    QTabWidget, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer

from .detection_panel import ColorSpecEditor
from ..components.screen_picker import ZoomRoiPickerDialog
from ..components.enhanced_color_editor import EnhancedColorEditor
from ..components.advanced_roi_selector import AdvancedROISelector
from ..components.overlay import AggroOverlay
from .teleport_panel import CoordinateSelector
from ...core.config import Coordinate

# Get module logger
logger = logging.getLogger('rspsbot.gui.panels.instance_panel')

class InstancePanel(QWidget):
    """
    Panel for instance settings
    """
    
    def __init__(self, config_manager, bot_controller):
        """
        Initialize the instance panel
        
        Args:
            config_manager: Configuration manager
            bot_controller: Bot controller
        """
        super().__init__()
        self.config_manager = config_manager
        self.bot_controller = bot_controller
        
        # Initialize UI
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI components"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Instance Entry
        entry_group = QGroupBox("Instance Entry")
        entry_group.setToolTip("Configure instance entry settings")
        entry_layout = QVBoxLayout(entry_group)
        
        # Token Location
        token_layout = QHBoxLayout()
        token_layout.addWidget(QLabel("Token Location:"))
        self.token_x_spin = QSpinBox()
        self.token_x_spin.setRange(0, 3000)
        self.token_x_spin.setValue(self.config_manager.get('instance_token_location', {}).get('x', 0))
        token_layout.addWidget(self.token_x_spin)
        token_layout.addWidget(QLabel("X"))
        self.token_y_spin = QSpinBox()
        self.token_y_spin.setRange(0, 3000)
        self.token_y_spin.setValue(self.config_manager.get('instance_token_location', {}).get('y', 0))
        token_layout.addWidget(self.token_y_spin)
        token_layout.addWidget(QLabel("Y"))
        self.token_pick_btn = QPushButton("Pick From Screen")
        self.token_pick_btn.clicked.connect(self.on_pick_token_location)
        token_layout.addWidget(self.token_pick_btn)
        token_layout.addStretch()
        entry_layout.addLayout(token_layout)
        
        # Teleport Location
        teleport_layout = QHBoxLayout()
        teleport_layout.addWidget(QLabel("Teleport Location:"))
        self.teleport_x_spin = QSpinBox()
        self.teleport_x_spin.setRange(0, 3000)
        self.teleport_x_spin.setValue(self.config_manager.get('instance_teleport_location', {}).get('x', 0))
        teleport_layout.addWidget(self.teleport_x_spin)
        teleport_layout.addWidget(QLabel("X"))
        self.teleport_y_spin = QSpinBox()
        self.teleport_y_spin.setRange(0, 3000)
        self.teleport_y_spin.setValue(self.config_manager.get('instance_teleport_location', {}).get('y', 0))
        teleport_layout.addWidget(self.teleport_y_spin)
        teleport_layout.addWidget(QLabel("Y"))
        self.teleport_pick_btn = QPushButton("Pick From Screen")
        self.teleport_pick_btn.clicked.connect(self.on_pick_teleport_location)
        teleport_layout.addWidget(self.teleport_pick_btn)
        teleport_layout.addStretch()
        entry_layout.addLayout(teleport_layout)
        
        # Token Delay
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Token Delay:"))
        self.token_delay_spin = QDoubleSpinBox()
        self.token_delay_spin.setRange(0.1, 10.0)
        self.token_delay_spin.setSingleStep(0.1)
        self.token_delay_spin.setValue(self.config_manager.get('instance_token_delay', 1.0))
        delay_layout.addWidget(self.token_delay_spin)
        delay_layout.addWidget(QLabel("seconds"))
        delay_layout.addStretch()
        entry_layout.addLayout(delay_layout)
        
        # Max Teleport Retries
        retries_layout = QHBoxLayout()
        retries_layout.addWidget(QLabel("Max Teleport Retries:"))
        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(1, 10)
        self.max_retries_spin.setValue(self.config_manager.get('instance_teleport_max_retries', 3))
        retries_layout.addWidget(self.max_retries_spin)
        retries_layout.addStretch()
        entry_layout.addLayout(retries_layout)
        
        layout.addWidget(entry_group)
        
        # Apply/Reset buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.clicked.connect(self.on_apply_clicked)
        buttons_layout.addWidget(self.apply_btn)
        
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self.on_reset_clicked)
        buttons_layout.addWidget(self.reset_btn)
        
        layout.addLayout(buttons_layout)
        layout.addStretch()
    
    def on_pick_token_location(self):
        """Pick token location from screen"""
        try:
            from ..components.screen_picker import ZoomCoordinatePickerDialog
            picker = ZoomCoordinatePickerDialog("Select Instance Token Location")
            if picker.exec_() == ZoomCoordinatePickerDialog.Accepted:
                x, y = picker.get_coordinate()
                self.token_x_spin.setValue(x)
                self.token_y_spin.setValue(y)
        except Exception as e:
            logger.error(f"Error picking token location: {e}")
    
    def on_pick_teleport_location(self):
        """Pick teleport location from screen"""
        try:
            from ..components.screen_picker import ZoomCoordinatePickerDialog
            picker = ZoomCoordinatePickerDialog("Select Instance Teleport Location")
            if picker.exec_() == ZoomCoordinatePickerDialog.Accepted:
                x, y = picker.get_coordinate()
                self.teleport_x_spin.setValue(x)
                self.teleport_y_spin.setValue(y)
        except Exception as e:
            logger.error(f"Error picking teleport location: {e}")
    
    def on_apply_clicked(self):
        """Apply settings changes"""
        try:
            # Save token location
            token_location = {
                'x': self.token_x_spin.value(),
                'y': self.token_y_spin.value()
            }
            self.config_manager.set('instance_token_location', token_location)
            
            # Save teleport location
            teleport_location = {
                'x': self.teleport_x_spin.value(),
                'y': self.teleport_y_spin.value()
            }
            self.config_manager.set('instance_teleport_location', teleport_location)
            
            # Save other settings
            self.config_manager.set('instance_token_delay', self.token_delay_spin.value())
            self.config_manager.set('instance_teleport_max_retries', self.max_retries_spin.value())
            
            logger.info("Instance settings saved")
        except Exception as e:
            logger.error(f"Error applying instance settings: {e}")
    
    def on_reset_clicked(self):
        """Reset settings to defaults"""
        try:
            # Reset token location
            self.token_x_spin.setValue(0)
            self.token_y_spin.setValue(0)
            
            # Reset teleport location
            self.teleport_x_spin.setValue(0)
            self.teleport_y_spin.setValue(0)
            
            # Reset other settings
            self.token_delay_spin.setValue(1.0)
            self.max_retries_spin.setValue(3)
            
            logger.info("Instance settings reset to defaults")
        except Exception as e:
            logger.error(f"Error resetting instance settings: {e}")


class InstanceModePanel(QWidget):
    """
    Main tab for Instance Mode with sub-tabs for HP Bar Detection, Aggro Potion, and Instance Teleport
    """
    def __init__(self, config_manager, bot_controller):
        super().__init__()
        self.config_manager = config_manager
        self.bot_controller = bot_controller
        # Overlay instance holder
        self._aggro_overlay: AggroOverlay = None  # type: ignore
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI components"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Mode Settings
        mode_group = QGroupBox("Instance Mode Settings")
        mode_group.setToolTip("Configure Instance Mode settings")
        mode_layout = QVBoxLayout(mode_group)
        
        # Enable Instance Mode
        enable_layout = QHBoxLayout()
        self.enable_checkbox = QCheckBox("Enable Instance Only Mode")
        self.enable_checkbox.setToolTip("When enabled, the bot will only operate in Instance Mode")
        self.enable_checkbox.setChecked(self.config_manager.get('instance_only_mode', False))
        enable_layout.addWidget(self.enable_checkbox)
        enable_layout.addStretch()
        mode_layout.addLayout(enable_layout)
        
        # Instance Active Detection
        instance_active_group = QGroupBox("Instance Active Detection")
        instance_active_group.setToolTip("Configure how the bot detects if the instance is active")
        instance_active_layout = QVBoxLayout(instance_active_group)
        
        # HP Bar Detection for Instance Active
        hp_layout = QHBoxLayout()
        hp_layout.addWidget(QLabel("HP Bar Timeout:"))
        self.hp_timeout_spin = QDoubleSpinBox()
        self.hp_timeout_spin.setToolTip("Time (in seconds) after which instance is considered inactive if HP bar is not seen")
        self.hp_timeout_spin.setRange(1.0, 600.0)
        self.hp_timeout_spin.setSingleStep(1.0)
        self.hp_timeout_spin.setValue(self.config_manager.get('instance_hp_timeout_s', 60.0))
        hp_layout.addWidget(self.hp_timeout_spin)
        hp_layout.addWidget(QLabel("seconds"))
        hp_layout.addStretch()
        instance_active_layout.addLayout(hp_layout)
        
        mode_layout.addWidget(instance_active_group)
        layout.addWidget(mode_group)
        
        # Create tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Aggro Potion tab
        self.aggro_tab = QWidget()
        self.tabs.addTab(self.aggro_tab, "Aggro Management")
        self._init_aggro_tab()
        
        # Instance Teleport tab
        self.teleport_tab = QWidget()
        self.tabs.addTab(self.teleport_tab, "Instance Teleport")
        self._init_teleport_tab()
        
        # Apply/Reset buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.clicked.connect(self.on_apply_clicked)
        buttons_layout.addWidget(self.apply_btn)
        
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self.on_reset_clicked)
        buttons_layout.addWidget(self.reset_btn)
        
        layout.addLayout(buttons_layout)
    
    def _init_aggro_tab(self):
        """Initialize the Aggro Potion tab"""
        layout = QVBoxLayout(self.aggro_tab)
        
        # Aggro Bar ROI
        roi_group = QGroupBox("Aggro Bar ROI")
        roi_group.setToolTip("Define the region where the bot will look for the aggro bar")
        roi_layout = QVBoxLayout(roi_group)
        
        roi_row = QHBoxLayout()
        self.aggro_roi_label = QLabel(self._roi_text(self.config_manager.get('instance_aggro_bar_roi')))
        roi_row.addWidget(self.aggro_roi_label)
        roi_row.addStretch()
        
        self.aggro_roi_pick_btn = QPushButton("Pick From Screen")
        self.aggro_roi_pick_btn.setToolTip("Pick the aggro bar region directly from your screen")
        self.aggro_roi_pick_btn.clicked.connect(self.on_pick_aggro_roi)
        roi_row.addWidget(self.aggro_roi_pick_btn)
        
        self.aggro_roi_clear_btn = QPushButton("Clear")
        self.aggro_roi_clear_btn.setToolTip("Remove the aggro bar region selection")
        self.aggro_roi_clear_btn.clicked.connect(self.on_clear_aggro_roi)
        roi_row.addWidget(self.aggro_roi_clear_btn)
        
        roi_layout.addLayout(roi_row)
        layout.addWidget(roi_group)
        
        # Aggro Bar Colors
        colors_group = QGroupBox("Aggro Bar Colors")
        colors_group.setToolTip("Configure colors for aggro bar detection")
        colors_layout = QVBoxLayout(colors_group)
        
        # Color 1
        color1_layout = QHBoxLayout()
        color1_layout.addWidget(QLabel("Color 1:"))
        self.color1_editor = ColorSpecEditor(self.config_manager, 'instance_aggro_bar_color1')
        color1_layout.addWidget(self.color1_editor)
        colors_layout.addLayout(color1_layout)
        
        # Color 2
        color2_layout = QHBoxLayout()
        color2_layout.addWidget(QLabel("Color 2:"))
        self.color2_editor = ColorSpecEditor(self.config_manager, 'instance_aggro_bar_color2')
        color2_layout.addWidget(self.color2_editor)
        colors_layout.addLayout(color2_layout)
        
        # Color 3
        color3_layout = QHBoxLayout()
        color3_layout.addWidget(QLabel("Color 3:"))
        self.color3_editor = ColorSpecEditor(self.config_manager, 'instance_aggro_bar_color3')
        color3_layout.addWidget(self.color3_editor)
        colors_layout.addLayout(color3_layout)
        
        layout.addWidget(colors_group)
        
        # Aggro Strategy
        strategy_row = QHBoxLayout()
        strategy_row.addWidget(QLabel("Aggro Strategy:"))
        self.aggro_strategy_combo = QComboBox()
        self.aggro_strategy_combo.addItems(["Detect Aggro Bar", "Legacy Timer", "Hybrid (Either)"])
        try:
            strat = str(self.config_manager.get('instance_aggro_strategy', 'bar')).lower()
        except Exception:
            strat = 'bar'
        idx = 0 if strat == 'bar' else (1 if strat == 'timer' else 2)
        self.aggro_strategy_combo.setCurrentIndex(idx)
        self.aggro_strategy_combo.setToolTip("Choose: Detect Aggro Bar (vision), Legacy Timer (fixed interval), or Hybrid (either triggers)")
        self.aggro_strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)
        strategy_row.addWidget(self.aggro_strategy_combo)
        strategy_row.addStretch()
        layout.addLayout(strategy_row)

        # Aggro potion coordinate selector
        self.aggro_potion_selector = CoordinateSelector(config_manager=self.config_manager, bot_controller=self.bot_controller)
        layout.addWidget(self.aggro_potion_selector)

        # Per-color minimum pixels threshold
        thr_row = QHBoxLayout()
        thr_row.addWidget(QLabel("Min pixels per color:"))
        self.aggro_min_pixels_spin = QSpinBox()
        self.aggro_min_pixels_spin.setRange(1, 1000)
        try:
            self.aggro_min_pixels_spin.setValue(int(self.config_manager.get('instance_aggro_min_pixels_per_color', 30)))
        except Exception:
            self.aggro_min_pixels_spin.setValue(30)
        thr_row.addWidget(self.aggro_min_pixels_spin)
        thr_row.addStretch()
        layout.addLayout(thr_row)
        
        # Legacy Mode Settings
        legacy_group = QGroupBox("Legacy Mode Settings")
        legacy_group.setToolTip("Configure Legacy Mode settings for aggro potion")
        legacy_layout = QVBoxLayout(legacy_group)
        
        # Aggro Interval
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Aggro Interval:"))
        self.aggro_interval_spin = QDoubleSpinBox()
        self.aggro_interval_spin.setRange(0.5, 60.0)
        self.aggro_interval_spin.setSingleStep(0.5)
        self.aggro_interval_spin.setValue(self.config_manager.get('instance_aggro_interval_min', 30.0))
        interval_layout.addWidget(self.aggro_interval_spin)
        interval_layout.addWidget(QLabel("minutes"))
        interval_layout.addStretch()
        legacy_layout.addLayout(interval_layout)
        
        # Start Delay
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Start Delay:"))
        self.start_delay_spin = QDoubleSpinBox()
        self.start_delay_spin.setRange(0.0, 60.0)
        self.start_delay_spin.setSingleStep(0.5)
        self.start_delay_spin.setValue(self.config_manager.get('instance_aggro_start_delay_s', 5.0))
        delay_layout.addWidget(self.start_delay_spin)
        delay_layout.addWidget(QLabel("seconds"))
        delay_layout.addStretch()
        legacy_layout.addLayout(delay_layout)
        
        # Jitter
        jitter_layout = QHBoxLayout()
        self.jitter_checkbox = QCheckBox("Enable Jitter")
        self.jitter_checkbox.setChecked(self.config_manager.get('instance_aggro_jitter_enabled', True))
        jitter_layout.addWidget(self.jitter_checkbox)
        jitter_layout.addWidget(QLabel("Jitter:"))
        self.jitter_spin = QSpinBox()
        self.jitter_spin.setRange(1, 50)
        self.jitter_spin.setValue(self.config_manager.get('instance_aggro_jitter_percent', 10))
        jitter_layout.addWidget(self.jitter_spin)
        jitter_layout.addWidget(QLabel("%"))
        jitter_layout.addStretch()
        legacy_layout.addLayout(jitter_layout)
        
        layout.addWidget(legacy_group)
    
    def _init_teleport_tab(self):
        """Initialize the Instance Teleport tab"""
        layout = QVBoxLayout(self.teleport_tab)
        
        # Post Teleport HP Wait
        wait_layout = QHBoxLayout()
        wait_layout.addWidget(QLabel("Post Teleport HP Wait:"))
        self.post_teleport_hp_wait_spin = QDoubleSpinBox()
        self.post_teleport_hp_wait_spin.setToolTip("Time to wait for HP bar to appear after teleporting")
        self.post_teleport_hp_wait_spin.setRange(0.1, 60.0)
        self.post_teleport_hp_wait_spin.setSingleStep(0.1)
        self.post_teleport_hp_wait_spin.setValue(self.config_manager.get('instance_post_teleport_hp_wait', 5.0))
        wait_layout.addWidget(self.post_teleport_hp_wait_spin)
        wait_layout.addWidget(QLabel("seconds"))
        wait_layout.addStretch()
        layout.addLayout(wait_layout)
        
        # Instance Entry Settings
        entry_group = QGroupBox("Instance Entry Settings")
        entry_group.setToolTip("Configure instance entry settings")
        entry_layout = QVBoxLayout(entry_group)
        
        # Token Location
        token_layout = QHBoxLayout()
        token_layout.addWidget(QLabel("Token Location:"))
        self.token_x_spin = QSpinBox()
        self.token_x_spin.setRange(0, 3000)
        self.token_x_spin.setValue(self.config_manager.get('instance_token_location', {}).get('x', 0))
        token_layout.addWidget(self.token_x_spin)
        token_layout.addWidget(QLabel("X"))
        self.token_y_spin = QSpinBox()
        self.token_y_spin.setRange(0, 3000)
        self.token_y_spin.setValue(self.config_manager.get('instance_token_location', {}).get('y', 0))
        token_layout.addWidget(self.token_y_spin)
        token_layout.addWidget(QLabel("Y"))
        self.token_pick_btn = QPushButton("Pick From Screen")
        self.token_pick_btn.clicked.connect(self.on_pick_token_location)
        token_layout.addWidget(self.token_pick_btn)
        token_layout.addStretch()
        entry_layout.addLayout(token_layout)
        
        # Teleport Location
        teleport_layout = QHBoxLayout()
        teleport_layout.addWidget(QLabel("Teleport Location:"))
        self.teleport_x_spin = QSpinBox()
        self.teleport_x_spin.setRange(0, 3000)
        self.teleport_x_spin.setValue(self.config_manager.get('instance_teleport_location', {}).get('x', 0))
        teleport_layout.addWidget(self.teleport_x_spin)
        teleport_layout.addWidget(QLabel("X"))
        self.teleport_y_spin = QSpinBox()
        self.teleport_y_spin.setRange(0, 3000)
        self.teleport_y_spin.setValue(self.config_manager.get('instance_teleport_location', {}).get('y', 0))
        teleport_layout.addWidget(self.teleport_y_spin)
        teleport_layout.addWidget(QLabel("Y"))
        self.teleport_pick_btn = QPushButton("Pick From Screen")
        self.teleport_pick_btn.clicked.connect(self.on_pick_teleport_location)
        teleport_layout.addWidget(self.teleport_pick_btn)
        teleport_layout.addStretch()
        entry_layout.addLayout(teleport_layout)
        
        # Token Delay
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Token Delay:"))
        self.token_delay_spin = QDoubleSpinBox()
        self.token_delay_spin.setRange(0.1, 10.0)
        self.token_delay_spin.setSingleStep(0.1)
        self.token_delay_spin.setValue(self.config_manager.get('instance_token_delay', 1.0))
        delay_layout.addWidget(self.token_delay_spin)
        delay_layout.addWidget(QLabel("seconds"))
        delay_layout.addStretch()
        entry_layout.addLayout(delay_layout)
        
        # Max Teleport Retries
        retries_layout = QHBoxLayout()
        retries_layout.addWidget(QLabel("Max Teleport Retries:"))
        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(1, 10)
        self.max_retries_spin.setValue(self.config_manager.get('instance_teleport_max_retries', 3))
        retries_layout.addWidget(self.max_retries_spin)
        retries_layout.addStretch()
        entry_layout.addLayout(retries_layout)
        
        layout.addWidget(entry_group)
    
    def _roi_text(self, roi):
        """Format ROI as text"""
        if not roi:
            return "Not set"
        return f"Left: {roi.get('left', 0)}, Top: {roi.get('top', 0)}, " \
               f"Width: {roi.get('width', 0)}, Height: {roi.get('height', 0)}"
    
    def on_pick_aggro_roi(self):
        """Pick aggro bar ROI from screen"""
        try:
            picker = AdvancedROISelector("Select Aggro Bar Region")
            if picker.exec_() == AdvancedROISelector.Accepted:
                roi = picker.get_roi()
                if roi:
                    self.config_manager.set('instance_aggro_bar_roi', roi)
                    self.aggro_roi_label.setText(self._roi_text(roi))
        except Exception as e:
            logger.error(f"Error picking aggro bar ROI: {e}")
    
    def on_clear_aggro_roi(self):
        """Clear aggro bar ROI"""
        self.config_manager.set('instance_aggro_bar_roi', None)
        self.aggro_roi_label.setText(self._roi_text(None))
    
    def on_pick_token_location(self):
        """Pick token location from screen"""
        try:
            from ..components.screen_picker import ZoomCoordinatePickerDialog
            picker = ZoomCoordinatePickerDialog("Select Instance Token Location")
            if picker.exec_() == ZoomCoordinatePickerDialog.Accepted:
                x, y = picker.get_coordinate()
                self.token_x_spin.setValue(x)
                self.token_y_spin.setValue(y)
        except Exception as e:
            logger.error(f"Error picking token location: {e}")
    
    def on_pick_teleport_location(self):
        """Pick teleport location from screen"""
        try:
            from ..components.screen_picker import ZoomCoordinatePickerDialog
            picker = ZoomCoordinatePickerDialog("Select Instance Teleport Location")
            if picker.exec_() == ZoomCoordinatePickerDialog.Accepted:
                x, y = picker.get_coordinate()
                self.teleport_x_spin.setValue(x)
                self.teleport_y_spin.setValue(y)
        except Exception as e:
            logger.error(f"Error picking teleport location: {e}")
    
    def _on_strategy_changed(self, index):
        """Handle aggro strategy change"""
        # Update UI based on selected strategy
        pass
    
    def on_apply_clicked(self):
        """Apply settings changes"""
        try:
            # Save instance mode settings
            self.config_manager.set('instance_only_mode', self.enable_checkbox.isChecked())
            self.config_manager.set('instance_hp_timeout_s', self.hp_timeout_spin.value())
            
            # Save aggro settings
            strat_idx = self.aggro_strategy_combo.currentIndex()
            strat = 'bar' if strat_idx == 0 else ('timer' if strat_idx == 1 else 'hybrid')
            self.config_manager.set('instance_aggro_strategy', strat)
            self.config_manager.set('instance_aggro_min_pixels_per_color', self.aggro_min_pixels_spin.value())
            self.config_manager.set('instance_aggro_interval_min', self.aggro_interval_spin.value())
            self.config_manager.set('instance_aggro_start_delay_s', self.start_delay_spin.value())
            self.config_manager.set('instance_aggro_jitter_enabled', self.jitter_checkbox.isChecked())
            self.config_manager.set('instance_aggro_jitter_percent', self.jitter_spin.value())
            
            # Save teleport settings
            self.config_manager.set('instance_post_teleport_hp_wait', self.post_teleport_hp_wait_spin.value())
            
            # Save token location
            token_location = {
                'x': self.token_x_spin.value(),
                'y': self.token_y_spin.value()
            }
            self.config_manager.set('instance_token_location', token_location)
            
            # Save teleport location
            teleport_location = {
                'x': self.teleport_x_spin.value(),
                'y': self.teleport_y_spin.value()
            }
            self.config_manager.set('instance_teleport_location', teleport_location)
            
            # Save other settings
            self.config_manager.set('instance_token_delay', self.token_delay_spin.value())
            self.config_manager.set('instance_teleport_max_retries', self.max_retries_spin.value())
            
            # Save aggro potion location from selector
            self.aggro_potion_selector.save_to_config('aggro_potion_location')
            
            logger.info("Instance mode settings saved")
            self.save_instance_mode_settings()
        except Exception as e:
            logger.error(f"Error applying instance mode settings: {e}")
    
    def on_reset_clicked(self):
        """Reset settings to defaults"""
        try:
            # Reset instance mode settings
            self.enable_checkbox.setChecked(False)
            self.hp_timeout_spin.setValue(60.0)
            
            # Reset aggro settings
            self.aggro_strategy_combo.setCurrentIndex(0)
            self.aggro_min_pixels_spin.setValue(30)
            self.aggro_interval_spin.setValue(30.0)
            self.start_delay_spin.setValue(5.0)
            self.jitter_checkbox.setChecked(True)
            self.jitter_spin.setValue(10)
            
            # Reset teleport settings
            self.post_teleport_hp_wait_spin.setValue(5.0)
            self.token_x_spin.setValue(0)
            self.token_y_spin.setValue(0)
            self.teleport_x_spin.setValue(0)
            self.teleport_y_spin.setValue(0)
            self.token_delay_spin.setValue(1.0)
            self.max_retries_spin.setValue(3)
            
            logger.info("Instance mode settings reset to defaults")
        except Exception as e:
            logger.error(f"Error resetting instance mode settings: {e}")
    
    def save_instance_mode_settings(self, silent=False):
        """Save all instance mode settings to config"""
        try:
            # Call on_apply_clicked to save all settings
            self.on_apply_clicked()
            if not silent:
                QMessageBox.information(self, "Settings Saved", "Instance mode settings have been saved.")
            return True
        except Exception as e:
            logger.error(f"Error saving instance mode settings: {e}")
            if not silent:
                QMessageBox.critical(self, "Error", f"Failed to save instance mode settings: {e}")
            return False