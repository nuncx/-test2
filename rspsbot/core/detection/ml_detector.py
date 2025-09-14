"""
Machine learning-based detection for RSPS Color Bot v3
"""
import logging
import numpy as np
import cv2
import os
import time
from typing import Tuple, List, Dict, Optional, Any
from pathlib import Path
import threading

from ..config import ROI

# Get module logger
logger = logging.getLogger('rspsbot.core.detection.ml_detector')

class MLDetector:
    """
    Machine learning-based detector for game objects
    
    This class provides object detection capabilities using machine learning models.
    It supports multiple model backends and can be used alongside traditional
    color-based detection for improved accuracy.
    """
    
    # Supported model types
    MODEL_TYPE_YOLO = "yolo"
    MODEL_TYPE_TENSORFLOW = "tensorflow"
    MODEL_TYPE_ONNX = "onnx"
    
    def __init__(self, config_manager=None):
        """
        Initialize the ML detector
        
        Args:
            config_manager: Configuration manager
        """
        self.config_manager = config_manager
        self.model = None
        self.model_type = None
        self.class_names = []
        self.confidence_threshold = 0.5
        self.nms_threshold = 0.4
        self._model_lock = threading.RLock()
        
        # Initialize from config if provided
        if config_manager:
            self._init_from_config()
    
    def _init_from_config(self):
        """Initialize detector from configuration"""
        if not self.config_manager:
            return
        
        # Get model path
        model_path = self.config_manager.get('ml_model_path')
        if not model_path or not os.path.exists(model_path):
            logger.warning("ML model path not found in configuration")
            return
        
        # Get model type
        model_type = self.config_manager.get('ml_model_type', self.MODEL_TYPE_YOLO)
        
        # Get class names
        class_names = self.config_manager.get('ml_class_names', [])
        
        # Get thresholds
        confidence_threshold = self.config_manager.get('ml_confidence_threshold', 0.5)
        nms_threshold = self.config_manager.get('ml_nms_threshold', 0.4)
        
        # Load model
        self.load_model(model_path, model_type, class_names, confidence_threshold, nms_threshold)
    
    def load_model(
        self,
        model_path: str,
        model_type: str = MODEL_TYPE_YOLO,
        class_names: List[str] = None,
        confidence_threshold: float = 0.5,
        nms_threshold: float = 0.4
    ) -> bool:
        """
        Load a machine learning model
        
        Args:
            model_path: Path to the model file
            model_type: Type of model (yolo, tensorflow, onnx)
            class_names: List of class names
            confidence_threshold: Confidence threshold for detections
            nms_threshold: Non-maximum suppression threshold
        
        Returns:
            True if model was loaded successfully, False otherwise
        """
        with self._model_lock:
            try:
                self.model_type = model_type.lower()
                self.confidence_threshold = confidence_threshold
                self.nms_threshold = nms_threshold
                self.class_names = class_names or []
                
                if self.model_type == self.MODEL_TYPE_YOLO:
                    return self._load_yolo_model(model_path)
                elif self.model_type == self.MODEL_TYPE_TENSORFLOW:
                    return self._load_tensorflow_model(model_path)
                elif self.model_type == self.MODEL_TYPE_ONNX:
                    return self._load_onnx_model(model_path)
                else:
                    logger.error(f"Unsupported model type: {model_type}")
                    return False
            
            except Exception as e:
                logger.error(f"Error loading model: {e}")
                self.model = None
                return False
    
    def _load_yolo_model(self, model_path: str) -> bool:
        """
        Load a YOLO model
        
        Args:
            model_path: Path to the model file
        
        Returns:
            True if model was loaded successfully, False otherwise
        """
        try:
            # Check if model path exists
            if not os.path.exists(model_path):
                logger.error(f"Model file not found: {model_path}")
                return False
            
            # Get model directory and filename
            model_dir = os.path.dirname(model_path)
            model_name = os.path.basename(model_path)
            
            # Check if it's a YOLO format (weights file with .weights extension)
            if model_name.endswith('.weights'):
                # Look for .cfg file with same name
                cfg_path = os.path.join(model_dir, model_name.replace('.weights', '.cfg'))
                if not os.path.exists(cfg_path):
                    logger.error(f"Config file not found: {cfg_path}")
                    return False
                
                # Load YOLO model
                self.model = cv2.dnn.readNetFromDarknet(cfg_path, model_path)
                logger.info(f"Loaded YOLO model from {model_path} and {cfg_path}")
            
            # Check if it's a YOLO ONNX format
            elif model_name.endswith('.onnx'):
                # Load YOLO ONNX model
                self.model = cv2.dnn.readNetFromONNX(model_path)
                logger.info(f"Loaded YOLO ONNX model from {model_path}")
            
            else:
                logger.error(f"Unsupported YOLO model format: {model_path}")
                return False
            
            # Try to use CUDA if available
            try:
                self.model.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
                self.model.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
                logger.info("Using CUDA backend for YOLO model")
            except:
                logger.info("CUDA not available, using CPU backend for YOLO model")
                self.model.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.model.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading YOLO model: {e}")
            return False
    
    def _load_tensorflow_model(self, model_path: str) -> bool:
        """
        Load a TensorFlow model
        
        Args:
            model_path: Path to the model file
        
        Returns:
            True if model was loaded successfully, False otherwise
        """
        try:
            # Check if TensorFlow is available
            try:
                import tensorflow as tf
            except ImportError:
                logger.error("TensorFlow not installed. Please install tensorflow or tensorflow-lite.")
                return False
            
            # Check if model path exists
            if not os.path.exists(model_path):
                logger.error(f"Model file not found: {model_path}")
                return False
            
            # Load TensorFlow model
            self.model = tf.saved_model.load(model_path)
            logger.info(f"Loaded TensorFlow model from {model_path}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading TensorFlow model: {e}")
            return False
    
    def _load_onnx_model(self, model_path: str) -> bool:
        """
        Load an ONNX model
        
        Args:
            model_path: Path to the model file
        
        Returns:
            True if model was loaded successfully, False otherwise
        """
        try:
            # Check if model path exists
            if not os.path.exists(model_path):
                logger.error(f"Model file not found: {model_path}")
                return False
            
            # Load ONNX model
            self.model = cv2.dnn.readNetFromONNX(model_path)
            logger.info(f"Loaded ONNX model from {model_path}")
            
            # Try to use CUDA if available
            try:
                self.model.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
                self.model.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
                logger.info("Using CUDA backend for ONNX model")
            except:
                logger.info("CUDA not available, using CPU backend for ONNX model")
                self.model.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.model.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading ONNX model: {e}")
            return False
    
    def detect(
        self,
        img_bgr: np.ndarray,
        roi: Optional[ROI] = None,
        classes: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect objects in an image
        
        Args:
            img_bgr: Input image in BGR format
            roi: Region of interest (optional)
            classes: List of class indices to detect (optional)
        
        Returns:
            List of detection results, each containing:
            - class_id: Class ID
            - class_name: Class name (if available)
            - confidence: Detection confidence
            - bbox: Bounding box [x, y, width, height]
        """
        with self._model_lock:
            if self.model is None:
                logger.error("No model loaded")
                return []
            
            # Apply ROI if specified
            if roi:
                x, y, w, h = roi.left, roi.top, roi.width, roi.height
                img = img_bgr[y:y+h, x:x+w]
            else:
                img = img_bgr
                x, y = 0, 0
            
            # Get image dimensions
            height, width = img.shape[:2]
            
            if self.model_type == self.MODEL_TYPE_YOLO:
                return self._detect_yolo(img, width, height, x, y, classes)
            elif self.model_type == self.MODEL_TYPE_TENSORFLOW:
                return self._detect_tensorflow(img, width, height, x, y, classes)
            elif self.model_type == self.MODEL_TYPE_ONNX:
                return self._detect_onnx(img, width, height, x, y, classes)
            else:
                logger.error(f"Unsupported model type: {self.model_type}")
                return []
    
    def _detect_yolo(
        self,
        img: np.ndarray,
        width: int,
        height: int,
        offset_x: int,
        offset_y: int,
        classes: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect objects using YOLO model
        
        Args:
            img: Input image
            width: Image width
            height: Image height
            offset_x: X offset for ROI
            offset_y: Y offset for ROI
            classes: List of class indices to detect (optional)
        
        Returns:
            List of detection results
        """
        try:
            # Create blob from image
            blob = cv2.dnn.blobFromImage(img, 1/255.0, (416, 416), swapRB=True, crop=False)
            
            # Set input and get output layer names
            self.model.setInput(blob)
            
            # Get output layer names
            layer_names = self.model.getLayerNames()
            output_layers = [layer_names[i - 1] for i in self.model.getUnconnectedOutLayers()]
            
            # Forward pass
            outputs = self.model.forward(output_layers)
            
            # Process outputs
            class_ids = []
            confidences = []
            boxes = []
            
            for output in outputs:
                for detection in output:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]
                    
                    # Filter by confidence and class
                    if confidence > self.confidence_threshold and (classes is None or class_id in classes):
                        # YOLO returns center, width, height
                        center_x = int(detection[0] * width)
                        center_y = int(detection[1] * height)
                        w = int(detection[2] * width)
                        h = int(detection[3] * height)
                        
                        # Calculate top-left corner
                        x = int(center_x - w / 2)
                        y = int(center_y - h / 2)
                        
                        class_ids.append(class_id)
                        confidences.append(float(confidence))
                        boxes.append([x, y, w, h])
            
            # Apply non-maximum suppression
            indices = cv2.dnn.NMSBoxes(boxes, confidences, self.confidence_threshold, self.nms_threshold)
            
            # Prepare results
            results = []
            
            for i in indices:
                # Handle different OpenCV versions
                if isinstance(i, (list, tuple)):
                    i = i[0]
                
                box = boxes[i]
                x, y, w, h = box
                
                # Adjust for ROI offset
                x += offset_x
                y += offset_y
                
                class_id = class_ids[i]
                confidence = confidences[i]
                
                # Get class name if available
                class_name = self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}"
                
                results.append({
                    'class_id': class_id,
                    'class_name': class_name,
                    'confidence': confidence,
                    'bbox': [x, y, w, h]
                })
            
            return results
        
        except Exception as e:
            logger.error(f"Error in YOLO detection: {e}")
            return []
    
    def _detect_tensorflow(
        self,
        img: np.ndarray,
        width: int,
        height: int,
        offset_x: int,
        offset_y: int,
        classes: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect objects using TensorFlow model
        
        Args:
            img: Input image
            width: Image width
            height: Image height
            offset_x: X offset for ROI
            offset_y: Y offset for ROI
            classes: List of class indices to detect (optional)
        
        Returns:
            List of detection results
        """
        try:
            import tensorflow as tf
            
            # Preprocess image
            input_tensor = tf.convert_to_tensor(img)
            input_tensor = input_tensor[tf.newaxis, ...]
            
            # Run inference
            detections = self.model(input_tensor)
            
            # Process results
            results = []
            
            # Extract detection results
            num_detections = int(detections.pop('num_detections'))
            detections = {key: value[0, :num_detections].numpy() for key, value in detections.items()}
            
            boxes = detections['detection_boxes']
            classes_detected = detections['detection_classes'].astype(np.int64)
            scores = detections['detection_scores']
            
            for i in range(num_detections):
                if scores[i] >= self.confidence_threshold and (classes is None or classes_detected[i] in classes):
                    # TensorFlow returns [y_min, x_min, y_max, x_max] normalized
                    y_min, x_min, y_max, x_max = boxes[i]
                    
                    # Convert to pixel coordinates
                    x = int(x_min * width)
                    y = int(y_min * height)
                    w = int((x_max - x_min) * width)
                    h = int((y_max - y_min) * height)
                    
                    # Adjust for ROI offset
                    x += offset_x
                    y += offset_y
                    
                    class_id = int(classes_detected[i])
                    confidence = float(scores[i])
                    
                    # Get class name if available
                    class_name = self.class_names[class_id - 1] if class_id - 1 < len(self.class_names) else f"class_{class_id}"
                    
                    results.append({
                        'class_id': class_id,
                        'class_name': class_name,
                        'confidence': confidence,
                        'bbox': [x, y, w, h]
                    })
            
            return results
        
        except Exception as e:
            logger.error(f"Error in TensorFlow detection: {e}")
            return []
    
    def _detect_onnx(
        self,
        img: np.ndarray,
        width: int,
        height: int,
        offset_x: int,
        offset_y: int,
        classes: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect objects using ONNX model
        
        Args:
            img: Input image
            width: Image width
            height: Image height
            offset_x: X offset for ROI
            offset_y: Y offset for ROI
            classes: List of class indices to detect (optional)
        
        Returns:
            List of detection results
        """
        try:
            # Create blob from image (assuming YOLO-style ONNX model)
            blob = cv2.dnn.blobFromImage(img, 1/255.0, (640, 640), swapRB=True, crop=False)
            
            # Set input
            self.model.setInput(blob)
            
            # Forward pass
            outputs = self.model.forward()
            
            # Process outputs (assuming YOLOv5 ONNX format)
            results = []
            
            # YOLOv5 ONNX output is [batch, num_detections, 5+num_classes]
            for detection in outputs[0]:
                confidence = detection[4]
                
                if confidence >= self.confidence_threshold:
                    # Get class scores
                    class_scores = detection[5:]
                    class_id = np.argmax(class_scores)
                    class_confidence = class_scores[class_id]
                    
                    if class_confidence >= self.confidence_threshold and (classes is None or class_id in classes):
                        # YOLOv5 ONNX returns center, width, height normalized
                        center_x = detection[0]
                        center_y = detection[1]
                        w_norm = detection[2]
                        h_norm = detection[3]
                        
                        # Convert to pixel coordinates
                        x = int((center_x - w_norm / 2) * width)
                        y = int((center_y - h_norm / 2) * height)
                        w = int(w_norm * width)
                        h = int(h_norm * height)
                        
                        # Adjust for ROI offset
                        x += offset_x
                        y += offset_y
                        
                        # Get class name if available
                        class_name = self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}"
                        
                        results.append({
                            'class_id': int(class_id),
                            'class_name': class_name,
                            'confidence': float(class_confidence),
                            'bbox': [x, y, w, h]
                        })
            
            # Apply non-maximum suppression
            boxes = [r['bbox'] for r in results]
            confidences = [r['confidence'] for r in results]
            class_ids = [r['class_id'] for r in results]
            
            if boxes:
                indices = cv2.dnn.NMSBoxes(boxes, confidences, self.confidence_threshold, self.nms_threshold)
                
                # Filter results by NMS indices
                filtered_results = []
                for i in indices:
                    # Handle different OpenCV versions
                    if isinstance(i, (list, tuple)):
                        i = i[0]
                    
                    filtered_results.append(results[i])
                
                return filtered_results
            
            return results
        
        except Exception as e:
            logger.error(f"Error in ONNX detection: {e}")
            return []
    
    def draw_detections(self, img: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
        """
        Draw detection results on an image
        
        Args:
            img: Input image
            detections: Detection results
        
        Returns:
            Image with detections drawn
        """
        result = img.copy()
        
        for detection in detections:
            # Get detection info
            x, y, w, h = detection['bbox']
            class_name = detection['class_name']
            confidence = detection['confidence']
            
            # Generate random color based on class ID
            color = (
                (detection['class_id'] * 123) % 255,
                (detection['class_id'] * 231) % 255,
                (detection['class_id'] * 321) % 255
            )
            
            # Draw bounding box
            cv2.rectangle(result, (x, y), (x + w, y + h), color, 2)
            
            # Draw label background
            label = f"{class_name}: {confidence:.2f}"
            (label_width, label_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(result, (x, y - label_height - 10), (x + label_width, y), color, -1)
            
            # Draw label text
            cv2.putText(result, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return result
    
    def is_model_loaded(self) -> bool:
        """Check if a model is loaded"""
        return self.model is not None