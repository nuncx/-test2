"""
Teleport settings panel for RSPS Color Bot v3
"""
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal

from ...core.config import Coordinate
from ..components.screen_picker import PointPickerDialog, ZoomPointPickerDialog
from ...core.modules.teleport import TeleportLocation

# Get module logger
logger = logging.getLogger('rspsbot.gui.panels.teleport_panel')

class CoordinateSelector(QWidget):
    """
    Widget for selecting coordinates on screen
    """
    
    coordinateSelected = pyqtSignal(int, int)
    
    def __init__(self, parent=None, config_manager=None, bot_controller=None):
        """
        Initialize the coordinate selector
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._config = config_manager
        self._controller = bot_controller
        # Initialize UI
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI components"""
        # Main layout
        main_layout = QHBoxLayout(self)
        
        # X coordinate
        main_layout.addWidget(QLabel("X:"))
        
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 9999)
        self.x_spin.valueChanged.connect(self.on_coordinate_changed)
        main_layout.addWidget(self.x_spin)
        
        # Y coordinate
        main_layout.addWidget(QLabel("Y:"))
        
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 9999)
        self.y_spin.valueChanged.connect(self.on_coordinate_changed)
        main_layout.addWidget(self.y_spin)

        # Buttons
        btns = QVBoxLayout()
        self.select_button = QPushButton("Select")
        self.select_button.setToolTip("Pick coordinates from a zoomable screenshot")
        self.select_button.clicked.connect(self.on_select_clicked)
        btns.addWidget(self.select_button)

        self.test_button = QPushButton("Test Click")
        self.test_button.setToolTip("Move and click at the selected coordinate")
        self.test_button.clicked.connect(self.on_test_click)
        btns.addWidget(self.test_button)

        main_layout.addLayout(btns)
    
    def on_coordinate_changed(self):
        """Handle coordinate change"""
        x = self.x_spin.value()
        y = self.y_spin.value()
        self.coordinateSelected.emit(x, y)
    
    def on_select_clicked(self):
        """Handle select button click using zoomable picker"""
        try:
            dialog = ZoomPointPickerDialog(self._config, self)
            if dialog.exec_() == dialog.Accepted and dialog.selected_point:
                x, y = dialog.selected_point
                self.set_coordinate(x, y)
        except Exception as e:
            logger.error(f"Coordinate select error: {e}")

    def on_test_click(self):
        """Test click at selected coordinate using MouseController if available."""
        x, y = self.get_coordinate()
        if x <= 0 and y <= 0:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Test Click", "Please select a coordinate first.")
            return
        try:
            controller = self._controller
            if controller and getattr(controller, 'action_manager', None):
                mc = controller.action_manager.mouse_controller
                if mc:
                    ok = mc.move_and_click(x, y)
                    if not ok:
                        logger.warning("MouseController click failed")
                    return
            # Fallback: use pyautogui directly
            try:
                import pyautogui
                pyautogui.moveTo(x, y, duration=0.1)
                pyautogui.click()
            except Exception as e:
                logger.error(f"Fallback click error: {e}")
        except Exception as e:
            logger.error(f"Test click error: {e}")
    
    def set_coordinate(self, x: int, y: int):
        """Set the coordinate values"""
        self.x_spin.setValue(x)
        self.y_spin.setValue(y)
    
    def get_coordinate(self) -> tuple:
        """Get the coordinate values"""
        return (self.x_spin.value(), self.y_spin.value())

