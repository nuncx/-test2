"""
Advanced ROI selector component for RSPS Color Bot v3
"""
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QFrame, QSizePolicy, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QRect
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush

from ...core.config import ROI
from ..components.screen_picker import ZoomRoiPickerDialog
from ..components.tooltip_helper import TooltipHelper

# Get module logger
logger = logging.getLogger('rspsbot.gui.components.advanced_roi_selector')

class ROIPreview(QFrame):
    """
    Widget for displaying a ROI preview
    """
    
    def __init__(self, parent=None):
        """
        Initialize the ROI preview
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setMinimumSize(100, 80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        
        self.roi = None
        self.screen_size = (1920, 1080)  # Default screen size
    
    def set_roi(self, roi):
        """
        Set the ROI to display
        
        Args:
            roi: ROI object
        """
        self.roi = roi
        self.update()
    
    def set_screen_size(self, width, height):
        """
        Set the screen size for scaling
        
        Args:
            width: Screen width
            height: Screen height
        """
        self.screen_size = (width, height)
        self.update()
    
    def paintEvent(self, event):
        """
        Paint the ROI preview
        
        Args:
            event: Paint event
        """
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), QColor(240, 240, 240))
        
        # Draw screen outline
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawRect(self.rect())
        
        # Draw ROI if available
        if self.roi:
            # Calculate scaled position
            scale_x = self.width() / self.screen_size[0]
            scale_y = self.height() / self.screen_size[1]
            
            x = int(self.roi.left * scale_x)
            y = int(self.roi.top * scale_y)
            width = int(self.roi.width * scale_x)
            height = int(self.roi.height * scale_y)
            
            # Draw ROI rectangle
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.setBrush(QBrush(QColor(255, 0, 0, 50)))
            painter.drawRect(x, y, width, height)
            
            # Draw ROI coordinates
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.drawText(
                x + 5, y + 15,
                f"({self.roi.left}, {self.roi.top}) {self.roi.width}x{self.roi.height}"
            )

class AdvancedROISelector(QWidget):
    """
    Advanced ROI selector widget with preview and screenshot picker
    """
    
    roiChanged = pyqtSignal(ROI)
    
    def __init__(self, config_manager=None, parent=None, title="Region of Interest"):
        """
        Initialize the ROI selector
        
        Args:
            config_manager: Configuration manager
            parent: Parent widget
            title: Title for the group box
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.title = title
        
        # Initialize UI
        self.init_ui()
        
        # Add tooltips
        self.add_tooltips()
        
        # Dialog compatibility flags
        self._accepted = False
    
    # Provide dialog-like constants
    Accepted = 1
    Rejected = 0

    def exec_(self):  # noqa: D401
        """Provide a dialog-like exec_ interface.
        Since this widget isn't a QDialog, we emulate a simple blocking modal by creating a transient
        QDialog container with this widget embedded. This preserves existing code that expects
        picker.exec_() returning Accepted/Rejected.
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout
        dlg = QDialog(parent=self.parent())
        dlg.setWindowTitle(self.title)
        layout = QVBoxLayout(dlg)
        # Reparent self into dialog
        self.setParent(dlg)
        layout.addWidget(self)
        # Add OK/Cancel buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        def on_ok():
            self._accepted = True
            dlg.accept()
        def on_cancel():
            self._accepted = False
            dlg.reject()
        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(on_cancel)
        res = dlg.exec_()
        return AdvancedROISelector.Accepted if (res == QDialog.Accepted and self._accepted) else AdvancedROISelector.Rejected
    
    def init_ui(self):
        """Initialize the UI components"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Group box
        group_box = QGroupBox(self.title)
        group_layout = QVBoxLayout(group_box)
        
        # ROI preview
        self.roi_preview = ROIPreview()
        group_layout.addWidget(self.roi_preview)
        
        # Position controls
        position_group = QFrame()
        position_layout = QHBoxLayout(position_group)
        position_layout.setContentsMargins(0, 0, 0, 0)
        
        # Left
        position_layout.addWidget(QLabel("Left:"))
        self.left_spin = QSpinBox()
        self.left_spin.setRange(0, 9999)
        self.left_spin.valueChanged.connect(self.on_roi_changed)
        position_layout.addWidget(self.left_spin)
        
        # Top
        position_layout.addWidget(QLabel("Top:"))
        self.top_spin = QSpinBox()
        self.top_spin.setRange(0, 9999)
        self.top_spin.valueChanged.connect(self.on_roi_changed)
        position_layout.addWidget(self.top_spin)
        
        group_layout.addWidget(position_group)
        
        # Size controls
        size_group = QFrame()
        size_layout = QHBoxLayout(size_group)
        size_layout.setContentsMargins(0, 0, 0, 0)
        
        # Width
        size_layout.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 9999)
        self.width_spin.setValue(100)
        self.width_spin.valueChanged.connect(self.on_roi_changed)
        size_layout.addWidget(self.width_spin)
        
        # Height
        size_layout.addWidget(QLabel("Height:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 9999)
        self.height_spin.setValue(100)
        self.height_spin.valueChanged.connect(self.on_roi_changed)
        size_layout.addWidget(self.height_spin)
        
        group_layout.addWidget(size_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.select_button = QPushButton("Select from Screen")
        self.select_button.clicked.connect(self.on_select_clicked)
        buttons_layout.addWidget(self.select_button)
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.on_clear_clicked)
        buttons_layout.addWidget(self.clear_button)
        
        group_layout.addLayout(buttons_layout)
        
        main_layout.addWidget(group_box)
        
        # Set initial ROI
        self.set_roi(ROI(0, 0, 100, 100))
    
    def add_tooltips(self):
        """Add tooltips to widgets"""
        TooltipHelper.add_tooltip(self.left_spin, "Left coordinate of the region (X position)")
        TooltipHelper.add_tooltip(self.top_spin, "Top coordinate of the region (Y position)")
        TooltipHelper.add_tooltip(self.width_spin, "Width of the region in pixels")
        TooltipHelper.add_tooltip(self.height_spin, "Height of the region in pixels")
        TooltipHelper.add_tooltip(self.select_button, "Select a region directly from your screen")
        TooltipHelper.add_tooltip(self.clear_button, "Clear the current region selection")
        TooltipHelper.add_tooltip(self.roi_preview, "Preview of the selected region")
    
    def on_roi_changed(self):
        """Handle ROI value change"""
        # Preserve existing mode if we have a current ROI with mode, default to 'absolute'
        current_mode = getattr(self.roi_preview.roi, 'mode', 'absolute') if getattr(self.roi_preview, 'roi', None) else 'absolute'
        roi = ROI(
            left=self.left_spin.value(),
            top=self.top_spin.value(),
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            mode=current_mode
        )
        
        # Update preview
        self.roi_preview.set_roi(roi)
        
        # Emit signal
        self.roiChanged.emit(roi)
    
    def on_select_clicked(self):
        """Handle select button click"""
        if self.config_manager:
            dialog = ZoomRoiPickerDialog(self.config_manager, self)
            if dialog.exec_() == dialog.Accepted and (dialog.result_rect is not None) and (not dialog.result_rect.isNull()):
                rect = dialog.result_rect
                # Store ROI relative to focused window so it remains valid if the window moves
                self.set_roi(ROI(
                    left=rect.left(),
                    top=rect.top(),
                    width=rect.width(),
                    height=rect.height(),
                    mode='relative'
                ))
    
    def on_clear_clicked(self):
        """Handle clear button click"""
        self.set_roi(ROI(0, 0, 100, 100, mode='absolute'))
    
    def set_roi(self, roi):
        """
        Set the ROI
        
        Args:
            roi: ROI object
        """
        if roi:
            # Block signals to prevent multiple emissions
            self.left_spin.blockSignals(True)
            self.top_spin.blockSignals(True)
            self.width_spin.blockSignals(True)
            self.height_spin.blockSignals(True)
            
            self.left_spin.setValue(roi.left)
            self.top_spin.setValue(roi.top)
            self.width_spin.setValue(roi.width)
            self.height_spin.setValue(roi.height)
            
            # Unblock signals
            self.left_spin.blockSignals(False)
            self.top_spin.blockSignals(False)
            self.width_spin.blockSignals(False)
            self.height_spin.blockSignals(False)
            
            # Update preview
            self.roi_preview.set_roi(roi)
            
            # Emit signal
            self.roiChanged.emit(roi)
    
    def get_roi(self):
        """
        Get the current ROI
        
        Returns:
            ROI: Current ROI
        """
        # Keep current mode if known
        current_mode = getattr(self.roi_preview.roi, 'mode', 'absolute') if getattr(self.roi_preview, 'roi', None) else 'absolute'
        return ROI(
            left=self.left_spin.value(),
            top=self.top_spin.value(),
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            mode=current_mode
        )