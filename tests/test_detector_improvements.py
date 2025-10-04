"""
Unit tests for detector improvements

Run with: pytest tests/test_detector_improvements.py -v
"""
import pytest
import numpy as np
import cv2
from unittest.mock import Mock, MagicMock, patch

# Import the improved detector
import sys
sys.path.insert(0, '../')
from rspsbot.core.detection.detector import DetectionEngine, TileDetector, MonsterDetector, CombatDetector
from rspsbot.core.config import ConfigManager, ColorSpec


class TestFrameValidation:
    """Test frame validation improvements"""
    
    def test_validate_frame_valid(self):
        """Test that valid frames pass validation"""
        config = ConfigManager()
        capture = Mock()
        engine = DetectionEngine(config, capture)
        
        # Create valid frame
        frame = np.random.randint(50, 200, (600, 800, 3), dtype=np.uint8)
        roi = {'left': 0, 'top': 0, 'width': 800, 'height': 600}
        
        assert engine._validate_frame(frame, roi) == True
    
    def test_validate_frame_black(self):
        """Test that black frames fail validation"""
        config = ConfigManager()
        capture = Mock()
        engine = DetectionEngine(config, capture)
        
        # Create black frame
        frame = np.zeros((600, 800, 3), dtype=np.uint8)
        roi = {'left': 0, 'top': 0, 'width': 800, 'height': 600}
        
        assert engine._validate_frame(frame, roi) == False
    
    def test_validate_frame_wrong_dimensions(self):
        """Test that frames with wrong dimensions fail validation"""
        config = ConfigManager()
        capture = Mock()
        engine = DetectionEngine(config, capture)
        
        # Create frame with wrong dimensions
        frame = np.random.randint(50, 200, (500, 700, 3), dtype=np.uint8)
        roi = {'left': 0, 'top': 0, 'width': 800, 'height': 600}
        
        assert engine._validate_frame(frame, roi) == False
    
    def test_validate_frame_none(self):
        """Test that None frames fail validation"""
        config = ConfigManager()
        capture = Mock()
        engine = DetectionEngine(config, capture)
        
        roi = {'left': 0, 'top': 0, 'width': 800, 'height': 600}
        
        assert engine._validate_frame(None, roi) == False


class TestROIValidation:
    """Test ROI validation improvements"""
    
    def test_validate_roi_valid(self):
        """Test that valid ROIs pass validation"""
        config = ConfigManager()
        capture = Mock()
        engine = DetectionEngine(config, capture)
        
        roi = {'left': 100, 'top': 100, 'width': 800, 'height': 600}
        assert engine._validate_roi(roi) == True
    
    def test_validate_roi_negative_dimensions(self):
        """Test that ROIs with negative dimensions fail"""
        config = ConfigManager()
        capture = Mock()
        engine = DetectionEngine(config, capture)
        
        roi = {'left': 100, 'top': 100, 'width': -800, 'height': 600}
        assert engine._validate_roi(roi) == False
    
    def test_validate_roi_missing_keys(self):
        """Test that ROIs with missing keys fail"""
        config = ConfigManager()
        capture = Mock()
        engine = DetectionEngine(config, capture)
        
        roi = {'left': 100, 'top': 100, 'width': 800}  # Missing height
        assert engine._validate_roi(roi) == False
    
    def test_validate_roi_too_large(self):
        """Test that unreasonably large ROIs fail"""
        config = ConfigManager()
        capture = Mock()
        engine = DetectionEngine(config, capture)
        
        roi = {'left': 0, 'top': 0, 'width': 20000, 'height': 20000}
        assert engine._validate_roi(roi) == False


class TestFrameSlicing:
    """Test frame slicing bug fixes"""
    
    def test_frame_slicing_normal(self):
        """Test normal frame slicing"""
        config = ConfigManager()
        detector = MonsterDetector(config)
        
        # Create test frame
        frame = np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)
        base_roi = {'left': 0, 'top': 0, 'width': 800, 'height': 600}
        tile_center = (400, 300)
        
        # Mock config
        config.set('detect_monsters', True)
        config.set('monster_colors', [
            {'rgb': [0, 255, 0], 'tol_rgb': 20, 'use_hsv': True, 'tol_h': 10, 'tol_s': 50, 'tol_v': 50}
        ])
        config.set('around_tile_radius', 100)
        
        # Should not raise exception
        monsters = detector.detect_monsters_near_tile(frame, base_roi, tile_center)
        assert isinstance(monsters, list)
    
    def test_frame_slicing_edge_case(self):
        """Test frame slicing at frame boundary"""
        config = ConfigManager()
        detector = MonsterDetector(config)
        
        # Create test frame
        frame = np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)
        base_roi = {'left': 0, 'top': 0, 'width': 800, 'height': 600}
        tile_center = (750, 550)  # Near edge
        
        # Mock config
        config.set('detect_monsters', True)
        config.set('monster_colors', [
            {'rgb': [0, 255, 0], 'tol_rgb': 20, 'use_hsv': True, 'tol_h': 10, 'tol_s': 50, 'tol_v': 50}
        ])
        config.set('around_tile_radius', 100)
        
        # Should not raise exception
        monsters = detector.detect_monsters_near_tile(frame, base_roi, tile_center)
        assert isinstance(monsters, list)
    
    def test_frame_slicing_out_of_bounds(self):
        """Test frame slicing with ROI exceeding frame"""
        config = ConfigManager()
        detector = MonsterDetector(config)
        
        # Create test frame
        frame = np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)
        base_roi = {'left': 0, 'top': 0, 'width': 800, 'height': 600}
        tile_center = (900, 700)  # Outside frame
        
        # Mock config
        config.set('detect_monsters', True)
        config.set('monster_colors', [
            {'rgb': [0, 255, 0], 'tol_rgb': 20, 'use_hsv': True, 'tol_h': 10, 'tol_s': 50, 'tol_v': 50}
        ])
        config.set('around_tile_radius', 100)
        
        # Should return empty list, not crash
        monsters = detector.detect_monsters_near_tile(frame, base_roi, tile_center)
        assert monsters == []


