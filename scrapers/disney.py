import logging
import re
from playwright.sync_api import Page
from scrapers.base import BaseScraper

logger = logging.getLogger("streamrecos")


# Sets that indicate watch history
HISTORY_SET_NAMES = {"continue watching", "pick up where you left off"}
# Sets that imply you watched something (e.g., "Because You Watched X")
BECAUSE_YOU_WATCHED_PATTERN = re.compile(r"because you watched (.+?)$", re.IGNORECASE)


class DisneyScraper(BaseScraper):
    name = "disney"
    login_url = "https://www.disneyplus.com/login"
    history_url = "https://www.disneyplus.com/watchlist"

    def login(self, page: Page) -> None:
        page.goto(self.login_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.fill("#email", self.email)
        page.click('button[type="submit"]')
        page.wait_for_timeout(3000)
        page.fill('input[type="password"]', self.password)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)
        self.handle_otp(page)
        try:
            page.locator('[data-testid="profile-avatar"]').first.click(timeout=5000)
            page.wait_for_timeout(3000)
        except Exception:
            pass

    def scrape_history(self, page: Page) -> list[dict]:
        history = []
        seen = set()

        # Intercept API responses to get structured data
        api_sets = []

        def handle_response(response):
            url = response.url
            if "explore/v1.18/set/" in url or "explore/v1.18/page/" in url:
                try:
                    api_sets.append(response.json())
                except Exception:
                    pass

        page.on("response", handle_response)

        # Load home page
        page.goto("https://www.disneyplus.com/home", wait_until="domcontentloaded")
        page.wait_for_timeout(20000)

        # Scroll to trigger lazy-loaded shelves
        for i in range(10):
            page.evaluate("window.scrollBy(0, 600)")
            page.wait_for_timeout(1500)

        # Extract titles from API responses
        for resp in api_sets:
            data = resp.get("data", {})

            # Handle set responses
            self._extract_from_set(data.get("set", {}), history, seen)

            # Handle page responses (contain containers with sets)
            page_data = data.get("page", {})
            for container in page_data.get("containers", []):
                self._extract_from_set(container.get("set", {}), history, seen)

        logger.info("[%s] Extracted %d titles from API", self.name, len(history))

        # Also grab watchlist via DOM (simple fallback)
        page.goto(self.history_url, wait_until="domcontentloaded")
        page.wait_for_timeout(10000)

        wl_cards = page.locator('a[aria-label][href*="/series/"], a[aria-label][href*="/movies/"], a[aria-label][href*="/play/"]')
        for i in range(wl_cards.count()):
            label = wl_cards.nth(i).get_attribute("aria-label") or ""
            title = re.sub(r"\s*\d+\s+(?:hours?\s+)?\d*\s*minutes?\s+remaining.*", "", label).strip()
            if title and len(title) > 2 and title not in seen:
                history.append({"title": title, "date": None})
                seen.add(title)

        return history

    def _extract_from_set(self, set_data: dict, history: list, seen: set) -> None:
        """Extract titles from a Disney+ API set response."""
        set_name = set_data.get("visuals", {}).get("name", "")
        items = set_data.get("items", [])

        # Check if this is a watch history set
        is_history = set_name.lower() in HISTORY_SET_NAMES
        byw_match = BECAUSE_YOU_WATCHED_PATTERN.match(set_name)

        if byw_match:
            # "Because You Watched X" — X is something you watched
            watched_title = byw_match.group(1).strip()
            if watched_title and watched_title not in seen:
                history.append({"title": watched_title, "date": None})
                seen.add(watched_title)

        if is_history:
            # Extract all titles from Continue Watching / Pick Up Where You Left Off
            for item in items:
                title = item.get("visuals", {}).get("title", "")
                if title and title not in seen:
                    history.append({"title": title, "date": None})
                    seen.add(title)
