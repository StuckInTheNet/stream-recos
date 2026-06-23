import json
import urllib.request
from pathlib import Path

HISTORY_DIR = Path(__file__).parent / "history"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"


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

Rules:
- Only output titles, one per line, numbered
- CRITICAL: Do NOT recommend anything already listed in the viewing history below. Every recommendation must be something NEW.
- Mix genres based on what the history shows — look for patterns in what this person likes
- Include which streaming service each recommendation is currently available on
- Focus on highly-rated shows and movies that match this person's taste

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
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())

    return result["response"]
