#!/usr/bin/env python3
"""
Snapshot and compare: client window vs Style/Weapon Tuner

- Focus and capture the target game/client window by title substring
- Capture and analyze Style ROI: per-style pixel counts vs thresholds, selected style
- Capture and analyze Weapon ROI: pixel count and clickable point for the selected/current style
- Capture the Style/Weapon Tuner window for a visual reference
- Save images and a summary report under logs/snapshots/<timestamp>/

Usage (PowerShell):
    .venv/Scripts/python.exe scripts/snapshot_compare.py --client-title "Velador - Donikk" --profile "v2 instance.json"

Optional flags:
  --save-dir <path>   # default logs/snapshots
  --no-masks          # skip saving mask images
  --debug             # verbose logging
"""
import sys
import os
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import cv2  # type: ignore
import numpy as np  # type: ignore

from rspsbot.utils.logging import setup_logging
from rspsbot.core.config import ConfigManager, ColorSpec
from rspsbot.core.detection.capture import CaptureService
from rspsbot.core.detection.detector import DetectionEngine
from rspsbot.core.detection.color_detector import build_mask, build_mask_precise_small

logger = logging.getLogger("rspsbot.tools.snapshot_compare")


def _timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _save_img(path: Path, img: np.ndarray) -> None:
    try:
        if img is None:
            return
        cv2.imwrite(str(path), img)
    except Exception as e:
        logger.error(f"Failed to save image {path}: {e}")


def _build_mask(frame: np.ndarray, spec: ColorSpec, cfg: ConfigManager) -> np.ndarray:
    use_precise_small = bool(cfg.get('combat_precise_mode', True))
    cm_cfg = {
        'combat_lab_tolerance': cfg.get('combat_lab_tolerance', 18),
        'combat_sat_min': cfg.get('combat_sat_min', 40),
        'combat_val_min': cfg.get('combat_val_min', 40),
        'combat_morph_open_iters': cfg.get('combat_morph_open_iters', 1),
        'combat_morph_close_iters': cfg.get('combat_morph_close_iters', 1),
    }
    if use_precise_small:
        mask, _ = build_mask_precise_small(frame, spec, cm_cfg, step=1, min_area=0)
    else:
        mask, _ = build_mask(frame, spec, step=1, precise=True, min_area=0)
    return mask


def _draw_crosshair(img: np.ndarray, pt: Optional[tuple], color=(0, 255, 255)) -> np.ndarray:
    if img is None or pt is None:
        return img
    x, y = int(pt[0]), int(pt[1])
    # Guard if pt uses screen coords; convert later by subtracting roi origin when drawing on ROI image
    cv2.drawMarker(img, (x, y), color, markerType=cv2.MARKER_CROSS, markerSize=12, thickness=2)
    return img


