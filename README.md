# PaperBot

A Discord bot for technology watch on [Hugging Face Daily Papers](https://huggingface.co/papers).

Every day it takes the papers featured **3 days earlier** (UTC), when upvotes have settled. It sorts them into fixed
categories with a local LLM, ranks them by upvotes plus a small bonus for proven authors, and posts a digest:

```
📚 HF Papers — 2026-11-15 · 34 papers
🧠 LLMs & Reasoning (8)
 1. ▲142 Scaling Test-Time Compute for Reasoners ⭐
 2. ▲97  Self-Correcting Reasoners
 ...
[📄 Get the PDF of a category… ▾]
```

Pick a category in the menu to get a PDF with a **summary**, **use cases**, and **what's new** for every
paper in it. Only you see the PDF.

The bot works only while it is running. If your PC was off, it catches up on missed digests at the next start
(up to 7 days).

---

## Setup on Windows

### 1. Install the prerequisites

- **Python 3.11 or newer**: <https://www.python.org/downloads/>. During setup, tick *Add python.exe to PATH*.
- **Ollama 0.5 or newer** (runs the local model on your GPU): <https://ollama.com/download/windows>
- **Git** (optional, to clone this repository).

Then download the model (a few GB; it runs on laptop GPUs as well as an RTX 3060). In PowerShell:

```powershell
ollama pull qwen3.5:4b
```

### 2. Create the Discord bot

1. Go to <https://discord.com/developers/applications> and click **New Application**.
2. Open **Bot**, click **Reset Token**, and copy the token. Keep it secret.
3. Open **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot permissions: *Send Messages*, *Embed Links*, *Attach Files*, *Read Message History*
4. Open the generated URL to invite the bot to your server.
5. In Discord, enable *Developer Mode* (User Settings → Advanced). Right-click the channel for the digest and
   choose **Copy Channel ID**.

### 3. Install PaperBot

In PowerShell, inside the project folder:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item config.example.yaml config.yaml
Copy-Item .env.example .env
```

If `Activate.ps1` is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

Edit `.env`:

```
DISCORD_TOKEN=paste-your-token-here
```

Edit `config.yaml` and set `default_channel_id:` to the channel ID you copied (a number, no quotes).

### 4. First run

```powershell
# Optional: seed author history now (otherwise the bot does it on first start)
python -m paperbot backfill

# Optional: test the pipeline on one date without posting anything
python -m paperbot run --date 2026-11-15

# Start the bot
python -m paperbot bot
```

Keep the window open; the bot runs as long as it is open. Logs go to `data\logs\paperbot.log`.

### 5. Start automatically at login (optional)

Create `start-paperbot.bat` in the project folder:

```bat
@echo off
cd /d %~dp0
call .venv\Scripts\activate.bat
python -m paperbot bot
```

Press `Win + R`, type `shell:startup`, and put a shortcut to `start-paperbot.bat` in that folder. Ollama
starts with Windows by default.

---

## Usage

- **Daily digest**: posted at `schedule_utc` (default 08:00 UTC) for the date 3 days earlier.
- **PDF menu**: under each digest. It keeps working after a restart.
- **Another server or channel**: a server admin runs `/paperbot setchannel #channel`. That channel gets
  digests from the next run on, with no backlog.
- **Re-run a date** (e.g. after changing the model or prompts):
  `python -m paperbot run --date 2026-11-15 --force`. PDFs are cached in `data\pdf\`, so delete the date's
  files there to regenerate them.

## Configuration (`config.yaml`)

| Key | Default | Meaning |
|---|---|---|
| `schedule_utc` | `"08:00"` | Daily run time (UTC) |
| `delay_days` | `3` | Look at papers from this many days ago |
| `catchup_max_days` | `7` | Most digests posted on startup after the PC was off |
| `backfill_days` | `90` | History fetched on first start (for author trust) |
| `top_n` | `10` | Papers shown per category in Discord (the rest are in the PDF) |
| `default_channel_id` | `null` | Your digest channel |
| `ranking.trust_vote_threshold` | `50` | A previous paper counts towards trust if it got at least this many upvotes |
| `ranking.trust_cap` | `5` | Most trust points an author can have |
| `ranking.trust_weight` | `0.05` | `score = upvotes × (1 + weight × trust)`, so at most +25% |
| `ollama.model` | `qwen3.5:4b` | Any Ollama model; run `ollama pull <name>` first |
| `ollama.think` | `false` | Turns off "thinking" on Qwen3-style models (much faster). Use `null` for models without a thinking mode if Ollama complains |
| `categories` | 12 categories | Name, emoji, and a one-line description used by the LLM. Must include `Other` |

**Author trust** only counts authors whose Hugging Face account is linked to the paper. Others are ignored.
Papers with a trusted author get ⭐.

The LLM prompts are in `src/paperbot/prompts/` and can be edited.

## Development

```powershell
pip install -e ".[dev]"
pytest
```

Code map: `hf_client` (fetch) → `categorize` / `enrich` (LLM) → `ranking` → `pipeline` (one date,
idempotent) → `digest` / `pdf` (output) → `bot` (Discord, scheduler, catch-up). Data is stored in SQLite at
`data\paperbot.db`.

The LLM sits behind a small interface (`paperbot.llm.LLMProvider`), so you can add a hosted API (e.g.
Claude) later by writing one class.
