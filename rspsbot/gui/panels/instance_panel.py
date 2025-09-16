import logging

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QLineEdit,
    QMessageBox, QFrame, QTabWidget, QTextEdit, QDialog, QGridLayout, QComboBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPalette, QImage, QPixmap

from ...core.config import Coordinate, ROI, ColorSpec
from ...core.state import EventType
from ..components.time_selector import TimeSelector
from ..components.tooltip_helper import TooltipHelper
from ..components.advanced_roi_selector import AdvancedROISelector
from ..components.enhanced_color_editor import EnhancedColorEditor
from .teleport_panel import CoordinateSelector
from ..components.overlay import AggroOverlay

# Get module logger
logger = logging.getLogger('rspsbot.gui.panels.instance_panel')

# New InstanceModePanel for reorganized Instance Mode main tab
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
        layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # HP Bar Detection Tab
        self.hp_tab = QWidget()
        self.init_hp_tab()
        self.tab_widget.addTab(self.hp_tab, "HP Bar Detection")

        # Aggro Potion Tab
        self.aggro_tab = QWidget()
        self.init_aggro_tab()
        self.tab_widget.addTab(self.aggro_tab, "Aggro Potion")

        # Aggro Bar Tab
        self.aggro_bar_tab = QWidget()
        self.init_aggro_bar_tab()
        self.tab_widget.addTab(self.aggro_bar_tab, "Aggro Bar")

        # Instance Teleport Tab
        self.teleport_tab = QWidget()
        self.init_teleport_tab()
        self.tab_widget.addTab(self.teleport_tab, "Instance Teleport")

        # Logs Tab (Instances done + event log)
        self.logs_tab = QWidget()
        self.init_logs_tab()
        self.tab_widget.addTab(self.logs_tab, "Logs")

        # Live refresh timer for countdowns
        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self.refresh_live_labels)
        self._live_timer.start(1000)

    # Footer actions
        footer = QHBoxLayout()
        footer.addStretch()
        self.save_button = QPushButton("Save Instance Mode Settings")
        self.save_button.clicked.connect(self.on_save_instance_mode_clicked)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)

        # Load existing settings into controls
        self.load_settings()

        # Subscribe to instance events
        try:
            if hasattr(self.bot_controller, 'event_system') and self.bot_controller.event_system is not None:
                self.bot_controller.event_system.subscribe(EventType.INSTANCE_ENTERED, self._on_instance_entered_event)
        except Exception:
            pass

    def init_hp_tab(self):
        layout = QVBoxLayout(self.hp_tab)
        label = QLabel("Configure HP Bar detection for instance mode.")
        label.setWordWrap(True)
        layout.addWidget(label)
        # HP Bar ROI
        self.hp_roi_selector = AdvancedROISelector(self.config_manager, title="HP Bar Region")
        # Auto-save ROI when changed so detector can use it immediately
        self.hp_roi_selector.roiChanged.connect(lambda roi: self.config_manager.set_roi('instance_hp_bar_roi', roi))
        layout.addWidget(self.hp_roi_selector)
        # HP Bar Color
        self.hp_color_editor = EnhancedColorEditor(self.config_manager, 'instance_hp_bar_color', title="HP Bar Color")
        # Auto-save color changes (EnhancedColorEditor already writes via set_color_spec in update_color_spec)
        layout.addWidget(self.hp_color_editor)
        # HP Bar Timeout
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("HP Bar Timeout:"))
        self.hp_timeout_selector = TimeSelector(label="", initial_seconds=self.config_manager.get('instance_hp_timeout', 30.0), mode=TimeSelector.MODE_SEC_ONLY, tooltip="Time to wait after HP bar disappears before considering instance empty")
        timeout_layout.addWidget(self.hp_timeout_selector)
        timeout_layout.addStretch()
        layout.addLayout(timeout_layout)
        # Minimum pixel count
        min_pixels_layout = QHBoxLayout()
        min_pixels_layout.addWidget(QLabel("Min. Pixel Count:"))
        self.hp_min_pixels_spin = QSpinBox()
        self.hp_min_pixels_spin.setRange(1, 1000)
        self.hp_min_pixels_spin.setValue(self.config_manager.get('instance_hp_min_pixels', 50))
        min_pixels_layout.addWidget(self.hp_min_pixels_spin)
        min_pixels_layout.addStretch()
        layout.addLayout(min_pixels_layout)

    def init_aggro_tab(self):
        layout = QVBoxLayout(self.aggro_tab)
        label = QLabel("Aggro strategy and potion: choose how the bot decides when to click aggro, and where to click it.")
        label.setWordWrap(True)
        layout.addWidget(label)

        # Strategy selector
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

        # Aggro bar cooldown (does not affect Legacy Timer)
        cd_row = QHBoxLayout()
        cd_label = QLabel("Aggro Bar Cooldown (seconds; does not affect Legacy Timer):")
        cd_label.setToolTip("Applies only when using Detect Aggro Bar or Hybrid (bar-missing) — Legacy Timer clicks ignore this cooldown.")
        cd_row.addWidget(cd_label)
        self.aggro_click_cooldown_spin = QDoubleSpinBox()
        self.aggro_click_cooldown_spin.setDecimals(1)
        self.aggro_click_cooldown_spin.setRange(0.0, 60.0)
        try:
            self.aggro_click_cooldown_spin.setSuffix(" s")
        except Exception:
            pass
        try:
            self.aggro_click_cooldown_spin.setValue(float(self.config_manager.get('instance_aggro_click_cooldown', 7.0)))
        except Exception:
            self.aggro_click_cooldown_spin.setValue(7.0)
        cd_row.addWidget(self.aggro_click_cooldown_spin)
        cd_row.addStretch()
        layout.addLayout(cd_row)

        # Legacy timer settings group
        self.legacy_group = QGroupBox("Legacy Timer Settings")
        lg = QVBoxLayout(self.legacy_group)
        # Interval minutes
        int_row = QHBoxLayout()
        int_row.addWidget(QLabel("Aggro Interval (minutes):"))
        self.aggro_interval_spin = QDoubleSpinBox()
        self.aggro_interval_spin.setDecimals(1)
        self.aggro_interval_spin.setRange(0.5, 180.0)
        try:
            self.aggro_interval_spin.setValue(float(self.config_manager.get('instance_aggro_interval_min', 15.0)))
        except Exception:
            self.aggro_interval_spin.setValue(15.0)
        int_row.addWidget(self.aggro_interval_spin)
        int_row.addStretch()
        lg.addLayout(int_row)
        # Start delay seconds
        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("Aggro Start Delay (seconds):"))
        self.aggro_start_delay_spin = QDoubleSpinBox()
        self.aggro_start_delay_spin.setDecimals(1)
        self.aggro_start_delay_spin.setRange(0.0, 600.0)
        try:
            self.aggro_start_delay_spin.setValue(float(self.config_manager.get('instance_aggro_start_delay_s', 5.0)))
        except Exception:
            self.aggro_start_delay_spin.setValue(5.0)
        delay_row.addWidget(self.aggro_start_delay_spin)
        delay_row.addStretch()
        lg.addLayout(delay_row)
        # Jitter percent
        jit_row = QHBoxLayout()
        self.aggro_jitter_checkbox = QCheckBox("Enable Jitter (+/- %)")
        try:
            self.aggro_jitter_checkbox.setChecked(bool(self.config_manager.get('instance_aggro_jitter_enabled', True)))
        except Exception:
            self.aggro_jitter_checkbox.setChecked(True)
        jit_row.addWidget(self.aggro_jitter_checkbox)
        jit_row.addWidget(QLabel("Jitter Percent:"))
        self.aggro_jitter_spin = QDoubleSpinBox()
        self.aggro_jitter_spin.setDecimals(0)
        self.aggro_jitter_spin.setRange(0.0, 50.0)
        try:
            self.aggro_jitter_spin.setValue(float(self.config_manager.get('instance_aggro_jitter_percent', 10.0)))
        except Exception:
            self.aggro_jitter_spin.setValue(10.0)
        jit_row.addWidget(self.aggro_jitter_spin)
        jit_row.addStretch()
        lg.addLayout(jit_row)
        layout.addWidget(self.legacy_group)

        # Post-aggro HP wait (seconds)
        post_aggro_row = QHBoxLayout()
        post_aggro_row.addWidget(QLabel("Post-Aggro HP Wait (seconds):"))
        self.instance_post_aggro_wait_spin = QDoubleSpinBox()
        self.instance_post_aggro_wait_spin.setDecimals(1)
        self.instance_post_aggro_wait_spin.setRange(0.0, 120.0)
        try:
            post_aggro_wait_val = float(self.config_manager.get('instance_post_aggro_hp_wait', 8.0))
        except Exception:
            post_aggro_wait_val = 8.0
        self.instance_post_aggro_wait_spin.setValue(post_aggro_wait_val)
        post_aggro_row.addWidget(self.instance_post_aggro_wait_spin)
        post_aggro_row.addStretch()
        layout.addLayout(post_aggro_row)

        # Actions row for legacy timer
        actions_row = QHBoxLayout()
        self.reset_timer_btn = QPushButton("Reset Aggro Timer Now")
        self.reset_timer_btn.setToolTip("Re-initialize the legacy timer schedule starting from now (respects start delay)")
        self.reset_timer_btn.clicked.connect(self._reset_aggro_timer_clicked)
        actions_row.addWidget(self.reset_timer_btn)
        actions_row.addSpacing(12)
        self.next_aggro_label = QLabel("Next aggro: --:--:-- (phase: -)")
        self.next_aggro_label.setStyleSheet("color: #6aa; font-weight: bold;")
        actions_row.addWidget(self.next_aggro_label)
        actions_row.addStretch()
        layout.addLayout(actions_row)

        note = QLabel("Tip: Configure the Aggro Bar detection in the Aggro Bar tab. The Legacy Timer uses Start Delay then Interval for its cadence.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #888;")
        layout.addWidget(note)

        # Initialize visibility of legacy group based on strategy
        self._update_legacy_group_visibility()

    def init_aggro_bar_tab(self):
        layout = QVBoxLayout(self.aggro_bar_tab)
        label = QLabel("Aggro Bar detection: set the ROI and three colors that indicate aggro is active. The bot keeps checking this; if absent, it clicks the aggro potion.")
        label.setWordWrap(True)
        layout.addWidget(label)

        # Aggro Bar ROI selector
        self.aggro_bar_roi_selector = AdvancedROISelector(self.config_manager, title="Aggro Bar Region")
        self.aggro_bar_roi_selector.roiChanged.connect(self._on_aggro_bar_roi_changed)
        layout.addWidget(self.aggro_bar_roi_selector)

        # Colors dialog button + overlay toggle
        btn_row = QHBoxLayout()
        self.open_aggro_bar_colors_btn = QPushButton("Configure Aggro Bar Colors…")
        self.open_aggro_bar_colors_btn.clicked.connect(self._open_aggro_bar_colors_dialog)
        btn_row.addWidget(self.open_aggro_bar_colors_btn)
        self.aggro_overlay_checkbox = QCheckBox("Show Aggro Overlay")
        self.aggro_overlay_checkbox.setToolTip("Draw the Aggro Bar ROI and computed click point on screen")
        self.aggro_overlay_checkbox.stateChanged.connect(self._on_overlay_toggled)
        btn_row.addWidget(self.aggro_overlay_checkbox)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Min pixels per color
        thr_row = QHBoxLayout()
        thr_row.addWidget(QLabel("Min pixels per color:"))
        self.aggro_bar_min_pixels_spin = QSpinBox()
        self.aggro_bar_min_pixels_spin.setRange(1, 2000)
        try:
            self.aggro_bar_min_pixels_spin.setValue(int(self.config_manager.get('instance_aggro_bar_min_pixels_per_color', 30)))
        except Exception:
            self.aggro_bar_min_pixels_spin.setValue(30)
        thr_row.addWidget(self.aggro_bar_min_pixels_spin)
        thr_row.addStretch()
        layout.addLayout(thr_row)

        # Preview + Test
        action_row = QHBoxLayout()
        self.refresh_aggro_bar_preview_btn = QPushButton("Refresh Preview")
        self.refresh_aggro_bar_preview_btn.clicked.connect(self._refresh_aggro_bar_preview)
        action_row.addWidget(self.refresh_aggro_bar_preview_btn)
        self.test_aggro_bar_btn = QPushButton("Test Detection")
        self.test_aggro_bar_btn.clicked.connect(self._test_aggro_bar_detection)
        action_row.addWidget(self.test_aggro_bar_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        preview_group = QGroupBox("Aggro Bar Preview (ROI)")
        grid = QGridLayout(preview_group)
        self._bar_mask_label_c1 = QLabel("Color 1 mask")
        self._bar_mask_label_c2 = QLabel("Color 2 mask")
        self._bar_mask_label_c3 = QLabel("Color 3 mask")
        self._bar_mask_label_combo = QLabel("Combined mask")
        for lbl in (self._bar_mask_label_c1, self._bar_mask_label_c2, self._bar_mask_label_c3, self._bar_mask_label_combo):
            lbl.setMinimumSize(160, 90)
            lbl.setStyleSheet("border: 1px solid #333; background: #111;")
            try:
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore[attr-defined]
            except Exception:
                try:
                    lbl.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined, arg-type]
                except Exception:
                    pass
        grid.addWidget(QLabel("Color 1"), 0, 0)
        grid.addWidget(self._bar_mask_label_c1, 1, 0)
        grid.addWidget(QLabel("Color 2"), 0, 1)
        grid.addWidget(self._bar_mask_label_c2, 1, 1)
        grid.addWidget(QLabel("Color 3"), 0, 2)
        grid.addWidget(self._bar_mask_label_c3, 1, 2)
        grid.addWidget(QLabel("Combined"), 0, 3)
        grid.addWidget(self._bar_mask_label_combo, 1, 3)
        layout.addWidget(preview_group)

        self.aggro_bar_debug_text = QTextEdit()
        self.aggro_bar_debug_text.setReadOnly(True)
        self.aggro_bar_debug_text.setMaximumHeight(90)
        self.aggro_bar_debug_text.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        layout.addWidget(self.aggro_bar_debug_text)

        # Note: overlay instance created lazily when toggled on

    def _update_legacy_group_visibility(self):
        """Show legacy timer controls when strategy is Timer or Hybrid."""
        try:
            idx = int(self.aggro_strategy_combo.currentIndex())
        except Exception:
            idx = 0
        # 0=bar, 1=timer, 2=hybrid
        visible = idx in (1, 2)
        try:
            if hasattr(self, 'legacy_group') and self.legacy_group is not None:
                self.legacy_group.setVisible(visible)
        except Exception:
            pass

    def _on_strategy_changed(self, idx: int):
        # Update visibility immediately
        self._update_legacy_group_visibility()
        # Optionally persist right away so other components can react without pressing Save
        try:
            strat = 'bar' if idx == 0 else ('timer' if idx == 1 else 'hybrid')
            self.config_manager.set('instance_aggro_strategy', strat)
        except Exception:
            pass

    def init_teleport_tab(self):
        layout = QVBoxLayout(self.teleport_tab)
        label = QLabel("Configure instance token and teleport locations.")
        label.setWordWrap(True)
        layout.addWidget(label)
        # Instance token
        token_layout = QVBoxLayout()
        token_layout.addWidget(QLabel("Instance Token Location:"))
        self.token_selector = CoordinateSelector(config_manager=self.config_manager, bot_controller=self.bot_controller)
        token_layout.addWidget(self.token_selector)
        layout.addLayout(token_layout)
        # Instance teleport
        teleport_option_layout = QVBoxLayout()
        teleport_option_layout.addWidget(QLabel("Instance Teleport Location:"))
        self.teleport_selector = CoordinateSelector(config_manager=self.config_manager, bot_controller=self.bot_controller)
        teleport_option_layout.addWidget(self.teleport_selector)
        layout.addLayout(teleport_option_layout)
        # Delay between clicks
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Click Delay:"))
        self.delay_selector = TimeSelector(label="", initial_seconds=self.config_manager.get('instance_token_delay', 2.0), mode=TimeSelector.MODE_SEC_ONLY, tooltip="Time to wait between clicking the instance token and the teleport option")
        delay_layout.addWidget(self.delay_selector)
        delay_layout.addStretch()
        layout.addLayout(delay_layout)

        # Post-teleport wait for HP bar to appear
        wait_layout = QHBoxLayout()
        wait_layout.addWidget(QLabel("Wait for HP after Teleport:"))
        self.hp_reappear_wait_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('instance_post_teleport_hp_wait', 8.0),
            mode=TimeSelector.MODE_SEC_ONLY,
            tooltip="Time to wait after teleport for the HP bar to become visible (combat). If not seen, the bot will retry instance entry."
        )
        wait_layout.addWidget(self.hp_reappear_wait_selector)
        wait_layout.addStretch()
        layout.addLayout(wait_layout)

        # Max Teleport Retries
        retries_layout = QHBoxLayout()
        retries_layout.addWidget(QLabel("Max Teleport Retries:"))
        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(0, 20)
        self.max_retries_spin.setValue(int(self.config_manager.get('instance_teleport_max_retries', 5)))
        self.max_retries_spin.setSuffix(" retries")
        self.max_retries_spin.setToolTip("Maximum times to retry entering the instance if the HP bar doesn't appear after teleport. Set 0 to disable retries.")
        retries_layout.addWidget(self.max_retries_spin)
        retries_layout.addStretch()
        layout.addLayout(retries_layout)

    def init_logs_tab(self):
        layout = QVBoxLayout(self.logs_tab)
        header = QHBoxLayout()
        self.instances_done_label = QLabel("Instances done: 0")
        self.instances_done_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self.instances_done_label)
        header.addStretch()
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self._clear_instance_log)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        self.instance_log = QTextEdit()
        self.instance_log.setReadOnly(True)
        self.instance_log.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        layout.addWidget(self.instance_log)

        # Initialize count from stats tracker if available
        self._instances_done = 0
        try:
            if hasattr(self.bot_controller, 'stats_tracker') and self.bot_controller.stats_tracker is not None:
                cur = int(self.bot_controller.stats_tracker.get_stats().get('instance_count', 0))
                self._instances_done = max(0, cur)
        except Exception:
            pass
        self._update_instances_done_label()

    def _on_instance_entered_event(self, data: dict):
        """Event callback (may occur off the GUI thread); dispatch to GUI thread."""
        try:
            payload = data or {}
        except Exception:
            payload = {}
        # Ensure GUI-thread update
        QTimer.singleShot(0, lambda p=payload: self._append_instance_log_entry(p))

    def _append_instance_log_entry(self, data: dict):
        try:
            ts = QTimer().remainingTime()  # dummy call just to ensure Qt imported; not using value
        except Exception:
            pass
        try:
            import time as _t
            stamp = _t.strftime('%H:%M:%S', _t.localtime())
        except Exception:
            stamp = '??:??:??'
        pos_t = data.get('teleport_position') if isinstance(data, dict) else None
        pos_str = ''
        try:
            if pos_t and isinstance(pos_t, (tuple, list)) and len(pos_t) == 2:
                pos_str = f" at ({int(pos_t[0])}, {int(pos_t[1])})"
        except Exception:
            pos_str = ''
        line = f"[{stamp}] Instance entered{pos_str}"
        try:
            self.instance_log.append(line)
        except Exception:
            pass
        self._instances_done += 1
        self._update_instances_done_label()

    def _update_instances_done_label(self):
        try:
            self.instances_done_label.setText(f"Instances done: {int(self._instances_done)}")
        except Exception:
            pass

    def _clear_instance_log(self):
        try:
            self.instance_log.clear()
        except Exception:
            pass

    def closeEvent(self, event):
        # Unsubscribe to avoid leaks
        try:
            if hasattr(self.bot_controller, 'event_system') and self.bot_controller.event_system is not None:
                self.bot_controller.event_system.unsubscribe(EventType.INSTANCE_ENTERED, self._on_instance_entered_event)
        except Exception:
            pass
        super().closeEvent(event)

    def _open_aggro_bar_colors_dialog(self):
        try:
            dlg = AggroBarColorsDialog(self.config_manager, self)
            dlg.exec_()
        except Exception as e:
            logger.error(f"Failed to open Aggro Bar Colors dialog: {e}")

    def _qimage_from_mask(self, mask):
        try:
            import numpy as _np
            import cv2 as _cv
            if mask is None:
                return None
            if mask.ndim == 3:
                # convert BGR to gray
                mask = _cv.cvtColor(mask, _cv.COLOR_BGR2GRAY)
            if mask.dtype != _np.uint8:
                mask = mask.astype(_np.uint8)
            h, w = mask.shape[:2]
            qimg = QImage(mask.data, w, h, w, QImage.Format_Grayscale8)
            return qimg.copy()
        except Exception:
            return None

    def _set_preview_pixmap(self, label: QLabel, img: QImage):
        try:
            if img is None:
                label.setText("n/a")
                label.setPixmap(QPixmap())
                return
            pm = QPixmap.fromImage(img)
            try:
                pm = pm.scaled(220, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)  # type: ignore[attr-defined]
            except Exception:
                try:
                    pm = pm.scaled(220, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # type: ignore[attr-defined]
                except Exception:
                    pm = pm.scaled(220, 120)
            label.setPixmap(pm)
        except Exception:
            pass

    def _refresh_aggro_bar_preview(self):
        # Build masks for current ROI and colors and display them
        try:
            from ...core.detection.color_detector import build_mask
            import cv2 as _cv
        except Exception as e:
            self.aggro_bar_debug_text.append(f"[error] Missing deps for preview: {e}")
            return
        roi = self.config_manager.get_roi('instance_aggro_bar_roi')
        if not roi:
            self.aggro_bar_debug_text.append("[warn] Aggro Bar ROI not set")
            return
        # Prefer new aggro bar keys; fallback to legacy keys
        c1 = self.config_manager.get_color_spec('instance_aggro_bar_color1') or self.config_manager.get_color_spec('instance_aggro_color1')
        c2 = self.config_manager.get_color_spec('instance_aggro_bar_color2') or self.config_manager.get_color_spec('instance_aggro_color2')
        c3 = self.config_manager.get_color_spec('instance_aggro_bar_color3') or self.config_manager.get_color_spec('instance_aggro_color3')
        if not (c1 and c2 and c3):
            self.aggro_bar_debug_text.append("[warn] Configure all three aggro bar colors first")
            return
        frame = None
        try:
            if hasattr(self.bot_controller, 'capture_service') and self.bot_controller.capture_service is not None:
                frame = self.bot_controller.capture_service.capture_region(roi)
        except Exception:
            frame = None
        if frame is None:
            self.aggro_bar_debug_text.append("[error] Failed to capture ROI")
            return
        try:
            m1, _ = build_mask(frame, c1, step=1, precise=True, min_area=0)
            m2, _ = build_mask(frame, c2, step=1, precise=True, min_area=0)
            m3, _ = build_mask(frame, c3, step=1, precise=True, min_area=0)
            ok1 = _cv.countNonZero(m1)
            ok2 = _cv.countNonZero(m2)
            ok3 = _cv.countNonZero(m3)
            combo = _cv.bitwise_or(_cv.bitwise_or(m1, m2), m3)
            okc = _cv.countNonZero(combo)
            self.aggro_bar_debug_text.append(f"pixels: c1={ok1}, c2={ok2}, c3={ok3}, combo={okc}")
            self._set_preview_pixmap(self._bar_mask_label_c1, self._qimage_from_mask(m1))
            self._set_preview_pixmap(self._bar_mask_label_c2, self._qimage_from_mask(m2))
            self._set_preview_pixmap(self._bar_mask_label_c3, self._qimage_from_mask(m3))
            self._set_preview_pixmap(self._bar_mask_label_combo, self._qimage_from_mask(combo))
        except Exception as e:
            self.aggro_bar_debug_text.append(f"[error] Preview build failed: {e}")

    def _append_log_line(self, text: str):
        try:
            import time as _t
            stamp = _t.strftime('%H:%M:%S', _t.localtime())
        except Exception:
            stamp = '??:??:??'
        try:
            if hasattr(self, 'instance_log') and self.instance_log:
                self.instance_log.append(f"[{stamp}] {text}")
        except Exception:
            pass

    

    def _test_aggro_bar_detection(self):
        detector = None
        try:
            if hasattr(self.bot_controller, 'detection_engine') and self.bot_controller.detection_engine is not None:
                detector = self.bot_controller.detection_engine.instance_only_detector
        except Exception:
            detector = None
        if detector is None:
            QMessageBox.warning(self, "Detection", "Detection engine not available")
            return
        try:
            present = detector.detect_aggro_bar_present()
            msg = "Aggro bar present: YES" if present else "Aggro bar present: NO"
            self._append_log_line(msg)
            QMessageBox.information(self, "Test Detection", msg)
        except Exception as e:
            self._append_log_line(f"Aggro bar test failed: {e}")
            QMessageBox.critical(self, "Test Detection", f"Error: {e}")
    def refresh_live_labels(self):
        """No-op: countdown removed for detection-based aggro."""
        return

    def load_settings(self):
        """Populate UI controls from config."""
        try:
            # HP ROI
            hp_roi = self.config_manager.get_roi('instance_hp_bar_roi')
            if hp_roi:
                try:
                    self.hp_roi_selector.set_roi(hp_roi)
                except Exception:
                    pass
            # HP timeout and min pixels
            try:
                self.hp_timeout_selector.set_time(self.config_manager.get('instance_hp_timeout', 30.0))
            except Exception:
                pass
            try:
                self.hp_min_pixels_spin.setValue(self.config_manager.get('instance_hp_min_pixels', 50))
            except Exception:
                pass
            # Aggro interval
            # Aggro potion coordinate
            c = self.config_manager.get_coordinate('instance_aggro_potion_location')
            if c:
                self.aggro_potion_selector.set_coordinate(c.x, c.y)
            # Post-aggro wait
            try:
                self.instance_post_aggro_wait_spin.setValue(float(self.config_manager.get('instance_post_aggro_hp_wait', 8.0)))
            except Exception:
                pass
            try:
                self.aggro_click_cooldown_spin.setValue(float(self.config_manager.get('instance_aggro_click_cooldown', 7.0)))
            except Exception:
                pass
            # Strategy
            try:
                strat = str(self.config_manager.get('instance_aggro_strategy', 'bar')).lower()
                idx = 0 if strat == 'bar' else (1 if strat == 'timer' else 2)
                self.aggro_strategy_combo.setCurrentIndex(idx)
                self._update_legacy_group_visibility()
            except Exception:
                pass
            c = self.config_manager.get_coordinate('instance_token_location')
            if c:
                self.token_selector.set_coordinate(c.x, c.y)
            c = self.config_manager.get_coordinate('instance_teleport_location')
            if c:
                self.teleport_selector.set_coordinate(c.x, c.y)
            # Delay
            try:
                self.delay_selector.set_time(self.config_manager.get('instance_token_delay', 2.0))
            except Exception:
                pass
            # Post-teleport HP wait
            try:
                self.hp_reappear_wait_selector.set_time(self.config_manager.get('instance_post_teleport_hp_wait', 8.0))
            except Exception:
                pass
            # Max retries
            try:
                self.max_retries_spin.setValue(int(self.config_manager.get('instance_teleport_max_retries', 5)))
            except Exception:
                pass
            # Aggro Bar ROI and threshold
            try:
                aggro_bar_roi = self.config_manager.get_roi('instance_aggro_bar_roi')
                if aggro_bar_roi:
                    self.aggro_bar_roi_selector.set_roi(aggro_bar_roi)
            except Exception:
                pass
            try:
                self.aggro_bar_min_pixels_spin.setValue(int(self.config_manager.get('instance_aggro_bar_min_pixels_per_color', 30)))
            except Exception:
                pass
            try:
                show_overlay = bool(self.config_manager.get('instance_show_aggro_overlay', False))
                self.aggro_overlay_checkbox.setChecked(show_overlay)
                if show_overlay:
                    self._ensure_overlay()
                    self._aggro_overlay.set_enabled(True)
            except Exception:
                pass
        except Exception:
            pass

    def on_save_instance_mode_clicked(self):
        """Save all Instance Mode related settings to config."""
        self.save_instance_mode_settings(silent=False)

    def save_instance_mode_settings(self, silent: bool = True):
        """Persist Instance Mode settings to config. Optionally suppress popups.

        Args:
            silent: When True, do not show QMessageBox popups.
        """
        try:
            # HP settings
            hp_roi = self.hp_roi_selector.get_roi()
            self.config_manager.set_roi('instance_hp_bar_roi', hp_roi)
            self.config_manager.set('instance_hp_timeout', self.hp_timeout_selector.get_time())
            self.config_manager.set('instance_hp_min_pixels', int(self.hp_min_pixels_spin.value()))
            # Aggro interval
            # Aggro potion coordinate
            ax, ay = self.aggro_potion_selector.get_coordinate()
            self.config_manager.set_coordinate('instance_aggro_potion_location', Coordinate(ax, ay, 'Instance Aggro Potion'))
            # Post-aggro HP wait
            try:
                self.config_manager.set('instance_post_aggro_hp_wait', float(self.instance_post_aggro_wait_spin.value()))
            except Exception:
                pass
            try:
                self.config_manager.set('instance_aggro_click_cooldown', float(self.aggro_click_cooldown_spin.value()))
            except Exception:
                pass
            # Strategy + legacy timer params
            try:
                idx = int(self.aggro_strategy_combo.currentIndex())
            except Exception:
                idx = 0
            strat = 'bar' if idx == 0 else ('timer' if idx == 1 else 'hybrid')
            self.config_manager.set('instance_aggro_strategy', strat)
            try:
                self.config_manager.set('instance_aggro_interval_min', float(self.aggro_interval_spin.value()))
            except Exception:
                pass
            try:
                self.config_manager.set('instance_aggro_start_delay_s', float(self.aggro_start_delay_spin.value()))
            except Exception:
                pass
            try:
                self.config_manager.set('instance_aggro_jitter_enabled', bool(self.aggro_jitter_checkbox.isChecked()))
            except Exception:
                pass
            try:
                self.config_manager.set('instance_aggro_jitter_percent', float(self.aggro_jitter_spin.value()))
            except Exception:
                pass
            # Aggro Bar ROI + threshold
            try:
                aggro_bar_roi = self.aggro_bar_roi_selector.get_roi()
                self.config_manager.set_roi('instance_aggro_bar_roi', aggro_bar_roi)
            except Exception:
                pass
            try:
                self.config_manager.set('instance_aggro_bar_min_pixels_per_color', int(self.aggro_bar_min_pixels_spin.value()))
            except Exception:
                pass
            try:
                self.config_manager.set('instance_post_aggro_hp_wait', float(self.instance_post_aggro_wait_spin.value()))
            except Exception:
                pass
            try:
                self.config_manager.set('instance_show_aggro_overlay', bool(self.aggro_overlay_checkbox.isChecked()))
            except Exception:
                pass
            tx, ty = self.token_selector.get_coordinate()
            self.config_manager.set_coordinate('instance_token_location', Coordinate(tx, ty, 'Instance Token'))
            px, py = self.teleport_selector.get_coordinate()
            self.config_manager.set_coordinate('instance_teleport_location', Coordinate(px, py, 'Instance Teleport'))
            # Delay
            self.config_manager.set('instance_token_delay', self.delay_selector.get_time())
            # Post-teleport HP wait
            self.config_manager.set('instance_post_teleport_hp_wait', self.hp_reappear_wait_selector.get_time())
            # Max retries
            try:
                self.config_manager.set('instance_teleport_max_retries', int(self.max_retries_spin.value()))
            except Exception:
                pass
            if not silent:
                QMessageBox.information(self, 'Saved', 'Instance Mode settings saved.')
        except Exception as e:
            logger.error(f"Error saving Instance Mode settings: {e}")

    def _reset_aggro_timer_clicked(self):
        """Publish an event or update config to trigger timer reset in controller."""
        try:
            # Set a volatile flag in config the controller will observe and clear
            self.config_manager.set('instance_aggro_timer_reset_now', True)
            QMessageBox.information(self, 'Aggro Timer', 'Aggro timer will reset now (start delay applies).')
        except Exception as e:
            logger.error(f"Failed to request aggro timer reset: {e}")
            QMessageBox.critical(self, 'Error', f'Could not reset timer: {e}')

    # -------- Timer UI update (polling) --------
    def showEvent(self, event):  # type: ignore[override]
        super().showEvent(event)
        # Lightweight polling every ~1s to refresh the label
        try:
            from PyQt5.QtCore import QTimer
        except Exception:
            try:
                from PyQt6.QtCore import QTimer  # type: ignore
            except Exception:
                QTimer = None  # type: ignore
        if QTimer is not None:
            if not hasattr(self, '_timer_update'):  # create once
                self._timer_update = QTimer(self)
                self._timer_update.setInterval(1000)
                self._timer_update.timeout.connect(self._refresh_next_aggro_label)
            self._timer_update.start()

    def hideEvent(self, event):  # type: ignore[override]
        super().hideEvent(event)
        if hasattr(self, '_timer_update') and self._timer_update is not None:
            try:
                self._timer_update.stop()
            except Exception:
                pass

    def _refresh_next_aggro_label(self):
        try:
            phase = str(self.config_manager.get('instance_aggro_timer_phase', '-'))
            ts = float(self.config_manager.get('instance_next_aggro_time_epoch', 0.0) or 0.0)
            if ts > 0:
                import time
                remaining = max(0.0, ts - time.time())
                m = int(remaining // 60)
                s = int(remaining % 60)
                text = f"Next aggro: {m:02d}:{s:02d} (phase: {phase})"
            else:
                text = "Next aggro: --:-- (phase: -)"
            self.next_aggro_label.setText(text)
        except Exception:
            pass

    # ----------------- Overlay handling -----------------
    def _ensure_overlay(self):
        if getattr(self, '_aggro_overlay', None) is None:
            try:
                self._aggro_overlay = AggroOverlay(self.config_manager, self.bot_controller, roi_key='instance_aggro_bar_roi')
                # Prime ROI
                roi = self.config_manager.get_roi('instance_aggro_bar_roi')
                if roi:
                    self._aggro_overlay.set_roi(roi)
            except Exception as e:
                logger.error(f"Failed to init overlay: {e}")

    def _on_overlay_toggled(self, state: int):
        try:
            enabled = state == getattr(Qt, 'CheckState').Checked  # PyQt6
        except Exception:
            enabled = state == getattr(Qt, 'Checked', 2)  # PyQt5 fallback or raw value
        try:
            self.config_manager.set('instance_show_aggro_overlay', bool(enabled))
        except Exception:
            pass
        if enabled:
            self._ensure_overlay()
            if self._aggro_overlay:
                self._aggro_overlay.set_enabled(True)
        else:
            if self._aggro_overlay:
                self._aggro_overlay.set_enabled(False)

    def _on_aggro_bar_roi_changed(self, roi: ROI):
        try:
            self.config_manager.set_roi('instance_aggro_bar_roi', roi)
        except Exception:
            pass
        try:
            if getattr(self, '_aggro_overlay', None):
                self._aggro_overlay.set_roi(roi)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Instance Settings panel (without legacy Instance-Only tab)
# ---------------------------------------------------------------------------

class InstancePanel(QWidget):
    """Panel for general Instance settings (entry/teleport)."""

    def __init__(self, config_manager, bot_controller):
        super().__init__()
        self.config_manager = config_manager
        self.bot_controller = bot_controller
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Instance entry group
        entry_group = QGroupBox("Instance Entry")
        entry_layout = QVBoxLayout(entry_group)

        # Instance token
        token_group = QGroupBox("Instance Token")
        token_layout = QVBoxLayout(token_group)
        self.token_selector = CoordinateSelector(config_manager=self.config_manager, bot_controller=self.bot_controller)
        token_layout.addWidget(self.token_selector)
        entry_layout.addWidget(token_group)

        # Instance teleport
        teleport_group = QGroupBox("Instance Teleport")
        teleport_layout = QVBoxLayout(teleport_group)
        self.teleport_selector = CoordinateSelector(config_manager=self.config_manager, bot_controller=self.bot_controller)
        teleport_layout.addWidget(self.teleport_selector)

        # Delay between clicks
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Click Delay:"))
        self.token_delay_selector = TimeSelector(
            label="",
            initial_seconds=self.config_manager.get('instance_token_delay', 2.0),
            mode=TimeSelector.MODE_SEC_ONLY,
            tooltip="Time to wait between clicking the instance token and the teleport option"
        )
        delay_layout.addWidget(self.token_delay_selector)
        delay_layout.addStretch()
        teleport_layout.addLayout(delay_layout)

        entry_layout.addWidget(teleport_group)

        # Actions
        actions = QHBoxLayout()
        self.test_entry_button = QPushButton("Test Instance Entry")
        self.test_entry_button.clicked.connect(self.on_test_entry_clicked)
        TooltipHelper.add_tooltip(self.test_entry_button, "Preview the instance entry sequence")
        actions.addWidget(self.test_entry_button)
        self.save_entry_button = QPushButton("Save Entry Settings")
        self.save_entry_button.clicked.connect(self.on_save_entry_clicked)
        actions.addWidget(self.save_entry_button)
        entry_layout.addLayout(actions)

        main_layout.addWidget(entry_group)
        main_layout.addStretch()

    def load_settings(self):
        token_coord = self.config_manager.get_coordinate('instance_token_location')
        if token_coord:
            self.token_selector.set_coordinate(token_coord.x, token_coord.y)
        teleport_coord = self.config_manager.get_coordinate('instance_teleport_location')
        if teleport_coord:
            self.teleport_selector.set_coordinate(teleport_coord.x, teleport_coord.y)
        self.token_delay_selector.set_time(self.config_manager.get('instance_token_delay', 2.0))

    def on_test_entry_clicked(self):
        token_x, token_y = self.token_selector.get_coordinate()
        teleport_x, teleport_y = self.teleport_selector.get_coordinate()
        if (token_x, token_y) == (0, 0):
            QMessageBox.warning(self, "Warning", "Instance token location not set")
            return
        if (teleport_x, teleport_y) == (0, 0):
            QMessageBox.warning(self, "Warning", "Instance teleport location not set")
            return
        delay_seconds = self.token_delay_selector.get_time()
        if delay_seconds is None:
            delay_val = float(self.config_manager.get('instance_token_delay', 2.0))
        else:
            delay_val = float(delay_seconds)
        m = int(delay_val // 60)
        s = int(delay_val % 60)
        delay_str = f"{m} min {s} sec" if m > 0 else f"{s} sec"
        QMessageBox.information(
            self,
            "Test Instance Entry",
            f"1) Click token at ({token_x}, {token_y})\n"
            f"2) Wait {delay_str}\n"
            f"3) Click teleport at ({teleport_x}, {teleport_y})\n\n"
            "This is a preview only — no clicks will be performed."
        )

    def on_save_entry_clicked(self):
        try:
            token_x, token_y = self.token_selector.get_coordinate()
            teleport_x, teleport_y = self.teleport_selector.get_coordinate()
            token_delay = self.token_delay_selector.get_time()
            token_coord = Coordinate(token_x, token_y, "Instance Token")
            teleport_coord = Coordinate(teleport_x, teleport_y, "Instance Teleport")
            self.config_manager.set_coordinate('instance_token_location', token_coord)
            self.config_manager.set_coordinate('instance_teleport_location', teleport_coord)
            self.config_manager.set('instance_token_delay', token_delay)
            QMessageBox.information(self, "Saved", "Instance entry settings saved.")
        except Exception as e:
            logger.error(f"Error saving instance entry settings: {e}")
            QMessageBox.critical(self, "Error", f"Could not save settings: {e}")


class AggroColorsDialog(QDialog):
    """Sub window to configure the three aggro colors to keep the main Aggro tab compact."""
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aggro Colors")
        self.config_manager = config_manager
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Pick three colors that uniquely identify the aggro potion. Changes save immediately."))
        self.color1 = EnhancedColorEditor(self.config_manager, 'instance_aggro_color1', title="Color 1")
        self.color2 = EnhancedColorEditor(self.config_manager, 'instance_aggro_color2', title="Color 2")
        self.color3 = EnhancedColorEditor(self.config_manager, 'instance_aggro_color3', title="Color 3")
        v.addWidget(self.color1)
        v.addWidget(self.color2)
        v.addWidget(self.color3)
        btns = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btns.addStretch()
        btns.addWidget(close_btn)
        v.addLayout(btns)


class AggroBarColorsDialog(QDialog):
    """Dialog to configure the three aggro bar colors (separate from potion)."""
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aggro Bar Colors")
        self.config_manager = config_manager
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Pick three colors that indicate the aggro bar is active. Changes save immediately."))
        self.color1 = EnhancedColorEditor(self.config_manager, 'instance_aggro_bar_color1', title="Color 1")
        self.color2 = EnhancedColorEditor(self.config_manager, 'instance_aggro_bar_color2', title="Color 2")
        self.color3 = EnhancedColorEditor(self.config_manager, 'instance_aggro_bar_color3', title="Color 3")
        v.addWidget(self.color1)
        v.addWidget(self.color2)
        v.addWidget(self.color3)
        btns = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btns.addStretch()
        btns.addWidget(close_btn)
        v.addLayout(btns)