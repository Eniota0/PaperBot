from paperbot.config import Tier
from paperbot.ranking import tier_for

TIERS = [Tier(name="Bronze", emoji="🥉", min_upvotes=50, color="#CD7F32"),
         Tier(name="Gold", emoji="🥇", min_upvotes=100, color="#D4AF37"),
         Tier(name="Platinum", emoji="💎", min_upvotes=200, color="#7F9BB3")]


def test_tier_for_picks_highest_reached():
    assert tier_for(49, TIERS) is None
    assert tier_for(50, TIERS).name == "Bronze"
    assert tier_for(199, TIERS).name == "Gold"
    assert tier_for(500, TIERS).name == "Platinum"


def test_tier_for_unsorted_and_empty():
    assert tier_for(120, list(reversed(TIERS))).name == "Gold"
    assert tier_for(1000, []) is None


def test_example_config_tiers(settings):
    assert [(t.name, t.min_upvotes, t.emoji) for t in settings.tiers] == [
        ("Bronze", 50, "🥉"), ("Gold", 100, "🥇"), ("Platinum", 200, "💎")]
