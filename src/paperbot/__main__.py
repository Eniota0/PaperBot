"""Command line: python -m paperbot {bot,run,backfill}."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from paperbot.config import load_settings, setup_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paperbot", description="Hugging Face papers digest for Discord")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--env", type=Path, default=Path(".env"))
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bot", help="run the Discord bot (scheduler + menu)")
    run = sub.add_parser("run", help="process one date and print the ranking (no posting)")
    run.add_argument("--date", type=date.fromisoformat, required=True)
    run.add_argument("--force", action="store_true", help="recompute categories and summaries")
    bf = sub.add_parser("backfill", help="fetch past papers (no LLM) to seed author trust")
    bf.add_argument("--days", type=int, default=None)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles may not be UTF-8
        sys.stdout.reconfigure(errors="replace")

    settings = load_settings(args.config, args.env)
    setup_logging(settings.log_dir)
    log = logging.getLogger("paperbot")

    if args.cmd == "bot":
        from paperbot.bot import run_bot

        run_bot(settings)
        return 0

    from paperbot.pipeline import build_pipeline

    pipe = build_pipeline(settings)
    if args.cmd == "backfill":
        n = pipe.backfill(args.days or settings.backfill_days, datetime.now(UTC).date())
        print(f"Stored {n} papers.")
        return 0

    try:
        groups = pipe.run(args.date, force=args.force)
    except Exception as e:  # noqa: BLE001 - CLI: show a clear message
        log.error("%s", e)
        return 1
    for g in groups:
        print(f"\n{g.category.emoji} {g.category.name} ({len(g.papers)})")
        for rp in g.papers:
            star = " *" if rp.trust else ""
            print(f"  {rp.rank:>2}. ▲{rp.paper.upvotes:<4} {rp.paper.title}{star}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