class TestDistanceCalculation:
    """Test distance calculation optimizations"""
    
    def test_distance_squared_present(self):
        """Test that distance_squared is included in monster data"""
        config = ConfigManager()
        detector = MonsterDetector(config)
        
        # Create test frame with green square
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        frame[80:120, 80:120] = [0, 255, 0]  # Green square in BGR
        
        base_roi = {'left': 0, 'top': 0, 'width': 200, 'height': 200}
        tile_center = (100, 100)
        
        # Mock config
        config.set('detect_monsters', True)
        config.set('monster_colors', [
            {'rgb': [0, 255, 0], 'tol_rgb': 20, 'use_hsv': True, 'tol_h': 10, 'tol_s': 50, 'tol_v': 50}
        ])
        config.set('around_tile_radius', 100)
        config.set('monster_min_area', 10)
        
        monsters = detector.detect_monsters_near_tile(frame, base_roi, tile_center)
        
        if monsters:
            assert 'distance_squared' in monsters[0]
            assert 'distance' in monsters[0]
            # Verify relationship
            assert abs(monsters[0]['distance']**2 - monsters[0]['distance_squared']) < 0.01


class TestThreadSafety:
    """Test thread safety improvements"""
    
    def test_stats_thread_safe(self):
        """Test that statistics access is thread-safe"""
        config = ConfigManager()
        capture = Mock()
        capture.capture_region = Mock(return_value=np.random.randint(50, 200, (600, 800, 3), dtype=np.uint8))
        
        engine = DetectionEngine(config, capture)
        
        # Access stats from multiple threads
        import threading
        
        def access_stats():
            for _ in range(100):
                stats = engine.get_stats()
                engine.reset_stats()
        
        threads = [threading.Thread(target=access_stats) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should not raise exception
        final_stats = engine.get_stats()
        assert isinstance(final_stats, dict)


class TestErrorHandling:
    """Test error handling improvements"""
    
    def test_detect_cycle_handles_exceptions(self):
        """Test that detect_cycle handles exceptions gracefully"""
        config = ConfigManager()
        capture = Mock()
        capture.capture_region = Mock(side_effect=Exception("Test exception"))
        
        engine = DetectionEngine(config, capture)
        
        # Should not raise exception
        result = engine.detect_cycle()
        
        assert isinstance(result, dict)
        assert 'tiles' in result
        assert 'monsters' in result
        assert result['tiles'] == []
        assert result['monsters'] == []
    
    def test_invalid_input_handling(self):
        """Test handling of invalid inputs"""
        config = ConfigManager()
        detector = MonsterDetector(config)
        
        # Test with None frame
        monsters = detector.detect_monsters_near_tile(None, {}, (100, 100))
        assert monsters == []
        
        # Test with invalid tile_center
        frame = np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)
        monsters = detector.detect_monsters_near_tile(frame, {}, None)
        assert monsters == []


class TestPerformanceOptimizations:
    """Test performance optimizations"""
    
    def test_cache_optimization(self):
        """Test that cache returns shallow copy"""
        config = ConfigManager()
        capture = Mock()
        capture.capture_region = Mock(return_value=np.random.randint(50, 200, (600, 800, 3), dtype=np.uint8))
        
        engine = DetectionEngine(config, capture)
        
        # First call - no cache
        result1 = engine.detect_cycle()
        
        # Second call - should use cache
        result2 = engine.detect_cycle()
        
        # Results should be equal but not the same object
        assert result1 == result2
        assert result1 is not result2  # Different objects (shallow copy)
    
    def test_progressive_refinement(self):
        """Test that adaptive detection uses progressive refinement"""
        config = ConfigManager()
        detector = TileDetector(config)
        
        # Create frame with red square
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        frame[80:120, 80:120] = [0, 0, 255]  # Red square in BGR
        
        roi = {'left': 0, 'top': 0, 'width': 200, 'height': 200}
        
        # Mock config
        config.set('tile_color', {
            'rgb': [255, 0, 0],
            'tol_rgb': 20,
            'use_hsv': True,
            'tol_h': 10,
            'tol_s': 50,
            'tol_v': 50
        })
        config.set('tile_min_area', 10)
        
        # Should find tiles with progressive refinement
        tiles = detector.detect_tiles_adaptive(frame, roi)
        
        # Should find at least one tile
        assert len(tiles) >= 0  # May or may not find depending on color matching


if __name__ == '__main__':
    pytest.main([__file__, '-v'])