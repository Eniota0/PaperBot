from datetime import date, timedelta

import pytest

from conftest import FakeLLM
from paperbot.hf_client import HFUnavailable
from paperbot.llm import LLMUnavailable
from paperbot.models import Author, Paper
from paperbot.pipeline import Pipeline

D = date(2026, 11, 15)


def schema_responder(prompt, schema):
    if "category" in schema["properties"]:
        return {"category": "Agents"}
    return {"summary": "S.", "use_cases": ["u"], "whats_new": ["n"]}


class FakeHF:
    def __init__(self, by_date=None, fail_dates=()):
        self.by_date = by_date or {}
        self.fail_dates = set(fail_dates)
        self.calls = []

    def fetch_daily(self, d):
        self.calls.append(d)
        if d in self.fail_dates:
            raise HFUnavailable("down")
        return [p.model_copy() for p in self.by_date.get(d, [])]


def mk(i, d=D, votes=10, user="alicem"):
    return Paper(arxiv_id=f"p{i}", date=d, title=f"T{i}", abstract="A", upvotes=votes,
                 authors=[Author(name="Alice", hf_user=user)])


def make(settings, store, hf, llm):
    return Pipeline(settings, store, hf, llm)


def test_run_categorises_enriches_and_marks_done(settings, store):
    llm = FakeLLM(responder=schema_responder)
    groups = make(settings, store, FakeHF({D: [mk(1), mk(2)]}), llm).run(D)
    assert store.is_date_done(D) and len(llm.prompts) == 4
    assert [g.category.name for g in groups] == ["Agents"] and len(groups[0].papers) == 2
    assert all(p.enrichment and p.enrichment.ok for p in store.papers_for_date(D))


def test_rerun_does_not_call_llm_again(settings, store):
    llm = FakeLLM(responder=schema_responder)
    hf = FakeHF({D: [mk(1)]})
    pipe = make(settings, store, hf, llm)
    pipe.run(D)
    hf.by_date[D] = [mk(1, votes=77)]
    pipe.run(D)
    assert len(llm.prompts) == 2 and store.papers_for_date(D)[0].upvotes == 77


def test_force_recomputes(settings, store):
    llm = FakeLLM(responder=schema_responder)
    pipe = make(settings, store, FakeHF({D: [mk(1)]}), llm)
    pipe.run(D)
    pipe.run(D, force=True)
    assert len(llm.prompts) == 4


def test_llm_down_does_not_mark_done(settings, store):
    pipe = make(settings, store, FakeHF({D: [mk(1)]}), FakeLLM([LLMUnavailable("down")]))
    with pytest.raises(LLMUnavailable):
        pipe.run(D)
    assert not store.is_date_done(D)


def test_hf_down_does_not_mark_done(settings, store):
    with pytest.raises(HFUnavailable):
        make(settings, store, FakeHF(fail_dates=[D]), FakeLLM()).run(D)
    assert not store.is_date_done(D)


def test_empty_day_marked_done(settings, store):
    assert make(settings, store, FakeHF(), FakeLLM()).run(D) == []
    assert store.is_date_done(D)


def test_trust_uses_only_earlier_dates(settings, store):
    later = mk(9, d=D + timedelta(days=1), votes=200, user="star")
    store.upsert_papers([later])
    pipe = make(settings, store, FakeHF({D: [mk(1, user="star")]}), FakeLLM(responder=schema_responder))
    assert pipe.run(D)[0].papers[0].trust == 0
    earlier = mk(8, d=D - timedelta(days=1), votes=200, user="star")
    store.upsert_papers([earlier])
    assert pipe.ranked(D)[0].papers[0].trust == 1


def test_backfill_makes_no_llm_calls_and_covers_range(settings, store):
    today = date(2026, 11, 18)  # target = 11-15; backfill 3 days -> 11-12, 11-13, 11-14
    days = [date(2026, 11, 12), date(2026, 11, 13), date(2026, 11, 14)]
    hf = FakeHF({d: [mk(i, d=d)] for i, d in enumerate(days)}, fail_dates=[date(2026, 11, 13)])
    llm = FakeLLM()
    n = make(settings, store, hf, llm).backfill(3, today)
    assert sorted(hf.calls) == days and n == 2 and llm.prompts == []
    assert not store.is_date_done(date(2026, 11, 12))


def test_low_vote_papers_hidden_and_not_sent_to_llm(settings, store):
    s = settings.model_copy(update={"min_upvotes": 10})
    llm = FakeLLM(responder=schema_responder)
    groups = make(s, store, FakeHF({D: [mk(1, votes=3), mk(2, votes=30)]}), llm).run(D)
    assert [rp.paper.arxiv_id for g in groups for rp in g.papers] == ["p2"]
    assert len(llm.prompts) == 2 and all("T1" not in p for p in llm.prompts)
    assert len(store.papers_for_date(D)) == 2  # still stored for author history


def test_min_upvotes_threshold_inclusive(settings, store):
    s = settings.model_copy(update={"min_upvotes": 10})
    groups = make(s, store, FakeHF({D: [mk(1, votes=10)]}), FakeLLM(responder=schema_responder)).run(D)
    assert len(groups) == 1


def test_all_below_threshold_gives_empty_day(settings, store):
    s = settings.model_copy(update={"min_upvotes": 10})
    assert make(s, store, FakeHF({D: [mk(1, votes=2)]}), FakeLLM()).run(D) == []
    assert store.is_date_done(D)
