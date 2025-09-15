"""
Time selector component for RSPS Color Bot v3
"""
import logging
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QSpinBox, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal

# Get module logger
logger = logging.getLogger('rspsbot.gui.components.time_selector')

class TimeSelector(QWidget):
    """
    Enhanced widget for selecting time with various modes:
    - Seconds only
    - Minutes and seconds
    - Hours and minutes
    """
    
    timeChanged = pyqtSignal(float)
    
    # Time selection modes
    MODE_SEC_ONLY = "sec_only"
    MODE_MIN_SEC = "min_sec"
    MODE_HOUR_MIN = "hour_min"
    
    def __init__(self, label="Time:", initial_seconds=0, mode=None, parent=None, tooltip=None):
        """
        Initialize the time selector
        
        Args:
            label: Label text
            initial_seconds: Initial time in seconds
            mode: Time selection mode (sec_only, min_sec, hour_min)
            parent: Parent widget
            tooltip: Tooltip text
        """
        super().__init__(parent)
        self.label_text = label
        self.initial_seconds = initial_seconds
        
        # Set default mode based on initial value if not specified
        if mode is None:
            if initial_seconds < 60:
                self.mode = self.MODE_SEC_ONLY
            elif initial_seconds < 3600:
                self.mode = self.MODE_MIN_SEC
            else:
                self.mode = self.MODE_HOUR_MIN
        else:
            self.mode = mode
        
        # Initialize UI
        self.init_ui()
        
        # Set tooltip if provided
        if tooltip:
            self.setToolTip(tooltip)
        
        # Set initial value
        self.set_time(initial_seconds)
    
    def init_ui(self):
        """Initialize the UI components"""
        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Label
        if self.label_text:
            self.label = QLabel(self.label_text)
            main_layout.addWidget(self.label)
        
        # Create appropriate inputs based on mode
        if self.mode == self.MODE_SEC_ONLY:
            # Seconds only
            self.seconds_spin = QSpinBox()
            self.seconds_spin.setRange(0, 3600)  # Up to 1 hour in seconds
            self.seconds_spin.setSuffix(" s")
            self.seconds_spin.setToolTip("Seconds")
            self.seconds_spin.valueChanged.connect(self.on_time_changed)
            main_layout.addWidget(self.seconds_spin)
            
        elif self.mode == self.MODE_MIN_SEC:
            # Minutes and seconds
            self.minutes_spin = QSpinBox()
            self.minutes_spin.setRange(0, 60)
            self.minutes_spin.setSuffix(" min")
            self.minutes_spin.setToolTip("Minutes")
            self.minutes_spin.valueChanged.connect(self.on_time_changed)
            main_layout.addWidget(self.minutes_spin)
            
            self.seconds_spin = QSpinBox()
            self.seconds_spin.setRange(0, 59)
            self.seconds_spin.setSuffix(" s")
            self.seconds_spin.setToolTip("Seconds")
            self.seconds_spin.valueChanged.connect(self.on_time_changed)
            main_layout.addWidget(self.seconds_spin)
            
        elif self.mode == self.MODE_HOUR_MIN:
            # Hours and minutes
            self.hours_spin = QSpinBox()
            self.hours_spin.setRange(0, 24)
            self.hours_spin.setSuffix(" h")
            self.hours_spin.setToolTip("Hours")
            self.hours_spin.valueChanged.connect(self.on_time_changed)
            main_layout.addWidget(self.hours_spin)
            
            self.minutes_spin = QSpinBox()
            self.minutes_spin.setRange(0, 59)
            self.minutes_spin.setSuffix(" min")
            self.minutes_spin.setToolTip("Minutes")
            self.minutes_spin.valueChanged.connect(self.on_time_changed)
            main_layout.addWidget(self.minutes_spin)
    
    def on_time_changed(self):
        """Handle time change"""
        total_seconds = self.get_time()
        self.timeChanged.emit(total_seconds)
    
    def set_time(self, seconds):
        """
        Set the time value
        
        Args:
            seconds: Time in seconds
        """
        if self.mode == self.MODE_SEC_ONLY:
            # Block signals to prevent multiple emissions
            self.seconds_spin.blockSignals(True)
            self.seconds_spin.setValue(int(seconds))
            self.seconds_spin.blockSignals(False)
            
        elif self.mode == self.MODE_MIN_SEC:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            
            # Block signals to prevent multiple emissions
            self.minutes_spin.blockSignals(True)
            self.seconds_spin.blockSignals(True)
            
            self.minutes_spin.setValue(minutes)
            self.seconds_spin.setValue(secs)
            
            # Unblock signals
            self.minutes_spin.blockSignals(False)
            self.seconds_spin.blockSignals(False)
            
        elif self.mode == self.MODE_HOUR_MIN:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            
            # Block signals to prevent multiple emissions
            self.hours_spin.blockSignals(True)
            self.minutes_spin.blockSignals(True)
            
            self.hours_spin.setValue(hours)
            self.minutes_spin.setValue(minutes)
            
            # Unblock signals
            self.hours_spin.blockSignals(False)
            self.minutes_spin.blockSignals(False)
    
    def get_time(self):
        """
        Get the time value in seconds
        
        Returns:
            float: Time in seconds
        """
        if self.mode == self.MODE_SEC_ONLY:
            return self.seconds_spin.value()
            
        elif self.mode == self.MODE_MIN_SEC:
            return self.minutes_spin.value() * 60 + self.seconds_spin.value()
            
        elif self.mode == self.MODE_HOUR_MIN:
            return self.hours_spin.value() * 3600 + self.minutes_spin.value() * 60