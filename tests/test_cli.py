from pathlib import Path
import os
import subprocess
import sys

import main as cli


def test_main_fails_fast_without_api_key(monkeypatch, tmp_path: Path, capsys):
    monkeypatch.setenv("CLAIM_REVIEW_DISABLE_DOTENV", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    output = tmp_path / "output.csv"
    log_file = tmp_path / "main.log"
    status = cli.main(["--input", "dataset/claims.csv", "--output", str(output), "--limit", "1", "--log-file", str(log_file)])
    captured = capsys.readouterr()
    assert status == 2
    assert "OPENAI_API_KEY is required" in captured.err
    assert "Logging to" in captured.err
    assert log_file.exists()
    assert not output.exists()


def test_evaluation_entrypoint_fails_fast_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env = os.environ.copy()
    env["CLAIM_REVIEW_DISABLE_DOTENV"] = "1"
    result = subprocess.run(
        [sys.executable, "code/evaluation/main.py"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2
    assert "OPENAI_API_KEY is required" in result.stderr
    assert "Logging to" in result.stderr
