"""
Logs panel for RSPS Color Bot v3
"""
import logging
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTextEdit, QComboBox, QCheckBox, QFileDialog,
    QSplitter
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTextCursor, QColor, QTextCharFormat, QFont

# Get module logger
logger = logging.getLogger('rspsbot.gui.panels.logs_panel')

class LogHandler(logging.Handler):
    """
    Custom logging handler that emits signals for log messages
    """
    
    def __init__(self, callback):
        """
        Initialize the log handler
        
        Args:
            callback: Function to call with log records
        """
        super().__init__()
        self.callback = callback
    
    def emit(self, record):
        """
        Emit a log record
        
        Args:
            record: Log record
        """
        try:
            msg = self.format(record)
            self.callback(record, msg)
        except Exception:
            self.handleError(record)

class LogsPanel(QWidget):
    """
    Panel for displaying log messages
    """
    
    def __init__(self, config_manager):
        """
        Initialize the logs panel
        
        Args:
            config_manager: Configuration manager
        """
        super().__init__()
        self.config_manager = config_manager
        
        # Log buffer
        self.log_buffer = []
        self.max_log_buffer = 1000
        
        # Initialize UI
        self.init_ui()
        
        # Set up log handler
        self.log_handler = LogHandler(self.handle_log)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
        self.log_handler.setLevel(logging.DEBUG)
        
        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        
        # Start auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_logs)
        self.refresh_timer.start(500)  # Refresh every 500ms
    
    def init_ui(self):
        """Initialize the UI components"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Create splitter for logs and debug info
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # Logs group
        logs_widget = QWidget()
        logs_layout = QVBoxLayout(logs_widget)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        
        # Log controls
        controls_layout = QHBoxLayout()
        
        # Level filter
        controls_layout.addWidget(QLabel("Level:"))
        
        self.level_combo = QComboBox()
        self.level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_combo.setCurrentText("INFO")
        self.level_combo.currentTextChanged.connect(self.on_level_changed)
        controls_layout.addWidget(self.level_combo)
        
        # Module filter
        controls_layout.addWidget(QLabel("Module:"))
        
        self.module_combo = QComboBox()
        self.module_combo.addItem("All")
        self.module_combo.addItems([
            "rspsbot.core",
            "rspsbot.gui",
            "rspsbot.utils"
        ])
        self.module_combo.setCurrentText("All")
        self.module_combo.currentTextChanged.connect(self.on_module_changed)
        controls_layout.addWidget(self.module_combo)
        
        # Auto-scroll checkbox
        self.auto_scroll_checkbox = QCheckBox("Auto-scroll")
        self.auto_scroll_checkbox.setChecked(True)
        controls_layout.addWidget(self.auto_scroll_checkbox)
        
        # Clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.on_clear_clicked)
        controls_layout.addWidget(self.clear_button)
        
        # Save button
        self.save_button = QPushButton("Save Logs")
        self.save_button.clicked.connect(self.on_save_clicked)
        controls_layout.addWidget(self.save_button)
        
        logs_layout.addLayout(controls_layout)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        self.log_text.setFont(QFont("Courier New", 9))
        logs_layout.addWidget(self.log_text)
        
        # Add logs widget to splitter
        splitter.addWidget(logs_widget)
        
        # Debug info group
        debug_group = QGroupBox("Debug Information")
        debug_layout = QVBoxLayout(debug_group)
        
        # Debug text area
        self.debug_text = QTextEdit()
        self.debug_text.setReadOnly(True)
        self.debug_text.setLineWrapMode(QTextEdit.NoWrap)
        self.debug_text.setFont(QFont("Courier New", 9))
        debug_layout.addWidget(self.debug_text)
        
        # Add debug group to splitter
        splitter.addWidget(debug_group)
        
        # Set initial splitter sizes
        splitter.setSizes([700, 300])
        
        # Update debug info
        self.update_debug_info()
    
    def handle_log(self, record, message):
        """
        Handle a log record
        
        Args:
            record: Log record
            message: Formatted message
        """
        # Add to buffer
        self.log_buffer.append((record, message))
        
        # Trim buffer if needed
        if len(self.log_buffer) > self.max_log_buffer:
            self.log_buffer = self.log_buffer[-self.max_log_buffer:]
    
    def refresh_logs(self):
        """Refresh the log display"""
        # Check if there are new logs
        if not self.log_buffer:
            return
        
        # Get current filter settings
        level_name = self.level_combo.currentText()
        level = getattr(logging, level_name)
        
        module_filter = self.module_combo.currentText()
        if module_filter == "All":
            module_filter = None
        
        # Get current cursor
        cursor = self.log_text.textCursor()
        
        # Remember if we were at the end
        at_end = cursor.atEnd()
        
        # Process new logs
        for record, message in self.log_buffer:
            # Apply filters
            if record.levelno < level:
                continue
            
            if module_filter and not record.name.startswith(module_filter):
                continue
            
            # Create format for this log level
            format = QTextCharFormat()
            
            if record.levelno >= logging.CRITICAL:
                format.setForeground(QColor(255, 0, 0))  # Red
                format.setFontWeight(QFont.Bold)
            elif record.levelno >= logging.ERROR:
                format.setForeground(QColor(255, 0, 0))  # Red
            elif record.levelno >= logging.WARNING:
                format.setForeground(QColor(255, 165, 0))  # Orange
            elif record.levelno >= logging.INFO:
                format.setForeground(QColor(0, 0, 0))  # Black
            else:  # DEBUG
                format.setForeground(QColor(128, 128, 128))  # Gray
            
            # Add message
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(message + "\n", format)
        
        # Clear buffer
        self.log_buffer = []
        
        # Auto-scroll if enabled
        if self.auto_scroll_checkbox.isChecked() or at_end:
            cursor.movePosition(QTextCursor.End)
            self.log_text.setTextCursor(cursor)
    
    def update_debug_info(self):
        """Update debug information"""
        try:
            # Get system info
            import platform
            import psutil
            import sys
            
            # Clear debug text
            self.debug_text.clear()
            
            # Add system info
            self.debug_text.append(f"Python: {sys.version}")
            self.debug_text.append(f"Platform: {platform.platform()}")
            self.debug_text.append(f"CPU: {platform.processor()}")
            self.debug_text.append(f"Memory: {psutil.virtual_memory().total / (1024 * 1024 * 1024):.2f} GB")
            self.debug_text.append("")
            
            # Add dependency versions
            self.debug_text.append("Dependency Versions:")
            
            try:
                import numpy
                self.debug_text.append(f"NumPy: {numpy.__version__}")
            except ImportError:
                self.debug_text.append("NumPy: Not installed")
            
            try:
                import cv2
                self.debug_text.append(f"OpenCV: {cv2.__version__}")
            except ImportError:
                self.debug_text.append("OpenCV: Not installed")
            
            try:
                import PyQt5.QtCore
                self.debug_text.append(f"PyQt5: {PyQt5.QtCore.QT_VERSION_STR}")
            except ImportError:
                self.debug_text.append("PyQt5: Not installed")
            
            try:
                import pyautogui
                try:
                    ver = getattr(pyautogui, "__version__", None)
                    if ver is None:
                        # fallback to package metadata
                        try:
                            from importlib.metadata import version, PackageNotFoundError
                        except Exception:
                            from importlib_metadata import version, PackageNotFoundError  # type: ignore
                        try:
                            ver = version("pyautogui")
                        except PackageNotFoundError:
                            ver = "Unknown"
                    self.debug_text.append(f"PyAutoGUI: {ver}")
                except Exception:
                    self.debug_text.append("PyAutoGUI: Unknown")
            except ImportError:
                self.debug_text.append("PyAutoGUI: Not installed")
            
            try:
                import mss
                try:
                    ver = getattr(mss, "__version__", None)
                    if ver is None:
                        try:
                            from importlib.metadata import version, PackageNotFoundError
                        except Exception:
                            from importlib_metadata import version, PackageNotFoundError  # type: ignore
                        try:
                            ver = version("mss")
                        except PackageNotFoundError:
                            ver = "Unknown"
                    self.debug_text.append(f"MSS: {ver}")
                except Exception:
                    self.debug_text.append("MSS: Unknown")
            except ImportError:
                self.debug_text.append("MSS: Not installed")
            
            try:
                import pynput
                try:
                    ver = getattr(pynput, "__version__", None)
                    if ver is None:
                        try:
                            from importlib.metadata import version, PackageNotFoundError
                        except Exception:
                            from importlib_metadata import version, PackageNotFoundError  # type: ignore
                        try:
                            ver = version("pynput")
                        except PackageNotFoundError:
                            ver = "Unknown"
                    self.debug_text.append(f"PyInput: {ver}")
                except Exception:
                    self.debug_text.append("PyInput: Unknown")
            except ImportError:
                self.debug_text.append("PyInput: Not installed")
            
            self.debug_text.append("")
            
            # Add runtime info
            self.debug_text.append("Runtime Information:")
            self.debug_text.append(f"CPU Usage: {psutil.cpu_percent()}%")
            self.debug_text.append(f"Memory Usage: {psutil.Process().memory_info().rss / (1024 * 1024):.2f} MB")
            
            # Schedule next update
            QTimer.singleShot(5000, self.update_debug_info)
        
        except Exception as e:
            self.debug_text.append(f"Error updating debug info: {e}")
    
    def on_level_changed(self, level_name):
        """
        Handle log level change
        
        Args:
            level_name: New level name
        """
        # Clear and refresh
        self.log_text.clear()
    
    def on_module_changed(self, module_name):
        """
        Handle module filter change
        
        Args:
            module_name: New module filter
        """
        # Clear and refresh
        self.log_text.clear()
    
    def on_clear_clicked(self):
        """Handle clear button click"""
        self.log_text.clear()
    
    def on_save_clicked(self):
        """Handle save button click"""
        # Open file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Logs",
            "",
            "Log Files (*.log);;Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                # Save logs
                with open(file_path, 'w') as f:
                    f.write(self.log_text.toPlainText())
                
                logger.info(f"Logs saved to: {file_path}")
            
            except Exception as e:
                logger.error(f"Failed to save logs: {e}")