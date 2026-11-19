"""Core data models."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from paperbot.config import Category


class Author(BaseModel):
    name: str
    hf_user: str | None = None


class Enrichment(BaseModel):
    summary: str
    use_cases: list[str] = Field(default_factory=list)
    whats_new: list[str] = Field(default_factory=list)
    ok: bool = True


class Paper(BaseModel):
    arxiv_id: str
    date: date
    title: str
    abstract: str = ""
    authors: list[Author] = Field(default_factory=list)
    upvotes: int = 0
    ai_summary: str | None = None
    ai_keywords: list[str] = Field(default_factory=list)
    category: str | None = None
    secondary_category: str | None = None
    enrichment: Enrichment | None = None

    @property
    def hf_url(self) -> str:
        return f"https://huggingface.co/papers/{self.arxiv_id}"

    @property
    def arxiv_url(self) -> str:
        return f"https://arxiv.org/abs/{self.arxiv_id}"


class RankedPaper(BaseModel):
    paper: Paper
    rank: int
    score: float
    trust: int
    secondary: Category | None = None  # "also relevant to" tag


class CategoryGroup(BaseModel):
    category: Category
    papers: list[RankedPaper]
    total_upvotes: int
    related: list[RankedPaper] = Field(default_factory=list)  # papers whose secondary category is this one
