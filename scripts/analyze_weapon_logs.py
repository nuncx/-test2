"""
Analyze JSONL logs produced by scripts/debug_weapon_detection.py --json --logfile ...
Print concise metrics to help tuning thresholds for small ROIs.
"""
from __future__ import annotations
import argparse
import json
from collections import defaultdict, Counter
from typing import Dict, Any


def safe_get(d: Dict[str, Any], key: str, default=None):
    try:
        return d.get(key, default)
    except Exception:
        return default


def analyze(path: str):
    total = 0
    errors = 0
    relaxed_hits = 0

    # Aggregates
    normal_sum = Counter()
    visible_hits = Counter()
    visible_sum = Counter()
    current_dist = Counter()
    decision_dist = Counter()
    required_present = 0
    required_visible_hits = 0
    zero_normal_frames = 0

    # Per-sample capture for optional debugging
    zero_normal_examples = []

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                sample = json.loads(line)
            except Exception:
                errors += 1
                continue
            if 'error' in sample:
                errors += 1
                continue
            total += 1

            nc = safe_get(sample, 'normal_counts', {}) or {}
            rc = safe_get(sample, 'relaxed_counts', None)
            vis = safe_get(sample, 'visible', {}) or {}
            cur = safe_get(sample, 'current', None)
            dec = safe_get(sample, 'decision', None)
            req = safe_get(sample, 'required', None)

            if rc:
                relaxed_hits += 1
            if isinstance(cur, str) or cur is None:
                current_dist[str(cur)] += 1
            if isinstance(dec, str):
                decision_dist[dec] += 1

            if not nc or sum(nc.values()) == 0:
                zero_normal_frames += 1
                if rc:
                    zero_normal_examples.append({
                        'ts': sample.get('ts'),
                        'normal_counts': nc,
                        'relaxed_counts': rc,
                        'visible': vis,
                        'decision': dec,
                        'required': req,
                    })

            # Sums and visibility
            for k, v in nc.items():
                normal_sum[k] += int(v)
            for k, v in vis.items():
                visible_hits[k] += 1
                visible_sum[k] += int(v)

            if req:
                required_present += 1
                if isinstance(vis, dict) and req in vis:
                    required_visible_hits += 1

    # Print summary
    print("=== Weapon Log Analysis ===")
    print(f"file: {path}")
    print(f"total_samples: {total} | parse_errors: {errors}")
    print(f"relaxed_triggered_frames: {relaxed_hits} ({(relaxed_hits/total*100 if total else 0):.1f}%)")
    print(f"zero_normal_frames: {zero_normal_frames} ({(zero_normal_frames/total*100 if total else 0):.1f}%)")

    styles = ['melee','ranged','magic']
    print("-- Averages (normal counts) --")
    for s in styles:
        avg = (normal_sum[s]/total) if total else 0
        print(f"{s:>6}: avg={avg:.2f}")

    print("-- Visibility --")
    for s in styles:
        rate = (visible_hits[s]/total*100) if total else 0
        avg_visible_val = (visible_sum[s]/max(visible_hits[s],1)) if visible_hits[s] else 0
        print(f"{s:>6}: visible_rate={rate:5.1f}% | visible_avg_val={avg_visible_val:.1f}")

    print("-- Current detected distribution --")
    for k, v in current_dist.most_common():
        pct = v/total*100 if total else 0
        print(f"current={k:>6}: {v} ({pct:.1f}%)")

    print("-- Decision distribution --")
    for k, v in decision_dist.most_common():
        pct = v/total*100 if total else 0
        print(f"{k:>36}: {v} ({pct:.1f}%)")

    if required_present:
        pct = required_visible_hits/required_present*100
        print(f"required_frames: {required_present} | required_visible: {required_visible_hits} ({pct:.1f}%)")

    if zero_normal_examples:
        print("-- Examples where normal counts were zero but relaxed had signal (up to 5) --")
        for ex in zero_normal_examples[:5]:
            print(json.dumps(ex, ensure_ascii=False))

    # Heuristic hints
    print("-- Hints --")
    if relaxed_hits > total * 0.25:
        print("Relaxed retry fired often → loosen base slightly (lab +2) or reduce sat/val by ~5 each.")
    if any(visible_hits[s] > total * 0.8 for s in styles):
        print("A style is almost always visible → check ROI includes only icons; consider lab -2 or sat/val +5 to suppress bleed.")
    if zero_normal_frames > total * 0.25:
        print("Many frames had zero normal counts → base is too strict or ROI misses icons. Expand ROI or relax lab/sat/val a bit.")


def main():
    ap = argparse.ArgumentParser(description="Analyze weapon tuning JSONL logs")
    ap.add_argument("file", help="Path to JSONL file (logs/weapon_tuning.jsonl)")
    args = ap.parse_args()
    analyze(args.file)


if __name__ == '__main__':
    main()
