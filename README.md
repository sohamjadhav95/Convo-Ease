# ConvoEase v5

ConvoEase is a group chat where an AI moderator checks every message — text, images and voice notes — against rules that each group's admin writes in plain language. Messages that break the rules are held back, and the sender can appeal.

**Deploy it for free:** see [docs/DEPLOY.md](docs/DEPLOY.md) (Render + Neon + Gemini, about 10 minutes).

## Features

- **AI moderation for text, images and audio.** Images are described by a vision model and audio is transcribed and summarised; the result is then checked against the group rules.
- **Rules in plain language** per group, with AI suggestions for improving them, and upload from `.txt` / `.pdf`.
- **Moderation strictness** per group: `Strict`, `Moderate` or `Relaxed`.
- **Appeals.** The sender explains the context, the AI re-checks, and the admin makes the final call.
- **AI catch-up** summarises recent conversation for anyone who was away.
- **Admin dashboard** with pass/flag rates, reasons, trends, and a trust score per member.
- **Any language.** The moderator judges meaning and intent in the original language, and decodes leetspeak (e.g. `1d10t`).
- Prompt-injection and spam filters run before the AI is called.
- **Material Design 3 interface** with light/dark themes, four accent colors and a phone layout. Photos are shrunk and voice notes converted to WAV in the browser before upload.

## Quick start (on your computer)

Requires Python 3.10+ (3.12 recommended).

```bash
pip install -r requirements.txt
cp .env.example .env          # then put your GEMINI_API_KEY in .env
python run.py
```

Open <http://localhost:5000>. Data is saved in a local SQLite file (`database/convoease.db`).

Get a free Gemini key at <https://aistudio.google.com/apikey>.

### Upgrading from v4 (CSV files)

v5 stores data in a real database instead of CSV files. Copy your old data over once:

```bash
python scripts/import_legacy_csv.py --utc-offset +05:30
```

Old accounts keep their passwords (they are re-hashed securely at next login).

## What changed in v5

| Area | Before (v4) | Now (v5) |
|---|---|---|
| Storage | CSV files read with pandas | SQLite locally, Postgres in production (SQLAlchemy) |
| Media | Files on local disk | Stored in the database, so they survive redeploys |
| Login | The browser just sent a username; anyone could act as anyone | Signed session cookies; every request checks membership / admin rights |
| Passwords | Unsalted SHA-256 | scrypt (old hashes upgraded automatically) |
| AI | NVIDIA only; audio needed local Whisper + PyTorch (~2 GB) | Gemini by default; Groq, NVIDIA or any OpenAI-compatible API; audio via API |
| Install size | over 2 GB | ~170 MB |
| Server | Flask dev server | Gunicorn, Dockerfile, Render blueprint, health check |
| Abuse protection | none | Per-user rate limits, upload size and file-type checks, strict Content-Security-Policy |
| Interface | Single 2,400-line script | Material Design 3, split into small modules, light/dark, mobile layout |

Bugs fixed along the way:

- Groups without a password could not be joined (pandas 3 read the empty password as `"nan"`).
- Group IDs that look like numbers (e.g. `5928E9`, `012345`) were read as numbers and broke.
- Deleted messages were counted as "flagged" in the admin trend chart.

## AI providers

Pick one with `CONVOEASE_AI_PROVIDER` (or just set the matching key):

| Provider | Key variable | Text | Images | Audio |
|---|---|---|---|---|
| `gemini` (default) | `GEMINI_API_KEY` | ✓ | ✓ | ✓ |
| `groq` | `GROQ_API_KEY` | ✓ | ✓ | ✓ (Whisper) |
| `nvidia` | `NVIDIA_API_KEY` | ✓ | ✓ | set `CONVOEASE_AUDIO_PROVIDER` to another provider |
| `custom` | `CONVOEASE_API_KEY` + `CONVOEASE_API_URL` | any OpenAI-compatible API | | |

Models can be changed with `CONVOEASE_TEXT_MODEL_ID`, `CONVOEASE_IMAGE_MODEL_ID` and `CONVOEASE_AUDIO_MODEL_ID`. See [docs/DEPLOY.md](docs/DEPLOY.md#all-settings) for every setting.

### Running models on your own machine (optional)

The original local-model support is still there for research use:

```bash
pip install -r requirements-local.txt     # PyTorch, Transformers, Whisper
export CONVOEASE_MODEL_MODE=local
export CONVOEASE_TEXT_MODEL_PATH=/path/to/hf-model     # folder with config.json
export CONVOEASE_IMAGE_MODEL_PATH=/path/to/vision-model
export CONVOEASE_WHISPER_SIZE=base
python run.py
```

Each modality can be switched separately with `CONVOEASE_TEXT_BACKEND`, `CONVOEASE_IMAGE_BACKEND` and `CONVOEASE_AUDIO_BACKEND` (`api` or `local`). A model path may point at the model folder itself or at a parent folder containing exactly one model.

## Project layout

```text
main.py                     Flask app and REST API
core_processing_engine.py   Moderation plugins (text, image, audio)
backends/                   AI backends (hosted API or local models)
database/Database_processing/  Database tables and data access
Frontend/                   The web interface (plain HTML/CSS/JS modules, no build step)
  css/tokens.css            Material 3 color schemes (generated from seed colors)
  js/                       main, shell, chat, dashboard, settings, dialogs, media helpers
scripts/                    One-off tools (v4 data import)
testing/                    pytest, Playwright and Locust suites
paper_artifacts/            Data and scripts behind the paper
Archives/                   Earlier versions, kept for reference
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest testing/pytest -q
```

The suite uses a throwaway database and a fake AI, so it needs no API key. To run it against Postgres, set `CONVOEASE_TEST_DATABASE_URL`.

Browser tests (real Chromium, fake AI):

```bash
playwright install chromium     # once
pytest testing/e2e -q
```

## Reproducing the paper results

The raw predictions are included, so the published numbers can be recomputed without any API key:

```bash
pip install -r requirements-research.txt
python paper_artifacts/scripts/per_rule_accuracy_org_moderate.py
python paper_artifacts/scripts/mcnemar_tests.py
python paper_artifacts/scripts/compute_metrics.py
python paper_artifacts/scripts/verify_rows_vs_summary.py
```

The paper's live benchmarks used NVIDIA-hosted models. To generate new predictions the same way, set `CONVOEASE_AI_PROVIDER=nvidia` and `NVIDIA_API_KEY`.

## License

MIT — see [LICENSE](LICENSE).
