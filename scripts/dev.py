"""Run the Sweepr backend and the Vite dev server together.

    uv run python scripts/dev.py
    uv run python scripts/dev.py --port 8765 --token dev

The backend serves the API on 127.0.0.1 and Vite serves the UI with hot reload
on 127.0.0.1:5173. Ctrl+C stops both.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "sweepr_app" / "ui"
HOST = "127.0.0.1"
VITE_PORT = 5173


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    return True


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def _pnpm(*args: str) -> list[str]:
    exe = shutil.which("pnpm")
    if exe is None:
        raise SystemExit("pnpm is not on PATH. Install Node 22 and pnpm 10 first.")
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", exe, *args]
    return [exe, *args]


def _stop(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
            )
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        proc.kill()


def _open_browser(url: str) -> None:
    time.sleep(2.5)
    webbrowser.open(url)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, help="backend port (default: 8765 or a free port)")
    parser.add_argument("--token", default=os.environ.get("SWEEPR_TOKEN") or "dev", help="dev access token (default: dev)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the Vite URL")
    args = parser.parse_args()

    if not _port_free(VITE_PORT):
        print(f"error: Vite port {VITE_PORT} is already in use", file=sys.stderr)
        return 2

    port = args.port or 8765
    if not _port_free(port):
        if args.port:
            print(f"error: backend port {port} is already in use", file=sys.stderr)
            return 2
        port = _free_port()

    if not (UI / "node_modules").is_dir():
        print("installing UI dependencies...")
        subprocess.run(_pnpm("--dir", str(UI), "install"), cwd=ROOT, check=True)

    env = {**os.environ, "SWEEPR_PORT": str(port)}
    backend = [
        sys.executable,
        "-m",
        "sweepr_app",
        "--no-browser",
        "--host",
        HOST,
        "--port",
        str(port),
        "--token",
        args.token,
    ]
    frontend = _pnpm("--dir", str(UI), "dev")

    url = f"http://{HOST}:{VITE_PORT}/#token={quote(args.token, safe='')}"
    print(f"backend:  http://{HOST}:{port}")
    print(f"frontend: {url}")
    print("Ctrl+C stops both.")

    backend_proc = subprocess.Popen(backend, cwd=ROOT, env=env)
    try:
        frontend_proc = subprocess.Popen(frontend, cwd=ROOT, env=env)
    except BaseException:
        _stop(backend_proc)
        raise

    if not args.no_browser:
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    try:
        while True:
            for proc in (backend_proc, frontend_proc):
                if proc.poll() is not None:
                    return proc.returncode or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nstopping...")
        return 0
    finally:
        _stop(frontend_proc)
        _stop(backend_proc)


if __name__ == "__main__":
    raise SystemExit(main())
