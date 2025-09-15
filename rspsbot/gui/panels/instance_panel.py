"""
Instance settings panel for RSPS Color Bot v3
"""
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QLineEdit,
    QMessageBox, QFrame, QTabWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette

from ...core.config import Coordinate, ROI, ColorSpec
from ..components.time_selector import TimeSelector
from ..components.tooltip_helper import TooltipHelper
from ..components.advanced_roi_selector import AdvancedROISelector
from ..components.enhanced_color_editor import EnhancedColorEditor
from .teleport_panel import CoordinateSelector

# Get module logger
logger = logging.getLogger('rspsbot.gui.panels.instance_panel')

class InstancePanel(QWidget):
    """
    Panel for instance settings with tabs for normal mode and instance-only mode
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
        
        # Load settings
        self.load_settings()
    
    def init_ui(self):
        """Initialize the UI components"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Normal mode tab
        self.normal_tab = QWidget()
        self.init_normal_tab()
        self.tab_widget.addTab(self.normal_tab, "Normal Mode")
        
        # Instance-Only Mode tab
        self.instance_only_tab = QWidget()
        self.init_instance_only_tab()
        self.tab_widget.addTab(self.instance_only_tab, "Instance-Only Mode")
        
        # Add stretch to push everything to the top
        main_layout.addStretch()
    
    def init_normal_tab(self):
        """Initialize the normal mode tab"""
        # Main layout
        normal_layout = QVBoxLayout(self.normal_tab)
        
        # Instance entry group
        entry_group = QGroupBox("Instance Entry")
        entry_layout = QVBoxLayout(entry_group)
        
        # Instance token
        token_group = QGroupBox("Instance Token")
        token_layout = QVBoxLayout(token_group)
        
        self.token_selector = CoordinateSelector()
        token_layout.addWidget(self.token_selector)
        
        entry_layout.addWidget(token_group)
        
        # Instance teleport
        teleport_group = QGroupBox("Instance Teleport")
        teleport_layout = QVBoxLayout(teleport_group)
        
        self.teleport_selector = CoordinateSelector()
        teleport_layout.addWidget(self.teleport_selector)
        
        # Delay
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay:"))
        
        # Use TimeSelector for delay
        self.token_delay_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('instance_token_delay', 1.0),
            mode=TimeSelector.MODE_SEC_ONLY,
            tooltip="Time to wait between clicking the instance token and the teleport spot"
        )
        delay_layout.addWidget(self.token_delay_selector)
        
        delay_layout.addStretch()
        
        teleport_layout.addLayout(delay_layout)
        
        entry_layout.addWidget(teleport_group)
        
        # Test button
        test_layout = QHBoxLayout()
        
        self.test_entry_button = QPushButton("Test Instance Entry")
        self.test_entry_button.clicked.connect(self.on_test_entry_clicked)
        TooltipHelper.add_tooltip(self.test_entry_button, "Test the instance entry sequence without actually executing it")
        test_layout.addWidget(self.test_entry_button)
        
        self.save_entry_button = QPushButton("Save Entry Settings")
        self.save_entry_button.clicked.connect(self.on_save_entry_clicked)
        TooltipHelper.add_tooltip(self.save_entry_button, "Save the instance entry settings")
        test_layout.addWidget(self.save_entry_button)
        
        entry_layout.addLayout(test_layout)
        
        normal_layout.addWidget(entry_group)
        
        # Aggro potion group
        aggro_group = QGroupBox("Aggro Potion")
        aggro_layout = QVBoxLayout(aggro_group)
        
        # Aggro potion location
        location_group = QGroupBox("Potion Location")
        location_layout = QVBoxLayout(location_group)
        
        self.aggro_selector = CoordinateSelector()
        location_layout.addWidget(self.aggro_selector)
        
        aggro_layout.addWidget(location_group)
        
        # Aggro duration
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Duration:"))
        
        # Use TimeSelector for duration
        self.aggro_duration_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('aggro_duration', 300.0),
            mode=TimeSelector.MODE_MIN_SEC,
            tooltip="Duration of the aggro potion effect"
        )
        duration_layout.addWidget(self.aggro_duration_selector)
        
        duration_layout.addStretch()
        
        aggro_layout.addLayout(duration_layout)
        
        # Aggro effect detection
        effect_group = QGroupBox("Effect Detection")
        effect_layout = QVBoxLayout(effect_group)
        
        # Enable visual check
        check_layout = QHBoxLayout()
        
        self.visual_check_checkbox = QCheckBox("Enable Visual Check")
        self.visual_check_checkbox.toggled.connect(self.on_visual_check_toggled)
        TooltipHelper.add_tooltip(self.visual_check_checkbox, "Enable visual detection of aggro potion effect")
        check_layout.addWidget(self.visual_check_checkbox)
        
        check_layout.addStretch()
        
        effect_layout.addLayout(check_layout)
        
        # Effect ROI
        self.roi_group = QGroupBox("Effect ROI")
        roi_layout = QVBoxLayout(self.roi_group)
        
        self.roi_selector = AdvancedROISelector(self.config_manager, title="")
        roi_layout.addWidget(self.roi_selector)
        
        effect_layout.addWidget(self.roi_group)
        
        # Effect color
        self.color_group = QGroupBox("Effect Color")
        color_layout = QVBoxLayout(self.color_group)
        
        self.color_editor = EnhancedColorEditor(self.config_manager, 'aggro_effect_color', title="")
        color_layout.addWidget(self.color_editor)
        
        effect_layout.addWidget(self.color_group)
        
        aggro_layout.addWidget(effect_group)
        
        # Test button
        aggro_test_layout = QHBoxLayout()
        
        self.test_aggro_button = QPushButton("Test Aggro Potion")
        self.test_aggro_button.clicked.connect(self.on_test_aggro_clicked)
        TooltipHelper.add_tooltip(self.test_aggro_button, "Test the aggro potion detection without actually using it")
        aggro_test_layout.addWidget(self.test_aggro_button)
        
        self.save_aggro_button = QPushButton("Save Aggro Settings")
        self.save_aggro_button.clicked.connect(self.on_save_aggro_clicked)
        TooltipHelper.add_tooltip(self.save_aggro_button, "Save the aggro potion settings")
        aggro_test_layout.addWidget(self.save_aggro_button)
        
        aggro_layout.addLayout(aggro_test_layout)
        
        normal_layout.addWidget(aggro_group)
    
    def init_instance_only_tab(self):
        """Initialize the Instance-Only Mode tab"""
        # Main layout
        instance_only_layout = QVBoxLayout(self.instance_only_tab)
        
        # Description
        description_label = QLabel(
            "Instance-Only Mode focuses solely on aggro potion and instance teleport mechanics, "
            "skipping tile and monster detection entirely. This mode is useful for simple AFK training."
        )
        description_label.setWordWrap(True)
        instance_only_layout.addWidget(description_label)
        
        # HP Bar Detection group
        hp_group = QGroupBox("HP Bar Detection")
        hp_layout = QVBoxLayout(hp_group)
        
        # HP Bar ROI
        self.instance_hp_roi_selector = AdvancedROISelector(
            self.config_manager,
            title="HP Bar Region"
        )
        TooltipHelper.add_tooltip(self.instance_hp_roi_selector, "Region where the HP bar appears during combat")
        hp_layout.addWidget(self.instance_hp_roi_selector)
        
        # HP Bar Color
        self.instance_hp_color_editor = EnhancedColorEditor(
            self.config_manager,
            'instance_hp_bar_color',
            title="HP Bar Color"
        )
        TooltipHelper.add_tooltip(self.instance_hp_color_editor, "Color of the HP bar to detect")
        hp_layout.addWidget(self.instance_hp_color_editor)
        
        # HP Bar Timeout
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("HP Bar Timeout:"))
        
        self.hp_timeout_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('instance_hp_timeout', 30.0),
            mode=TimeSelector.MODE_SEC_ONLY,
            tooltip="Time to wait after HP bar disappears before considering instance empty"
        )
        timeout_layout.addWidget(self.hp_timeout_selector)
        
        timeout_layout.addStretch()
        
        hp_layout.addLayout(timeout_layout)
        
        # Minimum pixel count
        min_pixels_layout = QHBoxLayout()
        min_pixels_layout.addWidget(QLabel("Min. Pixel Count:"))
        
        self.hp_min_pixels_spin = QSpinBox()
        self.hp_min_pixels_spin.setRange(1, 1000)
        self.hp_min_pixels_spin.setValue(self.config_manager.get('instance_hp_min_pixels', 50))
        TooltipHelper.add_tooltip(self.hp_min_pixels_spin, "Minimum number of matching pixels required to detect HP bar")
        min_pixels_layout.addWidget(self.hp_min_pixels_spin)
        
        min_pixels_layout.addStretch()
        
        hp_layout.addLayout(min_pixels_layout)
        
        instance_only_layout.addWidget(hp_group)
        
        # Aggro Potion group
        aggro_group = QGroupBox("Aggro Potion")
        aggro_layout = QVBoxLayout(aggro_group)
        
        # Aggro potion location
        self.instance_aggro_selector = CoordinateSelector()
        TooltipHelper.add_tooltip(self.instance_aggro_selector, "Location of the aggro potion in your inventory")
        aggro_layout.addWidget(self.instance_aggro_selector)
        
        # Visual check
        visual_check_layout = QHBoxLayout()
        
        self.instance_visual_check_checkbox = QCheckBox("Enable Visual Check")
        self.instance_visual_check_checkbox.toggled.connect(self.on_instance_visual_check_toggled)
        TooltipHelper.add_tooltip(self.instance_visual_check_checkbox, "Enable visual detection of aggro potion effect")
        visual_check_layout.addWidget(self.instance_visual_check_checkbox)
        
        visual_check_layout.addStretch()
        
        aggro_layout.addLayout(visual_check_layout)
        
        # Aggro effect ROI
        self.instance_aggro_roi_group = QGroupBox("Aggro Effect Region")
        aggro_roi_layout = QVBoxLayout(self.instance_aggro_roi_group)
        
        self.instance_aggro_roi_selector = AdvancedROISelector(self.config_manager, title="")
        TooltipHelper.add_tooltip(self.instance_aggro_roi_selector, "Region where the aggro potion effect appears")
        aggro_roi_layout.addWidget(self.instance_aggro_roi_selector)
        
        self.instance_aggro_roi_group.setLayout(aggro_roi_layout)
        aggro_layout.addWidget(self.instance_aggro_roi_group)
        
        # Aggro effect color
        self.instance_aggro_color_group = QGroupBox("Aggro Effect Color")
        aggro_color_layout = QVBoxLayout(self.instance_aggro_color_group)
        
        self.instance_aggro_color_editor = EnhancedColorEditor(self.config_manager, 'instance_aggro_effect_color', title="")
        TooltipHelper.add_tooltip(self.instance_aggro_color_editor, "Color of the aggro potion effect to detect")
        aggro_color_layout.addWidget(self.instance_aggro_color_editor)
        
        self.instance_aggro_color_group.setLayout(aggro_color_layout)
        aggro_layout.addWidget(self.instance_aggro_color_group)
        
        instance_only_layout.addWidget(aggro_group)
        
        # Instance Teleport group
        teleport_group = QGroupBox("Instance Teleport")
        teleport_layout = QVBoxLayout(teleport_group)
        
        # Instance token
        token_layout = QVBoxLayout()
        token_layout.addWidget(QLabel("Instance Token Location:"))
        
        self.instance_token_selector = CoordinateSelector()
        TooltipHelper.add_tooltip(self.instance_token_selector, "Location of the instance token in your inventory")
        token_layout.addWidget(self.instance_token_selector)
        
        teleport_layout.addLayout(token_layout)
        
        # Instance teleport
        teleport_option_layout = QVBoxLayout()
        teleport_option_layout.addWidget(QLabel("Instance Teleport Location:"))
        
        self.instance_teleport_selector = CoordinateSelector()
        TooltipHelper.add_tooltip(self.instance_teleport_selector, "Location of the teleport option in the menu")
        teleport_option_layout.addWidget(self.instance_teleport_selector)
        
        teleport_layout.addLayout(teleport_option_layout)
        
        # Delay between clicks
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Click Delay:"))
        
        self.instance_delay_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('instance_token_delay', 2.0),
            mode=TimeSelector.MODE_SEC_ONLY,
            tooltip="Time to wait between clicking the instance token and the teleport option"
        )
        delay_layout.addWidget(self.instance_delay_selector)
        
        delay_layout.addStretch()
        
        teleport_layout.addLayout(delay_layout)
        
        instance_only_layout.addWidget(teleport_group)
        
        # Save button
        save_layout = QHBoxLayout()
        
        self.save_instance_only_button = QPushButton("Save Instance-Only Settings")
        self.save_instance_only_button.clicked.connect(self.on_save_instance_only_clicked)
        TooltipHelper.add_tooltip(self.save_instance_only_button, "Save all Instance-Only Mode settings")
        save_layout.addWidget(self.save_instance_only_button)
        
        instance_only_layout.addLayout(save_layout)
    
    def load_settings(self):
        """Load settings from config"""
        # Normal mode settings
        
        # Instance token
        token_coord = self.config_manager.get_coordinate('instance_token_location')
        if token_coord:
            self.token_selector.set_coordinate(token_coord.x, token_coord.y)
        
        # Instance teleport
        teleport_coord = self.config_manager.get_coordinate('instance_teleport_location')
        if teleport_coord:
            self.teleport_selector.set_coordinate(teleport_coord.x, teleport_coord.y)
        
        # Token delay
        self.token_delay_selector.set_time(self.config_manager.get('instance_token_delay', 1.0))
        
        # Aggro potion
        aggro_coord = self.config_manager.get_coordinate('aggro_potion_location')
        if aggro_coord:
            self.aggro_selector.set_coordinate(aggro_coord.x, aggro_coord.y)
        
        # Aggro duration
        self.aggro_duration_selector.set_time(self.config_manager.get('aggro_duration', 300.0))
        
        # Visual check
        self.visual_check_checkbox.setChecked(self.config_manager.get('aggro_visual_check', True))
        
        # Effect ROI
        roi = self.config_manager.get_roi('aggro_effect_roi')
        if roi:
            self.roi_selector.set_roi(roi)
        
        # Update UI state
        self.on_visual_check_toggled(self.visual_check_checkbox.isChecked())
        
        # Instance-Only Mode settings
        
        # HP Bar ROI
        hp_roi = self.config_manager.get_roi('instance_hp_bar_roi')
        if hp_roi:
            self.instance_hp_roi_selector.set_roi(hp_roi)
        
        # HP Bar timeout
        self.hp_timeout_selector.set_time(self.config_manager.get('instance_hp_timeout', 30.0))
        
        # HP Bar min pixels
        self.hp_min_pixels_spin.setValue(self.config_manager.get('instance_hp_min_pixels', 50))
        
        # Aggro potion location
        instance_aggro_coord = self.config_manager.get_coordinate('instance_aggro_potion_location')
        if instance_aggro_coord:
            self.instance_aggro_selector.set_coordinate(instance_aggro_coord.x, instance_aggro_coord.y)
        
        # Visual check
        self.instance_visual_check_checkbox.setChecked(self.config_manager.get('instance_aggro_visual_check', True))
        
        # Aggro effect ROI
        instance_aggro_roi = self.config_manager.get_roi('instance_aggro_effect_roi')
        if instance_aggro_roi:
            self.instance_aggro_roi_selector.set_roi(instance_aggro_roi)
        
        # Instance token location
        instance_token_coord = self.config_manager.get_coordinate('instance_token_location')
        if instance_token_coord:
            self.instance_token_selector.set_coordinate(instance_token_coord.x, instance_token_coord.y)
        
        # Instance teleport location
        instance_teleport_coord = self.config_manager.get_coordinate('instance_teleport_location')
        if instance_teleport_coord:
            self.instance_teleport_selector.set_coordinate(instance_teleport_coord.x, instance_teleport_coord.y)
        
        # Instance delay
        self.instance_delay_selector.set_time(self.config_manager.get('instance_token_delay', 2.0))
        
        # Update UI state
        self.on_instance_visual_check_toggled(self.instance_visual_check_checkbox.isChecked())
    
    def on_visual_check_toggled(self, checked):
        """Handle visual check checkbox toggle"""
        self.roi_group.setEnabled(checked)
        self.color_group.setEnabled(checked)
        self.config_manager.set('aggro_visual_check', checked)
    
    def on_instance_visual_check_toggled(self, checked):
        """Handle instance visual check checkbox toggle"""
        self.instance_aggro_roi_group.setEnabled(checked)
        self.instance_aggro_color_group.setEnabled(checked)
        self.config_manager.set('instance_aggro_visual_check', checked)
    
    def on_test_entry_clicked(self):
        """Handle test entry button click"""
        token_x, token_y = self.token_selector.get_coordinate()
        teleport_x, teleport_y = self.teleport_selector.get_coordinate()
        
        if token_x == 0 and token_y == 0:
            QMessageBox.warning(self, "Warning", "Instance token location not set")
            return
        
        if teleport_x == 0 and teleport_y == 0:
            QMessageBox.warning(self, "Warning", "Instance teleport location not set")
            return
        
        # Get delay in minutes and seconds for display
        delay_seconds = self.token_delay_selector.get_time()
        delay_minutes = int(delay_seconds // 60)
        delay_secs = int(delay_seconds % 60)
        delay_str = f"{delay_minutes} min {delay_secs} sec" if delay_minutes > 0 else f"{delay_secs} sec"
        
        QMessageBox.information(
            self,
            "Test Instance Entry",
            f"Instance entry sequence will be executed:\n\n"
            f"1. Click instance token at ({token_x}, {token_y})\n"
            f"2. Wait {delay_str}\n"
            f"3. Click teleport at ({teleport_x}, {teleport_y})\n\n"
            "Note: This is just a test. The actual entry will not be executed."
        )
    
    def on_save_entry_clicked(self):
        """Handle save entry button click"""
        try:
            # Get values
            token_x, token_y = self.token_selector.get_coordinate()
            teleport_x, teleport_y = self.teleport_selector.get_coordinate()
            token_delay = self.token_delay_selector.get_time()
            
            # Create coordinates
            token_coord = Coordinate(token_x, token_y, "Instance Token")
            teleport_coord = Coordinate(teleport_x, teleport_y, "Instance Teleport")
            
            # Save to config
            self.config_manager.set_coordinate('instance_token_location', token_coord)
            self.config_manager.set_coordinate('instance_teleport_location', teleport_coord)
            self.config_manager.set('instance_token_delay', token_delay)
            
            QMessageBox.information(
                self,
                "Settings Saved",
                "Instance entry settings saved successfully."
            )
        
        except Exception as e:
            logger.error(f"Error saving instance entry settings: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Error saving instance entry settings: {e}"
            )
    
    def on_test_aggro_clicked(self):
        """Handle test aggro button click"""
        aggro_x, aggro_y = self.aggro_selector.get_coordinate()
        
        if aggro_x == 0 and aggro_y == 0:
            QMessageBox.warning(self, "Warning", "Aggro potion location not set")
            return
        
        # Get duration in minutes and seconds for display
        duration_seconds = self.aggro_duration_selector.get_time()
        duration_minutes = int(duration_seconds // 60)
        duration_secs = int(duration_seconds % 60)
        duration_str = f"{duration_minutes} min {duration_secs} sec" if duration_minutes > 0 else f"{duration_secs} sec"
        
        QMessageBox.information(
            self,
            "Test Aggro Potion",
            f"Aggro potion will be used at ({aggro_x}, {aggro_y}).\n\n"
            f"Duration: {duration_str}\n\n"
            "Note: This is just a test. The actual potion will not be used."
        )
    
    def on_save_aggro_clicked(self):
        """Handle save aggro button click"""
        try:
            # Get values
            aggro_x, aggro_y = self.aggro_selector.get_coordinate()
            aggro_duration = self.aggro_duration_selector.get_time()
            visual_check = self.visual_check_checkbox.isChecked()
            
            # Create coordinate
            aggro_coord = Coordinate(aggro_x, aggro_y, "Aggro Potion")
            
            # Save to config
            self.config_manager.set_coordinate('aggro_potion_location', aggro_coord)
            self.config_manager.set('aggro_duration', aggro_duration)
            self.config_manager.set('aggro_visual_check', visual_check)
            
            # Save ROI if visual check is enabled
            if visual_check:
                roi = self.roi_selector.get_roi()
                self.config_manager.set_roi('aggro_effect_roi', roi)
                
                # Color is saved automatically by the ColorSpecEditor
            
            QMessageBox.information(
                self,
                "Settings Saved",
                "Aggro potion settings saved successfully."
            )
        
        except Exception as e:
            logger.error(f"Error saving aggro potion settings: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Error saving aggro potion settings: {e}"
            )
    
    def on_save_instance_only_clicked(self):
        """Handle save instance-only button click"""
        try:
            # Save HP Bar settings
            hp_roi = self.instance_hp_roi_selector.get_roi()
            self.config_manager.set_roi('instance_hp_bar_roi', hp_roi)
            
            # HP Bar color is saved automatically by the ColorSpecEditor
            
            # HP Bar timeout
            hp_timeout = self.hp_timeout_selector.get_time()
            self.config_manager.set('instance_hp_timeout', hp_timeout)
            
            # HP Bar min pixels
            hp_min_pixels = self.hp_min_pixels_spin.value()
            self.config_manager.set('instance_hp_min_pixels', hp_min_pixels)
            
            # Aggro potion location
            aggro_x, aggro_y = self.instance_aggro_selector.get_coordinate()
            aggro_coord = Coordinate(aggro_x, aggro_y, "Instance Aggro Potion")
            self.config_manager.set_coordinate('instance_aggro_potion_location', aggro_coord)
            
            # Visual check
            visual_check = self.instance_visual_check_checkbox.isChecked()
            self.config_manager.set('instance_aggro_visual_check', visual_check)
            
            # Aggro effect ROI
            if visual_check:
                aggro_roi = self.instance_aggro_roi_selector.get_roi()
                self.config_manager.set_roi('instance_aggro_effect_roi', aggro_roi)
                
                # Color is saved automatically by the ColorSpecEditor
            
            # Instance token location
            token_x, token_y = self.instance_token_selector.get_coordinate()
            token_coord = Coordinate(token_x, token_y, "Instance Token")
            self.config_manager.set_coordinate('instance_token_location', token_coord)
            
            # Instance teleport location
            teleport_x, teleport_y = self.instance_teleport_selector.get_coordinate()
            teleport_coord = Coordinate(teleport_x, teleport_y, "Instance Teleport")
            self.config_manager.set_coordinate('instance_teleport_location', teleport_coord)
            
            # Instance delay
            token_delay = self.instance_delay_selector.get_time()
            self.config_manager.set('instance_token_delay', token_delay)
            
            QMessageBox.information(
                self,
                "Settings Saved",
                "Instance-Only Mode settings saved successfully."
            )
        
        except Exception as e:
            logger.error(f"Error saving Instance-Only Mode settings: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Error saving Instance-Only Mode settings: {e}"
            )