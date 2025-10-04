"""
Quick Chat Debug Tool
- Captures Chat ROI
- Runs OCR to list lines
- For each known pattern, verifies color mask and optional template
- Saves crop & mask to outputs/ when applicable
- Prints a concise summary (OK/FAIL per pattern; overall matched or false)

Usage:
  python scripts/chat_debug_tool.py
Optional args:
  --save  Save crops and masks to outputs/
  --once  Run once and exit (default)
"""
from __future__ import annotations
import os
import sys
import time
import argparse
import logging
from typing import Tuple, List

import cv2
import numpy as np

# Ensure project root in sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rspsbot.core.config import ConfigManager, ColorSpec # type: ignore
from rspsbot.core.detection.capture import CaptureService # type: ignore
from rspsbot.core.detection.color_detector import build_mask # type: ignore

try:
    import pytesseract # type: ignore
    from pytesseract import Output as TessOutput # type: ignore
except Exception:
    pytesseract = None
    TessOutput = None

logger = logging.getLogger("chat_debug_tool")
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def preprocess(img: np.ndarray) -> np.ndarray:
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    except Exception:
        gray = img
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 41, 10)
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((1, 1), np.uint8))
    return bw


def ocr_lines(img_bin: np.ndarray) -> List[str]:
    if pytesseract is None:
        return []
    cfg = "--oem 3 --psm 6 -l eng"
    try:
        txt = pytesseract.image_to_string(img_bin, config=cfg)
    except Exception:
        return []
    return [l.strip() for l in txt.splitlines() if l.strip()]


def ocr_line_boxes(img_bin: np.ndarray) -> List[Tuple[str, Tuple[int, int, int, int]]]:
    if pytesseract is None or TessOutput is None:
        return []
    try:
        data = pytesseract.image_to_data(img_bin, output_type=TessOutput.DICT)
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
            lines[key] = {'text': str(txt), 'bbox': [x, y, x + w, y + h]}
        else:
            lines[key]['text'] += ' ' + str(txt)
            bx0, by0, bx1, by1 = lines[key]['bbox']
            lines[key]['bbox'] = [min(bx0, x), min(by0, y), max(bx1, x + w), max(by1, y + h)]
    out = []
    for v in lines.values():
        t = v['text'].strip().lower()
        x0, y0, x1, y1 = v['bbox']
        out.append((t, (x0, y0, max(1, x1 - x0), max(1, y1 - y0))))
    return out


def verify_template(config: ConfigManager, roi_color: np.ndarray, pnorm: str) -> Tuple[bool, str]:
    if not bool(config.get('chat_template_enable', False)):
        return True, "templates disabled"
    tkey = None
    if 'you better run!' in pnorm:
        tkey = 'chat_template_ybr_path'
    elif 'your prayers have been disabled!' in pnorm:
        tkey = 'chat_template_prayer_disabled_path'
    elif 'rebirth demon disabled your prayers' in pnorm:
        tkey = 'chat_template_rebirth_disabled_path'
    tpath = config.get(tkey) if tkey else None
    if not tpath or not os.path.exists(tpath):
        return True, "no template path; skip"
    gray = cv2.cvtColor(roi_color, cv2.COLOR_BGR2GRAY)
    tmpl = cv2.imread(tpath, cv2.IMREAD_GRAYSCALE)
    if tmpl is None or tmpl.size == 0:
        return True, "template read failed; skip"
    if gray.shape[0] < tmpl.shape[0] or gray.shape[1] < tmpl.shape[1]:
        return False, "template larger than ROI"
    res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
    _minV, maxV, _minL, _maxL = cv2.minMaxLoc(res)
    thr = float(config.get('chat_template_threshold', 0.7))
    return (maxV >= thr), f"template max={maxV:.3f} thr={thr}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--save', action='store_true', help='Save crops and masks to outputs/')
    args = ap.parse_args()

    config = ConfigManager()
    capture = CaptureService()

    chat_roi = config.get_roi('chat_roi')
    if not chat_roi:
        logger.error('No chat_roi configured')
        return 1

    frame = capture.capture_region(chat_roi)
    if frame is None or frame.size == 0:
        logger.error('Failed to capture chat ROI')
        return 1

    img_bin = preprocess(frame)
    lines = ocr_lines(img_bin)
    bboxes = ocr_line_boxes(img_bin)

    print('OCR lines:')
    for l in lines:
        print(f"- {l}")

    tests = [
        ("Your prayers have been disabled!", 'chat_text_color_prayer_disabled'),
        ("YOU BETTER RUN!", 'chat_text_color_ybr'),
        ("Rebirth Demon disabled your prayers", 'chat_text_color_rebirth_disabled'),
    ]
    min_ratio = float(config.get('chat_color_verify_min_ratio', 0.03))
    min_pixels = int(config.get('chat_color_verify_min_pixels', 30))

    any_ok = False
    outdir = config.get('debug_output_dir', 'outputs') or 'outputs'
    if args.save:
        os.makedirs(outdir, exist_ok=True)

    for pat, color_key in tests:
        pnorm = pat.strip().lower()
        present = any(pnorm in (t or '') for (t, _b) in bboxes)
        if not present:
            print(f"[NO MATCH] {pat}")
            continue
        spec = config.get_color_spec(color_key)
        if spec is None:
            print(f"[SKIP] {pat} (no color spec)")
            continue
        # find bbox
        bb = None
        for t, b in bboxes:
            if pnorm in t:
                bb = b
                break
        if bb is None:
            print(f"[ERROR] {pat} present but no bbox")
            continue
        x, y, w, h = bb
        x = max(0, min(frame.shape[1] - 1, x))
        y = max(0, min(frame.shape[0] - 1, y))
        w = max(1, min(frame.shape[1] - x, w))
        h = max(1, min(frame.shape[0] - y, h))
        roi = frame[y:y+h, x:x+w]
        try:
            mask, _contours = build_mask(roi, spec, step=1, precise=True, min_area=1)
        except Exception:
            mask = None
        if mask is None or mask.size == 0:
            print(f"[FAIL] {pat} color mask empty")
            continue
        pos = int((mask > 0).sum())
        total = int(mask.size)
        ratio = (pos / float(total)) if total > 0 else 0.0
        ok = (ratio >= min_ratio) or (pos >= min_pixels)
        print(f"[{'OK' if ok else 'FAIL'}] {pat} color pixels={pos} ratio={ratio:.3f}")

        ok_tmpl = True
        detail = ''
        ok_tmpl, detail = verify_template(config, roi, pnorm)
        if detail:
            print(f"    {detail} -> {'OK' if ok_tmpl else 'FAIL'}")
        ok = ok and ok_tmpl
        any_ok = any_ok or ok

        if args.save and ok:
            ts = int(time.time() * 1000)
            cv2.imwrite(os.path.join(outdir, f"chat_crop_{ts}.png"), roi)
            cv2.imwrite(os.path.join(outdir, f"chat_mask_{ts}.png"), mask)

    print(f"\nResult: {'matched' if any_ok else 'false'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
