# ConvoEase v3.5 — AI-Powered Group Chat with Real-Time Moderation

> **Industry-grade, plugin-based conversational platform** featuring AI content moderation across text, images, and audio. Built with a Python/Flask backend, vanilla JS SPA frontend, and a dark/light multi-accent theme system.

---

## Features at a Glance

| Feature | Details |
|---|---|
| **Text Moderation** | AI checks messages against custom group rules before delivery |
| **Image Moderation** | Vision AI summarises images; summary moderated against rules |
| **Audio Moderation** | Google Speech → AI summary → moderated against rules |
| **Role-based Access** | Admins see full panel (rules, flagged, reports); members see rules only |
| **Theme Switcher** | Dark/Light mode + 5 accent palettes (Violet, Blue, Emerald, Rose, Amber) |
| **Persistent Media** | Images and audio saved to disk; accessible after page reload |
| **Moderation Report** | Per-group analytics: pass/flag rates, member activity, flagged reasons |

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.11+, Flask, Flask-CORS |
| AI / ML | OpenRouter API (configurable model), Google Speech Recognition (free) |
| Audio Processing | `pydub`, `SpeechRecognition` |
| Database | CSV flat-file (pandas), auto-migrated schema |
| Frontend | Vanilla HTML/CSS/JS SPA (no frameworks) |
| Fonts | Inter (Google Fonts) |

---

## Project Structure

```
v3.5 Deployment Version/
├── main.py                       # Flask app factory, all API routes
├── config.py                     # Environment, model config, paths
├── core_processing_engine.py     # Plugin system: Text, Image, Audio moderation
│
├── database/
│   ├── Database_processing/
│   │   ├── db_manager.py         # CSV read/write, schema init & migration
│   │   ├── user_store.py         # Auth: register, login, profile
│   │   ├── group_store.py        # Groups: create, join, rules, members
│   │   └── message_store.py      # Messages: save, load, flags, analytics
│   └── *.csv                     # Flat-file data (auto-created on first run)
│
├── Frontend/
│   ├── index.html                # SPA shell
│   ├── css/style.css             # Design system (CSS custom properties)
│   └── js/app.js                 # All frontend logic + ThemeManager
│
├── media/
│   ├── image/                    # Persisted uploaded images
│   └── audio/                    # Persisted uploaded audio
│
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Prerequisites

- Python 3.11+
- pip

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file **or** export the variable in your shell:

```bash
# Required — your OpenRouter API key
export CONVOEASE_API_KEY="sk-or-v1-..."
```

> The key is used for text moderation, image summarization, and audio summarization.  
> Audio **transcription** uses Google's free Speech Recognition API (no key needed).

### 4. Run the Server

```bash
python main.py
```

Then open **http://localhost:5000** in your browser.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `CONVOEASE_API_KEY` | Yes | OpenRouter API key for AI moderation & summarization |

The model, base URL, vision model, and plugin list are configured in **`config.py`**.

---

## REST API Reference

### Auth

| Method | Endpoint | Body | Description |
|---|---|---|---|
| `POST` | `/api/auth/register` | `{username, password, full_name}` | Register new user |
| `POST` | `/api/auth/login` | `{username, password}` | Login |

### Groups

| Method | Endpoint | Body / Params | Description |
|---|---|---|---|
| `GET` | `/api/groups?username=` | — | Get user's groups |
| `POST` | `/api/groups` | `{group_name, password, admin_username, rules}` | Create group |
| `POST` | `/api/groups/join` | `{group_id, password, username}` | Join group |
| `GET` | `/api/groups/<id>` | — | Group details |
| `GET` | `/api/groups/<id>/members` | — | Member list |
| `PUT` | `/api/groups/<id>/rules` | `{rules, username}` | Update rules (admin only) |

### Messages

| Method | Endpoint | Body | Description |
|---|---|---|---|
| `GET` | `/api/groups/<id>/messages` | — | Get visible (PASS) messages |
| `GET` | `/api/groups/<id>/messages/flagged` | — | Get flagged messages |
| `POST` | `/api/groups/<id>/messages` | `{username, message}` | Send text message |
| `POST` | `/api/groups/<id>/images` | `{username, image_data (base64), mime_type}` | Send image |
| `POST` | `/api/groups/<id>/audio` | `{username, audio_data (base64), mime_type}` | Send audio |
| `GET` | `/api/groups/<id>/report` | — | Moderation analytics report |

### System

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/settings` | Current engine config (safe view) |

---

## Theme System (v3.5)

Preferences are stored in `localStorage` and applied immediately on load (no flash).

### Toggle via UI
Open **Settings → Appearance** to:
- Switch between **Dark** and **Light** mode
- Pick an accent colour: **Violet** · **Blue** · **Emerald** · **Rose** · **Amber**

### How It Works

```
localStorage["ce_theme"]  = "dark" | "light"
localStorage["ce_accent"] = "violet" | "blue" | "emerald" | "rose" | "amber"
    ↓
ThemeManager.applyPersisted()  →  sets data-theme / data-accent on <html>
    ↓
CSS [data-theme="light"] { ... }  and  [data-accent="blue"] { ... }  override the root tokens
```

---

## Database Schema

All data is stored in CSV files under `database/`.

### `group_chats.csv` (messages)

| Column | Description |
|---|---|
| `message_id` | UUID |
| `group_id` | Parent group |
| `username` | Sender |
| `message` | Content (`[IMAGE]` / `[AUDIO]` for media) |
| `status` | `PASS` or `FLAGGED` |
| `reason` | Moderation block reason |
| `summary` | AI-generated summary (image/audio) |
| `media_url` | Server-relative persistent file URL |
| `group_rules` | Snapshot of active rules at send time |
| `timestamp` | Send time |

### `groups.csv`

| Column | Description |
|---|---|
| `group_id` | 6-char unique ID |
| `group_name` | Display name |
| `admin_username` | Creator / admin |
| `password` | Join password |
| `rules` | Current moderation rules |
| `created_at` | Creation timestamp |

---

## Plugin Architecture

`core_processing_engine.py` uses a simple registry pattern:

```python
engine.register_plugin(TextModerationPlugin(config))
engine.register_plugin(ImageModerationPlugin(config, vision_config))
engine.register_plugin(AudioModerationPlugin(config))

result = engine.process("text_moderation", { "message": "...", "rules": "...", ... })
```

Each plugin implements a `process(input_data, context) → dict` method and exposes a `plugin_name` property.

---

## Moderation Flow

```
Text:  User message → TextModerationPlugin → PASS / FLAGGED
Image: base64 → save to disk → ImageModerationPlugin (vision summarize → text moderate) → PASS / FLAGGED
Audio: base64 → save to disk → AudioModerationPlugin:
           Step 1: Google SpeechRecognition (free) → transcript
           Step 2: AI summarize transcript (1-2 sentences)
           Step 3: TextModerationPlugin (moderate summary against rules)
       → PASS / FLAGGED
```

---

## License

This project is for educational / research purposes.
