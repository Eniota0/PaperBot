from datetime import date, datetime, time, timezone

UTC = timezone.utc
from zoneinfo import ZoneInfo

from paperbot.dates import catchup_dates, new_channel_baseline, target_date


def test_target_date_uses_utc():
    paris = datetime(2026, 11, 18, 0, 30, tzinfo=ZoneInfo("Europe/Paris"))  # 23:30 UTC on 17th
    assert target_date(paris, 3) == date(2026, 11, 14)


def test_catchup_fresh_install():
    assert catchup_dates(None, date(2026, 11, 15), 7) == [date(2026, 11, 15)]


def test_catchup_range_and_cap():
    assert catchup_dates(date(2026, 11, 12), date(2026, 11, 15), 7) == [
        date(2026, 11, 13), date(2026, 11, 14), date(2026, 11, 15)]
    r = catchup_dates(date(2026, 11, 1), date(2026, 11, 15), 7)
    assert r[0] == date(2026, 11, 9) and r[-1] == date(2026, 11, 15) and len(r) == 7


def test_catchup_nothing_to_do():
    assert catchup_dates(date(2026, 11, 15), date(2026, 11, 15), 7) == []
    assert catchup_dates(date(2026, 11, 16), date(2026, 11, 15), 7) == []


def test_new_channel_baseline():
    t = time(8, 0)
    assert new_channel_baseline(datetime(2026, 11, 18, 9, 0, tzinfo=UTC), t, 3) == date(2026, 11, 15)
    assert new_channel_baseline(datetime(2026, 11, 18, 7, 0, tzinfo=UTC), t, 3) == date(2026, 11, 14)
