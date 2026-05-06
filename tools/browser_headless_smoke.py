#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "SourceCode"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.common import ensure_runtime
from werkzeug.serving import make_server


def _browser_path() -> Path | None:
    candidates = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    browser = _browser_path()
    if browser is None:
        print("Browser smoke skipped: no local Chrome/Edge binary found.")
        return 2

    from web_gui import app as appmod

    temp_root = ROOT / "Runtime" / "test_browser_headless_smoke"
    if temp_root.exists():
        shutil.rmtree(temp_root, ignore_errors=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    ensure_runtime(temp_root)

    original_root = appmod.ROOT
    original_background = appmod._ensure_background_services_started
    appmod.ROOT = temp_root
    appmod._ensure_background_services_started = lambda _app=None: None

    server = None
    thread = None
    try:
        app = appmod.create_app()
        server = make_server("127.0.0.1", 5067, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(1.0)

        required = ("Life Admin", "Second Brain", "System", "Oathweaver")
        browser_candidates = [browser]
        alternate = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        if alternate.exists() and alternate not in browser_candidates:
            browser_candidates.append(alternate)
        edge_alt = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
        if edge_alt.exists() and edge_alt not in browser_candidates:
            browser_candidates.append(edge_alt)

        last_error = ""
        for candidate in browser_candidates:
            screenshot_path = temp_root / "Runtime" / f"browser_smoke_{candidate.stem}.png"
            user_data_dir = temp_root / "Runtime" / f"{candidate.stem}_profile"
            user_data_dir.mkdir(parents=True, exist_ok=True)
            cmd = [
                str(candidate),
                "--headless=new",
                "--disable-gpu",
                "--disable-crashpad-for-testing",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={user_data_dir}",
                f"--screenshot={screenshot_path}",
                "--window-size=1440,1400",
                "--virtual-time-budget=4000",
                "--dump-dom",
                "http://127.0.0.1:5067/",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
            if proc.returncode != 0:
                last_error = proc.stderr.strip() or proc.stdout.strip() or f"{candidate.name} exited with {proc.returncode}"
                continue

            dom = proc.stdout
            missing = [token for token in required if token not in dom]
            if missing:
                last_error = f"{candidate.name} missing DOM markers: {', '.join(missing)}"
                continue
            if not screenshot_path.exists():
                last_error = f"{candidate.name} did not create a screenshot"
                continue
            print(f"Browser smoke passed with {candidate.name}. Screenshot: {screenshot_path}")
            return 0

        print(last_error or "Browser smoke failed for all local browser candidates.")
        return 1
    finally:
        if server is not None:
            server.shutdown()
        if thread is not None:
            thread.join(timeout=5)
        appmod.ROOT = original_root
        appmod._ensure_background_services_started = original_background
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
