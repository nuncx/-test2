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

        settings_layout = QGridLayout()
        settings_layout.addWidget(QLabel("Minimum Area:"), 0, 0)
        self.hpbar_min_area_spin = QSpinBox()
        self.hpbar_min_area_spin.setRange(10, 200)
        self.hpbar_min_area_spin.setValue(self.config_manager.get('hpbar_min_area', 50))
        self.hpbar_min_area_spin.setToolTip(
            "Smallest contour area to accept as HP bar. Increase to filter noise."
        )
        self.hpbar_min_area_spin.valueChanged.connect(self.on_hpbar_min_area_changed)
        settings_layout.addWidget(self.hpbar_min_area_spin, 0, 1)
        settings_layout.addWidget(QLabel("Minimum Pixel Matches:"), 1, 0)
        self.hpbar_min_pixel_matches_spin = QSpinBox()
        self.hpbar_min_pixel_matches_spin.setRange(50, 500)
        self.hpbar_min_pixel_matches_spin.setValue(self.config_manager.get('hpbar_min_pixel_matches', 150))
        self.hpbar_min_pixel_matches_spin.setToolTip(
            "Minimum number of HP-color pixels required inside the ROI to confirm the bar."
        )
        self.hpbar_min_pixel_matches_spin.valueChanged.connect(self.on_hpbar_min_pixel_matches_changed)
        settings_layout.addWidget(self.hpbar_min_pixel_matches_spin, 1, 1)
        hpbar_layout.addLayout(settings_layout)
        general_layout.addWidget(hpbar_group)

        # Combat Timing
        timing_group = QGroupBox("Combat Timing")
        timing_group.setToolTip(
            "Pacing around combat: delays after combat ends, timeout when combat stops, and attack grace."
        )
        timing_layout = QVBoxLayout(timing_group)
        post_combat_layout = QGridLayout()
        from ..components import TimeSelector, TooltipHelper
        post_combat_layout.addWidget(QLabel("Post-Combat Delay Min:"), 0, 0)
        self.post_combat_delay_min_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('post_combat_delay_min_s', 1.0),
            mode=TimeSelector.MODE_SEC_ONLY,
            tooltip="Minimum time to wait after combat ends before looking for new targets"
        )
        self.post_combat_delay_min_selector.timeChanged.connect(self.on_post_combat_delay_min_changed)
        post_combat_layout.addWidget(self.post_combat_delay_min_selector, 0, 1)
        post_combat_layout.addWidget(QLabel("Post-Combat Delay Max:"), 1, 0)
        self.post_combat_delay_max_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('post_combat_delay_max_s', 3.0),
            mode=TimeSelector.MODE_SEC_ONLY,
            tooltip="Maximum time to wait after combat ends before looking for new targets"
        )
        self.post_combat_delay_max_selector.timeChanged.connect(self.on_post_combat_delay_max_changed)
        post_combat_layout.addWidget(self.post_combat_delay_max_selector, 1, 1)
        post_combat_layout.addWidget(QLabel("Combat Not Seen Timeout:"), 2, 0)
        self.combat_timeout_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('combat_not_seen_timeout_s', 10.0),
            mode=TimeSelector.MODE_SEC_ONLY,
            tooltip="Time to wait after combat is not detected before considering combat to be over"
        )
        self.combat_timeout_selector.timeChanged.connect(self.on_combat_timeout_changed)
        post_combat_layout.addWidget(self.combat_timeout_selector, 2, 1)
        post_combat_layout.addWidget(QLabel("Attack Grace:"), 3, 0)
        self.attack_grace_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('attack_grace_s', self.config_manager.get('post_combat_delay_min_s', 1.0)),
            mode=TimeSelector.MODE_SEC_ONLY,
            tooltip="After clicking a monster (attack), wait at least this long before trying to attack again."
        )
        self.attack_grace_selector.timeChanged.connect(self.on_attack_grace_changed)
        post_combat_layout.addWidget(self.attack_grace_selector, 3, 1)
        timing_layout.addLayout(post_combat_layout)
        general_layout.addWidget(timing_group)

        # Camera Adjustment
        camera_group = QGroupBox("Camera Adjustment")
        camera_group.setToolTip("Automatically nudges the camera to keep targets visible.")
        camera_layout = QVBoxLayout(camera_group)
        enable_cam_layout = QHBoxLayout()
        self.enable_cam_adjust_checkbox = QCheckBox("Enable Camera Adjustment")
        self.enable_cam_adjust_checkbox.setToolTip("Toggle automatic camera nudging.")
        self.enable_cam_adjust_checkbox.setChecked(self.config_manager.get('enable_cam_adjust', True))
        self.enable_cam_adjust_checkbox.toggled.connect(self.on_enable_cam_adjust_toggled)
        enable_cam_layout.addWidget(self.enable_cam_adjust_checkbox)
        enable_cam_layout.addStretch()
        camera_layout.addLayout(enable_cam_layout)

        cam_settings_layout = QGridLayout()
        cam_settings_layout.addWidget(QLabel("Hold Time:"), 0, 0)
        self.cam_adjust_hold_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('cam_adjust_hold_s', 0.08),
            mode=TimeSelector.MODE_SEC_ONLY,
            tooltip="Duration to hold camera adjustment keys"
        )
        self.cam_adjust_hold_selector.timeChanged.connect(self.on_cam_adjust_hold_changed)
        cam_settings_layout.addWidget(self.cam_adjust_hold_selector, 0, 1)
        cam_settings_layout.addWidget(QLabel("Gap Time:"), 1, 0)
        self.cam_adjust_gap_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('cam_adjust_gap_s', 0.03),
            mode=TimeSelector.MODE_SEC_ONLY,
            tooltip="Gap between camera adjustment key presses"
        )
        self.cam_adjust_gap_selector.timeChanged.connect(self.on_cam_adjust_gap_changed)
        cam_settings_layout.addWidget(self.cam_adjust_gap_selector, 1, 1)
        camera_layout.addLayout(cam_settings_layout)

        micro_layout = QGridLayout()
        micro_layout.addWidget(QLabel("Micro Adjust Every:"), 0, 0)
        self.micro_adjust_every_spin = QSpinBox()
        self.micro_adjust_every_spin.setRange(1, 20)
        self.micro_adjust_every_spin.setValue(self.config_manager.get('micro_adjust_every_loops', 8))
        self.micro_adjust_every_spin.setToolTip("Run a micro camera adjust every N main loops.")
        self.micro_adjust_every_spin.valueChanged.connect(self.on_micro_adjust_every_changed)
        micro_layout.addWidget(self.micro_adjust_every_spin, 0, 1)
        micro_layout.addWidget(QLabel("Micro Hold Time:"), 1, 0)
        self.micro_adjust_hold_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('micro_adjust_hold_s', 0.04),
            mode=TimeSelector.MODE_SEC_ONLY,
            tooltip="Duration to hold micro adjustment keys"
        )
        self.micro_adjust_hold_selector.timeChanged.connect(self.on_micro_adjust_hold_changed)
        micro_layout.addWidget(self.micro_adjust_hold_selector, 1, 1)
        micro_layout.addWidget(QLabel("Micro Gap Time:"), 2, 0)
        self.micro_adjust_gap_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('micro_adjust_gap_s', 0.03),
            mode=TimeSelector.MODE_SEC_ONLY,
            tooltip="Gap between micro adjustment key presses"
        )
        self.micro_adjust_gap_selector.timeChanged.connect(self.on_micro_adjust_gap_changed)
        micro_layout.addWidget(self.micro_adjust_gap_selector, 2, 1)
        camera_layout.addLayout(micro_layout)
        general_layout.addWidget(camera_group)
        general_layout.addStretch()

        # ---------- Combat Style sub-tab ----------
        self.style_tab = QWidget()
        style_tab_layout = QVBoxLayout(self.style_tab)
        style_group = QGroupBox("Combat Style")
        style_group.setToolTip("Detect current style and optionally enforce a preferred one.")
        style_layout = QVBoxLayout(style_group)

        # Enable (no preferred style concept)
        top_row = QHBoxLayout()
        self.style_enforce_checkbox = QCheckBox("Enable Combat Style")
        self.style_enforce_checkbox.setToolTip(
            "Before attacking, detect the current style from the Style Indicator ROI;\n"
            "if its linked weapon color is found in the Weapon ROI, click it once, then attack.\n"
            "After an attack, if no HP bar within ~5s, retry one weapon click."
        )
        self.style_enforce_checkbox.setChecked(bool(self.config_manager.get('combat_style_enforce', False)))
        self.style_enforce_checkbox.toggled.connect(lambda v: self.config_manager.set('combat_style_enforce', bool(v)))
        top_row.addWidget(self.style_enforce_checkbox)
        top_row.addStretch()
        style_layout.addLayout(top_row)

    # NOTE: ROI Settings moved to its own sub-tab below

        # Min pixel thresholds (global + per-style)
        thr_group = QGroupBox("Min Pixels (Style Indicator)")
        thr_group.setToolTip(
            "Minimum pixels required in the color mask (Style Indicator ROI) to count a style as present.\n"
            "Mask is built from the selected HSV color; detection happens when count(mask) ≥ min pixels."
        )
        thr_grid = QGridLayout(thr_group)

        thr_grid.addWidget(QLabel("Global (fallback)"), 0, 0)
        self.style_min_pixels_spin = QSpinBox()
        self.style_min_pixels_spin.setRange(1, 5000)
        self.style_min_pixels_spin.setToolTip("Global fallback threshold used when a per-style value is 0.")
        try:
            self.style_min_pixels_spin.setValue(int(self.config_manager.get('combat_style_min_pixels', 40)))
        except Exception:
            self.style_min_pixels_spin.setValue(40)
        self.style_min_pixels_spin.valueChanged.connect(lambda v: self.config_manager.set('combat_style_min_pixels', int(v)))
        thr_grid.addWidget(self.style_min_pixels_spin, 0, 1)

        thr_grid.addWidget(QLabel("Melee"), 1, 0)
        self.style_min_pixels_melee_spin = QSpinBox()
        self.style_min_pixels_melee_spin.setRange(0, 5000)
        try:
            self.style_min_pixels_melee_spin.setValue(int(self.config_manager.get('combat_style_min_pixels_melee', 0) or 0))
        except Exception:
            self.style_min_pixels_melee_spin.setValue(0)
        self.style_min_pixels_melee_spin.setToolTip("Override for melee. 0 = use Global fallback.")
        self.style_min_pixels_melee_spin.valueChanged.connect(lambda v: self.config_manager.set('combat_style_min_pixels_melee', int(v)))
        thr_grid.addWidget(self.style_min_pixels_melee_spin, 1, 1)

        thr_grid.addWidget(QLabel("Ranged"), 2, 0)
        self.style_min_pixels_ranged_spin = QSpinBox()
        self.style_min_pixels_ranged_spin.setRange(0, 5000)
        try:
            self.style_min_pixels_ranged_spin.setValue(int(self.config_manager.get('combat_style_min_pixels_ranged', 0) or 0))
        except Exception:
            self.style_min_pixels_ranged_spin.setValue(0)
        self.style_min_pixels_ranged_spin.setToolTip("Override for ranged. 0 = use Global fallback.")
        self.style_min_pixels_ranged_spin.valueChanged.connect(lambda v: self.config_manager.set('combat_style_min_pixels_ranged', int(v)))
        thr_grid.addWidget(self.style_min_pixels_ranged_spin, 2, 1)

        thr_grid.addWidget(QLabel("Magic"), 3, 0)
        self.style_min_pixels_magic_spin = QSpinBox()
        self.style_min_pixels_magic_spin.setRange(0, 5000)
        try:
            self.style_min_pixels_magic_spin.setValue(int(self.config_manager.get('combat_style_min_pixels_magic', 0) or 0))
        except Exception:
            self.style_min_pixels_magic_spin.setValue(0)
        self.style_min_pixels_magic_spin.setToolTip("Override for magic. 0 = use Global fallback.")
        self.style_min_pixels_magic_spin.valueChanged.connect(lambda v: self.config_manager.set('combat_style_min_pixels_magic', int(v)))
        thr_grid.addWidget(self.style_min_pixels_magic_spin, 3, 1)

        style_layout.addWidget(thr_group)

        # Color editors
        colors_group = QGroupBox("Style Colors")
        colors_group.setToolTip(
            "HSV colors used to detect the current combat style in the Style Indicator ROI.\n"
            "Pick a representative color for each style's icon or highlight."
        )
        colors_layout = QGridLayout(colors_group)
        colors_layout.addWidget(QLabel("Melee"), 0, 0)
        self.melee_color_editor = EnhancedColorEditor(self.config_manager, 'combat_style_melee_color', title="Melee Color")
        self.melee_color_editor.setToolTip("Melee style HSV color for style detection in Style Indicator ROI.")
        colors_layout.addWidget(self.melee_color_editor, 1, 0)
        colors_layout.addWidget(QLabel("Ranged"), 0, 1)
        self.ranged_color_editor = EnhancedColorEditor(self.config_manager, 'combat_style_ranged_color', title="Ranged Color")
        self.ranged_color_editor.setToolTip("Ranged style HSV color for style detection in Style Indicator ROI.")
        colors_layout.addWidget(self.ranged_color_editor, 1, 1)
        colors_layout.addWidget(QLabel("Magic"), 0, 2)
        self.magic_color_editor = EnhancedColorEditor(self.config_manager, 'combat_style_magic_color', title="Magic Color")
        self.magic_color_editor.setToolTip("Magic style HSV color for style detection in Style Indicator ROI.")
        colors_layout.addWidget(self.magic_color_editor, 1, 2)
        style_layout.addWidget(colors_group)

        # Note: XY switching removed; switching is color-based via Weapon ROI

        # Test row
        test_row = QHBoxLayout()
        self.test_style_btn = QPushButton("Test Detect Style")
        self.test_style_btn.setToolTip("Runs style detection using Style Indicator ROI, selected colors, and thresholds.")
        self.test_style_btn.clicked.connect(self._on_test_style_clicked)
        test_row.addWidget(self.test_style_btn)
        self.style_status_label = QLabel("Current style: (unknown)")
        self.style_status_label.setStyleSheet("color:#6aa; font-weight:bold;")
        test_row.addWidget(self.style_status_label)
        test_row.addStretch()
        save_style_btn = QPushButton("Save Combat Settings")
        save_style_btn.setToolTip("Save all Combat settings to the current profile.")
        save_style_btn.clicked.connect(lambda: self._save_combat_settings(silent=False))
        test_row.addWidget(save_style_btn)
        style_layout.addLayout(test_row)

    # Finalize tabs
        style_tab_layout.addWidget(style_group)
        self._combat_tabs.addTab(self.general_tab, "General")
        self._combat_tabs.addTab(self.style_tab, "Combat Style")

        # ---------- ROI Settings sub-tab ----------
        self.roi_tab = QWidget()
        roi_tab_layout = QVBoxLayout(self.roi_tab)

        roi_group = QGroupBox("ROI Settings")
        roi_group.setToolTip("Configure the screen regions used for style detection and weapon switching.")
        roi_group_layout = QVBoxLayout(roi_group)

        # Style Indicator ROI + overlay toggle (routes to global Debug Overlay)
        roi_row2 = QHBoxLayout()
        self.style_roi_selector = AdvancedROISelector(self.config_manager, title="Style Indicator ROI")
        self.style_roi_selector.setToolTip("Region containing the style indicator icon used to detect current style.")
        self.style_roi_selector.roiChanged.connect(self._on_style_roi_changed)
        roi_row2.addWidget(self.style_roi_selector)
        side = QVBoxLayout()
        self.style_overlay_checkbox = QCheckBox("Show Style ROI (Debug Overlay)")
        self.style_overlay_checkbox.setToolTip("Highlights the Style ROI using the global Debug Overlay. Auto-enables Debug Overlay when checked.")
        self.style_overlay_checkbox.setChecked(bool(self.config_manager.get('overlay_show_combat_style_roi', False)))
        self.style_overlay_checkbox.toggled.connect(self._on_style_overlay_toggled)
        side.addWidget(self.style_overlay_checkbox)
        side.addStretch()
        roi_row2.addLayout(side)
        roi_group_layout.addLayout(roi_row2)

        # Style ROI status label (compact)
        style_status_row = QHBoxLayout()
        style_status_row.addWidget(QLabel("Style ROI:"))
        self.style_roi_status_label = QLabel(self._roi_text(self.config_manager.get('combat_style_roi')))
        self.style_roi_status_label.setStyleSheet("color:#777; font-style:italic;")
        style_status_row.addWidget(self.style_roi_status_label)
        style_status_row.addStretch()
        roi_group_layout.addLayout(style_status_row)

        # Weapon ROI selector (area where style/weapon buttons live)
        weapon_roi_group = QGroupBox("Weapon/Style Switch ROI")
        weapon_roi_group.setToolTip("Region containing the style/weapon buttons or icons used for switching.")
        weapon_roi_layout = QVBoxLayout(weapon_roi_group)
        self.weapon_roi_selector = AdvancedROISelector(self.config_manager, title="Weapon ROI")
        self.weapon_roi_selector.setToolTip("Region where the bot searches for the preferred style/weapon color to click.")
        self.weapon_roi_selector.roiChanged.connect(self._on_weapon_roi_changed)
        weapon_roi_layout.addWidget(self.weapon_roi_selector)
        # Weapon ROI overlay toggle
        w_overlay_row = QHBoxLayout()
        self.weapon_overlay_checkbox = QCheckBox("Show Weapon ROI (Debug Overlay)")
        self.weapon_overlay_checkbox.setToolTip("Highlights the Weapon ROI using the global Debug Overlay. Auto-enables Debug Overlay when checked.")
        self.weapon_overlay_checkbox.setChecked(bool(self.config_manager.get('overlay_show_combat_weapon_roi', False)))
        self.weapon_overlay_checkbox.toggled.connect(self._on_weapon_overlay_toggled)
        w_overlay_row.addWidget(self.weapon_overlay_checkbox)
        w_overlay_row.addStretch()
        weapon_roi_layout.addLayout(w_overlay_row)
        roi_group_layout.addWidget(weapon_roi_group)

        # Weapon ROI status label (compact)
        w_status_row = QHBoxLayout()
        w_status_row.addWidget(QLabel("Weapon ROI:"))
        self.weapon_roi_status_label = QLabel(self._roi_text(self.config_manager.get('combat_weapon_roi')))
        self.weapon_roi_status_label.setStyleSheet("color:#777; font-style:italic;")
        w_status_row.addWidget(self.weapon_roi_status_label)
        w_status_row.addStretch()
        roi_group_layout.addLayout(w_status_row)

        roi_tab_layout.addWidget(roi_group)
        # Bottom actions: Precise Mode toggle and Save button
        actions_row = QHBoxLayout()
        self.combat_precise_checkbox = QCheckBox("Use Precise Mode (small ROI)")
        self.combat_precise_checkbox.setToolTip(
            "When enabled, uses a stricter formula for small ROIs: HSV∩RGB match AND Lab ΔE gating,\n"
            "plus S/V minima and tuned morphology for fewer false positives in tight regions."
        )
        try:
            self.combat_precise_checkbox.setChecked(bool(self.config_manager.get('combat_precise_mode', True)))
        except Exception:
            self.combat_precise_checkbox.setChecked(True)
        self.combat_precise_checkbox.toggled.connect(lambda v: self.config_manager.set('combat_precise_mode', bool(v)))
        actions_row.addWidget(self.combat_precise_checkbox)

        actions_row.addStretch()

        save_roi_btn = QPushButton("Save ROI Settings")
        save_roi_btn.setToolTip("Save the ROI and overlay settings to the current profile so the script uses them.")
        save_roi_btn.clicked.connect(lambda: self._save_combat_settings(silent=False))
        actions_row.addWidget(save_roi_btn)

        roi_tab_layout.addLayout(actions_row)
        roi_tab_layout.addStretch()
        self._combat_tabs.addTab(self.roi_tab, "ROI Settings")

        # ---------- Weapon Switching sub-tab ----------
        self.weapon_tab = QWidget()
        w_tab_layout = QVBoxLayout(self.weapon_tab)

        w_group = QGroupBox("Weapon Switching (Color-based)")
        w_group.setToolTip("Click the preferred style/weapon by color inside the Weapon ROI. No XY coordinates.")
        w_layout = QVBoxLayout(w_group)

        info = QLabel("Switches based on preferred style color within the Weapon ROI. No XY coordinates are used.")
        info.setWordWrap(True)
        w_layout.addWidget(info)

        # Weapon color editors (per-style), with pipette picker
        w_colors = QGroupBox("Weapon Colors")
        w_colors.setToolTip("HSV colors to look for in the Weapon ROI when switching to each style.")
        w_colors_layout = QGridLayout(w_colors)
        w_colors_layout.addWidget(QLabel("Melee"), 0, 0)
        self.weapon_melee_color_editor = EnhancedColorEditor(self.config_manager, 'combat_weapon_melee_color', title="Weapon Melee Color")
        self.weapon_melee_color_editor.setToolTip("HSV color to look for in Weapon ROI when switching to Melee.")
        w_colors_layout.addWidget(self.weapon_melee_color_editor, 1, 0)
        w_colors_layout.addWidget(QLabel("Ranged"), 0, 1)
        self.weapon_ranged_color_editor = EnhancedColorEditor(self.config_manager, 'combat_weapon_ranged_color', title="Weapon Ranged Color")
        self.weapon_ranged_color_editor.setToolTip("HSV color to look for in Weapon ROI when switching to Ranged.")
        w_colors_layout.addWidget(self.weapon_ranged_color_editor, 1, 1)
        w_colors_layout.addWidget(QLabel("Magic"), 0, 2)
        self.weapon_magic_color_editor = EnhancedColorEditor(self.config_manager, 'combat_weapon_magic_color', title="Weapon Magic Color")
        self.weapon_magic_color_editor.setToolTip("HSV color to look for in Weapon ROI when switching to Magic.")
        w_colors_layout.addWidget(self.weapon_magic_color_editor, 1, 2)
        w_layout.addWidget(w_colors)

        # Min pixels for weapon color detection (global + per-style)
        w_thr_group = QGroupBox("Min Pixels (Weapon ROI)")
        w_thr_group.setToolTip(
            "Minimum pixels required in the color mask (Weapon ROI) to count a weapon/style as present.\n"
            "Mask is built from the selected HSV color; click happens only if count(mask) ≥ min pixels."
        )
        w_thr_grid = QGridLayout(w_thr_group)

        w_thr_grid.addWidget(QLabel("Global (fallback)"), 0, 0)
        self.weapon_min_pixels_spin = QSpinBox()
        self.weapon_min_pixels_spin.setRange(1, 5000)
        self.weapon_min_pixels_spin.setToolTip("Global fallback threshold used when a per-style value is 0.")
        try:
            self.weapon_min_pixels_spin.setValue(int(self.config_manager.get('combat_weapon_min_pixels', 30)))
        except Exception:
            self.weapon_min_pixels_spin.setValue(30)
        self.weapon_min_pixels_spin.valueChanged.connect(lambda v: self.config_manager.set('combat_weapon_min_pixels', int(v)))
        w_thr_grid.addWidget(self.weapon_min_pixels_spin, 0, 1)

        w_thr_grid.addWidget(QLabel("Melee"), 1, 0)
        self.weapon_min_pixels_melee_spin = QSpinBox()
        self.weapon_min_pixels_melee_spin.setRange(0, 5000)
        try:
            self.weapon_min_pixels_melee_spin.setValue(int(self.config_manager.get('combat_weapon_min_pixels_melee', 0) or 0))
        except Exception:
            self.weapon_min_pixels_melee_spin.setValue(0)
        self.weapon_min_pixels_melee_spin.setToolTip("Override for melee. 0 = use Global fallback.")
        self.weapon_min_pixels_melee_spin.valueChanged.connect(lambda v: self.config_manager.set('combat_weapon_min_pixels_melee', int(v)))
        w_thr_grid.addWidget(self.weapon_min_pixels_melee_spin, 1, 1)

        w_thr_grid.addWidget(QLabel("Ranged"), 2, 0)
        self.weapon_min_pixels_ranged_spin = QSpinBox()
        self.weapon_min_pixels_ranged_spin.setRange(0, 5000)
        try:
            self.weapon_min_pixels_ranged_spin.setValue(int(self.config_manager.get('combat_weapon_min_pixels_ranged', 0) or 0))
        except Exception:
            self.weapon_min_pixels_ranged_spin.setValue(0)
        self.weapon_min_pixels_ranged_spin.setToolTip("Override for ranged. 0 = use Global fallback.")
        self.weapon_min_pixels_ranged_spin.valueChanged.connect(lambda v: self.config_manager.set('combat_weapon_min_pixels_ranged', int(v)))
        w_thr_grid.addWidget(self.weapon_min_pixels_ranged_spin, 2, 1)

        w_thr_grid.addWidget(QLabel("Magic"), 3, 0)
        self.weapon_min_pixels_magic_spin = QSpinBox()
        self.weapon_min_pixels_magic_spin.setRange(0, 5000)
        try:
            self.weapon_min_pixels_magic_spin.setValue(int(self.config_manager.get('combat_weapon_min_pixels_magic', 0) or 0))
        except Exception:
            self.weapon_min_pixels_magic_spin.setValue(0)
        self.weapon_min_pixels_magic_spin.setToolTip("Override for magic. 0 = use Global fallback.")
        self.weapon_min_pixels_magic_spin.valueChanged.connect(lambda v: self.config_manager.set('combat_weapon_min_pixels_magic', int(v)))
        w_thr_grid.addWidget(self.weapon_min_pixels_magic_spin, 3, 1)

        w_layout.addWidget(w_thr_group)

        # Test switch
        w_test_row = QHBoxLayout()
        self.test_switch_btn = QPushButton("Test Switch Style Now")
        self.test_switch_btn.setToolTip(
            "Looks for the Preferred style’s color in the Weapon ROI using thresholds and clicks it once if found.\n"
            "Use this to validate your color and pixel settings."
        )
        self.test_switch_btn.clicked.connect(self._on_test_switch_style_clicked)
        w_test_row.addWidget(self.test_switch_btn)
        self.weapon_status_label = QLabel("Switch: (idle)")
        self.weapon_status_label.setStyleSheet("color:#6aa; font-weight:bold;")
        w_test_row.addWidget(self.weapon_status_label)
        w_test_row.addStretch()
        save_weapon_btn = QPushButton("Save Combat Settings")
        save_weapon_btn.setToolTip("Save all Combat settings to the current profile.")
        save_weapon_btn.clicked.connect(lambda: self._save_combat_settings(silent=False))
        w_test_row.addWidget(save_weapon_btn)
        w_layout.addLayout(w_test_row)

        w_tab_layout.addWidget(w_group)
        w_tab_layout.addStretch()
        self._combat_tabs.addTab(self.weapon_tab, "Weapon Switching")
        
        # Load any saved settings into UI once all widgets exist
        try:
            self._load_style_settings_into_ui()
        except Exception:
            pass

        # If overlay was previously enabled in profile, actually enable/show it now
        try:
            self._on_style_overlay_toggled(bool(self.style_overlay_checkbox.isChecked()))
        except Exception:
            pass

    # ---------- Combat Style helpers ----------
    # No preferred style support any more

    def _on_style_roi_changed(self, roi):
        try:
            self.config_manager.set_roi('combat_style_roi', roi)
        except Exception:
            pass
        # Update overlay
        try:
            if self._style_overlay is not None:
                self._style_overlay.set_roi(roi)
        except Exception:
            pass
        try:
            self.style_roi_status_label.setText(self._roi_text(roi))
        except Exception:
            pass

    def _on_weapon_roi_changed(self, roi):
        try:
            self.config_manager.set_roi('combat_weapon_roi', roi)
        except Exception:
            pass
        try:
            self.weapon_roi_status_label.setText(self._roi_text(roi))
        except Exception:
            pass

    def _on_style_overlay_toggled(self, checked: bool):
        # Route to Debug Overlay flags; also auto-enable main Debug Overlay when turning this on
        self.config_manager.set('overlay_show_combat_style_roi', bool(checked))
        if checked:
            try:
                self.config_manager.set('debug_overlay', True)
            except Exception:
                pass
        # Update status label to reflect visibility intent
        try:
            self.style_roi_status_label.setText(self._roi_text(self.config_manager.get('combat_style_roi')))
        except Exception:
            pass

    def _on_weapon_overlay_toggled(self, checked: bool):
        self.config_manager.set('overlay_show_combat_weapon_roi', bool(checked))
        if checked:
            try:
                self.config_manager.set('debug_overlay', True)
            except Exception:
                pass

    def _on_test_style_clicked(self):
        try:
            det = None
            if self.bot_controller and getattr(self.bot_controller, 'detection_engine', None):
                det = self.bot_controller.detection_engine
            # Prefer counts API for transparency during tuning
            result = det.detect_combat_style_counts() if det else None
            if result is None:
                self.style_status_label.setText("Current style: (error)")
                return
            style = result.get('style')
            c = result.get('counts', {})
            thr = result.get('thresholds', {})
            melee_txt = f"M:{c.get('melee',0)}/{thr.get('melee','-')}"
            ranged_txt = f"R:{c.get('ranged',0)}/{thr.get('ranged','-')}"
            magic_txt = f"Mg:{c.get('magic',0)}/{thr.get('magic','-')}"
            # Show explicit 'false' when none of the style colors exceed thresholds
            label = style if style else 'false'
            self.style_status_label.setText(f"Current style: {label}  |  {melee_txt}  {ranged_txt}  {magic_txt}")
        except Exception as e:
            logger.error(f"Test style detect error: {e}")
            self.style_status_label.setText("Current style: (error)")

    def _on_test_switch_style_clicked(self):
        try:
            det = getattr(self.bot_controller, 'detection_engine', None)
            am = getattr(self.bot_controller, 'action_manager', None)
            if not det:
                if hasattr(self, 'weapon_status_label'):
                    self.weapon_status_label.setText("Switch test: detection unavailable")
                return
            st = det.detect_combat_style()
            if not st:
                if hasattr(self, 'weapon_status_label'):
                    self.weapon_status_label.setText("Switch test: style not detected")
                return
            pt = det.detect_weapon_for_style(st)
            if pt is None:
                if hasattr(self, 'weapon_status_label'):
                    self.weapon_status_label.setText(f"Switch test: no match in Weapon ROI for style '{st}'")
                return
            # Perform a single click if action manager is available
            if am and am.mouse_controller:
                ok = am.mouse_controller.move_and_click(int(pt[0]), int(pt[1]))
                if ok:
                    if hasattr(self, 'weapon_status_label'):
                        self.weapon_status_label.setText(f"Switch test: clicked at {pt} for style '{st}'")
                else:
                    if hasattr(self, 'weapon_status_label'):
                        self.weapon_status_label.setText(f"Switch test: failed click at {pt} for style '{st}'")
            else:
                if hasattr(self, 'weapon_status_label'):
                    self.weapon_status_label.setText(f"Switch test: found at {pt} (no click) for style '{st}'")
        except Exception as e:
            logger.error(f"Test switch style error: {e}")
            if hasattr(self, 'weapon_status_label'):
                self.weapon_status_label.setText("Switch test: (error)")

    # Lightweight save hook for Combat Settings
    def _save_combat_settings(self, silent: bool = False):
        try:
            prof = getattr(self.config_manager, 'current_profile', None)
            target = prof if prof else 'v2 instance.json'
            ok = self.config_manager.save_profile(target)
            if not silent:
                # Try to place feedback near whichever tab is active
                msg = "Saved" if ok else "Save failed"
                if hasattr(self, 'style_status_label') and self._combat_tabs.currentWidget() is self.style_tab:
                    self.style_status_label.setText(f"{msg} → {target}")
                if hasattr(self, 'weapon_status_label') and self._combat_tabs.currentWidget() is self.weapon_tab:
                    self.weapon_status_label.setText(f"{msg} → {target}")
        except Exception as e:
            logger.error(f"Combat settings save error: {e}")

    def _load_style_settings_into_ui(self):
        try:
            roi = self.config_manager.get_roi('combat_style_roi')
            if roi:
                self.style_roi_selector.set_roi(roi)
        except Exception:
            pass
        try:
            wroi = self.config_manager.get_roi('combat_weapon_roi')
            if wroi:
                self.weapon_roi_selector.set_roi(wroi)
        except Exception:
            pass
        # Refresh status labels
        try:
            self.style_roi_status_label.setText(self._roi_text(self.config_manager.get('combat_style_roi')))
        except Exception:
            pass
        try:
            self.weapon_roi_status_label.setText(self._roi_text(self.config_manager.get('combat_weapon_roi')))
        except Exception:
            pass
        # No coordinates to load; switching is color-based

    def _roi_text(self, roi_dict):
        if not roi_dict:
            return "(none)"
        try:
            return f"{roi_dict['left']},{roi_dict['top']}  {roi_dict['width']}x{roi_dict['height']}"
        except Exception:
            return str(roi_dict)

    def on_pick_hpbar_roi(self):
        dlg = ZoomRoiPickerDialog(self.config_manager, self)
        if dlg.exec_() == dlg.Accepted and dlg.result_rect is not None:
            r = dlg.result_rect
            roi = {"left": int(r.left()), "top": int(r.top()), "width": int(r.width()), "height": int(r.height())}
            self.config_manager.set('hpbar_roi', roi)
            self.hpbar_roi_label.setText(self._roi_text(roi))
            logger.info(f"HP bar ROI set to {roi}")

    def on_clear_hpbar_roi(self):
        self.config_manager.set('hpbar_roi', None)
        self.hpbar_roi_label.setText(self._roi_text(None))
        logger.info("HP bar ROI cleared")
    
    def on_hpbar_detect_toggled(self, checked):
        """Handle HP bar detection toggle"""
        logger.debug(f"HP bar detection {'enabled' if checked else 'disabled'}")
        self.config_manager.set('hpbar_detect_enabled', checked)
    
    def on_hpbar_min_area_changed(self, value):
        """Handle HP bar min area change"""
        logger.debug(f"HP bar minimum area set to {value}")
        self.config_manager.set('hpbar_min_area', value)
    
    def on_hpbar_min_pixel_matches_changed(self, value):
        """Handle HP bar min pixel matches change"""
        logger.debug(f"HP bar minimum pixel matches set to {value}")
        self.config_manager.set('hpbar_min_pixel_matches', value)
    
    def on_post_combat_delay_min_changed(self, value):
        """Handle post-combat delay min change"""
        logger.debug(f"Post-combat delay min set to {value} seconds")
        self.config_manager.set('post_combat_delay_min_s', value)
        
        # Ensure max is not less than min
        max_value = self.post_combat_delay_max_selector.get_time()
        if value > max_value:
            self.post_combat_delay_max_selector.set_time(value)
    
    def on_post_combat_delay_max_changed(self, value):
        """Handle post-combat delay max change"""
        logger.debug(f"Post-combat delay max set to {value} seconds")
        self.config_manager.set('post_combat_delay_max_s', value)
        
        # Ensure min is not greater than max
        min_value = self.post_combat_delay_min_selector.get_time()
        if value < min_value:
            self.post_combat_delay_min_selector.set_time(value)
    
    def on_combat_timeout_changed(self, value):
        """Handle combat timeout change"""
        logger.debug(f"Combat not seen timeout set to {value} seconds")
        self.config_manager.set('combat_not_seen_timeout_s', value)

    def on_attack_grace_changed(self, value):
        """Handle attack grace change"""
        logger.debug(f"Attack grace set to {value} seconds")
        self.config_manager.set('attack_grace_s', value)
    
    def on_enable_cam_adjust_toggled(self, checked):
        """Handle enable camera adjustment toggle"""
        logger.debug(f"Camera adjustment {'enabled' if checked else 'disabled'}")
        self.config_manager.set('enable_cam_adjust', checked)
    
    def on_cam_adjust_hold_changed(self, value):
        """Handle camera adjust hold change"""
        logger.debug(f"Camera adjust hold set to {value} seconds")
        self.config_manager.set('cam_adjust_hold_s', value)
    
    def on_cam_adjust_gap_changed(self, value):
        """Handle camera adjust gap change"""
        logger.debug(f"Camera adjust gap set to {value} seconds")
        self.config_manager.set('cam_adjust_gap_s', value)
    
    def on_micro_adjust_every_changed(self, value):
        """Handle micro adjust every change"""
        logger.debug(f"Micro adjust every set to {value} loops")
        self.config_manager.set('micro_adjust_every_loops', value)
    
    def on_micro_adjust_hold_changed(self, value):
        """Handle micro adjust hold change"""
        logger.debug(f"Micro adjust hold set to {value} seconds")
        self.config_manager.set('micro_adjust_hold_s', value)
    
    def on_micro_adjust_gap_changed(self, value):
        """Handle micro adjust gap change"""
        logger.debug(f"Micro adjust gap set to {value} seconds")
        self.config_manager.set('micro_adjust_gap_s', value)