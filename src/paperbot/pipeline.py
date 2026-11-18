"""One-date pipeline: fetch -> categorise -> enrich -> rank. Idempotent."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from paperbot.categorize import categorize
from paperbot.config import Settings
from paperbot.enrich import enrich
from paperbot.hf_client import HFClient, HFUnavailable
from paperbot.llm import LLMProvider
from paperbot.models import CategoryGroup
from paperbot.ranking import author_trust, rank_day
from paperbot.storage import Storage

log = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, settings: Settings, storage: Storage, hf: HFClient, llm: LLMProvider):
        self.settings = settings
        self.storage = storage
        self.hf = hf
        self.llm = llm

    def run(self, d: date, force: bool = False) -> list[CategoryGroup]:
        """Process date d. HFUnavailable / LLMUnavailable propagate; d is then not marked done."""
        fetched = self.hf.fetch_daily(d)
        self.storage.upsert_papers(fetched)
        papers = self.storage.papers_for_date(d)
        log.info("%s: %d papers", d, len(papers))

        todo = [p for p in papers if force or p.category is None]
        for i, p in enumerate(todo, 1):
            self.storage.set_category(p.arxiv_id, categorize(p, self.settings.categories, self.llm))
            log.info("%s: categorised %d/%d", d, i, len(todo))

        todo = [p for p in papers if force or p.enrichment is None]
        for i, p in enumerate(todo, 1):
            self.storage.set_enrichment(p.arxiv_id, enrich(p, self.llm))
            log.info("%s: enriched %d/%d", d, i, len(todo))

        self.storage.mark_date_done(d, len(papers))
        return self.ranked(d)

    def ranked(self, d: date) -> list[CategoryGroup]:
        r = self.settings.ranking

        def trust_of(user: str) -> int:
            return author_trust(self.storage.author_upvotes_before(user, d), r.trust_vote_threshold, r.trust_cap)

        return rank_day(self.storage.papers_for_date(d), self.settings.categories, trust_of, r)

    def backfill(self, days: int, today: date) -> int:
        """Fetch metadata (no LLM) for the `days` dates before the current target date."""
        target = today - timedelta(days=self.settings.delay_days)
        stored = 0
        for k in range(days, 0, -1):
            d = target - timedelta(days=k)
            try:
                papers = self.hf.fetch_daily(d)
            except HFUnavailable as e:
                log.warning("backfill: skipping %s (%s)", d, e)
                continue
            self.storage.upsert_papers(papers)
            stored += len(papers)
        log.info("backfill: stored %d papers over %d days", stored, days)
        return stored


def build_pipeline(settings: Settings) -> Pipeline:
    from paperbot.llm.ollama import OllamaProvider

    o = settings.ollama
    return Pipeline(
        settings,
        Storage(settings.db_path),
        HFClient(),
        OllamaProvider(o.url, o.model, o.timeout_s),
    )
