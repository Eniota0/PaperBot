"""Ranking: author trust bonus and per-category ordering."""
from __future__ import annotations

from collections.abc import Callable

from paperbot.config import Category, RankingSettings, Tier
from paperbot.models import CategoryGroup, Paper, RankedPaper


def author_trust(previous_upvotes: list[int], threshold: int, cap: int) -> int:
    return min(sum(1 for v in previous_upvotes if v >= threshold), cap)


def paper_score(upvotes: int, trust: int, weight: float) -> float:
    return upvotes * (1 + weight * trust)


def rank_day(
    papers: list[Paper],
    categories: list[Category],
    trust_of: Callable[[str], int],
    cfg: RankingSettings,
) -> list[CategoryGroup]:
    known = {c.name for c in categories}
    buckets: dict[str, list[tuple[Paper, int, float]]] = {c.name: [] for c in categories}
    for p in papers:
        users = {a.hf_user for a in p.authors if a.hf_user}
        trust = max((trust_of(u) for u in users), default=0)
        cat = p.category if p.category in known else "Other"
        buckets[cat].append((p, trust, paper_score(p.upvotes, trust, cfg.trust_weight)))

    groups: list[CategoryGroup] = []
    for c in categories:
        items = sorted(buckets[c.name], key=lambda t: (-t[2], -t[0].upvotes, t[0].arxiv_id))
        if not items:
            continue
        groups.append(CategoryGroup(
            category=c,
            papers=[RankedPaper(paper=p, rank=i + 1, score=s, trust=t) for i, (p, t, s) in enumerate(items)],
            total_upvotes=sum(p.upvotes for p, _, _ in items),
        ))
    order = {c.name: i for i, c in enumerate(categories)}
    groups.sort(key=lambda g: (-g.total_upvotes, order[g.category.name]))
    return groups


def tier_for(upvotes: int, tiers: list[Tier]) -> Tier | None:
    reached = [t for t in tiers if upvotes >= t.min_upvotes]
    return max(reached, key=lambda t: t.min_upvotes) if reached else None
