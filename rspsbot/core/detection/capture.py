"""
Screen capture utilities for RSPS Color Bot v3
"""
import time
import threading
import logging
import numpy as np
from typing import Dict, Optional, Tuple, List
import mss
import cv2

# Get module logger
logger = logging.getLogger('rspsbot.core.detection.capture')

class CaptureService:
    """
    Screen capture service with caching and region-based capture
    
    This class provides methods to capture the screen or specific regions.
    It uses caching to improve performance and supports multi-monitor setups.
    """
    
    _global_instance = None  # lightweight singleton (same process)

    def __new__(cls, *args, **kwargs):
        """Provide a simple singleton-style instance so ad-hoc GUI helpers reuse
        the same underlying MSS resources and avoid log spam. If a distinct
        instance is ever required (e.g. different cache_ttl), caller can pass
        force_new=True in kwargs."""
        force_new = kwargs.pop('force_new', False)
        if not force_new and cls._global_instance is not None:
            return cls._global_instance
        inst = super().__new__(cls)
        if not force_new:
            cls._global_instance = inst
        return inst

    def __init__(self, cache_ttl: float = 0.05, force_new: bool = False):
        """Initialize the capture service (idempotent for singleton reuse)."""
        # If we've already run initialization for the singleton instance, skip to avoid log spam.
        if getattr(self, '_initialized', False):
            return

        # MSS is not thread-safe, so we use thread-local storage
        self._tls = threading.local()

        # Cache settings
        self.cache_ttl = cache_ttl
        self._cache = {}
        self._cache_lock = threading.RLock()

        # Window information & focus logging throttle
        self._window_bbox = None
        self._last_focus_title: Optional[str] = None
        self._last_focus_log_time: float = 0.0
        self._focus_log_interval: float = 30.0  # seconds between identical focus info logs

        logger.debug("Capture service initialized")
        self._initialized = True
    
    def _get_mss(self):
        """
        Get or create an MSS instance for the current thread
        
        Returns:
            MSS instance
        """
        if not hasattr(self._tls, 'mss'):
            self._tls.mss = mss.mss()
        return self._tls.mss
    
    def list_windows(self) -> List[str]:
        """
        List available window titles
        
        Returns:
            List of window titles
        """
        try:
            import pygetwindow as gw
            return [w.title for w in gw.getAllWindows() if w.title]
        except ImportError:
            logger.warning("pygetwindow not available, cannot list windows")
            return []
    
    def focus_window(self, title_substr: str, retries: int = 5, sleep_s: float = 0.3, exact: bool = False) -> bool:
        """
        Focus a window by title
        
        Args:
            title_substr: Window title or substring
            retries: Number of retries
            sleep_s: Sleep time between retries
            exact: Whether to match title exactly
        
        Returns:
            True if window was focused, False otherwise
        """
        try:
            import pygetwindow as gw
            
            for _ in range(retries):
                wins = gw.getAllWindows()
                
                if exact:
                    candidates = [w for w in wins if w.title == title_substr]
                else:
                    candidates = [w for w in wins if title_substr.lower() in w.title.lower()]
                
                # Sort by minimized state and size (prefer non-minimized and larger windows)
                candidates.sort(key=lambda w: (w.isMinimized, -w.width * w.height))
                
                for w in candidates:
                    try:
                        if w.isMinimized:
                            w.restore()
                            time.sleep(sleep_s)
                        
                        w.activate()
                        time.sleep(sleep_s)
                        
                        # Update window bbox
                        self._window_bbox = {
                            "left": w.left,
                            "top": w.top,
                            "width": w.width,
                            "height": w.height
                        }
                        
                        # Throttled logging: only log at INFO if title changed or interval elapsed; else debug.
                        now = time.time()
                        if (self._last_focus_title != w.title) or (now - self._last_focus_log_time > self._focus_log_interval):
                            logger.info(f"Focused window: {w.title}")
                            self._last_focus_log_time = now
                            self._last_focus_title = w.title
                        else:
                            logger.debug(f"Focused window unchanged: {w.title}")
                        return True
                    except Exception as e:
                        logger.error(f"Error focusing window: {e}")
                        continue
                
                time.sleep(sleep_s)
            
            logger.warning(f"Could not focus window with title: {title_substr}")
            return False
        
        except ImportError:
            logger.warning("pygetwindow not available, cannot focus window")
            return False
    
    def get_window_bbox(self) -> Dict[str, int]:
        """
        Get the bounding box of the focused window or primary screen
        
        Returns:
            Dictionary with left, top, width, height
        """
        if self._window_bbox is not None:
            return self._window_bbox.copy()
        
        # Fallback to primary monitor
        mon = self._get_mss().monitors[1]  # Primary monitor
        return {
            "left": mon["left"],
            "top": mon["top"],
            "width": mon["width"],
            "height": mon["height"]
        }
    
    def capture(self, bbox: Optional[Dict[str, int]] = None) -> np.ndarray:
        """
        Capture a region of the screen
        
        Args:
            bbox: Bounding box to capture (left, top, width, height)
                 If None, captures the focused window or primary screen
        
        Returns:
            Numpy array with captured image in BGR format
        """
        if bbox is None:
            bbox = self.get_window_bbox()
        
        # Check cache
        cache_key = self._get_cache_key(bbox)
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached:
                timestamp, img = cached
                if time.time() - timestamp < self.cache_ttl:
                    return img.copy()
        
        # Convert bbox to mss format
        mss_bbox = {
            "left": bbox["left"],
            "top": bbox["top"],
            "width": bbox["width"],
            "height": bbox["height"]
        }
        
        # Capture screen
        try:
            img = self._get_mss().grab(mss_bbox)
            img_np = np.array(img)[:, :, :3]  # BGR format
            
            # Cache result
            with self._cache_lock:
                self._cache[cache_key] = (time.time(), img_np.copy())
            
            return img_np
        except Exception as e:
            logger.error(f"Error capturing screen: {e}")
            
            # Return black image as fallback
            return np.zeros((bbox["height"], bbox["width"], 3), dtype=np.uint8)
    
    def capture_region(self, roi) -> np.ndarray:
        """
        Capture a specific region of interest
        
        Args:
            roi: Region of interest (ROI object or dict with left, top, width, height)
        
        Returns:
            Numpy array with captured image in BGR format
        """
        if hasattr(roi, 'to_dict'):
            roi_dict = roi.to_dict()
        else:
            roi_dict = roi

        # Normalize ROI coordinates to absolute screen space.
        # Supports modes:
        #  - absolute: use as-is
        #  - relative: add window bbox offset
        #  - percent: multiply by window size then add offset
        # Heuristic fallback: if ROI appears client-relative, translate by window bbox.
        try:
            bbox = self.get_window_bbox()
            l, t, w, h = int(roi_dict.get('left', 0)), int(roi_dict.get('top', 0)), int(roi_dict.get('width', 0)), int(roi_dict.get('height', 0))
            mode = str(roi_dict.get('mode', 'absolute')).lower()
            if mode == 'percent':
                # Re-read as floats
                lf = float(roi_dict.get('left', 0.0)); tf = float(roi_dict.get('top', 0.0))
                wf = float(roi_dict.get('width', 0.0)); hf = float(roi_dict.get('height', 0.0))
                roi_dict = {
                    'left': int(bbox['left'] + lf * bbox['width']),
                    'top': int(bbox['top'] + tf * bbox['height']),
                    'width': int(max(1, wf * bbox['width'])),
                    'height': int(max(1, hf * bbox['height'])),
                    'mode': 'absolute'
                }
            elif mode == 'relative':
                roi_dict = {
                    'left': bbox['left'] + l,
                    'top': bbox['top'] + t,
                    'width': w,
                    'height': h,
                    'mode': 'absolute'
                }
            # Heuristic: treat as absolute if coordinates lie within the absolute window rectangle
            within_abs_window = (
                l >= bbox['left'] - 2 and l <= bbox['left'] + bbox['width'] + 2 and
                t >= bbox['top'] - 2 and t <= bbox['top'] + bbox['height'] + 2
            )
            # Treat as relative if clearly within client area dimensions
            looks_relative = (l < bbox['width'] and t < bbox['height'] and w <= bbox['width'] and h <= bbox['height'])
            if mode not in ('relative', 'percent') and (not within_abs_window and looks_relative):
                roi_dict = {
                    'left': bbox['left'] + l,
                    'top': bbox['top'] + t,
                    'width': w,
                    'height': h,
                    'mode': 'absolute'
                }
        except Exception:
            # Fallback: use as-is
            pass

        return self.capture(roi_dict)
    
    def _get_cache_key(self, bbox: Dict[str, int]) -> str:
        """
        Generate a cache key for a bounding box
        
        Args:
            bbox: Bounding box
        
        Returns:
            Cache key string
        """
        return f"{bbox['left']}_{bbox['top']}_{bbox['width']}_{bbox['height']}"
    
    def clear_cache(self):
        """Clear the capture cache"""
        with self._cache_lock:
            self._cache.clear()
    
    def __del__(self):
        """Clean up resources"""
        try:
            if hasattr(self._tls, 'mss'):
                self._tls.mss.close()
        except Exception:
            pass