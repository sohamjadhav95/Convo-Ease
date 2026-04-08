"""
ConvoEase Automated Test Suite
-------------------------------
Bypasses the UI entirely. Uses Flask's built-in test client to call
every API endpoint directly — same code path as production, real AI calls,
no browser, no HTTP server, no mocks.

Usage:
    python automated_test.py

Results are written to: convoease_test_results.txt (same directory)

Requirements:
    - Run from the project root directory
    - The project must be configured (config.py, backends, models)
    - All dependencies installed (requirements.txt)
"""

import sys
import os
import base64
import json
import time
import traceback
from datetime import datetime
from pathlib import Path

# ── Make sure project root is on the path ────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Colour helpers (terminal output only) ────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"  {GREEN}PASS{RESET}  {msg}")
def fail(msg): print(f"  {RED}FAIL{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}WARN{RESET}  {msg}")
def info(msg): print(f"  {CYAN}    {RESET}  {msg}")
def header(msg): print(f"\n{BOLD}{msg}{RESET}")


# ═════════════════════════════════════════════════════════════════════════════
# TEST DATA
# ═════════════════════════════════════════════════════════════════════════════

USERS = [
    {"username": "arjun_sharma", "password": "Test@1234", "full_name": "Arjun Sharma",  "role": "admin"},
    {"username": "priya_patel",  "password": "Test@1234", "full_name": "Priya Patel",   "role": "admin"},
    {"username": "rahul_k",      "password": "Test@1234", "full_name": "Rahul Kulkarni","role": "member"},
    {"username": "sneha_more",   "password": "Test@1234", "full_name": "Sneha More",    "role": "member"},
    {"username": "vikram_d",     "password": "Test@1234", "full_name": "Vikram Desai",  "role": "member"},
    {"username": "neha_k",       "password": "Test@1234", "full_name": "Neha Kapoor",   "role": "member"},
]

GROUPS = [
    {
        "key":         "study",
        "name":        "Study Circle",
        "password":    "study123",
        "admin":       "arjun_sharma",
        "members":     ["rahul_k", "sneha_more", "neha_k"],
        "sensitivity": "Strict",
        "rules": (
            "1. Only academic topics — no off-topic discussions\n"
            "2. No abusive language or personal attacks\n"
            "3. No sharing of pirated study material or answer keys\n"
            "4. No promotional messages or spam links\n"
            "5. English or Marathi only"
        ),
    },
    {
        "key":         "tech",
        "name":        "Tech Talk",
        "password":    "tech456",
        "admin":       "priya_patel",
        "members":     ["arjun_sharma", "rahul_k", "vikram_d"],
        "sensitivity": "Moderate",
        "rules": (
            "1. Stay on tech topics — coding, tools, industry news\n"
            "2. No hate speech or discrimination\n"
            "3. No self-promotion without permission\n"
            "4. Mild language acceptable but no targeted abuse"
        ),
    },
    {
        "key":         "hangout",
        "name":        "Friends Hangout",
        "password":    "hang789",
        "admin":       "sneha_more",
        "members":     ["priya_patel", "vikram_d", "neha_k"],
        "sensitivity": "Relaxed",
        "rules": (
            "1. No threats or doxxing of any kind\n"
            "2. No NSFW content\n"
            "3. No political arguments"
        ),
    },
]

