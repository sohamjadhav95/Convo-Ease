# Part 2: Implementation details from source

### Evaluation prompt template
**File**: `core_processing_engine.py` (lines 132-171)
```
You are a strict Group Chat Moderator.

ADMIN RULES:
{rules}

MODERATION SENSITIVITY:
{moderation_sensitivity}
{sensitivity_instructions}

CHAT CONTEXT USE MODE:
{context_mode}

MODERATION PRINCIPLES:
1. The ADMIN RULES are the primary decision boundary.
2. CHAT CONTEXT is only for understanding references, short replies, follow-up questions, or pronouns.
3. Do not narrow a broad rule to the latest micro-topic in the chat.
4. If a message fits the ADMIN RULES on its own, it should PASS even if it changes the subtopic.
5. Only use context to rescue ambiguous messages like "what happened?", "yes", "same here", "when?", or similar short replies.
6. Do not FLAG a message just because it is different from the last few messages, unless it clearly violates or falls outside the ADMIN RULES.

EMOJI HANDLING:
- Evaluate emoji by their meaning and intent, not just their appearance.
- The 🤬 emoji (face with symbols on mouth) represents profanity or strong frustration. Flag it if rules prohibit profanity or disrespectful language.
- Skin-tone modified emoji and combinations that could carry discriminatory intent should be evaluated by context and intent.
- A single emoji like 👍 or 😊 used as a reaction is almost always harmless.
- Do not flag emoji just because they look unusual - focus on whether the intent violates the rules.

CHAT CONTEXT:
{context_str}

TASK:
Validate the NEW message against the rules and context.
If the message is in a non-English language or script, evaluate its meaning and intent just as you would for English.
Be aware that users may use character substitutions (leetspeak) to disguise prohibited content. Evaluate the phonetic and visual meaning, not just literal characters.
Reply in one of these formats only:
PASS
FLAGGED <reason>

NEW MESSAGE: "{message}"{normalized_line}
```
**Sensitivity Instructions** (lines 337-349):
Strict: `"Strict mode: flag borderline content, mild disrespect, and messages that are even slightly off-topic. When uncertain between PASS and FLAGGED, lean toward FLAGGED."`
Relaxed: `"Relaxed mode: only flag clear and meaningful rule violations. Allow harmless digressions, mild tone issues, and ambiguous content unless the violation is obvious."`
Moderate: `"Moderate mode: enforce the rules consistently without over-flagging. Flag clear violations and clear off-topic messages, but do not punish minor ambiguity."`

**Context-use Mode strings** (line 126): `"required"` and `"reference_only"`.
**System message**: A separate system message is used: `"You are a strict Group Chat Moderator."` (line 108).

### Plugin interface
**File**: `core_processing_engine.py` (lines 46-60)
Class: `ProcessingPlugin`
```python
    def get_input_schema(self): ...
    def get_output_schema(self): ...
    @abstractmethod
    def process(self, input_data, context=None): ...
```
**File**: `backend_factory.py` (line 12-58 for backend factory resolution).
Task is bound to a backend in `TextModerationPlugin.__init__` (line 72 `core_processing_engine.py`): `self._backend = get_text_backend(model_config)`.
Concrete plugins: `TextModerationPlugin`, `ImageModerationPlugin`, `AudioModerationPlugin`.

### Send-path integration
**File**: `main.py` (lines 718-850)
1. Request payload is extracted (`username`, `message`, `group_id`).
2. Checks DB for group details (`GroupStore.get_group_details`).
3. Fetches up to 6 recent messages as context (`MessageStore.get_visible_messages`).
4. Extracts `text_moderation` plugin.
5. If rules exist, it calls `engine.process` with the plugin to run moderation.
6. If API throws error or flags system unavailable, returns HTTP 503 (fail closed). 
7. If passed, saves message to DB (`status`="PASS"). Else saves with `status`="FLAGGED" and reason.
**Withheld state data model**: `database/Database_processing/message_store.py` (lines 61-90). Field name: `status`, Type: String, Values: `"PASS"`, `"FLAGGED"`, `"DELETED"`.
**Query to exclude flagged**: `visible = msgs[msgs["status"].isin(["PASS", "DELETED"])].sort_values("timestamp")`
**Fail-closed handling**: If backend fails or times out, it throws an exception logged by `main.py` and returns `{"status": "UNAVAILABLE", "message": "Text moderation is temporarily unavailable. Please try again later."}` with status `503`. Timeout value is 90 seconds (from `image_api_backend.py` configuration) or standard library defaults.

### Context slice
**File**: `main.py` (line 735), `core_processing_engine.py` (lines 173-199)
How many prior messages: 6 (`recent[-6:]`). No explicit character/token cap.
Mode selection rule (`_message_needs_context`):
```python
        if len(tokens) <= 4: return True
        if text in short_reference_phrases: return True
        if len(tokens) <= 8 and any(token in pronoun_markers for token in tokens): return True
        if text.endswith("?") and len(tokens) <= 6: return True
```

