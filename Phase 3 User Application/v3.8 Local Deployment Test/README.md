# ConvoEase v3.6

ConvoEase is a hybrid AI-powered group chat platform with moderation for text, image, and audio messages. It supports local model folders for offline or demo use and Groq-hosted inference for deployment.

## Highlights

- Text, image, and audio moderation through a shared plugin-based processing engine
- Smart chat summarization with one-click catch-up for members
- Moderation explainability dashboard with reasons, categories, trends, and message logs
- Toxicity and compliance heatmap with per-member trust scores and risk badges
- Smart rule suggestions during group creation and admin rule editing
- Context-aware moderation sensitivity per group: `Strict`, `Moderate`, or `Relaxed`
- Appeal workflow for flagged members with AI re-evaluation and admin final review
- Multilingual moderation using language detection plus model-facing English translation fallback
- Persistent media storage and CSV-backed analytics with automatic schema migration

## Feature Overview

### 1. Smart Chat Summarization

Any member can click `Catch me up` in the chat header to get a concise recent-conversation summary.

Backend:

- `GET /api/groups/<group_id>/summary?limit=25`

Frontend:

- Chat header catch-up button
- Summary modal for all members

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

### 4. Smart Rule Suggestions

Admins and group creators can request AI suggestions to improve moderation rules.

Backend:

- `POST /api/rules/suggest`

Frontend:

- create-group rules editor
- admin rules editor

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

- appeal modal for flagged members
- admin review actions inside the flagged messages panel

### 7. Multilingual Moderation

ConvoEase now supports multilingual moderation without changing the existing moderation backend design.

Approach:

- detect the likely message language
- preserve the original message for UI and source-of-truth moderation context
- provide a best-effort English translation as model-facing reference for compatibility
- store detected language and translation metadata for explainability

Useful for Hindi, Marathi, mixed-language, and other multilingual group conversations.

## Hybrid Model Architecture

Each modality can run independently in either:

- `local` mode: load from `Models/Text`, `Models/Image`, `Models/Audio`
- `api` mode: use hosted model IDs through the configured OpenAI-compatible endpoint

Edit [config.py](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.7%20Major%20Featurs%20Addition/config.py):

- `TEXT_MODEL_CONFIG`
- `IMAGE_MODEL_CONFIG`
- `AUDIO_MODEL_CONFIG`

Important fields:

- `backend`
- `base_url`
- `api_model_id`
- `local_model_path`
- `local_model_type`
- `api_summary_model_id` for audio transcript summarization

## Default Local Model Folders

- [Models/Text](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.7%20Major%20Featurs%20Addition/Models/Text)
- [Models/Image](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.7%20Major%20Featurs%20Addition/Models/Image)
- [Models/Audio](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.7%20Major%20Featurs%20Addition/Models/Audio)

## Current Hosted Defaults

Current hosted defaults in [config.py](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.7%20Major%20Featurs%20Addition/config.py):

- Text moderation and text tasks: `openai/gpt-oss-120b`
- Image moderation model: `meta-llama/llama-4-scout-17b-16e-instruct`
- Audio transcription model: `whisper-large-v3-turbo`
- Audio summary model: `llama-3.1-8b-instant`
- Base URL: `https://api.groq.com/openai/v1`

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Set your API key:

```bash
export GROQ_API_KEY="gsk_..."
```

Run the app:

```bash
python run.py
```

Open:

- `http://localhost:5000`

## Testing Architecture

The project now keeps testing fully isolated under [testing](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.7%20Major%20Featurs%20Addition/testing).

- Layer 1: `pytest` API and backend coverage in [testing/pytest](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.7%20Major%20Featurs%20Addition/testing/pytest)
- Layer 2: Playwright browser scenarios in [testing/e2e](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.7%20Major%20Featurs%20Addition/testing/e2e)
- Layer 3: Locust load tests in [testing/stress](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.7%20Major%20Featurs%20Addition/testing/stress)

Quick start:

```bash
pytest testing/pytest -q
pytest testing/e2e -q
python testing/stress/run_mock_server.py
locust -f testing/stress/locustfile.py --host http://127.0.0.1:5000
```

## Notes

- Local runtime dependencies for transformer-based inference remain optional in [requirements.txt](/E:/Projects/Personal/Convo-Ease/Phase%203%20User%20Application/v3.7%20Major%20Featurs%20Addition/requirements.txt).
- Existing CSV files are automatically schema-migrated on startup for new group and message fields.
- The moderation engine treats admin rules as the primary decision boundary, while recent chat context is supporting reference.
- Multilingual moderation uses language detection and translation as a compatibility layer; the original message remains visible in the UI.
