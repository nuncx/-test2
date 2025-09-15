"""
Windows power management helpers.

Provides a KeepAwake context/manager that calls SetThreadExecutionState to prevent
the system from sleeping while the bot is running. By default it allows the
display to turn off to save power unless configured otherwise.
"""
from __future__ import annotations

import sys
import logging
import threading
from contextlib import AbstractContextManager

logger = logging.getLogger("rspsbot.utils.power")


class KeepAwake(AbstractContextManager):
    """
    Prevent system sleep on Windows while this object is active.

    By default, allows the display to turn off (monitor sleep) but keeps the system awake.
    If keep_display_awake=True, also requests the display to remain on.
    """

    # Execution state flags (from WinBase.h)
    ES_AWAYMODE_REQUIRED = 0x00000040
    ES_CONTINUOUS = 0x80000000
    ES_DISPLAY_REQUIRED = 0x00000002
    ES_SYSTEM_REQUIRED = 0x00000001

    def __init__(self, keep_display_awake: bool = False):
        self.keep_display_awake = keep_display_awake
        self._applied = False
        self._lock = threading.Lock()
        self._restore_state = None

        # Late-bound imports to avoid platform issues
        self._kernel32 = None
        self._SetThreadExecutionState = None

        if sys.platform.startswith("win"):
            try:
                import ctypes
                self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                self._SetThreadExecutionState = self._kernel32.SetThreadExecutionState
                self._SetThreadExecutionState.restype = ctypes.c_uint
                self._SetThreadExecutionState.argtypes = [ctypes.c_uint]
            except Exception as e:
                logger.warning(f"Failed to initialize Windows power API: {e}")
        else:
            logger.info("KeepAwake is a no-op on non-Windows platforms")

    def _apply(self):
        if not self._SetThreadExecutionState:
            return
        flags = self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED
        if self.keep_display_awake:
            flags |= self.ES_DISPLAY_REQUIRED
        prev = self._SetThreadExecutionState(flags)
        if prev == 0:
            logger.warning("SetThreadExecutionState failed (returned 0)")
        else:
            self._restore_state = prev
        self._applied = True
        logger.debug("KeepAwake applied: system_required=%s, display_required=%s",
                     True, self.keep_display_awake)

    def _clear(self):
        if not self._SetThreadExecutionState:
            return
        # Reapply ES_CONTINUOUS to clear requirements
        prev = self._SetThreadExecutionState(self.ES_CONTINUOUS)
        if prev == 0:
            logger.debug("Clearing execution state returned 0 (may still be ok)")
        self._applied = False
        logger.debug("KeepAwake cleared")

    def __enter__(self) -> "KeepAwake":
        with self._lock:
            if not self._applied:
                self._apply()
        return self

    def __exit__(self, exc_type, exc, tb):
        with self._lock:
            if self._applied:
                self._clear()
        return False

    def start(self):
        """Imperative start (same as entering context)."""
        self.__enter__()

    def stop(self):
        """Imperative stop (same as exiting context)."""
        self.__exit__(None, None, None)
