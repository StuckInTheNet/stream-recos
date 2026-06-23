#!/usr/bin/env python3
"""Open a browser for manual login. Saves full session state for the scraper."""

import os
os.environ["PYTHONUNBUFFERED"] = "1"

import argparse
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

SESSIONS_DIR = Path(__file__).parent / "sessions"

SERVICES = {
    "netflix": "https://www.netflix.com/login",
    "disney": "https://www.disneyplus.com/login",
    "hulu": "https://www.hulu.com",
    "max": "https://www.hbomax.com",
}

# URL patterns that indicate successful login
LOGGED_IN_PATTERNS = {
    "netflix": ["/browse", "/profiles"],
    "disney": ["/home", "/watchlist"],
    "hulu": ["/hub/", "/my-stuff"],
    "max": ["/home", "/my-list"],
}


def manual_login(service: str) -> None:
    SESSIONS_DIR.mkdir(exist_ok=True)
    session_path = SESSIONS_DIR / f"{service}.json"
    url = SERVICES[service]
    patterns = LOGGED_IN_PATTERNS[service]

    print(f"Opening browser for {service}...", flush=True)
    print(f"Log in fully, then the session will auto-save when the home page loads.\n", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)

        # Poll until URL shows logged-in state
        for i in range(180):  # 6 min max
            try:
                current_url = page.url
                if any(pattern in current_url for pattern in patterns):
                    print(f"Detected logged-in page: {current_url}", flush=True)
                    page.wait_for_timeout(5000)  # Let it fully load
                    break
            except Exception:
                break  # Browser was closed
            time.sleep(2)

        # Save full storage state
        context.storage_state(path=str(session_path))

        state = json.loads(session_path.read_text())
        n_cookies = len(state.get("cookies", []))
        ls_items = sum(len(o.get("localStorage", [])) for o in state.get("origins", []))
        print(f"\nSaved: {n_cookies} cookies, {ls_items} localStorage items", flush=True)
        print(f"Session file: {session_path}", flush=True)

        browser.close()


def main():
    parser = argparse.ArgumentParser(description="Manual login for streaming services")
    parser.add_argument("service", choices=list(SERVICES.keys()))
    args = parser.parse_args()
    manual_login(args.service)


if __name__ == "__main__":
    main()
