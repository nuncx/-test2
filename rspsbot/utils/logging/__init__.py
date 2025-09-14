"""
Logging utilities for RSPS Color Bot v3
"""
import os
import logging
import logging.handlers
import colorlog
from datetime import datetime

def setup_logging(level=logging.INFO, log_to_file=True):
    """
    Setup logging configuration with colored console output and file logging.
    
    Args:
        level: Logging level (default: INFO)
        log_to_file: Whether to log to file (default: True)
    
    Returns:
        Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatter for console with colors
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Create file handler if requested
    if log_to_file:
        # Create a new log file for each run
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join('logs', f'rspsbot_{timestamp}.log')
        
        # Create formatter for file (without colors)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Create rotating file handler (10 MB max size, keep 5 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Create module-specific loggers
    create_module_logger('core', level)
    create_module_logger('gui', level)
    create_module_logger('modules', level)
    create_module_logger('utils', level)
    
    return logger

def create_module_logger(module_name, level=logging.INFO):
    """
    Create a logger for a specific module.
    
    Args:
        module_name: Name of the module
        level: Logging level (default: INFO)
    
    Returns:
        Logger: Module-specific logger
    """
    logger = logging.getLogger(f'rspsbot.{module_name}')
    logger.setLevel(level)
    return logger

# Convenience function to get a logger for a specific module
def get_logger(name):
    """
    Get a logger for a specific module or class.
    
    Args:
        name: Name of the module or class
    
    Returns:
        Logger: Module-specific logger
    """
    if not name.startswith('rspsbot.'):
        name = f'rspsbot.{name}'
    return logging.getLogger(name)