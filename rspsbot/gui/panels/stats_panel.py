"""
Statistics panel for RSPS Color Bot v3
"""
import logging
import time
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTabWidget, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QFileDialog, QSplitter
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QFont

# Import matplotlib for graphs
try:
    import matplotlib
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# Get module logger
logger = logging.getLogger('rspsbot.gui.panels.stats_panel')

class StatsGraph(QWidget):
    """
    Widget for displaying statistics graphs
    """
    
    def __init__(self, parent=None):
        """
        Initialize the stats graph
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Check if matplotlib is available
        if not HAS_MATPLOTLIB:
            self.init_fallback_ui()
            return
        
        # Initialize UI
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI components"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Create figure and canvas
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas)
        
        # Create axes
        self.axes = self.figure.add_subplot(111)
        self.axes.set_title("Monster Kills")
        self.axes.set_xlabel("Time")
        self.axes.set_ylabel("Kills")
        
        # Format x-axis as time
        self.axes.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        
        # Add grid
        self.axes.grid(True)
        
        # Adjust layout
        self.figure.tight_layout()
    
    def init_fallback_ui(self):
        """Initialize fallback UI when matplotlib is not available"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Add message
        label = QLabel(
            "Matplotlib is not installed. Graphs are not available.\n\n"
            "To enable graphs, install matplotlib:\n"
            "pip install matplotlib"
        )
        label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(label)
    
    def update_graph(self, data_type: str, time_series_data: List[tuple]):
        """
        Update the graph with new data
        
        Args:
            data_type: Type of data to display
            time_series_data: List of (timestamp, value) tuples
        """
        if not HAS_MATPLOTLIB or not time_series_data:
            return
        
        # Clear axes
        self.axes.clear()
        
        # Set title and labels based on data type
        if data_type == 'kills':
            self.axes.set_title("Monster Kills")
            self.axes.set_ylabel("Kills")
        elif data_type == 'teleports':
            self.axes.set_title("Teleports Used")
            self.axes.set_ylabel("Teleports")
        elif data_type == 'potions':
            self.axes.set_title("Potions Used")
            self.axes.set_ylabel("Potions")
        elif data_type == 'boosts':
            self.axes.set_title("Boosts Used")
            self.axes.set_ylabel("Boosts")
        elif data_type == 'instances':
            self.axes.set_title("Instances Entered")
            self.axes.set_ylabel("Instances")
        elif data_type == 'aggro':
            self.axes.set_title("Aggro Potions Used")
            self.axes.set_ylabel("Aggro Potions")
        elif data_type == 'errors':
            self.axes.set_title("Errors Occurred")
            self.axes.set_ylabel("Errors")
        
        self.axes.set_xlabel("Time")
        
        # Extract timestamps and values
        timestamps = [datetime.fromtimestamp(ts) for ts, _ in time_series_data]
        values = [val for _, val in time_series_data]
        
        # Plot data
        self.axes.plot(timestamps, values, 'b-')
        
        # Format x-axis as time
        self.axes.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        
        # Add grid
        self.axes.grid(True)
        
        # Adjust layout
        self.figure.tight_layout()
        
        # Redraw canvas
        self.canvas.draw()

