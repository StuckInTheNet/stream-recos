from playwright.sync_api import Page
from scrapers.base import BaseScraper


# API endpoint for Hulu home page data
HULU_HOME_API = "https://discover.hulu.com/content/v5/view_hubs/home?schema=3&limit=100"

# Component names that indicate watch history
HISTORY_COMPONENTS = {"continue watching", "keep watching"}


class HuluScraper(BaseScraper):
    name = "hulu"
    login_url = "https://auth.hulu.com/web/login"
    history_url = "https://www.hulu.com/my-stuff"

    def login(self, page: Page) -> None:
        page.goto(self.login_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.fill("#email-field", self.email)
        page.click('button[type="submit"]')
        page.wait_for_timeout(3000)
        page.fill('input[type="password"]', self.password)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)
        self.handle_otp(page)
        try:
            page.locator('[data-testid="profile-avatar"], [class*="profile"]').first.click(timeout=5000)
            page.wait_for_timeout(3000)
        except Exception:
            pass

    def scrape_history(self, page: Page) -> list[dict]:
        history = []
        seen = set()

        # Navigate to Hulu first to establish cookie context
        page.goto("https://www.hulu.com/hub/home", wait_until="domcontentloaded")
        page.wait_for_timeout(10000)

        # Fetch home API directly from browser context (bypasses service worker cache)
        data = page.evaluate(
            """async (url) => {
                const resp = await fetch(url, { credentials: 'include' });
                return await resp.json();
            }""",
            HULU_HOME_API,
        )

        if not data or "components" not in data:
            print(f"[{self.name}] API fetch failed, falling back to DOM scraping", flush=True)
            return self._scrape_dom(page)

        components = data["components"]
        print(f"[{self.name}] API returned {len(components)} components", flush=True)

        for comp in components:
            name = (comp.get("name") or "").lower()

            if name in HISTORY_COMPONENTS:
                items = comp.get("items", [])
                for item in items:
                    mi = item.get("metrics_info", {})
                    title = mi.get("target_name", item.get("name", ""))
                    if title and title not in seen:
                        history.append({"title": title, "date": None})
                        seen.add(title)

        return history

    def _scrape_dom(self, page: Page) -> list[dict]:
        """Fallback DOM scraping if API fetch fails."""
        history = []
        seen = set()

        cards = page.locator('a[href*="/series/"], a[href*="/movie/"], [class*="card"]')
        for i in range(cards.count()):
            title = cards.nth(i).get_attribute("aria-label") or cards.nth(i).text_content(timeout=2000)
            if title and title.strip() not in seen:
                history.append({"title": title.strip(), "date": None})
                seen.add(title.strip())

        return history
