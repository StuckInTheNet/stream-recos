#!/usr/bin/env python3
"""Stream Recos — scrape your streaming history and get recommendations."""

import os
os.environ["PYTHONUNBUFFERED"] = "1"

import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

from scrapers import SCRAPERS
from recommender import load_all_history, get_recommendations, check_ollama, OLLAMA_URL, OLLAMA_MODEL

load_dotenv()

ENV_KEYS = {
    "netflix": ("NETFLIX_EMAIL", "NETFLIX_PASSWORD"),
    "disney": ("DISNEY_EMAIL", "DISNEY_PASSWORD"),
    "hulu": ("HULU_EMAIL", "HULU_PASSWORD"),
    "max": ("MAX_EMAIL", "MAX_PASSWORD"),
}


def scrape(services: list[str], headless: bool) -> None:
    for name in services:
        env_email, env_pass = ENV_KEYS[name]
        email = os.getenv(env_email)
        password = os.getenv(env_pass)

        if not email or not password:
            print(f"[{name}] Skipping — {env_email} or {env_pass} not set in .env")
            continue

        scraper_cls = SCRAPERS[name]
        scraper = scraper_cls(email, password)
        try:
            scraper.run(headless=headless)
        except Exception as e:
            print(f"[{name}] Failed: {e}")


def recommend(count: int) -> None:
    history = load_all_history()
    if not history:
        print("No history found. Run `python main.py scrape` first.")
        sys.exit(1)

    total = sum(len(v) for v in history.values())
    services = ", ".join(history.keys())
    print(f"\nLoaded {total} titles from: {services}\n")
    print("Getting recommendations...\n")
    print(get_recommendations(history, count))


def status() -> None:
    """Check the health of all dependencies and show current state."""
    HISTORY_DIR = Path(__file__).parent / "history"

    # Check Ollama
    print("Ollama")
    if check_ollama():
        print(f"  OK  {OLLAMA_URL} ({OLLAMA_MODEL})")
    else:
        print(f"  FAIL  Cannot reach {OLLAMA_URL}")

    # Check credentials
    print("\nCredentials")
    for name, (env_email, env_pass) in ENV_KEYS.items():
        email = os.getenv(env_email)
        has_pass = bool(os.getenv(env_pass))
        if email and has_pass:
            print(f"  OK  {name}: {email}")
        else:
            missing = []
            if not email:
                missing.append(env_email)
            if not has_pass:
                missing.append(env_pass)
            print(f"  --  {name}: missing {', '.join(missing)}")

    # Check scraped history
    print("\nHistory")
    history = load_all_history()
    if history:
        for service, titles in history.items():
            json_path = HISTORY_DIR / f"{service}.json"
            age = ""
            if json_path.exists():
                import json
                from datetime import datetime
                data = json.loads(json_path.read_text())
                scraped_at = data.get("scraped_at", "")
                if scraped_at:
                    dt = datetime.fromisoformat(scraped_at)
                    age = f" (scraped {dt.strftime('%Y-%m-%d %H:%M')})"
            print(f"  {service}: {len(titles)} titles{age}")
    else:
        print("  No history found. Run `python main.py scrape` first.")

    # Check sessions
    print("\nSessions")
    sessions_dir = Path(__file__).parent / "sessions"
    if sessions_dir.exists():
        for f in sorted(sessions_dir.glob("*.json")):
            from datetime import datetime
            age_days = (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days
            print(f"  {f.stem}: {age_days}d old")
    else:
        print("  No saved sessions")


def clear(services: list[str]) -> None:
    """Delete scraped history and/or sessions for given services."""
    HISTORY_DIR = Path(__file__).parent / "history"
    SESSIONS_DIR = Path(__file__).parent / "sessions"

    for name in services:
        deleted = []
        history_file = HISTORY_DIR / f"{name}.json"
        session_file = SESSIONS_DIR / f"{name}.json"
        if history_file.exists():
            history_file.unlink()
            deleted.append("history")
        if session_file.exists():
            session_file.unlink()
            deleted.append("session")
        if deleted:
            print(f"[{name}] Cleared: {', '.join(deleted)}")
        else:
            print(f"[{name}] Nothing to clear")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream Recos")
    sub = parser.add_subparsers(dest="command")

    # scrape command
    scrape_p = sub.add_parser("scrape", help="Scrape viewing history")
    scrape_p.add_argument(
        "services",
        nargs="*",
        default=list(SCRAPERS.keys()),
        choices=list(SCRAPERS.keys()),
        help="Services to scrape (default: all configured)",
    )
    scrape_p.add_argument(
        "--visible", action="store_true",
        help="Show browser window (useful for debugging / 2FA)",
    )

    # recommend command
    rec_p = sub.add_parser("recos", help="Get recommendations from scraped history")
    rec_p.add_argument("-n", "--count", type=int, default=10, help="Number of recommendations")

    # all-in-one
    all_p = sub.add_parser("all", help="Scrape + recommend in one shot")
    all_p.add_argument(
        "services",
        nargs="*",
        default=list(SCRAPERS.keys()),
        choices=list(SCRAPERS.keys()),
    )
    all_p.add_argument("--visible", action="store_true")
    all_p.add_argument("-n", "--count", type=int, default=10)

    # status command
    sub.add_parser("status", help="Check Ollama, credentials, and scraped history")

    # clear command
    clear_p = sub.add_parser("clear", help="Delete history and sessions for services")
    clear_p.add_argument(
        "services",
        nargs="*",
        default=list(SCRAPERS.keys()),
        choices=list(SCRAPERS.keys()),
        help="Services to clear (default: all)",
    )

    args = parser.parse_args()

    if args.command == "scrape":
        scrape(args.services, headless=not args.visible)
    elif args.command == "recos":
        recommend(args.count)
    elif args.command == "all":
        scrape(args.services, headless=not args.visible)
        recommend(args.count)
    elif args.command == "status":
        status()
    elif args.command == "clear":
        clear(args.services)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
