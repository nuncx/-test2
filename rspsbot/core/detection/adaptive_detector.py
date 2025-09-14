"""
Adaptive detection algorithms for RSPS Color Bot v3
"""
import logging
import numpy as np
import cv2
import time
import json
import os
from typing import Tuple, List, Dict, Optional, Any, Union
from dataclasses import dataclass, field
from pathlib import Path

from ..config import ColorSpec, ROI
from .color_detector import build_mask, build_mask_multi, contours_to_screen_points
from .parallel_detector import ParallelDetector

# Get module logger
logger = logging.getLogger('rspsbot.core.detection.adaptive_detector')

@dataclass
class DetectionResult:
    """
    Detection result data class
    """
    success: bool = False
    contours: List = field(default_factory=list)
    points: List[Tuple[int, int]] = field(default_factory=list)
    execution_time: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0

@dataclass
class EnvironmentCondition:
    """
    Environment condition data class
    """
    lighting_level: float = 0.0  # 0.0 (dark) to 1.0 (bright)
    contrast_level: float = 0.0  # 0.0 (low) to 1.0 (high)
    noise_level: float = 0.0     # 0.0 (clean) to 1.0 (noisy)
    color_scheme: str = "unknown"  # "light", "dark", "custom"
    game_area: str = "unknown"    # "wilderness", "city", "dungeon", etc.

class ParameterSet:
    """
    Detection parameter set
    """
    
    def __init__(
        self,
        rgb_tolerance: int = 30,
        hsv_tolerance_h: int = 10,
        hsv_tolerance_s: int = 50,
        hsv_tolerance_v: int = 50,
        min_area: int = 30,
        use_hsv: bool = True,
        precise_mode: bool = True,
        search_step: int = 2,
        scan_interval: float = 0.2,
        morph_iterations: int = 1
    ):
        """
        Initialize parameter set
        
        Args:
            rgb_tolerance: RGB color tolerance
            hsv_tolerance_h: HSV hue tolerance
            hsv_tolerance_s: HSV saturation tolerance
            hsv_tolerance_v: HSV value tolerance
            min_area: Minimum contour area
            use_hsv: Whether to use HSV color space
            precise_mode: Whether to use precise mode (RGB+HSV)
            search_step: Search step size
            scan_interval: Scan interval in seconds
            morph_iterations: Morphological operations iterations
        """
        self.rgb_tolerance = rgb_tolerance
        self.hsv_tolerance_h = hsv_tolerance_h
        self.hsv_tolerance_s = hsv_tolerance_s
        self.hsv_tolerance_v = hsv_tolerance_v
        self.min_area = min_area
        self.use_hsv = use_hsv
        self.precise_mode = precise_mode
        self.search_step = search_step
        self.scan_interval = scan_interval
        self.morph_iterations = morph_iterations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'rgb_tolerance': self.rgb_tolerance,
            'hsv_tolerance_h': self.hsv_tolerance_h,
            'hsv_tolerance_s': self.hsv_tolerance_s,
            'hsv_tolerance_v': self.hsv_tolerance_v,
            'min_area': self.min_area,
            'use_hsv': self.use_hsv,
            'precise_mode': self.precise_mode,
            'search_step': self.search_step,
            'scan_interval': self.scan_interval,
            'morph_iterations': self.morph_iterations
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ParameterSet':
        """Create from dictionary"""
        return cls(
            rgb_tolerance=data.get('rgb_tolerance', 30),
            hsv_tolerance_h=data.get('hsv_tolerance_h', 10),
            hsv_tolerance_s=data.get('hsv_tolerance_s', 50),
            hsv_tolerance_v=data.get('hsv_tolerance_v', 50),
            min_area=data.get('min_area', 30),
            use_hsv=data.get('use_hsv', True),
            precise_mode=data.get('precise_mode', True),
            search_step=data.get('search_step', 2),
            scan_interval=data.get('scan_interval', 0.2),
            morph_iterations=data.get('morph_iterations', 1)
        )
    
    def apply_to_color_spec(self, color_spec: ColorSpec) -> ColorSpec:
        """
        Apply parameters to color specification
        
        Args:
            color_spec: Original color specification
        
        Returns:
            Updated color specification
        """
        return ColorSpec(
            rgb=color_spec.rgb,
            tol_rgb=self.rgb_tolerance,
            use_hsv=self.use_hsv,
            tol_h=self.hsv_tolerance_h,
            tol_s=self.hsv_tolerance_s,
            tol_v=self.hsv_tolerance_v
        )
    
    def get_variation(self, variation_level: float = 0.2) -> 'ParameterSet':
        """
        Get a variation of this parameter set
        
        Args:
            variation_level: Level of variation (0.0 to 1.0)
        
        Returns:
            New parameter set with variations
        """
        # Clamp variation level
        variation_level = max(0.0, min(1.0, variation_level))
        
        # Calculate variation ranges
        rgb_range = int(10 * variation_level)
        hsv_h_range = int(5 * variation_level)
        hsv_sv_range = int(20 * variation_level)
        min_area_range = int(10 * variation_level)
        step_range = max(1, int(2 * variation_level))
        
        # Create variation
        return ParameterSet(
            rgb_tolerance=max(5, min(50, self.rgb_tolerance + np.random.randint(-rgb_range, rgb_range + 1))),
            hsv_tolerance_h=max(2, min(20, self.hsv_tolerance_h + np.random.randint(-hsv_h_range, hsv_h_range + 1))),
            hsv_tolerance_s=max(10, min(100, self.hsv_tolerance_s + np.random.randint(-hsv_sv_range, hsv_sv_range + 1))),
            hsv_tolerance_v=max(10, min(100, self.hsv_tolerance_v + np.random.randint(-hsv_sv_range, hsv_sv_range + 1))),
            min_area=max(5, min(100, self.min_area + np.random.randint(-min_area_range, min_area_range + 1))),
            use_hsv=self.use_hsv,
            precise_mode=self.precise_mode,
            search_step=max(1, min(5, self.search_step + np.random.randint(-step_range, step_range + 1))),
            scan_interval=self.scan_interval,
            morph_iterations=max(0, min(3, self.morph_iterations + np.random.randint(-1, 2)))
        )

