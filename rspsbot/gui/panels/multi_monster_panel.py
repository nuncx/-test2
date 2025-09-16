"""
Multi Monster Mode panel for RSPS Color Bot v3
"""
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox, QGridLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt5.QtCore import Qt

from .detection_panel import ColorSpecEditor
from ..components.screen_picker import ZoomRoiPickerDialog
from ..components.enhanced_color_editor import EnhancedColorEditor
from ..components.advanced_roi_selector import AdvancedROISelector
from ...core.config import Coordinate

# Get module logger
logger = logging.getLogger('rspsbot.gui.panels.multi_monster_panel')

class MultiMonsterPanel(QWidget):
    """
    Panel for Multi Monster Mode settings
    """
    
    def __init__(self, config_manager, bot_controller):
        """
        Initialize the multi monster panel
        
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
        # Main layout and tabs container
        main_layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        main_layout.addWidget(self._tabs)

        # ---------- General Settings sub-tab ----------
        self.general_tab = QWidget()
        general_layout = QVBoxLayout(self.general_tab)

        # Enable Multi Monster Mode
        mode_group = QGroupBox("Mode Settings")
        mode_group.setToolTip(
            "Enable Multi Monster Mode to handle different monster types with different combat styles"
        )
        mode_layout = QVBoxLayout(mode_group)
        
        self.enable_checkbox = QCheckBox("Enable Multi Monster Mode")
        self.enable_checkbox.setToolTip(
            "When enabled, the bot will detect monster types and switch combat styles accordingly"
        )
        self.enable_checkbox.setChecked(self.config_manager.get('multi_monster_mode_enabled', False))
        self.enable_checkbox.toggled.connect(self.on_mode_toggled)
        mode_layout.addWidget(self.enable_checkbox)
        
        # Post-attack wait time
        wait_layout = QHBoxLayout()
        wait_layout.addWidget(QLabel("Post-attack Wait Time:"))
        self.wait_time_spin = QDoubleSpinBox()
        self.wait_time_spin.setToolTip(
            "Time to wait after attacking before checking for new monsters"
        )
        self.wait_time_spin.setRange(0.1, 60.0)
        self.wait_time_spin.setSingleStep(0.1)
        self.wait_time_spin.setValue(self.config_manager.get('multi_monster_post_attack_wait', 2.0))
        wait_layout.addWidget(self.wait_time_spin)
        wait_layout.addWidget(QLabel("seconds"))
        wait_layout.addStretch()
        mode_layout.addLayout(wait_layout)
        
        general_layout.addWidget(mode_group)

        # Tile ROI Settings
        tile_roi_group = QGroupBox("Tile ROI Settings")
        tile_roi_group.setToolTip("Define the region where the bot will search for tiles")
        tile_roi_layout = QVBoxLayout(tile_roi_group)
        
        roi_row = QHBoxLayout()
        self.tile_roi_label = QLabel(self._roi_text(self.config_manager.get('tile_search_roi')))
        roi_row.addWidget(self.tile_roi_label)
        roi_row.addStretch()
        
        self.tile_roi_pick_btn = QPushButton("Pick From Screen")
        self.tile_roi_pick_btn.setToolTip("Pick the tile search region directly from your screen")
        self.tile_roi_pick_btn.clicked.connect(self.on_pick_tile_roi)
        roi_row.addWidget(self.tile_roi_pick_btn)
        
        self.tile_roi_clear_btn = QPushButton("Clear")
        self.tile_roi_clear_btn.setToolTip("Remove the tile search region selection")
        self.tile_roi_clear_btn.clicked.connect(self.on_clear_tile_roi)
        roi_row.addWidget(self.tile_roi_clear_btn)
        
        tile_roi_layout.addLayout(roi_row)
        general_layout.addWidget(tile_roi_group)

        # Precision Mode Settings
        precision_group = QGroupBox("Precision Mode Settings")
        precision_group.setToolTip("Configure detection precision for different scenarios")
        precision_layout = QVBoxLayout(precision_group)
        
        precision_row = QHBoxLayout()
        precision_row.addWidget(QLabel("Detection Precision:"))
        self.precision_combo = QComboBox()
        self.precision_combo.addItems(["Normal", "Accurate", "Non-Accurate"])
        self.precision_combo.setCurrentText(self.config_manager.get('multi_monster_precision_mode', "Normal"))
        self.precision_combo.currentTextChanged.connect(self.on_precision_changed)
        precision_row.addWidget(self.precision_combo)
        precision_row.addStretch()
        precision_layout.addLayout(precision_row)
        
        # Precision parameters
        params_layout = QGridLayout()
        params_layout.addWidget(QLabel("Lab Tolerance:"), 0, 0)
        self.lab_tolerance_spin = QSpinBox()
        self.lab_tolerance_spin.setRange(5, 30)
        self.lab_tolerance_spin.setValue(self.config_manager.get('multi_monster_lab_tolerance', 15))
        params_layout.addWidget(self.lab_tolerance_spin, 0, 1)
        
        params_layout.addWidget(QLabel("Saturation Min:"), 0, 2)
        self.sat_min_spin = QSpinBox()
        self.sat_min_spin.setRange(0, 100)
        self.sat_min_spin.setValue(self.config_manager.get('multi_monster_sat_min', 50))
        params_layout.addWidget(self.sat_min_spin, 0, 3)
        
        params_layout.addWidget(QLabel("Value Min:"), 1, 0)
        self.val_min_spin = QSpinBox()
        self.val_min_spin.setRange(0, 100)
        self.val_min_spin.setValue(self.config_manager.get('multi_monster_val_min', 50))
        params_layout.addWidget(self.val_min_spin, 1, 1)
        
        params_layout.addWidget(QLabel("Morph Open:"), 1, 2)
        self.morph_open_spin = QSpinBox()
        self.morph_open_spin.setRange(0, 5)
        self.morph_open_spin.setValue(self.config_manager.get('multi_monster_morph_open_iters', 1))
        params_layout.addWidget(self.morph_open_spin, 1, 3)
        
        params_layout.addWidget(QLabel("Morph Close:"), 2, 0)
        self.morph_close_spin = QSpinBox()
        self.morph_close_spin.setRange(0, 5)
        self.morph_close_spin.setValue(self.config_manager.get('multi_monster_morph_close_iters', 2))
        params_layout.addWidget(self.morph_close_spin, 2, 1)
        
        precision_layout.addLayout(params_layout)
        general_layout.addWidget(precision_group)

        # Overlay Settings
        overlay_group = QGroupBox("Overlay Settings")
        overlay_group.setToolTip("Configure visual overlays for debugging")
        overlay_layout = QVBoxLayout(overlay_group)
        
        self.overlay_checkbox = QCheckBox("Enable Detection Overlays")
        self.overlay_checkbox.setToolTip("Show visual overlays for tiles, monsters, and combat styles")
        self.overlay_checkbox.setChecked(self.config_manager.get('multi_monster_overlay_enabled', False))
        overlay_layout.addWidget(self.overlay_checkbox)
        
        general_layout.addWidget(overlay_group)

        # Apply/Reset buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.clicked.connect(self.on_apply_clicked)
        buttons_layout.addWidget(self.apply_btn)
        
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self.on_reset_clicked)
        buttons_layout.addWidget(self.reset_btn)
        
        general_layout.addLayout(buttons_layout)
        general_layout.addStretch()
        
        # Add the general tab
        self._tabs.addTab(self.general_tab, "General Settings")

        # ---------- Monster Configuration sub-tab ----------
        self.monsters_tab = QWidget()
        monsters_layout = QVBoxLayout(self.monsters_tab)
        
        # Monster Table
        monsters_group = QGroupBox("Monster Configuration")
        monsters_group.setToolTip("Configure monster types and their associated combat styles")
        monsters_layout_inner = QVBoxLayout(monsters_group)
        
        self.monsters_table = QTableWidget(3, 3)  # 3 rows, 3 columns
        self.monsters_table.setHorizontalHeaderLabels(["Monster Color", "Combat Style", "Actions"])
        self.monsters_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.monsters_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.monsters_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        
        # Initialize monster table
        self._init_monster_table()
        
        monsters_layout_inner.addWidget(self.monsters_table)
        monsters_layout.addWidget(monsters_group)
        
        # Apply/Reset buttons for monsters tab
        monsters_buttons_layout = QHBoxLayout()
        monsters_buttons_layout.addStretch()
        
        self.monsters_apply_btn = QPushButton("Apply Changes")
        self.monsters_apply_btn.clicked.connect(self.on_monsters_apply_clicked)
        monsters_buttons_layout.addWidget(self.monsters_apply_btn)
        
        self.monsters_reset_btn = QPushButton("Reset to Defaults")
        self.monsters_reset_btn.clicked.connect(self.on_monsters_reset_clicked)
        monsters_buttons_layout.addWidget(self.monsters_reset_btn)
        
        monsters_layout.addLayout(monsters_buttons_layout)
        monsters_layout.addStretch()
        
        # Add the monsters tab
        self._tabs.addTab(self.monsters_tab, "Monster Configuration")

        # ---------- Weapon Configuration sub-tab ----------
        self.weapons_tab = QWidget()
        weapons_layout = QVBoxLayout(self.weapons_tab)
        
        # Weapon ROI
        weapon_roi_group = QGroupBox("Weapon ROI")
        weapon_roi_group.setToolTip("Define the region where the bot will look for equipped weapons")
        weapon_roi_layout = QVBoxLayout(weapon_roi_group)
        
        weapon_roi_row = QHBoxLayout()
        self.weapon_roi_label = QLabel(self._roi_text(self.config_manager.get('weapon_roi')))
        weapon_roi_row.addWidget(self.weapon_roi_label)
        weapon_roi_row.addStretch()
        
        self.weapon_roi_pick_btn = QPushButton("Pick From Screen")
        self.weapon_roi_pick_btn.setToolTip("Pick the weapon detection region directly from your screen")
        self.weapon_roi_pick_btn.clicked.connect(self.on_pick_weapon_roi)
        weapon_roi_row.addWidget(self.weapon_roi_pick_btn)
        
        self.weapon_roi_clear_btn = QPushButton("Clear")
        self.weapon_roi_clear_btn.setToolTip("Remove the weapon detection region selection")
        self.weapon_roi_clear_btn.clicked.connect(self.on_clear_weapon_roi)
        weapon_roi_row.addWidget(self.weapon_roi_clear_btn)
        
        weapon_roi_layout.addLayout(weapon_roi_row)
        weapons_layout.addWidget(weapon_roi_group)
        
        # Weapon Colors
        weapon_colors_group = QGroupBox("Weapon Colors")
        weapon_colors_group.setToolTip("Configure colors for different weapon types")
        weapon_colors_layout = QVBoxLayout(weapon_colors_group)
        
        # Melee weapon color
        melee_layout = QHBoxLayout()
        melee_layout.addWidget(QLabel("Melee Weapon Color:"))
        self.melee_weapon_color_editor = ColorSpecEditor(self.config_manager, 'multi_monster_melee_weapon_color')
        melee_layout.addWidget(self.melee_weapon_color_editor)
        weapon_colors_layout.addLayout(melee_layout)
        
        # Ranged weapon color
        ranged_layout = QHBoxLayout()
        ranged_layout.addWidget(QLabel("Ranged Weapon Color:"))
        self.ranged_weapon_color_editor = ColorSpecEditor(self.config_manager, 'multi_monster_ranged_weapon_color')
        ranged_layout.addWidget(self.ranged_weapon_color_editor)
        weapon_colors_layout.addLayout(ranged_layout)
        
        # Magic weapon color
        magic_layout = QHBoxLayout()
        magic_layout.addWidget(QLabel("Magic Weapon Color:"))
        self.magic_weapon_color_editor = ColorSpecEditor(self.config_manager, 'multi_monster_magic_weapon_color')
        magic_layout.addWidget(self.magic_weapon_color_editor)
        weapon_colors_layout.addLayout(magic_layout)
        
        weapons_layout.addWidget(weapon_colors_group)
        
        # Apply/Reset buttons for weapons tab
        weapons_buttons_layout = QHBoxLayout()
        weapons_buttons_layout.addStretch()
        
        self.weapons_apply_btn = QPushButton("Apply Changes")
        self.weapons_apply_btn.clicked.connect(self.on_weapons_apply_clicked)
        weapons_buttons_layout.addWidget(self.weapons_apply_btn)
        
        self.weapons_reset_btn = QPushButton("Reset to Defaults")
        self.weapons_reset_btn.clicked.connect(self.on_weapons_reset_clicked)
        weapons_buttons_layout.addWidget(self.weapons_reset_btn)
        
        weapons_layout.addLayout(weapons_buttons_layout)
        weapons_layout.addStretch()
        
        # Add the weapons tab
        self._tabs.addTab(self.weapons_tab, "Weapon Configuration")
    
    def _init_monster_table(self):
        """Initialize the monster configuration table"""
        monster_configs = self.config_manager.get('multi_monster_configs', [
            {'color': {'rgb': [255, 0, 0], 'tol_rgb': 15}, 'style': 'melee'},
            {'color': {'rgb': [0, 255, 0], 'tol_rgb': 15}, 'style': 'ranged'},
            {'color': {'rgb': [0, 0, 255], 'tol_rgb': 15}, 'style': 'magic'}
        ])
        
        for i, config in enumerate(monster_configs[:3]):  # Limit to 3 monsters
            # Color editor
            color_editor = ColorSpecEditor(self.config_manager, f'temp_monster_{i}_color')
            if 'color' in config:
                color_editor.set_color_spec(config['color'])
            self.monsters_table.setCellWidget(i, 0, color_editor)
            
            # Combat style combo
            style_combo = QComboBox()
            style_combo.addItems(['melee', 'ranged', 'magic'])
            if 'style' in config:
                style_combo.setCurrentText(config['style'])
            self.monsters_table.setCellWidget(i, 1, style_combo)
            
            # Test button
            test_btn = QPushButton("Test Detection")
            test_btn.clicked.connect(lambda checked, row=i: self.on_test_monster_detection(row))
            self.monsters_table.setCellWidget(i, 2, test_btn)
    
    def _roi_text(self, roi):
        """Format ROI as text"""
        if not roi:
            return "Not set"
        return f"Left: {roi.get('left', 0)}, Top: {roi.get('top', 0)}, " \
               f"Width: {roi.get('width', 0)}, Height: {roi.get('height', 0)}"
    
    def on_mode_toggled(self, checked):
        """Handle mode toggle"""
        # Update UI elements based on mode state
        pass
    
    def on_precision_changed(self, text):
        """Handle precision mode change"""
        # Set default values based on precision mode
        if text == "Accurate":
            self.lab_tolerance_spin.setValue(10)
            self.sat_min_spin.setValue(60)
            self.val_min_spin.setValue(60)
            self.morph_open_spin.setValue(1)
            self.morph_close_spin.setValue(2)
        elif text == "Non-Accurate":
            self.lab_tolerance_spin.setValue(20)
            self.sat_min_spin.setValue(30)
            self.val_min_spin.setValue(30)
            self.morph_open_spin.setValue(0)
            self.morph_close_spin.setValue(1)
        else:  # Normal
            self.lab_tolerance_spin.setValue(15)
            self.sat_min_spin.setValue(50)
            self.val_min_spin.setValue(50)
            self.morph_open_spin.setValue(1)
            self.morph_close_spin.setValue(2)
    
    def on_pick_tile_roi(self):
        """Pick tile search ROI from screen"""
        try:
            picker = AdvancedROISelector("Select Tile Search Region")
            if picker.exec_() == AdvancedROISelector.Accepted:
                roi = picker.get_roi()
                if roi:
                    self.config_manager.set('tile_search_roi', roi)
                    self.tile_roi_label.setText(self._roi_text(roi))
        except Exception as e:
            logger.error(f"Error picking tile ROI: {e}")
    
    def on_clear_tile_roi(self):
        """Clear tile search ROI"""
        self.config_manager.set('tile_search_roi', None)
        self.tile_roi_label.setText(self._roi_text(None))
    
    def on_pick_weapon_roi(self):
        """Pick weapon detection ROI from screen"""
        try:
            picker = AdvancedROISelector("Select Weapon Detection Region")
            if picker.exec_() == AdvancedROISelector.Accepted:
                roi = picker.get_roi()
                if roi:
                    self.config_manager.set('weapon_roi', roi)
                    self.weapon_roi_label.setText(self._roi_text(roi))
        except Exception as e:
            logger.error(f"Error picking weapon ROI: {e}")
    
    def on_clear_weapon_roi(self):
        """Clear weapon detection ROI"""
        self.config_manager.set('weapon_roi', None)
        self.weapon_roi_label.setText(self._roi_text(None))
    
    def on_test_monster_detection(self, row):
        """Test monster detection for the specified row"""
        try:
            color_editor = self.monsters_table.cellWidget(row, 0)
            if color_editor:
                color_spec = color_editor.get_color_spec()
                # Implement test detection logic here
                QMessageBox.information(self, "Test Detection", 
                                       f"Testing detection for monster {row+1}\n"
                                       f"Color: RGB{color_spec.rgb}, Tolerance: {color_spec.tol_rgb}")
        except Exception as e:
            logger.error(f"Error testing monster detection: {e}")
    
    def on_apply_clicked(self):
        """Apply general settings changes"""
        try:
            # Save general settings
            self.config_manager.set('multi_monster_mode_enabled', self.enable_checkbox.isChecked())
            self.config_manager.set('multi_monster_post_attack_wait', self.wait_time_spin.value())
            self.config_manager.set('multi_monster_precision_mode', self.precision_combo.currentText())
            self.config_manager.set('multi_monster_lab_tolerance', self.lab_tolerance_spin.value())
            self.config_manager.set('multi_monster_sat_min', self.sat_min_spin.value())
            self.config_manager.set('multi_monster_val_min', self.val_min_spin.value())
            self.config_manager.set('multi_monster_morph_open_iters', self.morph_open_spin.value())
            self.config_manager.set('multi_monster_morph_close_iters', self.morph_close_spin.value())
            self.config_manager.set('multi_monster_overlay_enabled', self.overlay_checkbox.isChecked())
            
            QMessageBox.information(self, "Settings Saved", "Multi Monster Mode general settings have been saved.")
        except Exception as e:
            logger.error(f"Error applying settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")
    
    def on_reset_clicked(self):
        """Reset general settings to defaults"""
        try:
            # Reset to defaults
            self.enable_checkbox.setChecked(False)
            self.wait_time_spin.setValue(2.0)
            self.precision_combo.setCurrentText("Normal")
            self.lab_tolerance_spin.setValue(15)
            self.sat_min_spin.setValue(50)
            self.val_min_spin.setValue(50)
            self.morph_open_spin.setValue(1)
            self.morph_close_spin.setValue(2)
            self.overlay_checkbox.setChecked(False)
            
            QMessageBox.information(self, "Settings Reset", "Multi Monster Mode general settings have been reset to defaults.")
        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to reset settings: {e}")
    
    def on_monsters_apply_clicked(self):
        """Apply monster configuration changes"""
        try:
            monster_configs = []
            for i in range(3):  # 3 monsters
                color_editor = self.monsters_table.cellWidget(i, 0)
                style_combo = self.monsters_table.cellWidget(i, 1)
                
                if color_editor and style_combo:
                    monster_configs.append({
                        'color': color_editor.get_color_spec().__dict__,
                        'style': style_combo.currentText()
                    })
            
            self.config_manager.set('multi_monster_configs', monster_configs)
            QMessageBox.information(self, "Settings Saved", "Monster configurations have been saved.")
        except Exception as e:
            logger.error(f"Error applying monster settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save monster settings: {e}")
    
    def on_monsters_reset_clicked(self):
        """Reset monster configurations to defaults"""
        try:
            # Reset to defaults
            default_configs = [
                {'color': {'rgb': [255, 0, 0], 'tol_rgb': 15, 'use_hsv': True, 'tol_h': 5, 'tol_s': 40, 'tol_v': 40}, 'style': 'melee'},
                {'color': {'rgb': [0, 255, 0], 'tol_rgb': 15, 'use_hsv': True, 'tol_h': 5, 'tol_s': 40, 'tol_v': 40}, 'style': 'ranged'},
                {'color': {'rgb': [0, 0, 255], 'tol_rgb': 15, 'use_hsv': True, 'tol_h': 5, 'tol_s': 40, 'tol_v': 40}, 'style': 'magic'}
            ]
            
            self.config_manager.set('multi_monster_configs', default_configs)
            self._init_monster_table()  # Reinitialize the table
            
            QMessageBox.information(self, "Settings Reset", "Monster configurations have been reset to defaults.")
        except Exception as e:
            logger.error(f"Error resetting monster settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to reset monster settings: {e}")
    
    def on_weapons_apply_clicked(self):
        """Apply weapon configuration changes"""
        try:
            # Save weapon colors
            self.config_manager.set('multi_monster_melee_weapon_color', self.melee_weapon_color_editor.get_color_spec().__dict__)
            self.config_manager.set('multi_monster_ranged_weapon_color', self.ranged_weapon_color_editor.get_color_spec().__dict__)
            self.config_manager.set('multi_monster_magic_weapon_color', self.magic_weapon_color_editor.get_color_spec().__dict__)
            
            QMessageBox.information(self, "Settings Saved", "Weapon configurations have been saved.")
        except Exception as e:
            logger.error(f"Error applying weapon settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save weapon settings: {e}")
    
    def on_weapons_reset_clicked(self):
        """Reset weapon configurations to defaults"""
        try:
            # Reset to defaults
            default_melee = {'rgb': (5, 5, 10), 'tol_rgb': 20, 'use_hsv': True, 'tol_h': 3, 'tol_s': 25, 'tol_v': 25}
            default_ranged = {'rgb': (255, 0, 0), 'tol_rgb': 20, 'use_hsv': True, 'tol_h': 3, 'tol_s': 25, 'tol_v': 25}
            default_magic = {'rgb': (99, 35, 52), 'tol_rgb': 20, 'use_hsv': True, 'tol_h': 3, 'tol_s': 25, 'tol_v': 25}
            
            self.config_manager.set('multi_monster_melee_weapon_color', default_melee)
            self.config_manager.set('multi_monster_ranged_weapon_color', default_ranged)
            self.config_manager.set('multi_monster_magic_weapon_color', default_magic)
            
            self.melee_weapon_color_editor.set_color_spec(default_melee)
            self.ranged_weapon_color_editor.set_color_spec(default_ranged)
            self.magic_weapon_color_editor.set_color_spec(default_magic)
            
            QMessageBox.information(self, "Settings Reset", "Weapon configurations have been reset to defaults.")
        except Exception as e:
            logger.error(f"Error resetting weapon settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to reset weapon settings: {e}")