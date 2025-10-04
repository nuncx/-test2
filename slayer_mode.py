#!/usr/bin/env python3
"""
Standalone runner for Slayer Mode.
Initializes config, detection engine, action managers, GUI panels, and the SlayerModule loop.
"""
import sys
import os
import logging
from pathlib import Path
from typing import Optional

# Ensure project root on path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from rspsbot.utils.logging import setup_logging
from rspsbot.core.config import ConfigManager, ROI
from rspsbot.core.detection.detector import DetectionEngine
from rspsbot.core.state import EventSystem
from rspsbot.core.action import ActionManager
from rspsbot.core.modules.slayer_module import SlayerModule


def main():
    logger = setup_logging(logging.INFO)
    logger.info("Starting Slayer Mode")

    config = ConfigManager()

    # Ensure ROIs sane (reuse defaults from run.py)
    try:
        hp = config.get('hpbar_roi')
        if not hp or (isinstance(hp, dict) and (hp.get('left') != 25 or hp.get('top') != 79 or hp.get('width') != 100 or hp.get('height') != 17)):
            config.set_roi('hpbar_roi', ROI(25, 79, 100, 17, mode='relative'))
            config.set('hpbar_roi_follow_window', True)
    except Exception:
        pass
    try:
        s = config.get('search_roi')
        if not s or (isinstance(s, dict) and (s.get('left') != 6 or s.get('top') != 28 or s.get('width') != 515 or s.get('height') != 338)):
            config.set_roi('search_roi', ROI(6, 28, 515, 338, mode='relative'))
    except Exception:
        pass

    # Wire core components
    from rspsbot.core.detection.capture import CaptureService
    capture = CaptureService()
    engine = DetectionEngine(config, capture)
    actions = ActionManager(config)
    events = EventSystem()

    # Hook GUI
    from PyQt5.QtWidgets import QApplication
    from rspsbot.gui.slayer_window import SlayerWindow

    app = QApplication(sys.argv)
    app.setApplicationName("RSPS Color Bot v3 - Slayer Mode")

    win = SlayerWindow(config, engine, actions, events)
    win.show()

    # Install a timer loop to drive SlayerModule
    from PyQt5.QtCore import QTimer
    slayer = SlayerModule(config, engine, actions.mouse_controller, actions.keyboard_controller, events)
    slayer.start()

    def tick():
        try:
            slayer.update_config()
            slayer.process_cycle()
        except Exception as e:
            logging.getLogger('slayer_mode').error(f"Slayer cycle error: {e}")

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(int(1000 * float(config.get('scan_interval', 0.2))))

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