### Pre-filters
**File**: `core_processing_engine.py`
- **Injection** (lines 210-245): 28 patterns, substring match. Ex: `"ignore previous"`, `"act as if"`.
- **Spam** (lines 257-271): Checks for lorem ipsum (4 patterns, e.g. `"lorem ipsum"`), unique chars <= 2 if length >= 8, or unique words <= 2 if words >= 5.
- **Leetspeak** (lines 276-290): Substitution character map size 13. Ex: `"0": "o", "1": "i", "3": "e"`.

### Batching and concurrency
**File**: `testing/analysis/run_live_policy_benchmark.py` (lines 65-68, 165-192)
Batch size constant: `--batch-size`, default 10.
Run concurrently: Yes, via `ThreadPoolExecutor(max_workers=workers)` (default 3).
Retry policy: Exponential backoff (`time.sleep(2 ** (attempt - 1))`), max 3 retries.

### Inference configuration
**File**: `testing/analysis/run_live_policy_benchmark.py` (lines 172-181)
Model: `os.getenv("CONVOEASE_TEXT_MODEL_ID", "openai/gpt-oss-120b")`
Params sent: `temperature=0`, `top_p=1`, `max_tokens=max(512, len(batch) * 80)`.
For general API (`backends/api_backend.py`): `temperature=0.2`, `top_p=1`, `max_tokens=256` (or 512).

### Stack
**Language/Version**: Python 3.10+
**Web framework**: Flask>=3.1.3
**Database**: CSV file-based (`DBManager` and `pandas`)
**ORM**: None.
**Transcriber**: `whisper` library (model size: `base` by default), invoked locally using Python API (loaded on startup, processes local temporary audio files extracted using `imageio_ffmpeg`).

### Follow-up: Batching semantics
**File**: `testing/analysis/run_live_policy_benchmark.py`
One API call carries all ten messages in the batch.
Request body code (lines 100-144):
```python
def build_prompt(condition_name, batch):
    condition = CONDITIONS[condition_name]
    if condition["mode"] == "organization":
        boundary = (
            "For each item, ADMIN RULES are the primary decision boundary. Use chat context "
            "only to resolve references or short ambiguous replies. Do not narrow broad admin "
            "rules to the latest micro-topic. Evaluate disguised wording and non-English text "
            "by meaning and intent."
        )
        payload = [
            {
                "id": row["row_id"],
                "message": row["message"],
                "admin_rules": row["rules"],
                "chat_context": row.get("context") or "(no prior messages)",
            }
            for row in batch
        ]
    else:
        boundary = (
            "Ignore organization-specific rules. Apply only the generic safety taxonomy in "
            "the sensitivity instruction, using chat context only when needed for meaning."
        )
        payload = [
            {
                "id": row["row_id"],
                "message": row["message"],
                "chat_context": row.get("context") or "(no prior messages)",
            }
            for row in batch
        ]

    return f"""Classify every item as PASS or FLAGGED.

POLICY MODE: {condition["mode"]}
SENSITIVITY: {condition["sensitivity"]}
SENSITIVITY INSTRUCTION: {condition["instruction"]}
DECISION BOUNDARY: {boundary}

Return ONLY a JSON array with one object per input, preserving IDs:
[{{"id":"0","decision":"PASS"}},{{"id":"1","decision":"FLAGGED"}}]

INPUT ITEMS:
{json.dumps(payload, ensure_ascii=True)}
"""
```
Parsing response into per-message verdicts (lines 153-158):
```python
    found = {}
    for item in parsed:
        row_id = str(item.get("id", "")).strip()
        decision = str(item.get("decision", "")).strip().upper()
        if row_id in expected_ids and decision in {POSITIVE, NEGATIVE}:
            found[row_id] = decision
```
The JSON object `id` field maps the verdict directly back to the `row_id` of the original item.

### Follow-up: Latency semantics
**File**: `testing/analysis/run_live_policy_benchmark.py`
`batch_latency_ms` measures one round trip spanning the evaluation of all ten messages via a single batched API call.
Timing code (lines 170-182):
```python
        started = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a precise moderation classifier."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                top_p=1,
                max_tokens=max(512, len(batch) * 80),
            )
            latency_ms = (time.perf_counter() - started) * 1000
```
The three-worker thread pool operates **across** batches, not within a batch. Ten messages are bundled per task, and up to three such tasks run concurrently (lines 309-315).

### Follow-up: Retries
**File**: `paper_artifacts/benchmark_raw_1200.csv`
- Distribution: `attempt` = 1 (1200 rows). 
- No row has `attempt > 1` (all API requests succeeded on the first try).
- The latency recorded for a retried call does **not** include the backoff sleep because `started = time.perf_counter()` is called at the start of every loop iteration (line 170), effectively resetting the timer right before the HTTP request is dispatched.

### Follow-up: Text-backend timeout
**File**: `backends/api_backend.py`
NOT FOUND. The text moderation backend specifically does not explicitly set a request timeout in `APITextBackend.__init__` (lines 7-17) or `generate` (lines 19-35). Because it initializes standard `OpenAI(...)` without a timeout argument, it inherits the Python `openai` library's client default (which is historically 10 minutes or `httpx` standard defaults depending on the library version).
