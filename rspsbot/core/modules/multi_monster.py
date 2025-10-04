"""
Multi Monster Mode module for RSPS Color Bot v3
"""
import time
import logging
import random
from typing import Dict, List, Tuple, Optional, Any

from ..config import ConfigManager
from ..detection.multi_monster_detector import MultiMonsterDetector
# Corrected controller imports (modules are mouse_controller.py / keyboard_controller.py)
from ..action.mouse_controller import MouseController
from ..action.keyboard_controller import KeyboardController

# Get module logger
logger = logging.getLogger('rspsbot.core.modules.multi_monster')

class MultiMonsterModule:
    """
    Module for handling Multi Monster Mode
    """
    
    def __init__(self, config_manager: ConfigManager, mouse_controller: MouseController, keyboard_controller: KeyboardController, detector: MultiMonsterDetector):
        """
        Initialize the Multi Monster Module
        
        Args:
            config_manager: Configuration manager
            mouse_controller: Mouse controller
            keyboard_controller: Keyboard controller
            detector: Multi Monster detector
        """
        self.config_manager = config_manager
        self.mouse_controller = mouse_controller
        self.keyboard_controller = keyboard_controller
        self.detector = detector
        
        # State variables
        self.enabled = False
        self.in_combat = False
        self._prev_in_combat = False
        self.last_combat_end_time = 0
        self.last_weapon_switch_time = 0
        self.current_style = None
        self.current_target = None
        # Deterministic gating: after HP bar disappears, wait a fixed grace period before resuming detection
        self._hp_gone_until = 0.0
        self._hp_verify_until = 0.0
        self._post_attack_retry_done = False
        self._last_attack_time = 0.0
        self._post_attack_switch_retry_done = False
        
        # Load configuration
        self.load_config()
    
    def load_config(self):
        """Load configuration settings"""
        self.enabled = self.config_manager.get('multi_monster_mode_enabled', False)
        # Legacy post-combat cooldown settings are no longer used for Multi Monster Mode; gating is driven by HP-bar-gone timeout
        self.post_combat_delay_min = float(self.config_manager.get('post_combat_delay_min_s', 0.0))
        self.post_combat_delay_max = float(self.config_manager.get('post_combat_delay_max_s', 0.0))
        # Weapon switch cooldown (seconds)
        self.weapon_switch_cooldown = float(self.config_manager.get('multi_monster_weapon_switch_cooldown_s', 0.6))
        # Small pause after switching weapon before attacking (seconds)
        self.weapon_switch_to_attack_delay_s = float(self.config_manager.get('multi_monster_weapon_switch_to_attack_delay_s', 0.5))
        # Verification and retry settings for weapon switching
        self.weapon_switch_max_retries = int(self.config_manager.get('multi_monster_weapon_switch_max_retries', 5))
        self.weapon_switch_retry_delay_s = float(self.config_manager.get('multi_monster_weapon_switch_retry_delay_s', 0.5))

        # Enforce the requested runtime values and persist them so profiles are updated automatically
        try:
            desired_delay = 0.5
            desired_retries = 5
            desired_retry_delay = 0.5
            if abs(self.weapon_switch_to_attack_delay_s - desired_delay) > 1e-6:
                self.weapon_switch_to_attack_delay_s = desired_delay
                self.config_manager.set('multi_monster_weapon_switch_to_attack_delay_s', desired_delay)
            if self.weapon_switch_max_retries != desired_retries:
                self.weapon_switch_max_retries = desired_retries
                self.config_manager.set('multi_monster_weapon_switch_max_retries', desired_retries)
            if abs(self.weapon_switch_retry_delay_s - desired_retry_delay) > 1e-6:
                self.weapon_switch_retry_delay_s = desired_retry_delay
                self.config_manager.set('multi_monster_weapon_switch_retry_delay_s', desired_retry_delay)
        except Exception:
            pass
    
    def update_config(self):
        """Update configuration settings"""
        self.load_config()
    
    def process_cycle(self, frame, base_roi: Dict[str, int]) -> Dict[str, Any]:
        """
        Process a detection cycle in Multi Monster Mode
        
        Args:
            frame: Captured frame
            base_roi: Base region of interest
            
        Returns:
            Dictionary with detection results and actions taken
        """
        if not self.enabled:
            return {'enabled': False, 'action': None, 'reason': 'module_disabled'}
        
        # Check if in combat (HP bar based)
        self.in_combat = self.detector.is_in_combat()
        # Detect combat end transition internally
        if self._prev_in_combat and not self.in_combat:
            self.on_combat_end()
        self._prev_in_combat = self.in_combat
        
        # 1) If HP bar is visible → action=nothing (do not perform MM detection while in combat)
        if self.in_combat:
            return {'enabled': True, 'in_combat': True, 'action': 'nothing', 'reason': 'hp_bar_visible'}
        
        # After HP bar disappears, wait a deterministic grace equal to HP timeout before resuming detection
        if self._hp_gone_until > 0:
            now_g = time.time()
            if now_g < self._hp_gone_until:
                return {
                    'enabled': True,
                    'in_combat': False,
                    'action': 'hp_gone_wait',
                    'wait_remaining': round(self._hp_gone_until - now_g, 2),
                    'reason': 'hp_bar_gone_grace'
                }
            # Clear gate when elapsed
            self._hp_gone_until = 0.0

        # After an attack/switch+attack, allow up to configured seconds for HP bar to appear before retrying more actions
        if self._hp_verify_until > 0:
            now_v = time.time()
            if now_v <= self._hp_verify_until:
                # One-time fallback: if not in combat and we still see a target, retry a single attack during the verify window
                did_retry_click = False
                did_retry_switch = False
                if not self._post_attack_retry_done:
                    try:
                        # Small grace to avoid double-clicking too fast
                        if (now_v - float(self._last_attack_time)) >= 0.5:
                            # Prepare ROIs
                            sr = self.config_manager.get_roi('search_roi')
                            sr_dict = sr.to_dict() if sr else None
                            wr = self.config_manager.get_roi('weapon_roi')
                            wr_dict = wr.to_dict() if wr else None
                            def _inside(x: int, y: int, r: Optional[Dict[str, int]]):
                                if not r:
                                    return True
                                return (r['left'] <= x <= r['left'] + r['width'] and r['top'] <= y <= r['top'] + r['height'])

                            # First, re-check if the right combat style is worn; if detector says switch is needed, attempt a one-time switch
                            if not getattr(self, '_post_attack_switch_retry_done', False):
                                try:
                                    mm_retry_pre = self.detector.process_multi_monster_mode(frame, base_roi)
                                except Exception:
                                    mm_retry_pre = {}
                                req_style = mm_retry_pre.get('required_style')
                                act_pre = mm_retry_pre.get('action')
                                if act_pre == 'switch_weapon' and isinstance(req_style, str):
                                    try:
                                        auto_pt = self.detector.get_click_point_for_style(req_style) if hasattr(self.detector, 'get_click_point_for_style') else None
                                    except Exception:
                                        auto_pt = None
                                    if auto_pt and 'x' in auto_pt and 'y' in auto_pt and _inside(int(auto_pt['x']), int(auto_pt['y']), wr_dict):
                                        # Perform a single switch click without full verification loop (we're in a verify window already)
                                        self.mouse_controller.move_to(int(auto_pt['x']), int(auto_pt['y']))
                                        self.mouse_controller.click()
                                        self.last_weapon_switch_time = time.time()
                                        self._post_attack_switch_retry_done = True
                                        did_retry_switch = True
                                        logger.debug("[MultiMonster] verify_wait: retried weapon switch to %s at (%d,%d)", req_style, int(auto_pt['x']), int(auto_pt['y']))

                            # Prefer reusing the last known target from the attack (more stable than re-detecting mid-verify)
                            tgt_saved = self.current_target if isinstance(self.current_target, dict) else None
                            if tgt_saved and 'center_x' in tgt_saved and 'center_y' in tgt_saved and _inside(int(tgt_saved['center_x']), int(tgt_saved['center_y']), sr_dict):
                                if self.mouse_controller.move_and_click(int(tgt_saved['center_x']), int(tgt_saved['center_y']), enforce_guard=False):
                                    self._last_attack_time = time.time()
                                    self._post_attack_retry_done = True
                                    did_retry_click = True
                                    logger.debug("[MultiMonster] verify_wait: retried attack using saved target at (%d,%d)", int(tgt_saved['center_x']), int(tgt_saved['center_y']))
                            else:
                                # Secondary: try a fresh detection and retry if it suggests an attack target within ROI
                                mm_retry = self.detector.process_multi_monster_mode(frame, base_roi)
                                tgt = mm_retry.get('target')
                                act = mm_retry.get('action')
                                if tgt and 'center_x' in tgt and 'center_y' in tgt and _inside(int(tgt['center_x']), int(tgt['center_y']), sr_dict):
                                    # Retry regardless of act; during verify we just need to ensure an attack happens if plausible
                                    if self.mouse_controller.move_and_click(int(tgt['center_x']), int(tgt['center_y']), enforce_guard=False):
                                        self._last_attack_time = time.time()
                                        self._post_attack_retry_done = True
                                        did_retry_click = True
                                        logger.debug("[MultiMonster] verify_wait: retried attack using fresh detection at (%d,%d), act=%s", int(tgt['center_x']), int(tgt['center_y']), str(act))

                            if did_retry_click or did_retry_switch:
                                # Optionally extend window slightly to allow HP to appear after retry
                                try:
                                    extra = 1.5
                                    self._hp_verify_until = max(self._hp_verify_until, time.time() + extra)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                return {
                    'enabled': True,
                    'in_combat': False,
                    'action': 'verify_wait',
                    'wait_remaining': round(self._hp_verify_until - now_v, 2),
                    'reason': 'await_hp_bar_retry' if (did_retry_click or did_retry_switch) else 'await_hp_bar'
                }
            else:
                # Verification window elapsed; reset and continue with normal loop
                self._hp_verify_until = 0.0
                self._post_attack_retry_done = False
                self._post_attack_switch_retry_done = False
        
        # Process multi monster detection
        result = self.detector.process_multi_monster_mode(frame, base_roi)
        try:
            logger.debug(
                "[MultiMonster] tiles->monsters pipeline: monsters=%d required_style=%s visible_styles=%s required_visible=%s action=%s",
                len(result.get('monsters', [])),
                result.get('required_style'),
                list(result.get('visible_weapon_styles', {}).keys()) if result.get('visible_weapon_styles') else [],
                result.get('required_style_visible'),
                result.get('action')
            )
            # Persist lightweight summary for overlays / debugging
            self.config_manager.set('multi_monster_last_cycle', {
                't': time.time(),
                'monsters': len(result.get('monsters', [])),
                'required_style': result.get('required_style'),
                'visible_styles': list(result.get('visible_weapon_styles', {}).keys()) if result.get('visible_weapon_styles') else [],
                'current_style': result.get('current_style'),
                'required_visible': bool(result.get('required_style_visible')),
                'weapon_found': bool(result.get('weapon_found')),
                'action': result.get('action')
            })
        except Exception:
            pass
        
        # If no monsters detected, return
        if not result['monsters']:
            return {'enabled': True, 'in_combat': False, 'monsters': 0, 'action': 'no_monsters', 'reason': 'no_monsters_detected'}
        
        # Get target and required style
        target = result['target']
        required_style = result['required_style']
        current_style = result['current_style']
        
        # Update current style
        self.current_style = current_style
        self.current_target = target
        
        # Determine allowed click ROIs
        search_roi = None
        weapon_roi = None
        try:
            sr = self.config_manager.get_roi('search_roi')
            if sr:
                search_roi = sr.to_dict()
        except Exception:
            search_roi = None
        try:
            wr = self.config_manager.get_roi('weapon_roi')
            if wr:
                weapon_roi = wr.to_dict()
        except Exception:
            weapon_roi = None

        # Normalize ROI dicts to absolute coordinates if they are marked relative
        def _roi_abs(roi: Optional[Dict[str, int]]) -> Optional[Dict[str, int]]:
            if not roi:
                return roi
            try:
                mode = str(roi.get('mode', 'absolute'))
                if mode == 'relative':
                    # Translate by current window bbox
                    try:
                        from ..detection.capture import CaptureService  # type: ignore
                        bbox = CaptureService().get_window_bbox()
                        return {
                            'left': int(bbox['left']) + int(roi.get('left', 0)),
                            'top': int(bbox['top']) + int(roi.get('top', 0)),
                            'width': int(roi.get('width', 0)),
                            'height': int(roi.get('height', 0))
                        }
                    except Exception:
                        return roi
                elif mode == 'percent':
                    # Scale by window bbox and translate
                    try:
                        from ..detection.capture import CaptureService  # type: ignore
                        bbox = CaptureService().get_window_bbox()
                        lf = float(roi.get('left', 0.0)); tf = float(roi.get('top', 0.0))
                        wf = float(roi.get('width', 0.0)); hf = float(roi.get('height', 0.0))
                        return {
                            'left': int(bbox['left'] + lf * bbox['width']),
                            'top': int(bbox['top'] + tf * bbox['height']),
                            'width': int(max(1, wf * bbox['width'])),
                            'height': int(max(1, hf * bbox['height']))
                        }
                    except Exception:
                        return roi
                return roi
            except Exception:
                return roi

        search_roi = _roi_abs(search_roi)
        weapon_roi = _roi_abs(weapon_roi)

        def inside_roi(x: int, y: int, roi: Optional[Dict[str, int]]) -> bool:
            if not roi:
                return True
            return (roi['left'] <= x <= roi['left'] + roi['width'] and
                    roi['top'] <= y <= roi['top'] + roi['height'])

        # Determine action per new spec (switch if required style visible, else attack)
        if result['action'] == 'switch_weapon':
            # Enforce cooldown
            now = time.time()
            if (now - self.last_weapon_switch_time) < self.weapon_switch_cooldown:
                return {
                    'enabled': True,
                    'in_combat': False,
                    'monsters': len(result['monsters']),
                    'target': target,
                    'required_style': required_style,
                    'action': 'switch_cooldown',
                    'reason': 'weapon_switch_cooldown'
                }
            # Always compute a click point dynamically based on weapon ROI search (no persisted XY usage)
            try:
                auto_pt = self.detector.get_click_point_for_style(required_style) if hasattr(self.detector, 'get_click_point_for_style') else None
            except Exception:
                auto_pt = None
            weapon_position = None
            if auto_pt and 'x' in auto_pt and 'y' in auto_pt and inside_roi(int(auto_pt['x']), int(auto_pt['y']), weapon_roi):
                weapon_position = {'x': int(auto_pt['x']), 'y': int(auto_pt['y'])}

            # Validate against weapon ROI (NOT search ROI)
            if weapon_position and inside_roi(weapon_position['x'], weapon_position['y'], weapon_roi):
                # Capture pre-click visibility/current for diagnostics
                try:
                    pre_vis = self.detector.visible_weapon_styles(frame)
                except Exception:
                    pre_vis = {}
                try:
                    pre_cur = self.detector.detect_weapon(frame)
                except Exception:
                    pre_cur = None
                # Use move_to + click to avoid search ROI clamping that exists in move_and_click
                def _click_weapon():
                    self.mouse_controller.move_to(weapon_position['x'], weapon_position['y'])
                    self.mouse_controller.click()
                # Perform initial click
                _click_weapon()
                self.last_weapon_switch_time = now
                logger.debug(f"[MultiMonster] Switching weapon to {required_style} at {weapon_position}")
                # Verify switch by re-checking visible styles: required should no longer be visible
                switched_ok = False
                post_vis = {}
                post_cur = None
                try:
                    # Allow full configured retry delay (keep tiny floor to avoid zero)
                    time.sleep(max(0.06, self.weapon_switch_retry_delay_s))
                    post_vis = self.detector.visible_weapon_styles(frame)
                    post_cur = self.detector.detect_weapon(frame)
                    switched_ok = (required_style not in (post_vis.keys() if isinstance(post_vis, dict) else [])) or (post_cur == required_style)
                    if not switched_ok:
                        # Retry up to N times
                        for attempt in range(self.weapon_switch_max_retries):
                            logger.debug(f"[MultiMonster] Switch verify failed; retrying click {attempt+1}/{self.weapon_switch_max_retries}")
                            _click_weapon()
                            time.sleep(max(0.06, self.weapon_switch_retry_delay_s))
                            post_vis = self.detector.visible_weapon_styles(frame)
                            post_cur = self.detector.detect_weapon(frame)
                            if (required_style not in (post_vis.keys() if isinstance(post_vis, dict) else [])) or (post_cur == required_style):
                                switched_ok = True
                                break
                except Exception:
                    pass
                if not switched_ok:
                    logger.debug(
                        "[MultiMonster] Weapon switch verification failed; pre_vis=%s pre_cur=%s post_vis=%s post_cur=%s", 
                        list(pre_vis.keys()) if isinstance(pre_vis, dict) else pre_vis,
                        pre_cur,
                        list(post_vis.keys()) if isinstance(post_vis, dict) else post_vis,
                        post_cur
                    )
                    # Fallback: optimistically chain the attack once if target is valid inside ROI
                    if target and 'center_x' in target and 'center_y' in target and inside_roi(target['center_x'], target['center_y'], search_roi):
                        try:
                            if self.weapon_switch_to_attack_delay_s > 0:
                                time.sleep(max(0.0, self.weapon_switch_to_attack_delay_s))
                        except Exception:
                            pass
                        ok = self.mouse_controller.move_and_click(target['center_x'], target['center_y'], enforce_guard=False)
                        if ok:
                            self._last_attack_time = time.time()
                            self._hp_verify_until = time.time() + 5.0
                            logger.debug("[MultiMonster] Fallback switch-and-attack: clicked target at (%d,%d)", int(target['center_x']), int(target['center_y']))
                            return {
                                'enabled': True,
                                'in_combat': False,
                                'monsters': len(result['monsters']),
                                'target': target,
                                'required_style': required_style,
                                'action': 'switch_and_attack',
                                'reason': 'switch_verify_failed_but_attacked'
                            }
                        # If click blocked/failed, do not claim attack
                        return {
                            'enabled': True,
                            'in_combat': False,
                            'monsters': len(result['monsters']),
                            'target': target,
                            'required_style': required_style,
                            'action': 'switch_weapon',
                            'reason': 'switch_verify_failed_attack_blocked'
                        }
                    # Otherwise, do not chain attack
                    return {
                        'enabled': True,
                        'in_combat': False,
                        'monsters': len(result['monsters']),
                        'target': target,
                        'required_style': required_style,
                        'action': 'switch_weapon',
                        'reason': 'switch_verify_failed'
                    }
                # After verified switching, attempt attack if target still valid
                if target and 'center_x' in target and 'center_y' in target and inside_roi(target['center_x'], target['center_y'], search_roi):
                    # Brief pause to allow the UI to register the style switch before attacking
                    try:
                        if self.weapon_switch_to_attack_delay_s > 0:
                            # Honor full configured delay (no cap), keep non-negative
                            time.sleep(max(0.0, self.weapon_switch_to_attack_delay_s))
                    except Exception:
                        pass
                    ok = self.mouse_controller.move_and_click(target['center_x'], target['center_y'], enforce_guard=False)
                    if ok:
                        self._last_attack_time = time.time()
                        self._hp_verify_until = time.time() + 5.0
                        logger.debug("[MultiMonster] Switched then attacked target at (%d,%d) style=%s", int(target['center_x']), int(target['center_y']), str(required_style))
                        return {
                            'enabled': True,
                            'in_combat': False,
                            'monsters': len(result['monsters']),
                            'target': target,
                            'required_style': required_style,
                            'action': 'switch_and_attack',
                            'reason': 'switched_then_attacked'
                        }
                    # If click blocked/failed, fall back to switched only
                    return {
                        'enabled': True,
                        'in_combat': False,
                        'monsters': len(result['monsters']),
                        'target': target,
                        'required_style': required_style,
                        'action': 'switch_weapon',
                        'reason': 'attack_click_blocked'
                    }
                else:
                    # Log detailed gating reason for not attacking after a verified switch
                    logger.debug(
                        "[MultiMonster] Post-switch target invalid or outside search ROI; target=(%s,%s) search_roi=%s",
                        target.get('center_x') if isinstance(target, dict) else None,
                        target.get('center_y') if isinstance(target, dict) else None,
                        search_roi
                    )
                return {
                    'enabled': True,
                    'in_combat': False,
                    'monsters': len(result['monsters']),
                    'target': target,
                    'required_style': required_style,
                    'action': 'switch_weapon',
                    'reason': 'switched_weapon'
                }
            # If we get here, we couldn't click the weapon
            # Determine why: no dynamic click point found in Weapon ROI
            sw_reason = 'weapon_click_point_not_found'
            return {
                'enabled': True,
                'in_combat': False,
                'monsters': len(result['monsters']),
                'target': target,
                'required_style': required_style,
                'action': 'none',
                'reason': sw_reason
            }
        elif result['action'] == 'attack':
            if target and 'center_x' in target and 'center_y' in target and inside_roi(target['center_x'], target['center_y'], search_roi):
                ok = self.mouse_controller.move_and_click(target['center_x'], target['center_y'], enforce_guard=False)
                if ok:
                    logger.debug(f"[MultiMonster] Attacking target at ({target['center_x']},{target['center_y']}) style={required_style}")
                    # Arm verification window using global combat timeout
                    try:
                        verify_s = float(self.config_manager.get('combat_not_seen_timeout_s', 5.0))
                    except Exception:
                        verify_s = 5.0
                    self._hp_verify_until = time.time() + max(0.5, verify_s)
                    self._post_attack_retry_done = False
                    self._last_attack_time = time.time()
                    return {
                        'enabled': True,
                        'in_combat': False,
                        'monsters': len(result['monsters']),
                        'target': target,
                        'required_style': required_style,
                        'action': 'attack',
                        'reason': 'attacked'
                    }
                else:
                    logger.debug(
                        "[MultiMonster] Attack click blocked/failed at (%s,%s) within ROI=%s",
                        str(target.get('center_x')), str(target.get('center_y')), str(search_roi)
                    )
                    return {
                        'enabled': True,
                        'in_combat': False,
                        'monsters': len(result['monsters']),
                        'target': target,
                        'required_style': required_style,
                        'action': 'none',
                        'reason': 'attack_click_blocked'
                    }
            elif target:
                logger.debug(
                    f"[MultiMonster] Skipping attack outside allowed ROI target=({target.get('center_x')},{target.get('center_y')}) allowed={search_roi}"
                )
                return {
                    'enabled': True,
                    'in_combat': False,
                    'monsters': len(result['monsters']),
                    'target': target,
                    'required_style': required_style,
                    'action': 'none',
                    'reason': 'target_outside_allowed_roi'
                }
        
        # Default return: carry through target and required_style for observability
        # Default no-op
        return {
            'enabled': True,
            'in_combat': False,
            'monsters': len(result['monsters']),
            'target': result.get('target'),
            'required_style': result.get('required_style'),
            'action': 'none',
            'reason': 'no_action_taken'
        }
    
    def on_combat_end(self):
        """Handle combat end event"""
        self.last_combat_end_time = time.time()
        # Use HP bar timeout as deterministic grace before resuming multi-monster detection
        try:
            hp_gone_grace = float(self.config_manager.get('combat_not_seen_timeout_s', 0.0))
        except Exception:
            hp_gone_grace = 0.0
        self._hp_gone_until = self.last_combat_end_time + max(0.0, hp_gone_grace)
        logger.debug(
            f"[MultiMonster] Combat ended. HP-bar-gone grace set to {max(0.0, hp_gone_grace):.2f}s"
        )
    
    def is_enabled(self) -> bool:
        """Check if Multi Monster Mode is enabled"""
        return self.enabled