# ConvoEase v4.2

ConvoEase is a hybrid AI-powered group chat platform with moderation for text, image, and audio messages. It now supports a working local-model path for all three modalities alongside Groq-hosted inference.

## Highlights

- Text, image, and audio moderation through a shared plugin-based processing engine
- Smart AI catch-up summaries with a dedicated chat-header action for members
- Moderation explainability dashboard with reasons, categories, trends, trust scores, and message logs
- Toxicity and compliance heatmap with per-member trust scores and risk badges
- Smart rule suggestions during group creation and admin rule editing, shown on demand to keep forms compact
- Context-aware moderation sensitivity per group: `Strict`, `Moderate`, or `Relaxed`
- Appeal workflow for flagged members with AI re-evaluation and admin final review
- Multilingual moderation using language detection plus model-facing English translation fallback
- Persistent media storage and CSV-backed analytics with automatic schema migration
- Local backend support for text, image, and audio with automatic model-path resolution
- Improved chat UX with unread indicators, persistent dismissible moderation banners, copyable group IDs, and auto-growing message drafts

## Local Model Support

The local runtime was updated so the app can boot and run reliably with local models instead of only hosted APIs.

What changed:

- A global mode switch now defaults the app to `local` mode through `CONVOEASE_MODEL_MODE`
- Text, image, and audio backends can each be overridden independently
- Local text and image backends can point either to an exact model folder or to a parent folder that contains exactly one exported Hugging Face model
- The text backend now lazy-loads the model on first use instead of loading everything during app startup
- Local text loading forces synchronous Hugging Face weight loading on Windows/CUDA for stability
- Local text loading prefers GPU, then falls back to automatic CPU offload when VRAM is tight
- Local image loading prefers GPU and falls back to CPU automatically on CUDA memory pressure
- Local audio mode uses Whisper locally and resolves `ffmpeg` automatically through `imageio-ffmpeg` when needed
- Flask reloader is disabled automatically when local models are active and CUDA is involved, which avoids duplicate model loads and unstable restarts

## Feature Overview

### 1. Smart Chat Summarization

Any member can click the `AI catch-up` action in the chat header to get a concise recent-conversation summary.

Backend:

- `GET /api/groups/<group_id>/summary?limit=25`

Frontend:

- chat header AI icon action with tooltip
- summary modal with animated loading state for all members

### 2. Moderation Explainability Dashboard

The admin report includes:

- pass and flagged rates
- flagged reasons
- flag categories
- moderation trend cards
- recent passed and flagged message logs

Backend:

- `GET /api/groups/<group_id>/report`

### 3. Toxicity Heatmap Per Member

The moderation report calculates:

- trust score
- compliance rate
- risk level
- watch and high-risk badges

These indicators appear in the admin member list and report views.

### 3.1. Sidebar Awareness And Read State

Members can now see unread activity in other groups without opening each one manually.

Frontend:

- unread dots in the sidebar for inactive groups
- unread state cleared when the group is opened
- role labeling for admin-owned groups directly in the group list

### 4. Smart Rule Suggestions

Admins and group creators can request AI suggestions to improve moderation rules.

Backend:

- `POST /api/rules/suggest`

Frontend:

- create-group rules editor
- admin rules editor
- suggestion panel and revised-rule preview stay hidden until requested

### 5. Context-Aware Moderation Sensitivity

Each group can choose its moderation sensitivity:

- `Strict`: flags mild off-topic or borderline content more aggressively
- `Moderate`: balanced enforcement
- `Relaxed`: blocks only clear violations

This setting is stored per group and is injected into moderation prompts for text, image summaries, and audio summaries.

### 6. Appeal System

When a message is flagged, the sender can submit an appeal explaining the context. The system re-evaluates the original message together with the appeal text, then the admin makes the final decision.

Backend:

- `POST /api/groups/<group_id>/messages/<message_id>/appeal`
- `POST /api/groups/<group_id>/messages/<message_id>/appeal/review`

Frontend:

- persistent dismissible moderation banner with appeal access for flagged members
- appeal modal for flagged members
- admin review actions with inline admin notes inside the flagged messages panel
- copy-to-clipboard group ID action in the admin/info panel

### 7. Multilingual Moderation

ConvoEase supports multilingual moderation without changing the existing moderation backend design.

Approach:

- detect the likely message language
- preserve the original message for UI and source-of-truth moderation context
- provide a best-effort English translation as model-facing reference for compatibility
- store detected language and translation metadata for explainability

Useful for Hindi, Marathi, mixed-language, and other multilingual group conversations.

## Frontend UX Notes

