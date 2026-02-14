"""Stop local backend/frontend processes using PID files under .local/."""

from __future__ import annotations

import argparse
import os
import signal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / ".local"
BACKEND_PID = STATE_DIR / "backend.pid"
FRONTEND_PID = STATE_DIR / "frontend.pid"


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _stop_pid(path: Path, label: str) -> None:
    pid = _read_pid(path)
    if pid is None:
        print(f"{label}: no pid file")
        return
    if not _is_running(pid):
        print(f"{label}: process not running (pid={pid})")
        path.unlink(missing_ok=True)
        return

    try:
        os.kill(pid, signal.SIGTERM)
        print(f"{label}: sent SIGTERM to pid={pid}")
    except OSError as exc:
        print(f"{label}: failed to stop pid={pid}: {exc}")
    finally:
        path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stop local marketplace processes.")
    parser.add_argument(
        "--only",
        choices=["backend", "frontend", "both"],
        default="both",
        help="Choose which process group to stop (default: both).",
    )
    args = parser.parse_args()

    if args.only in {"backend", "both"}:
        _stop_pid(BACKEND_PID, "backend")
    if args.only in {"frontend", "both"}:
        _stop_pid(FRONTEND_PID, "frontend")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
