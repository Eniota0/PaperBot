from datetime import time
from pathlib import Path

import pytest
import yaml

from paperbot.config import load_settings

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.yaml"


def test_example_config_loads(tmp_path):
    s = load_settings(EXAMPLE, tmp_path / "missing.env")
    assert s.delay_days == 3 and s.schedule_utc == time(8, 0)
    assert s.ranking.trust_weight == 0.05 and s.top_n == 10
    assert s.catchup_max_days == 7 and s.backfill_days == 90
    assert s.ollama.model == "qwen3.5:4b" and s.ollama.think is False
    assert [c.name for c in s.categories][-1] == "Other" and len(s.categories) == 12
    assert s.db_path == Path("data") / "paperbot.db"


def test_token_from_env(tmp_path, monkeypatch):
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    (tmp_path / ".env").write_text("DISCORD_TOKEN=abc\n")
    assert load_settings(EXAMPLE, tmp_path / ".env").discord_token == "abc"


def test_categories_must_include_other(tmp_path):
    data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    data["categories"] = [c for c in data["categories"] if c["name"] != "Other"]
    cfg = tmp_path / "c.yaml"
    cfg.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Other"):
        load_settings(cfg, tmp_path / "x.env")


def test_category_lookup(tmp_path):
    s = load_settings(EXAMPLE, tmp_path / "x.env")
    assert s.category("Agents").emoji == "🤖"
