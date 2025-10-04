"""
Modules for RSPS Color Bot v3

This package contains various modules that extend the bot's functionality.
"""
# Re-export concrete manager/module classes for external use.
# Note: Original code attempted to import TeleportModule/PotionModule/InstanceModule which
# do not exist. The implemented classes are TeleportManager, PotionManager, InstanceManager,
# and MultiMonsterModule (the latter actually is named with *Module). Adjust exports to
# prevent ImportError during package import.
from .teleport import TeleportManager, TeleportLocation
from .potion import PotionManager, Potion, PotionType
from .instance import InstanceManager
from .slayer_module import SlayerModule
from .multi_monster import MultiMonsterModule

__all__ = [
	'TeleportManager',
	'TeleportLocation',
	'PotionManager',
	'Potion',
	'PotionType',
	'InstanceManager',
	'MultiMonsterModule',
	'SlayerModule',
]