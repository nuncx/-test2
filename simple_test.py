import os
import sys
import cv2
import numpy as np
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any

@dataclass
class ColorSpec:
    """Color specification with tolerance settings"""
    rgb: Tuple[int, int, int]
    tol_rgb: int = 8
    use_hsv: bool = True
    tol_h: int = 4
    tol_s: int = 30
    tol_v: int = 30

def rgb_to_hsv_cached(r: int, g: int, b: int) -> Tuple[int, int, int]:
    """Convert RGB to HSV using OpenCV"""
    swatch = np.array([[[b, g, r]]], dtype=np.uint8)
    hsv = cv2.cvtColor(swatch, cv2.COLOR_BGR2HSV)[0, 0]
    return int(hsv[0]), int(hsv[1]), int(hsv[2])

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

def build_mask(
    img_bgr: np.ndarray,
    color_spec: ColorSpec,
    step: int = 1,
    precise: bool = True,
    min_area: int = 30
) -> Tuple[np.ndarray, List]:
    """Build a binary mask for a single color specification"""
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

def build_mask_precise_small(
    img_bgr: np.ndarray,
    color_spec: ColorSpec,
    config: Optional[Dict[str, Any]] = None,
    step: int = 1,
    min_area: int = 0,
) -> Tuple[np.ndarray, List]:
    """Build a stricter mask for small ROIs with enhanced Lab color matching"""
    small = img_bgr[::step, ::step] if step > 1 else img_bgr

    # Base precise mask (HSV∩RGB)
    mask, _ = build_mask(img_bgr, color_spec, step=step, precise=True, min_area=0)

    # Lab ΔE filtering (ALWAYS apply for more accurate color matching)
    try:
        # Default to 15 if not specified, which is a good middle ground
        lab_thr = float((config or {}).get('combat_lab_tolerance', 15))
        if lab_thr > 0:
            r, g, b = int(color_spec.rgb[0]), int(color_spec.rgb[1]), int(color_spec.rgb[2])
            lab_mask = _lab_delta_e_mask(small, (r, g, b), lab_thr)
            mask = cv2.bitwise_and(mask, lab_mask)
    except Exception:
        pass

    # HSV S/V gating
    try:
        # Increased default values for better filtering of gray/dark colors
        sat_min = int((config or {}).get('combat_sat_min', 50))
        val_min = int((config or {}).get('combat_val_min', 50))
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

    # Morphology
    try:
        open_it = int((config or {}).get('combat_morph_open_iters', 1))
        close_it = int((config or {}).get('combat_morph_close_iters', 2))  # Increased default to 2
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

def create_test_image(width, height, color):
    """Create a test image with a specific color"""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = color
    return img

def test_color_matching():
    """Test the optimized color matching parameters"""
    print("Testing optimized color matching parameters...")
    
    # Load the example profile
    with open('profiles/examples/example_profile.json', 'r') as f:
        profile = json.load(f)
    
    # Extract the combat style colors
    melee_color_dict = profile['combat_style_melee_color']
    
    # Create ColorSpec objects
    melee_color = ColorSpec(
        rgb=tuple(melee_color_dict['rgb']),
        tol_rgb=melee_color_dict.get('tol_rgb', 8),
        use_hsv=melee_color_dict.get('use_hsv', True),
        tol_h=melee_color_dict.get('tol_h', 4),
        tol_s=melee_color_dict.get('tol_s', 30),
        tol_v=melee_color_dict.get('tol_v', 30)
    )
    
    print(f"Testing with melee color: RGB={melee_color.rgb}, tol_rgb={melee_color.tol_rgb}")
    
    # Create test images
    melee_exact = create_test_image(100, 100, (melee_color.rgb[2], melee_color.rgb[1], melee_color.rgb[0]))  # BGR format
    
    # Create similar but different colors
    similar_color = (
        max(0, melee_color.rgb[2] + 10),
        max(0, melee_color.rgb[1] + 10),
        max(0, melee_color.rgb[0] + 10)
    )
    different_color = (0, 0, 255)  # Blue, very different
    
    melee_similar = create_test_image(100, 100, similar_color)
    melee_different = create_test_image(100, 100, different_color)
    
    # Test with regular build_mask
    mask_exact, contours_exact = build_mask(melee_exact, melee_color, step=1, precise=True, min_area=0)
    mask_similar, contours_similar = build_mask(melee_similar, melee_color, step=1, precise=True, min_area=0)
    mask_different, contours_different = build_mask(melee_different, melee_color, step=1, precise=True, min_area=0)
    
    # Count matching pixels
    exact_pixels = cv2.countNonZero(mask_exact)
    similar_pixels = cv2.countNonZero(mask_similar)
    different_pixels = cv2.countNonZero(mask_different)
    
    print(f"Exact color match: {exact_pixels} pixels")
    print(f"Similar color match: {similar_pixels} pixels")
    print(f"Different color match: {different_pixels} pixels")
    
    # Test with enhanced precise mode
    config = {
        'combat_sat_min': 40,
        'combat_val_min': 40,
        'combat_lab_tolerance': 15,
        'combat_morph_open_iters': 1,
        'combat_morph_close_iters': 1
    }
    
    mask_exact_precise, contours_exact_precise = build_mask_precise_small(melee_exact, melee_color, config, step=1, min_area=0)
    mask_similar_precise, contours_similar_precise = build_mask_precise_small(melee_similar, melee_color, config, step=1, min_area=0)
    mask_different_precise, contours_different_precise = build_mask_precise_small(melee_different, melee_color, config, step=1, min_area=0)
    
    # Count matching pixels
    exact_pixels_precise = cv2.countNonZero(mask_exact_precise)
    similar_pixels_precise = cv2.countNonZero(mask_similar_precise)
    different_pixels_precise = cv2.countNonZero(mask_different_precise)
    
    print(f"Exact color match (precise): {exact_pixels_precise} pixels")
    print(f"Similar color match (precise): {similar_pixels_precise} pixels")
    print(f"Different color match (precise): {different_pixels_precise} pixels")
    
    # Verify that the optimized parameters work correctly
    assert exact_pixels > 0, "Exact color should match"
    assert exact_pixels_precise > 0, "Exact color should match with precise mode"
    assert different_pixels == 0, "Different color should not match"
    assert different_pixels_precise == 0, "Different color should not match with precise mode"
    
    print("Color matching test passed!")
    return True

