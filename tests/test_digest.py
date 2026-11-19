from datetime import date

from paperbot.config import Category
from paperbot.digest import EmbedSpec, build_digest, chunk_embeds
from paperbot.models import CategoryGroup, Paper, RankedPaper

D = date(2026, 11, 15)
CAT = Category(name="LLMs & Reasoning", emoji="🧠", description="d")


def group_of(n, title="Title", trust=0):
    rps = [RankedPaper(paper=Paper(arxiv_id=f"2611.{i:05d}", date=D, title=title, upvotes=100 - i),
                       rank=i, score=1.0, trust=trust) for i in range(1, n + 1)]
    return CategoryGroup(category=CAT, papers=rps, total_upvotes=sum(r.paper.upvotes for r in rps))


def test_digest_header_and_lines_and_star():
    d = build_digest(D, [group_of(1, trust=2)], 10)
    assert d.header == "📚 HF Papers — 2026-11-15 · 1 papers"
    assert d.embeds[0].title == "🧠 LLMs & Reasoning (1)"
    assert d.embeds[0].description == "1. ▲99 [Title](https://huggingface.co/papers/2611.00001) ⭐"


def test_no_star_without_trust():
    assert "⭐" not in build_digest(D, [group_of(1)], 10).embeds[0].description


def test_top_n_and_more_line():
    lines = build_digest(D, [group_of(13)], 10).embeds[0].description.split("\n")
    assert len(lines) == 11 and lines[-1] == "+3 more in PDF"


def test_long_title_truncated():
    line = build_digest(D, [group_of(1, title="x" * 200)], 10).embeds[0].description
    assert "[" + "x" * 89 + "…]" in line


def test_brackets_in_title_do_not_break_links():
    line = build_digest(D, [group_of(1, title="[RL] Agents")], 10).embeds[0].description
    assert "[(RL) Agents](" in line


def test_limits_with_huge_day():  # Review Focus 4
    d = build_digest(D, [group_of(40, title="x" * 300)], 40)
    assert all(len(e.description) <= 4096 and len(e.title) <= 256 for e in d.embeds)


def test_chunk_embeds_respects_count_and_chars():
    embeds = [EmbedSpec(title="t", description="y" * 1000) for _ in range(25)]
    chunks = chunk_embeds(embeds)
    assert sum(len(c) for c in chunks) == 25
    assert all(len(c) <= 10 and sum(len(e.title) + len(e.description) for e in c) <= 6000 for c in chunks)


from test_tiers import TIERS


def votes_group(*votes):
    rps = [RankedPaper(paper=Paper(arxiv_id=f"2611.{i:05d}", date=D, title=f"T{i}", upvotes=v),
                       rank=i, score=v, trust=0) for i, v in enumerate(votes, 1)]
    return CategoryGroup(category=CAT, papers=rps, total_upvotes=sum(votes))


def test_tier_badge_and_bold_title():
    lines = build_digest(D, [votes_group(231, 120, 60, 10)], 10, TIERS).embeds[0].description.split("\n")
    assert lines[0] == "1. ▲231 💎 **[T1](https://huggingface.co/papers/2611.00001)**"
    assert lines[1].startswith("2. ▲120 🥇 **[T2]")
    assert lines[2].startswith("3. ▲60 🥉 **[T3]")
    assert lines[3] == "4. ▲10 [T4](https://huggingface.co/papers/2611.00004)"


def test_header_counts_tiers_highest_first():
    d = build_digest(D, [votes_group(231, 120, 110, 60, 10)], 10, TIERS)
    assert d.header == "📚 HF Papers — 2026-11-15 · 5 papers · 💎 1 · 🥇 2 · 🥉 1"


def test_no_tiers_keeps_plain_output():
    d = build_digest(D, [votes_group(231)], 10)
    assert d.header.endswith("1 papers") and "**" not in d.embeds[0].description
