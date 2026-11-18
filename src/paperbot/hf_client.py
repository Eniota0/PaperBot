"""Client for the Hugging Face Daily Papers API."""
from __future__ import annotations

import logging
import time
from datetime import date

import httpx

from paperbot.models import Author, Paper

log = logging.getLogger(__name__)


class HFUnavailable(Exception):
    """Hugging Face could not be reached after retries."""


def _author(raw: dict) -> Author:
    user = raw.get("user")
    hf_user = user.get("user") if isinstance(user, dict) else None
    return Author(name=raw.get("name") or "Unknown", hf_user=hf_user or None)


def parse_daily_papers(items: list[dict], d: date) -> list[Paper]:
    papers: list[Paper] = []
    for item in items or []:
        raw = item.get("paper") if isinstance(item, dict) else None
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        papers.append(
            Paper(
                arxiv_id=str(raw["id"]),
                date=d,
                title=(raw.get("title") or item.get("title") or "").strip() or str(raw["id"]),
                abstract=(raw.get("summary") or "").strip(),
                authors=[_author(a) for a in raw.get("authors") or [] if isinstance(a, dict)],
                upvotes=int(raw.get("upvotes") or 0),
                ai_summary=raw.get("ai_summary") or None,
                ai_keywords=[str(k) for k in raw.get("ai_keywords") or []],
            )
        )
    return papers


class HFClient:
    def __init__(
        self,
        base_url: str = "https://huggingface.co",
        client: httpx.Client | None = None,
        retries: int = 3,
        backoff_s: float = 2.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=30, follow_redirects=True)
        self.retries = retries
        self.backoff_s = backoff_s

    def fetch_daily(self, d: date) -> list[Paper]:
        url = f"{self.base_url}/api/daily_papers"
        params = {"date": d.isoformat(), "limit": "100"}
        last_err: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = self.client.get(url, params=params)
                if resp.status_code >= 500 or resp.status_code == 429:
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                return parse_daily_papers(resp.json(), d)
            except (httpx.HTTPError, ValueError) as e:
                last_err = e
                log.warning("HF fetch for %s failed (attempt %d): %s", d, attempt + 1, e)
                if attempt < self.retries - 1:
                    time.sleep(self.backoff_s * (2**attempt))
        raise HFUnavailable(f"Could not fetch HF daily papers for {d}: {last_err}")
