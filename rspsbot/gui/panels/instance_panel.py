import logging

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QLineEdit,
    QMessageBox, QFrame, QTabWidget
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPalette

from ...core.config import Coordinate, ROI, ColorSpec
from ..components.time_selector import TimeSelector
from ..components.tooltip_helper import TooltipHelper
from ..components.advanced_roi_selector import AdvancedROISelector
from ..components.enhanced_color_editor import EnhancedColorEditor
from .teleport_panel import CoordinateSelector

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

        # Instance Teleport Tab
        self.teleport_tab = QWidget()
        self.init_teleport_tab()
        self.tab_widget.addTab(self.teleport_tab, "Instance Teleport")

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
        label = QLabel("Configure timer-based aggro potion usage for Instance Mode.")
        label.setWordWrap(True)
        layout.addWidget(label)
        # Interval (minutes) for timer-based aggro usage in Instance Mode
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Aggro Interval (minutes):"))
        self.instance_aggro_interval_spin = QDoubleSpinBox()
        self.instance_aggro_interval_spin.setDecimals(1)
        self.instance_aggro_interval_spin.setRange(0.2, 240.0)
        self.instance_aggro_interval_spin.setValue(float(self.config_manager.get('instance_aggro_interval_min', 15.0)))
        interval_row.addWidget(self.instance_aggro_interval_spin)
        interval_row.addStretch()
        layout.addLayout(interval_row)
        # Remaining-time display (live)
        self.aggro_remaining_label = QLabel("Next aggro in: --:--")
        self.aggro_remaining_label.setStyleSheet("color: #4aa; font-weight: bold;")
        layout.addWidget(self.aggro_remaining_label)
        # Aggro potion location
        self.aggro_selector = CoordinateSelector(config_manager=self.config_manager, bot_controller=self.bot_controller)
        layout.addWidget(self.aggro_selector)
        # No visual aggro controls (removed)

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
    def refresh_live_labels(self):
        """Update the aggro countdown label using controller state."""
        try:
            remaining = self.bot_controller.get_aggro_remaining_seconds()
            if remaining is None:
                self.aggro_remaining_label.setText("Next aggro in: n/a")
            else:
                remaining = max(0, int(remaining))
                m, s = divmod(remaining, 60)
                if m >= 60:
                    h, rem = divmod(m, 60)
                    self.aggro_remaining_label.setText(f"Next aggro in: {int(h):02}:{int(rem):02}:{int(s):02}")
                else:
                    self.aggro_remaining_label.setText(f"Next aggro in: {int(m):02}:{int(s):02}")
        except Exception:
            pass

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
            try:
                self.instance_aggro_interval_spin.setValue(float(self.config_manager.get('instance_aggro_interval_min', 15.0)))
            except Exception:
                pass
            # Coordinates
            c = self.config_manager.get_coordinate('instance_aggro_potion_location')
            if c:
                self.aggro_selector.set_coordinate(c.x, c.y)
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
            self.config_manager.set('instance_aggro_interval_min', float(self.instance_aggro_interval_spin.value()))
            # Coordinates
            ax, ay = self.aggro_selector.get_coordinate()
            self.config_manager.set_coordinate('instance_aggro_potion_location', Coordinate(ax, ay, 'Instance Aggro Potion'))
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
            if not silent:
                QMessageBox.critical(self, 'Error', f'Could not save settings: {e}')


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
        m = int(delay_seconds // 60)
        s = int(delay_seconds % 60)
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