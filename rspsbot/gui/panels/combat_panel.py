"""
Combat settings panel for RSPS Color Bot v3
"""
import logging
from ..utils.roi_utils import format_roi
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox, QGridLayout,
    QTabWidget, QLineEdit
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
        # Snapshot/Test button row
        snapshot_row = QHBoxLayout()
        self.hpbar_test_btn = QPushButton("Test HP Bar Detection")
        self.hpbar_test_btn.setToolTip("Capture the HP bar ROI, run detection, and save debug snapshots (frame + mask).")
        self.hpbar_test_btn.clicked.connect(self.on_test_hpbar_detection)
        snapshot_row.addWidget(self.hpbar_test_btn)
        snapshot_row.addStretch()
        hpbar_layout.addLayout(snapshot_row)

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
        # Follow-window toggle
        follow_row = QHBoxLayout()
        self.hpbar_follow_checkbox = QCheckBox("Follow client window")
        self.hpbar_follow_checkbox.setToolTip("When enabled, the HP bar ROI is stored relative to the game window, so it follows the window when moved. Disable to lock to absolute screen coordinates.")
        self.hpbar_follow_checkbox.setChecked(bool(self.config_manager.get('hpbar_roi_follow_window', True)))
        self.hpbar_follow_checkbox.toggled.connect(self.on_hpbar_follow_toggled)
        follow_row.addWidget(self.hpbar_follow_checkbox)
        follow_row.addStretch()
        hpbar_roi_layout.addLayout(follow_row)
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
        timing_group = QGroupBox("Combat Timing & Gating")
        timing_group.setToolTip("Configure post-combat delays and target-click gating.")
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
        
        # Min monster click cooldown
        timing_layout.addWidget(QLabel("Min monster click cooldown:"), 2, 0)
        self.min_click_cooldown_spin = QDoubleSpinBox()
        self.min_click_cooldown_spin.setRange(0.0, 5.0)
        self.min_click_cooldown_spin.setSingleStep(0.1)
        self.min_click_cooldown_spin.setDecimals(2)
        self.min_click_cooldown_spin.setToolTip("Minimum time between monster attack clicks. Lower for more aggressive clicking; higher to avoid overclicks.")
        self.min_click_cooldown_spin.setValue(float(self.config_manager.get('min_monster_click_cooldown_s', 0.8)))
        timing_layout.addWidget(self.min_click_cooldown_spin, 2, 1)
        timing_layout.addWidget(QLabel("seconds"), 2, 2)

        # Attack grace after a click
        timing_layout.addWidget(QLabel("Attack grace:"), 3, 0)
        self.attack_grace_spin = QDoubleSpinBox()
        self.attack_grace_spin.setRange(0.0, 3.0)
        self.attack_grace_spin.setSingleStep(0.1)
        self.attack_grace_spin.setDecimals(2)
        self.attack_grace_spin.setToolTip("Short pause after an attack click before attempting another. Helps the client register target selection.")
        self.attack_grace_spin.setValue(float(self.config_manager.get('attack_grace_s', 0.6)))
        timing_layout.addWidget(self.attack_grace_spin, 3, 1)
        timing_layout.addWidget(QLabel("seconds"), 3, 2)

        # Min-distance gate enable
        timing_layout.addWidget(QLabel("Min-distance gate:"), 4, 0)
        self.min_dist_enable_checkbox = QCheckBox("Enabled")
        self.min_dist_enable_checkbox.setToolTip("When enabled, ignore clicks that are too close to the last monster click to avoid double-clicking nearly the same spot.")
        self.min_dist_enable_checkbox.setChecked(bool(self.config_manager.get('min_monster_click_distance_enabled', True)))
        timing_layout.addWidget(self.min_dist_enable_checkbox, 4, 1)

        # Min-distance pixels
        timing_layout.addWidget(QLabel("Min click distance:"), 5, 0)
        self.min_dist_px_spin = QSpinBox()
        self.min_dist_px_spin.setRange(0, 60)
        self.min_dist_px_spin.setToolTip("Minimum pixel distance from the previous attack click before another click is allowed. Set 0 to disable distance gating.")
        self.min_dist_px_spin.setValue(int(self.config_manager.get('min_monster_click_distance_px', 12)))
        timing_layout.addWidget(self.min_dist_px_spin, 5, 1)
        timing_layout.addWidget(QLabel("px"), 5, 2)

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

        # ---------- 1 Tele 1 Kill sub-tab ----------
        self.one_tele_tab = QWidget()
        one_tele_layout = QVBoxLayout(self.one_tele_tab)

        otk_group = QGroupBox("1 Tele 1 Kill (override)")
        otk_group.setToolTip(
            "When enabled: TILE → MONSTER → ATTACK → wait for HP; if HP not seen within timeout, teleport to the selected XY and repeat."
        )
        otk_layout = QGridLayout(otk_group)

        # Enable toggle
        otk_layout.addWidget(QLabel("Enable mode:"), 0, 0)
        self.one_tele_enable_checkbox = QCheckBox("Enabled (overrides normal logic)")
        self.one_tele_enable_checkbox.setChecked(self.config_manager.get('one_tele_one_kill_enabled', False))
        self.one_tele_enable_checkbox.toggled.connect(self.on_one_tele_enable_toggled)
        otk_layout.addWidget(self.one_tele_enable_checkbox, 0, 1, 1, 2)

        # HP timeout seconds
        otk_layout.addWidget(QLabel("HP verify timeout:"), 1, 0)
        self.one_tele_hp_timeout_spin = QDoubleSpinBox()
        self.one_tele_hp_timeout_spin.setRange(0.5, 30.0)
        self.one_tele_hp_timeout_spin.setSingleStep(0.5)
        self.one_tele_hp_timeout_spin.setSuffix(" s")
        self.one_tele_hp_timeout_spin.setToolTip("If your HP bar is not seen within this time after an attack, we'll teleport.")
        self.one_tele_hp_timeout_spin.setValue(self.config_manager.get('one_tele_one_kill_hp_timeout_s', 5.0))
        self.one_tele_hp_timeout_spin.valueChanged.connect(self.on_one_tele_timeout_changed)
        otk_layout.addWidget(self.one_tele_hp_timeout_spin, 1, 1)

        # Teleport target group (coordinate or ROI + optional hotkey)
        tp_group = QGroupBox("Teleport target")
        tp_layout = QVBoxLayout(tp_group)

        # Toggle: use ROI instead of fixed coordinate
        self.one_tele_use_roi_checkbox = QCheckBox("Use ROI for teleport click (random point inside)")
        self.one_tele_use_roi_checkbox.setChecked(self.config_manager.get('one_tele_use_roi', False))
        self.one_tele_use_roi_checkbox.toggled.connect(lambda v: self.config_manager.set('one_tele_use_roi', bool(v)))
        tp_layout.addWidget(self.one_tele_use_roi_checkbox)

        # ROI pick/display row
        roi_row = QHBoxLayout()
        roi_row.addWidget(QLabel("Teleport ROI:"))
        self.one_tele_roi_label = QLabel(self._roi_text(self.config_manager.get_roi('one_tele_one_kill_teleport_roi')))
        roi_row.addWidget(self.one_tele_roi_label, 1)
        self.one_tele_pick_roi_btn = QPushButton("Pick ROI")
        self.one_tele_pick_roi_btn.setToolTip("Select an ROI region to click for teleport; stored as window-relative by default.")
        self.one_tele_pick_roi_btn.clicked.connect(self.on_pick_one_tele_roi)
        roi_row.addWidget(self.one_tele_pick_roi_btn)
        self.one_tele_clear_roi_btn = QPushButton("Clear")
        self.one_tele_clear_roi_btn.clicked.connect(self.on_clear_one_tele_roi)
        roi_row.addWidget(self.one_tele_clear_roi_btn)
        tp_layout.addLayout(roi_row)

        # Coordinate picker (fallback when ROI disabled)
        coord_group = QGroupBox("Fallback coordinate (used when ROI not enabled)")
        coord_layout = QVBoxLayout(coord_group)
        self.one_tele_coord_selector = CoordinateSelector(parent=self, config_manager=self.config_manager, bot_controller=self.bot_controller)
        try:
            coord = self.config_manager.get_coordinate('one_tele_one_kill_teleport_xy')
            if coord:
                self.one_tele_coord_selector.set_coordinate(coord.x, coord.y)
        except Exception:
            pass
        self.one_tele_coord_selector.coordinateSelected.connect(self.on_one_tele_coord_selected)
        coord_layout.addWidget(self.one_tele_coord_selector)
        tp_layout.addWidget(coord_group)

        # Post-teleport hotkey row
        hk_row = QHBoxLayout()
        self.one_tele_hk_enable = QCheckBox("Enable hotkey after teleport")
        self.one_tele_hk_enable.setChecked(self.config_manager.get('one_tele_post_hotkey_enabled', False))
        self.one_tele_hk_enable.toggled.connect(lambda v: self.config_manager.set('one_tele_post_hotkey_enabled', bool(v)))
        hk_row.addWidget(self.one_tele_hk_enable)
        hk_row.addWidget(QLabel("Hotkey:"))
        self.one_tele_hk_edit = QLineEdit()
        self.one_tele_hk_edit.setText(self.config_manager.get('one_tele_post_hotkey', '2'))
        self.one_tele_hk_edit.textChanged.connect(lambda t: self.config_manager.set('one_tele_post_hotkey', t.strip() or '2'))
        hk_row.addWidget(self.one_tele_hk_edit)
        hk_row.addWidget(QLabel("Delay (s):"))
        self.one_tele_hk_delay = QDoubleSpinBox()
        self.one_tele_hk_delay.setRange(0.0, 5.0)
        self.one_tele_hk_delay.setSingleStep(0.05)
        self.one_tele_hk_delay.setValue(float(self.config_manager.get('one_tele_post_hotkey_delay', 0.15)))
        self.one_tele_hk_delay.valueChanged.connect(lambda v: self.config_manager.set('one_tele_post_hotkey_delay', float(v)))
        hk_row.addWidget(self.one_tele_hk_delay)
        tp_layout.addLayout(hk_row)

        one_tele_layout.addWidget(otk_group)
        one_tele_layout.addWidget(tp_group)
        one_tele_layout.addStretch()

        self._combat_tabs.addTab(self.one_tele_tab, "1 Tele 1 Kill")

    # (Removed) Combat Style sub-tab – use Multi Monster Mode settings instead

    def _roi_text(self, roi):
        return format_roi(roi)
    
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
                    # Respect follow-window preference: store as 'relative' else 'absolute'
                    try:
                        roi.mode = 'relative' if self.hpbar_follow_checkbox.isChecked() else 'absolute'
                    except Exception:
                        pass
                    self.config_manager.set_roi('hpbar_roi', roi)
                    self.hpbar_roi_label.setText(self._roi_text(roi))
        except Exception as e:
            logger.error(f"Error picking HP bar ROI: {e}")
    
    def on_clear_hpbar_roi(self):
        """Clear HP bar ROI"""
        self.config_manager.set('hpbar_roi', None)
        self.hpbar_roi_label.setText(self._roi_text(None))

    def on_hpbar_follow_toggled(self, checked: bool):
        """Persist follow-window preference and migrate stored ROI if reasonable."""
        try:
            self.config_manager.set('hpbar_roi_follow_window', bool(checked))
            roi = self.config_manager.get_roi('hpbar_roi')
            if not roi:
                return
            from ...core.config import ROI as ROIModel
            from ...core.detection.capture import CaptureService
            cs = CaptureService()
            bbox = cs.get_window_bbox()
            if checked:
                # Convert absolute -> relative when possible
                if str(getattr(roi, 'mode', 'absolute')).lower() == 'absolute':
                    rel_l = int(roi.left) - int(bbox['left'])
                    rel_t = int(roi.top) - int(bbox['top'])
                    if 0 <= rel_l <= bbox['width'] and 0 <= rel_t <= bbox['height']:
                        new_roi = ROIModel(rel_l, rel_t, int(roi.width), int(roi.height), mode='relative')
                        self.config_manager.set_roi('hpbar_roi', new_roi)
                        self.hpbar_roi_label.setText(self._roi_text(new_roi))
            else:
                # Convert relative/percent -> absolute
                mode = str(getattr(roi, 'mode', 'absolute')).lower()
                if mode in ('relative', 'percent'):
                    if mode == 'percent':
                        abs_l = int(bbox['left'] + float(roi.left) * bbox['width'])
                        abs_t = int(bbox['top'] + float(roi.top) * bbox['height'])
                        abs_w = int(float(roi.width) * bbox['width'])
                        abs_h = int(float(roi.height) * bbox['height'])
                    else:
                        abs_l = int(bbox['left'] + int(roi.left))
                        abs_t = int(bbox['top'] + int(roi.top))
                        abs_w = int(roi.width)
                        abs_h = int(roi.height)
                    new_roi = ROIModel(abs_l, abs_t, abs_w, abs_h, mode='absolute')
                    self.config_manager.set_roi('hpbar_roi', new_roi)
                    self.hpbar_roi_label.setText(self._roi_text(new_roi))
        except Exception:
            pass

    def on_test_hpbar_detection(self):
        """Manually test HP bar detection and save a snapshot for diagnostics."""
        try:
            hp_roi = self.config_manager.get_roi('hpbar_roi')
            if not hp_roi:
                logger.warning("HP Bar ROI not set; cannot test.")
                return
            # Basic ROI sanity checks
            if hp_roi.width < 3 or hp_roi.height < 3:
                logger.warning(f"HP Bar ROI too small: {hp_roi.width}x{hp_roi.height}")
            if hp_roi.width * hp_roi.height > 300000:  # arbitrary large cut-off
                logger.warning(f"HP Bar ROI unusually large: {hp_roi.width}x{hp_roi.height}")

            # Access capture service & color spec
            cap = getattr(self.bot_controller, 'capture_service', None)
            if cap is None:
                logger.error("Capture service unavailable on bot_controller")
                return
            color_spec = self.config_manager.get_color_spec('hpbar_color')
            if not color_spec:
                logger.error("HP bar color not configured; cannot test")
                return

            # Capture frame
            frame = cap.capture_region(hp_roi)
            from ...core.detection.color_detector import build_mask  # local import to avoid cycles
            min_area = int(self.config_manager.get('hpbar_min_area', 50))
            min_pixels = int(self.config_manager.get('hpbar_min_pixel_matches', 150))
            mask, contours = build_mask(frame, color_spec, step=1, precise=True, min_area=min_area)
            pixel_matches = int((mask > 0).sum())
            detected = pixel_matches >= min_pixels and len(contours) > 0
            largest_area = 0
            if contours:
                import cv2
                largest_area = max(cv2.contourArea(c) for c in contours)

            # Save debug images if enabled
            debug_dir = self.config_manager.get('debug_output_dir', 'outputs')
            import os, time, cv2
            ts = time.strftime('%Y%m%d_%H%M%S')
            hp_dir = os.path.join(debug_dir, 'hpbar')
            os.makedirs(hp_dir, exist_ok=True)
            frame_path = os.path.join(hp_dir, f'hpbar_{ts}.png')
            mask_path = os.path.join(hp_dir, f'hpbar_{ts}_mask.png')
            try:
                cv2.imwrite(frame_path, frame)
                cv2.imwrite(mask_path, mask)
            except Exception as e:
                logger.error(f"Failed saving HP bar snapshots: {e}")

            logger.info(
                f"HPBarTest roi=({hp_roi.left},{hp_roi.top},{hp_roi.width}x{hp_roi.height}) matches={pixel_matches} contours={len(contours)} largest_area={largest_area:.1f} detected={detected} saved={frame_path}"
            )
            # Persist quick stats for overlay HUD
            try:
                self.config_manager.set('hpbar_last_test', {
                    'roi': hp_roi.to_dict(),
                    'matches': pixel_matches,
                    'contours': len(contours),
                    'largest_area': float(largest_area),
                    'detected': bool(detected),
                    'timestamp': ts,
                    'frame_path': frame_path,
                    'mask_path': mask_path,
                })
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error during HP bar test: {e}")
    
    
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
            self.config_manager.set('min_monster_click_cooldown_s', float(self.min_click_cooldown_spin.value()))
            self.config_manager.set('attack_grace_s', float(self.attack_grace_spin.value()))
            self.config_manager.set('min_monster_click_distance_enabled', self.min_dist_enable_checkbox.isChecked())
            self.config_manager.set('min_monster_click_distance_px', int(self.min_dist_px_spin.value()))
            
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
            self.min_click_cooldown_spin.setValue(0.8)
            self.attack_grace_spin.setValue(0.6)
            self.min_dist_enable_checkbox.setChecked(True)
            self.min_dist_px_spin.setValue(12)
            
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
    
    def on_one_tele_enable_toggled(self, checked):
        """Handle enabling/disabling 1 Tele 1 Kill mode"""
        try:
            self.config_manager.set('one_tele_one_kill_enabled', bool(checked))
        except Exception as e:
            logger.error(f"Failed to set one_tele_one_kill_enabled: {e}")

    def on_one_tele_timeout_changed(self, val: float):
        """Handle HP timeout value change for 1T1K mode"""
        try:
            self.config_manager.set('one_tele_one_kill_hp_timeout_s', float(val))
        except Exception as e:
            logger.error(f"Failed to set one_tele_one_kill_hp_timeout_s: {e}")

    def on_one_tele_coord_selected(self, x: int, y: int):
        """Update teleport coordinate for 1T1K mode when user picks or edits XY"""
        try:
            coord = Coordinate(x=x, y=y, name='1T1K Teleport')
            self.config_manager.set_coordinate('one_tele_one_kill_teleport_xy', coord)
        except Exception as e:
            logger.error(f"Failed to set one_tele_one_kill_teleport_xy: {e}")

    def on_pick_one_tele_roi(self):
        """Pick an ROI to click for teleport in 1T1K mode"""
        try:
            picker = ZoomRoiPickerDialog(self.config_manager, self)
            if picker.exec_() == picker.Accepted:
                rect = getattr(picker, 'result_rect', None)
                if rect is None:
                    return
                if hasattr(rect, 'isNull') and rect.isNull():
                    return
                # Store ROI relative to focused window so it remains valid if the window moves
                from ...core.config import ROI as ROIModel
                roi = ROIModel(left=rect.left(), top=rect.top(), width=rect.width(), height=rect.height(), mode='relative')
                self.config_manager.set_roi('one_tele_one_kill_teleport_roi', roi)
                self.one_tele_roi_label.setText(self._roi_text(roi))
        except Exception as e:
            logger.error(f"Error picking 1T1K teleport ROI: {e}")

    def on_clear_one_tele_roi(self):
        """Clear the Teleport ROI for 1T1K mode"""
        try:
            self.config_manager.set('one_tele_one_kill_teleport_roi', None)
            self.one_tele_roi_label.setText(self._roi_text(None))
        except Exception:
            pass