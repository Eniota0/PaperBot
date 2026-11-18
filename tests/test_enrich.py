import pytest

from conftest import FakeLLM
from paperbot.enrich import enrich
from paperbot.llm import LLMError, LLMUnavailable


def test_enrich_ok(paper):
    e = enrich(paper, FakeLLM([{"summary": "S.", "use_cases": ["a", "b"], "whats_new": ["n"]}]))
    assert e.ok and e.summary == "S." and e.use_cases == ["a", "b"] and e.whats_new == ["n"]


def test_enrich_fallback(paper):
    e = enrich(paper, FakeLLM([{"summary": ""}, LLMError("x")]))
    assert not e.ok and e.summary == paper.abstract and e.use_cases == [] and e.whats_new == []


def test_enrich_trims_lists(paper):
    e = enrich(paper, FakeLLM([{"summary": "S", "use_cases": list("abcdef"), "whats_new": list("vwxyz")}]))
    assert len(e.use_cases) == 4 and len(e.whats_new) == 3


def test_enrich_drops_non_string_items(paper):
    e = enrich(paper, FakeLLM([{"summary": "S", "use_cases": ["a", 3, "  "], "whats_new": ["n"]}]))
    assert e.use_cases == ["a"]


def test_enrich_unavailable_propagates(paper):
    with pytest.raises(LLMUnavailable):
        enrich(paper, FakeLLM([LLMUnavailable("down")]))


def test_enrich_prompt_has_paper_and_english(paper):
    llm = FakeLLM([{"summary": "S", "use_cases": [], "whats_new": []}])
    enrich(paper.model_copy(update={"ai_summary": "HF says hi"}), llm)
    assert paper.title in llm.prompts[0] and "HF says hi" in llm.prompts[0] and "English" in llm.prompts[0]