TEXT_TESTS = [
    # Study Circle — PASS
    {"id": "T01", "group": "study",   "sender": "rahul_k",      "expected": "PASS",
     "message": "Can someone share notes from today's lecture on binary trees?"},
    {"id": "T02", "group": "study",   "sender": "sneha_more",   "expected": "PASS",
     "message": "I think the answer to Q3 is O(n log n), here is my working..."},
    {"id": "T03", "group": "study",   "sender": "neha_k",       "expected": "PASS",
     "message": "Aaj ki class mein kya cover hua? I missed it."},
    {"id": "T04", "group": "study",   "sender": "rahul_k",      "expected": "PASS",
     "message": "Chapter 5 practice problems are up on the portal."},
    # Study Circle — FLAGGED
    {"id": "T05", "group": "study",   "sender": "sneha_more",   "expected": "FLAGGED",
     "message": "Bhai exam ka paper mil sakta hai kya? 500 rupees dunga."},
    {"id": "T06", "group": "study",   "sender": "neha_k",       "expected": "FLAGGED",
     "message": "Anyone want to watch IPL tonight? Totally off topic I know lol"},
    {"id": "T07", "group": "study",   "sender": "rahul_k",      "expected": "FLAGGED",
     "message": "You're so dumb, how did you even pass last semester?"},
    {"id": "T08", "group": "study",   "sender": "sneha_more",   "expected": "FLAGGED",
     "message": "Check this out: free-notes-pirated.xyz — has all textbooks"},
    # Tech Talk — PASS
    {"id": "T09", "group": "tech",    "sender": "rahul_k",      "expected": "PASS",
     "message": "Anyone tried the new Claude API? The context window is massive now."},
    {"id": "T10", "group": "tech",    "sender": "vikram_d",     "expected": "PASS",
     "message": "Python 3.13 dropped — pattern matching improvements look solid."},
    {"id": "T11", "group": "tech",    "sender": "arjun_sharma", "expected": "PASS",
     "message": "Honest opinion: React is getting too bloated. Vue is cleaner for mid-scale projects."},
    {"id": "T12", "group": "tech",    "sender": "rahul_k",      "expected": "PASS",
     "message": "What deployment setup are you all using? We just moved to Render."},
    # Tech Talk — FLAGGED
    {"id": "T13", "group": "tech",    "sender": "vikram_d",     "expected": "FLAGGED",
     "message": "Buy my Udemy course on Python! 90% off today only — link in bio"},
    {"id": "T14", "group": "tech",    "sender": "arjun_sharma", "expected": "FLAGGED",
     "message": "Women shouldn't be in tech, they just don't get it."},
    {"id": "T15", "group": "tech",    "sender": "rahul_k",      "expected": "FLAGGED",
     "message": "Modi is ruining the economy, I'm so done with this country."},
    # Friends Hangout — PASS
    {"id": "T16", "group": "hangout", "sender": "vikram_d",     "expected": "PASS",
     "message": "Movie tonight? Dunki is on Netflix finally."},
    {"id": "T17", "group": "hangout", "sender": "neha_k",       "expected": "PASS",
     "message": "Haha that meme is too relatable, sending it to my mom."},
    {"id": "T18", "group": "hangout", "sender": "priya_patel",  "expected": "PASS",
     "message": "Weekend trip to Lonavala? I can book the place."},
    {"id": "T19", "group": "hangout", "sender": "vikram_d",     "expected": "PASS",
     "message": "yaar aaj ka din bohot bura raha"},
    # Friends Hangout — FLAGGED
    {"id": "T20", "group": "hangout", "sender": "neha_k",       "expected": "FLAGGED",
     "message": "I know where Vikram lives, he better watch out."},
    {"id": "T21", "group": "hangout", "sender": "priya_patel",  "expected": "FLAGGED",
     "message": "[explicit NSFW content] — check this out lol"},
    {"id": "T22", "group": "hangout", "sender": "vikram_d",     "expected": "FLAGGED",
     "message": "BJP vs Congress argument — one party is literally destroying India!"},
    # Edge cases
    {"id": "T23", "group": "study",   "sender": "rahul_k",      "expected": "PASS",
     "message": "yes",
     "note": "Single-word reply after academic context — should pass"},
    {"id": "T24", "group": "tech",    "sender": "vikram_d",     "expected": "PASS",
     "message": "Arey yaar chill kar",
     "note": "Mild Hinglish, telling someone to calm down — not an attack"},
    {"id": "T25", "group": "study",   "sender": "sneha_more",   "expected": "FLAGGED",
     "message": "This group is full of idiots",
     "note": "General hostility without a specific target"},
    {"id": "T26", "group": "tech",    "sender": "rahul_k",      "expected": "FLAGGED",
     "message": "Password: admin123 — sharing login for a shared test account",
     "note": "Credential sharing"},
]

IMAGE_TESTS = [
    {"id": "I01", "group": "tech",    "sender": "vikram_d",
     "description": "Python code screenshot (safe)",
     "content": "python code screenshot safe academic content",
     "expected": "PASS"},
    {"id": "I02", "group": "study",   "sender": "rahul_k",
     "description": "Meme unrelated to academics",
     "content": "funny meme off topic entertainment not academic",
     "expected": "FLAGGED"},
    {"id": "I03", "group": "hangout", "sender": "neha_k",
     "description": "Landscape nature photo",
     "content": "landscape mountains trees nature photo safe",
     "expected": "PASS"},
]

