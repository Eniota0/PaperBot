from datetime import date

import pytest

from paperbot.models import Author, Paper
from paperbot.ranking import author_trust, paper_score, rank_day

D = date(2026, 11, 15)


def mk(i, votes, cat="Agents", users=()):
    return Paper(arxiv_id=f"p{i}", date=D, title=f"T{i}", upvotes=votes, category=cat,
                 authors=[Author(name=u or "anon", hf_user=u) for u in users])


def test_author_trust():
    assert author_trust([10, 50, 120, 49], 50, 5) == 2
    assert author_trust([60] * 9, 50, 5) == 5
    assert author_trust([], 50, 5) == 0


def test_paper_score():
    assert paper_score(100, 5, 0.05) == pytest.approx(125.0)
    assert paper_score(100, 0, 0.05) == 100


def test_trust_reorders_close_papers(settings):
    a, b = mk(1, 100, users=["x"]), mk(2, 90, users=["star", "x"])
    groups = rank_day([a, b], settings.categories, lambda u: 5 if u == "star" else 0, settings.ranking)
    ranked = groups[0].papers
    assert [r.paper.arxiv_id for r in ranked] == ["p2", "p1"]
    assert ranked[0].rank == 1 and ranked[0].trust == 5 and ranked[0].score == pytest.approx(112.5)
    assert ranked[1].trust == 0


def test_unlinked_authors_get_no_trust(settings):
    calls = []
    rank_day([mk(1, 10, users=[None])], settings.categories, lambda u: calls.append(u) or 3, settings.ranking)
    assert calls == []


def test_groups_ordered_by_total_and_empty_omitted(settings):
    papers = [mk(1, 10, "Agents"), mk(2, 15, "Agents"), mk(3, 30, "Computer Vision")]
    groups = rank_day(papers, settings.categories, lambda u: 0, settings.ranking)
    assert [g.category.name for g in groups] == ["Computer Vision", "Agents"]
    assert groups[1].total_upvotes == 25


def test_unknown_category_goes_to_other(settings):
    groups = rank_day([mk(1, 5, "Quantum"), mk(2, 5, None)], settings.categories, lambda u: 0, settings.ranking)
    assert [g.category.name for g in groups] == ["Other"] and len(groups[0].papers) == 2


def test_ties_broken_by_votes_then_id(settings):
    groups = rank_day([mk(2, 10), mk(1, 10)], settings.categories, lambda u: 0, settings.ranking)
    assert [r.paper.arxiv_id for r in groups[0].papers] == ["p1", "p2"]
