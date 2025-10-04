"""
OCR-based ChatWatcher service: polls a Chat ROI, OCRs text lines, matches triggers, and executes actions.
"""
from __future__ import annotations
import time
import logging
import threading
import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import pytesseract  # type: ignore
    from pytesseract import Output as TessOutput  # type: ignore
except Exception:  # pragma: no cover
    pytesseract = None
    TessOutput = None

from ..config import ConfigManager, ROI, ColorSpec
from ..detection.capture import CaptureService
from ..detection.color_detector import build_mask, build_mask_multi
from ..state import EventSystem
from ..action.action_manager import ActionManager

logger = logging.getLogger('rspsbot.core.modules.chat_watcher')


class ChatWatcher(threading.Thread):
    """Background thread that OCRs the chat and fires actions based on triggers."""

    def __init__(
        self,
        config: ConfigManager,
        capture: CaptureService,
        actions: ActionManager,
        events: EventSystem,
    ) -> None:
        super().__init__(daemon=True)
        self.config = config
        self.capture = capture
        self.actions = actions
        self.events = events
        self._stop = threading.Event()
        self._seen: List[str] = []  # rolling buffer of recent line hashes

    def stop(self) -> None:
        self._stop.set()

    def _roi_dict(self, roi: Any) -> Dict[str, int]:
        if roi is None:
            return {}
        if isinstance(roi, dict):
            return {
                'left': int(roi.get('left', 0)),
                'top': int(roi.get('top', 0)),
                'width': int(roi.get('width', 0)),
                'height': int(roi.get('height', 0)),
            }
        if hasattr(roi, 'to_dict'):
            return self._roi_dict(roi.to_dict())
        return {}

    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        # Convert to gray and enhance contrast, adaptive threshold to cope with gradients
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        except Exception:
            gray = img
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 41, 10)
        # Small open to reduce speckles
        bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((1, 1), np.uint8))
        return bw

    def _ocr_lines(self, img: np.ndarray) -> List[str]:
        if pytesseract is None:
            logger.debug("pytesseract not available; chat OCR disabled")
            return []
        # Use configured language(s)
        lang = str(self.config.get('chat_ocr_lang', 'eng') or 'eng')
        cfg = f"--oem 3 --psm 6 -l {lang}"
        try:
            txt = pytesseract.image_to_string(img, config=cfg)
        except Exception as e:
            logger.debug(f"OCR error: {e}")
            return []
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        return lines

    def _ocr_line_boxes(self, img_bin: np.ndarray) -> List[Tuple[str, Tuple[int, int, int, int]]]:
        """Return list of (line_text_lower, (x,y,w,h)) from OCR using image_to_data() on a binarized image.
        """
        if pytesseract is None or TessOutput is None:
            return []
        try:
            lang = str(self.config.get('chat_ocr_lang', 'eng') or 'eng')
            data = pytesseract.image_to_data(img_bin, output_type=TessOutput.DICT, config=f"-l {lang}")
        except Exception:
            return []
        n = int(data.get('level') and len(data['level']) or 0)
        if n == 0:
            return []
        lines = {}
        for i in range(n):
            conf = data.get('conf', ['-1'])[i]
            try:
                if conf is None or (isinstance(conf, str) and conf.strip() == "-1"):
                    continue
            except Exception:
                pass
            txt = data.get('text', [''])[i]
            if not txt or not str(txt).strip():
                continue
            key = (data.get('block_num', [0])[i], data.get('par_num', [0])[i], data.get('line_num', [0])[i])
            x = int(data.get('left', [0])[i]); y = int(data.get('top', [0])[i])
            w = int(data.get('width', [0])[i]); h = int(data.get('height', [0])[i])
            if key not in lines:
                lines[key] = {
                    'text': str(txt),
                    'bbox': [x, y, x + w, y + h]
                }
            else:
                lines[key]['text'] += ' ' + str(txt)
                bx0, by0, bx1, by1 = lines[key]['bbox']
                lines[key]['bbox'] = [min(bx0, x), min(by0, y), max(bx1, x + w), max(by1, y + h)]
        results: List[Tuple[str, Tuple[int, int, int, int]]] = []
        for v in lines.values():
            t = v['text'].strip().lower()
            x0, y0, x1, y1 = v['bbox']
            results.append((t, (x0, y0, max(1, x1 - x0), max(1, y1 - y0))))
        return results

    def _verify_text_color(self, color_img: np.ndarray, bin_img: np.ndarray, pattern_lower: str, spec: ColorSpec) -> bool:
        """Verify that the OCR line matching pattern_lower has enough pixels of the target color.
        Uses OCR line bounding boxes and checks color mask coverage within the box.
        """
        try:
            lines = self._ocr_line_boxes(bin_img)
            if not lines:
                return False
            # Find a line containing the pattern
            match_bbox = None
            for t, bbox in lines:
                if pattern_lower in t:
                    match_bbox = bbox
                    break
            if match_bbox is None:
                return False
            x, y, w, h = match_bbox
            x = max(0, min(color_img.shape[1] - 1, x))
            y = max(0, min(color_img.shape[0] - 1, y))
            w = max(1, min(color_img.shape[1] - x, w))
            h = max(1, min(color_img.shape[0] - y, h))
            roi = color_img[y:y + h, x:x + w]
            if roi is None or roi.size == 0:
                return False
            # Build color mask for the target spec within the line bbox
            try:
                mask, _contours = build_mask(roi, spec, step=1, precise=True, min_area=1)
            except Exception:
                return False
            if mask is None or mask.size == 0:
                return False
            # Optional dilation to capture thin/anti-aliased text
            try:
                iters = int(self.config.get('chat_color_mask_dilate_iters', 0) or 0)
                if iters > 0:
                    kernel = np.ones((3, 3), np.uint8)
                    mask = cv2.dilate(mask, kernel, iterations=iters)
            except Exception:
                pass
            pos = int((mask > 0).sum())
            total = int(mask.size)
            if total <= 0:
                return False
            ratio = pos / float(total)
            min_ratio = float(self.config.get('chat_color_verify_min_ratio', 0.03))
            min_pixels = int(self.config.get('chat_color_verify_min_pixels', 30))
            ok = (ratio >= min_ratio) or (pos >= min_pixels)
            # Optional debug: save crop and mask to outputs/chat_debug_*.png
            if bool(self.config.get('chat_debug_save', False)):
                try:
                    import os
                    outdir = self.config.get('debug_output_dir', 'outputs') or 'outputs'
                    os.makedirs(outdir, exist_ok=True)
                    ts = int(time.time() * 1000)
                    cv2.imwrite(os.path.join(outdir, f"chat_crop_{ts}.png"), roi)
                    cv2.imwrite(os.path.join(outdir, f"chat_mask_{ts}.png"), mask)
                except Exception:
                    pass
            return ok
        except Exception:
            return False

    def _verify_template(self, color_img: np.ndarray, pattern_lower: str, bbox: Tuple[int,int,int,int]) -> bool:
        """Optional template verification inside the line bbox using grayscale NCC.
        Returns True if either templates disabled or match passes threshold.
        """
        try:
            if not bool(self.config.get('chat_template_enable', False)):
                return True
            # Pick template path by pattern
            tpath = None
            p = pattern_lower
            if 'you better run!' in p:
                tpath = self.config.get('chat_template_ybr_path')
            elif 'your prayers have been disabled!' in p:
                tpath = self.config.get('chat_template_prayer_disabled_path')
            elif 'rebirth demon disabled your prayers' in p:
                tpath = self.config.get('chat_template_rebirth_disabled_path')
            if not tpath:
                return True
            import os
            if not os.path.exists(tpath):
                logger.warning(f"Chat template file not found: {tpath}")
                return True
            x, y, w, h = bbox
            x = max(0, min(color_img.shape[1] - 1, x))
            y = max(0, min(color_img.shape[0] - 1, y))
            w = max(1, min(color_img.shape[1] - x, w))
            h = max(1, min(color_img.shape[0] - y, h))
            roi = color_img[y:y+h, x:x+w]
            if roi is None or roi.size == 0:
                return False
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            tmpl = cv2.imread(tpath, cv2.IMREAD_GRAYSCALE)
            if tmpl is None or tmpl.size == 0:
                logger.warning(f"Failed to read chat template: {tpath}")
                return True
            if gray.shape[0] < tmpl.shape[0] or gray.shape[1] < tmpl.shape[1]:
                return False
            res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
            minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(res)
            thr = float(self.config.get('chat_template_threshold', 0.7))
            return maxVal >= thr
        except Exception:
            return True

    def _dedupe(self, line: str) -> bool:
        h = hashlib.md5(line.encode('utf-8')).hexdigest()
        if h in self._seen:
            return False
        self._seen.append(h)
        if len(self._seen) > 400:
            self._seen = self._seen[-200:]
        return True

    def _match_trigger(self, line: str) -> Optional[Dict[str, Any]]:
        trig_list = self.config.get('chat_triggers', []) or []
        norm = line.lower() if bool(self.config.get('chat_normalize_case', True)) else line
        for tr in trig_list:
            try:
                pat = str(tr.get('pattern', ''))
                is_regex = bool(tr.get('regex', False))
                action = str(tr.get('action', '')).strip()
                if not pat or not action:
                    continue
                if is_regex:
                    if re.search(pat, norm, flags=re.IGNORECASE):
                        return {'action': action, 'pattern': pat}
                else:
                    if pat.lower() in norm.lower():
                        return {'action': action, 'pattern': pat}
            except Exception:
                continue
        return None

    def _click_prayer_enable(self) -> bool:
        xy = self.config.get('chat_prayer_enable_xy') or {'x': 0, 'y': 0}
        x, y = int(xy.get('x', 0)), int(xy.get('y', 0))
        if x <= 0 and y <= 0:
            logger.warning("chat_prayer_enable_xy not set; skipping click")
            return False
        # Convert window-relative to absolute if within window bounds
        abs_x, abs_y = x, y
        try:
            bbox = self.capture.get_window_bbox()
            if 0 <= x <= int(bbox.get('width', 0)) and 0 <= y <= int(bbox.get('height', 0)):
                abs_x = int(bbox.get('left', 0)) + x
                abs_y = int(bbox.get('top', 0)) + y
        except Exception:
            pass
        mc = self.actions.mouse_controller
        # Double-click to ensure prayer toggles reliably
        return mc.move_and_click(
            abs_x,
            abs_y,
            clicks=2,
            enforce_guard=False,
            clamp_to_search_roi=False
        )

    def _choose_ybr_tile_and_click(self) -> bool:
        # Scan the Search ROI for the configured YBR tile color, pick a tile not equal to last clicked
        base_roi_obj = self.config.get_roi('search_roi')
        if not base_roi_obj:
            return False
        base_roi = base_roi_obj.to_dict() if hasattr(base_roi_obj, 'to_dict') else {}
        frame = self.capture.capture_region(base_roi_obj)
        if frame is None:
            return False
        spec = self.config.get_color_spec('chat_ybr_tile_color')
        if not spec:
            logger.warning('chat_ybr_tile_color not configured')
            return False
        step = 1
        try:
            mask, contours = build_mask(frame, spec, step, True, min_area=12)
        except Exception:
            return False
        if not contours:
            return False
        # Compute candidate centers
        centers: List[Tuple[int, int]] = []
        for cnt in contours:
            M = cv2.moments(cnt)
            if M.get('m00', 0) == 0:
                x, y, w, h = cv2.boundingRect(cnt)
                cx, cy = x + w // 2, y + h // 2
            else:
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])
            # Translate to screen
            centers.append((int(base_roi.get('left', 0) + cx), int(base_roi.get('top', 0) + cy)))
        if not centers:
            return False
        # Avoid immediate repeat: recall last center from config temp cache
        last = self.config.get('_chat_last_ybr_click') or None
        choice = None
        for pt in centers:
            if last is None or (abs(pt[0]-last[0]) > 6 or abs(pt[1]-last[1]) > 6):
                choice = pt
                break
        if choice is None:
            choice = centers[0]
        mc = self.actions.mouse_controller
        ok = mc.move_and_click(choice[0], choice[1], enforce_guard=False, clamp_to_search_roi=False)
        if ok:
            try:
                self.config.set('_chat_last_ybr_click', {'x': choice[0], 'y': choice[1]})
            except Exception:
                pass
        return ok

    def _execute_action(self, action: str) -> None:
        if action == 'enable_prayer':
            ok = self._click_prayer_enable()
            logger.info(f"Chat action enable_prayer executed -> {ok}")
        elif action == 'click_ybr_tile':
            ok = self._choose_ybr_tile_and_click()
            logger.info(f"Chat action click_ybr_tile executed -> {ok}")
        else:
            logger.debug(f"Unknown chat action '{action}'")

    def run(self) -> None:
        if not bool(self.config.get('chat_enabled', False)):
            logger.info("ChatWatcher not started (chat_enabled False)")
            return
        if pytesseract is None:
            logger.warning("pytesseract not installed; chat OCR disabled. Install 'pytesseract' and Tesseract OCR.")
            return
        poll = int(self.config.get('chat_poll_ms', 600))
        logger.info(f"ChatWatcher started (poll={poll} ms)")
        while not self._stop.is_set() and bool(self.config.get('chat_enabled', False)):
            try:
                chat_roi = self.config.get_roi('chat_roi')
                if not chat_roi:
                    time.sleep(poll / 1000.0)
                    continue
                frame = self.capture.capture_region(chat_roi)
                if frame is None:
                    time.sleep(poll / 1000.0)
                    continue
                prep = self._preprocess(frame)
                lines = self._ocr_lines(prep)
                for line in lines:
                    if not line:
                        continue
                    if not self._dedupe(line):
                        continue
                    # Optionally: publish a custom chat event if you later add it to EventType
                    trig = self._match_trigger(line)
                    if trig:
                        # Color verification mapping by pattern
                        pnorm = trig['pattern'].strip().lower()
                        color_key = None
                        if 'your prayers have been disabled!' in pnorm:
                            color_key = 'chat_text_color_prayer_disabled'
                        elif 'you better run!' in pnorm:
                            color_key = 'chat_text_color_ybr'
                        elif 'rebirth demon disabled your prayers' in pnorm:
                            color_key = 'chat_text_color_rebirth_disabled'
                        if color_key:
                            spec = self.config.get_color_spec(color_key)
                            if spec is None:
                                logger.debug(f"No color spec for {color_key}; skipping trigger")
                                continue
                            ok_color = self._verify_text_color(frame, prep, pnorm, spec)
                            if not ok_color:
                                logger.info(f"Chat trigger '{trig['action']}' ignored: color verification failed for pattern '{trig['pattern']}'")
                                continue
                        # Optional template verification inside the matched line bbox
                        # We recompute bbox here for simplicity; color verification already used it internally.
                        ok_tmpl = True
                        if bool(self.config.get('chat_template_enable', False)):
                            # Find bbox for the matched pattern
                            bboxes = self._ocr_line_boxes(prep)
                            bb = None
                            for t, b in bboxes:
                                if pnorm in t:
                                    bb = b
                                    break
                            if bb is not None:
                                ok_tmpl = self._verify_template(frame, pnorm, bb)
                            else:
                                ok_tmpl = True  # can't verify, don't block
                        if not ok_tmpl:
                            logger.info(f"Chat trigger '{trig['action']}' ignored: template verification failed for pattern '{trig['pattern']}'")
                            continue
                        logger.info(f"Chat trigger matched: {trig['action']} on '{line}' (color verified)")
                        self._execute_action(trig['action'])
                time.sleep(poll / 1000.0)
            except Exception as e:
                logger.debug(f"ChatWatcher loop error: {e}")
                time.sleep(poll / 1000.0)
        logger.info("ChatWatcher stopped")
