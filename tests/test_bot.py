import re
from datetime import UTC, date, datetime

import pytest

from paperbot.bot import CategoryPdfSelect, PaperBot, plan_cycle
from paperbot.hf_client import HFUnavailable

NOW = datetime(2026, 11, 18, 8, 0, tzinfo=UTC)  # target = 2026-11-15
T = date(2026, 11, 15)


def test_plan_cycle_fresh_and_new_channel(store):
    store.set_guild_channel(1, 20, baseline=T)
    assert plan_cycle(store, [10, 20], T, 7) == {10: [T], 20: []}


def test_plan_cycle_catchup_capped(store):
    store.mark_posted(10, date(2026, 11, 3))
    dates = plan_cycle(store, [10], T, 7)[10]
    assert dates[0] == date(2026, 11, 9) and dates[-1] == T and len(dates) == 7


async def test_custom_id_roundtrip():
    item = CategoryPdfSelect(T, [("🧠", "LLMs & Reasoning")])
    assert item.custom_id == "paperbot:pdf:2026-11-15"
    m = re.fullmatch(CategoryPdfSelect.__discord_ui_compiled_template__, item.custom_id)
    again = await CategoryPdfSelect.from_custom_id(None, item.item, m)
    assert again.d == T
    assert [o.value for o in item.item.options] == ["LLMs & Reasoning"]


class FakePipeline:
    def __init__(self, fail=()):
        self.fail = set(fail)
        self.runs = []

    def run(self, d, force=False):
        self.runs.append(d)
        if d in self.fail:
            raise HFUnavailable("down")
        return []


def make_bot(settings, store, pipe):
    bot = PaperBot(settings, pipe, store)
    posted = []

    async def fake_post(ch, d):
        posted.append((ch, d))
        store.mark_posted(ch, d)
        return True

    bot.post_digest = fake_post
    return bot, posted


async def test_run_cycle_stops_on_failure(settings, store):
    s = settings.model_copy(update={"default_channel_id": 10})
    store.mark_posted(10, date(2026, 11, 12))
    pipe = FakePipeline(fail=[date(2026, 11, 14)])
    bot, posted = make_bot(s, store, pipe)
    await bot.run_cycle(NOW)
    assert posted == [(10, date(2026, 11, 13))] and store.last_posted(10) == date(2026, 11, 13)


async def test_failure_on_already_done_date_still_posts(settings, store):
    s = settings.model_copy(update={"default_channel_id": 10})
    store.mark_date_done(T, 3)
    bot, posted = make_bot(s, store, FakePipeline(fail=[T]))
    await bot.run_cycle(NOW)
    assert posted == [(10, T)]


async def test_run_cycle_runs_pipeline_once_for_two_channels(settings, store):
    s = settings.model_copy(update={"default_channel_id": 10})
    store.set_guild_channel(1, 20, baseline=date(2026, 11, 14))
    pipe = FakePipeline()
    bot, posted = make_bot(s, store, pipe)
    await bot.run_cycle(NOW)
    assert pipe.runs == [T] and sorted(posted) == [(10, T), (20, T)]


def test_target_channels_dedup(settings, store):
    s = settings.model_copy(update={"default_channel_id": 10})
    store.set_guild_channel(1, 10, baseline=T)
    store.set_guild_channel(2, 20, baseline=T)
    bot, _ = make_bot(s, store, FakePipeline())
    assert bot.target_channels() == [10, 20]