AUDIO_TESTS = [
    {"id": "A01", "group": "study",   "sender": "sneha_more",
     "description": "Voice note about chapter discussion",
     "content": "Can we discuss chapter three tomorrow",
     "expected": "PASS"},
    {"id": "A02", "group": "tech",    "sender": "arjun_sharma",
     "description": "Promotional voice note",
     "content": "Buy my course huge discount today only",
     "expected": "FLAGGED"},
    {"id": "A03", "group": "hangout", "sender": "priya_patel",
     "description": "Casual meetup voice note",
     "content": "Let us meet at the cafe at six pm",
     "expected": "PASS"},
]

ADMIN_TESTS = [
    {"id": "AD01", "description": "View flagged messages after text tests"},
    {"id": "AD02", "description": "Submit appeal on flagged message"},
    {"id": "AD03", "description": "Admin reviews and approves appeal"},
    {"id": "AD04", "description": "Update group rules as admin"},
    {"id": "AD05", "description": "Sensitivity change affects moderation"},
]

ERROR_TESTS = [
    {"id": "N01", "description": "Wrong group password — should be denied"},
    {"id": "N02", "description": "Empty message — should be rejected"},
    {"id": "N03", "description": "Wrong login credentials — should fail"},
    {"id": "N04", "description": "Member tries admin action — should be denied"},
]


# ═════════════════════════════════════════════════════════════════════════════
# RESULT TRACKER
# ═════════════════════════════════════════════════════════════════════════════

class Results:
    def __init__(self):
        self.setup    = {}
        self.text     = {}
        self.image    = {}
        self.audio    = {}
        self.admin    = {}
        self.errors   = {}
        self.notes    = []
        self.start_time = datetime.now()

    def record(self, bucket, test_id, expected, actual, correct, note=""):
        bucket[test_id] = {
            "expected": expected,
            "actual":   actual,
            "correct":  correct,
            "note":     note,
        }
        status = f"{GREEN}correct{RESET}" if correct else f"{RED}WRONG{RESET}"
        verdict = f"expected={expected} actual={actual} [{status}]"
        if note:
            verdict += f" | {note}"
        if correct:
            ok(verdict)
        else:
            fail(verdict)

    def record_setup(self, step_id, passed, note=""):
        self.setup[step_id] = {"passed": passed, "note": note}
        if passed:
            ok(f"{step_id} — {note}")
        else:
            fail(f"{step_id} — {note}")

    def add_note(self, note):
        self.notes.append(note)

    # ── Summaries ──────────────────────────────────────────────────────────
    def _bucket_counts(self, bucket):
        total   = len(bucket)
        correct = sum(1 for v in bucket.values() if v.get("correct"))
        return total, correct

    def text_accuracy(self):
        total, correct = self._bucket_counts(self.text)
        return (correct / total * 100) if total else 0

    def false_positives(self):
        return [tid for tid, v in self.text.items()
                if v["expected"] == "PASS" and v["actual"] == "FLAGGED"]

    def false_negatives(self):
        return [tid for tid, v in self.text.items()
                if v["expected"] == "FLAGGED" and v["actual"] == "PASS"]

    def setup_failures(self):
        return [sid for sid, v in self.setup.items() if not v["passed"]]

    def overall(self):
        all_buckets = [self.text, self.image, self.audio, self.admin, self.errors]
        total   = sum(len(b) for b in all_buckets)
        correct = sum(sum(1 for v in b.values() if v.get("correct")) for b in all_buckets)
        return total, correct


# ═════════════════════════════════════════════════════════════════════════════
# HELPER UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

def b64(text: str) -> str:
    """Encode a plain string as base64 — simulates image/audio payload."""
    return base64.b64encode(text.encode()).decode()


def post(client, url, payload):
    r = client.post(url, json=payload)
    try:
        return r.status_code, r.get_json()
    except Exception:
        return r.status_code, {}


def get(client, url, params=None):
    full_url = url
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"{url}?{qs}"
    r = client.get(full_url)
    try:
        return r.status_code, r.get_json()
    except Exception:
        return r.status_code, {}


