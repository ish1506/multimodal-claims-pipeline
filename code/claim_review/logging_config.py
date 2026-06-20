from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path


def default_log_file(repo_root: Path, command_name: str) -> Path:
    """Return a timestamped log path under the repository logs directory."""
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    return repo_root / "logs" / f"{command_name}_{stamp}.log"


def setup_logging(*, log_file: Path, level: str) -> Path:
    """Configure stderr and file logging for a CLI run."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(numeric_level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(numeric_level)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)

    root.addHandler(stream_handler)
    root.addHandler(file_handler)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return log_file
