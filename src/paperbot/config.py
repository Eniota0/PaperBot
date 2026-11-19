"""Settings loading (config.yaml + .env) and logging setup."""
from __future__ import annotations

import logging
import os
from datetime import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, field_validator, model_validator


class Category(BaseModel):
    name: str
    emoji: str
    description: str


class Tier(BaseModel):
    """Vote badge, e.g. Gold for 100+ upvotes. Display only; does not affect ranking."""
    name: str
    emoji: str
    min_upvotes: int
    color: str = "#888888"  # hex, used in the PDF

    @property
    def rgb(self) -> tuple[int, int, int]:
        h = self.color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


class RankingSettings(BaseModel):
    trust_vote_threshold: int = 50
    trust_cap: int = 5
    trust_weight: float = 0.05


class OllamaSettings(BaseModel):
    url: str = "http://localhost:11434"
    model: str = "qwen3.5:4b"
    timeout_s: float = 180
    think: bool | None = False  # False disables "thinking" on Qwen3-style models; None = model default


class Settings(BaseModel):
    discord_token: str | None = None
    schedule_utc: time = time(8, 0)
    delay_days: int = 3
    catchup_max_days: int = 7
    backfill_days: int = 90
    top_n: int = 10
    min_upvotes: int = 10
    default_channel_id: int | None = None
    data_dir: Path = Path("data")
    ranking: RankingSettings = RankingSettings()
    ollama: OllamaSettings = OllamaSettings()
    categories: list[Category]
    tiers: list[Tier] = []

    @field_validator("schedule_utc", mode="before")
    @classmethod
    def _parse_time(cls, v):
        if isinstance(v, str):
            return time.fromisoformat(v)
        if isinstance(v, int):  # YAML may read 08:00 as sexagesimal minutes
            return time(v // 60, v % 60)
        return v

    @model_validator(mode="after")
    def _require_other(self):
        if not any(c.name == "Other" for c in self.categories):
            raise ValueError('categories must include a category named "Other"')
        return self

    @property
    def db_path(self) -> Path:
        return self.data_dir / "paperbot.db"

    @property
    def pdf_dir(self) -> Path:
        return self.data_dir / "pdf"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    def category(self, name: str) -> Category:
        for c in self.categories:
            if c.name == name:
                return c
        raise KeyError(name)


def load_settings(
    config_path: Path = Path("config.yaml"), env_path: Path = Path(".env")
) -> Settings:
    if Path(env_path).exists():
        load_dotenv(env_path, override=False)
    data = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    data["discord_token"] = os.environ.get("DISCORD_TOKEN") or None
    return Settings(**data)


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if any(getattr(h, "_paperbot", False) for h in root.handlers):
        return
    console = logging.StreamHandler()
    file = RotatingFileHandler(
        log_dir / "paperbot.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    for h in (console, file):
        h.setFormatter(fmt)
        h._paperbot = True  # type: ignore[attr-defined]
        root.addHandler(h)
