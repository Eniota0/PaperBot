"""Assign a main category (and optionally a secondary one) to a paper using the LLM."""
from __future__ import annotations

import logging
from importlib.resources import files
from string import Template

from paperbot.config import Category
from paperbot.llm import LLMError, LLMProvider, LLMUnavailable
from paperbot.models import Paper

log = logging.getLogger(__name__)
_PROMPT = Template(files("paperbot.prompts").joinpath("categorize.txt").read_text(encoding="utf-8"))
NONE = "none"


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def categorize(paper: Paper, categories: list[Category], llm: LLMProvider) -> tuple[str, str | None]:
    """Return (main category, secondary category or None). Falls back to ("Other", None)."""
    names = [c.name for c in categories]
    by_norm = {_norm(n): n for n in names}
    prompt = _PROMPT.substitute(
        categories="\n".join(f"- {c.name}: {c.description}" for c in categories),
        title=paper.title,
        keywords=", ".join(paper.ai_keywords) or "(none)",
        abstract=paper.abstract or "(no abstract)",
    )
    schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": names},
            "secondary": {"type": "string", "enum": names + [NONE]},
        },
        "required": ["category", "secondary"],
    }
    for _ in range(2):
        try:
            data = llm.complete_json(prompt, schema)
        except LLMUnavailable:
            raise
        except LLMError as e:
            log.warning("categorize %s: %s", paper.arxiv_id, e)
            continue
        answer = data.get("category")
        if not (isinstance(answer, str) and _norm(answer) in by_norm):
            log.warning("categorize %s: invalid answer %r", paper.arxiv_id, answer)
            continue
        primary = by_norm[_norm(answer)]
        sec = data.get("secondary")
        secondary = by_norm.get(_norm(sec)) if isinstance(sec, str) else None
        if secondary in (primary, "Other"):
            secondary = None
        return primary, secondary
    return "Other", None
