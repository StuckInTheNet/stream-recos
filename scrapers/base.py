import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser

logger = logging.getLogger("streamrecos")

HISTORY_DIR = Path(__file__).parent.parent / "history"
SESSIONS_DIR = Path(__file__).parent.parent / "sessions"

MAX_SESSION_AGE_DAYS = 30
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class BaseScraper(ABC):
    name: str = ""
    login_url: str = ""
    history_url: str = ""

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password

    @abstractmethod
    def login(self, page: Page) -> None:
        """Log into the streaming service."""

    @abstractmethod
    def scrape_history(self, page: Page) -> list[dict]:
        """Scrape viewing history. Returns list of {"title": str, "date": str | None}."""

    def handle_otp(self, page: Page, submit_selector: str = 'button:has-text("Continue"), button[type="submit"]') -> bool:
        """Detect an OTP/verification code page and handle it.

        Detects the "Check your email" page used by MyDisney (Hulu/Disney+)
        and similar services. Uses file-based code delivery for automation
        or falls back to terminal input.

        Returns True if OTP was handled, False if no OTP page was detected.
        """
        from email_code import wait_for_code

        # Check for OTP verification page (NOT the login error which says "check your email and password")
        page_text = page.text_content("body", timeout=3000) or ""
        page_lower = page_text.lower()

        # Reject false positives: login error pages
        if "couldn't log you in" in page_lower or "check your email and password" in page_lower:
            logger.error("[%s] Login failed -- wrong password", self.name)
            return False

        otp_indicators = ["check your email inbox", "one-time passcode", "enter the code", "enter it below", "6-digit code"]
        is_otp_page = any(indicator in page_lower for indicator in otp_indicators)

        if not is_otp_page:
            return False

        logger.info("[%s] OTP verification page detected", self.name)
        code = wait_for_code(self.name)

        if not code:
            logger.warning("[%s] No code provided, cannot continue", self.name)
            return False

        # Type the code digit by digit using keyboard (works with split OTP inputs)
        # Click on the page first to ensure focus
        page.keyboard.press("Tab")
        page.wait_for_timeout(500)
        for digit in code:
            page.keyboard.type(digit, delay=100)
        page.wait_for_timeout(1000)

        # Click Continue/Submit
        submit = page.locator(submit_selector)
        if submit.first.is_visible(timeout=2000):
            submit.first.click()
        page.wait_for_timeout(5000)

        return True

    def handle_2fa(self, page: Page, input_selector: str, submit_selector: str = 'button[type="submit"]') -> None:
        """Legacy 2FA handler for single-input code fields (e.g., Netflix)."""
        code_input = page.locator(input_selector)
        if code_input.is_visible(timeout=3000):
            from email_code import wait_for_code
            code = wait_for_code(self.name)
            if code:
                code_input.fill(code)
                page.click(submit_selector)
                page.wait_for_timeout(5000)

    def find_shelf_titles(self, page: Page, shelf_selector: str, keyword: str, card_selector: str) -> list[str]:
        """Scan shelves for one matching a keyword, return card titles from it."""
        titles = []
        shelves = page.locator(shelf_selector)
        count = shelves.count()
        for i in range(count):
            shelf = shelves.nth(i)
            heading = shelf.locator("h2, h3")
            if heading.count() == 0:
                continue
            text = heading.first.text_content(timeout=2000) or ""
            if keyword in text.lower():
                cards = shelf.locator(card_selector)
                for j in range(cards.count()):
                    card = cards.nth(j)
                    title = card.get_attribute("aria-label") or card.text_content(timeout=2000)
                    if title and title.strip():
                        titles.append(title.strip())
                break
        return titles

    def _is_session_valid(self, session_path: Path) -> bool:
        """Check if a saved session file exists and is not too old."""
        if not session_path.exists():
            return False
        age_days = (datetime.now() - datetime.fromtimestamp(session_path.stat().st_mtime)).days
        if age_days > MAX_SESSION_AGE_DAYS:
            logger.info("[%s] Session is %dd old (max %d), re-logging in", self.name, age_days, MAX_SESSION_AGE_DAYS)
            session_path.unlink()
            return False
        return True

    def run(self, headless: bool = True) -> list[dict]:
        """Launch browser, login, scrape, save, and return history."""
        logger.info("[%s] Launching browser...", self.name)
        session_path = SESSIONS_DIR / f"{self.name}.json"
        has_session = self._is_session_valid(session_path)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)

            if has_session:
                context = browser.new_context(
                    storage_state=str(session_path),
                    user_agent=USER_AGENT,
                )
                logger.info("[%s] Loaded saved session", self.name)
            else:
                context = browser.new_context(user_agent=USER_AGENT)

            page = context.new_page()

            if has_session:
                logger.info("[%s] Using saved session (skipping login)", self.name)
            else:
                logger.info("[%s] Logging in...", self.name)
                self.login(page)

                # Save full state for next time
                SESSIONS_DIR.mkdir(exist_ok=True)
                context.storage_state(path=str(session_path))
                logger.info("[%s] Saved session for reuse", self.name)

            logger.info("[%s] Scraping viewing history...", self.name)
            # Save debug screenshot
            debug_path = HISTORY_DIR / f"{self.name}_debug.png"
            HISTORY_DIR.mkdir(exist_ok=True)
            page.screenshot(path=str(debug_path))
            logger.debug("[%s] Debug screenshot: %s", self.name, debug_path)

            history = self.scrape_history(page)

            browser.close()

        logger.info("[%s] Found %d titles", self.name, len(history))
        self._save(history)
        return history

    def _save(self, history: list[dict]) -> None:
        HISTORY_DIR.mkdir(exist_ok=True)
        path = HISTORY_DIR / f"{self.name}.json"

        # Merge with existing history to avoid losing titles from previous scrapes
        existing_titles = set()
        if path.exists():
            try:
                existing = json.loads(path.read_text())
                existing_history = existing.get("history", [])
                existing_titles = {item["title"] for item in existing_history}
                # Keep existing entries that aren't in the new scrape
                new_titles = {item["title"] for item in history}
                for item in existing_history:
                    if item["title"] not in new_titles:
                        history.append(item)
            except (json.JSONDecodeError, KeyError):
                pass

        merged_count = len(history) - len(existing_titles - {item["title"] for item in history})
        data = {
            "service": self.name,
            "scraped_at": datetime.now().isoformat(),
            "count": len(history),
            "history": history,
        }
        path.write_text(json.dumps(data, indent=2))
        logger.info("[%s] Saved %d titles to %s", self.name, len(history), path)
