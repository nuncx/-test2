"""
Modules for RSPS Color Bot v3

This package contains various modules that extend the bot's functionality.
"""

from .teleport import TeleportModule
from .potion import PotionModule
from .instance import InstanceModule
from .multi_monster import MultiMonsterModule

__all__ = ['TeleportModule', 'PotionModule', 'InstanceModule', 'MultiMonsterModule']