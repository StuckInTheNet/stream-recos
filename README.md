<p align="center">
  <img src="assets/logo.svg" alt="streamrecos" width="700" />
</p>

<p align="center">
  <strong>Scrape your streaming history. Get personalized recommendations. All from your terminal.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/ollama-llama3:8b-orange?logo=meta&logoColor=white" alt="Ollama" />
  <img src="https://img.shields.io/badge/playwright-chromium-green?logo=playwright&logoColor=white" alt="Playwright" />
  <img src="https://img.shields.io/badge/license-MIT-purple" alt="MIT License" />
</p>

---

## What It Does

**streamrecos** logs into your streaming services, pulls your viewing history, and feeds it to a local LLM to generate personalized recommendations. No data leaves your machine (besides the login itself). Platforms are verified through JustWatch so you know exactly where to watch each recommendation.

### Supported Services

| Service | Scraper | History Source |
|---------|---------|----------------|
| Netflix | `netflix.py` | Activity page (paginated, up to 50 pages) |
| Disney+ | `disney.py` | Watch history shelf |
| Hulu | `hulu.py` | Watch history shelf |
| Max | `max.py` | Continue Watching shelf |

## Getting Started

### Prerequisites

- **Python 3.10+**
- **[Ollama](https://ollama.com)** running locally with `llama3:8b` pulled
- Streaming service credentials

### Installation

```bash
git clone https://github.com/StuckInTheNet/stream-recos.git
cd stream-recos
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Configuration

Create a `.env` file in the project root:

```env
NETFLIX_EMAIL=you@example.com
NETFLIX_PASSWORD=your-password

DISNEY_EMAIL=you@example.com
DISNEY_PASSWORD=your-password

HULU_EMAIL=you@example.com
HULU_PASSWORD=your-password

MAX_EMAIL=you@example.com
MAX_PASSWORD=your-password
```

Only configure the services you use. Any missing credentials are simply skipped.

## Usage

### Scrape viewing history

```bash
# Scrape all configured services
python main.py scrape

# Scrape specific services
python main.py scrape netflix disney

# Show the browser window (useful for 2FA or debugging)
python main.py scrape --visible
```

### Get recommendations

```bash
# Get 10 recommendations (default)
python main.py recos

# Get a custom number
python main.py recos -n 20
```

### Do everything at once

```bash
python main.py all
python main.py all netflix hulu -n 15
```

### Example Output

```
──────────────────────────────────────────────────────────
  🎬  YOUR RECOMMENDATIONS
  Based on 247 titles across your streaming services
──────────────────────────────────────────────────────────

   1. Severance
      Apple TV+
      █████████░ 9/10 match
      Dark workplace thriller like Black Mirror episodes you've watched

   2. The Bear
      Hulu · Disney+
      ████████░░ 8/10 match
      High-intensity drama similar to your interest in Breaking Bad

   3. Shogun
      Hulu · Disney+
      ████████░░ 8/10 match
      Epic historical drama matching your Game of Thrones viewing pattern
──────────────────────────────────────────────────────────
```

## How It Works

1. **Scrape** - Playwright launches a headless Chromium browser, logs into each service, and extracts your watch history. Sessions are cached so subsequent runs skip the login step.

2. **Recommend** - Your combined history is sent to a local Ollama instance running `llama3:8b`. The model analyzes your viewing patterns and generates scored recommendations with reasoning.

3. **Verify** - Each recommendation is checked against JustWatch to confirm which streaming platforms currently offer it. Already-watched titles are automatically filtered out.

## Project Structure

```
stream-recos/
├── main.py              # CLI entry point
├── recommender.py       # Ollama integration + JustWatch verification
├── email_code.py        # OTP/2FA code handler
├── scrapers/
│   ├── base.py          # BaseScraper with shared browser logic
│   ├── netflix.py       # Netflix history scraper
│   ├── disney.py        # Disney+ history scraper
│   ├── hulu.py          # Hulu history scraper
│   └── max.py           # Max (HBO) history scraper
├── history/             # Scraped history JSON files (gitignored)
├── sessions/            # Saved browser sessions (gitignored)
└── requirements.txt
```

## 2FA / OTP Handling

Some services (Disney+, Hulu) may prompt for a one-time passcode during login. streamrecos handles this automatically:

1. When an OTP page is detected, it watches for the code via `email_code.py`
2. The code is entered digit-by-digit into split input fields
3. Use `--visible` if you need to manually intervene

## Privacy

All recommendation processing happens locally through Ollama. Your viewing history stays on your machine. The only external calls are:

- **Login requests** to each streaming service (required to access history)
- **JustWatch API** to verify platform availability for recommendations

No analytics. No telemetry. No cloud AI APIs.

## License

MIT
