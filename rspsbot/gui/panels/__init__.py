"""
Panels for RSPS Color Bot v3 - CLEANED VERSION

Removed unused panels:
- TeleportPanel (not integrated)
- PotionPanel (not integrated) 
- InstancePanel (not integrated)
"""
from .control_panel import ControlPanel
from .detection_panel import DetectionPanel, ColorSpecEditor
from .combat_panel import CombatPanel
from .profiles_panel import ProfilesPanel
from .logs_panel import LogsPanel
from .stats_panel import StatsPanel, StatsGraph

__all__ = [
    "ControlPanel",
    "DetectionPanel", 
    "CombatPanel",
    "ProfilesPanel",
    "LogsPanel",
    "StatsPanel"
]
