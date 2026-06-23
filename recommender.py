import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

HISTORY_DIR = Path(__file__).parent / "history"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

JUSTWATCH_URL = "https://apis.justwatch.com/graphql"
JUSTWATCH_QUERY = """
query GetSearchTitles($searchTitlesFilter: TitleFilter!, $country: Country!, $language: Language!) {
  popularTitles(country: $country, filter: $searchTitlesFilter, first: 1) {
    edges {
      node {
        content(country: $country, language: $language) {
          title
        }
        offers(country: $country, platform: WEB) {
          monetizationType
          package {
            clearName
          }
        }
      }
    }
  }
}
"""

# ANSI colors
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
WHITE = "\033[97m"
RED = "\033[31m"


def check_ollama() -> bool:
    """Check if Ollama is reachable. Returns True if healthy."""
    try:
        req = urllib.request.Request(
            OLLAMA_URL.replace("/api/generate", "/api/tags"),
            method="GET",
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False


def load_all_history() -> dict[str, list[str]]:
    """Load saved history from all services. Returns {service: [title, ...]}."""
    history = {}
    for path in HISTORY_DIR.glob("*.json"):
        data = json.loads(path.read_text())
        if "history" not in data:
            continue
        titles = [item["title"] for item in data["history"]]
        if titles:
            history[data["service"]] = titles
    return history


def lookup_platform(title: str) -> list[str]:
    """Look up which streaming platforms a title is available on via JustWatch."""
    try:
        payload = json.dumps({
            "query": JUSTWATCH_QUERY,
            "variables": {
                "searchTitlesFilter": {"searchQuery": title},
                "country": "US",
                "language": "en",
            },
        }).encode()
        req = urllib.request.Request(
            JUSTWATCH_URL, data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read())
        edges = data["data"]["popularTitles"]["edges"]
        if not edges:
            return []
        offers = edges[0]["node"].get("offers", [])
        # Only include streaming (not rent/buy)
        platforms = []
        seen = set()
        for o in offers:
            if o["monetizationType"] in ("FLATRATE", "FREE", "ADS"):
                name = o["package"]["clearName"]
                # Normalize common names
                name = name.replace(" Standard with Ads", "").replace(" Basic with Ads", "")
                if name not in seen:
                    platforms.append(name)
                    seen.add(name)
        return platforms
    except Exception:
        return []


def get_recommendations(history: dict[str, list[str]], count: int = 10) -> str:
    """Use Ollama to generate recommendations based on viewing history."""
    if not history:
        return "No viewing history found. Run scraping first."

    # Pre-check: is Ollama running?
    if not check_ollama():
        print(f"{RED}Error: Cannot reach Ollama at {OLLAMA_URL}{RESET}")
        print(f"{DIM}Make sure Ollama is running: ollama serve{RESET}")
        print(f"{DIM}Then pull the model: ollama pull {OLLAMA_MODEL}{RESET}")
        sys.exit(1)

    total_titles = sum(len(v) for v in history.values())

    history_text = ""
    for service, titles in history.items():
        history_text += f"\n{service.upper()} ({len(titles)} titles):\n"
        for title in titles[:100]:
            history_text += f"  - {title}\n"

    prompt = f"""Based on this viewing history across streaming services, recommend {count} shows or movies to watch next.

You MUST respond with valid JSON only. No other text before or after the JSON.

Rules:
- CRITICAL: Do NOT recommend anything already listed in the viewing history below.
- Every recommendation must be something NEW that is not in the history.
- Mix genres based on patterns in what this person watches.
- Focus on highly-rated shows and movies.
- The match_score is 1-10 representing how well this matches their taste (10 = perfect match).
- Do NOT include a "platform" field -- platforms will be looked up separately.

Respond with this exact JSON format:
{{
  "recommendations": [
    {{
      "title": "Show Name",
      "match_score": 9,
      "reason": "1-2 sentence explanation referencing specific shows from their history"
    }}
  ]
}}

Viewing history:
{history_text}"""

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    print(f"{DIM}  Generating recommendations with {OLLAMA_MODEL}...{RESET}", flush=True)

    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            result = json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"{RED}Error: Failed to connect to Ollama at {OLLAMA_URL}{RESET}")
        print(f"{DIM}{e}{RESET}")
        sys.exit(1)
    except TimeoutError:
        print(f"{RED}Error: Ollama timed out after {OLLAMA_TIMEOUT}s{RESET}")
        print(f"{DIM}Try increasing OLLAMA_TIMEOUT or using a smaller model{RESET}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"{RED}Error: Ollama returned invalid JSON{RESET}")
        sys.exit(1)

    raw = result["response"]

    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        data = json.loads(raw[start:end])
        recs = data["recommendations"]
    except (ValueError, KeyError, json.JSONDecodeError):
        print(f"{RED}Error: Could not parse recommendations from model response{RESET}")
        print(f"{DIM}Raw response:{RESET}\n{raw[:500]}")
        sys.exit(1)

    # Filter out titles that are already in the viewing history
    all_watched = set()
    for titles in history.values():
        for t in titles:
            # Normalize: lowercase, strip season/episode info
            all_watched.add(t.lower().split(":")[0].strip())
    recs = [r for r in recs if r["title"].lower().split(":")[0].strip() not in all_watched]

    # Look up real platforms via JustWatch
    justwatch_failed = 0
    for i, rec in enumerate(recs, 1):
        print(f"{DIM}  Verifying platforms ({i}/{len(recs)})...{RESET}", end="\r", flush=True)
        platforms = lookup_platform(rec["title"])
        rec["platforms"] = platforms
        if not platforms:
            justwatch_failed += 1
    print(" " * 60, end="\r")  # Clear progress line

    if justwatch_failed == len(recs) and len(recs) > 0:
        print(f"{YELLOW}  Warning: JustWatch API returned no results. Platform info may be unavailable.{RESET}")

    return format_recommendations(recs, total_titles)


def score_bar(score: int) -> str:
    """Render a visual match score bar."""
    filled = "\u2588" * score
    empty = "\u2591" * (10 - score)
    if score >= 8:
        color = GREEN
    elif score >= 5:
        color = YELLOW
    else:
        color = DIM
    return f"{color}{filled}{DIM}{empty}{RESET}"


def format_recommendations(recs: list[dict], total_titles: int) -> str:
    """Format recommendations into a clean terminal display."""
    lines = []
    lines.append(f"\n{BOLD}{'\u2500' * 60}{RESET}")
    lines.append(f"{BOLD}  \U0001f3ac  YOUR RECOMMENDATIONS{RESET}")
    lines.append(f"{DIM}  Based on {total_titles:,} titles across your streaming services{RESET}")
    lines.append(f"{BOLD}{'\u2500' * 60}{RESET}\n")

    for i, rec in enumerate(recs, 1):
        title = rec.get("title", "Unknown")
        score = min(max(rec.get("match_score", 5), 1), 10)
        reason = rec.get("reason", "")
        platforms = rec.get("platforms", [])

        if platforms:
            platform_str = f"{CYAN}{' \u00b7 '.join(platforms[:3])}{RESET}"
        else:
            platform_str = f"{DIM}Platform unavailable{RESET}"

        lines.append(f"  {BOLD}{WHITE}{i:2d}. {title}{RESET}")
        lines.append(f"      {platform_str}")
        lines.append(f"      {score_bar(score)} {BOLD}{score}/10{RESET} match")
        lines.append(f"      {DIM}{reason}{RESET}")
        lines.append("")

    lines.append(f"{BOLD}{'\u2500' * 60}{RESET}")
    return "\n".join(lines)