- The message composer uses an auto-growing textarea
- `Enter` sends a message
- `Shift+Enter` inserts a new line
- Image and audio attach actions show a busy state while uploads are being processed
- Polling pauses while modal dialogs are open and resumes when they close

## Model Configuration

Main configuration lives in [config.py](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.8%20Local%20Deployment%20Test%20Working/config.py).

The app now supports one global model mode plus per-modality overrides:

- `CONVOEASE_MODEL_MODE`: default backend for all modalities, `local` or `api`
- `CONVOEASE_TEXT_BACKEND`
- `CONVOEASE_IMAGE_BACKEND`
- `CONVOEASE_AUDIO_BACKEND`

Current defaults in code:

- Global mode: `local`
- Text API model: `openai/gpt-oss-120b`
- Image API model: `meta-llama/llama-4-scout-17b-16e-instruct`
- Audio API transcription model: `whisper-large-v3-turbo`
- Audio API summary model: `llama-3.1-8b-instant`
- API base URL: `https://api.groq.com/openai/v1`

## Local Model Folder Layout

Default folders:

- [Models/Text](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.8%20Local%20Deployment%20Test%20Working/Models/Text)
- [Models/Image](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.8%20Local%20Deployment%20Test%20Working/Models/Image)
- [Models/Audio](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.8%20Local%20Deployment%20Test%20Working/Models/Audio)

How folder resolution works:

- For text and image local mode, you can point the path directly at a model export folder that contains `config.json`
- You can also point at a parent folder that contains exactly one child model folder with `config.json`
- If the folder contains zero models, startup fails with a clear error
- If the folder contains multiple candidate models, startup fails and asks you to point to the exact folder you want

Examples:

- `CONVOEASE_TEXT_MODEL_PATH=E:\models\Qwen2.5-3B-Instruct`
- `CONVOEASE_TEXT_MODEL_PATH=E:\Projects\...\Models\Text`
- `CONVOEASE_IMAGE_MODEL_PATH=E:\models\SmolVLM-500M-Instruct`

Important note for image local mode:

- The current image config defaults `CONVOEASE_IMAGE_MODEL_PATH` to the text-model directory in code
- That is intentional for the current multimodal setup, where a Gemma or similar vision-language model may live under `Models/Text`
- If you keep a separate vision model under `Models/Image`, set `CONVOEASE_IMAGE_MODEL_PATH` explicitly

Audio local mode behaves differently:

- `LocalAudioBackend` uses Whisper by model size, not by loading a Hugging Face folder from `Models/Audio`
- `CONVOEASE_WHISPER_SIZE` controls the local model, for example `base`, `small`, or `medium`
- Whisper downloads and caches model weights automatically on first run if they are not already cached

## Environment Variables

Common server settings:

- `CONVOEASE_HOST`
- `CONVOEASE_PORT`
- `CONVOEASE_DEBUG`
- `CONVOEASE_SECRET_KEY`
- `CONVOEASE_LOG_LEVEL`

API settings:

- `GROQ_API_KEY` or `CONVOEASE_API_KEY`
- `GROQ_API_URL` or `CONVOEASE_API_URL`

Important:

- Do not hardcode API keys in `config.py` or commit them to Git
- For PowerShell, set the key in the current shell before running the app:
  `$env:GROQ_API_KEY="gsk_..."`
- For a permanent Windows user-level variable:
  `[System.Environment]::SetEnvironmentVariable("GROQ_API_KEY", "gsk_...", "User")`

Text local settings:

- `CONVOEASE_TEXT_MODEL_PATH`
- `CONVOEASE_TEXT_MODEL_TYPE`
- `CONVOEASE_TEXT_DEVICE_PREFERENCE`
- `CONVOEASE_TEXT_ALLOW_CPU_OFFLOAD`

Image local settings:

- `CONVOEASE_IMAGE_MODEL_PATH`
- `CONVOEASE_IMAGE_MODEL_TYPE`

Audio local settings:

- `CONVOEASE_AUDIO_MODEL_PATH`
- `CONVOEASE_AUDIO_MODEL_TYPE`
- `CONVOEASE_WHISPER_SIZE`
- `FFMPEG_BINARY`

Hosted API model IDs:

- `CONVOEASE_TEXT_MODEL_ID`
- `CONVOEASE_IMAGE_MODEL_ID`
- `CONVOEASE_AUDIO_MODEL_ID`
- `CONVOEASE_AUDIO_SUMMARY_MODEL_ID`

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

If you want local text or image inference, also install the optional runtime packages listed in [requirements.txt](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.8%20Local%20Deployment%20Test%20Working/requirements.txt):

```bash
pip install torch transformers protobuf pillow numpy
```