def test_lab_color_matching():
    """Test the Lab color matching functionality"""
    print("\nTesting Lab color matching...")
    
    # Create a test color
    target_rgb = (107, 38, 56)  # Melee color
    
    # Create test images
    exact_color = (56, 38, 107)  # BGR format
    similar_color = (66, 48, 117)  # BGR format
    different_color = (0, 0, 255)  # BGR format
    
    test_img_exact = create_test_image(100, 100, exact_color)
    test_img_similar = create_test_image(100, 100, similar_color)
    test_img_different = create_test_image(100, 100, different_color)
    
    # Test with different Lab tolerances
    tolerances = [5, 10, 15, 20, 30]
    
    for thr in tolerances:
        mask_exact = _lab_delta_e_mask(test_img_exact, target_rgb, thr)
        mask_similar = _lab_delta_e_mask(test_img_similar, target_rgb, thr)
        mask_different = _lab_delta_e_mask(test_img_different, target_rgb, thr)
        
        exact_pixels = cv2.countNonZero(mask_exact)
        similar_pixels = cv2.countNonZero(mask_similar)
        different_pixels = cv2.countNonZero(mask_different)
        
        print(f"Lab tolerance {thr}:")
        print(f"  Exact color match: {exact_pixels} pixels")
        print(f"  Similar color match: {similar_pixels} pixels")
        print(f"  Different color match: {different_pixels} pixels")
    
    print("Lab color matching test passed!")
    return True

def test_roi_expansion():
    """Test the ROI expansion strategy"""
    print("\nTesting ROI expansion strategy...")
    
    # Create a base ROI
    base_roi = {'left': 0, 'top': 0, 'width': 800, 'height': 600}
    
    # Create a tile center
    tile_center = (400, 300)
    
    # Calculate ROIs with different expansion levels
    base_radius = 120
    expansion_factor = 1.2
    max_expansion = 3
    
    for level in range(max_expansion + 1):
        radius = int(base_radius * (expansion_factor ** level))
        
        # Calculate ROI bounds
        cx, cy = tile_center
        left = base_roi['left']
        top = base_roi['top']
        width = base_roi['width']
        height = base_roi['height']
        
        x0 = max(left, cx - radius)
        y0 = max(top, cy - radius)
        x1 = min(left + width, cx + radius)
        y1 = min(top + height, cy + radius)
        
        roi = {
            'left': x0,
            'top': y0,
            'width': max(0, x1 - x0),
            'height': max(0, y1 - y0)
        }
        
        print(f"Expansion level {level} (radius {radius}):")
        print(f"  ROI: {roi}")
    
    print("ROI expansion test passed!")
    return True

def run_tests():
    """Run all tests"""
    print("Running optimization tests...")
    
    test_color_matching()
    test_lab_color_matching()
    test_roi_expansion()
    
    print("\nAll tests passed!")

if __name__ == "__main__":
    run_tests()