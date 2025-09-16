#!/usr/bin/env python3
"""
Style/Weapon ROI live tuner for RSPS Color Bot v3

This utility mirrors the app's config/capture/detection stack and gives
live diagnostics to tune Combat Style detection and Weapon ROI thresholds.

- Shows per-style pixel counts in Style Indicator ROI vs thresholds
- Shows selected style and weapon ROI pixel count for that style
- Indicates if a clickable point would be found for the current style
- Lets you adjust thresholds on the fly and saves them to the active profile
- Optional mask preview windows (OpenCV)

Run:
  python scripts/style_tuner.py --profile "v2 instance.json" --debug
"""
import sys
import os
import logging
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rspsbot.utils.logging import setup_logging
from rspsbot.core.config import ConfigManager, ColorSpec
from rspsbot.core.detection.capture import CaptureService
from rspsbot.core.detection.detector import DetectionEngine
from rspsbot.core.detection.color_detector import build_mask, build_mask_precise_small
from rspsbot.gui.components.enhanced_color_editor import EnhancedColorEditor

import cv2
import numpy as np

# PyQt
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QGridLayout, QSpinBox, QCheckBox, QPushButton, QComboBox, QMessageBox
)
from PyQt5.QtCore import QTimer, Qt

logger = logging.getLogger("rspsbot.tools.style_tuner")


def parse_args():
    p = argparse.ArgumentParser(description="RSPS v3 Style/Weapon Tuner")
    p.add_argument('--debug', action='store_true')
    p.add_argument('--profile', type=str, help='Profile filename in profiles/ to load')
    p.add_argument('--interval', type=float, default=0.25, help='Update interval seconds')
    p.add_argument('--show-masks', action='store_true', help='Show OpenCV mask windows')
    return p.parse_args()


