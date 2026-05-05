import os
from pathlib import Path
from urllib.parse import urlparse


PROXY_ENV_KEYS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]


def load_local_env(env_path: str | None = None) -> None:
    """Load simple KEY=VALUE pairs from a local env file without extra deps."""
    target_path = Path(env_path) if env_path else Path(__file__).resolve().parent / ".env.local"
    if not target_path.exists():
        return

    for raw_line in target_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _is_blocking_loopback_proxy(value: str) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    port = parsed.port
    return host in {"127.0.0.1", "localhost", "::1"} and port == 9


def clear_invalid_proxy_env() -> None:
    for key in PROXY_ENV_KEYS:
        value = os.getenv(key)
        if value and _is_blocking_loopback_proxy(value):
            os.environ.pop(key, None)