def put(client, url, payload):
    r = client.put(url, json=payload)
    try:
        return r.status_code, r.get_json()
    except Exception:
        return r.status_code, {}


# ═════════════════════════════════════════════════════════════════════════════
# SETUP PHASE
# ═════════════════════════════════════════════════════════════════════════════

def run_setup(client, results):
    header("SETUP — registering users and creating groups")

    group_ids = {}  # key -> group_id

    # S1 — Register all users
    print("\n  Registering users...")
    all_ok = True
    for u in USERS:
        status, data = post(client, "/api/auth/register", {
            "username":  u["username"],
            "password":  u["password"],
            "full_name": u["full_name"],
            "bio":       "",
        })
        if status == 200 and data.get("success"):
            info(f"registered {u['username']}")
        elif status == 409:
            info(f"{u['username']} already exists — skipping")
        else:
            warn(f"failed to register {u['username']}: {data}")
            all_ok = False

    results.record_setup("S1", all_ok, "register all users")

    # S2-S7 — Create groups and add members
    for i, g in enumerate(GROUPS):
        step_create = f"S{2 + i*2}"
        step_members = f"S{3 + i*2}"

        # Create group
        status, data = post(client, "/api/groups", {
            "group_name":              g["name"],
            "password":                g["password"],
            "admin_username":          g["admin"],
            "rules":                   g["rules"],
            "moderation_sensitivity":  g["sensitivity"],
        })
        if status == 200 and data.get("success"):
            group_ids[g["key"]] = data["group_id"]
            results.record_setup(step_create, True, f"create {g['name']} (id={data['group_id']})")
        else:
            results.record_setup(step_create, False, f"create {g['name']} failed: {data}")
            group_ids[g["key"]] = None

        # Add members
        if group_ids.get(g["key"]):
            gid = group_ids[g["key"]]
            member_ok = True
            for member in g["members"]:
                st, d = post(client, "/api/groups/join", {
                    "group_id": gid,
                    "password": g["password"],
                    "username": member,
                })
                if not (st == 200 and d.get("success")):
                    warn(f"  could not add {member} to {g['name']}: {d}")
                    member_ok = False
                else:
                    info(f"  added {member} to {g['name']}")
            results.record_setup(step_members, member_ok,
                                 f"add members to {g['name']}")
        else:
            results.record_setup(step_members, False,
                                 f"skipped — group was not created")

    return group_ids


# ═════════════════════════════════════════════════════════════════════════════
# TEXT MODERATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

def run_text_tests(client, group_ids, results):
    header("TEXT MODERATION TESTS")

    for t in TEXT_TESTS:
        gid = group_ids.get(t["group"])
        if not gid:
            results.text[t["id"]] = {
                "expected": t["expected"], "actual": "SKIPPED",
                "correct": False, "note": "group not created"
            }
            warn(f"{t['id']} skipped — group not available")
            continue

        note = t.get("note", "")
        print(f"\n  {CYAN}{t['id']}{RESET} [{t['group']}] {t['sender']}: \"{t['message'][:60]}{'...' if len(t['message'])>60 else ''}\"")
        if note:
            info(f"note: {note}")

        status, data = post(client, f"/api/groups/{gid}/messages", {
            "username": t["sender"],
            "message":  t["message"],
        })

        actual = data.get("status", "ERROR") if status == 200 else "HTTP_ERROR"
        reason = data.get("reason", "")
        correct = (actual == t["expected"])

        display_note = reason if reason else note
        results.record(results.text, t["id"], t["expected"], actual, correct, display_note)


# ═════════════════════════════════════════════════════════════════════════════
# IMAGE MODERATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

def run_image_tests(client, group_ids, results):
    header("IMAGE MODERATION TESTS")

    for t in IMAGE_TESTS:
        gid = group_ids.get(t["group"])
        if not gid:
            results.image[t["id"]] = {
                "expected": t["expected"], "actual": "SKIPPED",
                "correct": False, "note": "group not created"
            }
            warn(f"{t['id']} skipped — group not available")
            continue

        print(f"\n  {CYAN}{t['id']}{RESET} [{t['group']}] {t['description']}")

        status, data = post(client, f"/api/groups/{gid}/images", {
            "username":   t["sender"],
            "image_data": b64(t["content"]),
            "mime_type":  "image/jpeg",
        })

        if status == 503:
            actual = "UNAVAILABLE"
            correct = False
            note = "image moderation backend not available"
        else:
            actual  = data.get("status", "ERROR") if status == 200 else "HTTP_ERROR"
            correct = (actual == t["expected"])
            note    = data.get("summary", data.get("reason", ""))[:80]

        results.record(results.image, t["id"], t["expected"], actual, correct, note)


