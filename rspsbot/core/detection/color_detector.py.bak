"""
Color detection utilities for RSPS Color Bot v3
"""
import logging
import numpy as np
import cv2
from typing import Tuple, List, Dict, Optional, Any, cast
from functools import lru_cache

from ..config import ColorSpec

# Get module logger
logger = logging.getLogger('rspsbot.core.detection.color_detector')

def _lab_delta_e_mask(img_bgr: np.ndarray, target_rgb: Tuple[int, int, int], thr: float) -> np.ndarray:
    """Compute a binary mask where DeltaE76 to target <= thr."""
    try:
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        r, g, b = target_rgb
        sw = np.array([[[b, g, r]]], dtype=np.uint8)
        tgt_lab = cv2.cvtColor(sw, cv2.COLOR_BGR2LAB)[0, 0].astype(np.int16)
        # Use squared distance to avoid sqrt and prevent overflow in int16
        diff = lab.astype(np.int16) - tgt_lab[None, None, :]
        diff_f = diff.astype(np.int32)
        d2 = (
            diff_f[:, :, 0] * diff_f[:, :, 0]
            + diff_f[:, :, 1] * diff_f[:, :, 1]
            + diff_f[:, :, 2] * diff_f[:, :, 2]
        )
        thr = float(max(0.0, thr))
        thr2 = thr * thr
        return ((d2.astype(np.float32) <= thr2).astype(np.uint8) * 255)
    except Exception:
        h, w = img_bgr.shape[:2]
        return np.zeros((h, w), dtype=np.uint8)

def build_mask_precise_small(
    img_bgr: np.ndarray,
    color_spec: ColorSpec,
    config: Optional[Dict[str, Any]] = None,
    step: int = 1,
    min_area: int = 0,
) -> Tuple[np.ndarray, List]:
    """
    Build a stricter mask for small ROIs:
    - Base HSV∩RGB precise mask
    - Apply S/V minima gating (s >= combat_sat_min, v >= combat_val_min)
    - Apply Lab ΔE intersection if configured (combat_lab_tolerance > 0)
    - Apply tunable morphology (combat_morph_open_iters/close)
    """
    small = img_bgr[::step, ::step] if step > 1 else img_bgr

    # Base precise mask (HSV∩RGB)
    mask, _ = build_mask(img_bgr, color_spec, step=step, precise=True, min_area=0)

    # HSV S/V gating
    try:
        sat_min = int((config or {}).get('combat_sat_min', 40))
        val_min = int((config or {}).get('combat_val_min', 40))
        if sat_min > 0 or val_min > 0:
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            s = hsv[:, :, 1]
            v = hsv[:, :, 2]
            s_ok = (s >= sat_min) if sat_min > 0 else np.ones_like(s, dtype=np.uint8)
            v_ok = (v >= val_min) if val_min > 0 else np.ones_like(v, dtype=np.uint8)
            gate = cv2.bitwise_and(s_ok.astype(np.uint8) * 255, v_ok.astype(np.uint8) * 255)
            mask = cv2.bitwise_and(mask, gate)
    except Exception:
        pass

    # Lab ΔE intersection
    try:
        lab_thr = float((config or {}).get('combat_lab_tolerance', 0))
        if lab_thr and lab_thr > 0:
            r, g, b = int(color_spec.rgb[0]), int(color_spec.rgb[1]), int(color_spec.rgb[2])
            lab_mask = _lab_delta_e_mask(small, (r, g, b), lab_thr)
            mask = cv2.bitwise_and(mask, lab_mask)
    except Exception:
        pass

    # Morphology
    try:
        open_it = int((config or {}).get('combat_morph_open_iters', 1))
        close_it = int((config or {}).get('combat_morph_close_iters', 1))
        kernel = np.ones((3, 3), np.uint8)
        if open_it > 0:
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=open_it)
        if close_it > 0:
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=close_it)
    except Exception:
        pass

    # Contours and area filter
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area_scaled = min_area / (step * step if step > 0 else 1)
    filtered = [cnt for cnt in contours if cv2.contourArea(cnt) >= min_area_scaled]
    return mask, filtered if filtered else []

