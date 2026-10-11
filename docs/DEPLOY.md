# ConvoEase Deployment & Infrastructure Guide

This guide provides end-to-end instructions for deploying ConvoEase on the internet using 100% free hosting tiers, along with detailed documentation on the keep-awake hook system, sleep prevention, and workspace quota management.

---

## 1. Architecture & Free Tier Stack

| Component | Provider | Role | Free Tier Specifications |
|---|---|---|---|
| **Web Service** | [Render](https://render.com) | Python web server & frontend | 512 MB RAM, 0.1 CPU, 750 free instance hours/month |
| **Database** | [Neon](https://neon.tech) | Persistent PostgreSQL | 0.5–1 GB storage, automated branching, survives redeploys |
| **AI Engine** | [Google Gemini](https://aistudio.google.com/apikey) | Moderation (Text, Vision, Audio) | Free tier API access (RPM / RPD limits) |

> [!IMPORTANT]
> **Why an external database?**  
> Free cloud hosts (Render, Koyeb, etc.) use ephemeral disks that wipe completely on every restart, redeploy, or wake cycle. Storing users, messages, and uploaded media directly on the server disk results in complete data loss. Neon keeps all data and media safe across restarts.

---

## 2. Step-by-Step Deployment Setup

### Step 1: Obtain a Google Gemini API Key (2 minutes)
1. Go to [Google AI Studio](https://aistudio.google.com/apikey) and sign in.
2. Click **Create API key** and copy it.

### Step 2: Provision the PostgreSQL Database (3 minutes)
1. Sign up at [Neon](https://neon.tech) and create a project (e.g., `convoease-db`).
2. Select the cloud region closest to your primary users (e.g., Singapore for Asia/India).
3. In the project dashboard, click **Connect** and copy the connection string. It looks like:
   ```text
   postgresql://username:password@ep-sample-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```
   *(Note: `?sslmode=require` is required for encrypted communication).*
4. ConvoEase automatically creates all required tables and relationships on first launch.

> [!TIP]
> **Using Vercel Storage:** If you already use Vercel, you can provision the same free Neon database from your Vercel Dashboard: **Storage** → **Create Database** → **Neon** → Free Plan, then copy `DATABASE_URL`.

### Step 3: Deploy via Render Blueprint (5 minutes)
1. Fork or push this repository to your GitHub account.
2. Sign in to [Render](https://render.com) with GitHub.
3. Click **New +** → **Blueprint**.
4. Select the `Convo-Ease` repository and your deployment branch (`main`).
5. Render reads [`render.yaml`](../render.yaml) from the repository root and prompts you for:
   - `GEMINI_API_KEY`: Key from Step 1.
   - `DATABASE_URL`: Connection string from Step 2.
6. Click **Apply**. Render will build and deploy the application using Gunicorn and Python 3.12.
7. Once deployed, open your live URL (`https://<service-name>.onrender.com`).

---

## 3. Keep-Awake Hook & Sleep Prevention System

### Why Render Free Services Sleep
Render's free web tier puts instances to sleep after **15 minutes of zero incoming HTTP traffic**. When a sleeping service receives a request, Render spins the container back up, resulting in a cold-start delay of **30 to 60 seconds**.

---

### Method A: The Repository GitHub Action Hook (`keep-awake.yml`)

The repository includes a built-in scheduled GitHub Action workflow at [`.github/workflows/keep-awake.yml`](../.github/workflows/keep-awake.yml).

```yaml
name: Keep app awake

on:
  schedule:
    - cron: "*/10 * * * *"   # Scheduled every 10 minutes
  workflow_dispatch:        # Allows manual trigger

jobs:
  ping:
    if: ${{ vars.APP_URL != '' }}
    runs-on: ubuntu-latest
    timeout-minutes: 3
    steps:
      - name: Ping health check
        run: curl --fail --silent --show-error --max-time 100 --retry 2 --retry-delay 5 "${APP_URL%/}/healthz"
        env:
          APP_URL: ${{ vars.APP_URL }}
```

#### How to Configure the Hook:
1. Open your GitHub repository in your browser.
2. Go to **Settings** → **Secrets and variables** → **Actions**.
3. Click on the **Variables** tab (*NOT* the Secrets tab).
4. Click **New repository variable**:
   - **Name:** `APP_URL`
   - **Value:** Your Render live URL (e.g., `https://convoease-prod.onrender.com`)
5. Click **Add variable**.

> [!CAUTION]
> **Critical Caveat regarding GitHub Actions Cron Scheduling:**  
> GitHub Actions schedules run on a shared, low-priority queue. As explicitly documented by GitHub:
> *"The schedule event can be delayed during periods of high loads... queued jobs may be dropped."*  
> High-frequency cron jobs (`*/10 * * * *`) on public repositories are frequently delayed by **20 minutes to several hours** during peak traffic. Because Render's inactivity threshold is strictly **15 minutes**, a single delayed or dropped GitHub Actions run allows the Render instance to fall asleep.

---

### Method B: Dedicated Uptime Monitor (Recommended / 100% Reliable)

For guaranteed, zero-latency wakefulness without depending on GitHub's variable runner load, use an external uptime monitor:

#### 1. Setup with [UptimeRobot](https://uptimerobot.com) (Free, 2 minutes)
1. Sign up for a free UptimeRobot account (no credit card required).
2. Click **Add New Monitor**:
   - **Monitor Type:** `HTTP(s)`
   - **Friendly Name:** `ConvoEase Health Check`
   - **URL (or IP):** `https://<your-render-app>.onrender.com/healthz`
   - **Monitoring Interval:** `5 minutes` (well within Render's 15-minute idle limit)
3. Click **Create Monitor**.
4. **Result:** UptimeRobot sends an HTTP GET request to `/healthz` like clockwork every 5 minutes from distributed edge nodes, guaranteeing the app never sleeps.

#### 2. Alternative: Scheduled Sleep with [cron-job.org](https://cron-job.org)
If you want to keep the app awake during the day but let it sleep late at night to conserve monthly hours:
- Set up an HTTP GET request to `https://<your-app>.onrender.com/healthz` running every 10 minutes **only between 07:00 and 01:00 UTC**.

---

## 4. Render Monthly Free Hours (750 Hours) Strategy

Render allocates **750 free instance hours per calendar month per workspace/account**, shared across all free services.

### Monthly Math Breakdown
* **Always-on service in a 30-day month (April, June, Sept, Nov):**  
  $30 \times 24 = 720\text{ hours}$ (Leaves **30 safe hours** of headroom).
* **Always-on service in a 31-day month (Jan, Mar, May, Jul, Aug, Oct, Dec):**  
  $31 \times 24 = 744\text{ hours}$ (Leaves **6 hours** of margin).

### Handling Multiple Services in the Same Account
* **Sleeping services do NOT consume hours:** Instances only consume hours when active. If you have other services in your account that sleep and run for less than 2 hours per month combined, they consume only ~2–4 hours total.
* **Safety Margin Warning:** In a 31-day month, $744\text{ hrs} + 4\text{ hrs} = 748\text{ hrs}$, which is within 2 hours of the 750-hour cap. If redeploys or build times push usage past 750 hours, Render suspends all free services until the 1st of the next month.

### Best Practices to Prevent Suspension:
1. **Dedicated Workspace:** Create a separate, dedicated Render workspace or account specifically for ConvoEase so it has its own unshared 750-hour quota.
2. **Scheduled Night Window:** Using `cron-job.org` to ping only 18 hours/day (e.g. 7 AM – 1 AM) consumes only $18 \times 31 = 558\text{ hours/month}$, leaving ~190 hours of buffer.

---

## 5. Docker Deployment

The repository includes a multi-stage production [`Dockerfile`](../Dockerfile) optimized for container runtimes:

```bash
# Build the production image
docker build -t convoease:latest .

# Run locally with required configuration
docker run -d \
  -p 7860:7860 \
  -e CONVOEASE_ENV=production \
  -e CONVOEASE_SECRET_KEY=your_random_secret_hex_key \
  -e GEMINI_API_KEY=your_gemini_api_key \
  -e DATABASE_URL="postgresql://user:pass@ep-host.neon.tech/neondb?sslmode=require" \
  convoease:latest
```

The container exposes port `7860` (compatible with Hugging Face Spaces and standard PaaS) and includes built-in container health checking on `/healthz`.

---

## 6. Environment Variables Reference

| Variable | Default | Purpose |
|---|---|---|
| `CONVOEASE_ENV` | `development` | Set to `production` in live environments (activates secure cookies, error handling). |
| `CONVOEASE_SECRET_KEY` | — | Cryptographic secret for signing session cookies. Auto-generated by Render. Generate manually: `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `DATABASE_URL` | local SQLite | Connection string for PostgreSQL (`postgresql://...`). |
| `GEMINI_API_KEY` | — | Google Gemini API key. |
| `CONVOEASE_AI_PROVIDER` | `gemini` | `gemini`, `groq`, `nvidia`, or `custom`. |
| `GROQ_API_KEY` | — | API key when using Groq provider. |
| `NVIDIA_API_KEY` | — | API key when using NVIDIA NIM provider. |
| `CONVOEASE_TEXT_MODEL_ID` | provider default | Override text moderation model. |
| `CONVOEASE_IMAGE_MODEL_ID` | provider default | Override image moderation model. |
| `CONVOEASE_AUDIO_MODEL_ID` | provider default | Override audio transcription model. |
| `CONVOEASE_MAX_IMAGE_MB` | `8` | Maximum allowable image upload size in megabytes. |
| `CONVOEASE_MAX_AUDIO_MB` | `10` | Maximum allowable voice note upload size in megabytes. |
| `CONVOEASE_RATE_LIMITS` | `true` | Rate-limiting protection per user session (30 msgs / 10 uploads per min). |
| `WEB_CONCURRENCY` | `1` | Number of Gunicorn worker processes (keep at `1` on 512 MB instances). |
| `PORT` | `5000` (`7860` in Docker) | Port the web server listens on. Injected automatically by Render/Cloud hosts. |

---

## 7. Verification & Health Monitoring

Test your live service at:
```text
https://<your-domain>/healthz
```

A healthy response returns HTTP 200 with JSON status:
```json
{
  "status": "ok",
  "version": "5.0",
  "database": "ok",
  "ai": {
    "provider": "gemini",
    "text": "ready",
    "image": "ready",
    "audio": "ready"
  }
}
```

* If `"database"` returns `"error"`, verify your `DATABASE_URL` credentials and ensure `?sslmode=require` is present.
* If any AI capability says `"unavailable"`, check server logs for invalid API keys or quota exhaustion.
