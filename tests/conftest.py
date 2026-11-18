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


class FakeLLM:
    """Returns queued responses (dicts, or exceptions to raise) and records prompts.

    If `responder` is given it is called as responder(prompt, schema) when the queue is empty.
    """

    def __init__(self, responses=None, responder=None):
        self.responses = list(responses or [])
        self.responder = responder
        self.prompts: list[str] = []

    def complete_json(self, prompt, schema):
        self.prompts.append(prompt)
        if self.responses:
            r = self.responses.pop(0)
        elif self.responder:
            r = self.responder(prompt, schema)
        else:
            raise AssertionError("FakeLLM: no response queued")
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def settings(tmp_path):
    s = load_settings(ROOT / "config.example.yaml", tmp_path / "none.env")
    return s.model_copy(update={"data_dir": tmp_path / "data"})
