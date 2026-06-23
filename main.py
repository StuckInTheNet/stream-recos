#!/Users/mattfish/stream-recos/.venv/bin/python3
"""Stream Recos — scrape your streaming history and get recommendations."""

import os
os.environ["PYTHONUNBUFFERED"] = "1"

import argparse
import sys
from dotenv import load_dotenv

from scrapers import SCRAPERS
from recommender import load_all_history, get_recommendations

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

    args = parser.parse_args()

    if args.command == "scrape":
        scrape(args.services, headless=not args.visible)
    elif args.command == "recos":
        recommend(args.count)
    elif args.command == "all":
        scrape(args.services, headless=not args.visible)
        recommend(args.count)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