@lru_cache(maxsize=256)
def rgb_to_hsv_cached(r: int, g: int, b: int) -> Tuple[int, int, int]:
    """
    Convert RGB color to HSV using OpenCV with caching
    
    Args:
        r, g, b: RGB color components (0-255)
    
    Returns:
        Tuple of HSV values (H: 0-179, S: 0-255, V: 0-255)
    """
    swatch = np.array([[[b, g, r]]], dtype=np.uint8)  # OpenCV uses BGR input
    hsv = cv2.cvtColor(swatch, cv2.COLOR_BGR2HSV)[0, 0]
    return int(hsv[0]), int(hsv[1]), int(hsv[2])

def build_mask(
    img_bgr: np.ndarray,
    color_spec: ColorSpec,
    step: int = 1,
    precise: bool = True,
    min_area: int = 30
) -> Tuple[np.ndarray, List]:
    """
    Build a binary mask for a single color specification
    
    Args:
        img_bgr: Input image in BGR format
        color_spec: Color specification
        step: Subsampling factor (1 = no subsampling)
        precise: Whether to use both RGB and HSV for precise detection
        min_area: Minimum contour area
    
    Returns:
        Tuple of (mask, contours)
    """
    h, w = img_bgr.shape[:2]
    small = img_bgr[0:h:step, 0:w:step] if step > 1 else img_bgr
    
    # Create HSV mask
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    h0, s0, v0 = rgb_to_hsv_cached(*color_spec.rgb)
    
    # Handle hue wrap-around
    low_h = (h0 - color_spec.tol_h) % 180
    high_h = (h0 + color_spec.tol_h) % 180
    
    if low_h <= high_h:
        lower = np.array([low_h, max(0, s0 - color_spec.tol_s), max(0, v0 - color_spec.tol_v)], dtype=np.uint8)
        upper = np.array([high_h, min(255, s0 + color_spec.tol_s), min(255, v0 + color_spec.tol_v)], dtype=np.uint8)
        mask_hsv = cv2.inRange(hsv, lower, upper)
    else:
        # Handle hue wrap-around (e.g., red spans 170-180 and 0-10)
        lower1 = np.array([0, max(0, s0 - color_spec.tol_s), max(0, v0 - color_spec.tol_v)], dtype=np.uint8)
        upper1 = np.array([high_h, min(255, s0 + color_spec.tol_s), min(255, v0 + color_spec.tol_v)], dtype=np.uint8)
        lower2 = np.array([low_h, max(0, s0 - color_spec.tol_s), max(0, v0 - color_spec.tol_v)], dtype=np.uint8)
        upper2 = np.array([179, min(255, s0 + color_spec.tol_s), min(255, v0 + color_spec.tol_v)], dtype=np.uint8)
        m1 = cv2.inRange(hsv, lower1, upper1)
        m2 = cv2.inRange(hsv, lower2, upper2)
        mask_hsv = cv2.bitwise_or(m1, m2)
    
    # Create RGB mask
    b0, g0, r0 = color_spec.rgb[2], color_spec.rgb[1], color_spec.rgb[0]
    lower_rgb = np.array([max(0, b0 - color_spec.tol_rgb), max(0, g0 - color_spec.tol_rgb), max(0, r0 - color_spec.tol_rgb)], dtype=np.uint8)
    upper_rgb = np.array([min(255, b0 + color_spec.tol_rgb), min(255, g0 + color_spec.tol_rgb), min(255, r0 + color_spec.tol_rgb)], dtype=np.uint8)
    mask_rgb = cv2.inRange(small, lower_rgb, upper_rgb)
    
    # Combine masks
    if color_spec.use_hsv and precise:
        mask = cv2.bitwise_and(mask_hsv, mask_rgb)
    else:
        mask = mask_hsv if color_spec.use_hsv else mask_rgb
    
    # Apply morphological operations
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter by area
    min_area_scaled = min_area / (step * step)
    filtered = [cnt for cnt in contours if cv2.contourArea(cnt) >= min_area_scaled]
    
    return mask, filtered if filtered else []

