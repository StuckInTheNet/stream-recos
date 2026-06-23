import time
from playwright.sync_api import Page
from scrapers.base import BaseScraper


class NetflixScraper(BaseScraper):
    name = "netflix"
    login_url = "https://www.netflix.com/login"
    history_url = "https://www.netflix.com/viewingactivity"

    def login(self, page: Page) -> None:
        page.goto(self.login_url, wait_until="networkidle")
        page.fill('input[name="userLoginId"]', self.email)
        page.fill('input[name="password"]', self.password)
        page.click('button[type="submit"]')

        # Wait for either browse page or 2FA challenge
        page.wait_for_timeout(5000)

        # Check if 2FA code input appeared
        self.handle_2fa(page, 'input[name="pin"]')

        # Wait for browse page after login / 2FA
        page.wait_for_url("**/browse**", timeout=30000)

        # If profile picker appears, select the first profile
        try:
            if page.locator(".profile-icon").first.is_visible(timeout=5000):
                page.locator(".profile-icon").first.click()
                page.wait_for_timeout(3000)
        except Exception:
            pass

    def scrape_history(self, page: Page) -> list[dict]:
        page.goto(self.history_url, wait_until="networkidle")

        # Netflix lazy-loads history -- click "Show More" until exhausted (max 50 pages)
        for i in range(50):
            show_more = page.get_by_role("button", name="Show More")
            if show_more.is_visible(timeout=2000):
                try:
                    print(f"[{self.name}] Loading history page {i + 1}/50...", end="\r", flush=True)
                    show_more.click(timeout=5000)
                    page.wait_for_timeout(1500)
                except Exception:
                    break
            else:
                break
        print(f"[{self.name}] Loaded {i + 1} pages of history        ", flush=True)

        rows = page.locator(".retableRow")
        count = rows.count()
        history = []

        for i in range(count):
            row = rows.nth(i)
            title_el = row.locator(".title a")
            date_el = row.locator(".date")

            title = title_el.text_content() if title_el.count() else None
            date = date_el.text_content() if date_el.count() else None

            if title:
                history.append({"title": title.strip(), "date": date.strip() if date else None})

        return history