class StyleTunerWindow(QWidget):
    def __init__(self, cfg: ConfigManager, det: DetectionEngine, cap: CaptureService, interval_s: float, show_masks: bool):
        super().__init__()
        self.cfg = cfg
        self.det = det
        self.cap = cap
        self.interval_s = max(0.05, float(interval_s))
        self.show_masks = bool(show_masks)

        self.setWindowTitle("RSPS v3 - Style/Weapon ROI Tuner")
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(int(self.interval_s * 1000))

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- Profile row ---
        prof_row = QHBoxLayout()
        prof_row.addWidget(QLabel("Profile:"))
        self.combo_profile = QComboBox()
        try:
            profiles_dir = PROJECT_ROOT / 'profiles'
            files = [p.name for p in profiles_dir.glob('*.json')]
            files.sort()
            self.combo_profile.addItems(files)
            # Try to set current profile if known
            curr = getattr(self.cfg, 'current_profile', None)
            if curr and curr in files:
                self.combo_profile.setCurrentText(curr)
        except Exception:
            pass
        prof_row.addWidget(self.combo_profile)

        def _load_selected_profile():
            name = self.combo_profile.currentText()
            if not name:
                return
            try:
                self.cfg.load_profile(name)
                logger.info(f"Loaded profile: {name}")
                self._refresh_from_config()
                QMessageBox.information(self, "Profile loaded", f"Loaded: {name}")
            except Exception as e:
                logger.error(f"Failed to load profile {name}: {e}", exc_info=True)
                QMessageBox.warning(self, "Load failed", str(e))

        btn_load = QPushButton("Load")
        btn_load.clicked.connect(_load_selected_profile)
        prof_row.addWidget(btn_load)
        prof_row.addStretch()
        layout.addLayout(prof_row)

        # Tabs container
        from PyQt5.QtWidgets import QTabWidget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Diagnostics tab (existing controls)
        diag_tab = QWidget()
        diag_layout = QVBoxLayout(diag_tab)
        self.tabs.addTab(diag_tab, "Diagnostics")

        # --- Style counts group ---
        style_group = QGroupBox("Style Indicator ROI - Counts & Thresholds")
        sgrid = QGridLayout(style_group)

        self.lbl_roi = QLabel("Style ROI: -")
        sgrid.addWidget(self.lbl_roi, 0, 0, 1, 3)

        # Global threshold
        sgrid.addWidget(QLabel("Global min pixels:"), 1, 0)
        self.spin_style_global = QSpinBox()
        self.spin_style_global.setRange(0, 10000)
        self.spin_style_global.setValue(int(self.cfg.get('combat_style_min_pixels', 40)))
        self.spin_style_global.valueChanged.connect(lambda v: self.cfg.set('combat_style_min_pixels', int(v)))
        sgrid.addWidget(self.spin_style_global, 1, 1)

        # Per-style thresholds
        rows = {
            'melee': 2,
            'ranged': 3,
            'magic': 4,
        }
        self.count_labels: Dict[str, QLabel] = {}
        self.thr_spins: Dict[str, QSpinBox] = {}
        for key, row in rows.items():
            sgrid.addWidget(QLabel(key.capitalize()), row, 0)
            lbl = QLabel("count: -")
            self.count_labels[key] = lbl
            sgrid.addWidget(lbl, row, 1)

            sp = QSpinBox()
            sp.setRange(0, 10000)
            sp.setToolTip("0 = use Global fallback")
            sp.setValue(int(self.cfg.get(f'combat_style_min_pixels_{key}', 0) or 0))
            sp.valueChanged.connect(lambda v, k=key: self.cfg.set(f'combat_style_min_pixels_{k}', int(v)))
            self.thr_spins[key] = sp
            sgrid.addWidget(sp, row, 2)

        # Precise mode
        self.chk_precise = QCheckBox("Use Precise Mode (Lab ΔE)")
        self.chk_precise.setChecked(bool(self.cfg.get('combat_precise_mode', True)))
        self.chk_precise.toggled.connect(lambda v: self.cfg.set('combat_precise_mode', bool(v)))
        sgrid.addWidget(self.chk_precise, 5, 0, 1, 3)

        # Selected style
        self.lbl_selected = QLabel("Selected style: -")
        sgrid.addWidget(self.lbl_selected, 6, 0, 1, 3)

        diag_layout.addWidget(style_group)

        # --- Style ROI selector ---
        try:
            from rspsbot.gui.components.advanced_roi_selector import AdvancedROISelector  # lazy import for PyQt UI
            self.style_roi_selector = AdvancedROISelector(self.cfg, title="Style ROI")
            # Initialize with current ROI
            sroi = self.cfg.get_roi('combat_style_roi')
            if sroi:
                self.style_roi_selector.set_roi(sroi)

            def _on_style_roi_changed(roi):
                try:
                    self.cfg.set_roi('combat_style_roi', roi)
                    self._update_roi_labels()
                except Exception:
                    logger.exception("Failed to set style ROI")

            self.style_roi_selector.roiChanged.connect(_on_style_roi_changed)
            diag_layout.addWidget(self.style_roi_selector)
        except Exception as e:
            logger.warning(f"AdvancedROISelector unavailable: {e}")
            diag_layout.addWidget(QLabel("Style ROI selector unavailable (see logs)."))

        # --- Weapon group ---
        weap_group = QGroupBox("Weapon ROI - Counts & Point")
        wgrid = QGridLayout(weap_group)

        self.lbl_wroi = QLabel("Weapon ROI: -")
        wgrid.addWidget(self.lbl_wroi, 0, 0, 1, 3)

        wgrid.addWidget(QLabel("Global weapon min pixels:"), 1, 0)
        self.spin_weapon_global = QSpinBox()
        self.spin_weapon_global.setRange(0, 10000)
        self.spin_weapon_global.setValue(int(self.cfg.get('combat_weapon_min_pixels', 30)))
        self.spin_weapon_global.valueChanged.connect(lambda v: self.cfg.set('combat_weapon_min_pixels', int(v)))
        wgrid.addWidget(self.spin_weapon_global, 1, 1)

        wrows = {'melee': 2, 'ranged': 3, 'magic': 4}
        self.wcount_labels: Dict[str, QLabel] = {}
        self.wthr_spins: Dict[str, QSpinBox] = {}
        for key, row in wrows.items():
            wgrid.addWidget(QLabel(key.capitalize()), row, 0)
            lbl = QLabel("count: -")
            self.wcount_labels[key] = lbl
            wgrid.addWidget(lbl, row, 1)

            sp = QSpinBox()
            sp.setRange(0, 10000)
            sp.setToolTip("0 = use Global fallback")
            sp.setValue(int(self.cfg.get(f'combat_weapon_min_pixels_{key}', 0) or 0))
            sp.valueChanged.connect(lambda v, k=key: self.cfg.set(f'combat_weapon_min_pixels_{k}', int(v)))
            self.wthr_spins[key] = sp
            wgrid.addWidget(sp, row, 2)

        self.lbl_wpoint = QLabel("Current style weapon point: -")
        wgrid.addWidget(self.lbl_wpoint, 5, 0, 1, 3)

        # Mask preview toggle
        self.chk_masks = QCheckBox("Show mask previews (OpenCV windows)")
        self.chk_masks.setChecked(self.show_masks)
        self.chk_masks.toggled.connect(self._toggle_masks)
        wgrid.addWidget(self.chk_masks, 6, 0, 1, 3)

        diag_layout.addWidget(weap_group)

        # --- Weapon ROI selector ---
        try:
            from rspsbot.gui.components.advanced_roi_selector import AdvancedROISelector  # reuse
            self.weapon_roi_selector = AdvancedROISelector(self.cfg, title="Weapon ROI")
            wroi = self.cfg.get_roi('combat_weapon_roi')
            if wroi:
                self.weapon_roi_selector.set_roi(wroi)

            def _on_weapon_roi_changed(roi):
                try:
                    self.cfg.set_roi('combat_weapon_roi', roi)
                    self._update_roi_labels()
                except Exception:
                    logger.exception("Failed to set weapon ROI")

            self.weapon_roi_selector.roiChanged.connect(_on_weapon_roi_changed)
            diag_layout.addWidget(self.weapon_roi_selector)
        except Exception as e:
            logger.warning(f"AdvancedROISelector unavailable for weapon: {e}")
            diag_layout.addWidget(QLabel("Weapon ROI selector unavailable (see logs)."))

        # Colors tab
        colors_tab = QWidget()
        colors_layout = QVBoxLayout(colors_tab)
        self.tabs.addTab(colors_tab, "Colors")

        # Style Colors group
        style_colors_group = QGroupBox("Style Colors")
        sc_layout = QVBoxLayout(style_colors_group)
        self.color_editors = {}

        def add_color_editor(key: str, title: str):
            try:
                editor = EnhancedColorEditor(self.cfg, key, title=title)
                # When a color changes, kick an immediate refresh tick
                try:
                    editor.colorChanged.connect(lambda *_: self._tick())
                except Exception:
                    pass
                sc_layout.addWidget(editor)
                self.color_editors[key] = editor
            except Exception as e:
                logger.warning(f"Failed to create color editor for {key}: {e}")

        add_color_editor('combat_style_melee_color', 'Melee')
        add_color_editor('combat_style_ranged_color', 'Ranged')
        add_color_editor('combat_style_magic_color', 'Magic')
        colors_layout.addWidget(style_colors_group)

        # Weapon Colors group
        weapon_colors_group = QGroupBox("Weapon Colors")
        wc_layout = QVBoxLayout(weapon_colors_group)

        def add_weapon_editor(key: str, title: str):
            try:
                editor = EnhancedColorEditor(self.cfg, key, title=title)
                try:
                    editor.colorChanged.connect(lambda *_: self._tick())
                except Exception:
                    pass
                wc_layout.addWidget(editor)
                self.color_editors[key] = editor
            except Exception as e:
                logger.warning(f"Failed to create color editor for {key}: {e}")

        add_weapon_editor('combat_weapon_melee_color', 'Melee weapon')
        add_weapon_editor('combat_weapon_ranged_color', 'Ranged weapon')
        add_weapon_editor('combat_weapon_magic_color', 'Magic weapon')
        colors_layout.addWidget(weapon_colors_group)

        # Control row
        ctrl_row = QHBoxLayout()
        self.btn_refresh_now = QPushButton("Refresh Now")
        self.btn_refresh_now.clicked.connect(self._tick)
        ctrl_row.addWidget(self.btn_refresh_now)

        self.btn_save = QPushButton("Save Profile")

        def _do_save() -> None:
            prof = getattr(self.cfg, 'current_profile', None)
            if prof:
                self.cfg.save_profile(prof)
                logger.info(f"Profile saved: {prof}")
            else:
                # Default to v2 instance.json if none loaded
                self.cfg.save_profile('v2 instance.json')
                logger.info("Profile saved: v2 instance.json (default)")

        self.btn_save.clicked.connect(_do_save)
        ctrl_row.addWidget(self.btn_save)

        self.btn_quit = QPushButton("Quit")

        # Wrap to ensure a None-returning slot for type checkers
        def _do_close() -> None:
            QWidget.close(self)

        self.btn_quit.clicked.connect(_do_close)
        ctrl_row.addWidget(self.btn_quit)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        # Initialize ROI labels
        self._update_roi_labels()
        # Ensure UI reflects current config
        self._refresh_from_config()

        # Helper label
        help_lbl = QLabel(
            "Tips: Set Style ROI to the indicator icon area and Weapon ROI over your inventory/gear.\n"
            "Adjust min pixels until a style is selected and a weapon point appears, then Save Profile."
        )
        help_lbl.setWordWrap(True)
        layout.addWidget(help_lbl)

    def _toggle_masks(self, checked: bool):
        self.show_masks = bool(checked)
        if not checked:
            try:
                cv2.destroyWindow('style_mask')
                cv2.destroyWindow('weapon_mask')
            except Exception:
                pass

    def _update_roi_labels(self):
        sroi = self.cfg.get_roi('combat_style_roi')
        if sroi:
            try:
                self.lbl_roi.setText(f"Style ROI: {sroi.left},{sroi.top} {sroi.width}x{sroi.height}")
            except Exception:
                d = sroi.to_dict() if hasattr(sroi, 'to_dict') else (dict(sroi) if isinstance(sroi, dict) else {})
                self.lbl_roi.setText(f"Style ROI: {d.get('left',0)},{d.get('top',0)} {d.get('width',0)}x{d.get('height',0)}")
        else:
            self.lbl_roi.setText("Style ROI: (not set)")

        wroi = self.cfg.get_roi('combat_weapon_roi')
        if wroi:
            try:
                self.lbl_wroi.setText(f"Weapon ROI: {wroi.left},{wroi.top} {wroi.width}x{wroi.height}")
            except Exception:
                d = wroi.to_dict() if hasattr(wroi, 'to_dict') else (dict(wroi) if isinstance(wroi, dict) else {})
                self.lbl_wroi.setText(f"Weapon ROI: {d.get('left',0)},{d.get('top',0)} {d.get('width',0)}x{d.get('height',0)}")
        else:
            self.lbl_wroi.setText("Weapon ROI: (not set)")

    def _build_mask(self, frame, spec: ColorSpec, precise: bool):
        cm_cfg = {
            'combat_lab_tolerance': self.cfg.get('combat_lab_tolerance', 18),
            'combat_sat_min': self.cfg.get('combat_sat_min', 40),
            'combat_val_min': self.cfg.get('combat_val_min', 40),
            'combat_morph_open_iters': self.cfg.get('combat_morph_open_iters', 1),
            'combat_morph_close_iters': self.cfg.get('combat_morph_close_iters', 1),
        }
        if precise:
            mask, _ = build_mask_precise_small(frame, spec, cm_cfg, step=1, min_area=0)
        else:
            # When precise is off, don't force RGB∩HSV; allow the configured color space path
            mask, _ = build_mask(frame, spec, step=1, precise=False, min_area=0)
        return mask

    def _refresh_from_config(self):
        """Sync UI controls from current config values."""
        try:
            # Style thresholds
            self.spin_style_global.blockSignals(True)
            self.spin_style_global.setValue(int(self.cfg.get('combat_style_min_pixels', 40)))
            self.spin_style_global.blockSignals(False)
            for key, sp in self.thr_spins.items():
                sp.blockSignals(True)
                sp.setValue(int(self.cfg.get(f'combat_style_min_pixels_{key}', 0) or 0))
                sp.blockSignals(False)
            # Weapon thresholds
            self.spin_weapon_global.blockSignals(True)
            self.spin_weapon_global.setValue(int(self.cfg.get('combat_weapon_min_pixels', 30)))
            self.spin_weapon_global.blockSignals(False)
            for key, sp in self.wthr_spins.items():
                sp.blockSignals(True)
                sp.setValue(int(self.cfg.get(f'combat_weapon_min_pixels_{key}', 0) or 0))
                sp.blockSignals(False)
            # Precise mode
            self.chk_precise.blockSignals(True)
            self.chk_precise.setChecked(bool(self.cfg.get('combat_precise_mode', True)))
            self.chk_precise.blockSignals(False)
            # ROIs loaded into selectors
            if hasattr(self, 'style_roi_selector'):
                sroi = self.cfg.get_roi('combat_style_roi')
                if sroi:
                    self.style_roi_selector.set_roi(sroi)
            if hasattr(self, 'weapon_roi_selector'):
                wroi = self.cfg.get_roi('combat_weapon_roi')
                if wroi:
                    self.weapon_roi_selector.set_roi(wroi)
            # Labels update
            self._update_roi_labels()
            # Refresh color editors to reflect current config/profile
            if hasattr(self, 'color_editors') and isinstance(self.color_editors, dict):
                try:
                    for key, editor in self.color_editors.items():
                        try:
                            # Pull latest spec and update editor
                            spec = self.cfg.get_color_spec(getattr(editor, 'color_key', key))
                            if spec is not None:
                                editor.color_spec = spec
                                editor.update_ui_from_color_spec()
                        except Exception:
                            logger.debug("Failed to refresh color editor %s", key, exc_info=True)
                except Exception:
                    logger.debug("Color editors refresh skipped", exc_info=True)
        except Exception:
            logger.exception("Failed to refresh UI from config")

    def _tick(self):
        try:
            self._update_roi_labels()
            precise = bool(self.cfg.get('combat_precise_mode', True))

            # STYLE ROI analysis
            sroi = self.cfg.get_roi('combat_style_roi')
            counts: Dict[str, int] = {'melee': 0, 'ranged': 0, 'magic': 0}
            selected: Optional[str] = None
            if sroi is not None:
                frame = self.cap.capture_region(sroi)
                if frame is not None:
                    specs: Dict[str, Optional[ColorSpec]] = {
                        'melee': self.cfg.get_color_spec('combat_style_melee_color'),
                        'ranged': self.cfg.get_color_spec('combat_style_ranged_color'),
                        'magic': self.cfg.get_color_spec('combat_style_magic_color'),
                    }
                    for key, spec in specs.items():
                        if not spec:
                            counts[key] = 0
                            continue
                        try:
                            mask = self._build_mask(frame, spec, precise)
                            counts[key] = int(cv2.countNonZero(mask))
                            if self.show_masks and key == 'melee':
                                cv2.imshow('style_mask', mask)
                        except Exception:
                            counts[key] = 0
                    # Choose selected style like detector: must exceed per-style (or global) threshold
                    gmin = int(self.cfg.get('combat_style_min_pixels', 40))
                    thr = {
                        'melee': int(self.cfg.get('combat_style_min_pixels_melee', 0) or 0) or gmin,
                        'ranged': int(self.cfg.get('combat_style_min_pixels_ranged', 0) or 0) or gmin,
                        'magic': int(self.cfg.get('combat_style_min_pixels_magic', 0) or 0) or gmin,
                    }
                    eligible = [k for k in counts.keys() if counts[k] >= thr[k]]
                    if eligible:
                        if len(eligible) == 1:
                            selected = eligible[0]
                        else:
                            selected = max(eligible, key=lambda k: counts[k])
                else:
                    # No frame available
                    pass
            else:
                # Provide guidance when ROI missing
                self.lbl_selected.setText("Selected style: - (set Style ROI)")
            # Update labels
            for k, lbl in self.count_labels.items():
                lbl.setText(f"count: {counts[k]}")
            self.lbl_selected.setText(f"Selected style: {selected if selected else '-'}")

            # WEAPON ROI analysis for each style + current selected
            wroi = self.cfg.get_roi('combat_weapon_roi')
            wcounts: Dict[str, int] = {'melee': 0, 'ranged': 0, 'magic': 0}
            point_txt = "-"
            if wroi is not None:
                wframe = self.cap.capture_region(wroi)
                if wframe is not None:
                    for key in ['melee', 'ranged', 'magic']:
                        # prefer weapon color, fallback to style color
                        spec = (
                            self.cfg.get_color_spec(f'combat_weapon_{key}_color')
                            or self.cfg.get_color_spec(f'combat_style_{key}_color')
                        )
                        if not spec:
                            wcounts[key] = 0
                            continue
                        try:
                            wmask = self._build_mask(wframe, spec, precise)
                            wcounts[key] = int(cv2.countNonZero(wmask))
                            if self.show_masks and key == 'melee':
                                cv2.imshow('weapon_mask', wmask)
                        except Exception:
                            wcounts[key] = 0
                    # Also compute the clickable point using engine for the selected style
                    if selected:
                        try:
                            pt = self.det.detect_weapon_for_style(selected)
                            if pt is not None:
                                point_txt = f"{pt[0]},{pt[1]}"
                        except Exception:
                            # Allow tuner to continue even if detector path fails
                            logger.debug("detect_weapon_for_style failed in tuner", exc_info=True)
                else:
                    pass
            else:
                self.lbl_wpoint.setText("Current style weapon point: - (set Weapon ROI)")
            for k, lbl in self.wcount_labels.items():
                lbl.setText(f"count: {wcounts[k]}")
            self.lbl_wpoint.setText(f"Current style weapon point: {point_txt}")

            if self.show_masks:
                cv2.waitKey(1)
        except Exception as e:
            logger.error(f"Tick error: {e}")


def main():
    args = parse_args()
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(log_level)
    logger.info("Starting Style/Weapon ROI Tuner")

    cfg = ConfigManager()
    if args.profile:
        prof_path = os.path.join('profiles', args.profile)
        if os.path.exists(prof_path):
            logger.info(f"Loading profile: {args.profile}")
            cfg.load_profile(args.profile)
        else:
            logger.warning(f"Profile not found: {args.profile}")

    cap = CaptureService()
    det = DetectionEngine(cfg, cap)

    app = QApplication(sys.argv)
    w = StyleTunerWindow(cfg, det, cap, args.interval, args.show_masks)
    w.resize(520, 360)
    w.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
