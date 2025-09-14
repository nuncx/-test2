"""
Enhanced adaptive detection algorithms for RSPS Color Bot v3

This module provides advanced adaptive detection features including
environment detection, parameter adaptation, and failure recovery.
"""
import logging
import numpy as np
import cv2
import time
import json
import os
import random
from typing import Tuple, List, Dict, Optional, Any, Union
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import pickle

from ..config import ColorSpec, ROI
from .color_detector import build_mask, build_mask_multi, contours_to_screen_points
from .parallel_detector import ParallelDetector
from .adaptive_detector import AdaptiveDetector, EnvironmentCondition, ParameterSet, DetectionResult

# Get module logger
logger = logging.getLogger('rspsbot.core.detection.enhanced_adaptive_detector')

class GameArea(Enum):
    """Game area types for context-aware detection"""
    UNKNOWN = "unknown"
    WILDERNESS = "wilderness"
    CITY = "city"
    DUNGEON = "dungeon"
    FOREST = "forest"
    DESERT = "desert"
    WATER = "water"
    CAVE = "cave"
    INDOOR = "indoor"
    OUTDOOR = "outdoor"

class ColorScheme(Enum):
    """Color scheme types for adaptive detection"""
    UNKNOWN = "unknown"
    LIGHT = "light"
    DARK = "dark"
    COLORFUL = "colorful"
    MUTED = "muted"
    CUSTOM = "custom"

@dataclass
class EnhancedEnvironmentCondition(EnvironmentCondition):
    """
    Enhanced environment condition data class with additional properties
    """
    game_area: GameArea = GameArea.UNKNOWN
    color_scheme: ColorScheme = ColorScheme.UNKNOWN
    time_of_day: str = "unknown"  # "day", "night", "dusk", "dawn"
    weather_condition: str = "unknown"  # "clear", "foggy", "rainy", "snowy"
    screen_resolution: Tuple[int, int] = (0, 0)
    ui_scale: float = 1.0
    color_temperature: float = 0.0  # -1.0 (cool/blue) to 1.0 (warm/red)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'lighting_level': self.lighting_level,
            'contrast_level': self.contrast_level,
            'noise_level': self.noise_level,
            'color_scheme': self.color_scheme.value if isinstance(self.color_scheme, ColorScheme) else self.color_scheme,
            'game_area': self.game_area.value if isinstance(self.game_area, GameArea) else self.game_area,
            'time_of_day': self.time_of_day,
            'weather_condition': self.weather_condition,
            'screen_resolution': self.screen_resolution,
            'ui_scale': self.ui_scale,
            'color_temperature': self.color_temperature
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedEnvironmentCondition':
        """Create from dictionary"""
        # Convert string enum values to enum objects
        game_area = data.get('game_area', 'unknown')
        if isinstance(game_area, str):
            try:
                game_area = GameArea(game_area)
            except ValueError:
                game_area = GameArea.UNKNOWN
        
        color_scheme = data.get('color_scheme', 'unknown')
        if isinstance(color_scheme, str):
            try:
                color_scheme = ColorScheme(color_scheme)
            except ValueError:
                color_scheme = ColorScheme.UNKNOWN
        
        return cls(
            lighting_level=data.get('lighting_level', 0.0),
            contrast_level=data.get('contrast_level', 0.0),
            noise_level=data.get('noise_level', 0.0),
            color_scheme=color_scheme,
            game_area=game_area,
            time_of_day=data.get('time_of_day', 'unknown'),
            weather_condition=data.get('weather_condition', 'unknown'),
            screen_resolution=data.get('screen_resolution', (0, 0)),
            ui_scale=data.get('ui_scale', 1.0),
            color_temperature=data.get('color_temperature', 0.0)
        )

