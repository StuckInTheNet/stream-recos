"""Fetch verification codes via file-based delivery.

The scraper writes a request, then polls for a code file.
An external process (or the user manually) writes the code to the file.
"""

import logging
import time
from pathlib import Path

logger = logging.getLogger("streamrecos")

CODE_DIR = Path(__file__).parent / "history"


def wait_for_code(service: str, timeout: int = 120) -> str | None:
    """Wait for a verification code to appear in a file.

    Polls CODE_DIR/{service}_code.txt for up to `timeout` seconds.
    An external process should write just the digits to that file.
    Falls back to manual terminal input if stdin is available.
    """
    CODE_DIR.mkdir(exist_ok=True)
    code_file = CODE_DIR / f"{service}_code.txt"
    request_file = CODE_DIR / f"{service}_needs_code.txt"

    # Clean up stale files
    if code_file.exists():
        code_file.unlink()

    # Signal that we need a code
    request_file.write_text(f"{service} needs verification code")
    logger.info("[%s] Waiting for verification code...", service)
    logger.info("[%s] Write code to: %s", service, code_file)

    start = time.time()
    while time.time() - start < timeout:
        try:
            code = code_file.read_text().strip()
            if code:
                code_file.unlink(missing_ok=True)
                request_file.unlink(missing_ok=True)
                logger.info("[%s] Code received: %s", service, code)
                return code
        except FileNotFoundError:
            pass
        time.sleep(2)

    request_file.unlink(missing_ok=True)
    logger.warning("[%s] Timed out waiting for code", service)
    return None
