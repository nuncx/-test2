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
    
    def __init__(self, cache_ttl: float = 0.05):
        """
        Initialize the capture service
        
        Args:
            cache_ttl: Time-to-live for cached captures in seconds
        """
        # MSS is not thread-safe, so we use thread-local storage
        self._tls = threading.local()
        
        # Cache settings
        self.cache_ttl = cache_ttl
        self._cache = {}
        self._cache_lock = threading.RLock()
        
        # Window information
        self._window_bbox = None
        
        logger.info("Capture service initialized")
    
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
                        
                        logger.info(f"Focused window: {w.title}")
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
        
        return self.capture(roi_dict)

    def capture_healthcheck(self, roi: Optional[Dict[str, int]] = None) -> Dict[str, float]:
        """
        Capture once and report basic stats to detect black/blank frames.

        Returns a dict with mean, std, and nonzero_ratio to help detect if the
        screen went black due to display off or locking.
        """
        frame = self.capture(roi or self.get_window_bbox())
        # Compute statistics
        mean_val = float(frame.mean()) if frame.size else 0.0
        std_val = float(frame.std()) if frame.size else 0.0
        nonzero_ratio = float((frame > 0).any(axis=2).mean()) if frame.size else 0.0
        return {"mean": mean_val, "std": std_val, "nonzero_ratio": nonzero_ratio}
    
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