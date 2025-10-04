"""
Standalone Slayer Mode window wiring Detection, Action, and the SlayerPanel.
"""
from __future__ import annotations
import logging
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTabWidget
from types import SimpleNamespace

from ..core.config import ConfigManager
from ..core.detection.detector import DetectionEngine
from ..utils.logging import setup_logging
from ..core.state import EventSystem
from ..core.action import ActionManager
from .panels.slayer_panel import SlayerPanel
from .panels.detection_panel import DetectionPanel
from .panels.combat_panel import CombatPanel
from .panels.teleport_panel import TeleportPanel
from .panels.logs_panel_enhanced import LogsPanelEnhanced
from .panels.stats_panel import StatsPanel

logger = logging.getLogger('rspsbot.gui.slayer_window')


class SlayerWindow(QMainWindow):
    def __init__(self, config: ConfigManager, detection_engine: DetectionEngine, action_manager: ActionManager, event_system: EventSystem):
        super().__init__()
        self.setWindowTitle("RSPS Color Bot v3 - Slayer Mode")
        self.config = config
        self.engine = detection_engine
        self.action_manager = action_manager
        self.events = event_system

        central = QWidget(self)
        layout = QVBoxLayout(central)
        tabs = QTabWidget(central)

        # Build a lightweight controller object expected by existing panels
        # Provides: action_manager, event_system, capture_service, detection_engine
        capture_service = getattr(self.engine, 'capture_service', None)
        self.bot_controller = SimpleNamespace(
            action_manager=self.action_manager,
            event_system=self.events,
            capture_service=capture_service,
            detection_engine=self.engine,
        )
        # Optionally attach commonly used managers for richer panel functionality
        try:
            from ..core.modules.teleport import TeleportManager
            self.bot_controller.teleport_manager = TeleportManager(self.config, self.action_manager, self.events)
        except Exception:
            self.bot_controller.teleport_manager = None
        try:
            from ..core.modules.potion import PotionManager
            self.bot_controller.potion_manager = PotionManager(self.config, self.action_manager, self.events)
        except Exception:
            self.bot_controller.potion_manager = None
        try:
            from ..core.stats import StatisticsTracker
            self.bot_controller.stats_tracker = StatisticsTracker(self.events)
        except Exception:
            self.bot_controller.stats_tracker = None

        # Core panels (use existing panels that expect a bot_controller arg)
        tabs.addTab(DetectionPanel(self.config, self.bot_controller, hide_monster_colors=True), "Detection")
        tabs.addTab(CombatPanel(self.config, self.bot_controller), "Combat")
        tabs.addTab(TeleportPanel(self.config, self.bot_controller), "Teleport")
        tabs.addTab(SlayerPanel(self.config), "Slayer")
        tabs.addTab(LogsPanelEnhanced(self.config), "Logs")
        tabs.addTab(StatsPanel(self.config, self.bot_controller), "Stats")

        layout.addWidget(tabs)
        self.setCentralWidget(central)
