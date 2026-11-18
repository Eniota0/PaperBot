import os
import time
from datetime import date
from pathlib import Path

from paperbot.config import Category
from paperbot.models import Author, CategoryGroup, Enrichment, Paper, RankedPaper
from paperbot.pdf import get_or_render_pdf, paper_sections, pdf_path, render_category_pdf

D = date(2026, 11, 15)
CAT = Category(name="Multimodal / Vision-Language", emoji="🖼️", description="d")


def rp(enrichment=None, authors=("Alice",)):
    p = Paper(arxiv_id="2611.00001", date=D, title="A Paper ▲ with “quotes”", abstract="The abstract.",
              upvotes=42, authors=[Author(name=a) for a in authors], enrichment=enrichment)
    return RankedPaper(paper=p, rank=1, score=42, trust=0)


def group(*rps):
    return CategoryGroup(category=CAT, papers=list(rps), total_upvotes=42)


GOOD = Enrichment(summary="Sum.", use_cases=["u1", "u2"], whats_new=["n1"])


def test_renders_pdf(tmp_path):
    p = render_category_pdf(D, group(rp(GOOD)), tmp_path / "a.pdf")
    assert p.read_bytes()[:5] == b"%PDF-"


def test_unicode_authors(tmp_path):  # Review Focus 5
    p = render_category_pdf(D, group(rp(GOOD, authors=("Zoë Łukasz", "王伟", "Ægir Þór"))), tmp_path / "u.pdf")
    assert p.stat().st_size > 0


def test_sections_ok():
    assert paper_sections(rp(GOOD)) == [("Summary", "Sum."), ("Use cases", ["u1", "u2"]), ("What's new", ["n1"])]


def test_fallback_note_present():
    for e in (None, Enrichment(summary="The abstract.", ok=False)):
        summary = paper_sections(rp(e))[0][1]
        assert "The abstract." in summary and "Enrichment unavailable for this paper." in summary


def test_cache_reuses_file(tmp_path):
    first = get_or_render_pdf(tmp_path, D, group(rp(GOOD)))
    mtime = first.stat().st_mtime_ns
    time.sleep(0.01)
    second = get_or_render_pdf(tmp_path, D, group(rp(GOOD)))
    assert first == second and second.stat().st_mtime_ns == mtime


def test_pdf_path_slug():
    assert pdf_path(Path("d"), D, "Multimodal / Vision-Language").name == "2026-11-15_multimodal-vision-language.pdf"
    assert pdf_path(Path("d"), D, "LLMs & Reasoning").name == "2026-11-15_llms-reasoning.pdf"
