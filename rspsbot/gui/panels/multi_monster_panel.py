"""
Multi Monster Mode panel for RSPS Color Bot v3
"""
import logging
import time
import os
from ..utils.roi_utils import format_roi
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox, QGridLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QSlider,
    QScrollArea
)
from PyQt5.QtCore import Qt

from .detection_panel import ColorSpecEditor
from ..components.screen_picker import ZoomRoiPickerDialog, ZoomColorPickerDialog
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

        # Monster Configuration using sub-tabs per style (Option B)
        monsters_group = QGroupBox("Monster Configuration")
        monsters_group.setToolTip("Configure each monster's color cleanly in its own tab (Melee/Ranged/Magic)")
        monsters_layout_inner = QVBoxLayout(monsters_group)

        self.monsters_subtabs = QTabWidget()

        # Melee tab
        melee_tab = QWidget()
        melee_layout = QVBoxLayout(melee_tab)
        self.melee_monster_editor = EnhancedColorEditor(self.config_manager, 'multi_monster_monster_melee_color', title="Monster Color")
        try:
            self.melee_monster_editor.setMinimumHeight(180)
        except Exception:
            pass
        melee_layout.addWidget(self.melee_monster_editor)
        # Melee alternates
        melee_alt_row = QHBoxLayout()
        self.melee_alt_count = QLabel("Alternates: 0")
        melee_alt_row.addWidget(self.melee_alt_count)
        self.melee_add_alt_btn = QPushButton("Add Alternate Color…")
        self.melee_add_alt_btn.setToolTip("Pick an additional color for the Melee monster (OR-matched).")
        self.melee_add_alt_btn.clicked.connect(lambda: self.on_add_alternate_color('melee'))
        melee_alt_row.addWidget(self.melee_add_alt_btn)
        self.melee_clear_alt_btn = QPushButton("Clear Alternates")
        self.melee_clear_alt_btn.clicked.connect(lambda: self.on_clear_alternate_colors('melee'))
        melee_alt_row.addWidget(self.melee_clear_alt_btn)
        melee_layout.addLayout(melee_alt_row)
        melee_btn_row = QHBoxLayout()
        melee_btn_row.addStretch()
        self.melee_test_btn = QPushButton("Test Melee")
        self.melee_test_btn.clicked.connect(lambda: self.on_test_monster_detection_style('melee'))
        melee_btn_row.addWidget(self.melee_test_btn)
        melee_layout.addLayout(melee_btn_row)
        self.monsters_subtabs.addTab(melee_tab, "Melee")

        # Ranged tab
        ranged_tab = QWidget()
        ranged_layout = QVBoxLayout(ranged_tab)
        self.ranged_monster_editor = EnhancedColorEditor(self.config_manager, 'multi_monster_monster_ranged_color', title="Monster Color")
        try:
            self.ranged_monster_editor.setMinimumHeight(180)
        except Exception:
            pass
        ranged_layout.addWidget(self.ranged_monster_editor)
        # Ranged alternates
        ranged_alt_row = QHBoxLayout()
        self.ranged_alt_count = QLabel("Alternates: 0")
        ranged_alt_row.addWidget(self.ranged_alt_count)
        self.ranged_add_alt_btn = QPushButton("Add Alternate Color…")
        self.ranged_add_alt_btn.setToolTip("Pick an additional color for the Ranged monster (OR-matched).")
        self.ranged_add_alt_btn.clicked.connect(lambda: self.on_add_alternate_color('ranged'))
        ranged_alt_row.addWidget(self.ranged_add_alt_btn)
        self.ranged_clear_alt_btn = QPushButton("Clear Alternates")
        self.ranged_clear_alt_btn.clicked.connect(lambda: self.on_clear_alternate_colors('ranged'))
        ranged_alt_row.addWidget(self.ranged_clear_alt_btn)
        ranged_layout.addLayout(ranged_alt_row)
        ranged_btn_row = QHBoxLayout()
        ranged_btn_row.addStretch()
        self.ranged_test_btn = QPushButton("Test Ranged")
        self.ranged_test_btn.clicked.connect(lambda: self.on_test_monster_detection_style('ranged'))
        ranged_btn_row.addWidget(self.ranged_test_btn)
        ranged_layout.addLayout(ranged_btn_row)
        self.monsters_subtabs.addTab(ranged_tab, "Ranged")

        # Magic tab
        magic_tab = QWidget()
        magic_layout = QVBoxLayout(magic_tab)
        self.magic_monster_editor = EnhancedColorEditor(self.config_manager, 'multi_monster_monster_magic_color', title="Monster Color")
        try:
            self.magic_monster_editor.setMinimumHeight(180)
        except Exception:
            pass
        magic_layout.addWidget(self.magic_monster_editor)
        # Magic alternates
        magic_alt_row = QHBoxLayout()
        self.magic_alt_count = QLabel("Alternates: 0")
        magic_alt_row.addWidget(self.magic_alt_count)
        self.magic_add_alt_btn = QPushButton("Add Alternate Color…")
        self.magic_add_alt_btn.setToolTip("Pick an additional color for the Magic monster (OR-matched).")
        self.magic_add_alt_btn.clicked.connect(lambda: self.on_add_alternate_color('magic'))
        magic_alt_row.addWidget(self.magic_add_alt_btn)
        self.magic_clear_alt_btn = QPushButton("Clear Alternates")
        self.magic_clear_alt_btn.clicked.connect(lambda: self.on_clear_alternate_colors('magic'))
        magic_alt_row.addWidget(self.magic_clear_alt_btn)
        magic_layout.addLayout(magic_alt_row)
        magic_btn_row = QHBoxLayout()
        magic_btn_row.addStretch()
        self.magic_test_btn = QPushButton("Test Magic")
        self.magic_test_btn.clicked.connect(lambda: self.on_test_monster_detection_style('magic'))
        magic_btn_row.addWidget(self.magic_test_btn)
        magic_layout.addLayout(magic_btn_row)
        self.monsters_subtabs.addTab(magic_tab, "Magic")

        monsters_layout_inner.addWidget(self.monsters_subtabs)
        # Wrap monster group in a scroll area to avoid cramped layout
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_v = QVBoxLayout(scroll_content)
        scroll_v.setContentsMargins(0, 0, 0, 0)
        scroll_v.addWidget(monsters_group)
        scroll_v.addStretch(1)
        scroll.setWidget(scroll_content)
        monsters_layout.addWidget(scroll)
        # Add the Monsters tab to the main tabs
        self._tabs.addTab(self.monsters_tab, "Monsters")

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

        # Template Assist for Weapon Detection
        template_group = QGroupBox("Weapon Template Assist")
        template_group.setToolTip("Use a small image template to help detect dark/low-chroma icons like melee. Edge mode with threshold and optional search window.")
        template_layout = QGridLayout(template_group)

        # Enable checkbox
        self.template_enable_cb = QCheckBox("Enable Template Assist")
        self.template_enable_cb.setChecked(self.config_manager.get('weapon_template_enable', True))
        template_layout.addWidget(self.template_enable_cb, 0, 0, 1, 2)

        # Mode selector
        template_layout.addWidget(QLabel("Mode:"), 1, 0)
        self.template_mode_combo = QComboBox()
        self.template_mode_combo.addItems(["edge", "gray"])
        self.template_mode_combo.setCurrentText(self.config_manager.get('weapon_template_mode', 'edge'))
        template_layout.addWidget(self.template_mode_combo, 1, 1)

        # Threshold
        template_layout.addWidget(QLabel("Threshold:"), 1, 2)
        self.template_thr_spin = QDoubleSpinBox()
        self.template_thr_spin.setRange(0.0, 1.0)
        self.template_thr_spin.setSingleStep(0.01)
        self.template_thr_spin.setValue(self.config_manager.get('weapon_template_threshold', 0.58))
        template_layout.addWidget(self.template_thr_spin, 1, 3)

        # Search window
        template_layout.addWidget(QLabel("Search Window (px):"), 2, 0)
        self.template_win_spin = QSpinBox()
        self.template_win_spin.setRange(0, 600)
        self.template_win_spin.setValue(self.config_manager.get('weapon_template_window', 200))
        template_layout.addWidget(self.template_win_spin, 2, 1)

        # Melee template path label (read-only display)
        self.melee_template_label = QLabel(str(self.config_manager.get('weapon_melee_template_path', 'None')))
        template_layout.addWidget(QLabel("Melee Template:"), 3, 0)
        template_layout.addWidget(self.melee_template_label, 3, 1, 1, 2)

        # Button to load melee template from file using the GUI color/roi picker flow
        self.load_melee_template_btn = QPushButton("Load Melee Template…")
        self.load_melee_template_btn.clicked.connect(self.on_load_melee_template)
        template_layout.addWidget(self.load_melee_template_btn, 3, 3)

        # Test Melee Template button
        self.test_melee_template_btn = QPushButton("Test Melee Template")
        self.test_melee_template_btn.setToolTip("Run template matching in the current Weapon ROI and report PASS/FAIL.")
        self.test_melee_template_btn.clicked.connect(self.on_test_melee_template)
        template_layout.addWidget(self.test_melee_template_btn, 4, 0, 1, 4)

        # Magic template path label
        self.magic_template_label = QLabel(str(self.config_manager.get('weapon_magic_template_path', 'None')))
        template_layout.addWidget(QLabel("Magic Template:"), 5, 0)
        template_layout.addWidget(self.magic_template_label, 5, 1, 1, 2)

        # Button to load magic template from file
        self.load_magic_template_btn = QPushButton("Load Magic Template…")
        self.load_magic_template_btn.clicked.connect(self.on_load_magic_template)
        template_layout.addWidget(self.load_magic_template_btn, 5, 3)

        # Test Magic Template button
        self.test_magic_template_btn = QPushButton("Test Magic Template")
        self.test_magic_template_btn.setToolTip("Run template matching for Magic in the current Weapon ROI and report PASS/FAIL.")
        self.test_magic_template_btn.clicked.connect(self.on_test_magic_template)
        template_layout.addWidget(self.test_magic_template_btn, 6, 0, 1, 4)

        weapons_layout.addWidget(template_group)

        # Test Click buttons per style
        test_click_group = QGroupBox("Test Click (Weapon ROI)")
        test_click_group.setToolTip("Compute a click point for each style inside the Weapon ROI using color/template, and log whether it was found.")
        test_click_layout = QHBoxLayout(test_click_group)
        self.test_click_melee_btn = QPushButton("Test Click: Melee")
        self.test_click_melee_btn.clicked.connect(lambda: self.on_test_click_style('melee'))
        test_click_layout.addWidget(self.test_click_melee_btn)
        self.test_click_ranged_btn = QPushButton("Test Click: Ranged")
        self.test_click_ranged_btn.clicked.connect(lambda: self.on_test_click_style('ranged'))
        test_click_layout.addWidget(self.test_click_ranged_btn)
        self.test_click_magic_btn = QPushButton("Test Click: Magic")
        self.test_click_magic_btn.clicked.connect(lambda: self.on_test_click_style('magic'))
        test_click_layout.addWidget(self.test_click_magic_btn)
        test_click_layout.addStretch()
        weapons_layout.addWidget(test_click_group)
        
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

        # ---------- Tile Settings sub-tab ----------
        self.tiles_tab = QWidget()
        tiles_layout = QVBoxLayout(self.tiles_tab)

        tile_group = QGroupBox("Tile Settings")
        tile_group.setToolTip("Override tile search radius for Multi Monster Mode. This strictly gates how far from a tile a monster can be detected.")
        tile_group_layout = QVBoxLayout(tile_group)

        # Single slider to control tile radius
        row = QHBoxLayout()
        row.addWidget(QLabel("Tile Search Radius (px):"))
        self.tile_radius_slider = QSlider()  # type: ignore[call-arg]
        # Set orientation to Horizontal without relying on enum stubs
        try:
            self.tile_radius_slider.setOrientation(1)  # type: ignore[arg-type]
        except Exception:
            pass
        self.tile_radius_slider.setMinimum(20)
        self.tile_radius_slider.setMaximum(240)
        self.tile_radius_slider.setSingleStep(1)
        self.tile_radius_slider.setPageStep(5)
        self.tile_radius_slider.setValue(int(self.config_manager.get('multi_monster_tile_radius', 120)))
        row.addWidget(self.tile_radius_slider)
        self.tile_radius_value = QLabel(str(int(self.config_manager.get('multi_monster_tile_radius', 120))))
        row.addWidget(self.tile_radius_value)
        row.addStretch()
        tile_group_layout.addLayout(row)

        # Keep label in sync with slider
        self.tile_radius_slider.valueChanged.connect(lambda v: self.tile_radius_value.setText(str(int(v))))

        tiles_layout.addWidget(tile_group)

        # Apply/Reset for tile tab
        tiles_btns = QHBoxLayout()
        tiles_btns.addStretch()
        self.tiles_apply_btn = QPushButton("Apply Changes")
        self.tiles_apply_btn.clicked.connect(self.on_tiles_apply_clicked)
        tiles_btns.addWidget(self.tiles_apply_btn)
        self.tiles_reset_btn = QPushButton("Reset to Default")
        self.tiles_reset_btn.clicked.connect(self.on_tiles_reset_clicked)
        tiles_btns.addWidget(self.tiles_reset_btn)
        tiles_layout.addLayout(tiles_btns)
        tiles_layout.addStretch()

        self._tabs.addTab(self.tiles_tab, "Tile Settings")

        # Hydrate editors from existing multi_monster_configs if present
        self._hydrate_monster_editors_from_config()
        self._update_alternate_counts()
        # Finally, sync the rest of the controls from config
        self.reload_from_config()

    def reload_from_config(self):
        """Reload all Multi Monster UI controls from the current config.

        Call this after loading a profile so the panel reflects persisted values.
        """
        try:
            # General settings
            self.enable_checkbox.setChecked(self.config_manager.get('multi_monster_mode_enabled', False))
            self.wait_time_spin.setValue(float(self.config_manager.get('multi_monster_post_attack_wait', 2.0)))
            self.precision_combo.setCurrentText(self.config_manager.get('multi_monster_precision_mode', 'Normal'))
            self.lab_tolerance_spin.setValue(int(self.config_manager.get('multi_monster_lab_tolerance', 15)))
            self.sat_min_spin.setValue(int(self.config_manager.get('multi_monster_sat_min', 50)))
            self.val_min_spin.setValue(int(self.config_manager.get('multi_monster_val_min', 50)))
            self.morph_open_spin.setValue(int(self.config_manager.get('multi_monster_morph_open_iters', 1)))
            self.morph_close_spin.setValue(int(self.config_manager.get('multi_monster_morph_close_iters', 2)))
            self.overlay_checkbox.setChecked(self.config_manager.get('multi_monster_overlay_enabled', False))

            # Sub-tabs enable state mirrors mode toggle
            try:
                self.monsters_tab.setEnabled(bool(self.enable_checkbox.isChecked()))
                self.weapons_tab.setEnabled(bool(self.enable_checkbox.isChecked()))
            except Exception:
                pass

            # Monster color editors from multi_monster_configs
            self._hydrate_monster_editors_from_config()
            self._update_alternate_counts()

            # Weapon colors
            try:
                melee_spec = self.config_manager.get_color_spec('multi_monster_melee_weapon_color')
                if melee_spec:
                    self.melee_weapon_color_editor.set_color_spec(melee_spec)
                ranged_spec = self.config_manager.get_color_spec('multi_monster_ranged_weapon_color')
                if ranged_spec:
                    self.ranged_weapon_color_editor.set_color_spec(ranged_spec)
                magic_spec = self.config_manager.get_color_spec('multi_monster_magic_weapon_color')
                if magic_spec:
                    self.magic_weapon_color_editor.set_color_spec(magic_spec)
            except Exception:
                pass

            # Template assist
            try:
                self.template_enable_cb.setChecked(self.config_manager.get('weapon_template_enable', True))
                mode = str(self.config_manager.get('weapon_template_mode', 'edge'))
                if mode.lower() in ('edge', 'gray'):
                    # Ensure proper casing of option text
                    self.template_mode_combo.setCurrentText(mode.lower())
                thr = float(self.config_manager.get('weapon_template_threshold', 0.58))
                self.template_thr_spin.setValue(thr)
                win = int(self.config_manager.get('weapon_template_window', 200))
                self.template_win_spin.setValue(win)
                # Template paths into labels
                self.melee_template_label.setText(str(self.config_manager.get('weapon_melee_template_path', 'None')))
                # Ranged has no dedicated label yet; skip
                self.magic_template_label.setText(str(self.config_manager.get('weapon_magic_template_path', 'None')))
            except Exception:
                pass

            # Tile settings
            try:
                radius = int(self.config_manager.get('multi_monster_tile_radius', 120))
                self.tile_radius_slider.setValue(radius)
                if hasattr(self, 'tile_radius_value'):
                    self.tile_radius_value.setText(str(radius))
            except Exception:
                pass

            # Weapon ROI label
            try:
                self.weapon_roi_label.setText(self._roi_text(self.config_manager.get('weapon_roi')))
            except Exception:
                pass
        except Exception as e:
            logger.error(f"[MultiMonsterPanel] reload_from_config failed: {e}")


    def _capture_weapon_frame(self):
        """Capture and return the current weapon ROI frame, or None if unavailable."""
        try:
            from ...core.detection.capture import CaptureService
            roi = self.config_manager.get_roi('weapon_roi')
            if not roi:
                return None
            cs = CaptureService()
            return cs.capture_region(roi)
        except Exception:
            return None
    
    def _init_monster_table(self):
        """Initialize the monster configuration table"""
        monster_configs = self.config_manager.get('multi_monster_configs', [
            {'color': {'rgb': [255, 0, 0], 'tol_rgb': 15}, 'style': 'melee'},
            {'color': {'rgb': [0, 255, 0], 'tol_rgb': 15}, 'style': 'ranged'},
            {'color': {'rgb': [0, 0, 255], 'tol_rgb': 15}, 'style': 'magic'}
        ])
        # Legacy table init retained for compatibility if we ever show it again.
        # No-op under new sub-tab UI.
        return

    def _hydrate_monster_editors_from_config(self):
        """Read multi_monster_configs and push colors into the three editors."""
        try:
            cfgs = self.config_manager.get('multi_monster_configs', []) or []
            by_style = {}
            for c in cfgs:
                style = c.get('style') if isinstance(c, dict) else None
                if style and 'color' in c:
                    by_style[style] = c['color']
                    # Support optional alternates list
                    if 'alternates' in c and isinstance(c['alternates'], list):
                        self.config_manager.set(f'multi_monster_{style}_alternates', c['alternates'])
            if 'melee' in by_style:
                self.melee_monster_editor.set_color_spec(by_style['melee'])
            if 'ranged' in by_style:
                self.ranged_monster_editor.set_color_spec(by_style['ranged'])
            if 'magic' in by_style:
                self.magic_monster_editor.set_color_spec(by_style['magic'])
        except Exception as e:
            logger.debug(f"_hydrate_monster_editors_from_config error: {e}")
    
    def _update_alternate_counts(self):
        """Update the label counts for alternates loaded in config."""
        try:
            for style, label in [('melee', self.melee_alt_count), ('ranged', self.ranged_alt_count), ('magic', self.magic_alt_count)]:
                alts = self.config_manager.get(f'multi_monster_{style}_alternates', []) or []
                try:
                    n = len(alts) if isinstance(alts, list) else 0
                except Exception:
                    n = 0
                label.setText(f"Alternates: {n}")
        except Exception:
            pass
    
    def _roi_text(self, roi):
        return format_roi(roi)
    
    def on_mode_toggled(self, checked):
        """Handle mode toggle"""
        try:
            # Persist immediately so the main loop respects it next tick
            self.config_manager.set('multi_monster_mode_enabled', bool(checked))
            # Enable/disable monster and weapon sub-tabs to avoid accidental edits while off
            try:
                self.monsters_tab.setEnabled(bool(checked))
                self.weapons_tab.setEnabled(bool(checked))
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error toggling Multi Monster Mode: {e}")
    
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
    
    
    def on_pick_weapon_roi(self):
        """Pick weapon detection ROI from screen"""
        try:
            picker = AdvancedROISelector(self.config_manager, self, "Select Weapon Detection Region")
            if picker.exec_() == AdvancedROISelector.Accepted:
                roi = picker.get_roi()
                if roi:
                    # Normalize and persist via ConfigManager helper (handles absolute/relative)
                    try:
                        self.config_manager.set_roi('weapon_roi', roi)
                    except Exception:
                        # Fallback to raw set if helper unavailable
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
            style_combo = self.monsters_table.cellWidget(row, 1)
            if not color_editor:
                return
            color_spec = color_editor.get_color_spec()
            style = style_combo.currentText() if style_combo else 'unknown'

            # Persist a temporary monster config for this test row so detector can use it
            temp_key = f'multi_monster_test_row_{row}_color'
            self.config_manager.set(temp_key, {
                'rgb': list(color_spec.rgb),
                'tol_rgb': color_spec.tol_rgb,
                'use_hsv': color_spec.use_hsv,
                'tol_h': color_spec.tol_h,
                'tol_s': color_spec.tol_s,
                'tol_v': color_spec.tol_v
            })

            # Capture a fresh frame via CaptureService
            from ...core.detection.capture import CaptureService
            cs = CaptureService()
            bbox = cs.get_window_bbox()
            frame = cs.capture(bbox)
            if frame is None:
                QMessageBox.warning(self, "Test Detection", "Failed to capture frame.")
                return

            # Build a simple faux base ROI: entire window
            base_roi = {
                'left': bbox.get('left', 0),
                'top': bbox.get('top', 0),
                'width': bbox.get('width', frame.shape[1]),
                'height': bbox.get('height', frame.shape[0])
            }

            # Instantiate a lightweight detector instance for testing
            from ...core.detection.multi_monster_detector import MultiMonsterDetector
            test_detector = MultiMonsterDetector(self.config_manager, cs)
            # Inject only this monster's mapping for the test
            test_detector.monster_style_map = {tuple(color_spec.rgb): style}

            monsters = test_detector.detect_monsters_with_styles(frame, base_roi)
            count = len(monsters)

            # Aggregate metadata
            areas = [m.get('area', 0) for m in monsters]
            styles = [m.get('combat_style') for m in monsters]
            centers = [(m.get('center_x'), m.get('center_y')) for m in monsters[:5]]  # limit preview

            logger.info(
                "[MultiMonster Test] Row %d style=%s rgb=%s tol_rgb=%d monsters=%d areas=%s styles=%s centers(sample)=%s",
                row+1, style, color_spec.rgb, color_spec.tol_rgb, count, areas, styles, centers
            )

            detail_lines = [
                f"Monster {i+1}: center=({m.get('center_x')},{m.get('center_y')}), area={m.get('area')}, style={m.get('combat_style')}, color={m.get('color_rgb')}" for i, m in enumerate(monsters[:10])
            ]
            detail_text = "\n".join(detail_lines) if detail_lines else "None"

            QMessageBox.information(
                self,
                "Test Detection",
                (
                    f"Tested monster row {row+1}\n"
                    f"Configured Style: {style}\n"
                    f"Color RGB: {color_spec.rgb} tol_rgb={color_spec.tol_rgb}\n"
                    f"Detected Monsters: {count}\n"
                    f"Areas: {areas}\n"
                    f"Styles: {styles}\n"
                    f"Sample Centers: {centers}\n\n"
                    f"Details:\n{detail_text}"
                )
            )

            # Persist summary metrics for overlay/debug
            try:
                self.config_manager.set('multi_monster_last_test', {
                    'timestamp': time.time(),
                    'row': row+1,
                    'style': style,
                    'rgb': list(color_spec.rgb),
                    'tol_rgb': color_spec.tol_rgb,
                    'count': count,
                    'areas': areas,
                    'centers': centers,
                })
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error testing monster detection: {e}")

    def on_test_monster_detection_style(self, style: str):
        """Test monster detection using the editor on the given style tab (melee/ranged/magic)."""
        try:
            editor = {
                'melee': self.melee_monster_editor,
                'ranged': self.ranged_monster_editor,
                'magic': self.magic_monster_editor,
            }.get(style)
            if not editor:
                return
            color_spec = editor.get_color_spec()

            # Persist a temporary monster config for this style
            temp_key = f'multi_monster_test_{style}_color'
            self.config_manager.set(temp_key, {
                'rgb': list(color_spec.rgb),
                'tol_rgb': color_spec.tol_rgb,
                'use_hsv': color_spec.use_hsv,
                'tol_h': color_spec.tol_h,
                'tol_s': color_spec.tol_s,
                'tol_v': color_spec.tol_v
            })

            # Capture a fresh frame via CaptureService
            from ...core.detection.capture import CaptureService
            cs = CaptureService()
            bbox = cs.get_window_bbox()
            frame = cs.capture(bbox)
            if frame is None:
                QMessageBox.warning(self, "Test Detection", "Failed to capture frame.")
                return

            base_roi = {
                'left': bbox.get('left', 0),
                'top': bbox.get('top', 0),
                'width': bbox.get('width', frame.shape[1]),
                'height': bbox.get('height', frame.shape[0])
            }

            from ...core.detection.multi_monster_detector import MultiMonsterDetector
            test_detector = MultiMonsterDetector(self.config_manager, cs)
            test_detector.monster_style_map = {tuple(color_spec.rgb): style}

            monsters = test_detector.detect_monsters_with_styles(frame, base_roi)
            count = len(monsters)
            areas = [m.get('area', 0) for m in monsters]
            centers = [(m.get('center_x'), m.get('center_y')) for m in monsters[:5]]
            styles = [m.get('combat_style') for m in monsters]

            logger.info(
                "[MultiMonster Test] style=%s rgb=%s tol_rgb=%d monsters=%d areas=%s styles=%s centers(sample)=%s",
                style, color_spec.rgb, color_spec.tol_rgb, count, areas, styles, centers
            )
            QMessageBox.information(
                self,
                "Test Detection",
                (
                    f"Tested style: {style}\n"
                    f"Color RGB: {color_spec.rgb} tol_rgb={color_spec.tol_rgb}\n"
                    f"Detected Monsters: {count}\n"
                    f"Areas: {areas}\n"
                    f"Styles: {styles}\n"
                    f"Sample Centers: {centers}"
                )
            )
        except Exception as e:
            logger.error(f"Error testing monster detection (style): {e}")
    
    def on_apply_clicked(self, silent: bool = False):
        """Apply general settings changes.

        Args:
            silent: When True, do not show confirmation popups. Useful for profile auto-save.
        """
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
            if not silent:
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
    
    def on_monsters_apply_clicked(self, silent: bool = False):
        """Apply monster configuration changes

        Args:
            silent: When True, do not show confirmation popups.
        """
        try:
            # Compose configs from the three sub-tabs in fixed order
            # Gather alternates from config if present
            melee_alts = self.config_manager.get('multi_monster_melee_alternates', []) or []
            ranged_alts = self.config_manager.get('multi_monster_ranged_alternates', []) or []
            magic_alts = self.config_manager.get('multi_monster_magic_alternates', []) or []

            monster_configs = [
                {
                    'color': self.melee_monster_editor.get_color_spec().__dict__,
                    'style': 'melee',
                    'alternates': melee_alts
                },
                {
                    'color': self.ranged_monster_editor.get_color_spec().__dict__,
                    'style': 'ranged',
                    'alternates': ranged_alts
                },
                {
                    'color': self.magic_monster_editor.get_color_spec().__dict__,
                    'style': 'magic',
                    'alternates': magic_alts
                },
            ]
            
            self.config_manager.set('multi_monster_configs', monster_configs)
            if not silent:
                QMessageBox.information(self, "Settings Saved", "Monster configurations have been saved.")
        except Exception as e:
            logger.error(f"Error applying monster settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save monster settings: {e}")

    def on_add_alternate_color(self, style: str):
        """Pick an alternate color from the screen and append it to the given style's alternates list."""
        try:
            # Use the zoom color picker to sample a pixel color
            picker = ZoomColorPickerDialog(self.config_manager, self)
            if picker.exec_() == ZoomColorPickerDialog.Accepted:
                rgb = getattr(picker, 'selected_color', None)
                if rgb is None or len(rgb) != 3:
                    QMessageBox.warning(self, "Alternate Color", "No color selected.")
                    return
                # Build a default ColorSpec-ish dict with moderate tolerances
                alt = {
                    'rgb': [int(rgb[0]), int(rgb[1]), int(rgb[2])],
                    'tol_rgb': 20,
                    'use_hsv': True,
                    'tol_h': 8,
                    'tol_s': 50,
                    'tol_v': 50
                }
                key = f'multi_monster_{style}_alternates'
                alts = self.config_manager.get(key, []) or []
                alts.append(alt)
                self.config_manager.set(key, alts)
                self._update_alternate_counts()
                QMessageBox.information(self, "Alternate Color", f"Added alternate color for {style}: {alt['rgb']}")
        except Exception as e:
            logger.error(f"Error adding alternate color: {e}")
            QMessageBox.critical(self, "Alternate Color", f"Error: {e}")

    def on_clear_alternate_colors(self, style: str):
        """Clear alternates for the given style."""
        try:
            key = f'multi_monster_{style}_alternates'
            self.config_manager.set(key, [])
            self._update_alternate_counts()
            QMessageBox.information(self, "Alternate Color", f"Cleared alternates for {style}.")
        except Exception as e:
            logger.error(f"Error clearing alternate colors: {e}")
            QMessageBox.critical(self, "Alternate Color", f"Error: {e}")
    
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
            # Push into editors
            try:
                self.melee_monster_editor.set_color_spec(default_configs[0]['color'])
                self.ranged_monster_editor.set_color_spec(default_configs[1]['color'])
                self.magic_monster_editor.set_color_spec(default_configs[2]['color'])
            except Exception:
                pass
            
            QMessageBox.information(self, "Settings Reset", "Monster configurations have been reset to defaults.")
        except Exception as e:
            logger.error(f"Error resetting monster settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to reset monster settings: {e}")
    
    def on_weapons_apply_clicked(self, silent: bool = False):
        """Apply weapon configuration changes

        Args:
            silent: When True, do not show confirmation popups.
        """
        try:
            # Save weapon colors
            self.config_manager.set('multi_monster_melee_weapon_color', self.melee_weapon_color_editor.get_color_spec().__dict__)
            self.config_manager.set('multi_monster_ranged_weapon_color', self.ranged_weapon_color_editor.get_color_spec().__dict__)
            self.config_manager.set('multi_monster_magic_weapon_color', self.magic_weapon_color_editor.get_color_spec().__dict__)
            # Save template assist settings
            self.config_manager.set('weapon_template_enable', self.template_enable_cb.isChecked())
            self.config_manager.set('weapon_template_mode', self.template_mode_combo.currentText())
            self.config_manager.set('weapon_template_threshold', self.template_thr_spin.value())
            self.config_manager.set('weapon_template_window', self.template_win_spin.value())
            if not silent:
                QMessageBox.information(self, "Settings Saved", "Weapon configurations have been saved.")
        except Exception as e:
            logger.error(f"Error applying weapon settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save weapon settings: {e}")

    def on_tiles_apply_clicked(self, silent: bool = False):
        """Apply tile settings (single radius slider)."""
        try:
            radius = int(self.tile_radius_slider.value())
            self.config_manager.set('multi_monster_tile_radius', radius)
            if not silent:
                QMessageBox.information(self, "Settings Saved", f"Tile search radius set to {radius} px.")
        except Exception as e:
            logger.error(f"Error applying tile settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save tile settings: {e}")

    def on_tiles_reset_clicked(self):
        """Reset tile radius to a sensible default."""
        try:
            default_radius = 120
            self.tile_radius_slider.setValue(default_radius)
            self.config_manager.set('multi_monster_tile_radius', default_radius)
            QMessageBox.information(self, "Settings Reset", f"Tile search radius reset to {default_radius} px.")
        except Exception as e:
            logger.error(f"Error resetting tile settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to reset tile settings: {e}")

    def save_all_settings(self, silent: bool = False):
        """Convenience method to save all Multi Monster settings at once.

        Calls general, monsters, and weapons apply handlers.
        """
        try:
            self.on_apply_clicked(silent=silent)
            self.on_monsters_apply_clicked(silent=silent)
            self.on_weapons_apply_clicked(silent=silent)
            # Include Tile Settings so radius override is persisted before profile save
            self.on_tiles_apply_clicked(silent=silent)
        except Exception as e:
            logger.error(f"Error saving all Multi Monster settings: {e}")
    
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
            # Reset template UI to defaults
            self.template_enable_cb.setChecked(True)
            self.template_mode_combo.setCurrentText('edge')
            self.template_thr_spin.setValue(0.58)
            self.template_win_spin.setValue(200)
            
            QMessageBox.information(self, "Settings Reset", "Weapon configurations have been reset to defaults.")
        except Exception as e:
            logger.error(f"Error resetting weapon settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to reset weapon settings: {e}")

    def on_load_melee_template(self):
        """Load a melee template image from disk and set it in config."""
        try:
            from PyQt5.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(self, "Select Melee Template Image", "", "Images (*.png *.jpg *.jpeg)")
            if path:
                self.config_manager.set('weapon_melee_template_path', path)
                self.melee_template_label.setText(path)
                # Ensure sensible defaults as requested by user
                self.template_enable_cb.setChecked(True)
                self.template_mode_combo.setCurrentText('edge')
                self.template_thr_spin.setValue(max(0.58, self.template_thr_spin.value()))
                self.template_win_spin.setValue(max(200, self.template_win_spin.value()))
                QMessageBox.information(self, "Template Loaded", f"Melee template set to:\n{path}\nMode=edge, Threshold>=0.58, Window>=200 will be used.")
        except Exception as e:
            logger.error(f"Error loading melee template: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load template: {e}")

    def on_test_melee_template(self):
        """Run template match on the current ROI and show PASS/FAIL with score and settings."""
        try:
            if not self.template_enable_cb.isChecked():
                QMessageBox.information(self, "Template Test", "Template Assist is disabled. Enable it first.")
                return
            mode = self.template_mode_combo.currentText().lower()
            thr = float(self.template_thr_spin.value())
            win = int(self.template_win_spin.value())
            tpath = self.config_manager.get('weapon_melee_template_path')
            if not tpath:
                QMessageBox.warning(self, "Template Test", "No melee template path set. Load a template image first.")
                return
            import cv2
            import numpy as np
            tmpl = cv2.imread(str(tpath), cv2.IMREAD_UNCHANGED)
            if tmpl is None:
                QMessageBox.critical(self, "Template Test", f"Failed to read template at: {tpath}")
                return
            if tmpl.ndim == 2:
                needle = cv2.Canny(cv2.cvtColor(tmpl, cv2.COLOR_GRAY2BGR), 50, 150) if mode == 'edge' else tmpl
            else:
                bgr = tmpl[:, :, :3]
                if mode == 'edge':
                    needle = cv2.Canny(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), 50, 150)
                else:
                    needle = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

            hay_bgr = self._capture_weapon_frame()
            if hay_bgr is None:
                QMessageBox.warning(self, "Template Test", "Failed to capture Weapon ROI. Set the ROI first.")
                return
            # Optional search window around melee position
            if win > 0:
                try:
                    roi = self.config_manager.get_roi('weapon_roi')
                    pos = self.config_manager.get('multi_monster_melee_weapon_position')
                    if roi and pos and 'x' in pos and 'y' in pos:
                        x_local = int(pos['x'] - roi.left)
                        y_local = int(pos['y'] - roi.top)
                        h, w = hay_bgr.shape[:2]
                        half = max(8, win // 2)
                        x0 = max(0, x_local - half); y0 = max(0, y_local - half)
                        x1 = min(w, x_local + half); y1 = min(h, y_local + half)
                        if (x1 - x0) >= 8 and (y1 - y0) >= 8:
                            hay_bgr = hay_bgr[y0:y1, x0:x1]
                except Exception:
                    pass
            if mode == 'edge':
                hay = cv2.Canny(cv2.cvtColor(hay_bgr, cv2.COLOR_BGR2GRAY), 50, 150)
            else:
                hay = cv2.cvtColor(hay_bgr, cv2.COLOR_BGR2GRAY)
            if hay.shape[0] < needle.shape[0] or hay.shape[1] < needle.shape[1]:
                QMessageBox.warning(self, "Template Test", "Template is larger than the search area.")
                return
            res = cv2.matchTemplate(hay, needle, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            score = float(max_val)
            hH, hW = hay.shape[:2]
            nH, nW = needle.shape[:2]
            top_left = max_loc
            pass_fail = "PASS" if score >= thr else "FAIL"
            # Optional: save a preview with rectangle overlay
            try:
                bgr_copy = hay_bgr.copy()
                cv2.rectangle(bgr_copy, (top_left[0], top_left[1]), (top_left[0]+nW, top_left[1]+nH), (0,255,0) if score>=thr else (0,0,255), 1)
                out_dir = self.config_manager.get('debug_output_dir', 'outputs') or 'outputs'
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, 'melee_template_test.png')
                cv2.imwrite(out_path, bgr_copy)
                extra = f"\nPreview saved: {out_path}"
            except Exception:
                extra = ""
            QMessageBox.information(self, "Template Test", f"Mode={mode}  Threshold={thr}  Window={win}\nScore={score:.3f} -> {pass_fail}{extra}")
        except Exception as e:
            logger.error(f"Error testing melee template: {e}")
            QMessageBox.critical(self, "Template Test", f"Error: {e}")

    def on_load_magic_template(self):
        """Load a magic template image from disk and set it in config."""
        try:
            from PyQt5.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(self, "Select Magic Template Image", "", "Images (*.png *.jpg *.jpeg)")
            if path:
                self.config_manager.set('weapon_magic_template_path', path)
                self.magic_template_label.setText(path)
                # Ensure template assist is enabled; use current mode/threshold but keep sane minimums
                self.template_enable_cb.setChecked(True)
                # Leave user's chosen mode; don't force change here
                if float(self.template_thr_spin.value()) < 0.5:
                    self.template_thr_spin.setValue(0.5)
                if int(self.template_win_spin.value()) < 140:
                    self.template_win_spin.setValue(140)
                QMessageBox.information(self, "Template Loaded", f"Magic template set to:\n{path}\nYou can now run 'Test Magic Template'.")
        except Exception as e:
            logger.error(f"Error loading magic template: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load magic template: {e}")

    def on_test_magic_template(self):
        """Run template match for Magic on the current ROI and show PASS/FAIL with score and settings."""
        try:
            if not self.template_enable_cb.isChecked():
                QMessageBox.information(self, "Template Test", "Template Assist is disabled. Enable it first.")
                return
            mode = self.template_mode_combo.currentText().lower()
            thr = float(self.template_thr_spin.value())
            win = int(self.template_win_spin.value())
            tpath = self.config_manager.get('weapon_magic_template_path')
            if not tpath:
                QMessageBox.warning(self, "Template Test", "No magic template path set. Load a template image first.")
                return
            import cv2
            import numpy as np
            tmpl = cv2.imread(str(tpath), cv2.IMREAD_UNCHANGED)
            if tmpl is None:
                QMessageBox.critical(self, "Template Test", f"Failed to read template at: {tpath}")
                return
            if tmpl.ndim == 2:
                needle = cv2.Canny(cv2.cvtColor(tmpl, cv2.COLOR_GRAY2BGR), 50, 150) if mode == 'edge' else tmpl
            else:
                bgr = tmpl[:, :, :3]
                if mode == 'edge':
                    needle = cv2.Canny(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), 50, 150)
                else:
                    needle = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

            hay_bgr = self._capture_weapon_frame()
            if hay_bgr is None:
                QMessageBox.warning(self, "Template Test", "Failed to capture Weapon ROI. Set the ROI first.")
                return
            # Optional search window around magic position
            if win > 0:
                try:
                    roi = self.config_manager.get_roi('weapon_roi')
                    pos = self.config_manager.get('multi_monster_magic_weapon_position')
                    if roi and pos and 'x' in pos and 'y' in pos:
                        x_local = int(pos['x'] - roi.left)
                        y_local = int(pos['y'] - roi.top)
                        h, w = hay_bgr.shape[:2]
                        half = max(8, win // 2)
                        x0 = max(0, x_local - half); y0 = max(0, y_local - half)
                        x1 = min(w, x_local + half); y1 = min(h, y_local + half)
                        if (x1 - x0) >= 8 and (y1 - y0) >= 8:
                            hay_bgr = hay_bgr[y0:y1, x0:x1]
                except Exception:
                    pass
            if mode == 'edge':
                hay = cv2.Canny(cv2.cvtColor(hay_bgr, cv2.COLOR_BGR2GRAY), 50, 150)
            else:
                hay = cv2.cvtColor(hay_bgr, cv2.COLOR_BGR2GRAY)
            if hay.shape[0] < needle.shape[0] or hay.shape[1] < needle.shape[1]:
                QMessageBox.warning(self, "Template Test", "Template is larger than the search area.")
                return
            res = cv2.matchTemplate(hay, needle, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            score = float(max_val)
            nH, nW = needle.shape[:2]
            top_left = max_loc
            pass_fail = "PASS" if score >= thr else "FAIL"
            # Optional: save a preview with rectangle overlay
            try:
                bgr_copy = hay_bgr.copy()
                cv2.rectangle(bgr_copy, (top_left[0], top_left[1]), (top_left[0]+nW, top_left[1]+nH), (0,255,0) if score>=thr else (0,0,255), 1)
                out_dir = self.config_manager.get('debug_output_dir', 'outputs') or 'outputs'
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, 'magic_template_test.png')
                cv2.imwrite(out_path, bgr_copy)
                extra = f"\nPreview saved: {out_path}"
            except Exception:
                extra = ""
            QMessageBox.information(self, "Template Test", f"Mode={mode}  Threshold={thr}  Window={win}\nScore={score:.3f} -> {pass_fail}{extra}")
        except Exception as e:
            logger.error(f"Error testing magic template: {e}")
            QMessageBox.critical(self, "Template Test", f"Error: {e}")

    def on_test_click_style(self, style: str):
        """Compute a click point inside the Weapon ROI for the given style and report result.
        Logs 'weapon found = true/false'. If found, also simulates a click at that point.
        """
        try:
            # Ensure Weapon ROI exists
            roi = self.config_manager.get_roi('weapon_roi')
            if not roi:
                QMessageBox.warning(self, "Test Click", "Weapon ROI is not set. Pick it first.")
                return
            # Create a detector on the fly using current CaptureService
            from ...core.detection.capture import CaptureService
            from ...core.detection.multi_monster_detector import MultiMonsterDetector
            cs = CaptureService()
            detector = MultiMonsterDetector(self.config_manager, cs)
            pt = detector.get_click_point_for_style(style)
            if pt and 'x' in pt and 'y' in pt:
                msg = f"Style '{style}': click at ({pt['x']},{pt['y']})"
                logger.info(f"weapon found = true | {msg}")
                # Try to simulate the click. Prefer the bot's MouseController to keep behavior consistent.
                clicked = False
                try:
                    controller = getattr(self, 'bot_controller', None)
                    if controller and getattr(controller, 'action_manager', None):
                        mc = getattr(controller.action_manager, 'mouse_controller', None)
                        if mc:
                            # Use move_to + click to avoid search_roi clamping performed by move_and_click
                            moved = mc.move_to(int(pt['x']), int(pt['y']))
                            # Small human pause
                            try:
                                time.sleep(0.05)
                            except Exception:
                                pass
                            if moved:
                                clicked = mc.click(button='left', clicks=1)
                    if not clicked:
                        # Fallback: direct pyautogui
                        try:
                            import pyautogui
                            pyautogui.moveTo(int(pt['x']), int(pt['y']), duration=0.1)
                            pyautogui.click()
                            clicked = True
                        except Exception as e:
                            logger.error(f"Fallback pyautogui click failed: {e}")
                except Exception as e:
                    logger.error(f"Simulate click error: {e}")
                # Show result
                if clicked:
                    QMessageBox.information(self, "Test Click", msg + "\nSimulate click: OK")
                else:
                    QMessageBox.information(self, "Test Click", msg + "\nSimulate click: FAILED")
            else:
                logger.info("weapon found = false | style='%s'", style)
                QMessageBox.information(self, "Test Click", f"Style '{style}': no click point found in Weapon ROI.")
        except Exception as e:
            logger.error(f"Error testing click style '{style}': {e}")
            QMessageBox.critical(self, "Test Click", f"Error: {e}")