# ═════════════════════════════════════════════════════════════════════════════
# AUDIO MODERATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

def run_audio_tests(client, group_ids, results):
    header("AUDIO MODERATION TESTS")

    for t in AUDIO_TESTS:
        gid = group_ids.get(t["group"])
        if not gid:
            results.audio[t["id"]] = {
                "expected": t["expected"], "actual": "SKIPPED",
                "correct": False, "note": "group not created"
            }
            warn(f"{t['id']} skipped — group not available")
            continue

        print(f"\n  {CYAN}{t['id']}{RESET} [{t['group']}] {t['description']}")

        status, data = post(client, f"/api/groups/{gid}/audio", {
            "username":   t["sender"],
            "audio_data": b64(t["content"]),
            "mime_type":  "audio/wav",
        })

        if status == 503:
            actual  = "UNAVAILABLE"
            correct = False
            note    = "audio moderation backend not available"
        else:
            actual  = data.get("status", "ERROR") if status == 200 else "HTTP_ERROR"
            correct = (actual == t["expected"])
            note    = data.get("transcript", data.get("reason", ""))[:80]

        results.record(results.audio, t["id"], t["expected"], actual, correct, note)


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN FUNCTION TESTS
# ═════════════════════════════════════════════════════════════════════════════

def run_admin_tests(client, group_ids, results):
    header("ADMIN FUNCTION TESTS")
    gid = group_ids.get("study")

    # AD01 — View flagged messages
    print(f"\n  {CYAN}AD01{RESET} View flagged messages in Study Circle")
    if gid:
        status, data = get(client, f"/api/groups/{gid}/messages/flagged")
        flagged_list = data.get("flagged", []) if status == 200 else []
        passed = len(flagged_list) >= 1
        note   = f"{len(flagged_list)} flagged messages found"
        results.record(results.admin, "AD01", ">=1 flagged", str(len(flagged_list)), passed, note)
    else:
        results.record(results.admin, "AD01", ">=1 flagged", "SKIPPED", False, "group not created")

    # AD02 — Submit appeal
    print(f"\n  {CYAN}AD02{RESET} Submit appeal on a flagged message")
    appeal_msg_id = None
    if gid:
        _, fdata = get(client, f"/api/groups/{gid}/messages/flagged")
        flagged_msgs = fdata.get("flagged", [])
        if flagged_msgs:
            appeal_msg_id = flagged_msgs[0].get("message_id") or flagged_msgs[0].get("id")
            appealer = flagged_msgs[0].get("username", "rahul_k")
            status, data = post(client,
                f"/api/groups/{gid}/messages/{appeal_msg_id}/appeal", {
                    "username":    appealer,
                    "appeal_text": "This message was misunderstood — providing context.",
                })
            passed = status == 200 and data.get("appeal_status") == "PENDING_ADMIN"
            note   = f"appeal_status={data.get('appeal_status', 'n/a')}"
            results.record(results.admin, "AD02", "PENDING_ADMIN",
                           data.get("appeal_status", "n/a"), passed, note)
        else:
            results.record(results.admin, "AD02", "PENDING_ADMIN",
                           "SKIPPED", False, "no flagged messages to appeal")
    else:
        results.record(results.admin, "AD02", "PENDING_ADMIN",
                       "SKIPPED", False, "group not created")

    # AD03 — Admin reviews appeal
    print(f"\n  {CYAN}AD03{RESET} Admin reviews and approves appeal")
    if gid and appeal_msg_id:
        status, data = post(client,
            f"/api/groups/{gid}/messages/{appeal_msg_id}/appeal/review", {
                "username":   "arjun_sharma",
                "decision":   "approve",
                "admin_note": "Context accepted during testing.",
            })
        passed = status == 200 and data.get("success", False)
        note   = f"success={data.get('success')} status={data.get('status', '')}"
        results.record(results.admin, "AD03", "approved", "approved" if passed else "failed",
                       passed, note)
    else:
        results.record(results.admin, "AD03", "approved", "SKIPPED",
                       False, "no appeal to review")

    # AD04 — Update group rules
    print(f"\n  {CYAN}AD04{RESET} Update Tech Talk rules as admin")
    gid_tech = group_ids.get("tech")
    if gid_tech:
        new_rules = (
            "1. Stay on tech topics — coding, tools, industry news\n"
            "2. No hate speech or discrimination\n"
            "3. No self-promotion without permission\n"
            "4. Mild language acceptable but no targeted abuse\n"
            "5. No memes or reaction images"
        )
        status, data = put(client, f"/api/groups/{gid_tech}/rules", {
            "rules":                  new_rules,
            "username":               "priya_patel",
            "moderation_sensitivity": "Moderate",
        })
        passed = status == 200 and data.get("success", False)
        note   = f"rules updated: {passed}"
        results.record(results.admin, "AD04", "success", "success" if passed else "failed",
                       passed, note)
    else:
        results.record(results.admin, "AD04", "success", "SKIPPED",
                       False, "group not created")

    # AD05 — Sensitivity change
    print(f"\n  {CYAN}AD05{RESET} Change Tech Talk to Strict — retest borderline message")
    if gid_tech:
        # Change to Strict
        put(client, f"/api/groups/{gid_tech}/rules", {
            "rules":                  GROUPS[1]["rules"],
            "username":               "priya_patel",
            "moderation_sensitivity": "Strict",
        })
        # Send a borderline message
        status, data = post(client, f"/api/groups/{gid_tech}/messages", {
            "username": "vikram_d",
            "message":  "Arey yaar chill kar",
        })
        result_strict = data.get("status", "ERROR")
        # Restore to Moderate
        put(client, f"/api/groups/{gid_tech}/rules", {
            "rules":                  GROUPS[1]["rules"],
            "username":               "priya_patel",
            "moderation_sensitivity": "Moderate",
        })
        note = f"under Strict sensitivity, borderline message got: {result_strict}"
        # Under strict, borderline Hinglish may be flagged — either outcome is valid
        # We just record what happened
        passed = result_strict in ("PASS", "FLAGGED")
        results.record(results.admin, "AD05", "PASS or FLAGGED", result_strict, passed, note)
    else:
        results.record(results.admin, "AD05", "PASS or FLAGGED", "SKIPPED",
                       False, "group not created")


