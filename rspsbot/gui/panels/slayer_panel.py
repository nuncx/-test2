"""
Slayer Mode Panel: configuration UI for SlayerModule
- 8 monster color slots
- Hotkey for Slayer panel (default ctrl+s)
- Coordinate pickers for: task1, task2, monster entry, teleport
- Apply: writes colors into a dedicated slayer_monster_colors list used by module
"""
from __future__ import annotations
import logging
from typing import List
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QGridLayout, QLineEdit
)
from PyQt5.QtCore import Qt

from ...core.config import ConfigManager, ColorSpec, Coordinate
from ..components.enhanced_color_editor import EnhancedColorEditor
from ..components.screen_picker import ZoomPointPickerDialog

logger = logging.getLogger('rspsbot.gui.panels.slayer')


class SlayerPanel(QWidget):
    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self._init_ui()

    def _init_ui(self):
        main = QVBoxLayout(self)

        # Hotkey group
        hk_group = QGroupBox("Slayer Panel Hotkey (open/close)")
        hk_layout = QHBoxLayout(hk_group)
        hk_layout.addWidget(QLabel("Hotkey:"))
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setPlaceholderText("ctrl+s")
        self.hotkey_edit.setText(str(self.config.get('slayer_panel_hotkey', 'ctrl+s')))
        hk_layout.addWidget(self.hotkey_edit)
        main.addWidget(hk_group)

        # Coordinates group
        coord_group = QGroupBox("Slayer UI Coordinates (window-relative)")
        cg = QGridLayout(coord_group)
        rows = [
            ("Task 1", 'slayer_task1_xy'),
            ("Task 2", 'slayer_task2_xy'),
            ("Monster Entry", 'slayer_monster_button_xy'),
            ("Teleport", 'slayer_teleport_xy'),
        ]
        self.coord_labels = {}
        for i, (label, key) in enumerate(rows):
            cg.addWidget(QLabel(label+":"), i, 0)
            val = self.config.get_coordinate(key)
            txt = f"{val.x},{val.y}" if val else "(unset)"
            lb = QLabel(txt)
            self.coord_labels[key] = lb
            btn_pick = QPushButton("Pick")
            btn_test = QPushButton("Test Click")
            btn_pick.clicked.connect(lambda _=None, k=key, l=lb: self._pick_coord(k, l))
            btn_test.clicked.connect(lambda _=None, k=key: self._test_click(k))
            cg.addWidget(lb, i, 1)
            cg.addWidget(btn_pick, i, 2)
            cg.addWidget(btn_test, i, 3)
        main.addWidget(coord_group)

        # Colors group
        colors_group = QGroupBox("Slayer Monster Colors (up to 8)")
        gl = QGridLayout(colors_group)
        self.color_editors: List[EnhancedColorEditor] = []
        for idx in range(8):
            key = f'slayer_monster_color_{idx+1}'
            editor = EnhancedColorEditor(self.config, key, title=f"Monster {idx+1}")
            self.color_editors.append(editor)
            gl.addWidget(editor, idx//2, idx%2)
        main.addWidget(colors_group)

        # Apply/Reset
        actions = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.reset_btn = QPushButton("Reset")
        self.apply_btn.clicked.connect(self.on_apply)
        self.reset_btn.clicked.connect(self.on_reset)
        actions.addWidget(self.apply_btn)
        actions.addWidget(self.reset_btn)
        main.addLayout(actions)

        main.addStretch(1)

    def _pick_coord(self, key: str, label_widget: QLabel):
        dlg = ZoomPointPickerDialog(self.config, self)
        if dlg.exec_() == dlg.Accepted or dlg.selected_point_relative is not None:
            if dlg.selected_point_relative is not None:
                x, y = dlg.selected_point_relative
            else:
                return
            # Save as window-relative
            try:
                from ...core.detection.capture import CaptureService
                bbox = CaptureService().get_window_bbox()
                rx = max(0, x - int(bbox.get('left', 0)))
                ry = max(0, y - int(bbox.get('top', 0)))
                coord = Coordinate(rx, ry, name=key)
            except Exception:
                coord = Coordinate(x, y, name=key)
            self.config.set_coordinate(key, coord)
            label_widget.setText(f"{coord.x},{coord.y}")

    def _test_click(self, key: str):
        try:
            from ...core.action.mouse_controller import MouseController
            from ...core.action import ActionManager
            am = ActionManager(self.config)
            c = self.config.get_coordinate(key)
            if not c or am.mouse_controller is None:
                return
            from ...core.detection.capture import CaptureService
            bbox = CaptureService().get_window_bbox()
            ax = int(bbox.get('left', 0)) + int(c.x)
            ay = int(bbox.get('top', 0)) + int(c.y)
            am.mouse_controller.move_and_click(ax, ay, enforce_guard=False, clamp_to_search_roi=False)
        except Exception as e:
            logger.error(f"SlayerPanel test click failed: {e}")

    def on_apply(self):
        # Persist hotkey
        self.config.set('slayer_panel_hotkey', self.hotkey_edit.text().strip() or 'ctrl+s')
        # Build slayer colors list into dedicated key the module can consume
        colors = []
        for ed in self.color_editors:
            try:
                cs = ed.get_color_spec()
                colors.append(cs.__dict__ if hasattr(cs, '__dict__') else {'rgb': cs.rgb, 'tol_rgb': cs.tol_rgb})
            except Exception:
                pass
        self.config.set('slayer_monster_colors', colors)
        logger.info(f"SlayerPanel: applied {len(colors)} colors and hotkey")

    def on_reset(self):
        # Clear slayer-specific settings
        self.config.set('slayer_panel_hotkey', 'ctrl+s')
        self.config.set('slayer_monster_colors', [])
        # Coordinates: set to a sentinel empty that get_coordinate will treat as None
        for key in ('slayer_task1_xy','slayer_task2_xy','slayer_monster_button_xy','slayer_teleport_xy'):
            try:
                self.config._config[key] = None  # type: ignore[attr-defined]
            except Exception:
                pass
        for ed in self.color_editors:
            ed.set_color_spec({'rgb': (255, 0, 0), 'tol_rgb': 8, 'use_hsv': True, 'tol_h': 4, 'tol_s': 30, 'tol_v': 30})
        logger.info("SlayerPanel: reset done")
