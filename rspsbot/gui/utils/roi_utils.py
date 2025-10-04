"""Shared ROI utility functions for formatting and normalization."""
from typing import Any, Dict

def roi_to_dict(roi: Any) -> Dict[str, int]:
    if roi is None:
        return {}
    if isinstance(roi, dict):
        return {
            'left': int(roi.get('left', 0)),
            'top': int(roi.get('top', 0)),
            'width': int(roi.get('width', 0)),
            'height': int(roi.get('height', 0))
        }
    # Dataclass-like
    return {
        'left': int(getattr(roi, 'left', 0)),
        'top': int(getattr(roi, 'top', 0)),
        'width': int(getattr(roi, 'width', 0)),
        'height': int(getattr(roi, 'height', 0))
    }

def format_roi(roi: Any) -> str:
    if roi is None:
        return "Not set"
    # Allow ROI dataclass with mode or dict
    mode = getattr(roi, 'mode', None)
    data = roi_to_dict(roi)
    if not data or data.get('width', 0) <= 0 or data.get('height', 0) <= 0:
        return "Not set"
    if mode is None and isinstance(roi, dict):
        mode = roi.get('mode')
    mode_str = f" ({str(mode).lower()})" if mode else ""
    return f"Left: {data['left']}, Top: {data['top']}, Width: {data['width']}, Height: {data['height']}{mode_str}"
