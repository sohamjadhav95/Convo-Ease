# Testing Workspace

This project now keeps test code isolated in a dedicated top-level `testing/` workspace instead of mixing test files with the main application folders.

## Layout

```text
testing/
+-- pytest/        # Layer 1: fast API and backend tests
+-- e2e/           # Layer 2: Playwright browser flows
+-- stress/        # Layer 3: Locust load testing
+-- shared/        # Shared test harness and AI mocks
+-- artifacts/     # Generated reports, traces, screenshots, temp runtimes
```

## Layer 1

Run the backend suite:

```bash
pytest testing/pytest -q
```

Highlights:

- Redirects CSV and media writes into a disposable runtime sandbox
- Uses deterministic mocked AI for text, image, audio, summaries, and appeals
- Covers auth, groups, message moderation, media flows, reports, and rule suggestions

## Layer 2

Install browsers once:

```bash
playwright install chromium
```

Run the E2E suite:

```bash
pytest testing/e2e -q
```

Highlights:

- Starts an isolated local Flask server per test session
- Uses multiple browser pages to model separate users
- Keeps screenshots, traces, and future videos inside `testing/artifacts/`

## Layer 3

Start the mocked backend for load testing:

```bash
python testing/stress/run_mock_server.py
```

Then run Locust:

```bash
locust -f testing/stress/locustfile.py --host http://127.0.0.1:5000
```

Recommended report path:

- Save Locust screenshots and exports under `testing/artifacts/`
