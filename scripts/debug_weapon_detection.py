"""
Quick debug tool to inspect weapon detection and switching decision.

Usage examples:
  - python scripts/debug_weapon_detection.py --profile example_profile --required ranged
  - python scripts/debug_weapon_detection.py --focus "Velador" --loop --interval 0.5
    - python scripts/debug_weapon_detection.py --interactive --profile my_profile --focus "Velador"

This script:
  - Loads config/profile
  - Optionally focuses the game window (by substring)
  - Captures the weapon ROI
  - Computes pixel counts per style (normal and relaxed passes)
  - Calls MultiMonsterDetector.detect_weapon and visible_weapon_styles
    - Prints a simple switch decision against an optional --required style
    - Interactive mode lets you tune live:
            set lab <int>        # weapon_lab_tolerance
            set sat <int>        # weapon_sat_min
            set val <int>        # weapon_val_min
            set min <int>        # weapon_min_pixels
            set ratio <float>    # weapon_soft_floor_ratio (equipped detection)
            set visratio <float> # weapon_adaptive_ratio (visible styles)
            set floor <int>      # weapon_adaptive_min_pixels
            set visenable <on|off> # weapon_adaptive_enable (visible styles)
            set req <style|none> # required style for decision preview
            set interval <sec>   # update interval for loop
            focus <title-substr> # focus window by substring
                        roi                  # pick weapon ROI interactively
                        color <style> R G B  # set weapon color spec directly
                        pickcolor <style>    # pick weapon color from screen
            once | loop          # run once or loop (Ctrl+C to stop loop)
                        show                 # show current settings
                        show roi|colors      # show ROI and/or colors
            help                 # show commands
            quit                 # exit
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime
import time
import logging
from typing import Dict, Optional

import numpy as np
import cv2

import os
import sys

# Ensure project root is on sys.path so `rspsbot` imports resolve when running directly
_THIS_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from rspsbot.core.config import ConfigManager, ColorSpec, ROI
from rspsbot.core.detection.capture import CaptureService
from rspsbot.core.detection.multi_monster_detector import MultiMonsterDetector
from rspsbot.core.detection.color_detector import build_mask_precise_small
from rspsbot.gui.components.screen_picker import (
    ZoomRoiPickerDialog,
    ZoomColorPickerDialog,
)
from PyQt5.QtWidgets import QApplication


def _counts_for_specs(frame: np.ndarray, specs: Dict[str, ColorSpec], lab_tol: int, sat_min: int, val_min: int,
                      open_iters: int, close_iters: int) -> Dict[str, int]:
    cfg = {
        'combat_lab_tolerance': lab_tol,
        'combat_sat_min': sat_min,
        'combat_val_min': val_min,
        'combat_morph_open_iters': open_iters,
        'combat_morph_close_iters': close_iters,
    }
    counts: Dict[str, int] = {}
    for k, spec in specs.items():
        try:
            mask, _ = build_mask_precise_small(frame, spec, cfg, step=1, min_area=0)
            counts[k] = int(cv2.countNonZero(mask))
        except Exception:
            counts[k] = 0
    return counts


def decide_switch(required: Optional[str], current: Optional[str], visible: Dict[str, int]) -> str:
    if required and current == required:
        return 'attack (already_on_required)'
    if required and required in visible:
        return 'switch_weapon (required_visible)'
    if (not required or required not in visible) and visible and (current is None):
        return 'switch_weapon (current_unknown_switch_any_visible)'
    return 'attack (fallback)'


def main():
    parser = argparse.ArgumentParser(description='Debug weapon detection and switching')
    parser.add_argument('--profile', type=str, help='Profile name in profiles/ (without .json)')
    parser.add_argument('--focus', type=str, help='Window title (substring) to focus before capture')
    parser.add_argument('--required', type=str, choices=['melee', 'ranged', 'magic'], help='Required style to simulate decision')
    parser.add_argument('--loop', action='store_true', help='Run in a loop')
    parser.add_argument('--interval', type=float, default=0.5, help='Loop interval seconds')
    parser.add_argument('--verbose', action='store_true', help='Set log level DEBUG')
    parser.add_argument('--interactive', action='store_true', help='Start interactive tuning prompt')
    # Live, no-profile inputs
    parser.add_argument('--weapon-roi', type=str, help='Set weapon ROI as L,T,W,H (absolute) for this session')
    parser.add_argument('--color-melee', type=str, help='Set melee color as R,G,B for this session')
    parser.add_argument('--color-ranged', type=str, help='Set ranged color as R,G,B for this session')
    parser.add_argument('--color-magic', type=str, help='Set magic color as R,G,B for this session')
    parser.add_argument('--cmd', type=str, help='Semicolon-separated commands to run non-interactively (same syntax as REPL): e.g. "focus Velador; set lab 18; once; loop"')
    parser.add_argument('--iterations', type=int, default=20, help='Loop iterations when used with loop/--cmd (default: 20)')
    parser.add_argument('--json', action='store_true', help='Emit JSON lines for samples (with once/loop/cmd modes)')
    parser.add_argument('--logfile', type=str, help='Write JSON lines to this file for samples')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    cm = ConfigManager()
    # Profiles are optional. If not provided, we run in-memory only with live tuning.
    if args.profile:
        ok = cm.load_profile(args.profile)
        if not ok:
            logging.error('Failed to load profile: %s', args.profile)
            return 1

    cs = CaptureService()
    if args.focus:
        cs.focus_window(args.focus, retries=6, sleep_s=0.25, exact=False)

    det = MultiMonsterDetector(cm, cs)
    # Apply CLI-provided ROI and colors (no profile needed)
    def _parse_tuple4(text: str):
        parts = [p.strip() for p in text.split(',')]
        if len(parts) != 4:
            raise ValueError('ROI must be L,T,W,H')
        return tuple(int(x) for x in parts)
    def _parse_tuple3(text: str):
        parts = [p.strip() for p in text.split(',')]
        if len(parts) != 3:
            raise ValueError('Color must be R,G,B')
        return tuple(int(x) for x in parts)
    try:
        if args.weapon_roi:
            L,T,W,H = _parse_tuple4(args.weapon_roi)
            cm.set_roi('weapon_roi', ROI(left=L, top=T, width=W, height=H, mode='absolute'))
        if args.color_melee:
            r,g,b = _parse_tuple3(args.color_melee)
            cm.set_color_spec('multi_monster_melee_weapon_color', ColorSpec(rgb=(r,g,b), tol_rgb=24, use_hsv=True, tol_h=10, tol_s=60, tol_v=60))
        if args.color_ranged:
            r,g,b = _parse_tuple3(args.color_ranged)
            cm.set_color_spec('multi_monster_ranged_weapon_color', ColorSpec(rgb=(r,g,b), tol_rgb=24, use_hsv=True, tol_h=10, tol_s=60, tol_v=60))
        if args.color_magic:
            r,g,b = _parse_tuple3(args.color_magic)
            cm.set_color_spec('multi_monster_magic_weapon_color', ColorSpec(rgb=(r,g,b), tol_rgb=24, use_hsv=True, tol_h=10, tol_s=60, tol_v=60))
    except Exception as e:
        logging.error('Failed to parse/set ROI/colors: %s', e)


    # Mutable settings stored here (required style + interval); thresholds live in cm via cm.set(...)
    required_style: Optional[str] = (args.required if args.required else None)
    interval: float = float(args.interval)

    def sample_once_struct():
        roi = cm.get_roi('weapon_roi')
        if not roi:
            return {'error': 'weapon_roi not set'}
        frame = cs.capture_region(roi)
        if frame is None or frame.size == 0:
            return {'error': 'capture_failed'}

        # Specs
        specs = {
            'melee': cm.get_color_spec('multi_monster_melee_weapon_color'),
            'ranged': cm.get_color_spec('multi_monster_ranged_weapon_color'),
            'magic': cm.get_color_spec('multi_monster_magic_weapon_color'),
        }
        specs = {k: v for k, v in specs.items() if v is not None}
        if not specs:
            return {'error': 'no_specs'}

        # Thresholds
        lab_tol = max(int(cm.get('weapon_lab_tolerance', 10)), 12)
        sat_min = int(cm.get('weapon_sat_min', 20))
        val_min = int(cm.get('weapon_val_min', 30))
        open_iters = int(cm.get('multi_monster_morph_open_iters', 1))
        close_iters = int(cm.get('multi_monster_morph_close_iters', 2))
        min_pixels = int(cm.get('weapon_min_pixels', 20))
        adaptive_ratio = float(cm.get('weapon_soft_floor_ratio', 0.4))
        adaptive_floor = int(cm.get('weapon_adaptive_min_pixels', 5))

        normal_counts = _counts_for_specs(frame, specs, lab_tol, sat_min, val_min, open_iters, close_iters)
        relaxed_counts = {}
        if sum(normal_counts.values()) == 0:
            relaxed_counts = _counts_for_specs(frame, specs, max(lab_tol, 18), 0, 0, open_iters, close_iters)

        current = det.detect_weapon(frame)
        visible = det.visible_weapon_styles(frame)
        decision = decide_switch(required_style, current, visible)
        # Package result
        try:
            mean_bgr = frame.mean(axis=(0,1))
            mean_rgb = (int(mean_bgr[2]), int(mean_bgr[1]), int(mean_bgr[0]))
        except Exception:
            mean_rgb = None
        rl, rt, rw, rh = getattr(roi, 'left', None), getattr(roi, 'top', None), getattr(roi, 'width', None), getattr(roi, 'height', None)
        sample = {
            'ts': datetime.utcnow().isoformat() + 'Z',
            'roi': {'left': rl, 'top': rt, 'width': rw, 'height': rh},
            'mean_rgb': mean_rgb,
            'thresholds': {
                'lab_tol': lab_tol, 'sat_min': sat_min, 'val_min': val_min,
                'min_pixels': min_pixels, 'soft_ratio': adaptive_ratio, 'adaptive_floor': adaptive_floor,
                'visible_adaptive_ratio': float(cm.get('weapon_adaptive_ratio', 0.5)),
                'visible_adaptive_enable': bool(cm.get('weapon_adaptive_enable', True)),
            },
            'required': required_style,
            'normal_counts': normal_counts,
            'relaxed_counts': relaxed_counts if relaxed_counts else None,
            'current': current,
            'visible': visible,
            'decision': decision,
        }
        return sample

    def print_sample(sample: dict):
        if not sample or 'error' in sample:
            print(f"Error: {sample.get('error', 'unknown')}")
            return
        print('--- Weapon Detection Debug ---')
        roi = sample.get('roi') or {}
        print(f"ROI: ({roi.get('left')},{roi.get('top')},{roi.get('width')},{roi.get('height')}) mean_rgb={sample.get('mean_rgb')}")
        thr = sample.get('thresholds') or {}
        nc = sample.get('normal_counts') or {}
        rc = sample.get('relaxed_counts') or None
        print(f"Normal counts (lab_tol={thr.get('lab_tol')}, S>={thr.get('sat_min')}, V>={thr.get('val_min')}): {nc}")
        if rc:
            print(f"Relaxed counts (lab_tol>={max(int(thr.get('lab_tol',0)),18)}, S>=0, V>=0): {rc}")
        print(f"Current equipped: {sample.get('current')} (min_pixels={thr.get('min_pixels')}, soft_ratio={thr.get('soft_ratio')}, adaptive_floor={thr.get('adaptive_floor')})")
        print(f"Visible styles (>=min OR adaptive): {sample.get('visible')}")
        req = sample.get('required')
        if req:
            print(f"Required: {req} -> Decision: {sample.get('decision')}")
        else:
            print(f"Decision (no required given): {sample.get('decision')}")
        print('------------------------------\n')

    def write_jsonl(sample: dict, path: Optional[str]):
        if not path or not sample:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception:
            pass
        try:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Failed to write log: {e}")

    def one_pass():
        sample = sample_once_struct()
        if args.json and sample and 'error' not in sample:
            print(json.dumps(sample))
        else:
            print_sample(sample)
        if sample and 'error' not in sample:
            write_jsonl(sample, args.logfile)

    def show_settings():
        vals = {
            'weapon_lab_tolerance': cm.get('weapon_lab_tolerance', 10),
            'weapon_sat_min': cm.get('weapon_sat_min', 20),
            'weapon_val_min': cm.get('weapon_val_min', 30),
            'weapon_min_pixels': cm.get('weapon_min_pixels', 20),
            'weapon_soft_floor_ratio': cm.get('weapon_soft_floor_ratio', 0.4),  # equipped
            'weapon_adaptive_ratio': cm.get('weapon_adaptive_ratio', 0.5),      # visible
            'weapon_adaptive_min_pixels': cm.get('weapon_adaptive_min_pixels', 5),
            'weapon_adaptive_enable': cm.get('weapon_adaptive_enable', True),
            'weapon_template_enable': cm.get('weapon_template_enable', True),
            'weapon_template_mode': cm.get('weapon_template_mode', 'edge'),
            'weapon_template_threshold': cm.get('weapon_template_threshold', 0.58),
            'weapon_template_window': cm.get('weapon_template_window', 64),
        }
        print('--- Settings ---')
        for k, v in vals.items():
            print(f'{k}: {v}')
        print(f'required: {required_style}')
        print(f'interval: {interval}')
        # Show ROI and color specs short summary
        roi = cm.get_roi('weapon_roi')
        if roi:
            print(f'weapon_roi: ({roi.left},{roi.top},{roi.width},{roi.height})')
        else:
            print('weapon_roi: <not set>')
        for style in ('melee','ranged','magic'):
            cspec = cm.get_color_spec(f'multi_monster_{style}_weapon_color')
            if cspec:
                print(f'color[{style}]: rgb={cspec.rgb} hsv_tol(h={cspec.tol_h},s={cspec.tol_s},v={cspec.tol_v})')
            else:
                print(f'color[{style}]: <not set>')
        # Show template paths
        for style in ('melee','ranged','magic'):
            tpath = cm.get(f'weapon_{style}_template_path', None)
            print(f'template[{style}]: {tpath}')
        print('----------------')

    def print_help():
        print('Commands:')
        print('  set lab <int>        | set sat <int>       | set val <int>')
        print('  set min <int>        | set ratio <float>   | set floor <int>')
        print('  set visratio <float> | set visenable <on|off>')
        print("  set req <melee|ranged|magic|none> | set interval <sec>")
        print('  focus <title-substr> | roi | color <style> R G B | pickcolor <style>')
        print('  set templatemode <edge|gray> | set templatethr <0..1> | set templatewin <px>')
        print('  set template <melee|ranged|magic> <path-to-image>')
        print('  save <path-to-image>  # save current weapon ROI to image')
        print('  once | loop | show | show roi | show colors | help | quit')

    def _ensure_qapp():
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        return app

    def pick_roi_interactive():
        try:
            _ensure_qapp()
            dlg = ZoomRoiPickerDialog(config_manager=cm)
            if dlg.exec_() == 1 and dlg.result_rect is not None:
                # Convert client-relative rect to absolute via CaptureService bbox
                bbox = cs.get_window_bbox()
                left = bbox.get('left', 0) + dlg.result_rect.left()
                top = bbox.get('top', 0) + dlg.result_rect.top()
                width = dlg.result_rect.width()
                height = dlg.result_rect.height()
                roi = ROI(left=left, top=top, width=width, height=height, mode='absolute')
                cm.set_roi('weapon_roi', roi)
                print(f'set weapon_roi = ({left},{top},{width},{height})')
            else:
                print('ROI selection canceled')
        except Exception as e:
            print(f'ROI picker failed: {e}')

    def set_color_spec(style: str, rgb: tuple[int,int,int]):
        # Sensible defaults for small-ROI weapon icons
        spec = ColorSpec(rgb=rgb, tol_rgb=24, use_hsv=True, tol_h=10, tol_s=60, tol_v=60)
        cm.set_color_spec(f'multi_monster_{style}_weapon_color', spec)
        print(f'set color[{style}] = {rgb}')

    def pick_color_interactive(style: str):
        try:
            _ensure_qapp()
            dlg = ZoomColorPickerDialog(config_manager=cm)
            if dlg.exec_() == 1 and dlg.selected_color is not None:
                set_color_spec(style, dlg.selected_color)
            else:
                print('Color selection canceled')
        except Exception as e:
            print(f'Color picker failed: {e}')

    def save_weapon_roi(path: str):
        try:
            roi = cm.get_roi('weapon_roi')
            if not roi:
                print('weapon_roi not set; use `roi` to pick it first')
                return
            frame = cs.capture_region(roi)
            if frame is None or frame.size == 0:
                print('capture failed')
                return
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            ok = cv2.imwrite(path, frame)
            if ok:
                print(f'saved ROI to {path}')
            else:
                print('failed to write image')
        except Exception as e:
            print(f'save failed: {e}')

    if args.cmd and not args.interactive:
        # Non-interactive scripted execution
        cmdline = args.cmd
        # Very small parser: split by ';' and reuse REPL handlers where possible
        for raw in [c.strip() for c in cmdline.split(';') if c.strip()] + ([] if ('loop' in cmdline or 'once' in cmdline) else ['once']):
            parts = raw.split()
            if not parts:
                continue
            if parts[0].lower() == 'focus' and len(parts) >= 2:
                title = raw[len('focus '):]
                cs.focus_window(title, retries=6, sleep_s=0.25, exact=False)
                continue
            if parts[0].lower() == 'set' and len(parts) >= 3:
                key = parts[1].lower(); val = ' '.join(parts[2:])
                try:
                    if key == 'lab': cm.set('weapon_lab_tolerance', int(val))
                    elif key == 'sat': cm.set('weapon_sat_min', int(val))
                    elif key == 'val': cm.set('weapon_val_min', int(val))
                    elif key == 'min': cm.set('weapon_min_pixels', int(val))
                    elif key == 'ratio': cm.set('weapon_soft_floor_ratio', float(val))
                    elif key == 'visratio': cm.set('weapon_adaptive_ratio', float(val))
                    elif key == 'floor': cm.set('weapon_adaptive_min_pixels', int(val))
                    elif key == 'visenable':
                        v = val.lower().strip(); cm.set('weapon_adaptive_enable', v in ('on','true','1','yes'))
                    elif key == 'req':
                        v = val.lower();
                        required_style = v if v in ('melee','ranged','magic') else None
                    elif key == 'interval':
                        interval = float(val)
                    elif key == 'templatemode':
                        v = val.lower().strip(); cm.set('weapon_template_mode', 'edge' if v not in ('gray',) else 'gray')
                    elif key == 'templatethr':
                        cm.set('weapon_template_threshold', float(val))
                    elif key == 'templatewin':
                        cm.set('weapon_template_window', int(val))
                    elif key == 'template':
                        # supports: set template <style> <path>
                        vs = val.split()
                        if len(vs) >= 2 and vs[0].lower() in ('melee','ranged','magic'):
                            style = vs[0].lower(); path = ' '.join(vs[1:])
                            cm.set(f'weapon_{style}_template_path', path)
                except Exception:
                    pass
                continue
            if parts[0].lower() == 'save' and len(parts) >= 2:
                path = raw[len('save '):].strip()
                if path:
                    save_weapon_roi(path)
                continue
            if parts[0].lower() == 'once':
                one_pass();
                continue
            if parts[0].lower() == 'loop':
                iters = args.iterations
                # allow "loop 50" inline
                if len(parts) >= 2:
                    try:
                        iters = int(parts[1])
                    except Exception:
                        pass
                try:
                    for _ in range(max(1, iters)):
                        one_pass()
                        time.sleep(interval)
                except KeyboardInterrupt:
                    pass
                continue
            # Ignore GUI-only commands in scripted mode (roi/pickcolor/color)
        return 0

    if args.loop and not args.interactive:
        try:
            while True:
                one_pass()
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
    elif args.interactive:
        print('Interactive tuning mode. Type `help` for commands. Use Ctrl+C to break loops.')
        show_settings()
        while True:
            try:
                cmd = input('tune> ').strip()
            except (EOFError, KeyboardInterrupt):
                print('\nExiting.')
                break
            if not cmd:
                continue
            parts = cmd.split()
            if parts[0].lower() == 'quit' or parts[0].lower() == 'exit':
                break
            if parts[0].lower() == 'help':
                print_help()
                continue
            if parts[0].lower() == 'show':
                if len(parts) >= 2:
                    sub = parts[1].lower()
                    if sub == 'roi':
                        roi = cm.get_roi('weapon_roi')
                        if roi:
                            print(f'weapon_roi: ({roi.left},{roi.top},{roi.width},{roi.height})')
                        else:
                            print('weapon_roi: <not set>')
                        continue
                    if sub == 'colors':
                        for style in ('melee','ranged','magic'):
                            cspec = cm.get_color_spec(f'multi_monster_{style}_weapon_color')
                            if cspec:
                                print(f'color[{style}]: rgb={cspec.rgb} hsv_tol(h={cspec.tol_h},s={cspec.tol_s},v={cspec.tol_v})')
                            else:
                                print(f'color[{style}]: <not set>')
                        continue
                show_settings()
                continue
            if parts[0].lower() == 'once':
                one_pass()
                continue
            if parts[0].lower() == 'loop':
                try:
                    while True:
                        one_pass()
                        time.sleep(interval)
                except KeyboardInterrupt:
                    print('\n(loop stopped)')
                continue
            if parts[0].lower() == 'focus' and len(parts) >= 2:
                title = cmd[len('focus '):]
                cs.focus_window(title, retries=6, sleep_s=0.25, exact=False)
                continue
            if parts[0].lower() == 'save' and len(parts) >= 2:
                path = cmd[len('save '):].strip()
                if not path:
                    print('Usage: save <path-to-image>')
                else:
                    save_weapon_roi(path)
                continue
            if parts[0].lower() == 'roi':
                pick_roi_interactive()
                continue
            if parts[0].lower() == 'pickcolor' and len(parts) >= 2:
                style = parts[1].lower()
                if style not in ('melee','ranged','magic'):
                    print('Usage: pickcolor <melee|ranged|magic>')
                    continue
                pick_color_interactive(style)
                continue
            if parts[0].lower() == 'color' and len(parts) >= 5:
                style = parts[1].lower()
                if style not in ('melee','ranged','magic'):
                    print('Usage: color <melee|ranged|magic> R G B')
                    continue
                try:
                    r = int(parts[2]); g = int(parts[3]); b = int(parts[4])
                    r = max(0, min(255, r)); g = max(0, min(255, g)); b = max(0, min(255, b))
                    set_color_spec(style, (r,g,b))
                except ValueError:
                    print('Invalid R G B; must be integers 0-255')
                continue
            if parts[0].lower() == 'set' and len(parts) >= 3:
                key = parts[1].lower()
                val = ' '.join(parts[2:])
                try:
                    if key == 'lab':
                        cm.set('weapon_lab_tolerance', int(val))
                    elif key == 'sat':
                        cm.set('weapon_sat_min', int(val))
                    elif key == 'val':
                        cm.set('weapon_val_min', int(val))
                    elif key == 'min':
                        cm.set('weapon_min_pixels', int(val))
                    elif key == 'ratio':
                        cm.set('weapon_soft_floor_ratio', float(val))
                    elif key == 'visratio':
                        cm.set('weapon_adaptive_ratio', float(val))
                    elif key == 'floor':
                        cm.set('weapon_adaptive_min_pixels', int(val))
                    elif key == 'visenable':
                        v = val.lower().strip()
                        if v in ('on','true','1','yes'):
                            cm.set('weapon_adaptive_enable', True)
                        elif v in ('off','false','0','no'):
                            cm.set('weapon_adaptive_enable', False)
                        else:
                            print('Use: set visenable <on|off>')
                            continue
                    elif key == 'req':
                        v = val.lower()
                        if v in ('melee','ranged','magic'):
                            required_style = v
                        elif v in ('none','null',''): 
                            required_style = None
                        else:
                            print('Invalid required style; use melee|ranged|magic|none')
                            continue
                    elif key == 'interval':
                        interval = float(val)
                    elif key == 'templatemode':
                        v = val.lower().strip()
                        if v in ('edge','gray'):
                            cm.set('weapon_template_mode', v)
                        else:
                            print('Use: set templatemode <edge|gray>')
                            continue
                    elif key == 'templatethr':
                        cm.set('weapon_template_threshold', float(val))
                    elif key == 'templatewin':
                        cm.set('weapon_template_window', int(val))
                    elif key == 'template':
                        vs = val.split()
                        if len(vs) < 2 or vs[0].lower() not in ('melee','ranged','magic'):
                            print('Use: set template <melee|ranged|magic> <path-to-image>')
                            continue
                        style = vs[0].lower(); path = ' '.join(vs[1:])
                        cm.set(f'weapon_{style}_template_path', path)
                    else:
                        print('Unknown setting. Type `help`.')
                        continue
                    show_settings()
                except ValueError:
                    print('Invalid number format for value')
                continue
            print('Unknown command. Type `help`.')
    else:
        one_pass()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