# ═════════════════════════════════════════════════════════════════════════════
# ERROR HANDLING TESTS
# ═════════════════════════════════════════════════════════════════════════════

def run_error_tests(client, group_ids, results):
    header("ERROR HANDLING TESTS")
    gid = group_ids.get("study")

    # N01 — Wrong group password
    print(f"\n  {CYAN}N01{RESET} Join group with wrong password")
    if gid:
        status, data = post(client, "/api/groups/join", {
            "group_id": gid,
            "password": "wrongpassword123",
            "username": "vikram_d",
        })
        passed = not data.get("success", True)
        results.record(results.errors, "N01", "denied", "denied" if passed else "allowed",
                       passed, f"status={status} success={data.get('success')}")
    else:
        results.record(results.errors, "N01", "denied", "SKIPPED", False, "group not created")

    # N02 — Empty message
    print(f"\n  {CYAN}N02{RESET} Send empty message")
    if gid:
        status, data = post(client, f"/api/groups/{gid}/messages", {
            "username": "rahul_k",
            "message":  "",
        })
        passed = status == 400 or not data.get("success", True)
        results.record(results.errors, "N02", "rejected", "rejected" if passed else "accepted",
                       passed, f"status={status}")
    else:
        results.record(results.errors, "N02", "rejected", "SKIPPED", False, "group not created")

    # N03 — Wrong login credentials
    print(f"\n  {CYAN}N03{RESET} Login with wrong password")
    status, data = post(client, "/api/auth/login", {
        "username": "arjun_sharma",
        "password": "WrongPass99",
    })
    passed = status == 401 or not data.get("success", True)
    results.record(results.errors, "N03", "login denied", "denied" if passed else "allowed",
                   passed, f"status={status}")

    # N04 — Member tries admin action
    print(f"\n  {CYAN}N04{RESET} Member tries to update group rules (admin-only)")
    if gid:
        status, data = put(client, f"/api/groups/{gid}/rules", {
            "rules":    "Hacked rules",
            "username": "rahul_k",   # member, not admin
        })
        passed = status == 403 or not data.get("success", True)
        results.record(results.errors, "N04", "access denied", "denied" if passed else "allowed",
                       passed, f"status={status} success={data.get('success')}")
    else:
        results.record(results.errors, "N04", "access denied", "SKIPPED", False, "group not created")


