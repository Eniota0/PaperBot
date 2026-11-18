"""Assign one configured category to a paper using the LLM."""
from __future__ import annotations

import logging
from importlib.resources import files
from string import Template

from paperbot.config import Category
from paperbot.llm import LLMError, LLMProvider, LLMUnavailable
from paperbot.models import Paper

log = logging.getLogger(__name__)
_PROMPT = Template(files("paperbot.prompts").joinpath("categorize.txt").read_text(encoding="utf-8"))


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def categorize(paper: Paper, categories: list[Category], llm: LLMProvider) -> str:
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
        "properties": {"category": {"type": "string", "enum": names}},
        "required": ["category"],
    }
    for _ in range(2):
        try:
            answer = llm.complete_json(prompt, schema).get("category")
        except LLMUnavailable:
            raise
        except LLMError as e:
            log.warning("categorize %s: %s", paper.arxiv_id, e)
            continue
        if isinstance(answer, str) and _norm(answer) in by_norm:
            return by_norm[_norm(answer)]
        log.warning("categorize %s: invalid answer %r", paper.arxiv_id, answer)
    return "Other"
