"""
Advanced statistics and reporting for RSPS Color Bot v3
"""
import logging
import time
import json
import os
import datetime
import threading
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
from dataclasses import dataclass, field, asdict

from .state import EventType

# Get module logger
logger = logging.getLogger('rspsbot.core.stats')

@dataclass
class SessionStats:
    """
    Session statistics data class
    """
    session_id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    monster_count: int = 0
    teleport_count: int = 0
    potion_count: int = 0
    boost_count: int = 0
    instance_count: int = 0
    aggro_count: int = 0
    error_count: int = 0
    timeout_count: int = 0
    
    # Detection statistics
    detection_count: int = 0
    detection_success_count: int = 0
    detection_failure_count: int = 0
    avg_detection_time: float = 0.0
    
    # Performance statistics
    cpu_usage: List[float] = field(default_factory=list)
    memory_usage: List[float] = field(default_factory=list)
    
    # Time series data
    monster_kills_time: List[Tuple[float, int]] = field(default_factory=list)
    detection_times: List[Tuple[float, float]] = field(default_factory=list)
    
    # Advanced metrics
    kills_per_hour: float = 0.0
    detection_success_rate: float = 0.0
    avg_time_between_kills: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionStats':
        """Create from dictionary"""
        return cls(**data)

class StatisticsTracker:
    """
    Statistics tracking for the bot
    
    This class tracks various statistics during bot operation, such as
    monster kills, teleport usage, potion usage, etc.
    """
    
    def __init__(self, config_manager=None):
        """
        Initialize statistics tracker
        
        Args:
            config_manager: Configuration manager
        """
        self.config_manager = config_manager
        
        # Current session
        self.current_session = SessionStats()
        self.session_active = False
        
        # Historical sessions
        self.sessions = []
        self.max_sessions = 50
        
        # Performance monitoring
        self.performance_monitor_active = False
        self.performance_monitor_thread = None
        self.performance_monitor_interval = 5.0  # seconds

        # Data storage
        self.data_dir = Path("stats")
        os.makedirs(self.data_dir, exist_ok=True)
        # Backward/GUI compatibility: some UI references 'stats_dir'
        # Ensure it's a string path for os.path.join usage in the GUI.
        self.stats_dir = str(self.data_dir)
        
        # Load historical sessions
        self._load_sessions()
        
        logger.info("Statistics tracker initialized")
    
    def _load_sessions(self):
        """Load historical sessions from files"""
        try:
            # Find session files
            session_files = list(self.data_dir.glob("session_*.json"))
            
            # Sort by modification time (newest first)
            session_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Load up to max_sessions
            for file_path in session_files[:self.max_sessions]:
                try:
                    with open(file_path, 'r') as f:
                        session_data = json.load(f)
                        session = SessionStats.from_dict(session_data)
                        self.sessions.append(session)
                except Exception as e:
                    logger.error(f"Error loading session file {file_path}: {e}")
            
            logger.info(f"Loaded {len(self.sessions)} historical sessions")
        
        except Exception as e:
            logger.error(f"Error loading historical sessions: {e}")
    
    def _save_session(self, session: SessionStats):
        """
        Save session to file
        
        Args:
            session: Session to save
        """
        try:
            # Create filename
            filename = f"session_{session.session_id}.json"
            file_path = self.data_dir / filename
            
            # Save to file
            with open(file_path, 'w') as f:
                json.dump(session.to_dict(), f, indent=2)
            
            logger.info(f"Session statistics saved to {file_path}")
        
        except Exception as e:
            logger.error(f"Error saving session statistics: {e}")
    
    def _start_performance_monitoring(self):
        """Start performance monitoring thread"""
        if self.performance_monitor_active:
            return
        
        self.performance_monitor_active = True
        self.performance_monitor_thread = threading.Thread(
            target=self._performance_monitor_loop,
            daemon=True
        )
        self.performance_monitor_thread.start()
        
        logger.debug("Performance monitoring started")
    
    def _stop_performance_monitoring(self):
        """Stop performance monitoring thread"""
        self.performance_monitor_active = False
        
        if self.performance_monitor_thread:
            self.performance_monitor_thread.join(timeout=1.0)
            self.performance_monitor_thread = None
        
        logger.debug("Performance monitoring stopped")
    
    def _performance_monitor_loop(self):
        """Performance monitoring loop"""
        try:
            import psutil
        except ImportError:
            logger.warning("psutil not installed, performance monitoring disabled")
            return
        
        while self.performance_monitor_active and self.session_active:
            try:
                # Get CPU usage
                cpu_percent = psutil.cpu_percent(interval=None)
                
                # Get memory usage
                memory_info = psutil.Process(os.getpid()).memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)  # Convert to MB
                
                # Add to current session
                self.current_session.cpu_usage.append(cpu_percent)
                self.current_session.memory_usage.append(memory_mb)
                
                # Sleep for interval
                time.sleep(self.performance_monitor_interval)
            
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
                time.sleep(self.performance_monitor_interval)
    
    def _calculate_advanced_metrics(self):
        """Calculate advanced metrics for current session"""
        # Calculate kills per hour
        if self.current_session.duration > 0:
            hours = self.current_session.duration / 3600
            self.current_session.kills_per_hour = self.current_session.monster_count / hours if hours > 0 else 0
        
        # Calculate detection success rate
        total_detections = self.current_session.detection_success_count + self.current_session.detection_failure_count
        self.current_session.detection_success_rate = self.current_session.detection_success_count / total_detections if total_detections > 0 else 0
        
        # Calculate average time between kills
        if len(self.current_session.monster_kills_time) > 1:
            kill_times = [t for t, _ in self.current_session.monster_kills_time]
            time_diffs = [kill_times[i] - kill_times[i-1] for i in range(1, len(kill_times))]
            self.current_session.avg_time_between_kills = sum(time_diffs) / len(time_diffs) if time_diffs else 0
    
    def start_session(self):
        """Start a new statistics session"""
        if self.session_active:
            logger.warning("Session already active, ignoring start_session call")
            return
        
        # Generate session ID
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = timestamp
        
        # Create new session
        self.current_session = SessionStats(
            session_id=session_id,
            start_time=time.time()
        )
        
        # Mark session as active
        self.session_active = True
        
        # Start performance monitoring
        self._start_performance_monitoring()
        
        logger.info("Statistics session started")
    
    def end_session(self):
        """End the current statistics session"""
        if not self.session_active:
            logger.warning("No active session, ignoring end_session call")
            return
        
        # Stop performance monitoring
        self._stop_performance_monitoring()
        
        # Update session end time and duration
        self.current_session.end_time = time.time()
        self.current_session.duration = self.current_session.end_time - self.current_session.start_time
        
        # Calculate advanced metrics
        self._calculate_advanced_metrics()
        
        # Save session
        self._save_session(self.current_session)
        
        # Add to historical sessions
        self.sessions.insert(0, self.current_session)
        
        # Limit number of sessions
        if len(self.sessions) > self.max_sessions:
            self.sessions = self.sessions[:self.max_sessions]
        
        # Mark session as inactive
        self.session_active = False
        
        logger.info(f"Statistics session ended (duration: {self.current_session.duration:.1f}s)")

    # --- GUI adapter methods for StatsPanel compatibility ---
    def list_saved_sessions(self) -> List[str]:
        """
        Return a list of saved session filenames (e.g., 'session_YYYYMMDD_HHMMSS.json'),
        sorted by most recent first.
        """
        try:
            files = list(self.data_dir.glob("session_*.json"))
            files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            return [f.name for f in files]
        except Exception as e:
            logger.error(f"Error listing saved sessions: {e}")
            return []

    def load_session_stats(self, filename: str) -> Dict[str, Any]:
        """
        Load a specific session file and return a dict shaped for StatsPanel.

        Expected keys by GUI:
        - session_start, session_end, duration
        - counters: {monster_kills, teleports_used, potions_used, boosts_used,
                     instances_entered, aggro_potions_used, errors_occurred}
        - time_series: {kills, teleports, potions, boosts, instances, aggro, errors}
        """
        try:
            file_path = self.data_dir / filename
            with open(file_path, 'r') as f:
                data = json.load(f)

            session_start = data.get('start_time', 0.0)
            session_end = data.get('end_time', session_start + data.get('duration', 0.0))
            duration = data.get('duration', max(0.0, session_end - session_start))

            counters = {
                'monster_kills': data.get('monster_count', 0),
                'teleports_used': data.get('teleport_count', 0),
                'potions_used': data.get('potion_count', 0),
                'boosts_used': data.get('boost_count', 0),
                'instances_entered': data.get('instance_count', 0),
                'aggro_potions_used': data.get('aggro_count', 0),
                'errors_occurred': data.get('error_count', 0),
            }

            time_series = {
                'kills': data.get('monster_kills_time', []),
                'teleports': [],
                'potions': [],
                'boosts': [],
                'instances': [],
                'aggro': [],
                'errors': [],
            }

            return {
                'session_start': session_start,
                'session_end': session_end,
                'duration': duration,
                'counters': counters,
                'time_series': time_series,
            }
        except Exception as e:
            logger.error(f"Error loading session stats from {filename}: {e}")
            return {}

    def get_session_stats(self) -> Dict[str, Any]:
        """
        Return the current session stats in the format expected by StatsPanel.update_stats.
        Keys: is_active, start_time, duration, monster_kills, kills_per_hour,
              teleports_used, potions_used, boosts_used, instances_entered,
              aggro_potions_used, errors_occurred
        """
        if not self.session_active:
            return {
                'is_active': False,
                'start_time': 0.0,
                'duration': 0.0,
                'monster_kills': 0,
                'kills_per_hour': 0.0,
                'teleports_used': 0,
                'potions_used': 0,
                'boosts_used': 0,
                'instances_entered': 0,
                'aggro_potions_used': 0,
                'errors_occurred': 0,
            }

        duration = time.time() - self.current_session.start_time
        hours = duration / 3600 if duration > 0 else 0
        kph = (self.current_session.monster_count / hours) if hours > 0 else 0.0

        return {
            'is_active': True,
            'start_time': self.current_session.start_time,
            'duration': duration,
            'monster_kills': self.current_session.monster_count,
            'kills_per_hour': kph,
            'teleports_used': self.current_session.teleport_count,
            'potions_used': self.current_session.potion_count,
            'boosts_used': self.current_session.boost_count,
            'instances_entered': self.current_session.instance_count,
            'aggro_potions_used': self.current_session.aggro_count,
            'errors_occurred': self.current_session.error_count,
        }

    def get_time_series_data(self) -> Dict[str, List[tuple]]:
        """
        Return time series data for the current session in the format expected by StatsPanel.
        Keys: kills, teleports, potions, boosts, instances, aggro, errors
        """
        if not self.session_active:
            return {k: [] for k in ['kills', 'teleports', 'potions', 'boosts', 'instances', 'aggro', 'errors']}

        return {
            'kills': list(self.current_session.monster_kills_time),
            'teleports': [],
            'potions': [],
            'boosts': [],
            'instances': [],
            'aggro': [],
            'errors': [],
        }
    
    def handle_event(self, event_type: EventType, data: Dict[str, Any] = None):
        """
        Handle event for statistics tracking
        
        Args:
            event_type: Event type
            data: Event data
        """
        if not self.session_active:
            return
        
        # Default data
        if data is None:
            data = {}
        
        # Handle different event types
        if event_type == EventType.MONSTER_KILLED:
            self.current_session.monster_count += 1
            self.current_session.monster_kills_time.append((time.time(), self.current_session.monster_count))
        
        elif event_type == EventType.TELEPORT_USED:
            self.current_session.teleport_count += 1
        
        elif event_type == EventType.POTION_USED:
            self.current_session.potion_count += 1
        
        elif event_type == EventType.BOOST_USED:
            self.current_session.boost_count += 1
        
        elif event_type == EventType.INSTANCE_ENTERED:
            self.current_session.instance_count += 1
        
        elif event_type == EventType.AGGRO_USED:
            self.current_session.aggro_count += 1
        
        elif event_type == EventType.ERROR_OCCURRED:
            self.current_session.error_count += 1
        
        elif event_type == EventType.TIMEOUT_OCCURRED:
            self.current_session.timeout_count += 1
        
        elif event_type == EventType.DETECTION_COMPLETED:
            self.current_session.detection_count += 1
            
            # Extract detection data
            success = data.get('success', False)
            execution_time = data.get('execution_time', 0.0)
            
            if success:
                self.current_session.detection_success_count += 1
            else:
                self.current_session.detection_failure_count += 1
            
            # Update average detection time
            if self.current_session.detection_count > 0:
                self.current_session.avg_detection_time = (
                    (self.current_session.avg_detection_time * (self.current_session.detection_count - 1) + execution_time) / 
                    self.current_session.detection_count
                )
            
            # Add to time series
            self.current_session.detection_times.append((time.time(), execution_time))
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current statistics
        
        Returns:
            Dictionary with current statistics
        """
        if not self.session_active:
            return {
                'monster_count': 0,
                'teleport_count': 0,
                'potion_count': 0,
                'boost_count': 0,
                'instance_count': 0,
                'aggro_count': 0,
                'error_count': 0,
                'timeout_count': 0
            }
        
        return {
            'monster_count': self.current_session.monster_count,
            'teleport_count': self.current_session.teleport_count,
            'potion_count': self.current_session.potion_count,
            'boost_count': self.current_session.boost_count,
            'instance_count': self.current_session.instance_count,
            'aggro_count': self.current_session.aggro_count,
            'error_count': self.current_session.error_count,
            'timeout_count': self.current_session.timeout_count,
            'detection_count': self.current_session.detection_count,
            'detection_success_rate': self.current_session.detection_success_rate,
            'avg_detection_time': self.current_session.avg_detection_time
        }
    
    def get_monster_count(self) -> int:
        """
        Get monster kill count
        
        Returns:
            Monster kill count
        """
        if not self.session_active:
            return 0
        
        return self.current_session.monster_count
    
    def get_runtime(self) -> float:
        """
        Get session runtime in seconds
        
        Returns:
            Session runtime in seconds
        """
        if not self.session_active:
            return 0.0
        
        return time.time() - self.current_session.start_time
    
    def get_current_stats(self) -> Dict[str, Any]:
        """
        Get current session statistics
        
        Returns:
            Dictionary with current statistics
        """
        if not self.session_active:
            return {}
        
        # Calculate duration
        current_duration = time.time() - self.current_session.start_time
        
        # Calculate kills per hour
        hours = current_duration / 3600
        kills_per_hour = self.current_session.monster_count / hours if hours > 0 else 0
        
        # Calculate detection success rate
        total_detections = self.current_session.detection_success_count + self.current_session.detection_failure_count
        detection_success_rate = self.current_session.detection_success_count / total_detections if total_detections > 0 else 0
        
        return {
            'session_id': self.current_session.session_id,
            'duration': current_duration,
            'monster_count': self.current_session.monster_count,
            'teleport_count': self.current_session.teleport_count,
            'potion_count': self.current_session.potion_count,
            'boost_count': self.current_session.boost_count,
            'instance_count': self.current_session.instance_count,
            'aggro_count': self.current_session.aggro_count,
            'error_count': self.current_session.error_count,
            'timeout_count': self.current_session.timeout_count,
            'detection_count': self.current_session.detection_count,
            'detection_success_count': self.current_session.detection_success_count,
            'detection_failure_count': self.current_session.detection_failure_count,
            'avg_detection_time': self.current_session.avg_detection_time,
            'kills_per_hour': kills_per_hour,
            'detection_success_rate': detection_success_rate
        }
    
    def get_historical_stats(self) -> List[Dict[str, Any]]:
        """
        Get historical session statistics
        
        Returns:
            List of dictionaries with historical statistics
        """
        return [session.to_dict() for session in self.sessions]
    
    def get_aggregated_stats(self) -> Dict[str, Any]:
        """
        Get aggregated statistics across all sessions
        
        Returns:
            Dictionary with aggregated statistics
        """
        if not self.sessions:
            return {}
        
        # Aggregate statistics
        total_duration = sum(session.duration for session in self.sessions)
        total_monster_count = sum(session.monster_count for session in self.sessions)
        total_teleport_count = sum(session.teleport_count for session in self.sessions)
        total_potion_count = sum(session.potion_count for session in self.sessions)
        total_boost_count = sum(session.boost_count for session in self.sessions)
        total_instance_count = sum(session.instance_count for session in self.sessions)
        total_aggro_count = sum(session.aggro_count for session in self.sessions)
        total_error_count = sum(session.error_count for session in self.sessions)
        total_timeout_count = sum(session.timeout_count for session in self.sessions)
        
        # Calculate averages
        avg_session_duration = total_duration / len(self.sessions)
        avg_monsters_per_session = total_monster_count / len(self.sessions)
        
        # Calculate kills per hour across all sessions
        hours = total_duration / 3600
        kills_per_hour = total_monster_count / hours if hours > 0 else 0
        
        return {
            'total_sessions': len(self.sessions),
            'total_duration': total_duration,
            'total_monster_count': total_monster_count,
            'total_teleport_count': total_teleport_count,
            'total_potion_count': total_potion_count,
            'total_boost_count': total_boost_count,
            'total_instance_count': total_instance_count,
            'total_aggro_count': total_aggro_count,
            'total_error_count': total_error_count,
            'total_timeout_count': total_timeout_count,
            'avg_session_duration': avg_session_duration,
            'avg_monsters_per_session': avg_monsters_per_session,
            'kills_per_hour': kills_per_hour
        }
    
    def generate_report(self, output_dir: Optional[str] = None) -> str:
        """
        Generate a comprehensive statistics report
        
        Args:
            output_dir: Output directory (None for default)
        
        Returns:
            Path to generated report
        """
        try:
            # Use default directory if not specified
            if output_dir is None:
                output_dir = str(self.data_dir / "reports")
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create report filename
            report_file = os.path.join(output_dir, f"report_{timestamp}.html")
            
            # Generate plots
            plot_dir = os.path.join(output_dir, "plots")
            os.makedirs(plot_dir, exist_ok=True)
            
            # Generate plots if we have sessions
            plot_paths = {}
            if self.sessions:
                plot_paths = self._generate_report_plots(plot_dir, timestamp)
            
            # Get statistics
            current_stats = self.get_current_stats()
            historical_stats = self.get_historical_stats()
            aggregated_stats = self.get_aggregated_stats()
            
            # Generate HTML report
            with open(report_file, 'w') as f:
                f.write(self._generate_html_report(current_stats, historical_stats, aggregated_stats, plot_paths))
            
            logger.info(f"Statistics report generated: {report_file}")
            return report_file
        
        except Exception as e:
            logger.error(f"Error generating statistics report: {e}")
            return ""
    
    def _generate_report_plots(self, plot_dir: str, timestamp: str) -> Dict[str, str]:
        """
        Generate plots for report
        
        Args:
            plot_dir: Output directory for plots
            timestamp: Timestamp for filenames
        
        Returns:
            Dictionary mapping plot names to file paths
        """
        plot_paths = {}
        
        try:
            # 1. Kills over time
            plt.figure(figsize=(10, 6))
            
            for i, session in enumerate(self.sessions[:5]):  # Show up to 5 most recent sessions
                if session.monster_kills_time:
                    times = [(t - session.start_time) / 60 for t, _ in session.monster_kills_time]  # Convert to minutes
                    kills = [k for _, k in session.monster_kills_time]
                    plt.plot(times, kills, label=f"Session {i+1}")
            
            plt.title("Monster Kills Over Time")
            plt.xlabel("Time (minutes)")
            plt.ylabel("Kills")
            plt.grid(True)
            plt.legend()
            
            kills_plot = os.path.join(plot_dir, f"kills_over_time_{timestamp}.png")
            plt.savefig(kills_plot)
            plt.close()
            
            plot_paths['kills_over_time'] = os.path.relpath(kills_plot, plot_dir)
            
            # 2. Detection times
            plt.figure(figsize=(10, 6))
            
            for i, session in enumerate(self.sessions[:5]):  # Show up to 5 most recent sessions
                if session.detection_times:
                    times = [(t - session.start_time) / 60 for t, _ in session.detection_times]  # Convert to minutes
                    detection_times = [d for _, d in session.detection_times]
                    plt.plot(times, detection_times, label=f"Session {i+1}")
            
            plt.title("Detection Times")
            plt.xlabel("Time (minutes)")
            plt.ylabel("Detection Time (seconds)")
            plt.grid(True)
            plt.legend()
            
            detection_plot = os.path.join(plot_dir, f"detection_times_{timestamp}.png")
            plt.savefig(detection_plot)
            plt.close()
            
            plot_paths['detection_times'] = os.path.relpath(detection_plot, plot_dir)
            
            # 3. Performance metrics
            plt.figure(figsize=(10, 6))
            
            if self.sessions and self.sessions[0].cpu_usage:
                plt.subplot(2, 1, 1)
                plt.plot(self.sessions[0].cpu_usage)
                plt.title("CPU Usage")
                plt.ylabel("CPU %")
                plt.grid(True)
                
                plt.subplot(2, 1, 2)
                plt.plot(self.sessions[0].memory_usage)
                plt.title("Memory Usage")
                plt.xlabel("Sample")
                plt.ylabel("Memory (MB)")
                plt.grid(True)
                
                plt.tight_layout()
                
                performance_plot = os.path.join(plot_dir, f"performance_{timestamp}.png")
                plt.savefig(performance_plot)
                plt.close()
                
                plot_paths['performance'] = os.path.relpath(performance_plot, plot_dir)
            
            # 4. Session comparison
            plt.figure(figsize=(12, 8))
            
            # Get data for up to 10 most recent sessions
            sessions_to_plot = min(10, len(self.sessions))
            session_indices = list(range(sessions_to_plot))
            session_indices.reverse()  # Reverse to show most recent first
            
            kills = [self.sessions[i].monster_count for i in session_indices]
            durations = [self.sessions[i].duration / 60 for i in session_indices]  # Convert to minutes
            kills_per_hour = [self.sessions[i].kills_per_hour for i in session_indices]
            
            plt.subplot(3, 1, 1)
            plt.bar(session_indices, kills)
            plt.title("Kills per Session")
            plt.ylabel("Kills")
            plt.grid(True)
            
            plt.subplot(3, 1, 2)
            plt.bar(session_indices, durations)
            plt.title("Session Duration")
            plt.ylabel("Minutes")
            plt.grid(True)
            
            plt.subplot(3, 1, 3)
            plt.bar(session_indices, kills_per_hour)
            plt.title("Kills per Hour")
            plt.xlabel("Session Index (0 = most recent)")
            plt.ylabel("Kills/Hour")
            plt.grid(True)
            
            plt.tight_layout()
            
            comparison_plot = os.path.join(plot_dir, f"session_comparison_{timestamp}.png")
            plt.savefig(comparison_plot)
            plt.close()
            
            plot_paths['session_comparison'] = os.path.relpath(comparison_plot, plot_dir)
        
        except Exception as e:
            logger.error(f"Error generating report plots: {e}")
        
        return plot_paths
    
    def _generate_html_report(
        self,
        current_stats: Dict[str, Any],
        historical_stats: List[Dict[str, Any]],
        aggregated_stats: Dict[str, Any],
        plot_paths: Dict[str, str]
    ) -> str:
        """
        Generate HTML report content
        
        Args:
            current_stats: Current session statistics
            historical_stats: Historical session statistics
            aggregated_stats: Aggregated statistics
            plot_paths: Paths to generated plots
        
        Returns:
            HTML report content
        """
        # Generate timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Start HTML content
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>RSPS Color Bot v3 - Statistics Report</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    color: #333;
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                .header {{
                    background-color: #3498db;
                    color: white;
                    padding: 20px;
                    margin-bottom: 20px;
                    border-radius: 5px;
                }}
                .section {{
                    background-color: #f9f9f9;
                    padding: 20px;
                    margin-bottom: 20px;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }}
                th, td {{
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
                tr:hover {{
                    background-color: #f5f5f5;
                }}
                .plot {{
                    max-width: 100%;
                    height: auto;
                    margin: 20px 0;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                    gap: 20px;
                }}
                .stat-card {{
                    background-color: white;
                    padding: 15px;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                .stat-value {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #3498db;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding: 20px;
                    color: #7f8c8d;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>RSPS Color Bot v3 - Statistics Report</h1>
                    <p>Generated on {timestamp}</p>
                </div>
        """
        
        # Aggregated statistics section
        if aggregated_stats:
            html += """
                <div class="section">
                    <h2>Aggregated Statistics</h2>
                    <div class="stats-grid">
            """
            
            # Add stat cards for key metrics
            for key, value in aggregated_stats.items():
                if key in ['total_sessions', 'total_monster_count', 'total_duration', 'kills_per_hour']:
                    # Format value based on type
                    if key == 'total_duration':
                        formatted_value = f"{value / 3600:.1f} hours"
                    elif key == 'kills_per_hour':
                        formatted_value = f"{value:.1f}"
                    else:
                        formatted_value = str(value)
                    
                    # Format key for display
                    display_key = key.replace('_', ' ').title()
                    
                    html += f"""
                    <div class="stat-card">
                        <div class="stat-label">{display_key}</div>
                        <div class="stat-value">{formatted_value}</div>
                    </div>
                    """
            
            html += """
                    </div>
                    
                    <h3>Detailed Aggregated Statistics</h3>
                    <table>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                        </tr>
            """
            
            # Add all aggregated stats to table
            for key, value in aggregated_stats.items():
                # Format key for display
                display_key = key.replace('_', ' ').title()
                
                # Format value based on type
                if isinstance(value, float):
                    formatted_value = f"{value:.2f}"
                else:
                    formatted_value = str(value)
                
                html += f"""
                        <tr>
                            <td>{display_key}</td>
                            <td>{formatted_value}</td>
                        </tr>
                """
            
            html += """
                    </table>
                </div>
            """
        
        # Current session section
        if current_stats:
            html += """
                <div class="section">
                    <h2>Current Session</h2>
                    <div class="stats-grid">
            """
            
            # Add stat cards for key metrics
            for key, value in current_stats.items():
                if key in ['monster_count', 'duration', 'kills_per_hour', 'detection_success_rate']:
                    # Format value based on type
                    if key == 'duration':
                        hours = value // 3600
                        minutes = (value % 3600) // 60
                        seconds = value % 60
                        formatted_value = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
                    elif key in ['kills_per_hour', 'detection_success_rate']:
                        formatted_value = f"{value:.1f}"
                        if key == 'detection_success_rate':
                            formatted_value += "%"
                    else:
                        formatted_value = str(value)
                    
                    # Format key for display
                    display_key = key.replace('_', ' ').title()
                    
                    html += f"""
                    <div class="stat-card">
                        <div class="stat-label">{display_key}</div>
                        <div class="stat-value">{formatted_value}</div>
                    </div>
                    """
            
            html += """
                    </div>
                    
                    <h3>Detailed Session Statistics</h3>
                    <table>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                        </tr>
            """
            
            # Add all current stats to table
            for key, value in current_stats.items():
                # Format key for display
                display_key = key.replace('_', ' ').title()
                
                # Format value based on type
                if isinstance(value, float):
                    formatted_value = f"{value:.2f}"
                else:
                    formatted_value = str(value)
                
                html += f"""
                        <tr>
                            <td>{display_key}</td>
                            <td>{formatted_value}</td>
                        </tr>
                """
            
            html += """
                    </table>
                </div>
            """
        
        # Plots section
        if plot_paths:
            html += """
                <div class="section">
                    <h2>Performance Visualizations</h2>
            """
            
            # Add each plot
            for plot_name, plot_path in plot_paths.items():
                # Format plot name for display
                display_name = plot_name.replace('_', ' ').title()
                
                html += f"""
                    <h3>{display_name}</h3>
                    <img src="{plot_path}" alt="{display_name}" class="plot">
                """
            
            html += """
                </div>
            """
        
        # Historical sessions section
        if historical_stats:
            html += """
                <div class="section">
                    <h2>Historical Sessions</h2>
                    <table>
                        <tr>
                            <th>Session ID</th>
                            <th>Duration</th>
                            <th>Monsters</th>
                            <th>Kills/Hour</th>
                            <th>Detection Success</th>
                        </tr>
            """
            
            # Add historical sessions to table (limit to 10)
            for i, session in enumerate(historical_stats[:10]):
                # Format values
                session_id = session.get('session_id', 'Unknown')
                duration = session.get('duration', 0)
                duration_str = f"{duration / 3600:.1f} hours"
                monsters = session.get('monster_count', 0)
                kills_per_hour = session.get('kills_per_hour', 0)
                
                detection_success = session.get('detection_success_count', 0)
                detection_total = detection_success + session.get('detection_failure_count', 0)
                detection_rate = detection_success / detection_total if detection_total > 0 else 0
                detection_rate_str = f"{detection_rate * 100:.1f}%"
                
                html += f"""
                        <tr>
                            <td>{session_id}</td>
                            <td>{duration_str}</td>
                            <td>{monsters}</td>
                            <td>{kills_per_hour:.1f}</td>
                            <td>{detection_rate_str}</td>
                        </tr>
                """
            
            html += """
                    </table>
                </div>
            """
        
        # Footer and end of HTML
        html += """
                <div class="footer">
                    <p>RSPS Color Bot v3 - Advanced Statistics and Reporting</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def export_data(self, format: str = 'json', output_file: Optional[str] = None) -> str:
        """
        Export statistics data
        
        Args:
            format: Export format ('json' or 'csv')
            output_file: Output file path (None for default)
        
        Returns:
            Path to exported file
        """
        try:
            # Use default filename if not specified
            if output_file is None:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = str(self.data_dir / f"export_{timestamp}.{format}")
            
            # Get data
            data = {
                'current_session': self.get_current_stats() if self.session_active else {},
                'historical_sessions': self.get_historical_stats(),
                'aggregated_stats': self.get_aggregated_stats()
            }
            
            # Export based on format
            if format.lower() == 'json':
                with open(output_file, 'w') as f:
                    json.dump(data, f, indent=2)
            
            elif format.lower() == 'csv':
                import csv
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
                
                # Export sessions to CSV
                with open(output_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    
                    # Write header
                    if data['historical_sessions']:
                        header = list(data['historical_sessions'][0].keys())
                        writer.writerow(header)
                        
                        # Write data
                        for session in data['historical_sessions']:
                            writer.writerow([session.get(key, '') for key in header])
            
            else:
                logger.error(f"Unsupported export format: {format}")
                return ""
            
            logger.info(f"Statistics data exported to {output_file}")
            return output_file
        
        except Exception as e:
            logger.error(f"Error exporting statistics data: {e}")
            return ""