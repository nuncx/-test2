def detect_monsters_near_tile(
        self,
        frame: np.ndarray,
        base_roi: Dict[str, int],
        tile_center: Tuple[int, int]
    ) -> List[Dict[str, Any]]:
        """
        Detect monsters near a tile with progressive ROI expansion
        
        Args:
            frame: Input frame
            base_roi: Base region of interest
            tile_center: Tile center point (x, y)
        
        Returns:
            List of monster dictionaries with position and metadata
        """
        # Check if monster detection is enabled
        if not self.config_manager.get('detect_monsters', True):
            return []
        
        # Get monster detection parameters
        base_radius = self.config_manager.get('around_tile_radius', 120)
        max_expansion = self.config_manager.get('roi_max_expansion', 3)
        expansion_factor = self.config_manager.get('roi_expansion_factor', 1.2)
        
        # Try detection with progressively larger ROIs
        monsters = []
        expansion_level = 0
        
        while not monsters and expansion_level <= max_expansion:
            # Calculate expanded radius
            radius = int(base_radius * (expansion_factor ** expansion_level))
            
            # Create ROI with expanded radius
            roi_bbox = self._create_detection_roi_with_radius(tile_center, base_roi, radius)
            
            if roi_bbox['width'] <= 0 or roi_bbox['height'] <= 0:
                break
            
            # Get monster colors
            monster_colors = []
            monster_colors_dicts = self.config_manager.get('monster_colors', [])
            
            for color_dict in monster_colors_dicts:
                try:
                    color = ColorSpec(
                        rgb=tuple(color_dict['rgb']),
                        tol_rgb=color_dict.get('tol_rgb', 8),
                        use_hsv=color_dict.get('use_hsv', True),
                        tol_h=color_dict.get('tol_h', 4),
                        tol_s=color_dict.get('tol_s', 30),
                        tol_v=color_dict.get('tol_v', 30)
                    )
                    monster_colors.append(color)
                except Exception as e:
                    logger.error(f"Error creating monster ColorSpec: {e}")
            
            if not monster_colors:
                logger.warning("No valid monster colors configured")
                return []
            
            # Capture ROI
            roi_frame = frame[
                roi_bbox['top'] - base_roi['top']:roi_bbox['top'] - base_roi['top'] + roi_bbox['height'],
                roi_bbox['left'] - base_roi['left']:roi_bbox['left'] - base_roi['left'] + roi_bbox['width']
            ]
            
            # Detection parameters
            step = max(1, self.config_manager.get('monster_scan_step', 1))
            use_precise = self.config_manager.get('use_precise_mode', True)
            monster_min_area = self.config_manager.get('monster_min_area', 15)
            
            # Get additional config for advanced detection
            config_dict = {
                'monster_sat_min': self.config_manager.get('monster_sat_min', 50),
                'monster_val_min': self.config_manager.get('monster_val_min', 50),
                'monster_exclude_tile_color': self.config_manager.get('monster_exclude_tile_color', True),
                'monster_exclude_tile_dilate': self.config_manager.get('monster_exclude_tile_dilate', 1),
                'monster_morph_open_iters': self.config_manager.get('monster_morph_open_iters', 1),
                'monster_morph_close_iters': self.config_manager.get('monster_morph_close_iters', 2),
                'monster_use_lab_assist': self.config_manager.get('monster_use_lab_assist', True),  # Enable by default
                'monster_lab_tolerance': self.config_manager.get('monster_lab_tolerance', 20),
                'tile_color': self.config_manager.get('tile_color')
            }
            
            try:
                # Build mask and find contours
                _, contours = build_mask_multi(
                    roi_frame,
                    monster_colors,
                    step,
                    use_precise,
                    monster_min_area,
                    config_dict
                )
                
                # If no contours found, try adaptive detection
                if not contours and self.config_manager.get('adaptive_monster_detection', True):
                    contours = self._adaptive_monster_detection(roi_frame, monster_colors, config_dict)
                
                # Convert contours to screen points and create monster objects
                monsters = []
                
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
                    screen_x = roi_bbox['left'] + cx_small * step
                    screen_y = roi_bbox['top'] + cy_small * step
                    
                    # Calculate area and size
                    area = cv2.contourArea(cnt)
                    x, y, w, h = cv2.boundingRect(cnt)
                    
                    # Create monster object
                    monster = {
                        'position': (screen_x, screen_y),
                        'area': area * step * step,
                        'width': w * step,
                        'height': h * step,
                        'tile_center': tile_center,
                        'distance': ((screen_x - tile_center[0]) ** 2 + (screen_y - tile_center[1]) ** 2) ** 0.5,
                        'expansion_level': expansion_level  # Track which expansion level found this monster
                    }
                    
                    monsters.append(monster)
                
                # If monsters found, break the loop
                if monsters:
                    if expansion_level > 0:
                        logger.debug(f"Found {len(monsters)} monsters at expansion level {expansion_level}")
                    break
                
                # Otherwise, try with a larger radius
                expansion_level += 1
                logger.debug(f"No monsters found at expansion level {expansion_level-1}, trying level {expansion_level}")
                
            except Exception as e:
                logger.error(f"Error detecting monsters near tile: {e}")
                return []
        
        if monsters:
            logger.debug(f"Detected {len(monsters)} monsters near tile {tile_center}")
        
        return monsters