@dataclass
class EnhancedParameterSet(ParameterSet):
    """
    Enhanced detection parameter set with additional properties
    """
    # Additional parameters
    adaptive_threshold: bool = False
    adaptive_threshold_block_size: int = 11
    adaptive_threshold_c: int = 2
    
    edge_detection: bool = False
    edge_detection_low_threshold: int = 50
    edge_detection_high_threshold: int = 150
    
    color_correction: bool = False
    color_correction_brightness: float = 0.0  # -1.0 to 1.0
    color_correction_contrast: float = 0.0    # -1.0 to 1.0
    color_correction_saturation: float = 0.0  # -1.0 to 1.0
    
    noise_reduction: bool = False
    noise_reduction_strength: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        # Get base parameters
        params = super().to_dict()
        
        # Add enhanced parameters
        params.update({
            'adaptive_threshold': self.adaptive_threshold,
            'adaptive_threshold_block_size': self.adaptive_threshold_block_size,
            'adaptive_threshold_c': self.adaptive_threshold_c,
            
            'edge_detection': self.edge_detection,
            'edge_detection_low_threshold': self.edge_detection_low_threshold,
            'edge_detection_high_threshold': self.edge_detection_high_threshold,
            
            'color_correction': self.color_correction,
            'color_correction_brightness': self.color_correction_brightness,
            'color_correction_contrast': self.color_correction_contrast,
            'color_correction_saturation': self.color_correction_saturation,
            
            'noise_reduction': self.noise_reduction,
            'noise_reduction_strength': self.noise_reduction_strength
        })
        
        return params
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedParameterSet':
        """Create from dictionary"""
        # Create base parameter set
        params = super().from_dict(data)
        
        # Add enhanced parameters
        params.adaptive_threshold = data.get('adaptive_threshold', False)
        params.adaptive_threshold_block_size = data.get('adaptive_threshold_block_size', 11)
        params.adaptive_threshold_c = data.get('adaptive_threshold_c', 2)
        
        params.edge_detection = data.get('edge_detection', False)
        params.edge_detection_low_threshold = data.get('edge_detection_low_threshold', 50)
        params.edge_detection_high_threshold = data.get('edge_detection_high_threshold', 150)
        
        params.color_correction = data.get('color_correction', False)
        params.color_correction_brightness = data.get('color_correction_brightness', 0.0)
        params.color_correction_contrast = data.get('color_correction_contrast', 0.0)
        params.color_correction_saturation = data.get('color_correction_saturation', 0.0)
        
        params.noise_reduction = data.get('noise_reduction', False)
        params.noise_reduction_strength = data.get('noise_reduction_strength', 3)
        
        return params

