"""SQLite persistence for papers, enrichment, posting state and guild channels."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import date
from pathlib import Path

from paperbot.models import Author, Enrichment, Paper

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
  arxiv_id TEXT PRIMARY KEY, date TEXT NOT NULL, title TEXT NOT NULL,
  abstract TEXT NOT NULL DEFAULT '', upvotes INTEGER NOT NULL DEFAULT 0,
  ai_summary TEXT, ai_keywords TEXT NOT NULL DEFAULT '[]',
  authors TEXT NOT NULL DEFAULT '[]', category TEXT, enrichment TEXT
);
CREATE INDEX IF NOT EXISTS papers_date ON papers(date);
CREATE TABLE IF NOT EXISTS paper_authors (
  arxiv_id TEXT NOT NULL, hf_user TEXT NOT NULL, PRIMARY KEY (arxiv_id, hf_user)
);
CREATE INDEX IF NOT EXISTS paper_authors_user ON paper_authors(hf_user);
CREATE TABLE IF NOT EXISTS dates_done (date TEXT PRIMARY KEY, paper_count INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS posts (channel_id INTEGER NOT NULL, date TEXT NOT NULL, PRIMARY KEY (channel_id, date));
CREATE TABLE IF NOT EXISTS guild_channels (
  guild_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL, baseline TEXT NOT NULL
);
"""


class Storage:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def _exec(self, sql: str, params=()) -> list[sqlite3.Row]:
        with self._lock, self._conn:
            return self._conn.execute(sql, params).fetchall()

    # --- papers -----------------------------------------------------------
    def upsert_papers(self, papers: list[Paper]) -> None:
        with self._lock, self._conn:
            for p in papers:
                self._conn.execute(
                    """INSERT INTO papers (arxiv_id, date, title, abstract, upvotes, ai_summary, ai_keywords, authors)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(arxiv_id) DO UPDATE SET title=excluded.title, abstract=excluded.abstract,
                         upvotes=excluded.upvotes, ai_summary=excluded.ai_summary,
                         ai_keywords=excluded.ai_keywords, authors=excluded.authors""",
                    (p.arxiv_id, p.date.isoformat(), p.title, p.abstract, p.upvotes, p.ai_summary,
                     json.dumps(p.ai_keywords), json.dumps([a.model_dump() for a in p.authors])),
                )
                self._conn.execute("DELETE FROM paper_authors WHERE arxiv_id = ?", (p.arxiv_id,))
                for user in {a.hf_user for a in p.authors if a.hf_user}:
                    self._conn.execute("INSERT INTO paper_authors VALUES (?, ?)", (p.arxiv_id, user))

    @staticmethod
    def _row_to_paper(r: sqlite3.Row) -> Paper:
        return Paper(
            arxiv_id=r["arxiv_id"], date=date.fromisoformat(r["date"]), title=r["title"],
            abstract=r["abstract"], upvotes=r["upvotes"], ai_summary=r["ai_summary"],
            ai_keywords=json.loads(r["ai_keywords"]),
            authors=[Author(**a) for a in json.loads(r["authors"])],
            category=r["category"],
            enrichment=Enrichment(**json.loads(r["enrichment"])) if r["enrichment"] else None,
        )

    def papers_for_date(self, d: date) -> list[Paper]:
        rows = self._exec("SELECT * FROM papers WHERE date = ? ORDER BY arxiv_id", (d.isoformat(),))
        return [self._row_to_paper(r) for r in rows]

    def set_category(self, arxiv_id: str, category: str) -> None:
        self._exec("UPDATE papers SET category = ? WHERE arxiv_id = ?", (category, arxiv_id))

    def set_enrichment(self, arxiv_id: str, e: Enrichment) -> None:
        self._exec("UPDATE papers SET enrichment = ? WHERE arxiv_id = ?", (e.model_dump_json(), arxiv_id))

    def author_upvotes_before(self, hf_user: str, before: date) -> list[int]:
        rows = self._exec(
            """SELECT p.upvotes FROM papers p JOIN paper_authors a ON a.arxiv_id = p.arxiv_id
               WHERE a.hf_user = ? AND p.date < ?""",
            (hf_user, before.isoformat()),
        )
        return [r[0] for r in rows]

    def is_empty(self) -> bool:
        return not self._exec("SELECT 1 FROM papers LIMIT 1")

    # --- pipeline / posting state ----------------------------------------
    def mark_date_done(self, d: date, paper_count: int) -> None:
        self._exec("INSERT OR REPLACE INTO dates_done VALUES (?, ?)", (d.isoformat(), paper_count))

    def is_date_done(self, d: date) -> bool:
        return bool(self._exec("SELECT 1 FROM dates_done WHERE date = ?", (d.isoformat(),)))

    def mark_posted(self, channel_id: int, d: date) -> None:
        self._exec("INSERT OR IGNORE INTO posts VALUES (?, ?)", (channel_id, d.isoformat()))

    def last_posted(self, channel_id: int) -> date | None:
        rows = self._exec(
            """SELECT MAX(d) FROM (SELECT date AS d FROM posts WHERE channel_id = ?
                                   UNION ALL SELECT baseline FROM guild_channels WHERE channel_id = ?)""",
            (channel_id, channel_id),
        )
        v = rows[0][0]
        return date.fromisoformat(v) if v else None

    def set_guild_channel(self, guild_id: int, channel_id: int, baseline: date) -> None:
        self._exec("INSERT OR REPLACE INTO guild_channels VALUES (?, ?, ?)",
                   (guild_id, channel_id, baseline.isoformat()))

    def guild_channels(self) -> list[int]:
        return [r[0] for r in self._exec("SELECT channel_id FROM guild_channels ORDER BY guild_id")]
