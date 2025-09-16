"""
Combat settings panel for RSPS Color Bot v3
"""
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox, QGridLayout,
    QTabWidget
)
from PyQt5.QtCore import Qt

from .detection_panel import ColorSpecEditor
from ..components.screen_picker import ZoomRoiPickerDialog
from ..components.enhanced_color_editor import EnhancedColorEditor
from ..components.advanced_roi_selector import AdvancedROISelector
# from ..components.overlay import AggroOverlay  # no longer used; debug overlay is used instead
from .teleport_panel import CoordinateSelector
from ...core.config import Coordinate

# Get module logger
logger = logging.getLogger('rspsbot.gui.panels.combat_panel')

class CombatPanel(QWidget):
    """
    Panel for combat settings
    """
    
    def __init__(self, config_manager, bot_controller):
        """
        Initialize the combat panel
        
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
        self._combat_tabs = QTabWidget()
        main_layout.addWidget(self._combat_tabs)

        # ---------- General sub-tab ----------
        self.general_tab = QWidget()
        general_layout = QVBoxLayout(self.general_tab)

        # HP Bar Detection
        hpbar_group = QGroupBox("HP Bar Detection")
        hpbar_group.setToolTip(
            "Enable and tune HP bar detection. Used to confirm combat and for post-attack checks."
        )
        hpbar_layout = QVBoxLayout(hpbar_group)
        enable_layout = QHBoxLayout()
        self.hpbar_detect_checkbox = QCheckBox("Enable HP Bar Detection")
        self.hpbar_detect_checkbox.setToolTip(
            "When enabled, the bot looks for your HP bar to confirm you are in combat."
        )
        self.hpbar_detect_checkbox.setChecked(self.config_manager.get('hpbar_detect_enabled', True))
        self.hpbar_detect_checkbox.toggled.connect(self.on_hpbar_detect_toggled)
        enable_layout.addWidget(self.hpbar_detect_checkbox)
        enable_layout.addStretch()
        hpbar_layout.addLayout(enable_layout)

        hpbar_color_group = QGroupBox("HP Bar Color")
        hpbar_color_group.setToolTip(
            "HSV color used to detect the HP bar. Adjust if your client uses a different shade."
        )
        hpbar_color_layout = QVBoxLayout(hpbar_color_group)
        self.hpbar_color_editor = ColorSpecEditor(self.config_manager, 'hpbar_color')
        try:
            self.hpbar_color_editor.setToolTip("Pick the color that matches your HP bar highlight.")
        except Exception:
            pass
        hpbar_color_layout.addWidget(self.hpbar_color_editor)
        hpbar_layout.addWidget(hpbar_color_group)

        hpbar_roi_group = QGroupBox("HP Bar ROI")
        hpbar_roi_group.setToolTip("Screen region where the HP bar appears.")
        hpbar_roi_layout = QVBoxLayout(hpbar_roi_group)
        roi_row = QHBoxLayout()
        self.hpbar_roi_label = QLabel(self._roi_text(self.config_manager.get('hpbar_roi')))
        roi_row.addWidget(self.hpbar_roi_label)
        roi_row.addStretch()
        self.hpbar_roi_pick_btn = QPushButton("Pick From Screen")
        self.hpbar_roi_pick_btn.setToolTip("Pick the HP bar region directly from your screen.")
        self.hpbar_roi_pick_btn.clicked.connect(self.on_pick_hpbar_roi)
        roi_row.addWidget(self.hpbar_roi_pick_btn)
        self.hpbar_roi_clear_btn = QPushButton("Clear")
        self.hpbar_roi_clear_btn.setToolTip("Remove the HP bar region selection.")
        self.hpbar_roi_clear_btn.clicked.connect(self.on_clear_hpbar_roi)
        roi_row.addWidget(self.hpbar_roi_clear_btn)
        hpbar_roi_layout.addLayout(roi_row)
        hpbar_layout.addWidget(hpbar_roi_group)

        # HP Bar Detection Parameters
        hpbar_params_group = QGroupBox("HP Bar Detection Parameters")
        hpbar_params_group.setToolTip("Fine-tune HP bar detection parameters.")
        hpbar_params_layout = QGridLayout(hpbar_params_group)
        
        # Min Area
        hpbar_params_layout.addWidget(QLabel("Min Area:"), 0, 0)
        self.hpbar_min_area_spin = QSpinBox()
        self.hpbar_min_area_spin.setToolTip("Minimum area (in pixels) for HP bar detection.")
        self.hpbar_min_area_spin.setRange(1, 10000)
        self.hpbar_min_area_spin.setValue(self.config_manager.get('hpbar_min_area', 100))
        hpbar_params_layout.addWidget(self.hpbar_min_area_spin, 0, 1)
        
        # Min Pixel Matches
        hpbar_params_layout.addWidget(QLabel("Min Pixel Matches:"), 0, 2)
        self.hpbar_min_pixel_matches_spin = QSpinBox()
        self.hpbar_min_pixel_matches_spin.setToolTip("Minimum number of pixels that must match the HP bar color.")
        self.hpbar_min_pixel_matches_spin.setRange(1, 10000)
        self.hpbar_min_pixel_matches_spin.setValue(self.config_manager.get('hpbar_min_pixel_matches', 50))
        hpbar_params_layout.addWidget(self.hpbar_min_pixel_matches_spin, 0, 3)
        
        # Not Seen Timeout
        hpbar_params_layout.addWidget(QLabel("Not Seen Timeout:"), 1, 0)
        self.hpbar_not_seen_timeout_spin = QDoubleSpinBox()
        self.hpbar_not_seen_timeout_spin.setToolTip("Time (in seconds) after which combat is considered ended if HP bar is not seen.")
        self.hpbar_not_seen_timeout_spin.setRange(0.1, 60.0)
        self.hpbar_not_seen_timeout_spin.setSingleStep(0.1)
        self.hpbar_not_seen_timeout_spin.setValue(self.config_manager.get('combat_not_seen_timeout_s', 10.0))
        hpbar_params_layout.addWidget(self.hpbar_not_seen_timeout_spin, 1, 1)
        hpbar_params_layout.addWidget(QLabel("seconds"), 1, 2)
        
        hpbar_layout.addWidget(hpbar_params_group)
        general_layout.addWidget(hpbar_group)

        # Combat Timing
        timing_group = QGroupBox("Combat Timing")
        timing_group.setToolTip("Configure timing parameters for combat actions.")
        timing_layout = QGridLayout(timing_group)
        
        # Post Combat Delay Min
        timing_layout.addWidget(QLabel("Post Combat Delay Min:"), 0, 0)
        self.post_combat_delay_min_spin = QDoubleSpinBox()
        self.post_combat_delay_min_spin.setToolTip("Minimum time to wait after combat ends before taking next action.")
        self.post_combat_delay_min_spin.setRange(0.0, 60.0)
        self.post_combat_delay_min_spin.setSingleStep(0.1)
        self.post_combat_delay_min_spin.setValue(self.config_manager.get('post_combat_delay_min_s', 2.0))
        timing_layout.addWidget(self.post_combat_delay_min_spin, 0, 1)
        timing_layout.addWidget(QLabel("seconds"), 0, 2)
        
        # Post Combat Delay Max
        timing_layout.addWidget(QLabel("Post Combat Delay Max:"), 1, 0)
        self.post_combat_delay_max_spin = QDoubleSpinBox()
        self.post_combat_delay_max_spin.setToolTip("Maximum time to wait after combat ends before taking next action.")
        self.post_combat_delay_max_spin.setRange(0.0, 60.0)
        self.post_combat_delay_max_spin.setSingleStep(0.1)
        self.post_combat_delay_max_spin.setValue(self.config_manager.get('post_combat_delay_max_s', 5.0))
        timing_layout.addWidget(self.post_combat_delay_max_spin, 1, 1)
        timing_layout.addWidget(QLabel("seconds"), 1, 2)
        
        general_layout.addWidget(timing_group)

        # Precise Mode Settings
        precise_group = QGroupBox("Precise Mode Settings")
        precise_group.setToolTip("Configure parameters for precise color detection mode.")
        precise_layout = QGridLayout(precise_group)
        
        # Precision Mode
        precise_layout.addWidget(QLabel("Precision Mode:"), 0, 0)
        self.precision_combo = QComboBox()
        self.precision_combo.addItems(["Normal", "Accurate", "Non-Accurate"])
        current_precision = "Normal"
        if self.config_manager.get('combat_lab_tolerance', 15) <= 10:
            current_precision = "Accurate"
        elif self.config_manager.get('combat_lab_tolerance', 15) >= 20:
            current_precision = "Non-Accurate"
        self.precision_combo.setCurrentText(current_precision)
        self.precision_combo.currentTextChanged.connect(self.on_precision_changed)
        precise_layout.addWidget(self.precision_combo, 0, 1)
        
        # Lab Tolerance
        precise_layout.addWidget(QLabel("Lab Tolerance:"), 1, 0)
        self.lab_tolerance_spin = QSpinBox()
        self.lab_tolerance_spin.setToolTip("Delta E tolerance for Lab color space matching (lower is stricter).")
        self.lab_tolerance_spin.setRange(5, 30)
        self.lab_tolerance_spin.setValue(self.config_manager.get('combat_lab_tolerance', 15))
        precise_layout.addWidget(self.lab_tolerance_spin, 1, 1)
        
        # Saturation Min
        precise_layout.addWidget(QLabel("Saturation Min:"), 1, 2)
        self.sat_min_spin = QSpinBox()
        self.sat_min_spin.setToolTip("Minimum saturation value for HSV filtering (higher reduces gray colors).")
        self.sat_min_spin.setRange(0, 100)
        self.sat_min_spin.setValue(self.config_manager.get('combat_sat_min', 50))
        precise_layout.addWidget(self.sat_min_spin, 1, 3)
        
        # Value Min
        precise_layout.addWidget(QLabel("Value Min:"), 2, 0)
        self.val_min_spin = QSpinBox()
        self.val_min_spin.setToolTip("Minimum value for HSV filtering (higher reduces dark colors).")
        self.val_min_spin.setRange(0, 100)
        self.val_min_spin.setValue(self.config_manager.get('combat_val_min', 50))
        precise_layout.addWidget(self.val_min_spin, 2, 1)
        
        # Morph Open Iterations
        precise_layout.addWidget(QLabel("Morph Open Iterations:"), 2, 2)
        self.morph_open_spin = QSpinBox()
        self.morph_open_spin.setToolTip("Number of morphological opening iterations (removes noise).")
        self.morph_open_spin.setRange(0, 5)
        self.morph_open_spin.setValue(self.config_manager.get('combat_morph_open_iters', 1))
        precise_layout.addWidget(self.morph_open_spin, 2, 3)
        
        # Morph Close Iterations
        precise_layout.addWidget(QLabel("Morph Close Iterations:"), 3, 0)
        self.morph_close_spin = QSpinBox()
        self.morph_close_spin.setToolTip("Number of morphological closing iterations (connects components).")
        self.morph_close_spin.setRange(0, 5)
        self.morph_close_spin.setValue(self.config_manager.get('combat_morph_close_iters', 2))
        precise_layout.addWidget(self.morph_close_spin, 3, 1)
        
        general_layout.addWidget(precise_group)

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
        self._combat_tabs.addTab(self.general_tab, "General Settings")

        # ---------- ROI Settings sub-tab ----------
        self.roi_tab = QWidget()
        roi_layout = QVBoxLayout(self.roi_tab)
        
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
        roi_layout.addWidget(tile_roi_group)
        
        # Monster ROI Settings
        monster_roi_group = QGroupBox("Monster ROI Settings")
        monster_roi_group.setToolTip("Configure how monster detection regions are created around tiles")
        monster_roi_layout = QGridLayout(monster_roi_group)
        
        # Around Tile Radius
        monster_roi_layout.addWidget(QLabel("Around Tile Radius:"), 0, 0)
        self.around_tile_radius_spin = QSpinBox()
        self.around_tile_radius_spin.setToolTip("Radius around tiles to search for monsters (in pixels)")
        self.around_tile_radius_spin.setRange(10, 500)
        self.around_tile_radius_spin.setValue(self.config_manager.get('around_tile_radius', 100))
        monster_roi_layout.addWidget(self.around_tile_radius_spin, 0, 1)
        monster_roi_layout.addWidget(QLabel("pixels"), 0, 2)
        
        # ROI Max Expansion
        monster_roi_layout.addWidget(QLabel("ROI Max Expansion:"), 1, 0)
        self.roi_max_expansion_spin = QSpinBox()
        self.roi_max_expansion_spin.setToolTip("Maximum number of expansion levels if no monsters are found")
        self.roi_max_expansion_spin.setRange(0, 10)
        self.roi_max_expansion_spin.setValue(self.config_manager.get('roi_max_expansion', 3))
        monster_roi_layout.addWidget(self.roi_max_expansion_spin, 1, 1)
        monster_roi_layout.addWidget(QLabel("levels"), 1, 2)
        
        # ROI Expansion Factor
        monster_roi_layout.addWidget(QLabel("ROI Expansion Factor:"), 2, 0)
        self.roi_expansion_factor_spin = QDoubleSpinBox()
        self.roi_expansion_factor_spin.setToolTip("Multiplier for each expansion level")
        self.roi_expansion_factor_spin.setRange(1.0, 3.0)
        self.roi_expansion_factor_spin.setSingleStep(0.1)
        self.roi_expansion_factor_spin.setValue(self.config_manager.get('roi_expansion_factor', 1.2))
        monster_roi_layout.addWidget(self.roi_expansion_factor_spin, 2, 1)
        
        roi_layout.addWidget(monster_roi_group)
        
        # Overlay Settings
        overlay_group = QGroupBox("Overlay Settings")
        overlay_group.setToolTip("Configure visual overlays for debugging")
        overlay_layout = QVBoxLayout(overlay_group)
        
        self.roi_overlay_checkbox = QCheckBox("Enable ROI Overlays")
        self.roi_overlay_checkbox.setToolTip("Show visual overlays for ROIs (tiles, monsters, etc.)")
        self.roi_overlay_checkbox.setChecked(self.config_manager.get('roi_overlay_enabled', False))
        overlay_layout.addWidget(self.roi_overlay_checkbox)
        
        roi_layout.addWidget(overlay_group)
        
        # Apply/Reset buttons for ROI tab
        roi_buttons_layout = QHBoxLayout()
        roi_buttons_layout.addStretch()
        
        self.roi_apply_btn = QPushButton("Apply Changes")
        self.roi_apply_btn.clicked.connect(self.on_roi_apply_clicked)
        roi_buttons_layout.addWidget(self.roi_apply_btn)
        
        self.roi_reset_btn = QPushButton("Reset to Defaults")
        self.roi_reset_btn.clicked.connect(self.on_roi_reset_clicked)
        roi_buttons_layout.addWidget(self.roi_reset_btn)
        
        roi_layout.addLayout(roi_buttons_layout)
        roi_layout.addStretch()
        
        # Add the ROI tab
        self._combat_tabs.addTab(self.roi_tab, "ROI Settings")

        # ---------- Combat Style sub-tab ----------
        self.style_tab = QWidget()
        style_layout = QVBoxLayout(self.style_tab)
        
        # Combat Style ROI
        style_roi_group = QGroupBox("Combat Style ROI")
        style_roi_group.setToolTip("Define the region where the bot will look for combat style indicators")
        style_roi_layout = QVBoxLayout(style_roi_group)
        
        style_roi_row = QHBoxLayout()
        self.style_roi_label = QLabel(self._roi_text(self.config_manager.get('combat_style_roi')))
        style_roi_row.addWidget(self.style_roi_label)
        style_roi_row.addStretch()
        
        self.style_roi_pick_btn = QPushButton("Pick From Screen")
        self.style_roi_pick_btn.setToolTip("Pick the combat style indicator region directly from your screen")
        self.style_roi_pick_btn.clicked.connect(self.on_pick_style_roi)
        style_roi_row.addWidget(self.style_roi_pick_btn)
        
        self.style_roi_clear_btn = QPushButton("Clear")
        self.style_roi_clear_btn.setToolTip("Remove the combat style indicator region selection")
        self.style_roi_clear_btn.clicked.connect(self.on_clear_style_roi)
        style_roi_row.addWidget(self.style_roi_clear_btn)
        
        style_roi_layout.addLayout(style_roi_row)
        style_layout.addWidget(style_roi_group)
        
        # Combat Style Colors
        style_colors_group = QGroupBox("Combat Style Colors")
        style_colors_group.setToolTip("Configure colors for different combat style indicators")
        style_colors_layout = QVBoxLayout(style_colors_group)
        
        # Melee style color
        melee_layout = QHBoxLayout()
        melee_layout.addWidget(QLabel("Melee Style Color:"))
        self.melee_style_color_editor = ColorSpecEditor(self.config_manager, 'combat_style_melee_color')
        melee_layout.addWidget(self.melee_style_color_editor)
        style_colors_layout.addLayout(melee_layout)
        
        # Ranged style color
        ranged_layout = QHBoxLayout()
        ranged_layout.addWidget(QLabel("Ranged Style Color:"))
        self.ranged_style_color_editor = ColorSpecEditor(self.config_manager, 'combat_style_ranged_color')
        ranged_layout.addWidget(self.ranged_style_color_editor)
        style_colors_layout.addLayout(ranged_layout)
        
        # Magic style color
        magic_layout = QHBoxLayout()
        magic_layout.addWidget(QLabel("Magic Style Color:"))
        self.magic_style_color_editor = ColorSpecEditor(self.config_manager, 'combat_style_magic_color')
        magic_layout.addWidget(self.magic_style_color_editor)
        style_colors_layout.addLayout(magic_layout)
        
        style_layout.addWidget(style_colors_group)
        
        # Combat Style Detection Parameters
        style_params_group = QGroupBox("Combat Style Detection Parameters")
        style_params_group.setToolTip("Configure parameters for combat style detection")
        style_params_layout = QGridLayout(style_params_group)
        
        # Min Pixels
        style_params_layout.addWidget(QLabel("Min Pixels:"), 0, 0)
        self.style_min_pixels_spin = QSpinBox()
        self.style_min_pixels_spin.setToolTip("Minimum number of pixels that must match a style color")
        self.style_min_pixels_spin.setRange(1, 10000)
        self.style_min_pixels_spin.setValue(self.config_manager.get('combat_style_min_pixels', 40))
        style_params_layout.addWidget(self.style_min_pixels_spin, 0, 1)
        
        style_layout.addWidget(style_params_group)
        
        # Apply/Reset buttons for style tab
        style_buttons_layout = QHBoxLayout()
        style_buttons_layout.addStretch()
        
        self.style_apply_btn = QPushButton("Apply Changes")
        self.style_apply_btn.clicked.connect(self.on_style_apply_clicked)
        style_buttons_layout.addWidget(self.style_apply_btn)
        
        self.style_reset_btn = QPushButton("Reset to Defaults")
        self.style_reset_btn.clicked.connect(self.on_style_reset_clicked)
        style_buttons_layout.addWidget(self.style_reset_btn)
        
        style_layout.addLayout(style_buttons_layout)
        style_layout.addStretch()
        
        # Add the style tab
        self._combat_tabs.addTab(self.style_tab, "Combat Style")

    def _roi_text(self, roi):
        """Format ROI as text"""
        if not roi:
            return "Not set"
        return f"Left: {roi.get('left', 0)}, Top: {roi.get('top', 0)}, " \
               f"Width: {roi.get('width', 0)}, Height: {roi.get('height', 0)}"
    
    def on_hpbar_detect_toggled(self, checked):
        """Handle HP bar detection toggle"""
        self.config_manager.set('hpbar_detect_enabled', checked)
    
    def on_pick_hpbar_roi(self):
        """Pick HP bar ROI from screen"""
        try:
            picker = AdvancedROISelector("Select HP Bar Region")
            if picker.exec_() == AdvancedROISelector.Accepted:
                roi = picker.get_roi()
                if roi:
                    self.config_manager.set('hpbar_roi', roi)
                    self.hpbar_roi_label.setText(self._roi_text(roi))
        except Exception as e:
            logger.error(f"Error picking HP bar ROI: {e}")
    
    def on_clear_hpbar_roi(self):
        """Clear HP bar ROI"""
        self.config_manager.set('hpbar_roi', None)
        self.hpbar_roi_label.setText(self._roi_text(None))
    
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
    
    def on_pick_style_roi(self):
        """Pick combat style ROI from screen"""
        try:
            picker = AdvancedROISelector("Select Combat Style Indicator Region")
            if picker.exec_() == AdvancedROISelector.Accepted:
                roi = picker.get_roi()
                if roi:
                    self.config_manager.set('combat_style_roi', roi)
                    self.style_roi_label.setText(self._roi_text(roi))
        except Exception as e:
            logger.error(f"Error picking combat style ROI: {e}")
    
    def on_clear_style_roi(self):
        """Clear combat style ROI"""
        self.config_manager.set('combat_style_roi', None)
        self.style_roi_label.setText(self._roi_text(None))
    
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
    
    def on_apply_clicked(self):
        """Apply general settings changes"""
        try:
            # Save HP bar detection settings
            self.config_manager.set('hpbar_detect_enabled', self.hpbar_detect_checkbox.isChecked())
            self.config_manager.set('hpbar_min_area', self.hpbar_min_area_spin.value())
            self.config_manager.set('hpbar_min_pixel_matches', self.hpbar_min_pixel_matches_spin.value())
            self.config_manager.set('combat_not_seen_timeout_s', self.hpbar_not_seen_timeout_spin.value())
            
            # Save combat timing settings
            self.config_manager.set('post_combat_delay_min_s', self.post_combat_delay_min_spin.value())
            self.config_manager.set('post_combat_delay_max_s', self.post_combat_delay_max_spin.value())
            
            # Save precise mode settings
            self.config_manager.set('combat_lab_tolerance', self.lab_tolerance_spin.value())
            self.config_manager.set('combat_sat_min', self.sat_min_spin.value())
            self.config_manager.set('combat_val_min', self.val_min_spin.value())
            self.config_manager.set('combat_morph_open_iters', self.morph_open_spin.value())
            self.config_manager.set('combat_morph_close_iters', self.morph_close_spin.value())
            
            logger.info("Combat settings saved")
        except Exception as e:
            logger.error(f"Error applying combat settings: {e}")
    
    def on_reset_clicked(self):
        """Reset general settings to defaults"""
        try:
            # Reset HP bar detection settings
            self.hpbar_detect_checkbox.setChecked(True)
            self.hpbar_min_area_spin.setValue(100)
            self.hpbar_min_pixel_matches_spin.setValue(50)
            self.hpbar_not_seen_timeout_spin.setValue(10.0)
            
            # Reset combat timing settings
            self.post_combat_delay_min_spin.setValue(2.0)
            self.post_combat_delay_max_spin.setValue(5.0)
            
            # Reset precise mode settings
            self.precision_combo.setCurrentText("Normal")
            self.lab_tolerance_spin.setValue(15)
            self.sat_min_spin.setValue(50)
            self.val_min_spin.setValue(50)
            self.morph_open_spin.setValue(1)
            self.morph_close_spin.setValue(2)
            
            logger.info("Combat settings reset to defaults")
        except Exception as e:
            logger.error(f"Error resetting combat settings: {e}")
    
    def on_roi_apply_clicked(self):
        """Apply ROI settings changes"""
        try:
            # Save ROI settings
            self.config_manager.set('around_tile_radius', self.around_tile_radius_spin.value())
            self.config_manager.set('roi_max_expansion', self.roi_max_expansion_spin.value())
            self.config_manager.set('roi_expansion_factor', self.roi_expansion_factor_spin.value())
            self.config_manager.set('roi_overlay_enabled', self.roi_overlay_checkbox.isChecked())
            
            logger.info("ROI settings saved")
        except Exception as e:
            logger.error(f"Error applying ROI settings: {e}")
    
    def on_roi_reset_clicked(self):
        """Reset ROI settings to defaults"""
        try:
            # Reset ROI settings
            self.around_tile_radius_spin.setValue(100)
            self.roi_max_expansion_spin.setValue(3)
            self.roi_expansion_factor_spin.setValue(1.2)
            self.roi_overlay_checkbox.setChecked(False)
            
            logger.info("ROI settings reset to defaults")
        except Exception as e:
            logger.error(f"Error resetting ROI settings: {e}")
    
    def on_style_apply_clicked(self):
        """Apply combat style settings changes"""
        try:
            # Save combat style settings
            self.config_manager.set('combat_style_min_pixels', self.style_min_pixels_spin.value())
            
            logger.info("Combat style settings saved")
        except Exception as e:
            logger.error(f"Error applying combat style settings: {e}")
    
    def on_style_reset_clicked(self):
        """Reset combat style settings to defaults"""
        try:
            # Reset combat style settings
            self.style_min_pixels_spin.setValue(40)
            
            # Reset combat style colors
            default_melee = {'rgb': (107, 38, 56), 'tol_rgb': 15, 'use_hsv': False, 'tol_h': 5, 'tol_s': 40, 'tol_v': 40}
            default_ranged = {'rgb': (14, 150, 173), 'tol_rgb': 15, 'use_hsv': False, 'tol_h': 5, 'tol_s': 40, 'tol_v': 40}
            default_magic = {'rgb': (30, 6, 157), 'tol_rgb': 15, 'use_hsv': False, 'tol_h': 5, 'tol_s': 40, 'tol_v': 40}
            
            self.config_manager.set('combat_style_melee_color', default_melee)
            self.config_manager.set('combat_style_ranged_color', default_ranged)
            self.config_manager.set('combat_style_magic_color', default_magic)
            
            self.melee_style_color_editor.set_color_spec(default_melee)
            self.ranged_style_color_editor.set_color_spec(default_ranged)
            self.magic_style_color_editor.set_color_spec(default_magic)
            
            logger.info("Combat style settings reset to defaults")
        except Exception as e:
            logger.error(f"Error resetting combat style settings: {e}")