class StatsPanel(QWidget):
    """
    Panel for displaying statistics
    """
    
    def __init__(self, config_manager, bot_controller):
        """
        Initialize the stats panel
        
        Args:
            config_manager: Configuration manager
            bot_controller: Bot controller
        """
        super().__init__()
        self.config_manager = config_manager
        self.bot_controller = bot_controller
        
        # Get statistics tracker
        self.stats_tracker = None
        if hasattr(bot_controller, 'stats_tracker'):
            self.stats_tracker = bot_controller.stats_tracker
        
        # Initialize UI
        self.init_ui()
        
        # Set up update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_stats)
        self.update_timer.start(1000)  # Update every second
    
    def init_ui(self):
        """Initialize the UI components"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Create tab widget
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # Current session tab
        session_tab = QWidget()
        tab_widget.addTab(session_tab, "Current Session")
        
        session_layout = QVBoxLayout(session_tab)
        
        # Session stats group
        stats_group = QGroupBox("Session Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        # Stats table
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(2)
        self.stats_table.setHorizontalHeaderLabels(["Statistic", "Value"])
        self.stats_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.stats_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        stats_layout.addWidget(self.stats_table)
        
        session_layout.addWidget(stats_group)
        
        # Graphs group
        graphs_group = QGroupBox("Graphs")
        graphs_layout = QVBoxLayout(graphs_group)
        
        # Graph type selector
        selector_layout = QHBoxLayout()
        
        selector_layout.addWidget(QLabel("Graph Type:"))
        
        self.graph_type_combo = QComboBox()
        self.graph_type_combo.addItems([
            "Monster Kills",
            "Teleports Used",
            "Potions Used",
            "Boosts Used",
            "Instances Entered",
            "Aggro Potions Used",
            "Errors Occurred"
        ])
        self.graph_type_combo.currentIndexChanged.connect(self.on_graph_type_changed)
        selector_layout.addWidget(self.graph_type_combo)
        
        selector_layout.addStretch()
        
        graphs_layout.addLayout(selector_layout)
        
        # Graph widget
        self.graph_widget = StatsGraph()
        graphs_layout.addWidget(self.graph_widget)
        
        session_layout.addWidget(graphs_group)
        
        # History tab
        history_tab = QWidget()
        tab_widget.addTab(history_tab, "Session History")
        
        history_layout = QVBoxLayout(history_tab)
        
        # Session selector
        selector_layout = QHBoxLayout()
        
        selector_layout.addWidget(QLabel("Session:"))
        
        self.session_combo = QComboBox()
        self.session_combo.currentIndexChanged.connect(self.on_session_selected)
        selector_layout.addWidget(self.session_combo)
        
        self.load_button = QPushButton("Load")
        self.load_button.clicked.connect(self.on_load_clicked)
        selector_layout.addWidget(self.load_button)
        
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.on_export_clicked)
        selector_layout.addWidget(self.export_button)
        
        history_layout.addLayout(selector_layout)
        
        # Session details
        details_group = QGroupBox("Session Details")
        details_layout = QVBoxLayout(details_group)
        
        # Details table
        self.details_table = QTableWidget()
        self.details_table.setColumnCount(2)
        self.details_table.setHorizontalHeaderLabels(["Statistic", "Value"])
        self.details_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.details_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.details_table.setEditTriggers(QTableWidget.NoEditTriggers)
        details_layout.addWidget(self.details_table)
        
        history_layout.addWidget(details_group)
        
        # History graph
        history_graph_group = QGroupBox("Session Graph")
        history_graph_layout = QVBoxLayout(history_graph_group)
        
        # Graph type selector
        history_selector_layout = QHBoxLayout()
        
        history_selector_layout.addWidget(QLabel("Graph Type:"))
        
        self.history_graph_type_combo = QComboBox()
        self.history_graph_type_combo.addItems([
            "Monster Kills",
            "Teleports Used",
            "Potions Used",
            "Boosts Used",
            "Instances Entered",
            "Aggro Potions Used",
            "Errors Occurred"
        ])
        self.history_graph_type_combo.currentIndexChanged.connect(self.on_history_graph_type_changed)
        history_selector_layout.addWidget(self.history_graph_type_combo)
        
        history_selector_layout.addStretch()
        
        history_graph_layout.addLayout(history_selector_layout)
        
        # Graph widget
        self.history_graph_widget = StatsGraph()
        history_graph_layout.addWidget(self.history_graph_widget)
        
        history_layout.addWidget(history_graph_group)
        
        # Load session list
        self.load_session_list()
        
        # Initialize stats
        self.update_stats()
    
    def update_stats(self):
        """Update statistics display"""
        if not self.stats_tracker:
            return
        
        # Get current session stats
        stats = self.stats_tracker.get_session_stats()
        
        # Update stats table
        self.stats_table.setRowCount(0)
        
        # Add rows
        self.add_stat_row("Session Active", "Yes" if stats['is_active'] else "No")
        
        # Format start time
        if stats['start_time'] > 0:
            start_time = datetime.fromtimestamp(stats['start_time']).strftime("%Y-%m-%d %H:%M:%S")
        else:
            start_time = "N/A"
        
        self.add_stat_row("Start Time", start_time)
        
        # Format duration
        duration = stats['duration']
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
        
        self.add_stat_row("Duration", duration_str)
        self.add_stat_row("Monster Kills", str(stats['monster_kills']))
        self.add_stat_row("Kills Per Hour", f"{stats['kills_per_hour']:.1f}")
        self.add_stat_row("Teleports Used", str(stats['teleports_used']))
        self.add_stat_row("Potions Used", str(stats['potions_used']))
        self.add_stat_row("Boosts Used", str(stats['boosts_used']))
        self.add_stat_row("Instances Entered", str(stats['instances_entered']))
        self.add_stat_row("Aggro Potions Used", str(stats['aggro_potions_used']))
        self.add_stat_row("Errors Occurred", str(stats['errors_occurred']))
        
        # Update graph if needed
        self.update_current_graph()
    
    def add_stat_row(self, name, value):
        """Add a row to the stats table"""
        row = self.stats_table.rowCount()
        self.stats_table.insertRow(row)
        self.stats_table.setItem(row, 0, QTableWidgetItem(name))
        self.stats_table.setItem(row, 1, QTableWidgetItem(value))
    
    def update_current_graph(self):
        """Update the current session graph"""
        if not self.stats_tracker:
            return
        
        # Get time series data
        time_series_data = self.stats_tracker.get_time_series_data()
        
        # Get selected graph type
        index = self.graph_type_combo.currentIndex()
        data_type = self.get_data_type_from_index(index)
        
        # Update graph
        self.graph_widget.update_graph(data_type, time_series_data[data_type])
    
    def get_data_type_from_index(self, index):
        """Get data type from combo box index"""
        data_types = ['kills', 'teleports', 'potions', 'boosts', 'instances', 'aggro', 'errors']
        
        if 0 <= index < len(data_types):
            return data_types[index]
        
        return 'kills'
    
    def on_graph_type_changed(self, index):
        """Handle graph type change"""
        self.update_current_graph()
    
    def load_session_list(self):
        """Load session list"""
        if not self.stats_tracker:
            return
        
        # Get session list
        sessions = self.stats_tracker.list_saved_sessions()
        
        # Clear combo box
        self.session_combo.clear()
        
        # Add sessions
        for session in sessions:
            # Extract timestamp from filename
            if session.startswith('session_') and session.endswith('.json'):
                timestamp = session[8:-5]  # Remove 'session_' and '.json'
                
                try:
                    # Parse timestamp
                    dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                    
                    # Format for display
                    display_text = dt.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Add to combo box
                    self.session_combo.addItem(display_text, session)
                
                except ValueError:
                    # Invalid timestamp format
                    self.session_combo.addItem(session, session)
    
    def on_session_selected(self, index):
        """Handle session selection"""
        # Enable load button if session selected
        self.load_button.setEnabled(index >= 0)
        self.export_button.setEnabled(index >= 0)
    
    def on_load_clicked(self):
        """Handle load button click"""
        if not self.stats_tracker:
            return
        
        # Get selected session
        index = self.session_combo.currentIndex()
        
        if index < 0:
            return
        
        # Get session filename
        filename = self.session_combo.itemData(index)
        
        # Load session stats
        stats_data = self.stats_tracker.load_session_stats(filename)
        
        if not stats_data:
            QMessageBox.warning(
                self,
                "Error",
                "Failed to load session statistics."
            )
            return
        
        # Update details table
        self.details_table.setRowCount(0)
        
        # Add rows
        start_time = datetime.fromtimestamp(stats_data['session_start']).strftime("%Y-%m-%d %H:%M:%S")
        end_time = datetime.fromtimestamp(stats_data['session_end']).strftime("%Y-%m-%d %H:%M:%S")
        
        self.add_detail_row("Start Time", start_time)
        self.add_detail_row("End Time", end_time)
        
        # Format duration
        duration = stats_data['duration']
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
        
        self.add_detail_row("Duration", duration_str)
        
        # Add counters
        counters = stats_data['counters']
        
        self.add_detail_row("Monster Kills", str(counters['monster_kills']))
        
        # Calculate kills per hour
        if duration > 0:
            kills_per_hour = counters['monster_kills'] / (duration / 3600)
            self.add_detail_row("Kills Per Hour", f"{kills_per_hour:.1f}")
        
        self.add_detail_row("Teleports Used", str(counters['teleports_used']))
        self.add_detail_row("Potions Used", str(counters['potions_used']))
        self.add_detail_row("Boosts Used", str(counters['boosts_used']))
        self.add_detail_row("Instances Entered", str(counters['instances_entered']))
        self.add_detail_row("Aggro Potions Used", str(counters['aggro_potions_used']))
        self.add_detail_row("Errors Occurred", str(counters['errors_occurred']))
        
        # Update history graph
        self.update_history_graph(stats_data)
    
    def add_detail_row(self, name, value):
        """Add a row to the details table"""
        row = self.details_table.rowCount()
        self.details_table.insertRow(row)
        self.details_table.setItem(row, 0, QTableWidgetItem(name))
        self.details_table.setItem(row, 1, QTableWidgetItem(value))
    
    def update_history_graph(self, stats_data):
        """Update the history graph"""
        if not HAS_MATPLOTLIB:
            return
        
        # Get time series data
        time_series_data = stats_data['time_series']
        
        # Get selected graph type
        index = self.history_graph_type_combo.currentIndex()
        data_type = self.get_data_type_from_index(index)
        
        # Update graph
        self.history_graph_widget.update_graph(data_type, time_series_data[data_type])
    
    def on_history_graph_type_changed(self, index):
        """Handle history graph type change"""
        # Get selected session
        session_index = self.session_combo.currentIndex()
        
        if session_index < 0:
            return
        
        # Get session filename
        filename = self.session_combo.itemData(session_index)
        
        # Load session stats
        stats_data = self.stats_tracker.load_session_stats(filename)
        
        if stats_data:
            self.update_history_graph(stats_data)
    
    def on_export_clicked(self):
        """Handle export button click"""
        if not self.stats_tracker:
            return
        
        # Get selected session
        index = self.session_combo.currentIndex()
        
        if index < 0:
            return
        
        # Get session filename
        filename = self.session_combo.itemData(index)
        
        # Get save path
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Session Statistics",
            filename,
            "JSON Files (*.json)"
        )
        
        if not save_path:
            return
        
        try:
            # Copy file
            import shutil
            source_path = os.path.join(self.stats_tracker.stats_dir, filename)
            shutil.copy(source_path, save_path)
            
            QMessageBox.information(
                self,
                "Export Successful",
                f"Session statistics exported to {save_path}"
            )
        
        except Exception as e:
            logger.error(f"Error exporting session statistics: {e}")
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export session statistics: {e}"
            )