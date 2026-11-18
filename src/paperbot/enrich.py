"""Generate summary / use cases / what's new for a paper using the LLM."""
from __future__ import annotations

import logging
from importlib.resources import files
from string import Template

from paperbot.llm import LLMError, LLMProvider, LLMUnavailable
from paperbot.models import Enrichment, Paper

log = logging.getLogger(__name__)
_PROMPT = Template(files("paperbot.prompts").joinpath("enrich.txt").read_text(encoding="utf-8"))
_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "use_cases": {"type": "array", "items": {"type": "string"}},
        "whats_new": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "use_cases", "whats_new"],
}


def _clean_list(v, limit: int) -> list[str]:
    if not isinstance(v, list):
        return []
    return [s.strip() for s in v if isinstance(s, str) and s.strip()][:limit]


def _validate(data: dict) -> Enrichment | None:
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return None
    return Enrichment(
        summary=summary.strip(),
        use_cases=_clean_list(data.get("use_cases"), 4),
        whats_new=_clean_list(data.get("whats_new"), 3),
    )


def enrich(paper: Paper, llm: LLMProvider) -> Enrichment:
    prompt = _PROMPT.substitute(
        title=paper.title,
        ai_summary=paper.ai_summary or "",
        abstract=paper.abstract or "(no abstract)",
    )
    for _ in range(2):
        try:
            result = _validate(llm.complete_json(prompt, _SCHEMA))
        except LLMUnavailable:
            raise
        except LLMError as e:
            log.warning("enrich %s: %s", paper.arxiv_id, e)
            continue
        if result:
            return result
        log.warning("enrich %s: invalid answer", paper.arxiv_id)
    return Enrichment(summary=paper.abstract, use_cases=[], whats_new=[], ok=False)
