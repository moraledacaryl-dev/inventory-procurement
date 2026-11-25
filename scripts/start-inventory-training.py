#!/usr/bin/env python3
"""Start an already installed browser training build. No employee setup prompts.

Administrators install Python requirements and build the web payload first.
The launcher inherits no operational API/DB settings and refuses contaminated
environments instead of silently deleting their values.
"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.request import urlopen
import webbrowser

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def main():
    from importlib.util import find_spec
    if sys.version_info < (3, 11) or not find_spec("uvicorn"):
        raise SystemExit("The training runtime is not installed. Ask your trainer to install the prepared training package.")
    frontend = ROOT / "frontend/.next/standalone"
    if not (frontend / "server.js").is_file() or not (frontend / ".next/static").is_dir():
        raise SystemExit("The training web build is missing. Ask your trainer for the complete package.")
    import json
    marker=frontend/"inventory-training-build.json"
    if not marker.is_file() or json.loads(marker.read_text()).get("environment")!="isolated-training":
        raise SystemExit("This package has no verified training build. Ask your trainer for the correct package.")
    # Validate before starting either service; never pass an operational env.
    sys.path.insert(0, str(ROOT / "backend"))
    from training.safety import configure
    previous = Path.cwd()
    os.chdir(ROOT / "backend")
    data = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "HiddenOasis" / "inventory-training"
    configure(data)
    env = {**os.environ, "NEXT_PUBLIC_INVENTORY_TRAINING": "1", "NEXT_TELEMETRY_DISABLED": "1", "HOSTNAME": "127.0.0.1", "PORT": "3400"}
    children = []
    def stop(*_):
        for child in children:
            if child.poll() is None: child.terminate()
        for child in children:
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: child.kill()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        # Probe both ports first, so an unrelated service is never mistaken for
        # a successful startup or opened as the practice application.
        import socket
        for port in (3400,8400):
            with socket.socket() as probe:
                # A previous smoke test may leave accepted sockets in TIME_WAIT.
                # POSIX permits reuse without sharing an active listener.
                if os.name != "nt": probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                elif hasattr(socket,"SO_EXCLUSIVEADDRUSE"): probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                try: probe.bind(("127.0.0.1",port))
                except OSError: raise SystemExit("Training is already open, or a required local port is in use. Close the earlier training window and try again.")
        api_command = [sys.executable,"--training-api","--data",str(data)] if getattr(sys,"frozen",False) else [sys.executable,"-m","training.launch","--data",str(data)]
        node = ROOT / "runtime" / ("node.exe" if os.name == "nt" else "node")
        children.append(subprocess.Popen(api_command,cwd=ROOT/"backend"))
        children.append(subprocess.Popen([str(node) if node.exists() else "node","server.js"],cwd=frontend,env=env))
        for _ in range(80):
            if any(child.poll() is not None for child in children): raise SystemExit("Training could not start. Ask your trainer to check the installation.")
            try:
                import json
                with urlopen("http://127.0.0.1:3400/api/v1/training/catalogue",timeout=1) as response:
                    if json.load(response).get("environment")=="isolated-training": break
            except Exception: time.sleep(.25)
        else: raise SystemExit("Training is taking too long to open. Close it and try again.")
        if os.environ.get("INVENTORY_TRAINING_NO_BROWSER") != "1":
            webbrowser.open("http://127.0.0.1:3400/training")
        children[0].wait()
    finally:
        stop();os.chdir(previous)


def launch():
    if sys.stdout is None: sys.stdout = open(os.devnull,"w")
    if sys.stderr is None: sys.stderr = open(os.devnull,"w")
    if "--training-api" in sys.argv:
        sys.argv.remove("--training-api")
        sys.path.insert(0,str(ROOT / "backend"))
        from training.launch import main as api_main
        api_main()
    else:
        main()


if __name__ == "__main__":
    try:
        launch()
    except BaseException:
        # Windowed macOS apps have no console. Keep startup failures available
        # to the trainer and CI, only inside an already marked training folder.
        import traceback
        data=Path(os.environ.get("LOCALAPPDATA",str(Path.home()/".local/share")))/"HiddenOasis"/"inventory-training"
        if (data/"training-only.json").is_file() and not data.is_symlink():
            (data/"launcher-error.log").write_text(traceback.format_exc())
        raise