### Local-Only Startup

PowerShell:

```powershell
$env:CONVOEASE_MODEL_MODE="local"
$env:CONVOEASE_TEXT_MODEL_PATH="E:\Projects\Personal\Convo-Ease\Phase 3 User Application\v3.8 Local Deployment Test Working\Models\Text"
$env:CONVOEASE_IMAGE_MODEL_PATH="E:\Projects\Personal\Convo-Ease\Phase 3 User Application\v3.8 Local Deployment Test Working\Models\Image"
$env:CONVOEASE_WHISPER_SIZE="base"
python run.py
```

Bash:

```bash
export CONVOEASE_MODEL_MODE=local
export CONVOEASE_TEXT_MODEL_PATH="/path/to/model/or/Models/Text"
export CONVOEASE_IMAGE_MODEL_PATH="/path/to/model/or/Models/Image"
export CONVOEASE_WHISPER_SIZE=base
python run.py
```

### Hybrid Startup

Example: local text plus hosted image/audio.

PowerShell:

```powershell
$env:CONVOEASE_MODEL_MODE="api"
$env:CONVOEASE_TEXT_BACKEND="local"
$env:CONVOEASE_IMAGE_BACKEND="api"
$env:CONVOEASE_AUDIO_BACKEND="api"
$env:GROQ_API_KEY="gsk_..."
$env:CONVOEASE_TEXT_MODEL_PATH="E:\models\Qwen2.5-3B-Instruct"
python run.py
```

### Hosted API Startup

PowerShell:

```powershell
$env:CONVOEASE_MODEL_MODE="api"
$env:GROQ_API_KEY="gsk_..."
python run.py
```

The app runs on:

- `http://localhost:5000`

## Local Runtime Notes

- Text local mode expects a full Hugging Face causal language model export with `config.json`
- Image local mode expects a full Hugging Face vision-language export with `config.json`
- Audio local mode uses `openai-whisper` and may download model weights into the user cache on first run
- If CUDA is available, text mode tries full GPU first and then auto offload unless `CONVOEASE_TEXT_ALLOW_CPU_OFFLOAD=false`
- If local models are enabled and CUDA is present, the Flask reloader is disabled automatically for stability
- `imageio-ffmpeg` is used as a fallback source for `ffmpeg.exe`, so a separate system `ffmpeg` install is often unnecessary

## Troubleshooting Local Models

### `No local text model was found`

Point `CONVOEASE_TEXT_MODEL_PATH` to a directory that either:

- contains `config.json` directly, or
- contains exactly one child directory with `config.json`

### `Multiple local text models were found`

Set `CONVOEASE_TEXT_MODEL_PATH` to the exact child model folder you want to load instead of its parent directory.

### Text model crashes or reload instability on Windows/CUDA

Current fixes already built into the app:

- synchronous Hugging Face loading is forced through `HF_DEACTIVATE_ASYNC_LOAD=1`
- lazy loading delays model initialization until the first request
- Flask reloader is disabled when local CUDA usage is detected

### CUDA out-of-memory during local inference

- Reduce model size
- Set `CONVOEASE_TEXT_ALLOW_CPU_OFFLOAD=true`
- Force CPU for text with `CONVOEASE_TEXT_DEVICE_PREFERENCE=cpu`
- Use API mode for one or more modalities

### Whisper fails to transcribe local audio

- Confirm `openai-whisper` and `imageio-ffmpeg` are installed
- If needed, point `FFMPEG_BINARY` at a valid `ffmpeg.exe`
- Try a smaller Whisper model such as `base`

## Testing Architecture

Testing is isolated under [testing](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.8%20Local%20Deployment%20Test%20Working/testing).

- Layer 1: `pytest` API and backend coverage in [testing/pytest](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.8%20Local%20Deployment%20Test%20Working/testing/pytest)
- Layer 2: Playwright browser scenarios in [testing/e2e](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.8%20Local%20Deployment%20Test%20Working/testing/e2e)
- Layer 3: Locust load tests in [testing/stress](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.8%20Local%20Deployment%20Test%20Working/testing/stress)

Quick start:

```bash
pytest testing/pytest -q
pytest testing/e2e -q
python testing/stress/run_mock_server.py
locust -f testing/stress/locustfile.py --host http://127.0.0.1:5000
```

## Notes

- Existing CSV files are automatically schema-migrated on startup for new group and message fields
- Media uploads are stored under `database/media`
- The moderation engine treats admin rules as the primary decision boundary, while recent chat context is supporting reference
- Multilingual moderation uses language detection and translation as a compatibility layer; the original message remains visible in the UI