def build_mask_multi(
    img_bgr: np.ndarray,
    color_specs: List[ColorSpec],
    step: int = 1,
    precise: bool = True,
    min_area: int = 15,
    config: Optional[Dict[str, Any]] = None
) -> Tuple[np.ndarray, List]:
    """
    Build a binary mask for multiple color specifications (OR combination)
    
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
    h, w = img_bgr.shape[:2]
    out_h = h if step <= 1 else max(1, h // step)
    out_w = w if step <= 1 else max(1, w // step)
    if not color_specs:
        return np.zeros((out_h, out_w), dtype=np.uint8), []

    # Start with zero mask
    mask_or: np.ndarray = np.zeros((out_h, out_w), dtype=np.uint8)
    
    # OR masks for each color
    for spec in color_specs:
        m, _ = build_mask(img_bgr, spec, step, precise, min_area=0)
        mask_or = cv2.bitwise_or(mask_or, m)
    
    # Apply additional processing if config is provided
    if config is not None:
        # S/V gating to suppress gray/dark noise
        sat_min = int(config.get('monster_sat_min', 0))
        val_min = int(config.get('monster_val_min', 0))
        
        if sat_min > 0 or val_min > 0:
            small = img_bgr[::step, ::step] if step > 1 else img_bgr
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            s = hsv[:, :, 1]
            v = hsv[:, :, 2]
            
            s_ok = (s >= sat_min) if sat_min > 0 else np.ones_like(s, dtype=np.uint8)
            v_ok = (v >= val_min) if val_min > 0 else np.ones_like(v, dtype=np.uint8)
            
            gate = cv2.bitwise_and(s_ok.astype(np.uint8) * 255, v_ok.astype(np.uint8) * 255)
            mask_or = cv2.bitwise_and(mask_or, gate)
        
        # Exclude tile color region
        if config.get('monster_exclude_tile_color', False):
            tile_color = config.get('tile_color')
            if tile_color:
                from ..config import ColorSpec
                tile_spec = ColorSpec(
                    rgb=tuple(tile_color['rgb']),
                    tol_rgb=tile_color.get('tol_rgb', 8),
                    use_hsv=tile_color.get('use_hsv', True),
                    tol_h=tile_color.get('tol_h', 4),
                    tol_s=tile_color.get('tol_s', 30),
                    tol_v=tile_color.get('tol_v', 30)
                )
                
                tile_mask, _ = build_mask(img_bgr, tile_spec, step, True, min_area=0)
                
                # Dilate tile mask if specified
                dilate_iters = int(config.get('monster_exclude_tile_dilate', 0))
                if dilate_iters > 0:
                    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                    tile_mask = cv2.dilate(tile_mask, k, iterations=dilate_iters)
                
                # Exclude tile pixels from monster mask
                inv = cv2.bitwise_not(tile_mask)
                mask_or = cv2.bitwise_and(mask_or, inv)
        
        # Lab color assist
        if config.get('monster_use_lab_assist', False):
            small = img_bgr[::step, ::step] if step > 1 else img_bgr
            lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
            lab_union: Optional[np.ndarray] = None
            for spec in color_specs:
                # Convert RGB target to Lab
                r, g, b = spec.rgb
                sw = np.array([[[b, g, r]]], dtype=np.uint8)
                tgt_lab = cv2.cvtColor(sw, cv2.COLOR_BGR2LAB)[0, 0].astype(np.int16)
                
                # Compute squared DeltaE (CIE76 approximation) to avoid sqrt/overflow
                diff = lab.astype(np.int16) - tgt_lab[None, None, :]
                diff_f = diff.astype(np.int32)
                d2 = (
                    diff_f[:, :, 0] * diff_f[:, :, 0]
                    + diff_f[:, :, 1] * diff_f[:, :, 1]
                    + diff_f[:, :, 2] * diff_f[:, :, 2]
                )
                thr = float(config.get('monster_lab_tolerance', 18))
                thr2 = thr * thr
                m = (d2.astype(np.float32) <= thr2).astype(np.uint8) * 255
                if lab_union is None:
                    lab_union = m.copy()
                else:
                    lab_union = cv2.bitwise_or(lab_union, m)
            
            # Combine Lab assist with existing mask
            if lab_union is not None:
                mask_or = cv2.bitwise_or(mask_or, lab_union)
    
    # Apply morphological operations
    kernel = np.ones((3, 3), np.uint8)
    
    open_it = 1
    close_it = 1
    
    if config is not None:
        open_it = int(config.get('monster_morph_open_iters', 1))
        close_it = int(config.get('monster_morph_close_iters', 1))
    
    if open_it > 0:
        mask_or = cv2.morphologyEx(mask_or, cv2.MORPH_OPEN, kernel, iterations=open_it)
    
    if close_it > 0:
        mask_or = cv2.morphologyEx(mask_or, cv2.MORPH_CLOSE, kernel, iterations=close_it)
    
    # Find contours
    contours, _ = cv2.findContours(mask_or, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter by area
    min_area_scaled = min_area / (step * step)
    filtered = [cnt for cnt in contours if cv2.contourArea(cnt) >= min_area_scaled]
    
    return mask_or, filtered if filtered else []

def contours_to_screen_points(
    contours: List,
    bbox: Dict[str, int],
    step: int
) -> List[Tuple[int, int]]:
    """
    Convert contour centers (centroids) to absolute screen coordinates
    
    Args:
        contours: List of contours
        bbox: Bounding box of the region
        step: Subsampling factor used during masking
    
    Returns:
        List of (x, y) screen coordinates
    """
    pts = []
    
    if not contours:
        return pts
    
    left, top = bbox["left"], bbox["top"]
    
    for cnt in contours:
        # Calculate centroid
        M = cv2.moments(cnt)
        
        if M["m00"] == 0:
            # Fallback to bounding rect center
            x, y, w, h = cv2.boundingRect(cnt)
            cx_small, cy_small = x + w // 2, y + h // 2
        else:
            # Use centroid
            cx_small = int(M["m10"] / M["m00"])
            cy_small = int(M["m01"] / M["m00"])
        
        # Convert to screen coordinates
        screen_x = left + cx_small * step
        screen_y = top + cy_small * step
        
        pts.append((screen_x, screen_y))
    
    return pts

def closest_contour_to_point(
    contours: List,
    target_xy: Tuple[float, float],
    step: int = 1
) -> Optional[np.ndarray]:
    """
    Find the contour with centroid closest to target point
    
    Args:
        contours: List of contours
        target_xy: Target point (x, y) in screen coordinates
        step: Subsampling factor used during masking
    
    Returns:
        Closest contour or None if no contours
    """
    if not contours:
        return None
    
    # Convert target to small coordinates
    target_x_small = target_xy[0] / step
    target_y_small = target_xy[1] / step
    
    best = None
    best_d2 = None
    
    for c in contours:
        # Calculate centroid
        M = cv2.moments(c)
        
        if M["m00"] == 0:
            continue
        
        cx = M["m10"] / M["m00"]
        cy = M["m01"] / M["m00"]
        
        # Calculate squared distance
        dx = cx - target_x_small
        dy = cy - target_y_small
        d2 = dx * dx + dy * dy
        
        # Update best if closer
        if best is None or best_d2 is None or d2 < best_d2:
            best = c
            best_d2 = d2
    
    # If no valid centroid found, use largest contour
    if best is None and contours:
        best = max(contours, key=lambda c: cv2.contourArea(c))
    
    return best

def largest_contour(contours: List) -> Optional[np.ndarray]:
    """
    Find the largest contour by area
    
    Args:
        contours: List of contours
    
    Returns:
        Largest contour or None if no contours
    """
    if not contours:
        return None
    
    return max(contours, key=lambda c: cv2.contourArea(c))

def random_contour(contours: List) -> Optional[np.ndarray]:
    """
    Select a random contour
    
    Args:
        contours: List of contours
    
    Returns:
        Random contour or None if no contours
    """
    import random
    
    if not contours:
        return None
    
    return random.choice(contours)

def draw_contours(
    img: np.ndarray,
    contours: List,
    color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2
) -> np.ndarray:
    """
    Draw contours on an image
    
    Args:
        img: Input image
        contours: List of contours
        color: BGR color tuple
        thickness: Line thickness
    
    Returns:
        Image with contours drawn
    """
    result = img.copy()
    cv2.drawContours(result, contours, -1, color, thickness)
    return result

def draw_points(
    img: np.ndarray,
    points: List[Tuple[int, int]],
    color: Tuple[int, int, int] = (0, 0, 255),
    radius: int = 5
) -> np.ndarray:
    """
    Draw points on an image
    
    Args:
        img: Input image
        points: List of (x, y) points
        color: BGR color tuple
        radius: Circle radius
    
    Returns:
        Image with points drawn
    """
    result = img.copy()
    
    for x, y in points:
        cv2.circle(result, (x, y), radius, color, -1)
    
    return result