def main(argv: Optional[list] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Snapshot client and tuner, analyze style/weapon ROIs")
    p.add_argument('--client-title', type=str, required=True, help='Substring of the client window title to focus (e.g., "Velador - Donikk")')
    p.add_argument('--profile', type=str, default=None, help='Profile filename in profiles/ to load (e.g., "v2 instance.json")')
    p.add_argument('--save-dir', type=str, default=str(PROJECT_ROOT / 'logs' / 'snapshots'), help='Directory to save snapshots')
    p.add_argument('--no-masks', action='store_true', help='Skip saving mask images')
    p.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = p.parse_args(argv)

    setup_logging(level=logging.DEBUG if args.debug else logging.INFO)

    out_dir = Path(args.save_dir) / _timestamp()
    _ensure_dir(out_dir)

    # Initialize config and capture/detection
    cfg = ConfigManager()
    if args.profile:
        try:
            cfg.load_profile(args.profile)
            logger.info(f"Profile loaded: {args.profile}")
        except Exception as e:
            logger.warning(f"Failed to load profile '{args.profile}': {e}")
    cap = CaptureService()
    det = DetectionEngine(cfg, cap)

    # Focus client window
    focused = cap.focus_window(args.client_title, retries=4, sleep_s=0.25, exact=False)
    if not focused:
        logger.warning(f"Could not focus client window with title containing: {args.client_title}")
    bbox = cap.get_window_bbox()
    logger.info(f"Client bbox: {bbox}")

    # Capture full client window
    full_img = cap.capture(bbox)
    _save_img(out_dir / 'client_full.png', full_img)

    # Analyze Style ROI
    report: Dict[str, Any] = {'client_bbox': bbox}
    sroi = cfg.get_roi('combat_style_roi')
    if sroi:
        try:
            if hasattr(sroi, 'to_dict'):
                sroi_dict = sroi.to_dict()
            else:
                sroi_dict = {
                    'left': int(getattr(sroi, 'left', 0)),
                    'top': int(getattr(sroi, 'top', 0)),
                    'width': int(getattr(sroi, 'width', 0)),
                    'height': int(getattr(sroi, 'height', 0)),
                }
        except Exception:
            sroi_dict = {'left': 0, 'top': 0, 'width': 0, 'height': 0}
        s_frame = cap.capture_region(sroi)
        _save_img(out_dir / 'style_roi.png', s_frame)
        style_counts = det.detect_combat_style_counts()
        report['style_counts'] = style_counts
        if style_counts:
            logger.info(f"Style counts: {style_counts}")
        # Save masks per style
        if not args.no_masks and s_frame is not None:
            specs = {
                'melee': cfg.get_color_spec('combat_style_melee_color'),
                'ranged': cfg.get_color_spec('combat_style_ranged_color'),
                'magic': cfg.get_color_spec('combat_style_magic_color'),
            }
            for k, spec in specs.items():
                if not spec:
                    continue
                try:
                    mask = _build_mask(s_frame, spec, cfg)
                    # Visualize mask as grayscale PNG
                    mask_vis = (mask > 0).astype(np.uint8) * 255
                    _save_img(out_dir / f'style_mask_{k}.png', mask_vis)
                except Exception as e:
                    logger.debug(f"Failed to build style mask for {k}: {e}")
    else:
        logger.warning("Style ROI not set in profile")

    # Analyze Weapon ROI
    wroi = cfg.get_roi('combat_weapon_roi')
    if wroi:
        try:
            if hasattr(wroi, 'to_dict'):
                wroi_dict = wroi.to_dict()
            else:
                wroi_dict = {
                    'left': int(getattr(wroi, 'left', 0)),
                    'top': int(getattr(wroi, 'top', 0)),
                    'width': int(getattr(wroi, 'width', 0)),
                    'height': int(getattr(wroi, 'height', 0)),
                }
        except Exception:
            wroi_dict = {'left': 0, 'top': 0, 'width': 0, 'height': 0}
        w_frame = cap.capture_region(wroi)
        _save_img(out_dir / 'weapon_roi.png', w_frame)
        # Decide current style
        cur_style = None
        try:
            cur_style = det.detect_combat_style() or None
        except Exception:
            pass
        report['weapon_style'] = cur_style
        # Try to find clickable point for current/preferred style
        try:
            pt = det.detect_weapon_for_style(cur_style)
        except Exception:
            pt = None
        report['weapon_point'] = pt
        if pt and w_frame is not None:
            # Convert screen pt to ROI-local for drawing
            try:
                lx = int(wroi_dict['left']) if isinstance(wroi_dict, dict) else 0
                ty = int(wroi_dict['top']) if isinstance(wroi_dict, dict) else 0
                loc = (int(pt[0] - lx), int(pt[1] - ty))
                draw = w_frame.copy()
                cv2.drawMarker(draw, (loc[0], loc[1]), (0, 255, 255), markerType=cv2.MARKER_CROSS, markerSize=14, thickness=2)
                _save_img(out_dir / 'weapon_roi_point.png', draw)
            except Exception:
                pass
        # Save mask for chosen style
        if not args.no_masks and w_frame is not None and cur_style:
            spec = None
            if cur_style.startswith('melee'):
                spec = cfg.get_color_spec('combat_weapon_melee_color') or cfg.get_color_spec('combat_style_melee_color')
            elif cur_style.startswith('rang'):
                spec = cfg.get_color_spec('combat_weapon_ranged_color') or cfg.get_color_spec('combat_style_ranged_color')
            else:
                spec = cfg.get_color_spec('combat_weapon_magic_color') or cfg.get_color_spec('combat_style_magic_color')
            if spec:
                try:
                    mask = _build_mask(w_frame, spec, cfg)
                    mask_vis = (mask > 0).astype(np.uint8) * 255
                    _save_img(out_dir / f'weapon_mask_{cur_style}.png', mask_vis)
                except Exception as e:
                    logger.debug(f"Failed to build weapon mask for {cur_style}: {e}")
    else:
        logger.warning("Weapon ROI not set in profile")

    # Capture tuner window if present
    try:
        tuner_title = None
        tuner_bbox = None
        try:
            import pygetwindow as gw
            wins = gw.getAllWindows()
            candidates = [w for w in wins if 'Style/Weapon ROI Tuner' in (w.title or '')]
            # Prefer non-minimized and largest area
            candidates.sort(key=lambda w: (w.isMinimized, -(w.width * w.height)))
            if candidates:
                w = candidates[0]
                tuner_title = w.title
                tuner_bbox = {'left': w.left, 'top': w.top, 'width': w.width, 'height': w.height}
        except Exception as e:
            logger.debug(f"pygetwindow failed for tuner: {e}")
        if tuner_bbox:
            t_img = cap.capture(tuner_bbox)
            _save_img(out_dir / 'tuner_window.png', t_img)
            report['tuner_bbox'] = tuner_bbox
            report['tuner_title'] = tuner_title
        else:
            logger.info("Tuner window not found; skip tuner snapshot")
    except Exception as e:
        logger.debug(f"Tuner capture failed: {e}")

    # Save report JSON
    try:
        with open(out_dir / 'report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Snapshot written to: {out_dir}")
    except Exception as e:
        logger.error(f"Failed to write report: {e}")

    # Heuristic checks and hints printed to console
    try:
        sc = report.get('style_counts') or {}
        if sc:
            counts = (sc.get('counts') or {})
            thr = (sc.get('thresholds') or {})
            sel = sc.get('style')
            msg = f"Style counts M={counts.get('melee',0)}/{thr.get('melee','-')} R={counts.get('ranged',0)}/{thr.get('ranged','-')} Mg={counts.get('magic',0)}/{thr.get('magic','-')} | selected={sel}"
            logger.info(msg)
            # Quick warnings
            if not sel:
                logger.info("No style selected: consider lowering min pixels, refining ROI placement, or re-picking colors.")
            else:
                logger.info("Style variable is working (selected style present).")
    except Exception:
        pass

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
