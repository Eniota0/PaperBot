"""Render one category's papers (with enrichment) as a PDF."""
from __future__ import annotations

import logging
import re
from datetime import date
from importlib.resources import as_file, files
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from paperbot.models import CategoryGroup, RankedPaper

logging.getLogger("fontTools").setLevel(logging.ERROR)
logging.getLogger("fpdf").setLevel(logging.ERROR)

FALLBACK_NOTE = "Enrichment unavailable for this paper."
NL = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}


def pdf_path(pdf_dir: Path, d: date, category: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", category.lower()).strip("-")
    return pdf_dir / f"{d:%Y-%m-%d}_{slug}.pdf"


def paper_sections(rp: RankedPaper) -> list[tuple[str, str | list[str]]]:
    e = rp.paper.enrichment
    if e is None or not e.ok:
        abstract = (e.summary if e else "") or rp.paper.abstract or ""
        return [("Summary", f"{abstract}\n\n{FALLBACK_NOTE}".strip()), ("Use cases", []), ("What's new", [])]
    return [("Summary", e.summary), ("Use cases", e.use_cases), ("What's new", e.whats_new)]


def render_category_pdf(d: date, group: CategoryGroup, out_path: Path) -> Path:
    assets = files("paperbot.assets")
    with as_file(assets / "DejaVuSans.ttf") as reg, as_file(assets / "DejaVuSans-Bold.ttf") as bold:
        pdf = FPDF(format="A4")
        pdf.set_auto_page_break(True, margin=15)
        pdf.add_font("DejaVu", "", str(reg))
        pdf.add_font("DejaVu", "B", str(bold))
        pdf.set_title(f"{group.category.name} - HF Papers {d:%Y-%m-%d}")
        pdf.add_page()
        w = pdf.epw

        pdf.set_font("DejaVu", "B", 18)
        pdf.multi_cell(w, 9, f"{group.category.name} — HF Papers {d:%Y-%m-%d}", **NL)
        pdf.set_font("DejaVu", "", 11)
        pdf.cell(w, 7, f"{len(group.papers)} papers", **NL)
        pdf.ln(4)

        for rp in group.papers:
            p = rp.paper
            pdf.set_font("DejaVu", "B", 13)
            pdf.multi_cell(w, 7, f"#{rp.rank}  {p.title}", **NL)
            pdf.set_font("DejaVu", "", 9)
            if p.authors:
                pdf.multi_cell(w, 5, ", ".join(a.name for a in p.authors), **NL)
            star = "   ★ trusted author" if rp.trust else ""
            pdf.multi_cell(w, 5, f"▲ {p.upvotes} upvotes{star}", **NL)
            pdf.set_text_color(30, 80, 200)
            pdf.cell(0, 5, "Hugging Face page", link=p.hf_url, **NL)
            pdf.cell(0, 5, "arXiv", link=p.arxiv_url, **NL)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)
            for heading, body in paper_sections(rp):
                if not body:
                    continue
                pdf.set_font("DejaVu", "B", 11)
                pdf.cell(w, 6, heading, **NL)
                pdf.set_font("DejaVu", "", 10)
                if isinstance(body, str):
                    pdf.multi_cell(w, 5, body, **NL)
                else:
                    for item in body:
                        pdf.multi_cell(w, 5, f"•  {item}", **NL)
                pdf.ln(1)
            pdf.ln(3)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + w, pdf.get_y())
            pdf.ln(4)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(out_path))
    return out_path


def get_or_render_pdf(pdf_dir: Path, d: date, group: CategoryGroup) -> Path:
    path = pdf_path(pdf_dir, d, group.category.name)
    if path.exists():
        return path
    return render_category_pdf(d, group, path)
