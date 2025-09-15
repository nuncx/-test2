#!/usr/bin/env python3
"""
RSPS Color Bot v3 - Main entry point

This is the main entry point for the RSPS Color Bot application.
It initializes the application, sets up logging, and starts the GUI.
"""
import sys
import os
import logging
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import after path setup
from rspsbot.utils.logging import setup_logging
from rspsbot.core.config import ConfigManager
from rspsbot.gui.main_window import MainWindow
from rspsbot.core.state import BotController

# Setup argument parser
def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='RSPS Color Bot v3')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--profile', type=str, help='Load specific profile on startup')
    parser.add_argument('--no-gui', action='store_true', help='Run without GUI (headless mode)')
    parser.add_argument('--capture-test', action='store_true', help='Run a capture health check and a safe test click, then exit')
    return parser.parse_args()

def main():
    """Main entry point for the application"""
    # Parse arguments
    args = parse_arguments()
    
    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logging(log_level)
    logger.info("Starting RSPS Color Bot v3")
    
    try:
        # Initialize configuration
        config_manager = ConfigManager()
        
        # Load profile if specified
        if args.profile:
            profile_path = os.path.join('profiles', f"{args.profile}")
            if os.path.exists(profile_path):
                logger.info(f"Loading profile: {args.profile}")
                config_manager.load_profile(args.profile)
            else:
                logger.warning(f"Profile not found: {args.profile}")
        
        # Initialize bot controller
        bot_controller = BotController(config_manager)
        
        # Start GUI or headless mode
        if args.capture_test:
            # Minimal capture test without GUI
            from rspsbot.core.detection.capture import CaptureService
            from rspsbot.core.detection.detector import ROIManager
            logger.info("Running capture health check...")
            cap = CaptureService()
            roi_mgr = ROIManager(config_manager, cap)
            roi = roi_mgr.get_active_roi()
            stats = cap.capture_healthcheck(roi)
            logger.info(f"Capture stats: mean={stats['mean']:.2f}, std={stats['std']:.2f}, nonzero_ratio={stats['nonzero_ratio']:.3f}")
            # Simple heuristic: if nonzero_ratio is near 0, capture likely black
            if stats['nonzero_ratio'] < 0.01 and stats['std'] < 1.0:
                logger.warning("Capture appears black/blank. Keep display awake or prevent lock.")
            # Perform a safe test click at ROI center via ActionManager's mouse controller (if available)
            try:
                am = bot_controller.action_manager
                if am:
                    cx = roi['left'] + roi['width'] // 2
                    cy = roi['top'] + roi['height'] // 2
                    logger.info(f"Test click at center: ({cx}, {cy})")
                    # Use underlying mouse controller
                    if hasattr(am, 'mouse_controller') and am.mouse_controller:
                        am.mouse_controller.move_and_click(cx, cy)
                    else:
                        logger.warning("Mouse controller not available on ActionManager")
                else:
                    logger.warning("ActionManager unavailable; skipping test click")
            except Exception as e:
                logger.error(f"Test click failed: {e}")
            sys.exit(0)
        elif args.no_gui:
            logger.info("Running in headless mode")
            # TODO: Implement headless mode
            raise NotImplementedError("Headless mode not yet implemented")
        else:
            # Import PyQt5 here to avoid dependency in headless mode
            from PyQt5.QtWidgets import QApplication
            
            # Create application
            app = QApplication(sys.argv)
            app.setApplicationName("RSPS Color Bot v3")
            
            # Create and show main window
            main_window = MainWindow(config_manager, bot_controller)
            main_window.show()
            
            # Start event loop
            logger.info("GUI initialized, entering main event loop")
            sys.exit(app.exec_())
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()