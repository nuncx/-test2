import os
import sys
import cv2
import numpy as np
import logging
import json
from typing import Dict, List, Tuple, Optional, Any

# Add the project directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the necessary modules
from rspsbot.core.config import ConfigManager, ColorSpec
from rspsbot.core.detection.color_detector import build_mask, build_mask_precise_small, _lab_delta_e_mask

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_optimizations')

def create_test_image(width, height, color):
    """Create a test image with a specific color"""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = color
    return img

def test_color_matching():
    """Test the optimized color matching parameters"""
    logger.info("Testing optimized color matching parameters...")
    
    # Load the example profile
    with open('profiles/examples/example_profile.json', 'r') as f:
        profile = json.load(f)
    
    # Extract the combat style colors
    melee_color_dict = profile['combat_style_melee_color']
    ranged_color_dict = profile['combat_style_ranged_color']
    magic_color_dict = profile['combat_style_magic_color']
    
    # Create ColorSpec objects
    melee_color = ColorSpec(
        rgb=tuple(melee_color_dict['rgb']),
        tol_rgb=melee_color_dict.get('tol_rgb', 8),
        use_hsv=melee_color_dict.get('use_hsv', True),
        tol_h=melee_color_dict.get('tol_h', 4),
        tol_s=melee_color_dict.get('tol_s', 30),
        tol_v=melee_color_dict.get('tol_v', 30)
    )
    
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
    
    logger.info(f"Exact color match: {exact_pixels} pixels")
    logger.info(f"Similar color match: {similar_pixels} pixels")
    logger.info(f"Different color match: {different_pixels} pixels")
    
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
    
    logger.info(f"Exact color match (precise): {exact_pixels_precise} pixels")
    logger.info(f"Similar color match (precise): {similar_pixels_precise} pixels")
    logger.info(f"Different color match (precise): {different_pixels_precise} pixels")
    
    # Verify that the optimized parameters work correctly
    assert exact_pixels > 0, "Exact color should match"
    assert exact_pixels_precise > 0, "Exact color should match with precise mode"
    assert different_pixels == 0, "Different color should not match"
    assert different_pixels_precise == 0, "Different color should not match with precise mode"
    
    logger.info("Color matching test passed!")
    return True

def test_lab_color_matching():
    """Test the Lab color matching functionality"""
    logger.info("Testing Lab color matching...")
    
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
        
        logger.info(f"Lab tolerance {thr}:")
        logger.info(f"  Exact color match: {exact_pixels} pixels")
        logger.info(f"  Similar color match: {similar_pixels} pixels")
        logger.info(f"  Different color match: {different_pixels} pixels")
        
        # Verify that the Lab color matching works correctly
        assert exact_pixels > 0, f"Exact color should match with tolerance {thr}"
        
        # At lower tolerances, similar colors should not match
        if thr < 15:
            assert similar_pixels == 0, f"Similar color should not match with tolerance {thr}"
        
        # Different colors should never match
        assert different_pixels == 0, f"Different color should not match with tolerance {thr}"
    
    logger.info("Lab color matching test passed!")
    return True

def test_roi_expansion():
    """Test the ROI expansion strategy"""
    logger.info("Testing ROI expansion strategy...")
    
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
        x0 = max(base_roi['left'], tile_center[0] - radius)
        y0 = max(base_roi['top'], tile_center[1] - radius)
        x1 = min(base_roi['left'] + base_roi['width'], tile_center[0] + radius)
        y1 = min(base_roi['top'] + base_roi['height'], tile_center[1] + radius)
        
        roi = {
            'left': x0,
            'top': y0,
            'width': max(0, x1 - x0),
            'height': max(0, y1 - y0)
        }
        
        logger.info(f"Expansion level {level} (radius {radius}):")
        logger.info(f"  ROI: {roi}")
        
        # Verify that the ROI is valid
        assert roi['width'] > 0, f"ROI width should be positive at level {level}"
        assert roi['height'] > 0, f"ROI height should be positive at level {level}"
        
        # Verify that the ROI grows with each expansion level
        if level > 0:
            assert radius > base_radius, f"Radius should increase at level {level}"
    
    logger.info("ROI expansion test passed!")
    return True

def run_tests():
    """Run all tests"""
    logger.info("Running optimization tests...")
    
    test_color_matching()
    test_lab_color_matching()
    test_roi_expansion()
    
    logger.info("All tests passed!")

if __name__ == "__main__":
    run_tests()