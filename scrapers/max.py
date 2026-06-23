from playwright.sync_api import Page
from scrapers.base import BaseScraper


class MaxScraper(BaseScraper):
    name = "max"
    login_url = "https://auth.hbomax.com/login?flow=login"
    history_url = "https://play.max.com/my-list"

    def login(self, page: Page) -> None:
        page.goto(self.login_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Dismiss cookie/legal consent
        agree = page.locator('button:has-text("Agree")')
        if agree.is_visible(timeout=3000):
            agree.click()
            page.wait_for_timeout(1000)

        # Two-step: email first
        page.fill("#sign-in-phoneEmail-input", self.email)
        page.click('button[type="submit"]')
        page.wait_for_timeout(3000)

        # Password step
        page.fill("#sign-in-password-password-input", self.password)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)

        # 2FA check
        self.handle_2fa(page, 'input[type="tel"], input[name*="code"], input[name*="otp"]')

        # Profile picker
        try:
            page.locator('[class*="profile"], [data-testid*="profile"]').first.click(timeout=5000)
            page.wait_for_timeout(3000)
        except Exception:
            pass

    def scrape_history(self, page: Page) -> list[dict]:
        page.goto("https://play.max.com", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        history = []

        # "Continue Watching" shelf
        shelves = page.locator('[class*="shelf"], [class*="rail"], section')
        for i in range(shelves.count()):
            shelf = shelves.nth(i)
            heading = shelf.locator("h2, h3, [class*='heading']").first.text_content() or ""
            if "continue watching" in heading.lower():
                cards = shelf.locator('[class*="card"], a[href*="/video/"], a[href*="/show/"]')
                for j in range(cards.count()):
                    title = cards.nth(j).get_attribute("aria-label") or cards.nth(j).text_content()
                    if title:
                        history.append({"title": title.strip(), "date": None})
                break

        # "My List"
        page.goto(self.history_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        cards = page.locator('[class*="card"], a[href*="/video/"], a[href*="/show/"]')
        seen = {h["title"] for h in history}
        for i in range(cards.count()):
            title = cards.nth(i).get_attribute("aria-label") or cards.nth(i).text_content()
            if title and title.strip() not in seen:
                history.append({"title": title.strip(), "date": None})
                seen.add(title.strip())

        return history
