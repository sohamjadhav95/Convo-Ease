# ConvoEase v3.2 — AI-Moderated Group Chat

A production-grade group chat application with real-time AI moderation. Messages are validated against admin-defined rules using a plugin-style AI engine before appearing in the chat.

---

## Architecture

```
v3.2 Architecutral Changes/
├── run.py                         ← Start here (entry point)
├── main.py                        ← Flask app factory + REST API routes
├── config.py                      ← All settings (paths, API, logging)
├── core_processing_engine.py      ← Plugin-style AI engine
├── requirements.txt               ← Python dependencies
├── README.md
│
├── database/
│   ├── Database_processing/       ← Data access layer
│   │   ├── db_manager.py          ← CSV init, read/write helpers
│   │   ├── user_store.py          ← User CRUD
│   │   ├── group_store.py         ← Group CRUD
│   │   └── message_store.py       ← Message CRUD
│   └── Databases/                 ← CSV data files (auto-created)
│
├── Frontend/                      ← HTML/CSS/JS (served by Flask)
│   ├── index.html                 ← Single-page app shell
│   ├── css/style.css              ← Design system (dark theme)
│   ├── js/app.js                  ← SPA logic, API calls, routing
│   └── img/                       ← Static assets
│
├── logs/                          ← Structured logs (auto-created)
└── tests/                         ← Test files
```

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python run.py
```

### 3. Open in Browser
Navigate to **http://localhost:5000**

---

## Configuration

All settings are in `config.py` and can be overridden via environment variables:

| Variable | Default | Description |
|---|---|---|
| `CONVOEASE_API_KEY` | (built-in) | OpenRouter API key |
| `CONVOEASE_MODEL_NAME` | `openai/gpt-oss-120b:free` | AI model name |
| `CONVOEASE_MODEL_MODE` | `api` | `api` or `local` |
| `CONVOEASE_LOCAL_MODEL_PATH` | (empty) | Path to local model |
| `CONVOEASE_HOST` | `0.0.0.0` | Server host |
| `CONVOEASE_PORT` | `5000` | Server port |
| `CONVOEASE_DEBUG` | `true` | Debug mode |
| `CONVOEASE_LOG_LEVEL` | `INFO` | Logging level |

---

## Core Processing Engine

The engine uses a **plugin architecture**:

- **`ProcessingPlugin`** — Base class with `process()`, `get_input_schema()`, `get_output_schema()`
- **`TextModerationPlugin`** — Current: validates messages via API. Supports switching to local models.
- **`ProcessingEngine`** — Registry that dispatches requests to registered plugins.

### Adding a New Plugin
```python
class ImageProcessingPlugin(ProcessingPlugin):
    name = "image_processing"
    
    def get_input_schema(self):
        return {"image_data": "bytes", "task": "str"}
    
    def get_output_schema(self):
        return {"result": "dict", "status": "str"}
    
    def process(self, input_data, context=None):
        # Your processing logic here
        pass
```

### Switching to Local Model
In `config.py`, set:
```python
MODEL_CONFIG = {
    "mode": "local",
    "model_path": "path/to/your/model",
    "model_type": "llama"
}
```

---

## Portability

- **Zero hardcoded paths** — all paths relative to project root
- **No system dependencies** — just install Python packages and run
- **Copy & deploy** — copy the folder to any Windows machine, install requirements, run

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3, Flask |
| Frontend | HTML5, CSS3, JavaScript (vanilla) |
| AI Engine | OpenAI SDK → OpenRouter API |
| Database | CSV files (via pandas) |
| Logging | Python `logging` with rotation |
