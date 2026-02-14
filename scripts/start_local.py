"""Start local backend and frontend processes and persist PIDs under .local/."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
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


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _start_backend() -> None:
    existing = _read_pid(BACKEND_PID)
    if existing and _is_running(existing):
        print(f"Backend already running (pid={existing})")
        return
    if _port_in_use("127.0.0.1", 8000):
        print("Backend port 8000 already in use; assuming backend is already running")
        return

    out = (STATE_DIR / "backend.out.log").open("w", encoding="utf-8")
    err = (STATE_DIR / "backend.err.log").open("w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "marketplace.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=ROOT,
            stdout=out,
            stderr=err,
        )
    finally:
        out.close()
        err.close()

    time.sleep(1.0)
    if proc.poll() is not None:
        BACKEND_PID.unlink(missing_ok=True)
        print("Backend failed to start; check .local/backend.err.log")
        return

    BACKEND_PID.write_text(str(proc.pid), encoding="utf-8")
    print(f"Started backend (pid={proc.pid}) -> http://127.0.0.1:8000")


def _start_frontend() -> None:
    existing = _read_pid(FRONTEND_PID)
    if existing and _is_running(existing):
        print(f"Frontend already running (pid={existing})")
        return
    if _port_in_use("127.0.0.1", 3000):
        print("Frontend port 3000 already in use; assuming frontend is already running")
        return

    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    out = (STATE_DIR / "frontend.out.log").open("w", encoding="utf-8")
    err = (STATE_DIR / "frontend.err.log").open("w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            [npm_cmd, "run", "dev:host"],
            cwd=ROOT / "frontend",
            stdout=out,
            stderr=err,
        )
    finally:
        out.close()
        err.close()

    time.sleep(1.0)
    if proc.poll() is not None:
        FRONTEND_PID.unlink(missing_ok=True)
        print("Frontend failed to start; check .local/frontend.err.log")
        return

    FRONTEND_PID.write_text(str(proc.pid), encoding="utf-8")
    print(f"Started frontend (pid={proc.pid}) -> http://127.0.0.1:3000")


def main() -> int:
    parser = argparse.ArgumentParser(description="Start local marketplace processes.")
    parser.add_argument(
        "--only",
        choices=["backend", "frontend", "both"],
        default="both",
        help="Choose which process group to start (default: both).",
    )
    args = parser.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if args.only in {"backend", "both"}:
        _start_backend()
    if args.only in {"frontend", "both"}:
        _start_frontend()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
