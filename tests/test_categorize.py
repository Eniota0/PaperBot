import pytest

from conftest import FakeLLM
from paperbot.categorize import categorize
from paperbot.llm import LLMError, LLMUnavailable


def cat(settings, paper, *responses):
    return categorize(paper, settings.categories, FakeLLM(list(responses)))


def test_category_exact(settings, paper):
    assert cat(settings, paper, {"category": "Agents", "secondary": "none"}) == ("Agents", None)


def test_category_normalised(settings, paper):  # Review Focus 3
    assert cat(settings, paper, {"category": " llms & reasoning ", "secondary": "none"})[0] == "LLMs & Reasoning"


def test_secondary_returned_and_normalised(settings, paper):
    assert cat(settings, paper, {"category": "Agents", "secondary": "robotics & embodied ai"}) == (
        "Agents", "Robotics & Embodied AI")


def test_secondary_same_as_primary_or_other_or_invalid_is_none(settings, paper):
    for sec in ("Agents", "Other", "Quantum", None):
        assert cat(settings, paper, {"category": "Agents", "secondary": sec}) == ("Agents", None)


def test_missing_secondary_ok(settings, paper):
    assert cat(settings, paper, {"category": "Agents"}) == ("Agents", None)


def test_category_retry_then_other(settings, paper):
    llm = FakeLLM([{"category": "Quantum"}, LLMError("bad")])
    assert categorize(paper, settings.categories, llm) == ("Other", None) and len(llm.prompts) == 2


def test_category_retry_succeeds(settings, paper):
    assert cat(settings, paper, {"nope": 1}, {"category": "Agents"}) == ("Agents", None)


def test_category_unavailable_propagates(settings, paper):
    with pytest.raises(LLMUnavailable):
        categorize(paper, settings.categories, FakeLLM([LLMUnavailable("down")]))


def test_prompt_contains_descriptions_and_paper(settings, paper):
    llm = FakeLLM([{"category": "Agents"}])
    categorize(paper.model_copy(update={"ai_keywords": ["kw1"]}), settings.categories, llm)
    p = llm.prompts[0]
    assert all(c.description in p for c in settings.categories)
    assert paper.title in p and paper.abstract in p and "kw1" in p and "secondary" in p


def test_tie_break_hints_in_example_config(settings):
    robotics = settings.category("Robotics & Embodied AI").description
    agents = settings.category("Agents").description
    assert "agent" in robotics.lower() and "robot" in agents.lower()