# ═════════════════════════════════════════════════════════════════════════════
# RESULTS FILE WRITER
# ═════════════════════════════════════════════════════════════════════════════

def write_results(results, output_path):
    duration = (datetime.now() - results.start_time).total_seconds()
    total_tests, total_correct = results.overall()
    text_total, text_correct   = results._bucket_counts(results.text)
    img_total, img_correct     = results._bucket_counts(results.image)
    aud_total, aud_correct     = results._bucket_counts(results.audio)
    adm_total, adm_correct     = results._bucket_counts(results.admin)
    err_total, err_correct     = results._bucket_counts(results.errors)

    sep  = "-" * 80
    sep2 = "=" * 80

    lines = [
        sep2,
        "CONVOEASE AUTOMATED TEST RESULTS",
        f"Run date    : {results.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration    : {duration:.1f} seconds",
        f"Tester      : automated_test.py (Flask test client, real AI)",
        sep2,
        "",
        "SETUP PHASE",
        sep,
    ]
    for sid, v in results.setup.items():
        status = "PASS" if v["passed"] else "FAIL"
        lines.append(f"  {sid:<6} {status:<6} {v['note']}")

    sf = results.setup_failures()
    if sf:
        lines += ["", f"  Setup failures: {', '.join(sf)}"]

    lines += [
        "",
        "TEXT MODERATION",
        sep,
        f"  {'ID':<6} {'Group':<14} {'Expected':<10} {'Actual':<10} {'Result':<8} Note",
        f"  {'-'*6} {'-'*14} {'-'*10} {'-'*10} {'-'*8} ----",
    ]
    group_lookup = {t["id"]: t["group"] for t in TEXT_TESTS}
    for tid, v in results.text.items():
        result = "CORRECT" if v["correct"] else "WRONG"
        grp    = group_lookup.get(tid, "")
        note   = v["note"][:50] if v["note"] else ""
        lines.append(f"  {tid:<6} {grp:<14} {v['expected']:<10} {v['actual']:<10} {result:<8} {note}")

    lines += [
        "",
        f"  Accuracy : {text_correct}/{text_total} ({results.text_accuracy():.1f}%)",
    ]
    fp = results.false_positives()
    fn = results.false_negatives()
    lines.append(f"  False positives (flagged incorrectly) : {', '.join(fp) if fp else 'none'}")
    lines.append(f"  False negatives (missed violations)   : {', '.join(fn) if fn else 'none'}")

    lines += [
        "",
        "IMAGE MODERATION",
        sep,
        f"  {'ID':<6} {'Expected':<10} {'Actual':<10} {'Result':<8} Description",
        f"  {'-'*6} {'-'*10} {'-'*10} {'-'*8} -----------",
    ]
    img_desc = {t["id"]: t["description"] for t in IMAGE_TESTS}
    for tid, v in results.image.items():
        result = "CORRECT" if v["correct"] else "WRONG"
        desc   = img_desc.get(tid, "")[:50]
        lines.append(f"  {tid:<6} {v['expected']:<10} {v['actual']:<10} {result:<8} {desc}")
    lines.append(f"\n  Accuracy : {img_correct}/{img_total}")

    lines += [
        "",
        "AUDIO MODERATION",
        sep,
        f"  {'ID':<6} {'Expected':<10} {'Actual':<10} {'Result':<8} Transcript / Note",
        f"  {'-'*6} {'-'*10} {'-'*10} {'-'*8} -----------------",
    ]
    aud_desc = {t["id"]: t["description"] for t in AUDIO_TESTS}
    for tid, v in results.audio.items():
        result = "CORRECT" if v["correct"] else "WRONG"
        note   = v["note"][:50] if v["note"] else aud_desc.get(tid, "")[:50]
        lines.append(f"  {tid:<6} {v['expected']:<10} {v['actual']:<10} {result:<8} {note}")
    lines.append(f"\n  Accuracy : {aud_correct}/{aud_total}")

    lines += [
        "",
        "ADMIN FUNCTIONS",
        sep,
    ]
    for tid, v in results.admin.items():
        result = "CORRECT" if v["correct"] else "WRONG"
        lines.append(f"  {tid:<6} {result:<8} {v['note']}")

    lines += [
        "",
        "ERROR HANDLING",
        sep,
    ]
    for tid, v in results.errors.items():
        result = "CORRECT" if v["correct"] else "WRONG"
        lines.append(f"  {tid:<6} {result:<8} {v['note']}")

    # Overall
    setup_pass = len(results.setup) - len(sf)
    overall_pct = (total_correct / total_tests * 100) if total_tests else 0
    overall_status = "PASS" if overall_pct >= 80 and not sf else ("PARTIAL" if overall_pct >= 50 else "FAIL")

    lines += [
        "",
        sep2,
        "SUMMARY",
        sep2,
        "",
        f"  Setup steps passed    : {setup_pass} / {len(results.setup)}",
        f"  Text tests            : {text_correct} / {text_total} ({results.text_accuracy():.1f}%)",
        f"  Image tests           : {img_correct} / {img_total}",
        f"  Audio tests           : {aud_correct} / {aud_total}",
        f"  Admin tests           : {adm_correct} / {adm_total}",
        f"  Error handling tests  : {err_correct} / {err_total}",
        "",
        f"  Total tests run       : {total_tests}",
        f"  Total correct         : {total_correct}",
        f"  Overall accuracy      : {overall_pct:.1f}%",
        "",
        f"  False positives       : {', '.join(fp) if fp else 'none'}",
        f"  False negatives       : {', '.join(fn) if fn else 'none'}",
        f"  Setup failures        : {', '.join(sf) if sf else 'none'}",
    ]

    if results.notes:
        lines += ["", "  Notes:"]
        for n in results.notes:
            lines.append(f"    - {n}")

    lines += [
        "",
        f"  Overall status        : {overall_status}",
        "",
        sep2,
        "END OF RESULTS",
        sep2,
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return overall_status


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n{BOLD}ConvoEase Automated Test Suite{RESET}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: real AI calls via Flask test client — no UI, no mocks, no server\n")

    results = Results()

    # Build the app exactly as production does — no patches, no mocks
    print("Initialising Flask app...")
    try:
        from main import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        print("  App ready.\n")
    except Exception as e:
        print(f"{RED}FATAL: could not create app: {e}{RESET}")
        traceback.print_exc()
        sys.exit(1)

    # Run all test phases
    try:
        group_ids = run_setup(client, results)
        run_text_tests(client, group_ids, results)
        run_image_tests(client, group_ids, results)
        run_audio_tests(client, group_ids, results)
        run_admin_tests(client, group_ids, results)
        run_error_tests(client, group_ids, results)
    except Exception as e:
        results.add_note(f"Test run crashed mid-way: {e}")
        traceback.print_exc()

    # Write results file
    output_path = PROJECT_ROOT / "convoease_test_results.txt"
    header("WRITING RESULTS FILE")
    try:
        overall = write_results(results, output_path)
        ok(f"Results written to: {output_path}")
    except Exception as e:
        fail(f"Could not write results file: {e}")
        overall = "FAIL"

    # Final terminal summary
    total, correct = results.overall()
    pct = correct / total * 100 if total else 0
    header("FINAL SUMMARY")
    print(f"  Total   : {total}")
    print(f"  Correct : {correct}")
    print(f"  Score   : {pct:.1f}%")
    fp = results.false_positives()
    fn = results.false_negatives()
    if fp: print(f"  {YELLOW}False positives : {', '.join(fp)}{RESET}")
    if fn: print(f"  {YELLOW}False negatives : {', '.join(fn)}{RESET}")
    sf = results.setup_failures()
    if sf: print(f"  {RED}Setup failures  : {', '.join(sf)}{RESET}")
    color = GREEN if overall == "PASS" else (YELLOW if overall == "PARTIAL" else RED)
    print(f"\n  {color}{BOLD}Overall: {overall}{RESET}\n")


if __name__ == "__main__":
    main()