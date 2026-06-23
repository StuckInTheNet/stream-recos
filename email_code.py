"""Fetch verification codes via file-based delivery.

The scraper writes a request, then polls for a code file.
An external process (Claude Code with Gmail MCP, or the user manually)
writes the code to the file.
"""

import time
from pathlib import Path

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
    print(f"[{service}] Waiting for verification code...", flush=True)
    print(f"[{service}] Write code to: {code_file}", flush=True)

    start = time.time()
    while time.time() - start < timeout:
        try:
            code = code_file.read_text().strip()
            if code:
                code_file.unlink(missing_ok=True)
                request_file.unlink(missing_ok=True)
                print(f"[{service}] Code received: {code}", flush=True)
                return code
        except FileNotFoundError:
            pass
        time.sleep(2)

    request_file.unlink(missing_ok=True)
    print(f"[{service}] Timed out waiting for code", flush=True)
    return None
