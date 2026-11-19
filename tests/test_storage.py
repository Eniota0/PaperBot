from datetime import date, timedelta

from paperbot.models import Enrichment, Paper
from paperbot.storage import Storage


def test_roundtrip_and_enrichment(store, paper):
    store.upsert_papers([paper])
    store.set_category(paper.arxiv_id, "Agents")
    store.set_enrichment(paper.arxiv_id, Enrichment(summary="S", use_cases=["u"], whats_new=["n"]))
    p = store.papers_for_date(paper.date)[0]
    assert p.title == "A Paper" and p.category == "Agents"
    assert p.enrichment.summary == "S" and p.enrichment.use_cases == ["u"]
    assert [a.hf_user for a in p.authors] == ["alicem", None]


def test_upsert_updates_votes_keeps_category(store, paper):
    store.upsert_papers([paper]); store.set_category(paper.arxiv_id, "Agents")
    store.upsert_papers([paper.model_copy(update={"upvotes": 99})])
    p = store.papers_for_date(paper.date)[0]
    assert p.upvotes == 99 and p.category == "Agents"


def test_refeatured_paper_keeps_original_date(store, paper):  # Review Focus 2
    store.upsert_papers([paper])
    store.upsert_papers([paper.model_copy(update={"date": paper.date + timedelta(days=5)})])
    assert store.papers_for_date(paper.date)
    assert not store.papers_for_date(paper.date + timedelta(days=5))


def test_author_upvotes_before_is_strict(store):
    mk = lambda i, d, v: Paper(arxiv_id=f"x{i}", date=d, title="t", upvotes=v,
                               authors=[{"name": "A", "hf_user": "alicem"}])
    store.upsert_papers([mk(1, date(2026, 11, 1), 70), mk(2, date(2026, 11, 5), 80), mk(3, date(2026, 11, 6), 90)])
    assert sorted(store.author_upvotes_before("alicem", date(2026, 11, 6))) == [70, 80]
    assert store.author_upvotes_before("nobody", date(2026, 11, 6)) == []


def test_dates_done(store):
    assert not store.is_date_done(date(2026, 11, 15))
    store.mark_date_done(date(2026, 11, 15), 3)
    assert store.is_date_done(date(2026, 11, 15))


def test_posted_and_baseline(store):
    store.set_guild_channel(1, 10, baseline=date(2026, 11, 14))
    assert store.last_posted(10) == date(2026, 11, 14) and store.guild_channels() == [10]
    store.mark_posted(10, date(2026, 11, 15))
    assert store.last_posted(10) == date(2026, 11, 15)
    assert store.last_posted(999) is None
    store.set_guild_channel(1, 11, baseline=date(2026, 11, 16))  # guild moves channel
    assert store.guild_channels() == [11]


def test_is_empty_and_file_db(tmp_path, paper):
    s = Storage(tmp_path / "sub" / "db.sqlite")
    assert s.is_empty()
    s.upsert_papers([paper])
    assert not s.is_empty()
    s.close()
    assert Storage(tmp_path / "sub" / "db.sqlite").papers_for_date(paper.date)


def test_secondary_category_roundtrip(store, paper):
    store.upsert_papers([paper])
    store.set_category(paper.arxiv_id, "Agents", "Robotics & Embodied AI")
    p = store.papers_for_date(paper.date)[0]
    assert (p.category, p.secondary_category) == ("Agents", "Robotics & Embodied AI")


def test_migrates_old_database(tmp_path, paper):
    import sqlite3
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE papers (arxiv_id TEXT PRIMARY KEY, date TEXT NOT NULL, title TEXT NOT NULL,
      abstract TEXT NOT NULL DEFAULT '', upvotes INTEGER NOT NULL DEFAULT 0, ai_summary TEXT,
      ai_keywords TEXT NOT NULL DEFAULT '[]', authors TEXT NOT NULL DEFAULT '[]', category TEXT, enrichment TEXT)""")
    con.execute("INSERT INTO papers (arxiv_id, date, title, category) VALUES ('old1', '2026-11-15', 'Old', 'Agents')")
    con.commit(); con.close()
    s = Storage(path)
    p = s.papers_for_date(paper.date)[0]
    assert p.category == "Agents" and p.secondary_category is None
    s.set_category("old1", "Agents", "Other")
    s.close()
