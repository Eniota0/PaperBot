from datetime import date
from pathlib import Path

import pytest

from paperbot.config import load_settings
from paperbot.models import Author, Paper
from paperbot.storage import Storage

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def store():
    s = Storage(":memory:")
    yield s
    s.close()


@pytest.fixture
def paper():
    return Paper(arxiv_id="2611.00001", date=date(2026, 11, 15), title="A Paper",
                 abstract="An abstract.", upvotes=10,
                 authors=[Author(name="Alice", hf_user="alicem"), Author(name="Bob")])
