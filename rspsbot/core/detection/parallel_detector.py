"""
Parallel color detection implementation for RSPS Color Bot v3
"""
import logging
import numpy as np
import cv2
from typing import Tuple, List, Dict, Optional, Any
import time
import threading

from ..config import ColorSpec, ROI
from .color_detector import build_mask, build_mask_multi, contours_to_screen_points
from ...utils.threading import ThreadPoolManager, TaskResult

# Get module logger
logger = logging.getLogger('rspsbot.core.detection.parallel_detector')

class ParallelDetector:
    """
    Parallel implementation of color detection
    
    This class uses a thread pool to parallelize the color detection process,
    significantly improving performance on multi-core systems.
    """
    
    def __init__(self, num_workers: int = None, region_size: int = 200):
        """
        Initialize the parallel detector
        
        Args:
            num_workers: Number of worker threads (None for CPU count)
            region_size: Size of image regions for parallel processing
        """
        self.thread_pool = ThreadPoolManager(num_workers=num_workers)
        self.region_size = region_size
        self.thread_pool.start()
        logger.info(f"Parallel detector initialized with {self.thread_pool.num_workers} workers")
    
    def shutdown(self):
        """Shutdown the thread pool"""
        self.thread_pool.shutdown()
    
    def detect_color_parallel(
        self,
        img_bgr: np.ndarray,
        color_spec: ColorSpec,
        step: int = 1,
        precise: bool = True,
        min_area: int = 30
    ) -> Tuple[np.ndarray, List]:
        """
        Detect a single color in parallel
        
        Args:
            img_bgr: Input image in BGR format
            color_spec: Color specification
            step: Subsampling factor (1 = no subsampling)
            precise: Whether to use both RGB and HSV for precise detection
            min_area: Minimum contour area
        
        Returns:
            Tuple of (mask, contours)
        """
        # Split image into regions
        regions = self._split_image(img_bgr)
        region_count = len(regions)
        
        if region_count <= 1:
            # For small images, just use the regular detector
            return build_mask(img_bgr, color_spec, step, precise, min_area)
        
        # Submit tasks for each region
        task_ids = []
        for i, (region, (x, y, w, h)) in enumerate(regions):
            task_id = self.thread_pool.submit_task(
                build_mask,
                region,
                color_spec,
                step,
                precise,
                0  # Use 0 for min_area as we'll filter later
            )
            task_ids.append((task_id, (x, y, w, h)))
        
        # Get results
        results = {}
        for task_id, region_info in task_ids:
            result = self.thread_pool.get_result(task_id)
            if result and result.success:
                results[region_info] = result.result
        
        # Combine masks and contours
        combined_mask, combined_contours = self._combine_results(
            results, img_bgr.shape[:2], min_area, step
        )
        
        return combined_mask, combined_contours
    
    def detect_colors_parallel(
        self,
        img_bgr: np.ndarray,
        color_specs: List[ColorSpec],
        step: int = 1,
        precise: bool = True,
        min_area: int = 15,
        config: Dict = None
    ) -> Tuple[np.ndarray, List]:
        """
        Detect multiple colors in parallel
        
        Args:
            img_bgr: Input image in BGR format
            color_specs: List of color specifications
            step: Subsampling factor (1 = no subsampling)
            precise: Whether to use both RGB and HSV for precise detection
            min_area: Minimum contour area
            config: Additional configuration parameters
        
        Returns:
            Tuple of (mask, contours)
        """
        if not color_specs:
            h, w = img_bgr.shape[:2]
            out_h = h if step <= 1 else (h // step)
            out_w = w if step <= 1 else (w // step)
            return np.zeros((out_h, out_w), dtype=np.uint8), []
        
        # Split image into regions
        regions = self._split_image(img_bgr)
        region_count = len(regions)
        
        if region_count <= 1:
            # For small images, just use the regular detector
            return build_mask_multi(img_bgr, color_specs, step, precise, min_area, config)
        
        # Submit tasks for each region
        task_ids = []
        for i, (region, (x, y, w, h)) in enumerate(regions):
            task_id = self.thread_pool.submit_task(
                build_mask_multi,
                region,
                color_specs,
                step,
                precise,
                0,  # Use 0 for min_area as we'll filter later
                config
            )
            task_ids.append((task_id, (x, y, w, h)))
        
        # Get results
        results = {}
        for task_id, region_info in task_ids:
            result = self.thread_pool.get_result(task_id)
            if result and result.success:
                results[region_info] = result.result
        
        # Combine masks and contours
        combined_mask, combined_contours = self._combine_results(
            results, img_bgr.shape[:2], min_area, step
        )
        
        return combined_mask, combined_contours
    
    def _split_image(self, img: np.ndarray) -> List[Tuple[np.ndarray, Tuple[int, int, int, int]]]:
        """
        Split an image into regions for parallel processing
        
        Args:
            img: Input image
        
        Returns:
            List of (region, (x, y, width, height)) tuples
        """
        h, w = img.shape[:2]
        regions = []
        
        # If image is smaller than region size, return the whole image
        if w <= self.region_size and h <= self.region_size:
            return [(img, (0, 0, w, h))]
        
        # Calculate number of regions in each dimension
        num_x = max(1, w // self.region_size)
        num_y = max(1, h // self.region_size)
        
        # Calculate actual region size
        region_w = w // num_x
        region_h = h // num_y
        
        # Create regions with 10% overlap
        overlap_x = max(1, int(region_w * 0.1))
        overlap_y = max(1, int(region_h * 0.1))
        
        for y in range(0, h - region_h + 1, region_h - overlap_y):
            if y + region_h > h:
                y = h - region_h
            
            for x in range(0, w - region_w + 1, region_w - overlap_x):
                if x + region_w > w:
                    x = w - region_w
                
                # Extract region
                region = img[y:y+region_h, x:x+region_w]
                regions.append((region, (x, y, region_w, region_h)))
        
        return regions
    
    def _combine_results(
        self,
        results: Dict[Tuple[int, int, int, int], Tuple[np.ndarray, List]],
        img_shape: Tuple[int, int],
        min_area: int,
        step: int
    ) -> Tuple[np.ndarray, List]:
        """
        Combine results from multiple regions
        
        Args:
            results: Dictionary mapping region info to (mask, contours)
            img_shape: Shape of the original image (height, width)
            min_area: Minimum contour area
            step: Subsampling factor
        
        Returns:
            Tuple of (combined_mask, combined_contours)
        """
        h, w = img_shape
        out_h = h if step <= 1 else (h // step)
        out_w = w if step <= 1 else (w // step)
        
        # Create empty mask
        combined_mask = np.zeros((out_h, out_w), dtype=np.uint8)
        
        # Combine masks and adjust contours
        all_contours = []
        
        for (x, y, region_w, region_h), (mask, contours) in results.items():
            # Calculate region coordinates in output mask
            x_out = x if step <= 1 else (x // step)
            y_out = y if step <= 1 else (y // step)
            region_w_out = region_w if step <= 1 else (region_w // step)
            region_h_out = region_h if step <= 1 else (region_h // step)
            
            # Ensure we don't go out of bounds
            region_w_out = min(region_w_out, out_w - x_out)
            region_h_out = min(region_h_out, out_h - y_out)
            
            # Copy mask to combined mask
            mask_region = mask[:region_h_out, :region_w_out]
            combined_mask[y_out:y_out+region_h_out, x_out:x_out+region_w_out] = \
                cv2.bitwise_or(combined_mask[y_out:y_out+region_h_out, x_out:x_out+region_w_out], mask_region)
            
            # Adjust contour coordinates
            for contour in contours:
                # Shift contour coordinates
                shifted_contour = contour.copy()
                shifted_contour[:, :, 0] += x_out
                shifted_contour[:, :, 1] += y_out
                all_contours.append(shifted_contour)
        
        # Find contours in the combined mask to merge overlapping regions
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter by area
        min_area_scaled = min_area / (step * step)
        filtered_contours = [cnt for cnt in contours if cv2.contourArea(cnt) >= min_area_scaled]
        
        return combined_mask, filtered_contours
    
    def detect_in_roi(
        self,
        img_bgr: np.ndarray,
        roi: ROI,
        color_specs: List[ColorSpec],
        step: int = 1,
        precise: bool = True,
        min_area: int = 15,
        config: Dict = None
    ) -> Tuple[np.ndarray, List, List[Tuple[int, int]]]:
        """
        Detect colors within a region of interest
        
        Args:
            img_bgr: Input image in BGR format
            roi: Region of interest
            color_specs: List of color specifications
            step: Subsampling factor (1 = no subsampling)
            precise: Whether to use both RGB and HSV for precise detection
            min_area: Minimum contour area
            config: Additional configuration parameters
        
        Returns:
            Tuple of (mask, contours, points)
        """
        # Extract ROI
        x, y, w, h = roi.left, roi.top, roi.width, roi.height
        
        # Ensure ROI is within image bounds
        img_h, img_w = img_bgr.shape[:2]
        x = max(0, min(x, img_w - 1))
        y = max(0, min(y, img_h - 1))
        w = max(1, min(w, img_w - x))
        h = max(1, min(h, img_h - y))
        
        # Extract ROI image
        roi_img = img_bgr[y:y+h, x:x+w]
        
        # Detect colors in ROI
        mask, contours = self.detect_colors_parallel(
            roi_img, color_specs, step, precise, min_area, config
        )
        
        # Convert contours to screen points
        bbox = {"left": x, "top": y}
        points = contours_to_screen_points(contours, bbox, step)
        
        return mask, contours, points
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.shutdown()