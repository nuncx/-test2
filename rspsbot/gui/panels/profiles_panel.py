"""
Profiles panel for RSPS Color Bot v3
"""
import logging
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QListWidget, QLineEdit, QMessageBox, QInputDialog,
    QFileDialog
)
from PyQt5.QtCore import Qt

# Get module logger
logger = logging.getLogger('rspsbot.gui.panels.profiles_panel')

class ProfilesPanel(QWidget):
    """
    Panel for managing configuration profiles
    """
    
    def __init__(self, config_manager):
        """
        Initialize the profiles panel
        
        Args:
            config_manager: Configuration manager
        """
        super().__init__()
        self.config_manager = config_manager
        
        # Initialize UI
        self.init_ui()
        
        # Refresh profile list
        self.refresh_profiles()
    
    def init_ui(self):
        """Initialize the UI components"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Profiles group
        profiles_group = QGroupBox("Profiles")
        profiles_layout = QVBoxLayout(profiles_group)
        
        # Profile list
        self.profile_list = QListWidget()
        self.profile_list.setMinimumHeight(200)
        self.profile_list.currentItemChanged.connect(self.on_profile_selected)
        profiles_layout.addWidget(self.profile_list)
        
        # Profile actions
        actions_layout = QHBoxLayout()
        
        self.load_button = QPushButton("Load")
        self.load_button.clicked.connect(self.on_load_clicked)
        actions_layout.addWidget(self.load_button)
        
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.on_save_clicked)
        actions_layout.addWidget(self.save_button)
        
        self.save_as_button = QPushButton("Save As")
        self.save_as_button.clicked.connect(self.on_save_as_clicked)
        actions_layout.addWidget(self.save_as_button)
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.on_delete_clicked)
        actions_layout.addWidget(self.delete_button)
        
        profiles_layout.addLayout(actions_layout)
        
        # Add profiles group to main layout
        main_layout.addWidget(profiles_group)
        
        # Import/Export group
        import_export_group = QGroupBox("Import/Export")
        import_export_layout = QHBoxLayout(import_export_group)
        
        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self.on_import_clicked)
        import_export_layout.addWidget(self.import_button)
        
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.on_export_clicked)
        import_export_layout.addWidget(self.export_button)
        
        # Add import/export group to main layout
        main_layout.addWidget(import_export_group)
        
        # Reset group
        reset_group = QGroupBox("Reset")
        reset_layout = QHBoxLayout(reset_group)
        
        self.reset_button = QPushButton("Reset to Defaults")
        self.reset_button.clicked.connect(self.on_reset_clicked)
        reset_layout.addWidget(self.reset_button)
        
        # Add reset group to main layout
        main_layout.addWidget(reset_group)
        
        # Add stretch to push everything to the top
        main_layout.addStretch()
        
        # Update button states
        self.update_button_states()
    
    def refresh_profiles(self):
        """Refresh the profile list"""
        # Get profiles
        profiles = self.config_manager.list_profiles()
        
        # Clear list
        self.profile_list.clear()
        
        # Add profiles to list
        for profile in profiles:
            # Remove .json extension
            if profile.endswith('.json'):
                profile = profile[:-5]
            
            self.profile_list.addItem(profile)
        
        # Select current profile
        current_profile = self.config_manager.current_profile
        if current_profile:
            # Remove .json extension
            if current_profile.endswith('.json'):
                current_profile = current_profile[:-5]
            
            # Find and select item
            items = self.profile_list.findItems(current_profile, Qt.MatchExactly)
            if items:
                self.profile_list.setCurrentItem(items[0])
        
        # Update button states
        self.update_button_states()
    
    def update_button_states(self):
        """Update button states based on selection"""
        has_selection = self.profile_list.currentItem() is not None
        
        self.load_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        self.export_button.setEnabled(has_selection)
    
    def on_profile_selected(self, current, previous):
        """Handle profile selection change"""
        self.update_button_states()
    
    def on_load_clicked(self):
        """Handle load button click"""
        item = self.profile_list.currentItem()
        if not item:
            return
        
        profile_name = item.text()
        
        # Confirm load
        reply = QMessageBox.question(
            self,
            "Load Profile",
            f"Load profile '{profile_name}'? This will replace the current configuration.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Load profile
            success = self.config_manager.load_profile(profile_name)
            
            if success:
                logger.info(f"Loaded profile: {profile_name}")
                QMessageBox.information(
                    self,
                    "Profile Loaded",
                    f"Profile '{profile_name}' loaded successfully."
                )
            else:
                logger.error(f"Failed to load profile: {profile_name}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to load profile '{profile_name}'."
                )
    
    def on_save_clicked(self):
        """Handle save button click"""
        # If current profile is set, save to it
        if self.config_manager.current_profile:
            profile_name = self.config_manager.current_profile
            
            # Remove .json extension
            if profile_name.endswith('.json'):
                profile_name = profile_name[:-5]
            
            # Confirm save
            reply = QMessageBox.question(
                self,
                "Save Profile",
                f"Save current configuration to profile '{profile_name}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Save profile
                success = self.config_manager.save_profile(profile_name)
                
                if success:
                    logger.info(f"Saved profile: {profile_name}")
                    QMessageBox.information(
                        self,
                        "Profile Saved",
                        f"Profile '{profile_name}' saved successfully."
                    )
                else:
                    logger.error(f"Failed to save profile: {profile_name}")
                    QMessageBox.critical(
                        self,
                        "Error",
                        f"Failed to save profile '{profile_name}'."
                    )
        else:
            # No current profile, use save as
            self.on_save_as_clicked()
    
    def on_save_as_clicked(self):
        """Handle save as button click"""
        # Get profile name
        profile_name, ok = QInputDialog.getText(
            self,
            "Save Profile As",
            "Enter profile name:"
        )
        
        if ok and profile_name:
            # Save profile
            success = self.config_manager.save_profile(profile_name)
            
            if success:
                logger.info(f"Saved profile as: {profile_name}")
                QMessageBox.information(
                    self,
                    "Profile Saved",
                    f"Profile '{profile_name}' saved successfully."
                )
                
                # Refresh profile list
                self.refresh_profiles()
            else:
                logger.error(f"Failed to save profile as: {profile_name}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to save profile '{profile_name}'."
                )
    
    def on_delete_clicked(self):
        """Handle delete button click"""
        item = self.profile_list.currentItem()
        if not item:
            return
        
        profile_name = item.text()
        
        # Confirm delete
        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete profile '{profile_name}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Delete profile
            try:
                # Add .json extension if not present
                if not profile_name.endswith('.json'):
                    profile_name += '.json'
                
                # Delete file
                os.remove(os.path.join(self.config_manager.config_dir, profile_name))
                
                logger.info(f"Deleted profile: {profile_name}")
                QMessageBox.information(
                    self,
                    "Profile Deleted",
                    f"Profile '{profile_name}' deleted successfully."
                )
                
                # Reset current profile if it was deleted
                if self.config_manager.current_profile == profile_name:
                    self.config_manager.current_profile = None
                
                # Refresh profile list
                self.refresh_profiles()
            
            except Exception as e:
                logger.error(f"Failed to delete profile: {profile_name} - {e}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to delete profile '{profile_name}'."
                )
    
    def on_import_clicked(self):
        """Handle import button click"""
        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Profile",
            "",
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                # Get profile name from file name
                profile_name = os.path.basename(file_path)
                
                # Copy file to profiles directory
                import shutil
                shutil.copy(file_path, os.path.join(self.config_manager.config_dir, profile_name))
                
                logger.info(f"Imported profile: {profile_name}")
                QMessageBox.information(
                    self,
                    "Profile Imported",
                    f"Profile '{profile_name}' imported successfully."
                )
                
                # Refresh profile list
                self.refresh_profiles()
            
            except Exception as e:
                logger.error(f"Failed to import profile: {file_path} - {e}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to import profile from '{file_path}'."
                )
    
    def on_export_clicked(self):
        """Handle export button click"""
        item = self.profile_list.currentItem()
        if not item:
            return
        
        profile_name = item.text()
        
        # Add .json extension if not present
        if not profile_name.endswith('.json'):
            profile_name += '.json'
        
        # Open file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Profile",
            profile_name,
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                # Copy file from profiles directory
                import shutil
                shutil.copy(
                    os.path.join(self.config_manager.config_dir, profile_name),
                    file_path
                )
                
                logger.info(f"Exported profile: {profile_name} to {file_path}")
                QMessageBox.information(
                    self,
                    "Profile Exported",
                    f"Profile '{profile_name}' exported successfully."
                )
            
            except Exception as e:
                logger.error(f"Failed to export profile: {profile_name} - {e}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to export profile '{profile_name}'."
                )
    
    def on_reset_clicked(self):
        """Handle reset button click"""
        # Confirm reset
        reply = QMessageBox.question(
            self,
            "Reset to Defaults",
            "Reset all settings to defaults? This will not affect saved profiles.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Reset to defaults
            self.config_manager.reset_to_defaults()
            
            logger.info("Reset configuration to defaults")
            QMessageBox.information(
                self,
                "Reset to Defaults",
                "Configuration reset to defaults successfully."
            )