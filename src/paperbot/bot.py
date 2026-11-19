"""Discord layer: daily scheduler, catch-up, digest posting, PDF menu, /paperbot setchannel."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone

UTC = timezone.utc

import discord
from discord import app_commands
from discord.ext import tasks

from paperbot.config import Settings
from paperbot.dates import new_channel_baseline, pending_dates, target_date
from paperbot.digest import build_digest, chunk_embeds
from paperbot.hf_client import HFUnavailable
from paperbot.llm import LLMUnavailable
from paperbot.pdf import get_or_render_pdf
from paperbot.storage import Storage

log = logging.getLogger(__name__)
EMBED_COLOR = 0xFFB000


def plan_cycle(storage: Storage, channels: list[int], target: date, max_days: int) -> dict[int, list[date]]:
    return {
        ch: pending_dates(storage.channel_floor(ch), storage.posted_dates(ch), target, max_days)
        for ch in channels
    }


class CategoryPdfSelect(
    discord.ui.DynamicItem[discord.ui.Select],
    template=r"paperbot:pdf:(?P<date>\d{4}-\d{2}-\d{2})",
):
    """Dropdown under a digest. Persistent: the date lives in the custom_id, so it survives restarts."""

    def __init__(self, d: date, categories: list[tuple[str, str]] | None = None):
        self.d = d
        options = [
            discord.SelectOption(label=f"{emoji} {name}"[:100], value=name[:100])
            for emoji, name in (categories or [])[:25]
        ] or [discord.SelectOption(label="—", value="—")]
        super().__init__(
            discord.ui.Select(
                custom_id=f"paperbot:pdf:{d.isoformat()}",
                placeholder="📄 Get the PDF of a category…",
                options=options,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(date.fromisoformat(match["date"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        bot = interaction.client
        values = (interaction.data or {}).get("values") or []
        await interaction.response.defer(ephemeral=True, thinking=True)
        groups = await asyncio.to_thread(bot.pipeline.ranked, self.d)
        group = next((g for g in groups if values and g.category.name == values[0]), None)
        if group is None:
            await interaction.followup.send("No data for that day.", ephemeral=True)
            return
        path = await asyncio.to_thread(get_or_render_pdf, bot.settings.pdf_dir, self.d, group)
        await interaction.followup.send(
            f"{group.category.emoji} **{group.category.name}** — {self.d:%Y-%m-%d}",
            file=discord.File(path),
            ephemeral=True,
        )


class PaperBot(discord.Client):
    def __init__(self, settings: Settings, pipeline, storage: Storage):
        super().__init__(intents=discord.Intents.default())
        self.settings = settings
        self.pipeline = pipeline
        self.storage = storage
        self.tree = app_commands.CommandTree(self)
        self._cycle_lock = asyncio.Lock()
        self._started = False
        self._daily = None

    # --- setup -------------------------------------------------------------
    async def setup_hook(self) -> None:
        self.add_dynamic_items(CategoryPdfSelect)
        self.tree.add_command(self._command_group())
        await self.tree.sync()
        when = self.settings.schedule_utc.replace(tzinfo=UTC)
        self._daily = tasks.loop(time=when)(self._daily_tick)
        self._daily.start()

    def _command_group(self) -> app_commands.Group:
        group = app_commands.Group(
            name="paperbot",
            description="PaperBot settings",
            default_permissions=discord.Permissions(manage_guild=True),
            guild_only=True,
        )

        @group.command(name="setchannel", description="Post the daily papers digest in this channel")
        @app_commands.describe(channel="Channel that will receive the digest")
        async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
            s = self.settings
            baseline = new_channel_baseline(datetime.now(UTC), s.schedule_utc, s.delay_days)
            self.storage.set_guild_channel(interaction.guild_id, channel.id, baseline)
            await interaction.response.send_message(
                f"✅ Daily digest will be posted in {channel.mention} from the next run "
                f"({s.schedule_utc:%H:%M} UTC).",
                ephemeral=True,
            )

        return group

    async def on_ready(self) -> None:
        log.info("Logged in as %s", self.user)
        if self._started:
            return
        self._started = True
        asyncio.create_task(self._startup())

    async def _startup(self) -> None:
        try:
            if self.storage.is_empty():
                log.info("First start: backfilling %d days of history", self.settings.backfill_days)
                await asyncio.to_thread(self.pipeline.backfill, self.settings.backfill_days, datetime.now(UTC).date())
            await self.run_cycle(datetime.now(UTC))
        except Exception:
            log.exception("Startup cycle failed")

    async def _daily_tick(self) -> None:
        await self.wait_until_ready()
        try:
            await self.run_cycle(datetime.now(UTC))
        except Exception:
            log.exception("Daily cycle failed")

    # --- cycle -------------------------------------------------------------
    def target_channels(self) -> list[int]:
        chans = list(self.storage.guild_channels())
        if self.settings.default_channel_id:
            chans.insert(0, self.settings.default_channel_id)
        return list(dict.fromkeys(chans))

    async def _process(self, d: date) -> bool:
        """Run the pipeline for d; True if d is ready to post."""
        try:
            await asyncio.to_thread(self.pipeline.run, d)
            return True
        except (HFUnavailable, LLMUnavailable) as e:
            ready = self.storage.is_date_done(d)
            log.error("Pipeline for %s failed: %s%s", d, e, " (posting stored data)" if ready else "")
            return ready

    async def run_cycle(self, now: datetime) -> None:
        async with self._cycle_lock:
            s = self.settings
            target = target_date(now, s.delay_days)
            plan = plan_cycle(self.storage, self.target_channels(), target, s.catchup_max_days)
            ready: dict[date, bool] = {}
            for ch, dates in plan.items():
                for d in dates:
                    if d not in ready:
                        ready[d] = await self._process(d)
                    if not ready[d]:
                        continue  # retried next cycle while inside the catch-up window
                    if not await self.post_digest(ch, d):
                        break  # channel problem: stop for this channel, retry next cycle

    async def post_digest(self, channel_id: int, d: date) -> bool:
        groups = await asyncio.to_thread(self.pipeline.ranked, d)
        if not groups:
            log.info("No papers for %s; nothing to post in %s", d, channel_id)
            self.storage.mark_posted(channel_id, d)
            return True
        try:
            channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
            guild = getattr(channel, "guild", None)
            if guild is not None and guild.me is not None:
                perms = channel.permissions_for(guild.me)
                if not (perms.send_messages and perms.embed_links):
                    log.warning("Missing Send Messages / Embed Links permission in channel %s", channel_id)
                    return False
            digest = build_digest(d, groups, self.settings.top_n)
            for i, chunk in enumerate(chunk_embeds(digest.embeds)):
                embeds = [discord.Embed(title=e.title, description=e.description, color=EMBED_COLOR) for e in chunk]
                # header rides with the first embeds, so a failure never leaves a lone header behind
                await channel.send(digest.header if i == 0 else None, embeds=embeds)
            view = discord.ui.View(timeout=None)
            view.add_item(CategoryPdfSelect(d, [(g.category.emoji, g.category.name) for g in groups]))
            await channel.send("Full summaries, use cases and what's new — pick a category:", view=view)
        except discord.HTTPException as e:  # includes NotFound / Forbidden / 5xx
            log.warning("Cannot post in channel %s: %s", channel_id, e)
            return False
        self.storage.mark_posted(channel_id, d)
        log.info("Posted digest for %s in %s", d, channel_id)
        return True


def run_bot(settings: Settings) -> None:
    if not settings.discord_token:
        raise SystemExit("DISCORD_TOKEN is missing: put it in the .env file (see .env.example).")
    from paperbot.pipeline import build_pipeline

    pipeline = build_pipeline(settings)
    bot = PaperBot(settings, pipeline, pipeline.storage)
    bot.run(settings.discord_token, log_handler=None)
