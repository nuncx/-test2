"""
Potion settings panel for RSPS Color Bot v3
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
from ...core.modules.potion import Potion, PotionType
from .teleport_panel import CoordinateSelector

# Get module logger
logger = logging.getLogger('rspsbot.gui.panels.potion_panel')

class PotionDialog(QWidget):
    """
    Dialog for adding or editing potions
    """
    
    def __init__(self, parent=None, potion=None):
        """
        Initialize the potion dialog
        
        Args:
            parent: Parent widget
            potion: Potion to edit (None for new potion)
        """
        super().__init__(parent)
        self.potion = potion
        self.setWindowTitle("Potion")
        self.setMinimumWidth(400)
        
        # Initialize UI
        self.init_ui()
        
        # Load potion data if editing
        if potion:
            self.load_potion(potion)
    
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
        
        # Potion type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        
        self.type_combo = QComboBox()
        for potion_type in PotionType.get_all_types():
            self.type_combo.addItem(PotionType.get_display_name(potion_type), potion_type)
        type_layout.addWidget(self.type_combo)
        
        main_layout.addLayout(type_layout)
        
        # Use method
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Use Method:"))
        
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Coordinate", "Hotkey"])
        self.method_combo.currentIndexChanged.connect(self.on_method_changed)
        method_layout.addWidget(self.method_combo)
        
        main_layout.addLayout(method_layout)
        
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
        self.cooldown_spin.setRange(0.1, 900.0)
        self.cooldown_spin.setDecimals(2)
        self.cooldown_spin.setSingleStep(0.1)
        self.cooldown_spin.setValue(30.0)
        self.cooldown_spin.setSuffix(" s")
        self.cooldown_spin.setToolTip("Minimum seconds between uses of this potion.")
        cooldown_layout.addWidget(self.cooldown_spin)
        
        main_layout.addLayout(cooldown_layout)
        
        # Duration
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Duration:"))

        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.0, 1800.0)
        self.duration_spin.setDecimals(2)
        self.duration_spin.setSingleStep(0.1)
        self.duration_spin.setValue(0.0)
        self.duration_spin.setSuffix(" s")
        self.duration_spin.setSpecialValueText("Instant")
        duration_layout.addWidget(self.duration_spin)
        
        main_layout.addLayout(duration_layout)
        
        # Auto-use settings
        auto_group = QGroupBox("Auto-Use Settings")
        auto_layout = QVBoxLayout(auto_group)
        
        # Auto-use checkbox
        self.auto_use_checkbox = QCheckBox("Auto-Use Potion")
        self.auto_use_checkbox.toggled.connect(self.on_auto_use_toggled)
        auto_layout.addWidget(self.auto_use_checkbox)
        
        # Threshold
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("Threshold:"))
        
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(0, 99)
        self.threshold_spin.setValue(0)
        self.threshold_spin.setEnabled(False)
        threshold_layout.addWidget(self.threshold_spin)
        
        auto_layout.addLayout(threshold_layout)
        
        main_layout.addWidget(auto_group)
        
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
        self.on_method_changed(0)
    
    def on_method_changed(self, index):
        """Handle use method change"""
        if index == 0:  # Coordinate
            self.coordinate_group.setVisible(True)
            self.hotkey_group.setVisible(False)
        else:  # Hotkey
            self.coordinate_group.setVisible(False)
            self.hotkey_group.setVisible(True)
    
    def on_auto_use_toggled(self, checked):
        """Handle auto-use checkbox toggle"""
        self.threshold_spin.setEnabled(checked)
    
    def load_potion(self, potion):
        """Load potion data"""
        self.name_edit.setText(potion.name)
        
        # Set potion type
        index = self.type_combo.findData(potion.potion_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        
        # Set use method
        if potion.hotkey:
            self.method_combo.setCurrentIndex(1)  # Hotkey
            self.hotkey_edit.setText(potion.hotkey)
        else:
            self.method_combo.setCurrentIndex(0)  # Coordinate
            if potion.coordinate:
                self.coordinate_selector.set_coordinate(
                    potion.coordinate.x,
                    potion.coordinate.y
                )
        
        # Set other values
        self.cooldown_spin.setValue(potion.cooldown)
        self.duration_spin.setValue(potion.duration)
        self.auto_use_checkbox.setChecked(potion.auto_use)
        self.threshold_spin.setValue(potion.threshold)
        self.threshold_spin.setEnabled(potion.auto_use)
    
    def get_potion_data(self):
        """Get potion data"""
        name = self.name_edit.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Warning", "Name cannot be empty")
            return None
        
        potion_type = self.type_combo.currentData()
        is_hotkey = self.method_combo.currentIndex() == 1
        
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
        duration = self.duration_spin.value()
        auto_use = self.auto_use_checkbox.isChecked()
        threshold = self.threshold_spin.value() if auto_use else 0
        
        return {
            "name": name,
            "potion_type": potion_type,
            "coordinate": coordinate,
            "hotkey": hotkey,
            "cooldown": cooldown,
            "duration": duration,
            "threshold": threshold,
            "auto_use": auto_use
        }
    
    def on_save_clicked(self):
        """Handle save button click"""
        data = self.get_potion_data()
        
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

class PotionPanel(QWidget):
    """
    Panel for potion settings
    """
    
    def __init__(self, config_manager, bot_controller):
        """
        Initialize the potion panel
        
        Args:
            config_manager: Configuration manager
            bot_controller: Bot controller
        """
        super().__init__()
        self.config_manager = config_manager
        self.bot_controller = bot_controller
        
        # Initialize UI
        self.init_ui()
        
        # Load potions
        self.load_potions()
    
    def init_ui(self):
        """Initialize the UI components"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Potions group
        potions_group = QGroupBox("Potions")
        potions_layout = QVBoxLayout(potions_group)
        
        # Potions table
        self.potions_table = QTableWidget()
        self.potions_table.setColumnCount(7)
        self.potions_table.setHorizontalHeaderLabels(["Name", "Type", "Method", "Cooldown", "Duration", "Auto-Use", "Threshold"])
        self.potions_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.potions_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.potions_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.potions_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.potions_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.potions_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.potions_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.potions_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.potions_table.setSelectionMode(QTableWidget.SingleSelection)
        self.potions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.potions_table.itemSelectionChanged.connect(self.on_selection_changed)
        potions_layout.addWidget(self.potions_table)
        
        # Buttons
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
        self.use_now_button.setToolTip("Immediately use the selected potion")
        self.use_now_button.clicked.connect(self.on_use_now_clicked)
        buttons_layout.addWidget(self.use_now_button)
        
        potions_layout.addLayout(buttons_layout)
        
        main_layout.addWidget(potions_group)
        
        # Auto-use settings group
        auto_group = QGroupBox("Auto-Use Settings")
        auto_layout = QVBoxLayout(auto_group)
        
        # Health potions
        health_layout = QHBoxLayout()
        health_layout.addWidget(QLabel("Health Potion Threshold:"))
        
        self.health_threshold_spin = QSpinBox()
        self.health_threshold_spin.setRange(0, 99)
        self.health_threshold_spin.setValue(self.config_manager.get('health_potion_threshold', 50))
        self.health_threshold_spin.valueChanged.connect(self.on_health_threshold_changed)
        health_layout.addWidget(self.health_threshold_spin)
        
        health_layout.addWidget(QLabel("HP"))
        health_layout.addStretch()
        
        auto_layout.addLayout(health_layout)
        
        # Prayer potions
        prayer_layout = QHBoxLayout()
        prayer_layout.addWidget(QLabel("Prayer Potion Threshold:"))
        
        self.prayer_threshold_spin = QSpinBox()
        self.prayer_threshold_spin.setRange(0, 99)
        self.prayer_threshold_spin.setValue(self.config_manager.get('prayer_potion_threshold', 20))
        self.prayer_threshold_spin.valueChanged.connect(self.on_prayer_threshold_changed)
        prayer_layout.addWidget(self.prayer_threshold_spin)
        
        prayer_layout.addWidget(QLabel("Prayer Points"))
        prayer_layout.addStretch()
        
        auto_layout.addLayout(prayer_layout)
        
        # Combat potions
        combat_layout = QHBoxLayout()
        combat_layout.addWidget(QLabel("Combat Potion Interval:"))

        self.combat_interval_spin = QDoubleSpinBox()
        self.combat_interval_spin.setRange(1.0, 3600.0)
        self.combat_interval_spin.setDecimals(1)
        self.combat_interval_spin.setSingleStep(1.0)
        self.combat_interval_spin.setValue(self.config_manager.get('combat_potion_interval', 60.0))
        self.combat_interval_spin.setSuffix(" s")
        self.combat_interval_spin.setToolTip("Seconds between reapplying combat potion buffs.")
        self.combat_interval_spin.valueChanged.connect(self.on_combat_interval_changed)
        combat_layout.addWidget(self.combat_interval_spin)
        
        combat_layout.addStretch()
        
        auto_layout.addLayout(combat_layout)
        
        main_layout.addWidget(auto_group)
        
        # Add stretch to push everything to the top
        main_layout.addStretch()
        
        # Update button states
        self.update_button_states()
    
    def load_potions(self):
        """Load potions from config"""
        potions_data = self.config_manager.get('potions', [])
        
        # Clear table
        self.potions_table.setRowCount(0)
        
        # Add potions to table
        for i, potion_data in enumerate(potions_data):
            try:
                # Create potion object
                potion = Potion.from_dict(potion_data)
                
                # Add row
                self.potions_table.insertRow(i)
                
                # Name
                self.potions_table.setItem(i, 0, QTableWidgetItem(potion.name))
                
                # Type
                type_text = PotionType.get_display_name(potion.potion_type)
                self.potions_table.setItem(i, 1, QTableWidgetItem(type_text))
                
                # Method
                method_text = "Hotkey" if potion.hotkey else "Coordinate"
                self.potions_table.setItem(i, 2, QTableWidgetItem(method_text))
                
                # Cooldown
                cooldown_text = f"{potion.cooldown:.1f}s"
                self.potions_table.setItem(i, 3, QTableWidgetItem(cooldown_text))
                
                # Duration
                if potion.duration > 0:
                    duration_text = f"{potion.duration:.1f}s"
                else:
                    duration_text = "Instant"
                self.potions_table.setItem(i, 4, QTableWidgetItem(duration_text))
                
                # Auto-use
                auto_use_text = "Yes" if potion.auto_use else "No"
                self.potions_table.setItem(i, 5, QTableWidgetItem(auto_use_text))
                
                # Threshold
                threshold_text = str(potion.threshold) if potion.auto_use else "-"
                self.potions_table.setItem(i, 6, QTableWidgetItem(threshold_text))
            
            except Exception as e:
                logger.error(f"Error loading potion: {e}")
        
        # Update button states
        self.update_button_states()
    
    def update_button_states(self):
        """Update button states based on selection"""
        has_selection = self.potions_table.currentRow() >= 0
        enabled_potions = self.config_manager.get('enable_potions', True)
        
        self.edit_button.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection)
        self.test_button.setEnabled(has_selection)
        self.use_now_button.setEnabled(has_selection and enabled_potions and getattr(self.bot_controller, 'potion_manager', None) is not None)
    
    def on_selection_changed(self):
        """Handle selection change"""
        self.update_button_states()
    
    def on_add_clicked(self):
        """Handle add button click"""
        dialog = PotionDialog(self)
        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.show()
        
        # Wait for dialog to close
        while dialog.isVisible():
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()
        
        # Check result
        if hasattr(dialog, 'result') and dialog.result:
            data = dialog.get_potion_data()
            
            if data:
                # Add to config
                potions = self.config_manager.get('potions', [])
                
                # Check if name already exists
                for potion in potions:
                    if potion.get('name') == data['name']:
                        QMessageBox.warning(
                            self,
                            "Warning",
                            f"Potion '{data['name']}' already exists"
                        )
                        return
                
                # Convert coordinate to dict if present
                if data['coordinate']:
                    data['coordinate'] = data['coordinate'].to_dict()
                
                # Add to list
                potions.append(data)
                
                # Save to config
                self.config_manager.set('potions', potions)
                
                # Reload potions
                self.load_potions()
    
    def on_edit_clicked(self):
        """Handle edit button click"""
        row = self.potions_table.currentRow()
        
        if row < 0:
            return
        
        # Get potion data
        potions = self.config_manager.get('potions', [])
        
        if row >= len(potions):
            return
        
        potion_data = potions[row]
        potion = Potion.from_dict(potion_data)
        
        # Open dialog
        dialog = PotionDialog(self, potion)
        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.show()
        
        # Wait for dialog to close
        while dialog.isVisible():
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()
        
        # Check result
        if hasattr(dialog, 'result') and dialog.result:
            data = dialog.get_potion_data()
            
            if data:
                # Check if name already exists and is not the same as the original
                if data['name'] != potion.name:
                    for p in potions:
                        if p.get('name') == data['name']:
                            QMessageBox.warning(
                                self,
                                "Warning",
                                f"Potion '{data['name']}' already exists"
                            )
                            return
                
                # Convert coordinate to dict if present
                if data['coordinate']:
                    data['coordinate'] = data['coordinate'].to_dict()
                
                # Update potion
                potions[row] = data
                
                # Save to config
                self.config_manager.set('potions', potions)
                
                # Reload potions
                self.load_potions()
    
    def on_remove_clicked(self):
        """Handle remove button click"""
        row = self.potions_table.currentRow()
        
        if row < 0:
            return
        
        # Get potion name
        name = self.potions_table.item(row, 0).text()
        
        # Confirm removal
        reply = QMessageBox.question(
            self,
            "Remove Potion",
            f"Are you sure you want to remove potion '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Remove potion
        potions = self.config_manager.get('potions', [])
        
        if row < len(potions):
            del potions[row]
            
            # Save to config
            self.config_manager.set('potions', potions)
            
            # Reload potions
            self.load_potions()
    
    def on_test_clicked(self):
        """Handle test button click"""
        row = self.potions_table.currentRow()
        
        if row < 0:
            return
        
        # Get potion name
        name = self.potions_table.item(row, 0).text()
        
        QMessageBox.information(
            self,
            "Test Potion",
            f"Potion '{name}' will be used.\n\n"
            "Note: This is just a test. The actual potion will not be used."
        )

    def on_use_now_clicked(self):
        """Immediately execute the selected potion via PotionManager"""
        row = self.potions_table.currentRow()
        if row < 0:
            return
        manager = getattr(self.bot_controller, 'potion_manager', None)
        if manager is None:
            QMessageBox.warning(self, "Unavailable", "Potion manager is not available.")
            return
        name = self.potions_table.item(row, 0).text()
        ok = manager.use_potion(name)
        if not ok:
            remaining = 0.0
            p = manager.get_potion(name)
            if p:
                remaining = p.get_cooldown_remaining()
            QMessageBox.warning(self, "Potion Failed", f"Could not use potion '{name}'. Cooldown remaining: {remaining:.1f}s")
        else:
            QMessageBox.information(self, "Potion", f"Used potion '{name}'.")
    
    def on_health_threshold_changed(self, value):
        """Handle health threshold change"""
        self.config_manager.set('health_potion_threshold', value)
    
    def on_prayer_threshold_changed(self, value):
        """Handle prayer threshold change"""
        self.config_manager.set('prayer_potion_threshold', value)
    
    def on_combat_interval_changed(self, value):
        """Handle combat interval change"""
        self.config_manager.set('combat_potion_interval', value)