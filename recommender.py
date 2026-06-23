import json
import urllib.request
from pathlib import Path

HISTORY_DIR = Path(__file__).parent / "history"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3:8b"

# ANSI colors
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
WHITE = "\033[97m"


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


def get_recommendations(history: dict[str, list[str]], count: int = 10) -> str:
    """Use Ollama to generate recommendations based on viewing history."""
    if not history:
        return "No viewing history found. Run scraping first."

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

Respond with this exact JSON format:
{{
  "recommendations": [
    {{
      "title": "Show Name",
      "platform": "Netflix",
      "match_score": 9,
      "reason": "1-2 sentence explanation referencing specific shows from their history"
    }}
  ]
}}

Viewing history:
{history_text}"""

    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read())

    raw = result["response"]

    # Try to parse as JSON and format nicely
    try:
        # Extract JSON from response (model might add text around it)
        start = raw.index("{")
        end = raw.rindex("}") + 1
        data = json.loads(raw[start:end])
        return format_recommendations(data["recommendations"])
    except (ValueError, KeyError, json.JSONDecodeError):
        # Fallback: return raw text if JSON parsing fails
        return raw


def score_bar(score: int) -> str:
    """Render a visual match score bar."""
    filled = "█" * score
    empty = "░" * (10 - score)
    if score >= 8:
        color = GREEN
    elif score >= 5:
        color = YELLOW
    else:
        color = DIM
    return f"{color}{filled}{DIM}{empty}{RESET}"


def format_recommendations(recs: list[dict]) -> str:
    """Format recommendations into a clean terminal display."""
    total = sum(len(v) for v in load_all_history().values())

    lines = []
    lines.append(f"\n{BOLD}{'─' * 60}{RESET}")
    lines.append(f"{BOLD}  🎬  YOUR RECOMMENDATIONS{RESET}")
    lines.append(f"{DIM}  Based on {total:,} titles across your streaming services{RESET}")
    lines.append(f"{BOLD}{'─' * 60}{RESET}\n")

    for i, rec in enumerate(recs, 1):
        title = rec.get("title", "Unknown")
        platform = rec.get("platform", "Unknown")
        score = min(max(rec.get("match_score", 5), 1), 10)
        reason = rec.get("reason", "")

        lines.append(f"  {BOLD}{WHITE}{i:2d}. {title}{RESET}")
        lines.append(f"      {CYAN}{platform}{RESET}  {score_bar(score)} {BOLD}{score}/10{RESET}")
        lines.append(f"      {DIM}{reason}{RESET}")
        lines.append("")

    lines.append(f"{BOLD}{'─' * 60}{RESET}")
    return "\n".join(lines)
