import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from paperbot.hf_client import HFClient, HFUnavailable, parse_daily_papers

FIXTURE = Path(__file__).parent / "fixtures" / "daily_papers.json"
D = date(2026, 11, 10)
URL = "https://huggingface.co/api/daily_papers"


def test_parse_fixture():
    papers = parse_daily_papers(json.loads(FIXTURE.read_text(encoding="utf-8")), D)
    assert len(papers) == 3 and all(p.date == D for p in papers)
    p = papers[0]
    assert p.arxiv_id == "2611.00001" and p.upvotes == 142
    assert p.abstract.startswith("We study") and p.ai_keywords == ["test-time compute", "reasoning"]
    assert [a.hf_user for a in p.authors] == ["alicem", None]


def test_parse_tolerates_missing_fields():  # Review Focus 1
    p = parse_daily_papers([{"paper": {"id": "2411.00001", "title": "T", "summary": None,
                                        "authors": [{"name": "A"}], "upvotes": 4}}], D)[0]
    assert p.abstract == "" and p.authors[0].hf_user is None and p.ai_keywords == []
    assert p.ai_summary is None


def test_parse_skips_items_without_id():
    assert parse_daily_papers([{"paper": {"title": "no id"}}, {"foo": 1}], D) == []


@respx.mock
def test_fetch_retries_then_fails():
    route = respx.get(URL).mock(return_value=httpx.Response(503))
    with pytest.raises(HFUnavailable):
        HFClient(backoff_s=0).fetch_daily(D)
    assert route.call_count == 3


@respx.mock
def test_fetch_ok():
    route = respx.get(URL).mock(return_value=httpx.Response(200, json=json.loads(FIXTURE.read_text(encoding="utf-8"))))
    papers = HFClient(backoff_s=0).fetch_daily(D)
    assert len(papers) == 3
    q = route.calls.last.request.url.params
    assert q["date"] == "2026-11-10" and q["limit"] == "100"


@respx.mock
def test_fetch_empty_day():
    respx.get(URL).mock(return_value=httpx.Response(200, json=[]))
    assert HFClient(backoff_s=0).fetch_daily(D) == []


@respx.mock
def test_404_is_empty_day():  # review I2
    respx.get(URL).mock(return_value=httpx.Response(404))
    assert HFClient(backoff_s=0).fetch_daily(D) == []


@respx.mock
def test_client_error_not_retried():  # review I2
    route = respx.get(URL).mock(return_value=httpx.Response(400))
    with pytest.raises(HFUnavailable):
        HFClient(backoff_s=0).fetch_daily(D)
    assert route.call_count == 1
