import logging
from pathlib import Path

from claim_review.logging_config import setup_logging


def test_setup_logging_writes_stream_and_file(tmp_path: Path, capsys):
    log_file = tmp_path / "logs" / "run.log"
    setup_logging(log_file=log_file, level="INFO")
    logging.getLogger("claim_review.test").info("hello log")
    captured = capsys.readouterr()
    assert "hello log" in captured.err
    assert "hello log" in log_file.read_text(encoding="utf-8")
