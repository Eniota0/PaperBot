import pytest

from conftest import FakeLLM
from paperbot.categorize import categorize
from paperbot.llm import LLMError, LLMUnavailable


def test_category_exact(settings, paper):
    assert categorize(paper, settings.categories, FakeLLM([{"category": "Agents"}])) == "Agents"


def test_category_normalised(settings, paper):  # Review Focus 3
    assert categorize(paper, settings.categories, FakeLLM([{"category": " llms & reasoning "}])) == "LLMs & Reasoning"


def test_category_retry_then_other(settings, paper):
    llm = FakeLLM([{"category": "Quantum"}, LLMError("bad")])
    assert categorize(paper, settings.categories, llm) == "Other" and len(llm.prompts) == 2


def test_category_retry_succeeds(settings, paper):
    llm = FakeLLM([{"nope": 1}, {"category": "Agents"}])
    assert categorize(paper, settings.categories, llm) == "Agents"


def test_category_unavailable_propagates(settings, paper):
    with pytest.raises(LLMUnavailable):
        categorize(paper, settings.categories, FakeLLM([LLMUnavailable("down")]))


def test_prompt_contains_descriptions_and_paper(settings, paper):
    llm = FakeLLM([{"category": "Agents"}])
    categorize(paper.model_copy(update={"ai_keywords": ["kw1"]}), settings.categories, llm)
    p = llm.prompts[0]
    assert all(c.description in p for c in settings.categories)
    assert paper.title in p and paper.abstract in p and "kw1" in p