class EnhancedAdaptiveDetector(AdaptiveDetector):
    """
    Enhanced adaptive detector with advanced environment detection and parameter adaptation
    """
    
    def __init__(
        self,
        use_parallel: bool = True,
        max_workers: int = None,
        learning_rate: float = 0.1,
        exploration_rate: float = 0.2,
        memory_size: int = 100,
        persistence_file: str = None
    ):
        """
        Initialize enhanced adaptive detector
        
        Args:
            use_parallel: Whether to use parallel processing
            max_workers: Maximum number of worker threads for parallel processing
            learning_rate: Rate at which parameters are adjusted (0.0 to 1.0)
            exploration_rate: Rate at which new parameter combinations are explored (0.0 to 1.0)
            memory_size: Number of detection results to remember for learning
            persistence_file: File path for saving/loading learned parameters
        """
        super().__init__(use_parallel, max_workers, learning_rate)
        
        # Enhanced properties
        self.exploration_rate = max(0.0, min(1.0, exploration_rate))
        self.memory_size = max(10, memory_size)
        self.persistence_file = persistence_file
        
        # Memory of detection results for learning
        self.detection_memory = []
        
        # Environment-specific parameter sets
        self.environment_parameters = {}
        
        # Failure recovery
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.fallback_strategies = [
            self._try_color_correction,
            self._try_noise_reduction,
            self._try_edge_detection,
            self._try_adaptive_threshold,
            self._try_parameter_reset
        ]
        
        # Load persisted data if available
        if self.persistence_file and os.path.exists(self.persistence_file):
            self._load_persisted_data()
    
    def detect(
        self,
        image: np.ndarray,
        color_spec: ColorSpec,
        roi: Optional[ROI] = None,
        parameters: Optional[Union[ParameterSet, EnhancedParameterSet]] = None
    ) -> DetectionResult:
        """
        Detect objects in image with adaptive parameters
        
        Args:
            image: Input image (BGR format)
            color_spec: Color specification
            roi: Region of interest (optional)
            parameters: Parameter set (optional)
        
        Returns:
            DetectionResult object
        """
        # Detect environment conditions
        environment = self._detect_environment(image)
        
        # Get parameters for this environment
        if parameters is None:
            parameters = self._get_environment_parameters(environment, color_spec)
        
        # Apply pre-processing based on parameters
        processed_image = self._preprocess_image(image, parameters)
        
        # Perform detection
        result = super().detect(processed_image, color_spec, roi, parameters)
        
        # Update detection memory
        self._update_detection_memory(result, environment, parameters)
        
        # Handle detection failure
        if not result.success and result.quality_score < 0.3:
            result = self._handle_detection_failure(image, color_spec, roi, environment, parameters)
        
        # Persist learned parameters periodically
        if random.random() < 0.1 and self.persistence_file:  # 10% chance to save
            self._persist_data()
        
        return result
    
    def _detect_environment(self, image: np.ndarray) -> EnhancedEnvironmentCondition:
        """
        Detect environment conditions from image
        
        Args:
            image: Input image
        
        Returns:
            EnhancedEnvironmentCondition object
        """
        # Create environment condition object
        env = EnhancedEnvironmentCondition()
        
        # Get image dimensions
        height, width = image.shape[:2]
        env.screen_resolution = (width, height)
        
        # Calculate lighting level (average brightness)
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        brightness = np.mean(hsv_image[:, :, 2]) / 255.0
        env.lighting_level = brightness
        
        # Calculate contrast level
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        contrast = np.std(gray_image) / 128.0
        env.contrast_level = min(1.0, contrast)
        
        # Calculate noise level
        blurred = cv2.GaussianBlur(gray_image, (5, 5), 0)
        noise = np.mean(np.abs(gray_image.astype(float) - blurred.astype(float))) / 255.0
        env.noise_level = min(1.0, noise * 10.0)  # Scale up for better differentiation
        
        # Detect color scheme
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        saturation = np.mean(hsv_image[:, :, 1]) / 255.0
        
        if brightness < 0.3:
            env.color_scheme = ColorScheme.DARK
        elif brightness > 0.7:
            env.color_scheme = ColorScheme.LIGHT
        elif saturation > 0.5:
            env.color_scheme = ColorScheme.COLORFUL
        elif saturation < 0.2:
            env.color_scheme = ColorScheme.MUTED
        else:
            env.color_scheme = ColorScheme.UNKNOWN
        
        # Detect color temperature
        b, g, r = cv2.split(image)
        if np.mean(r) > np.mean(b):
            # Warmer image (more red than blue)
            env.color_temperature = min(1.0, (np.mean(r) - np.mean(b)) / 128.0)
        else:
            # Cooler image (more blue than red)
            env.color_temperature = max(-1.0, (np.mean(b) - np.mean(r)) / -128.0)
        
        # Game area detection would require more sophisticated analysis
        # For now, we'll leave it as UNKNOWN
        env.game_area = GameArea.UNKNOWN
        
        # Time of day estimation based on brightness and color temperature
        if brightness < 0.3:
            env.time_of_day = "night"
        elif brightness > 0.7:
            env.time_of_day = "day"
        elif env.color_temperature > 0.3:
            env.time_of_day = "dusk"
        elif env.color_temperature < -0.3:
            env.time_of_day = "dawn"
        else:
            env.time_of_day = "unknown"
        
        return env
    
    def _get_environment_parameters(
        self,
        environment: EnhancedEnvironmentCondition,
        color_spec: ColorSpec
    ) -> EnhancedParameterSet:
        """
        Get parameters for specific environment
        
        Args:
            environment: Environment condition
            color_spec: Color specification
        
        Returns:
            EnhancedParameterSet object
        """
        # Create environment key
        env_key = self._create_environment_key(environment)
        color_key = f"{color_spec.r}_{color_spec.g}_{color_spec.b}"
        combined_key = f"{env_key}_{color_key}"
        
        # Check if we have parameters for this environment
        if combined_key in self.environment_parameters:
            # Decide whether to explore new parameters
            if random.random() < self.exploration_rate:
                # Create variation of existing parameters
                base_params = self.environment_parameters[combined_key]
                return self._create_parameter_variation(base_params)
            else:
                # Use existing parameters
                return self.environment_parameters[combined_key]
        
        # Create new parameters based on environment
        params = self._create_parameters_for_environment(environment, color_spec)
        
        # Store parameters
        self.environment_parameters[combined_key] = params
        
        return params
    
    def _create_environment_key(self, environment: EnhancedEnvironmentCondition) -> str:
        """
        Create a key for environment conditions
        
        Args:
            environment: Environment condition
        
        Returns:
            String key
        """
        # Discretize continuous values
        lighting = round(environment.lighting_level * 10) / 10
        contrast = round(environment.contrast_level * 10) / 10
        noise = round(environment.noise_level * 10) / 10
        
        # Create key
        return f"{lighting}_{contrast}_{noise}_{environment.color_scheme.value}_{environment.game_area.value}"
    
    def _create_parameters_for_environment(
        self,
        environment: EnhancedEnvironmentCondition,
        color_spec: ColorSpec
    ) -> EnhancedParameterSet:
        """
        Create parameters optimized for specific environment
        
        Args:
            environment: Environment condition
            color_spec: Color specification
        
        Returns:
            EnhancedParameterSet object
        """
        params = EnhancedParameterSet()
        
        # Adjust RGB tolerance based on lighting and contrast
        if environment.lighting_level < 0.3:
            # Dark environment - increase tolerance
            params.rgb_tolerance = 40
        elif environment.lighting_level > 0.7:
            # Bright environment - decrease tolerance
            params.rgb_tolerance = 20
        else:
            # Normal lighting
            params.rgb_tolerance = 30
        
        # Adjust HSV tolerance based on color scheme
        if environment.color_scheme == ColorScheme.COLORFUL:
            # More precise hue matching for colorful environments
            params.hsv_tolerance_h = 8
            params.hsv_tolerance_s = 60
            params.hsv_tolerance_v = 60
        elif environment.color_scheme == ColorScheme.MUTED:
            # More relaxed hue matching for muted environments
            params.hsv_tolerance_h = 15
            params.hsv_tolerance_s = 40
            params.hsv_tolerance_v = 60
        elif environment.color_scheme == ColorScheme.DARK:
            # Focus more on hue and saturation in dark environments
            params.hsv_tolerance_h = 12
            params.hsv_tolerance_s = 40
            params.hsv_tolerance_v = 80
        elif environment.color_scheme == ColorScheme.LIGHT:
            # Focus more on hue in light environments
            params.hsv_tolerance_h = 10
            params.hsv_tolerance_s = 60
            params.hsv_tolerance_v = 40
        
        # Adjust search step based on resolution
        width, height = environment.screen_resolution
        if width > 1920 or height > 1080:
            params.search_step = 3
        elif width > 1280 or height > 720:
            params.search_step = 2
        else:
            params.search_step = 1
        
        # Adjust minimum area based on resolution
        total_pixels = width * height
        params.min_area = max(20, int(total_pixels / 40000))
        
        # Enable noise reduction for noisy environments
        if environment.noise_level > 0.5:
            params.noise_reduction = True
            params.noise_reduction_strength = min(7, int(environment.noise_level * 10))
        
        # Enable color correction for extreme lighting
        if environment.lighting_level < 0.2 or environment.lighting_level > 0.8:
            params.color_correction = True
            
            # Adjust brightness
            if environment.lighting_level < 0.2:
                params.color_correction_brightness = 0.3
            elif environment.lighting_level > 0.8:
                params.color_correction_brightness = -0.3
            
            # Adjust contrast
            if environment.contrast_level < 0.3:
                params.color_correction_contrast = 0.3
            
            # Adjust saturation
            if environment.color_scheme == ColorScheme.MUTED:
                params.color_correction_saturation = 0.3
        
        return params
    
    def _create_parameter_variation(self, base_params: EnhancedParameterSet) -> EnhancedParameterSet:
        """
        Create a variation of parameters for exploration
        
        Args:
            base_params: Base parameters
        
        Returns:
            Varied parameters
        """
        # Create a copy of base parameters
        params = EnhancedParameterSet()
        
        # Copy all attributes
        for key, value in base_params.to_dict().items():
            if hasattr(params, key):
                setattr(params, key, value)
        
        # Apply random variations to selected parameters
        # We'll vary 2-4 parameters at a time
        num_params_to_vary = random.randint(2, 4)
        params_to_vary = random.sample([
            'rgb_tolerance',
            'hsv_tolerance_h',
            'hsv_tolerance_s',
            'hsv_tolerance_v',
            'min_area',
            'search_step',
            'morph_iterations',
            'noise_reduction_strength',
            'adaptive_threshold_block_size',
            'edge_detection_low_threshold',
            'color_correction_brightness',
            'color_correction_contrast',
            'color_correction_saturation'
        ], num_params_to_vary)
        
        # Apply variations
        for param in params_to_vary:
            if param == 'rgb_tolerance':
                params.rgb_tolerance = max(10, min(50, params.rgb_tolerance + random.randint(-10, 10)))
            elif param == 'hsv_tolerance_h':
                params.hsv_tolerance_h = max(5, min(20, params.hsv_tolerance_h + random.randint(-5, 5)))
            elif param == 'hsv_tolerance_s':
                params.hsv_tolerance_s = max(30, min(80, params.hsv_tolerance_s + random.randint(-15, 15)))
            elif param == 'hsv_tolerance_v':
                params.hsv_tolerance_v = max(30, min(80, params.hsv_tolerance_v + random.randint(-15, 15)))
            elif param == 'min_area':
                params.min_area = max(10, min(100, params.min_area + random.randint(-10, 10)))
            elif param == 'search_step':
                params.search_step = max(1, min(4, params.search_step + random.randint(-1, 1)))
            elif param == 'morph_iterations':
                params.morph_iterations = max(0, min(3, params.morph_iterations + random.randint(-1, 1)))
            elif param == 'noise_reduction_strength':
                params.noise_reduction_strength = max(1, min(9, params.noise_reduction_strength + random.randint(-2, 2)))
                # Make sure it's odd
                if params.noise_reduction_strength % 2 == 0:
                    params.noise_reduction_strength += 1
            elif param == 'adaptive_threshold_block_size':
                # Must be odd
                new_val = params.adaptive_threshold_block_size + random.randint(-4, 4) * 2
                params.adaptive_threshold_block_size = max(3, min(21, new_val))
                if params.adaptive_threshold_block_size % 2 == 0:
                    params.adaptive_threshold_block_size += 1
            elif param == 'edge_detection_low_threshold':
                params.edge_detection_low_threshold = max(20, min(100, params.edge_detection_low_threshold + random.randint(-20, 20)))
                params.edge_detection_high_threshold = params.edge_detection_low_threshold * 2
            elif param == 'color_correction_brightness':
                params.color_correction_brightness = max(-1.0, min(1.0, params.color_correction_brightness + random.uniform(-0.2, 0.2)))
            elif param == 'color_correction_contrast':
                params.color_correction_contrast = max(-1.0, min(1.0, params.color_correction_contrast + random.uniform(-0.2, 0.2)))
            elif param == 'color_correction_saturation':
                params.color_correction_saturation = max(-1.0, min(1.0, params.color_correction_saturation + random.uniform(-0.2, 0.2)))
        
        # Randomly toggle boolean parameters
        if random.random() < 0.2:
            params.adaptive_threshold = not params.adaptive_threshold
        
        if random.random() < 0.2:
            params.edge_detection = not params.edge_detection
        
        if random.random() < 0.2:
            params.color_correction = not params.color_correction
        
        if random.random() < 0.2:
            params.noise_reduction = not params.noise_reduction
        
        if random.random() < 0.2:
            params.use_hsv = not params.use_hsv
        
        if random.random() < 0.2:
            params.precise_mode = not params.precise_mode
        
        return params
    
    def _preprocess_image(self, image: np.ndarray, parameters: EnhancedParameterSet) -> np.ndarray:
        """
        Preprocess image based on parameters
        
        Args:
            image: Input image
            parameters: Parameter set
        
        Returns:
            Preprocessed image
        """
        # Make a copy of the image
        processed = image.copy()
        
        # Apply noise reduction if enabled
        if parameters.noise_reduction:
            kernel_size = parameters.noise_reduction_strength
            processed = cv2.GaussianBlur(processed, (kernel_size, kernel_size), 0)
        
        # Apply color correction if enabled
        if parameters.color_correction:
            # Convert to HSV for easier manipulation
            hsv = cv2.cvtColor(processed, cv2.COLOR_BGR2HSV).astype(np.float32)
            
            # Adjust brightness (V channel)
            if parameters.color_correction_brightness != 0:
                hsv[:, :, 2] *= (1.0 + parameters.color_correction_brightness)
                hsv[:, :, 2] = np.clip(hsv[:, :, 2], 0, 255)
            
            # Adjust contrast (V channel)
            if parameters.color_correction_contrast != 0:
                mean = np.mean(hsv[:, :, 2])
                hsv[:, :, 2] = (hsv[:, :, 2] - mean) * (1.0 + parameters.color_correction_contrast) + mean
                hsv[:, :, 2] = np.clip(hsv[:, :, 2], 0, 255)
            
            # Adjust saturation (S channel)
            if parameters.color_correction_saturation != 0:
                hsv[:, :, 1] *= (1.0 + parameters.color_correction_saturation)
                hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
            
            # Convert back to BGR
            processed = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        
        # Apply adaptive threshold if enabled
        if parameters.adaptive_threshold:
            gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                parameters.adaptive_threshold_block_size,
                parameters.adaptive_threshold_c
            )
            # Convert back to BGR for consistency
            processed = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        
        # Apply edge detection if enabled
        if parameters.edge_detection:
            gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(
                gray,
                parameters.edge_detection_low_threshold,
                parameters.edge_detection_high_threshold
            )
            # Combine with original
            processed = cv2.bitwise_and(processed, processed, mask=edges)
        
        return processed
    
    def _update_detection_memory(
        self,
        result: DetectionResult,
        environment: EnhancedEnvironmentCondition,
        parameters: EnhancedParameterSet
    ):
        """
        Update detection memory with result
        
        Args:
            result: Detection result
            environment: Environment condition
            parameters: Parameter set
        """
        # Create memory entry
        memory_entry = {
            'result': result,
            'environment': environment,
            'parameters': parameters,
            'timestamp': time.time()
        }
        
        # Add to memory
        self.detection_memory.append(memory_entry)
        
        # Limit memory size
        if len(self.detection_memory) > self.memory_size:
            self.detection_memory.pop(0)
        
        # Update environment parameters if successful
        if result.success and result.quality_score > 0.7:
            env_key = self._create_environment_key(environment)
            color_key = f"{result.parameters.get('target_color_r', 0)}_{result.parameters.get('target_color_g', 0)}_{result.parameters.get('target_color_b', 0)}"
            combined_key = f"{env_key}_{color_key}"
            
            # Update parameters with successful ones
            self.environment_parameters[combined_key] = parameters
            
            # Reset consecutive failures
            self.consecutive_failures = 0
        else:
            # Increment consecutive failures
            self.consecutive_failures += 1
    
    def _handle_detection_failure(
        self,
        image: np.ndarray,
        color_spec: ColorSpec,
        roi: Optional[ROI],
        environment: EnhancedEnvironmentCondition,
        parameters: EnhancedParameterSet
    ) -> DetectionResult:
        """
        Handle detection failure with fallback strategies
        
        Args:
            image: Input image
            color_spec: Color specification
            roi: Region of interest
            environment: Environment condition
            parameters: Parameter set
        
        Returns:
            Detection result from fallback strategy
        """
        logger.debug(f"Detection failed, trying fallback strategies (failure #{self.consecutive_failures})")
        
        # Try fallback strategies
        for strategy in self.fallback_strategies:
            # Skip if we've already tried too many times
            if self.consecutive_failures > self.max_consecutive_failures:
                logger.warning(f"Too many consecutive failures ({self.consecutive_failures}), skipping fallback strategies")
                break
            
            # Try this strategy
            result = strategy(image, color_spec, roi, environment, parameters)
            
            # If successful, return result
            if result.success:
                logger.debug(f"Fallback strategy {strategy.__name__} succeeded")
                return result
        
        # If all strategies failed, return original result
        logger.warning("All fallback strategies failed")
        return DetectionResult(
            success=False,
            contours=[],
            points=[],
            execution_time=0.0,
            parameters=parameters.to_dict(),
            quality_score=0.0
        )
    
    def _try_color_correction(
        self,
        image: np.ndarray,
        color_spec: ColorSpec,
        roi: Optional[ROI],
        environment: EnhancedEnvironmentCondition,
        parameters: EnhancedParameterSet
    ) -> DetectionResult:
        """
        Try color correction as fallback strategy
        
        Args:
            image: Input image
            color_spec: Color specification
            roi: Region of interest
            environment: Environment condition
            parameters: Parameter set
        
        Returns:
            Detection result
        """
        # Create parameter variation with color correction
        new_params = EnhancedParameterSet()
        
        # Copy all attributes
        for key, value in parameters.to_dict().items():
            if hasattr(new_params, key):
                setattr(new_params, key, value)
        
        # Enable color correction
        new_params.color_correction = True
        
        # Adjust based on environment
        if environment.lighting_level < 0.3:
            new_params.color_correction_brightness = 0.5
            new_params.color_correction_contrast = 0.3
        elif environment.lighting_level > 0.7:
            new_params.color_correction_brightness = -0.3
            new_params.color_correction_contrast = 0.3
        
        if environment.color_scheme == ColorScheme.MUTED:
            new_params.color_correction_saturation = 0.5
        
        # Try detection with new parameters
        processed_image = self._preprocess_image(image, new_params)
        return super().detect(processed_image, color_spec, roi, new_params)
    
    def _try_noise_reduction(
        self,
        image: np.ndarray,
        color_spec: ColorSpec,
        roi: Optional[ROI],
        environment: EnhancedEnvironmentCondition,
        parameters: EnhancedParameterSet
    ) -> DetectionResult:
        """
        Try noise reduction as fallback strategy
        
        Args:
            image: Input image
            color_spec: Color specification
            roi: Region of interest
            environment: Environment condition
            parameters: Parameter set
        
        Returns:
            Detection result
        """
        # Create parameter variation with noise reduction
        new_params = EnhancedParameterSet()
        
        # Copy all attributes
        for key, value in parameters.to_dict().items():
            if hasattr(new_params, key):
                setattr(new_params, key, value)
        
        # Enable noise reduction
        new_params.noise_reduction = True
        new_params.noise_reduction_strength = 5
        
        # Increase tolerance
        new_params.rgb_tolerance = int(new_params.rgb_tolerance * 1.3)
        new_params.hsv_tolerance_h = int(new_params.hsv_tolerance_h * 1.3)
        new_params.hsv_tolerance_s = int(new_params.hsv_tolerance_s * 1.3)
        new_params.hsv_tolerance_v = int(new_params.hsv_tolerance_v * 1.3)
        
        # Try detection with new parameters
        processed_image = self._preprocess_image(image, new_params)
        return super().detect(processed_image, color_spec, roi, new_params)
    
    def _try_edge_detection(
        self,
        image: np.ndarray,
        color_spec: ColorSpec,
        roi: Optional[ROI],
        environment: EnhancedEnvironmentCondition,
        parameters: EnhancedParameterSet
    ) -> DetectionResult:
        """
        Try edge detection as fallback strategy
        
        Args:
            image: Input image
            color_spec: Color specification
            roi: Region of interest
            environment: Environment condition
            parameters: Parameter set
        
        Returns:
            Detection result
        """
        # Create parameter variation with edge detection
        new_params = EnhancedParameterSet()
        
        # Copy all attributes
        for key, value in parameters.to_dict().items():
            if hasattr(new_params, key):
                setattr(new_params, key, value)
        
        # Enable edge detection
        new_params.edge_detection = True
        new_params.edge_detection_low_threshold = 50
        new_params.edge_detection_high_threshold = 150
        
        # Try detection with new parameters
        processed_image = self._preprocess_image(image, new_params)
        return super().detect(processed_image, color_spec, roi, new_params)
    
    def _try_adaptive_threshold(
        self,
        image: np.ndarray,
        color_spec: ColorSpec,
        roi: Optional[ROI],
        environment: EnhancedEnvironmentCondition,
        parameters: EnhancedParameterSet
    ) -> DetectionResult:
        """
        Try adaptive threshold as fallback strategy
        
        Args:
            image: Input image
            color_spec: Color specification
            roi: Region of interest
            environment: Environment condition
            parameters: Parameter set
        
        Returns:
            Detection result
        """
        # Create parameter variation with adaptive threshold
        new_params = EnhancedParameterSet()
        
        # Copy all attributes
        for key, value in parameters.to_dict().items():
            if hasattr(new_params, key):
                setattr(new_params, key, value)
        
        # Enable adaptive threshold
        new_params.adaptive_threshold = True
        new_params.adaptive_threshold_block_size = 11
        new_params.adaptive_threshold_c = 2
        
        # Try detection with new parameters
        processed_image = self._preprocess_image(image, new_params)
        return super().detect(processed_image, color_spec, roi, new_params)
    
    def _try_parameter_reset(
        self,
        image: np.ndarray,
        color_spec: ColorSpec,
        roi: Optional[ROI],
        environment: EnhancedEnvironmentCondition,
        parameters: EnhancedParameterSet
    ) -> DetectionResult:
        """
        Try parameter reset as fallback strategy
        
        Args:
            image: Input image
            color_spec: Color specification
            roi: Region of interest
            environment: Environment condition
            parameters: Parameter set
        
        Returns:
            Detection result
        """
        # Create default parameters
        new_params = EnhancedParameterSet()
        
        # Try detection with new parameters
        processed_image = self._preprocess_image(image, new_params)
        return super().detect(processed_image, color_spec, roi, new_params)
    
    def _persist_data(self):
        """Persist learned parameters to file"""
        if not self.persistence_file:
            return
        
        try:
            # Create data to persist
            data = {
                'environment_parameters': {k: v.to_dict() for k, v in self.environment_parameters.items()},
                'detection_memory': [
                    {
                        'result': {
                            'success': entry['result'].success,
                            'quality_score': entry['result'].quality_score,
                            'parameters': entry['result'].parameters
                        },
                        'environment': entry['environment'].to_dict(),
                        'parameters': entry['parameters'].to_dict(),
                        'timestamp': entry['timestamp']
                    }
                    for entry in self.detection_memory
                ]
            }
            
            # Save to file
            with open(self.persistence_file, 'wb') as f:
                pickle.dump(data, f)
            
            logger.debug(f"Persisted adaptive detector data to {self.persistence_file}")
        except Exception as e:
            logger.error(f"Failed to persist adaptive detector data: {e}")
    
    def _load_persisted_data(self):
        """Load persisted data from file"""
        if not self.persistence_file or not os.path.exists(self.persistence_file):
            return
        
        try:
            # Load data
            with open(self.persistence_file, 'rb') as f:
                data = pickle.load(f)
            
            # Restore environment parameters
            if 'environment_parameters' in data:
                self.environment_parameters = {
                    k: EnhancedParameterSet.from_dict(v)
                    for k, v in data['environment_parameters'].items()
                }
            
            # Restore detection memory
            if 'detection_memory' in data:
                self.detection_memory = [
                    {
                        'result': DetectionResult(
                            success=entry['result']['success'],
                            quality_score=entry['result']['quality_score'],
                            parameters=entry['result']['parameters']
                        ),
                        'environment': EnhancedEnvironmentCondition.from_dict(entry['environment']),
                        'parameters': EnhancedParameterSet.from_dict(entry['parameters']),
                        'timestamp': entry['timestamp']
                    }
                    for entry in data['detection_memory']
                ]
            
            logger.debug(f"Loaded adaptive detector data from {self.persistence_file}")
        except Exception as e:
            logger.error(f"Failed to load adaptive detector data: {e}")
"""
Enhanced adaptive detection algorithms for RSPS Color Bot v3
"""