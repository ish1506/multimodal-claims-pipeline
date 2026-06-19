import os
from pathlib import Path

from claim_review.env import load_dotenv


def test_load_dotenv_sets_missing_values_without_overriding(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
# comment
OPENAI_API_KEY="from-file"
OPENAI_VISION_MODEL=gpt-test
export EXTRA_VALUE='hello world'
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "from-shell")
    monkeypatch.delenv("OPENAI_VISION_MODEL", raising=False)
    monkeypatch.delenv("EXTRA_VALUE", raising=False)

    loaded = load_dotenv(env_file)

    assert os.environ["OPENAI_API_KEY"] == "from-shell"
    assert os.environ["OPENAI_VISION_MODEL"] == "gpt-test"
    assert os.environ["EXTRA_VALUE"] == "hello world"
    assert loaded == ["OPENAI_VISION_MODEL", "EXTRA_VALUE"]