class TeleportLocationDialog(QWidget):
    """
    Dialog for adding or editing teleport locations
    """
    
    def __init__(self, parent=None, location=None):
        """
        Initialize the teleport location dialog
        
        Args:
            parent: Parent widget
            location: Teleport location to edit (None for new location)
        """
        super().__init__(parent)
        self.location = location
        self.setWindowTitle("Teleport Location")
        self.setMinimumWidth(400)
        
        # Initialize UI
        self.init_ui()
        
        # Load location data if editing
        if location:
            self.load_location(location)
    
    def init_ui(self):
        """Initialize the UI components"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        
        main_layout.addLayout(name_layout)
        
        # Teleport type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Coordinate", "Hotkey"])
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        type_layout.addWidget(self.type_combo)
        
        main_layout.addLayout(type_layout)
        
        # Coordinate
        self.coordinate_group = QGroupBox("Coordinate")
        coordinate_layout = QVBoxLayout(self.coordinate_group)
        
        self.coordinate_selector = CoordinateSelector()
        coordinate_layout.addWidget(self.coordinate_selector)
        
        main_layout.addWidget(self.coordinate_group)
        
        # Hotkey
        self.hotkey_group = QGroupBox("Hotkey")
        hotkey_layout = QHBoxLayout(self.hotkey_group)
        
        hotkey_layout.addWidget(QLabel("Hotkey:"))
        
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setPlaceholderText("e.g., ctrl+h, alt+1, f1")
        hotkey_layout.addWidget(self.hotkey_edit)
        
        main_layout.addWidget(self.hotkey_group)
        
        # Cooldown
        cooldown_layout = QHBoxLayout()
        cooldown_layout.addWidget(QLabel("Cooldown:"))
        
        self.cooldown_spin = QDoubleSpinBox()
        self.cooldown_spin.setRange(0.1, 60.0)
        self.cooldown_spin.setValue(5.0)
        self.cooldown_spin.setSuffix(" s")
        cooldown_layout.addWidget(self.cooldown_spin)
        
        main_layout.addLayout(cooldown_layout)
        
        # Emergency teleport
        self.emergency_checkbox = QCheckBox("Emergency Teleport")
        main_layout.addWidget(self.emergency_checkbox)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.on_save_clicked)
        buttons_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.on_cancel_clicked)
        buttons_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(buttons_layout)
        
        # Set initial state
        self.on_type_changed(0)
    
    def on_type_changed(self, index):
        """Handle teleport type change"""
        if index == 0:  # Coordinate
            self.coordinate_group.setVisible(True)
            self.hotkey_group.setVisible(False)
        else:  # Hotkey
            self.coordinate_group.setVisible(False)
            self.hotkey_group.setVisible(True)
    
    def load_location(self, location):
        """Load teleport location data"""
        self.name_edit.setText(location.name)
        
        if location.hotkey:
            self.type_combo.setCurrentIndex(1)  # Hotkey
            self.hotkey_edit.setText(location.hotkey)
        else:
            self.type_combo.setCurrentIndex(0)  # Coordinate
            if location.coordinate:
                self.coordinate_selector.set_coordinate(
                    location.coordinate.x,
                    location.coordinate.y
                )
        
        self.cooldown_spin.setValue(location.cooldown)
        self.emergency_checkbox.setChecked(location.is_emergency)
    
    def get_location_data(self):
        """Get teleport location data"""
        name = self.name_edit.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Warning", "Name cannot be empty")
            return None
        
        is_hotkey = self.type_combo.currentIndex() == 1
        
        if is_hotkey:
            hotkey = self.hotkey_edit.text().strip()
            coordinate = None
            
            if not hotkey:
                QMessageBox.warning(self, "Warning", "Hotkey cannot be empty")
                return None
        else:
            hotkey = None
            x, y = self.coordinate_selector.get_coordinate()
            coordinate = Coordinate(x, y, name)
        
        cooldown = self.cooldown_spin.value()
        is_emergency = self.emergency_checkbox.isChecked()
        
        return {
            "name": name,
            "coordinate": coordinate,
            "hotkey": hotkey,
            "cooldown": cooldown,
            "is_emergency": is_emergency
        }
    
    def on_save_clicked(self):
        """Handle save button click"""
        data = self.get_location_data()
        
        if data:
            self.accept()
    
    def on_cancel_clicked(self):
        """Handle cancel button click"""
        self.reject()
    
    def accept(self):
        """Accept dialog"""
        self.result = True
        self.close()
    
    def reject(self):
        """Reject dialog"""
        self.result = False
        self.close()

class TeleportPanel(QWidget):
    """
    Panel for teleport settings
    """
    
    def __init__(self, config_manager, bot_controller):
        """
        Initialize the teleport panel
        
        Args:
            config_manager: Configuration manager
            bot_controller: Bot controller
        """
        super().__init__()
        self.config_manager = config_manager
        self.bot_controller = bot_controller
        
        # Initialize UI
        self.init_ui()
        
        # Load teleport locations
        self.load_teleport_locations()
    
    def init_ui(self):
        """Initialize the UI components"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Emergency teleport group
        emergency_group = QGroupBox("Emergency Teleport")
        emergency_layout = QHBoxLayout(emergency_group)
        
        emergency_layout.addWidget(QLabel("Hotkey:"))
        
        self.emergency_hotkey_edit = QLineEdit()
        self.emergency_hotkey_edit.setText(self.config_manager.get('emergency_teleport_hotkey', 'ctrl+h'))
        self.emergency_hotkey_edit.textChanged.connect(self.on_emergency_hotkey_changed)
        emergency_layout.addWidget(self.emergency_hotkey_edit)
        
        self.test_emergency_button = QPushButton("Test")
        self.test_emergency_button.clicked.connect(self.on_test_emergency_clicked)
        emergency_layout.addWidget(self.test_emergency_button)
        
        main_layout.addWidget(emergency_group)
        
        # Teleport locations group
        locations_group = QGroupBox("Teleport Locations")
        locations_layout = QVBoxLayout(locations_group)
        
        # Teleport locations table
        self.locations_table = QTableWidget()
        self.locations_table.setColumnCount(5)
        self.locations_table.setHorizontalHeaderLabels(["Name", "Type", "Value", "Cooldown", "Emergency"])
        self.locations_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.locations_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.locations_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.locations_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.locations_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.locations_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.locations_table.setSelectionMode(QTableWidget.SingleSelection)
        self.locations_table.setEditTriggers(QTableWidget.NoEditTriggers)
        locations_layout.addWidget(self.locations_table)
        
        # Teleport locations buttons
        buttons_layout = QHBoxLayout()
        
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.on_add_clicked)
        buttons_layout.addWidget(self.add_button)
        
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self.on_edit_clicked)
        buttons_layout.addWidget(self.edit_button)
        
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.on_remove_clicked)
        buttons_layout.addWidget(self.remove_button)
        
        self.test_button = QPushButton("Test")
        self.test_button.clicked.connect(self.on_test_clicked)
        buttons_layout.addWidget(self.test_button)
        
        # Quick-use button
        self.use_now_button = QPushButton("Use Now")
        self.use_now_button.setToolTip("Immediately trigger the selected teleport")
        self.use_now_button.clicked.connect(self.on_use_now_clicked)
        buttons_layout.addWidget(self.use_now_button)
        
        locations_layout.addLayout(buttons_layout)
        
        main_layout.addWidget(locations_group)
        
        # Add stretch to push everything to the top
        main_layout.addStretch()
        
        # Update button states
        self.update_button_states()
    
    def load_teleport_locations(self):
        """Load teleport locations from config"""
        teleport_locations_data = self.config_manager.get('teleport_locations', [])
        
        # Clear table
        self.locations_table.setRowCount(0)
        
        # Add locations to table
        for i, location_data in enumerate(teleport_locations_data):
            try:
                # Create location object
                location = TeleportLocation.from_dict(location_data)
                
                # Add row
                self.locations_table.insertRow(i)
                
                # Name
                self.locations_table.setItem(i, 0, QTableWidgetItem(location.name))
                
                # Type
                type_text = "Hotkey" if location.hotkey else "Coordinate"
                self.locations_table.setItem(i, 1, QTableWidgetItem(type_text))
                
                # Value
                if location.hotkey:
                    value_text = location.hotkey
                elif location.coordinate:
                    value_text = f"{location.coordinate.x}, {location.coordinate.y}"
                else:
                    value_text = "N/A"
                
                self.locations_table.setItem(i, 2, QTableWidgetItem(value_text))
                
                # Cooldown
                cooldown_text = f"{location.cooldown:.1f}s"
                self.locations_table.setItem(i, 3, QTableWidgetItem(cooldown_text))
                
                # Emergency
                emergency_text = "Yes" if location.is_emergency else "No"
                self.locations_table.setItem(i, 4, QTableWidgetItem(emergency_text))
            
            except Exception as e:
                logger.error(f"Error loading teleport location: {e}")
        
        # Update button states
        self.update_button_states()
    
    def update_button_states(self):
        """Update button states based on selection"""
        has_selection = self.locations_table.currentRow() >= 0
        enabled_teleport = self.config_manager.get('enable_teleport', True)
        
        self.edit_button.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection)
        self.test_button.setEnabled(has_selection)
        self.use_now_button.setEnabled(has_selection and enabled_teleport and getattr(self.bot_controller, 'teleport_manager', None) is not None)
    
    def on_emergency_hotkey_changed(self, text):
        """Handle emergency hotkey change"""
        self.config_manager.set('emergency_teleport_hotkey', text)
    
    def on_test_emergency_clicked(self):
        """Handle test emergency button click"""
        hotkey = self.emergency_hotkey_edit.text().strip()
        
        if not hotkey:
            QMessageBox.warning(self, "Warning", "Emergency hotkey cannot be empty")
            return
        
        QMessageBox.information(
            self,
            "Test Emergency Teleport",
            f"Emergency teleport hotkey '{hotkey}' will be used.\n\n"
            "Note: This is just a test. The actual teleport will not be executed."
        )
    
    def on_add_clicked(self):
        """Handle add button click"""
        dialog = TeleportLocationDialog(self)
        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.show()
        
        # Wait for dialog to close
        while dialog.isVisible():
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()
        
        # Check result
        if hasattr(dialog, 'result') and dialog.result:
            data = dialog.get_location_data()
            
            if data:
                # Add to config
                teleport_locations = self.config_manager.get('teleport_locations', [])
                
                # Check if name already exists
                for location in teleport_locations:
                    if location.get('name') == data['name']:
                        QMessageBox.warning(
                            self,
                            "Warning",
                            f"Teleport location '{data['name']}' already exists"
                        )
                        return
                
                # Convert coordinate to dict if present
                if data['coordinate']:
                    data['coordinate'] = data['coordinate'].to_dict()
                
                # Add to list
                teleport_locations.append(data)
                
                # Save to config
                self.config_manager.set('teleport_locations', teleport_locations)
                
                # Reload locations
                self.load_teleport_locations()
    
    def on_edit_clicked(self):
        """Handle edit button click"""
        row = self.locations_table.currentRow()
        
        if row < 0:
            return
        
        # Get location data
        teleport_locations = self.config_manager.get('teleport_locations', [])
        
        if row >= len(teleport_locations):
            return
        
        location_data = teleport_locations[row]
        location = TeleportLocation.from_dict(location_data)
        
        # Open dialog
        dialog = TeleportLocationDialog(self, location)
        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.show()
        
        # Wait for dialog to close
        while dialog.isVisible():
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()
        
        # Check result
        if hasattr(dialog, 'result') and dialog.result:
            data = dialog.get_location_data()
            
            if data:
                # Check if name already exists and is not the same as the original
                if data['name'] != location.name:
                    for loc in teleport_locations:
                        if loc.get('name') == data['name']:
                            QMessageBox.warning(
                                self,
                                "Warning",
                                f"Teleport location '{data['name']}' already exists"
                            )
                            return
                
                # Convert coordinate to dict if present
                if data['coordinate']:
                    data['coordinate'] = data['coordinate'].to_dict()
                
                # Update location
                teleport_locations[row] = data
                
                # Save to config
                self.config_manager.set('teleport_locations', teleport_locations)
                
                # Reload locations
                self.load_teleport_locations()
    
    def on_remove_clicked(self):
        """Handle remove button click"""
        row = self.locations_table.currentRow()
        
        if row < 0:
            return
        
        # Get location name
        name = self.locations_table.item(row, 0).text()
        
        # Confirm removal
        reply = QMessageBox.question(
            self,
            "Remove Teleport Location",
            f"Are you sure you want to remove teleport location '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Remove location
        teleport_locations = self.config_manager.get('teleport_locations', [])
        
        if row < len(teleport_locations):
            del teleport_locations[row]
            
            # Save to config
            self.config_manager.set('teleport_locations', teleport_locations)
            
            # Reload locations
            self.load_teleport_locations()
    
    def on_test_clicked(self):
        """Handle test button click"""
        row = self.locations_table.currentRow()
        
        if row < 0:
            return
        
        # Get location name
        name = self.locations_table.item(row, 0).text()
        
        QMessageBox.information(
            self,
            "Test Teleport",
            f"Teleport to '{name}' will be executed.\n\n"
            "Note: This is just a test. The actual teleport will not be executed."
        )

    def on_use_now_clicked(self):
        """Immediately execute the selected teleport via TeleportManager"""
        row = self.locations_table.currentRow()
        if row < 0:
            return
        manager = getattr(self.bot_controller, 'teleport_manager', None)
        if manager is None:
            QMessageBox.warning(self, "Unavailable", "Teleport manager is not available.")
            return
        name = self.locations_table.item(row, 0).text()
        ok = manager.teleport_to(name)
        if not ok:
            remaining = 0.0
            loc = manager.get_teleport_location(name)
            if loc:
                remaining = loc.get_cooldown_remaining()
            QMessageBox.warning(self, "Teleport Failed", f"Could not teleport to '{name}'. Cooldown remaining: {remaining:.1f}s")
        else:
            QMessageBox.information(self, "Teleport", f"Teleported to '{name}'.")