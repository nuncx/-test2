#!/usr/bin/env python3
"""
Weapon Tuning GUI

Simple PyQt5 app to live-tune weapon detection thresholds and colors,
pick ROI/colors on screen, and manage Template Assist images for dark icons.
"""
from __future__ import annotations

import os
import sys
from typing import Dict, Optional, Tuple

import numpy as np
import cv2
from PyQt5 import QtWidgets, QtCore, QtGui

# Ensure project root on sys.path so `rspsbot` imports resolve when running directly
_THIS_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from rspsbot.core.config import ConfigManager, ColorSpec, ROI
from rspsbot.core.detection.capture import CaptureService
from rspsbot.core.detection.multi_monster_detector import MultiMonsterDetector
from rspsbot.core.detection.color_detector import build_mask_precise_small
from rspsbot.gui.components.screen_picker import (
    ZoomRoiPickerDialog,
    ZoomColorPickerDialog,
)


# --- Small helpers ---------------------------------------------------------
class ColorSwatch(QtWidgets.QLabel):
    """Tiny colored rectangle to show the current RGB value."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, size: Tuple[int, int] = (40, 20)):
        super().__init__(parent)
        self.setFixedSize(*size)
        self.setFrameShape(QtWidgets.QFrame.Box)
        self._rgb: Optional[Tuple[int, int, int]] = None
        self.setAlignment(QtCore.Qt.AlignCenter)
        self._apply()

    def set_rgb(self, rgb: Optional[Tuple[int, int, int]]):
        self._rgb = rgb
        self._apply()

    def _apply(self):
        if self._rgb is None:
            self.setText("-")
            self.setStyleSheet("background: #333; color: #ccc;")
        else:
            r, g, b = self._rgb
            self.setText(f"{r},{g},{b}")
            self.setStyleSheet(f"background: rgb({r},{g},{b}); color: #000;")


def _counts_for_specs(frame: np.ndarray, specs: Dict[str, ColorSpec], lab_tol: int, sat_min: int, val_min: int,
                      open_iters: int, close_iters: int) -> Dict[str, int]:
    cfg = {
        'combat_lab_tolerance': lab_tol,
        'combat_sat_min': sat_min,
        'combat_val_min': val_min,
        'combat_morph_open_iters': open_iters,
        'combat_morph_close_iters': close_iters,
    }
    counts: Dict[str, int] = {}
    for k, spec in specs.items():
        try:
            mask, _ = build_mask_precise_small(frame, spec, cfg, step=1, min_area=0)
            counts[k] = int(cv2.countNonZero(mask))
        except Exception:
            counts[k] = 0
    return counts


def decide_switch(required: Optional[str], current: Optional[str], visible: Dict[str, int]) -> str:
    if required and current == required:
        return 'attack (already_on_required)'
    if required and required in visible:
        return 'switch_weapon (required_visible)'
    if (not required or required not in visible) and visible and (current is None):
        return 'switch_weapon (current_unknown_switch_any_visible)'
    return 'attack (fallback)'


class WeaponTuningWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Weapon Tuning GUI (live)")
        self.resize(980, 700)
        self.cm = ConfigManager()
        self.cs = CaptureService()
        self.det = MultiMonsterDetector(self.cm, self.cs)

        # Timer
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.sample_once)

        # Central layout
        container = QtWidgets.QWidget(self)
        self.setCentralWidget(container)
        layout = QtWidgets.QVBoxLayout(container)

        # Focus controls
        focus_box = QtWidgets.QGroupBox("Window focus")
        fl = QtWidgets.QHBoxLayout(focus_box)
        self.title_edit = QtWidgets.QLineEdit(self.cm.get('window_title', ''))
        self.focus_btn = QtWidgets.QPushButton("Focus")
        self.focus_btn.clicked.connect(self.on_focus)
        fl.addWidget(QtWidgets.QLabel("Title contains:"))
        fl.addWidget(self.title_edit)
        fl.addWidget(self.focus_btn)
        layout.addWidget(focus_box)

        # ROI controls
        roi_box = QtWidgets.QGroupBox("Weapon ROI")
        rl = QtWidgets.QHBoxLayout(roi_box)
        self.roi_label = QtWidgets.QLabel("<not set>")
        self.pick_roi_btn = QtWidgets.QPushButton("Pick ROI")
        self.pick_roi_btn.clicked.connect(self.on_pick_roi)
        rl.addWidget(self.roi_label)
        rl.addStretch()
        rl.addWidget(self.pick_roi_btn)
        layout.addWidget(roi_box)

        # Color controls
        colors_box = QtWidgets.QGroupBox("Weapon Colors")
        cl = QtWidgets.QGridLayout(colors_box)
        self.swatches: Dict[str, ColorSwatch] = {}
        row = 0
        for style in ("melee", "ranged", "magic"):
            cl.addWidget(QtWidgets.QLabel(style.capitalize()), row, 0)
            sw = ColorSwatch()
            self.swatches[style] = sw
            cl.addWidget(sw, row, 1)
            btn_pick = QtWidgets.QPushButton("Pick")
            btn_pick.clicked.connect(lambda _, s=style: self.on_pick_color(s))
            cl.addWidget(btn_pick, row, 2)
            r_edit = QtWidgets.QSpinBox(); r_edit.setRange(0,255)
            g_edit = QtWidgets.QSpinBox(); g_edit.setRange(0,255)
            b_edit = QtWidgets.QSpinBox(); b_edit.setRange(0,255)
            set_btn = QtWidgets.QPushButton("Set RGB")
            def make_set_fn(sty, re, ge, be):
                return lambda: self.set_color(sty, (re.value(), ge.value(), be.value()))
            set_btn.clicked.connect(make_set_fn(style, r_edit, g_edit, b_edit))
            cl.addWidget(QtWidgets.QLabel("R"), row, 3); cl.addWidget(r_edit, row, 4)
            cl.addWidget(QtWidgets.QLabel("G"), row, 5); cl.addWidget(g_edit, row, 6)
            cl.addWidget(QtWidgets.QLabel("B"), row, 7); cl.addWidget(b_edit, row, 8)
            cl.addWidget(set_btn, row, 9)
            row += 1
        layout.addWidget(colors_box)

        # Thresholds
        thr_box = QtWidgets.QGroupBox("Thresholds")
        tl = QtWidgets.QGridLayout(thr_box)
        self.lab_spin = QtWidgets.QSpinBox(); self.lab_spin.setRange(4, 40); self.lab_spin.setValue(int(self.cm.get('weapon_lab_tolerance', 10)))
        self.sat_spin = QtWidgets.QSpinBox(); self.sat_spin.setRange(0, 100); self.sat_spin.setValue(int(self.cm.get('weapon_sat_min', 20)))
        self.val_spin = QtWidgets.QSpinBox(); self.val_spin.setRange(0, 100); self.val_spin.setValue(int(self.cm.get('weapon_val_min', 30)))
        self.min_spin = QtWidgets.QSpinBox(); self.min_spin.setRange(0, 500); self.min_spin.setValue(int(self.cm.get('weapon_min_pixels', 20)))
        self.floor_spin = QtWidgets.QSpinBox(); self.floor_spin.setRange(0, 100); self.floor_spin.setValue(int(self.cm.get('weapon_adaptive_min_pixels', 5)))
        self.ratio_spin = QtWidgets.QDoubleSpinBox(); self.ratio_spin.setRange(0.0, 1.0); self.ratio_spin.setSingleStep(0.05); self.ratio_spin.setDecimals(2); self.ratio_spin.setValue(float(self.cm.get('weapon_soft_floor_ratio', 0.4)))
        self.interval_spin = QtWidgets.QDoubleSpinBox(); self.interval_spin.setRange(0.05, 2.0); self.interval_spin.setSingleStep(0.05); self.interval_spin.setValue(0.5)
        self.req_combo = QtWidgets.QComboBox(); self.req_combo.addItems(["none","melee","ranged","magic"]) 
        tl.addWidget(QtWidgets.QLabel("Lab tolerance"), 0, 0); tl.addWidget(self.lab_spin, 0, 1)
        tl.addWidget(QtWidgets.QLabel("Sat min"), 0, 2); tl.addWidget(self.sat_spin, 0, 3)
        tl.addWidget(QtWidgets.QLabel("Val min"), 0, 4); tl.addWidget(self.val_spin, 0, 5)
        tl.addWidget(QtWidgets.QLabel("Min pixels"), 1, 0); tl.addWidget(self.min_spin, 1, 1)
        tl.addWidget(QtWidgets.QLabel("Soft ratio"), 1, 2); tl.addWidget(self.ratio_spin, 1, 3)
        tl.addWidget(QtWidgets.QLabel("Adaptive floor"), 1, 4); tl.addWidget(self.floor_spin, 1, 5)
        tl.addWidget(QtWidgets.QLabel("Interval (s)"), 2, 0); tl.addWidget(self.interval_spin, 2, 1)
        tl.addWidget(QtWidgets.QLabel("Required"), 2, 2); tl.addWidget(self.req_combo, 2, 3)
        layout.addWidget(thr_box)

        # Template Assist controls
        templ_box = QtWidgets.QGroupBox("Template Assist (for dark icons e.g. melee)")
        gl = QtWidgets.QGridLayout(templ_box)
        self.templ_enable = QtWidgets.QCheckBox("Enable template assist")
        self.templ_enable.setChecked(bool(self.cm.get('weapon_template_enable', True)))
        self.templ_mode = QtWidgets.QComboBox(); self.templ_mode.addItems(["edge","gray"]) 
        self.templ_mode.setCurrentText(str(self.cm.get('weapon_template_mode', 'edge')))
        self.templ_thr = QtWidgets.QDoubleSpinBox(); self.templ_thr.setRange(0.0, 1.0); self.templ_thr.setSingleStep(0.01); self.templ_thr.setDecimals(2); self.templ_thr.setValue(float(self.cm.get('weapon_template_threshold', 0.58)))
        self.templ_win = QtWidgets.QSpinBox(); self.templ_win.setRange(0, 512); self.templ_win.setValue(int(self.cm.get('weapon_template_window', 64)))
        gl.addWidget(self.templ_enable, 0, 0, 1, 2)
        gl.addWidget(QtWidgets.QLabel("Mode"), 1, 0); gl.addWidget(self.templ_mode, 1, 1)
        gl.addWidget(QtWidgets.QLabel("Threshold"), 1, 2); gl.addWidget(self.templ_thr, 1, 3)
        gl.addWidget(QtWidgets.QLabel("Search window (px)"), 1, 4); gl.addWidget(self.templ_win, 1, 5)
        self.melee_templ_label = QtWidgets.QLabel("<melee template: not set>")
        btn_load_melee = QtWidgets.QPushButton("Load Melee Template…")
        btn_clear_melee = QtWidgets.QPushButton("Clear")
        btn_save_roi = QtWidgets.QPushButton("Save current ROI as image…")
        btn_test_melee = QtWidgets.QPushButton("Test Melee Template")
        btn_apply_melee = QtWidgets.QPushButton("Apply Melee Template (auto)")
        btn_load_melee.clicked.connect(lambda: self.on_load_template('melee'))
        btn_clear_melee.clicked.connect(lambda: self.on_clear_template('melee'))
        btn_save_roi.clicked.connect(self.on_save_roi_image)
        btn_test_melee.clicked.connect(self.on_test_melee_template)
        btn_apply_melee.clicked.connect(self.on_apply_melee_template)
        gl.addWidget(self.melee_templ_label, 2, 0, 1, 4)
        gl.addWidget(btn_load_melee, 2, 4)
        gl.addWidget(btn_clear_melee, 2, 5)
        gl.addWidget(btn_save_roi, 3, 0, 1, 2)
        gl.addWidget(btn_test_melee, 3, 2, 1, 2)
        gl.addWidget(btn_apply_melee, 3, 4, 1, 2)
        layout.addWidget(templ_box)

        # Controls
        ctl_box = QtWidgets.QGroupBox("Controls")
        clayout = QtWidgets.QHBoxLayout(ctl_box)
        self.once_btn = QtWidgets.QPushButton("Once")
        self.start_btn = QtWidgets.QPushButton("Start")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.once_btn.clicked.connect(self.sample_once)
        self.start_btn.clicked.connect(self.on_start)
        self.stop_btn.clicked.connect(self.on_stop)
        clayout.addWidget(self.once_btn)
        clayout.addWidget(self.start_btn)
        clayout.addWidget(self.stop_btn)
        layout.addWidget(ctl_box)

        # Preview & Output
        preview_box = QtWidgets.QGroupBox("Preview & Output")
        playout = QtWidgets.QHBoxLayout(preview_box)
        self.preview_label = QtWidgets.QLabel()
        self.preview_label.setFixedSize(280, 180)
        self.preview_label.setFrameShape(QtWidgets.QFrame.Box)
        self.output = QtWidgets.QPlainTextEdit(); self.output.setReadOnly(True)
        playout.addWidget(self.preview_label)
        playout.addWidget(self.output, 1)
        layout.addWidget(preview_box, 1)

        # Wire threshold changes to cm
        self.lab_spin.valueChanged.connect(lambda v: self.cm.set('weapon_lab_tolerance', int(v)))
        self.sat_spin.valueChanged.connect(lambda v: self.cm.set('weapon_sat_min', int(v)))
        self.val_spin.valueChanged.connect(lambda v: self.cm.set('weapon_val_min', int(v)))
        self.min_spin.valueChanged.connect(lambda v: self.cm.set('weapon_min_pixels', int(v)))
        self.ratio_spin.valueChanged.connect(lambda v: self.cm.set('weapon_soft_floor_ratio', float(v)))
        self.floor_spin.valueChanged.connect(lambda v: self.cm.set('weapon_adaptive_min_pixels', int(v)))

        # Wire template controls
        self.templ_enable.toggled.connect(lambda on: self.cm.set('weapon_template_enable', bool(on)))
        self.templ_mode.currentTextChanged.connect(lambda t: self.cm.set('weapon_template_mode', str(t)))
        self.templ_thr.valueChanged.connect(lambda v: self.cm.set('weapon_template_threshold', float(v)))
        self.templ_win.valueChanged.connect(lambda v: self.cm.set('weapon_template_window', int(v)))

        # Final refresh
        self.refresh_roi_label()
        self.refresh_swatches()
        self.refresh_template_labels()

    # --- UI helpers ---
    def log(self, text: str):
        self.output.appendPlainText(text)
        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())

    def refresh_roi_label(self):
        roi = self.cm.get_roi('weapon_roi')
        if roi:
            self.roi_label.setText(f"({roi.left},{roi.top},{roi.width},{roi.height})")
        else:
            self.roi_label.setText("<not set>")

    def refresh_swatches(self):
        for style in ("melee","ranged","magic"):
            cspec = self.cm.get_color_spec(f"multi_monster_{style}_weapon_color")
            if style in self.swatches:
                self.swatches[style].set_rgb(cspec.rgb if cspec else None)

    def refresh_template_labels(self):
        p = self.cm.get('weapon_melee_template_path', None)
        self.melee_templ_label.setText(f"melee template: {p if p else '<not set>'}")

    # --- Actions ---
    def on_focus(self):
        title = self.title_edit.text().strip()
        if title:
            self.cm.set('window_title', title)
        try:
            self.cs.focus_window(title or self.cm.get('window_title', ''), retries=6, sleep_s=0.25, exact=False)
            self.log(f"Focused window containing '{title}'")
        except Exception as e:
            self.log(f"Focus failed: {e}")

    def on_pick_roi(self):
        try:
            dlg = ZoomRoiPickerDialog(config_manager=self.cm)
            if dlg.exec_() == 1 and dlg.result_rect is not None:
                bbox = self.cs.get_window_bbox()
                left = bbox.get('left', 0) + dlg.result_rect.left()
                top = bbox.get('top', 0) + dlg.result_rect.top()
                roi = ROI(left=left, top=top, width=dlg.result_rect.width(), height=dlg.result_rect.height(), mode='absolute')
                self.cm.set_roi('weapon_roi', roi)
                self.refresh_roi_label()
                self.log(f"Set weapon_roi=({roi.left},{roi.top},{roi.width},{roi.height})")
            else:
                self.log("ROI selection canceled")
        except Exception as e:
            self.log(f"ROI picker failed: {e}")

    def set_color(self, style: str, rgb: Tuple[int,int,int]):
        spec = ColorSpec(rgb=rgb, tol_rgb=24, use_hsv=True, tol_h=10, tol_s=60, tol_v=60)
        self.cm.set_color_spec(f"multi_monster_{style}_weapon_color", spec)
        self.refresh_swatches()
        self.log(f"Set color[{style}]={rgb}")

    def on_pick_color(self, style: str):
        try:
            dlg = ZoomColorPickerDialog(config_manager=self.cm)
            if dlg.exec_() == 1 and dlg.selected_color is not None:
                self.set_color(style, dlg.selected_color)
            else:
                self.log("Color selection canceled")
        except Exception as e:
            self.log(f"Color picker failed: {e}")

    def on_load_template(self, style: str):
        try:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, f"Load {style} template", _PROJECT_ROOT, "Images (*.png *.jpg *.jpeg *.bmp)")
            if not path:
                return
            self.cm.set(f"weapon_{style}_template_path", path)
            self.refresh_template_labels()
            self.log(f"Loaded {style} template: {path}")
        except Exception as e:
            self.log(f"Load template failed: {e}")

    def on_clear_template(self, style: str):
        try:
            self.cm.set(f"weapon_{style}_template_path", None)
            self.refresh_template_labels()
            self.log(f"Cleared {style} template")
        except Exception as e:
            self.log(f"Clear template failed: {e}")

    def on_save_roi_image(self):
        try:
            roi = self.cm.get_roi('weapon_roi')
            if not roi:
                self.log("weapon_roi not set. Pick ROI first.")
                return
            frame = self.cs.capture_region(roi)
            if frame is None or frame.size == 0:
                self.log("Failed to capture weapon ROI")
                return
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save ROI image", os.path.join(_PROJECT_ROOT, "profiles", "examples", "weapon_roi.png"), "PNG (*.png);;JPEG (*.jpg *.jpeg)")
            if not path:
                return
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            ok = cv2.imwrite(path, frame)
            if ok:
                self.log(f"Saved ROI image to {path}")
            else:
                self.log("Failed to write image")
        except Exception as e:
            self.log(f"Save ROI failed: {e}")

    def on_apply_melee_template(self):
        try:
            # Capture current ROI and save to outputs
            roi = self.cm.get_roi('weapon_roi')
            if not roi:
                self.log("weapon_roi not set. Pick ROI first.")
                return
            frame = self.cs.capture_region(roi)
            if frame is None or frame.size == 0:
                self.log("Failed to capture weapon ROI")
                return
            out_dir = os.path.join(_PROJECT_ROOT, 'outputs')
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, 'weapon_roi.png')
            if not cv2.imwrite(out_path, frame):
                self.log("Failed to write outputs/weapon_roi.png")
                return
            # Apply template settings
            self.cm.set('weapon_template_enable', True)
            self.cm.set('weapon_template_mode', 'edge')
            self.cm.set('weapon_template_threshold', 0.58)
            self.cm.set('weapon_template_window', 200)
            self.cm.set('weapon_melee_template_path', out_path)
            self.refresh_template_labels()
            self.templ_enable.setChecked(True)
            self.templ_mode.setCurrentText('edge')
            self.templ_thr.setValue(0.58)
            self.templ_win.setValue(200)
            self.log(f"Applied melee template -> {out_path} (mode=edge thr=0.58 win=200)")
        except Exception as e:
            self.log(f"Apply melee template failed: {e}")

    def on_test_melee_template(self):
        try:
            roi = self.cm.get_roi('weapon_roi')
            if not roi:
                self.log("weapon_roi not set. Pick ROI first.")
                return
            frame = self.cs.capture_region(roi)
            if frame is None or frame.size == 0:
                self.log("Failed to capture weapon ROI")
                return

            tpath = self.cm.get('weapon_melee_template_path', None)
            if not tpath or not os.path.exists(tpath):
                self.log("Melee template path not set or file missing.")
                return

            templ = cv2.imread(tpath, cv2.IMREAD_COLOR)
            if templ is None or templ.size == 0:
                self.log("Failed to read template image.")
                return

            mode = str(self.cm.get('weapon_template_mode', 'edge'))
            thr = float(self.cm.get('weapon_template_threshold', 0.58))
            win = int(self.cm.get('weapon_template_window', 64))

            # Build search image and template according to mode
            def to_edge(img):
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 50, 150)
                return edges

            def to_gray(img):
                return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            if mode == 'edge':
                src = to_edge(frame)
                tpl = to_edge(templ)
            else:
                src = to_gray(frame)
                tpl = to_gray(templ)

            th, tw = tpl.shape[:2]
            h, w = src.shape[:2]
            if th > h or tw > w:
                self.log("Template larger than ROI; crop or pick a smaller template.")
                return

            # Optional search window: center window
            search = src
            if win and win > 0 and (win < w or win < h):
                cx, cy = w // 2, h // 2
                x0 = max(0, cx - win // 2)
                y0 = max(0, cy - win // 2)
                x1 = min(w, x0 + win)
                y1 = min(h, y0 + win)
                search = src[y0:y1, x0:x1]
                offset = (x0, y0)
            else:
                offset = (0, 0)

            res = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            top_left = (max_loc[0] + offset[0], max_loc[1] + offset[1])
            bottom_right = (top_left[0] + tw, top_left[1] + th)

            # Draw rectangle on preview image copy
            vis = frame.copy()
            cv2.rectangle(vis, top_left, bottom_right, (0, 255, 255), 1)

            # Update preview with overlay
            rgb = cv2.cvtColor(vis, cv2.COLOR_BGR2RGB)
            h2, w2, _ = rgb.shape
            qimg = QtGui.QImage(rgb.data, w2, h2, 3*w2, QtGui.QImage.Format_RGB888)
            pm = QtGui.QPixmap.fromImage(qimg.copy())
            self.preview_label.setPixmap(pm.scaled(self.preview_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

            self.log(f"Template test: mode={mode} score={max_val:.3f} thr={thr} win={win} at {top_left} -> {'PASS' if max_val>=thr else 'FAIL'}")
        except Exception as e:
            self.log(f"Template test failed: {e}")

    def on_start(self):
        interval_s = float(self.interval_spin.value())
        self._timer.start(int(max(0.05, interval_s) * 1000))
        self.log("Started live sampling")

    def on_stop(self):
        self._timer.stop()
        self.log("Stopped live sampling")

    def sample_once(self):
        roi = self.cm.get_roi('weapon_roi')
        if not roi:
            self.log("weapon_roi not set. Pick ROI first.")
            return
        frame = self.cs.capture_region(roi)
        if frame is None or frame.size == 0:
            self.log("Failed to capture weapon ROI")
            return

        # Update preview
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, _ = rgb.shape
            qimg = QtGui.QImage(rgb.data, w, h, 3*w, QtGui.QImage.Format_RGB888)
            pm = QtGui.QPixmap.fromImage(qimg.copy())
            self.preview_label.setPixmap(pm.scaled(self.preview_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        except Exception:
            pass

        specs = {
            'melee': self.cm.get_color_spec('multi_monster_melee_weapon_color'),
            'ranged': self.cm.get_color_spec('multi_monster_ranged_weapon_color'),
            'magic': self.cm.get_color_spec('multi_monster_magic_weapon_color'),
        }
        specs = {k: v for k, v in specs.items() if v is not None}
        if not specs:
            self.log("No weapon colors set. Pick at least one.")
            return

        lab_tol = max(int(self.cm.get('weapon_lab_tolerance', 10)), 12)
        sat_min = int(self.cm.get('weapon_sat_min', 20))
        val_min = int(self.cm.get('weapon_val_min', 30))
        open_iters = int(self.cm.get('multi_monster_morph_open_iters', 1))
        close_iters = int(self.cm.get('multi_monster_morph_close_iters', 2))
        min_pixels = int(self.cm.get('weapon_min_pixels', 20))
        adaptive_ratio = float(self.cm.get('weapon_soft_floor_ratio', 0.4))
        adaptive_floor = int(self.cm.get('weapon_adaptive_min_pixels', 5))

        normal_counts = _counts_for_specs(frame, specs, lab_tol, sat_min, val_min, open_iters, close_iters)
        relaxed_counts: Dict[str,int] = {}
        if sum(normal_counts.values()) == 0:
            relaxed_counts = _counts_for_specs(frame, specs, max(lab_tol, 18), 0, 0, open_iters, close_iters)

        current = self.det.detect_weapon(frame)
        visible = self.det.visible_weapon_styles(frame)
        req = self.req_combo.currentText(); required = None if req == 'none' else req
        decision = decide_switch(required, current, visible)

        # Print concise lines
        self.output.clear()
        self.log(f"Normal counts (lab={lab_tol}, S>={sat_min}, V>={val_min}): {normal_counts}")
        if relaxed_counts:
            self.log(f"Relaxed counts (lab>={max(lab_tol,18)}, S>=0, V>=0): {relaxed_counts}")
        self.log(f"Current: {current} | Visible: {visible}")
        self.log(f"Min={min_pixels} | Ratio={adaptive_ratio:.2f} | Floor={adaptive_floor}")
        self.log(f"Decision ({'none' if required is None else required}): {decision}")


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    win = WeaponTuningWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