class AdaptiveDetector:
    """
    Adaptive detector that automatically adjusts parameters based on environment and results
    """
    
    def __init__(self, config_manager=None, parallel_detector=None):
        """
        Initialize adaptive detector
        
        Args:
            config_manager: Configuration manager
            parallel_detector: Parallel detector instance (optional)
        """
        self.config_manager = config_manager
        
        # Create parallel detector if not provided
        if parallel_detector is None:
            self.parallel_detector = ParallelDetector()
        else:
            self.parallel_detector = parallel_detector
        
        # Initialize parameters
        self.base_parameters = ParameterSet()
        self.current_parameters = ParameterSet()
        self.best_parameters = ParameterSet()
        
        # Initialize environment condition
        self.environment = EnvironmentCondition()
        
        # Initialize performance tracking
        self.detection_history = []
        self.success_rate = 0.0
        self.avg_execution_time = 0.0
        self.last_adaptation_time = 0.0
        self.adaptation_interval = 60.0  # seconds
        
        # Initialize learning state
        self.learning_enabled = True
        self.exploration_rate = 0.2  # 20% chance to try new parameters
        self.learning_rate = 0.1     # How quickly to adapt parameters
        
        # Load parameters from config if available
        if config_manager:
            self._load_from_config()
        
        # Create data directory
        self.data_dir = Path("data/adaptive_detector")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Load saved parameters if available
        self._load_saved_parameters()
        
        logger.info("Adaptive detector initialized")
    
    def _load_from_config(self):
        """Load parameters from configuration"""
        if not self.config_manager:
            return
        
        # Load base parameters
        self.base_parameters = ParameterSet(
            rgb_tolerance=self.config_manager.get('rgb_tolerance', 30),
            hsv_tolerance_h=self.config_manager.get('hsv_tolerance_h', 10),
            hsv_tolerance_s=self.config_manager.get('hsv_tolerance_s', 50),
            hsv_tolerance_v=self.config_manager.get('hsv_tolerance_v', 50),
            min_area=self.config_manager.get('min_area', 30),
            use_hsv=self.config_manager.get('use_hsv', True),
            precise_mode=self.config_manager.get('precise_mode', True),
            search_step=self.config_manager.get('search_step', 2),
            scan_interval=self.config_manager.get('scan_interval', 0.2),
            morph_iterations=self.config_manager.get('morph_iterations', 1)
        )
        
        # Set current and best parameters to base parameters
        self.current_parameters = ParameterSet.from_dict(self.base_parameters.to_dict())
        self.best_parameters = ParameterSet.from_dict(self.base_parameters.to_dict())
        
        # Load learning settings
        self.learning_enabled = self.config_manager.get('adaptive_learning_enabled', True)
        self.exploration_rate = self.config_manager.get('adaptive_exploration_rate', 0.2)
        self.learning_rate = self.config_manager.get('adaptive_learning_rate', 0.1)
        self.adaptation_interval = self.config_manager.get('adaptive_adaptation_interval', 60.0)
    
    def _save_parameters(self):
        """Save parameters to file"""
        try:
            # Create data file
            data_file = self.data_dir / "parameters.json"
            
            # Prepare data
            data = {
                'base_parameters': self.base_parameters.to_dict(),
                'best_parameters': self.best_parameters.to_dict(),
                'current_parameters': self.current_parameters.to_dict(),
                'environment': {
                    'lighting_level': self.environment.lighting_level,
                    'contrast_level': self.environment.contrast_level,
                    'noise_level': self.environment.noise_level,
                    'color_scheme': self.environment.color_scheme,
                    'game_area': self.environment.game_area
                },
                'performance': {
                    'success_rate': self.success_rate,
                    'avg_execution_time': self.avg_execution_time
                },
                'learning': {
                    'enabled': self.learning_enabled,
                    'exploration_rate': self.exploration_rate,
                    'learning_rate': self.learning_rate,
                    'adaptation_interval': self.adaptation_interval
                }
            }
            
            # Save to file
            with open(data_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug("Saved adaptive detector parameters")
        
        except Exception as e:
            logger.error(f"Error saving parameters: {e}")
    
    def _load_saved_parameters(self):
        """Load parameters from file"""
        try:
            # Check if data file exists
            data_file = self.data_dir / "parameters.json"
            
            if not data_file.exists():
                logger.debug("No saved parameters found")
                return
            
            # Load data
            with open(data_file, 'r') as f:
                data = json.load(f)
            
            # Load parameters
            if 'base_parameters' in data:
                self.base_parameters = ParameterSet.from_dict(data['base_parameters'])
            
            if 'best_parameters' in data:
                self.best_parameters = ParameterSet.from_dict(data['best_parameters'])
            
            if 'current_parameters' in data:
                self.current_parameters = ParameterSet.from_dict(data['current_parameters'])
            
            # Load environment
            if 'environment' in data:
                env = data['environment']
                self.environment.lighting_level = env.get('lighting_level', 0.0)
                self.environment.contrast_level = env.get('contrast_level', 0.0)
                self.environment.noise_level = env.get('noise_level', 0.0)
                self.environment.color_scheme = env.get('color_scheme', 'unknown')
                self.environment.game_area = env.get('game_area', 'unknown')
            
            # Load performance
            if 'performance' in data:
                perf = data['performance']
                self.success_rate = perf.get('success_rate', 0.0)
                self.avg_execution_time = perf.get('avg_execution_time', 0.0)
            
            # Load learning settings
            if 'learning' in data:
                learn = data['learning']
                self.learning_enabled = learn.get('enabled', True)
                self.exploration_rate = learn.get('exploration_rate', 0.2)
                self.learning_rate = learn.get('learning_rate', 0.1)
                self.adaptation_interval = learn.get('adaptation_interval', 60.0)
            
            logger.info("Loaded adaptive detector parameters")
        
        except Exception as e:
            logger.error(f"Error loading parameters: {e}")
    
    def detect_environment(self, img_bgr: np.ndarray) -> EnvironmentCondition:
        """
        Detect environment conditions from image
        
        Args:
            img_bgr: Input image in BGR format
        
        Returns:
            Environment condition
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            
            # Calculate lighting level (average brightness)
            brightness = np.mean(gray) / 255.0
            
            # Calculate contrast level
            contrast = np.std(gray) / 128.0
            
            # Calculate noise level (approximation using Laplacian)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            noise = np.var(laplacian) / 100.0
            noise = min(1.0, noise)
            
            # Determine color scheme
            hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
            h, s, v = cv2.split(hsv)
            
            # Check if predominantly dark
            if brightness < 0.3:
                color_scheme = "dark"
            # Check if predominantly light
            elif brightness > 0.7:
                color_scheme = "light"
            else:
                color_scheme = "custom"
            
            # Create environment condition
            environment = EnvironmentCondition(
                lighting_level=brightness,
                contrast_level=contrast,
                noise_level=noise,
                color_scheme=color_scheme,
                game_area=self.environment.game_area  # Keep existing game area
            )
            
            # Update current environment
            self.environment = environment
            
            return environment
        
        except Exception as e:
            logger.error(f"Error detecting environment: {e}")
            return EnvironmentCondition()
    
    def _should_adapt_parameters(self) -> bool:
        """
        Determine if parameters should be adapted
        
        Returns:
            True if parameters should be adapted
        """
        # Check if learning is enabled
        if not self.learning_enabled:
            return False
        
        # Check if enough time has passed since last adaptation
        current_time = time.time()
        if current_time - self.last_adaptation_time < self.adaptation_interval:
            return False
        
        # Check if we have enough detection history
        if len(self.detection_history) < 10:
            return False
        
        # Calculate recent success rate
        recent_history = self.detection_history[-20:]
        recent_success_rate = sum(1 for r in recent_history if r.success) / len(recent_history)
        
        # Adapt if success rate is below threshold or randomly based on exploration rate
        return recent_success_rate < 0.7 or np.random.random() < self.exploration_rate
    
    def _adapt_parameters(self):
        """Adapt parameters based on detection history and environment"""
        try:
            # Update last adaptation time
            self.last_adaptation_time = time.time()
            
            # Check if we have detection history
            if not self.detection_history:
                return
            
            # Calculate success rate
            self.success_rate = sum(1 for r in self.detection_history if r.success) / len(self.detection_history)
            
            # Calculate average execution time
            self.avg_execution_time = sum(r.execution_time for r in self.detection_history) / len(self.detection_history)
            
            # If success rate is good, keep current parameters
            if self.success_rate > 0.9:
                # Update best parameters if current parameters are better
                if self.success_rate > 0.95:
                    self.best_parameters = ParameterSet.from_dict(self.current_parameters.to_dict())
                    logger.info("Updated best parameters due to high success rate")
                
                return
            
            # Analyze successful detections
            successful = [r for r in self.detection_history if r.success]
            
            if successful:
                # Find best successful detection based on quality score
                best_detection = max(successful, key=lambda r: r.quality_score)
                
                # Get parameters from best detection
                best_params = best_detection.parameters
                
                # Create new parameter set
                new_params = ParameterSet(
                    rgb_tolerance=best_params.get('rgb_tolerance', self.current_parameters.rgb_tolerance),
                    hsv_tolerance_h=best_params.get('hsv_tolerance_h', self.current_parameters.hsv_tolerance_h),
                    hsv_tolerance_s=best_params.get('hsv_tolerance_s', self.current_parameters.hsv_tolerance_s),
                    hsv_tolerance_v=best_params.get('hsv_tolerance_v', self.current_parameters.hsv_tolerance_v),
                    min_area=best_params.get('min_area', self.current_parameters.min_area),
                    use_hsv=best_params.get('use_hsv', self.current_parameters.use_hsv),
                    precise_mode=best_params.get('precise_mode', self.current_parameters.precise_mode),
                    search_step=best_params.get('search_step', self.current_parameters.search_step),
                    scan_interval=best_params.get('scan_interval', self.current_parameters.scan_interval),
                    morph_iterations=best_params.get('morph_iterations', self.current_parameters.morph_iterations)
                )
                
                # Apply learning rate
                self._blend_parameters(new_params, self.learning_rate)
                
                logger.info(f"Adapted parameters based on successful detection (success rate: {self.success_rate:.2f})")
            else:
                # No successful detections, try a variation of best parameters
                variation = self.best_parameters.get_variation(0.3)
                
                # Apply variation
                self._blend_parameters(variation, 0.5)
                
                logger.info("Adapted parameters using variation of best parameters")
            
            # Save parameters
            self._save_parameters()
        
        except Exception as e:
            logger.error(f"Error adapting parameters: {e}")
    
    def _blend_parameters(self, new_params: ParameterSet, weight: float):
        """
        Blend new parameters with current parameters
        
        Args:
            new_params: New parameters
            weight: Weight of new parameters (0.0 to 1.0)
        """
        # Clamp weight
        weight = max(0.0, min(1.0, weight))
        
        # Calculate weighted average for numeric parameters
        self.current_parameters.rgb_tolerance = int(
            self.current_parameters.rgb_tolerance * (1 - weight) + new_params.rgb_tolerance * weight
        )
        self.current_parameters.hsv_tolerance_h = int(
            self.current_parameters.hsv_tolerance_h * (1 - weight) + new_params.hsv_tolerance_h * weight
        )
        self.current_parameters.hsv_tolerance_s = int(
            self.current_parameters.hsv_tolerance_s * (1 - weight) + new_params.hsv_tolerance_s * weight
        )
        self.current_parameters.hsv_tolerance_v = int(
            self.current_parameters.hsv_tolerance_v * (1 - weight) + new_params.hsv_tolerance_v * weight
        )
        self.current_parameters.min_area = int(
            self.current_parameters.min_area * (1 - weight) + new_params.min_area * weight
        )
        self.current_parameters.search_step = int(
            self.current_parameters.search_step * (1 - weight) + new_params.search_step * weight
        )
        self.current_parameters.scan_interval = (
            self.current_parameters.scan_interval * (1 - weight) + new_params.scan_interval * weight
        )
        self.current_parameters.morph_iterations = int(
            self.current_parameters.morph_iterations * (1 - weight) + new_params.morph_iterations * weight
        )
        
        # For boolean parameters, use new value if weight is high enough
        if weight > 0.7:
            self.current_parameters.use_hsv = new_params.use_hsv
            self.current_parameters.precise_mode = new_params.precise_mode
    
    def _calculate_quality_score(
        self,
        contours: List,
        execution_time: float,
        expected_count: Optional[int] = None
    ) -> float:
        """
        Calculate quality score for detection result
        
        Args:
            contours: Detected contours
            execution_time: Execution time in seconds
            expected_count: Expected number of contours (optional)
        
        Returns:
            Quality score (0.0 to 1.0)
        """
        # Base score based on having contours
        if not contours:
            return 0.0
        
        # Start with base score
        score = 0.5
        
        # Adjust based on contour count
        if expected_count is not None:
            # Perfect match gets highest score
            if len(contours) == expected_count:
                score += 0.3
            # Close match gets partial score
            elif abs(len(contours) - expected_count) <= 2:
                score += 0.15
            # Too many or too few contours reduces score
            elif len(contours) > expected_count * 2 or len(contours) < expected_count / 2:
                score -= 0.2
        else:
            # Without expected count, prefer moderate number of contours
            if 1 <= len(contours) <= 10:
                score += 0.2
            elif len(contours) > 50:
                score -= 0.2
        
        # Adjust based on contour areas
        areas = [cv2.contourArea(c) for c in contours]
        if areas:
            avg_area = sum(areas) / len(areas)
            
            # Prefer moderate-sized contours
            if 50 <= avg_area <= 500:
                score += 0.1
            elif avg_area < 10 or avg_area > 2000:
                score -= 0.1
            
            # Prefer consistent contour sizes
            if len(areas) > 1:
                area_std = np.std(areas)
                area_mean = np.mean(areas)
                if area_std / area_mean < 0.5:
                    score += 0.1
        
        # Adjust based on execution time
        if execution_time < 0.05:
            score += 0.1
        elif execution_time > 0.2:
            score -= 0.1
        
        # Clamp score to valid range
        return max(0.0, min(1.0, score))
    
    def detect_color(
        self,
        img_bgr: np.ndarray,
        color_spec: ColorSpec,
        roi: Optional[ROI] = None,
        expected_count: Optional[int] = None
    ) -> DetectionResult:
        """
        Detect a single color with adaptive parameters
        
        Args:
            img_bgr: Input image in BGR format
            color_spec: Color specification
            roi: Region of interest (optional)
            expected_count: Expected number of contours (optional)
        
        Returns:
            Detection result
        """
        try:
            # Start timing
            start_time = time.time()
            
            # Detect environment if needed
            if time.time() - self.last_adaptation_time > 300:  # Every 5 minutes
                self.detect_environment(img_bgr)
            
            # Check if we should adapt parameters
            if self._should_adapt_parameters():
                self._adapt_parameters()
            
            # Apply current parameters to color spec
            adapted_color_spec = self.current_parameters.apply_to_color_spec(color_spec)
            
            # Extract ROI if specified
            if roi:
                x, y, w, h = roi.left, roi.top, roi.width, roi.height
                img = img_bgr[y:y+h, x:x+w]
                roi_offset = (x, y)
            else:
                img = img_bgr
                roi_offset = (0, 0)
            
            # Detect color
            mask, contours = build_mask(
                img,
                adapted_color_spec,
                step=self.current_parameters.search_step,
                precise=self.current_parameters.precise_mode,
                min_area=self.current_parameters.min_area
            )
            
            # Convert contours to screen points
            bbox = {"left": roi_offset[0], "top": roi_offset[1]}
            points = contours_to_screen_points(contours, bbox, self.current_parameters.search_step)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(contours, execution_time, expected_count)
            
            # Create detection result
            result = DetectionResult(
                success=len(contours) > 0,
                contours=contours,
                points=points,
                execution_time=execution_time,
                parameters=self.current_parameters.to_dict(),
                quality_score=quality_score
            )
            
            # Add to detection history
            self.detection_history.append(result)
            
            # Limit history size
            if len(self.detection_history) > 100:
                self.detection_history = self.detection_history[-100:]
            
            return result
        
        except Exception as e:
            logger.error(f"Error in adaptive color detection: {e}")
            return DetectionResult()
    
    def detect_colors(
        self,
        img_bgr: np.ndarray,
        color_specs: List[ColorSpec],
        roi: Optional[ROI] = None,
        expected_count: Optional[int] = None
    ) -> DetectionResult:
        """
        Detect multiple colors with adaptive parameters
        
        Args:
            img_bgr: Input image in BGR format
            color_specs: List of color specifications
            roi: Region of interest (optional)
            expected_count: Expected number of contours (optional)
        
        Returns:
            Detection result
        """
        try:
            # Start timing
            start_time = time.time()
            
            # Detect environment if needed
            if time.time() - self.last_adaptation_time > 300:  # Every 5 minutes
                self.detect_environment(img_bgr)
            
            # Check if we should adapt parameters
            if self._should_adapt_parameters():
                self._adapt_parameters()
            
            # Apply current parameters to color specs
            adapted_color_specs = [self.current_parameters.apply_to_color_spec(cs) for cs in color_specs]
            
            # Extract ROI if specified
            if roi:
                x, y, w, h = roi.left, roi.top, roi.width, roi.height
                img = img_bgr[y:y+h, x:x+w]
                roi_offset = (x, y)
            else:
                img = img_bgr
                roi_offset = (0, 0)
            
            # Create config for build_mask_multi
            config = {
                'monster_morph_open_iters': self.current_parameters.morph_iterations,
                'monster_morph_close_iters': self.current_parameters.morph_iterations
            }
            
            # Detect colors
            mask, contours = build_mask_multi(
                img,
                adapted_color_specs,
                step=self.current_parameters.search_step,
                precise=self.current_parameters.precise_mode,
                min_area=self.current_parameters.min_area,
                config=config
            )
            
            # Convert contours to screen points
            bbox = {"left": roi_offset[0], "top": roi_offset[1]}
            points = contours_to_screen_points(contours, bbox, self.current_parameters.search_step)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(contours, execution_time, expected_count)
            
            # Create detection result
            result = DetectionResult(
                success=len(contours) > 0,
                contours=contours,
                points=points,
                execution_time=execution_time,
                parameters=self.current_parameters.to_dict(),
                quality_score=quality_score
            )
            
            # Add to detection history
            self.detection_history.append(result)
            
            # Limit history size
            if len(self.detection_history) > 100:
                self.detection_history = self.detection_history[-100:]
            
            return result
        
        except Exception as e:
            logger.error(f"Error in adaptive multi-color detection: {e}")
            return DetectionResult()
    
    def detect_parallel(
        self,
        img_bgr: np.ndarray,
        color_specs: List[ColorSpec],
        roi: Optional[ROI] = None,
        expected_count: Optional[int] = None
    ) -> DetectionResult:
        """
        Detect colors using parallel processing with adaptive parameters
        
        Args:
            img_bgr: Input image in BGR format
            color_specs: List of color specifications
            roi: Region of interest (optional)
            expected_count: Expected number of contours (optional)
        
        Returns:
            Detection result
        """
        try:
            # Start timing
            start_time = time.time()
            
            # Detect environment if needed
            if time.time() - self.last_adaptation_time > 300:  # Every 5 minutes
                self.detect_environment(img_bgr)
            
            # Check if we should adapt parameters
            if self._should_adapt_parameters():
                self._adapt_parameters()
            
            # Apply current parameters to color specs
            adapted_color_specs = [self.current_parameters.apply_to_color_spec(cs) for cs in color_specs]
            
            # Create config for parallel detector
            config = {
                'monster_morph_open_iters': self.current_parameters.morph_iterations,
                'monster_morph_close_iters': self.current_parameters.morph_iterations
            }
            
            # Detect in ROI if specified
            if roi:
                mask, contours, points = self.parallel_detector.detect_in_roi(
                    img_bgr,
                    roi,
                    adapted_color_specs,
                    step=self.current_parameters.search_step,
                    precise=self.current_parameters.precise_mode,
                    min_area=self.current_parameters.min_area,
                    config=config
                )
            else:
                # Create full image ROI
                full_roi = ROI(0, 0, img_bgr.shape[1], img_bgr.shape[0])
                mask, contours, points = self.parallel_detector.detect_in_roi(
                    img_bgr,
                    full_roi,
                    adapted_color_specs,
                    step=self.current_parameters.search_step,
                    precise=self.current_parameters.precise_mode,
                    min_area=self.current_parameters.min_area,
                    config=config
                )
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(contours, execution_time, expected_count)
            
            # Create detection result
            result = DetectionResult(
                success=len(contours) > 0,
                contours=contours,
                points=points,
                execution_time=execution_time,
                parameters=self.current_parameters.to_dict(),
                quality_score=quality_score
            )
            
            # Add to detection history
            self.detection_history.append(result)
            
            # Limit history size
            if len(self.detection_history) > 100:
                self.detection_history = self.detection_history[-100:]
            
            return result
        
        except Exception as e:
            logger.error(f"Error in adaptive parallel detection: {e}")
            return DetectionResult()
    
    def reset_parameters(self):
        """Reset parameters to base values"""
        self.current_parameters = ParameterSet.from_dict(self.base_parameters.to_dict())
        logger.info("Reset parameters to base values")
    
    def set_game_area(self, area: str):
        """
        Set current game area
        
        Args:
            area: Game area name
        """
        self.environment.game_area = area
        logger.info(f"Set game area to: {area}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics
        
        Returns:
            Dictionary with performance statistics
        """
        # Calculate success rate
        if self.detection_history:
            self.success_rate = sum(1 for r in self.detection_history if r.success) / len(self.detection_history)
            self.avg_execution_time = sum(r.execution_time for r in self.detection_history) / len(self.detection_history)
        
        return {
            'success_rate': self.success_rate,
            'avg_execution_time': self.avg_execution_time,
            'detection_count': len(self.detection_history),
            'current_parameters': self.current_parameters.to_dict(),
            'best_parameters': self.best_parameters.to_dict(),
            'environment': {
                'lighting_level': self.environment.lighting_level,
                'contrast_level': self.environment.contrast_level,
                'noise_level': self.environment.noise_level,
                'color_scheme': self.environment.color_scheme,
                'game_area': self.environment.game_area
            }
        }
    
    def shutdown(self):
        """Shutdown the detector"""
        # Save parameters
        self._save_parameters()
        
        # Shutdown parallel detector
        self.parallel_detector.shutdown()
        
        logger.info("Adaptive detector shutdown")