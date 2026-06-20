from __future__ import annotations

import os
import shlex
from pathlib import Path


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    if "=" not in stripped:
        return None

    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
        return None

    raw_value = raw_value.strip()
    try:
        parts = shlex.split(raw_value, comments=True, posix=True)
    except ValueError:
        value = raw_value.strip("\"'")
    else:
        value = parts[0] if parts else ""
    return key, value


def load_dotenv(path: Path) -> list[str]:
    """Load missing environment variables from a dotenv-style file."""
    if not path.exists():
        return []

    loaded: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed is None:
            continue
        key, value = parsed
        if key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def load_repo_dotenv(repo_root: Path) -> list[str]:
    """Load the repository root .env unless disabled for tests."""
    if os.environ.get("CLAIM_REVIEW_DISABLE_DOTENV") == "1":
        return []
    return load_dotenv(repo_root / ".env")
