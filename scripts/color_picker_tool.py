"""
Quick color picker screenshot tool.
Opens a zoomable screenshot color picker; on each selection prints RGB/HEX and a config snippet to the terminal.
Press Cancel or close the dialog to exit. Use --once to pick a single color and exit.
"""
from __future__ import annotations
import sys
import argparse
from typing import Optional

from PyQt5.QtWidgets import QApplication

# Ensure repository root (parent of 'scripts') is on sys.path so 'rspsbot' is importable
try:
    from rspsbot.gui.components.screen_picker import ZoomColorPickerDialog
except Exception:
    try:
        import os
        ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from rspsbot.gui.components.screen_picker import ZoomColorPickerDialog  # type: ignore
    except Exception as e:
        print(f"Failed to import ZoomColorPickerDialog: {e}", file=sys.stderr)
        sys.exit(1)

# Optional: provide config write-back if available
ConfigManager = None
ColorSpec = None
try:
    from rspsbot.core.config import ConfigManager as _CM, ColorSpec as _CS
    ConfigManager = _CM
    ColorSpec = _CS
except Exception:
    pass


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02X}{g:02X}{b:02X}"


def print_color_outputs(rgb: tuple[int, int, int]) -> None:
    r, g, b = rgb
    hexv = rgb_to_hex(rgb)
    # Minimal JSON snippet for chat_ybr_tile_color
    json_snippet = (
        '{"rgb":[%d,%d,%d],"tol_rgb":30,"use_hsv":true,"tol_h":12,"tol_s":60,"tol_v":60}'
        % (r, g, b)
    )
    py_snippet = f"ColorSpec(({r}, {g}, {b}), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60)"
    print("============================")
    print(f"RGB: {r}, {g}, {b}")
    print(f"HEX: {hexv}")
    print("Config JSON (chat_ybr_tile_color):")
    print(json_snippet)
    print("Python ColorSpec snippet:")
    print(py_snippet)
    print("============================")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Quick color picker screenshot tool")
    parser.add_argument("--once", action="store_true", help="Pick one color and exit")
    parser.add_argument("--write-chat-ybr", action="store_true", help="Write picked color to chat_ybr_tile_color in a profile and save it")
    parser.add_argument("--profile", type=str, default=None, help="Profile name to load/save (without .json). If omitted and multiple exist, a new 'picked.json' is created")
    args = parser.parse_args(argv)

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Prepare config if writing back
    cm = None
    profile_name = None
    if args.write_chat_ybr and ConfigManager is not None:
        try:
            cm = ConfigManager()
            # If profile specified, try load; else use or create 'picked'
            if args.profile:
                cm.load_profile(args.profile)
                profile_name = args.profile
            else:
                profiles = cm.list_profiles()
                if len(profiles) == 1:
                    pn = profiles[0][:-5] if profiles[0].endswith('.json') else profiles[0]
                    if cm.load_profile(pn):
                        profile_name = pn
                if profile_name is None:
                    profile_name = 'picked'
        except Exception:
            cm = None
            profile_name = None

    # Loop until user cancels or --once
    while True:
        dlg = ZoomColorPickerDialog(config_manager=None)
        if dlg.exec_() == dlg.Accepted and dlg.selected_color is not None:
            r, g, b = (int(dlg.selected_color[0]), int(dlg.selected_color[1]), int(dlg.selected_color[2]))
            rgb = (r, g, b)
            print_color_outputs(rgb)
            # Copy JSON snippet to clipboard for convenience
            try:
                from PyQt5.QtGui import QGuiApplication
                clip = QGuiApplication.clipboard()
                r, g, b = (rgb[0], rgb[1], rgb[2])
                json_snippet = (
                    '{"rgb":[%d,%d,%d],"tol_rgb":30,"use_hsv":true,"tol_h":12,"tol_s":60,"tol_v":60}'
                    % (r, g, b)
                )
                if clip is not None:
                    clip.setText(json_snippet)
                print("(Copied JSON snippet to clipboard)")
            except Exception:
                pass

            # Write to config if requested
            if args.write_chat_ybr and cm is not None and ColorSpec is not None and profile_name is not None:
                try:
                    spec = ColorSpec((r, g, b), tol_rgb=30, tol_h=12, tol_s=60, tol_v=60)
                    cm.set_color_spec('chat_ybr_tile_color', spec)
                    if cm.save_profile(profile_name):
                        print(f"Saved chat_ybr_tile_color to profiles/{profile_name}.json")
                    else:
                        print(f"Failed to save profile '{profile_name}'", file=sys.stderr)
                except Exception as e:
                    print(f"Failed to write color to config: {e}", file=sys.stderr)
            if args.once:
                break
            # Continue loop to pick another
        else:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
