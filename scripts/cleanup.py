import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SAFE_EXTS = {'.bak'}

SKIP_DIRS = {'.git', '.venv', 'env', 'venv', 'ENV', '.mypy_cache', '.pytest_cache'}

LOG_DIR = ROOT / 'logs'

def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def delete_bak_files(root: Path) -> int:
    count = 0
    for p in root.rglob('*.bak'):
        try:
            p.unlink()
            count += 1
        except Exception:
            pass
    return count


def delete_pycache(root: Path) -> int:
    count = 0
    for p in root.rglob('__pycache__'):
        try:
            shutil.rmtree(p, ignore_errors=True)
            count += 1
        except Exception:
            pass
    return count


def prune_logs(log_dir: Path, keep: int = 5) -> int:
    if not log_dir.exists():
        return 0
    logs = sorted(log_dir.glob('*.log*'), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for p in logs[keep:]:
        try:
            p.unlink()
            removed += 1
        except Exception:
            pass
    return removed


def main():
    print(f"Repo root: {ROOT}")
    bak_removed = delete_bak_files(ROOT)
    pycache_removed = delete_pycache(ROOT)
    logs_removed = prune_logs(LOG_DIR, keep=8)
    print("Cleanup summary:")
    print(f"  .bak files removed: {bak_removed}")
    print(f"  __pycache__ directories removed: {pycache_removed}")
    print(f"  log files pruned: {logs_removed}")

if __name__ == '__main__':
    main()
