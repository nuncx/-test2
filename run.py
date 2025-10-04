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
    parser.add_argument('--multi-monster', action='store_true', help='Enable Multi Monster Mode at startup')
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

        # Ensure HP bar ROI is set to the fixed relative rectangle on startup
        try:
            hp_roi = config_manager.get('hpbar_roi')
            needs_set = False
            if not hp_roi:
                needs_set = True
            elif isinstance(hp_roi, dict):
                w = int(hp_roi.get('width', 0)); h = int(hp_roi.get('height', 0))
                l = int(hp_roi.get('left', -1)); t = int(hp_roi.get('top', -1))
                mode = str(hp_roi.get('mode', 'relative')).lower()
                if not (l == 25 and t == 79 and w == 100 and h == 17 and mode == 'relative'):
                    needs_set = True
            else:
                needs_set = True
            if needs_set:
                from rspsbot.core.config import ROI as ROIModel
                config_manager.set_roi('hpbar_roi', ROIModel(25, 79, 100, 17, mode='relative'))
                config_manager.set('hpbar_roi_follow_window', True)
        except Exception:
            pass

        # Ensure SEARCH ROI is set to the fixed relative rectangle on startup
        try:
            s_roi = config_manager.get('search_roi')
            needs_set = False
            if not s_roi:
                needs_set = True
            elif isinstance(s_roi, dict):
                w = int(s_roi.get('width', 0)); h = int(s_roi.get('height', 0))
                l = int(s_roi.get('left', -1)); t = int(s_roi.get('top', -1))
                mode = str(s_roi.get('mode', 'relative')).lower()
                if not (l == 6 and t == 28 and w == 515 and h == 338 and mode == 'relative'):
                    needs_set = True
            else:
                needs_set = True
            if needs_set:
                from rspsbot.core.config import ROI as ROIModel
                config_manager.set_roi('search_roi', ROIModel(6, 28, 515, 338, mode='relative'))
        except Exception:
            pass

        # Optional: force-enable Multi Monster Mode via CLI flag
        if getattr(args, 'multi_monster', False):
            logger.info("CLI flag --multi-monster provided: enabling Multi Monster Mode")
            try:
                config_manager.set('multi_monster_mode_enabled', True)
            except Exception as e:
                logger.warning(f"Failed to set multi_monster_mode_enabled via CLI: {e}")
        
        # Initialize bot controller
        bot_controller = BotController(config_manager)
        
        # Start GUI or headless mode
        if args.no_gui:
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