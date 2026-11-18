"""Pure formatting of the daily digest (no Discord dependency)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from paperbot.models import CategoryGroup, RankedPaper

TITLE_MAX = 90
EMBED_TITLE_MAX = 256
EMBED_DESC_MAX = 4096


@dataclass
class EmbedSpec:
    title: str
    description: str


@dataclass
class Digest:
    header: str
    embeds: list[EmbedSpec]


def _short(title: str) -> str:
    t = " ".join(title.split()).replace("[", "(").replace("]", ")")
    return t if len(t) <= TITLE_MAX else t[: TITLE_MAX - 1] + "…"


def _line(rp: RankedPaper) -> str:
    star = " ⭐" if rp.trust else ""
    return f"{rp.rank}. ▲{rp.paper.upvotes} [{_short(rp.paper.title)}]({rp.paper.hf_url}){star}"


def _description(group: CategoryGroup, top_n: int) -> str:
    lines = [_line(rp) for rp in group.papers[:top_n]]
    while True:
        k = len(group.papers) - len(lines)
        text = "\n".join(lines + ([f"+{k} more in PDF"] if k else []))
        if len(text) <= EMBED_DESC_MAX or not lines:
            return text
        lines.pop()


def build_digest(d: date, groups: list[CategoryGroup], top_n: int) -> Digest:
    n = sum(len(g.papers) for g in groups)
    embeds = [
        EmbedSpec(
            title=f"{g.category.emoji} {g.category.name} ({len(g.papers)})"[:EMBED_TITLE_MAX],
            description=_description(g, top_n),
        )
        for g in groups
    ]
    return Digest(header=f"📚 HF Papers — {d:%Y-%m-%d} · {n} papers", embeds=embeds)


def chunk_embeds(embeds: list[EmbedSpec], max_count: int = 10, max_chars: int = 6000) -> list[list[EmbedSpec]]:
    chunks: list[list[EmbedSpec]] = []
    cur: list[EmbedSpec] = []
    size = 0
    for e in embeds:
        n = len(e.title) + len(e.description)
        if cur and (len(cur) >= max_count or size + n > max_chars):
            chunks.append(cur)
            cur, size = [], 0
        cur.append(e)
        size += n
    if cur:
        chunks.append(cur)
    return chunks
