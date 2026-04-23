"""
ConvoEase automated backend test suite with real-media placeholders.

What this script does:
- Bypasses the UI and calls Flask endpoints directly.
- Uses the real application stack and current moderation backends.
- Runs inside an isolated runtime sandbox so it does not pollute the main CSV/media data.
- Supports real image/audio files per test case, with an explicit demo fallback when files are missing.

Usage:
    python "testing\\Automated Testings\\test_bypassing_ui_real_media.py"
    python "testing\\Automated Testings\\test_bypassing_ui_real_media.py" --require-real-media

Recommended asset folders:
    testing\\Automated Testings\\assets\\images
    testing\\Automated Testings\\assets\\audio

To convert a media case from demo mode to real-file mode, edit the `file_path` field inside
IMAGE_TESTS or AUDIO_TESTS and place the matching file at that location.
"""

import argparse
import base64
import mimetypes
import sys
import traceback
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = SCRIPT_DIR / "assets"
IMAGE_ASSET_DIR = ASSET_ROOT / "images"
AUDIO_ASSET_DIR = ASSET_ROOT / "audio"
ARTIFACTS_DIR = PROJECT_ROOT / "testing" / "artifacts" / "automated_runs"
RUN_STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
DEFAULT_OUTPUT_PATH = SCRIPT_DIR / f"convoease_real_media_results_{RUN_STAMP}.txt"
DEFAULT_RUNTIME_ROOT = ARTIFACTS_DIR / f"runtime_{RUN_STAMP}"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(message):
    print(f"  {GREEN}PASS{RESET}  {message}")


def fail(message):
    print(f"  {RED}FAIL{RESET}  {message}")


def warn(message):
    print(f"  {YELLOW}WARN{RESET}  {message}")


def info(message):
    print(f"  {CYAN}INFO{RESET}  {message}")


def header(message):
    print(f"\n{BOLD}{message}{RESET}")


USERS = [
    {"username": "meera_admin", "password": "Test@1234", "full_name": "Meera Joshi"},
    {"username": "kabir_admin", "password": "Test@1234", "full_name": "Kabir Malhotra"},
    {"username": "anika_admin", "password": "Test@1234", "full_name": "Anika Rao"},
    {"username": "rohan_m", "password": "Test@1234", "full_name": "Rohan Mehta"},
    {"username": "isha_s", "password": "Test@1234", "full_name": "Isha Shah"},
    {"username": "tanay_v", "password": "Test@1234", "full_name": "Tanay Verma"},
    {"username": "farah_n", "password": "Test@1234", "full_name": "Farah Naqvi"},
    {"username": "dev_p", "password": "Test@1234", "full_name": "Dev Patil"},
    {"username": "naina_r", "password": "Test@1234", "full_name": "Naina Reddy"},
]


GROUPS = [
    {
        "key": "campus_helpdesk",
        "name": "Campus Helpdesk",
        "password": "campus321",
        "admin": "meera_admin",
        "members": ["rohan_m", "isha_s", "naina_r"],
        "sensitivity": "Strict",
        "rules": (
            "1. Keep discussion limited to college logistics, classes, exams, and official notices.\n"
            "2. No leaked papers, cheating help, or paid answer sharing.\n"
            "3. No insults, harassment, or humiliation.\n"
            "4. No off-topic entertainment chatter, betting, or promotions.\n"
            "5. Images and audio must follow the same rules as text."
        ),
    },
    {
        "key": "build_ship_lab",
        "name": "Build and Ship Lab",
        "password": "lab654",
        "admin": "kabir_admin",
        "members": ["meera_admin", "tanay_v", "dev_p"],
        "sensitivity": "Moderate",
        "rules": (
            "1. Use this group for product, QA, deployment, bug triage, and engineering decisions.\n"
            "2. No hate speech, identity-based attacks, or personal abuse.\n"
            "3. No advertisements, recruitment spam, or self-promotion without permission.\n"
            "4. Do not share credentials, tokens, or confidential production access.\n"
            "5. Images and audio must stay relevant to engineering work."
        ),
    },
    {
        "key": "weekend_planners",
        "name": "Weekend Planners",
        "password": "weekend987",
        "admin": "farah_n",
        "members": ["isha_s", "dev_p", "naina_r"],
        "sensitivity": "Relaxed",
        "rules": (
            "1. Casual planning is welcome, but no threats, blackmail, or doxxing.\n"
            "2. No NSFW media or sexually explicit descriptions.\n"
            "3. No targeted abuse or repeated bullying.\n"
            "4. No scams or manipulative payment messages.\n"
            "5. Images and audio follow the same rules."
        ),
    },
    {
        "key": "family_updates",
        "name": "Family Updates",
        "password": "family111",
        "admin": "anika_admin",
        "members": ["rohan_m", "farah_n", "naina_r"],
        "sensitivity": "Moderate",
        "rules": (
            "1. Use this space for family updates, health coordination, plans, and support.\n"
            "2. No abuse, humiliation, or hostile arguments.\n"
            "3. No scam forwards, miracle-cure claims, or dangerous medical misinformation.\n"
            "4. No unrelated commercial offers or chain messages.\n"
            "5. Images and audio must follow the same standards."
        ),
    },
]


TEXT_TESTS = [
    {"id": "T01", "group": "campus_helpdesk", "sender": "rohan_m", "expected": "PASS",
     "message": "Tomorrow's electronics lab moved from B204 to B210. Please update your timetable."},
    {"id": "T02", "group": "campus_helpdesk", "sender": "isha_s", "expected": "PASS",
     "message": "Kal ka tutorial 10 baje hi hai na? I may reach five minutes late."},
    {"id": "T03", "group": "campus_helpdesk", "sender": "naina_r", "expected": "PASS",
     "message": "Can someone share the official notice about internship registration deadlines?"},
    {"id": "T04", "group": "campus_helpdesk", "sender": "rohan_m", "expected": "FLAGGED",
     "message": "I have tomorrow's quiz answers PDF. DM me if you want it."},
    {"id": "T05", "group": "campus_helpdesk", "sender": "isha_s", "expected": "FLAGGED",
     "message": "IPL auction was wild last night, who all watched it?"},
    {"id": "T06", "group": "campus_helpdesk", "sender": "naina_r", "expected": "FLAGGED",
     "message": "You are completely useless, stop asking stupid questions."},
    {"id": "T07", "group": "campus_helpdesk", "sender": "rohan_m", "expected": "FLAGGED",
     "message": "Join my paid crash course, 499 only, limited seats."},

    {"id": "T08", "group": "build_ship_lab", "sender": "dev_p", "expected": "PASS",
     "message": "The login retry bug happens only after the refresh token expires during idle time."},
    {"id": "T09", "group": "build_ship_lab", "sender": "tanay_v", "expected": "PASS",
     "message": "I pushed the websocket reconnect fix to feature/reconnect-handler for review."},
    {"id": "T10", "group": "build_ship_lab", "sender": "meera_admin", "expected": "PASS",
     "message": "Let's shift the release from Thursday to Friday after QA signs off on payments."},
    {"id": "T11", "group": "build_ship_lab", "sender": "dev_p", "expected": "FLAGGED",
     "message": "Use this shared prod password for now: Admin@123."},
    {"id": "T12", "group": "build_ship_lab", "sender": "tanay_v", "expected": "FLAGGED",
     "message": "Women slow down engineering teams anyway."},
    {"id": "T13", "group": "build_ship_lab", "sender": "kabir_admin", "expected": "FLAGGED",
     "message": "Please vote for my cousin in the local elections this weekend."},
    {"id": "T14", "group": "build_ship_lab", "sender": "meera_admin", "expected": "FLAGGED",
     "message": "Buy my SaaS template pack, link in bio, huge discount today."},

    {"id": "T15", "group": "weekend_planners", "sender": "farah_n", "expected": "PASS",
     "message": "Saturday brunch at 11 or should we do a late evening drive instead?"},
    {"id": "T16", "group": "weekend_planners", "sender": "naina_r", "expected": "PASS",
     "message": "I found a villa option in Alibaug with parking for three cars."},
    {"id": "T17", "group": "weekend_planners", "sender": "dev_p", "expected": "PASS",
     "message": "Rain looks heavy, maybe indoor games night is safer than the trek."},
    {"id": "T18", "group": "weekend_planners", "sender": "isha_s", "expected": "FLAGGED",
     "message": "I know where you live, so do not test me."},
    {"id": "T19", "group": "weekend_planners", "sender": "dev_p", "expected": "FLAGGED",
     "message": "[explicit NSFW clip] dropping it here now."},
    {"id": "T20", "group": "weekend_planners", "sender": "naina_r", "expected": "FLAGGED",
     "message": "You are a pathetic loser and nobody wants you on this trip."},

    {"id": "T21", "group": "family_updates", "sender": "anika_admin", "expected": "PASS",
     "message": "Dad's check-up is on Monday at 9 AM. I will book the cab."},
    {"id": "T22", "group": "family_updates", "sender": "rohan_m", "expected": "PASS",
     "message": "I will pick up medicines on my way back from work."},
    {"id": "T23", "group": "family_updates", "sender": "farah_n", "expected": "PASS",
     "message": "Let's do nani's birthday dinner at home this year."},
    {"id": "T24", "group": "family_updates", "sender": "naina_r", "expected": "FLAGGED",
     "message": "Forward this message to five people and you will win a free iPhone."},
    {"id": "T25", "group": "family_updates", "sender": "rohan_m", "expected": "FLAGGED",
     "message": "Stop grandma's tablets immediately. A WhatsApp reel said those medicines are fake."},
    {"id": "T26", "group": "family_updates", "sender": "farah_n", "expected": "FLAGGED",
     "message": "Uncle is an idiot and should be kicked out of the family group."},
]


IMAGE_TESTS = [
    {
        "id": "I01",
        "group": "campus_helpdesk",
        "sender": "rohan_m",
        "expected": "PASS",
        "mime_type": "image/jpeg",
        "description": "Photo of a classroom notice board or timetable sheet.",
        "file_path": IMAGE_ASSET_DIR / "campus_notice_board.jpg",
        "demo_content": "photo of official college notice board showing classroom change and timetable",
    },
    {
        "id": "I02",
        "group": "build_ship_lab",
        "sender": "dev_p",
        "expected": "PASS",
        "mime_type": "image/png",
        "description": "Screenshot of a bug tracker, dashboard, or code diff related to engineering work.",
        "file_path": IMAGE_ASSET_DIR / "engineering_bug_dashboard.png",
        "demo_content": "screenshot of bug dashboard and code diff for login retry fix",
    },
    {
        "id": "I03",
        "group": "weekend_planners",
        "sender": "naina_r",
        "expected": "PASS",
        "mime_type": "image/jpeg",
        "description": "Travel photo of a beach, villa, cafe, or road-trip destination.",
        "file_path": IMAGE_ASSET_DIR / "weekend_trip_spot.jpg",
        "demo_content": "photo of beachside villa and travel destination for weekend planning",
    },
    {
        "id": "I04",
        "group": "campus_helpdesk",
        "sender": "isha_s",
        "expected": "FLAGGED",
        "mime_type": "image/jpeg",
        "description": "Off-topic entertainment meme or cricket poster unrelated to campus logistics.",
        "file_path": IMAGE_ASSET_DIR / "offtopic_cricket_meme.jpg",
        "demo_content": "funny cricket meme poster unrelated to college logistics and study support",
    },
    {
        "id": "I05",
        "group": "weekend_planners",
        "sender": "dev_p",
        "expected": "FLAGGED",
        "mime_type": "image/jpeg",
        "description": "Threatening or abusive meme targeting a person.",
        "file_path": IMAGE_ASSET_DIR / "threatening_abusive_meme.jpg",
        "demo_content": "abusive threatening meme targeting a person with hostile text",
    },
    {
        "id": "I06",
        "group": "family_updates",
        "sender": "farah_n",
        "expected": "FLAGGED",
        "mime_type": "image/png",
        "description": "Scam or miracle-cure poster screenshot with misleading claims.",
        "file_path": IMAGE_ASSET_DIR / "miracle_cure_scam.png",
        "demo_content": "scam poster claiming miracle cure and fake medical advice",
    },
]


AUDIO_TESTS = [
    {
        "id": "A01",
        "group": "campus_helpdesk",
        "sender": "isha_s",
        "expected": "PASS",
        "mime_type": "audio/wav",
        "description": "Voice note about exam room or class timing updates.",
        "file_path": AUDIO_ASSET_DIR / "campus_exam_room_update.wav",
        "demo_content": "Please note the viva room has changed to B210 for tomorrow morning.",
    },
    {
        "id": "A02",
        "group": "build_ship_lab",
        "sender": "tanay_v",
        "expected": "PASS",
        "mime_type": "audio/wav",
        "description": "Voice note about QA status, deployment timing, or bug fix progress.",
        "file_path": AUDIO_ASSET_DIR / "release_status_update.wav",
        "demo_content": "The payment fix is ready and QA starts at four pm today.",
    },
    {
        "id": "A03",
        "group": "weekend_planners",
        "sender": "farah_n",
        "expected": "PASS",
        "mime_type": "audio/wav",
        "description": "Casual meetup plan or location coordination voice note.",
        "file_path": AUDIO_ASSET_DIR / "weekend_meetup_plan.wav",
        "demo_content": "Let's meet at the cafe by six and leave together from there.",
    },
    {
        "id": "A04",
        "group": "build_ship_lab",
        "sender": "dev_p",
        "expected": "FLAGGED",
        "mime_type": "audio/wav",
        "description": "Promotional sales pitch or spammy self-promotion voice note.",
        "file_path": AUDIO_ASSET_DIR / "promo_bootcamp_pitch.wav",
        "demo_content": "Buy my internship bootcamp today, huge discount for this team only.",
    },
    {
        "id": "A05",
        "group": "weekend_planners",
        "sender": "naina_r",
        "expected": "FLAGGED",
        "mime_type": "audio/wav",
        "description": "Threatening or abusive voice note directed at another member.",
        "file_path": AUDIO_ASSET_DIR / "threatening_voice_note.wav",
        "demo_content": "If you come late again, I will make you regret it.",
    },
    {
        "id": "A06",
        "group": "family_updates",
        "sender": "rohan_m",
        "expected": "FLAGGED",
        "mime_type": "audio/wav",
        "description": "Dangerous medical misinformation or scam-style forwarded advice.",
        "file_path": AUDIO_ASSET_DIR / "medical_misinformation_forward.wav",
        "demo_content": "Stop all medicines immediately because a forwarded reel said they are dangerous.",
    },
]


class Results:
    def __init__(self):
        self.start_time = datetime.now()
        self.setup = {}
        self.text = {}
        self.image = {}
        self.audio = {}
        self.admin = {}
        self.errors = {}
        self.notes = []
        self.media_usage = {
            "image": {"real_file": 0, "demo_fallback": 0, "skipped": 0},
            "audio": {"real_file": 0, "demo_fallback": 0, "skipped": 0},
        }

    def record(self, bucket, test_id, expected, actual, passed, note=""):
        bucket[test_id] = {
            "expected": expected,
            "actual": actual,
            "passed": passed,
            "note": note,
        }
        verdict = f"expected={expected} actual={actual}"
        if note:
            verdict += f" | {note}"
        if passed is True:
            ok(verdict)
        elif passed is None:
            warn(verdict)
        else:
            fail(verdict)

    def record_setup(self, step_id, passed, note):
        self.setup[step_id] = {"passed": passed, "note": note}
        if passed:
            ok(f"{step_id} | {note}")
        else:
            fail(f"{step_id} | {note}")

    def add_note(self, note):
        self.notes.append(note)

    def _bucket_counts(self, bucket):
        passed = sum(1 for item in bucket.values() if item["passed"] is True)
        failed = sum(1 for item in bucket.values() if item["passed"] is False)
        skipped = sum(1 for item in bucket.values() if item["passed"] is None)
        return {"total": len(bucket), "passed": passed, "failed": failed, "skipped": skipped}

    def overall_counts(self):
        all_buckets = [self.text, self.image, self.audio, self.admin, self.errors]
        totals = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
        for bucket in all_buckets:
            counts = self._bucket_counts(bucket)
            for key in totals:
                totals[key] += counts[key]
        return totals


def post(client, url, payload):
    response = client.post(url, json=payload)
    try:
        return response.status_code, response.get_json()
    except Exception:
        return response.status_code, {}


def get(client, url, params=None):
    query = ""
    if params:
        query = "?" + "&".join(f"{key}={value}" for key, value in params.items())
    response = client.get(f"{url}{query}")
    try:
        return response.status_code, response.get_json()
    except Exception:
        return response.status_code, {}


def put(client, url, payload):
    response = client.put(url, json=payload)
    try:
        return response.status_code, response.get_json()
    except Exception:
        return response.status_code, {}


def encode_demo_payload(text):
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")


def infer_mime_from_file(path, fallback_mime):
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or fallback_mime


def load_media_case_payload(case, media_kind, require_real_media, results):
    asset_path = Path(case["file_path"])
    if asset_path.exists():
        payload = base64.b64encode(asset_path.read_bytes()).decode("utf-8")
        results.media_usage[media_kind]["real_file"] += 1
        return {
            "payload": payload,
            "mime_type": infer_mime_from_file(asset_path, case["mime_type"]),
            "source": f"real file: {asset_path}",
        }

    if require_real_media:
        results.media_usage[media_kind]["skipped"] += 1
        return {
            "payload": None,
            "mime_type": case["mime_type"],
            "source": f"missing required file: {asset_path}",
        }

    results.media_usage[media_kind]["demo_fallback"] += 1
    return {
        "payload": encode_demo_payload(case["demo_content"]),
        "mime_type": case["mime_type"],
        "source": f"demo fallback used because file was missing: {asset_path}",
    }


def ensure_runtime_directories():
    for directory in (IMAGE_ASSET_DIR, AUDIO_ASSET_DIR, ARTIFACTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def build_test_client(runtime_root, use_live_data=False):
    if not use_live_data:
        from testing.shared.harness import configure_test_environment

        configure_test_environment(runtime_root)
    from main import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def run_setup(client, results):
    header("SETUP")
    group_ids = {}

    all_registered = True
    for user in USERS:
        status, data = post(client, "/api/auth/register", {
            "username": user["username"],
            "password": user["password"],
            "full_name": user["full_name"],
            "bio": "",
        })
        if status == 200 and data.get("success"):
            info(f"registered {user['username']}")
        elif status == 409:
            info(f"{user['username']} already exists; reusing account")
        else:
            all_registered = False
            warn(f"register failed for {user['username']}: status={status} payload={data}")
    results.record_setup("S01", all_registered, "register all scripted users")

    all_groups_created = True
    all_members_joined = True
    for index, group in enumerate(GROUPS, start=1):
        create_step = f"S{index * 2:02d}"
        join_step = f"S{index * 2 + 1:02d}"

        status, data = post(client, "/api/groups", {
            "group_name": group["name"],
            "password": group["password"],
            "admin_username": group["admin"],
            "rules": group["rules"],
            "moderation_sensitivity": group["sensitivity"],
        })

        group_id = data.get("group_id")
        group_ids[group["key"]] = group_id
        created = status == 200 and data.get("success") and bool(group_id)
        results.record_setup(create_step, created, f"create group {group['name']}")
        all_groups_created = all_groups_created and created

        joined = True
        if group_id:
            for member in group["members"]:
                member_status, member_data = post(client, "/api/groups/join", {
                    "group_id": group_id,
                    "password": group["password"],
                    "username": member,
                })
                if member_status != 200 or not member_data.get("success"):
                    joined = False
                    warn(
                        f"join failed for {member} -> {group['name']}: "
                        f"status={member_status} payload={member_data}"
                    )
        else:
            joined = False
        results.record_setup(join_step, joined, f"join scripted members to {group['name']}")
        all_members_joined = all_members_joined and joined
    if not all_groups_created or not all_members_joined:
        results.add_note("One or more setup steps failed, so later failures may cascade.")
    return group_ids


def run_text_tests(client, group_ids, results):
    header("TEXT MODERATION TESTS")
    for case in TEXT_TESTS:
        group_id = group_ids.get(case["group"])
        print(f"\n  {CYAN}{case['id']}{RESET}  {case['group']}  {case['sender']}")
        if not group_id:
            results.record(results.text, case["id"], case["expected"], "SKIPPED", None, "group was not created")
            continue

        status, data = post(client, f"/api/groups/{group_id}/messages", {
            "username": case["sender"],
            "message": case["message"],
        })
        actual = data.get("status", f"HTTP_{status}")
        passed = status == 200 and actual == case["expected"]
        note = data.get("reason", "") or case["message"][:90]
        results.record(results.text, case["id"], case["expected"], actual, passed, note)


def run_image_tests(client, group_ids, results, require_real_media):
    header("IMAGE MODERATION TESTS")
    for case in IMAGE_TESTS:
        group_id = group_ids.get(case["group"])
        print(f"\n  {CYAN}{case['id']}{RESET}  {case['description']}")
        if not group_id:
            results.record(results.image, case["id"], case["expected"], "SKIPPED", None, "group was not created")
            continue

        media = load_media_case_payload(case, "image", require_real_media, results)
        if media["payload"] is None:
            results.record(results.image, case["id"], case["expected"], "SKIPPED", None, media["source"])
            continue

        status, data = post(client, f"/api/groups/{group_id}/images", {
            "username": case["sender"],
            "image_data": media["payload"],
            "mime_type": media["mime_type"],
        })
        actual = data.get("status", f"HTTP_{status}")
        passed = status == 200 and actual == case["expected"]
        summary = data.get("summary", "")
        note = f"{media['source']} | {summary or case['description']}"
        results.record(results.image, case["id"], case["expected"], actual, passed, note)


def run_audio_tests(client, group_ids, results, require_real_media):
    header("AUDIO MODERATION TESTS")
    for case in AUDIO_TESTS:
        group_id = group_ids.get(case["group"])
        print(f"\n  {CYAN}{case['id']}{RESET}  {case['description']}")
        if not group_id:
            results.record(results.audio, case["id"], case["expected"], "SKIPPED", None, "group was not created")
            continue

        media = load_media_case_payload(case, "audio", require_real_media, results)
        if media["payload"] is None:
            results.record(results.audio, case["id"], case["expected"], "SKIPPED", None, media["source"])
            continue

        status, data = post(client, f"/api/groups/{group_id}/audio", {
            "username": case["sender"],
            "audio_data": media["payload"],
            "mime_type": media["mime_type"],
        })
        actual = data.get("status", f"HTTP_{status}")
        passed = status == 200 and actual == case["expected"]
        transcript = data.get("transcript", "")
        note = f"{media['source']} | {transcript or case['description']}"
        results.record(results.audio, case["id"], case["expected"], actual, passed, note)


def run_admin_tests(client, group_ids, results):
    header("ADMIN AND ANALYTICS TESTS")
    campus_group_id = group_ids.get("campus_helpdesk")
    lab_group_id = group_ids.get("build_ship_lab")

    flagged_messages = []
    if campus_group_id:
        _, flagged_data = get(client, f"/api/groups/{campus_group_id}/messages/flagged")
        flagged_messages = flagged_data.get("flagged", [])

    status = 200 if flagged_messages else 404
    actual = f"{len(flagged_messages)} flagged"
    passed = bool(flagged_messages)
    results.record(results.admin, "AD01", ">=1 flagged", actual if status == 200 else "0 flagged", passed,
                   "campus flagged queue is populated")

    if campus_group_id:
        report_status, report_data = get(client, f"/api/groups/{campus_group_id}/report")
        report = report_data.get("report", {})
        flagged_count = report.get("flagged_count", -1)
        passed = report_status == 200 and report_data.get("success") and flagged_count >= 1
        note = f"flagged_count={flagged_count} total_messages={report.get('total_messages', 'n/a')}"
        results.record(results.admin, "AD02", "flagged_count >= 1", str(flagged_count), passed, note)
    else:
        results.record(results.admin, "AD02", "flagged_count >= 1", "SKIPPED", None, "group was not created")

    appeal_message_id = None
    appeal_sender = None
    if flagged_messages:
        appeal_message_id = flagged_messages[0].get("message_id") or flagged_messages[0].get("id")
        appeal_sender = flagged_messages[0].get("username")
        status, data = post(
            client,
            f"/api/groups/{campus_group_id}/messages/{appeal_message_id}/appeal",
            {
                "username": appeal_sender,
                "appeal_text": "This was a misunderstood test sample and I am providing additional context.",
            },
        )
        actual = data.get("appeal_status", f"HTTP_{status}")
        passed = status == 200 and actual == "PENDING_ADMIN"
        results.record(results.admin, "AD03", "PENDING_ADMIN", actual, passed, data.get("ai_reason", ""))
    else:
        results.record(results.admin, "AD03", "PENDING_ADMIN", "SKIPPED", None, "no flagged message available")

    if campus_group_id and appeal_message_id:
        status, data = post(
            client,
            f"/api/groups/{campus_group_id}/messages/{appeal_message_id}/appeal/review",
            {
                "username": "meera_admin",
                "decision": "approve",
                "admin_note": "Approved during automated validation.",
            },
        )
        actual = data.get("appeal_status", f"HTTP_{status}")
        passed = status == 200 and data.get("final_status") == "PASS"
        note = f"final_status={data.get('final_status', '')}"
        results.record(results.admin, "AD04", "APPROVED", actual, passed, note)
    else:
        results.record(results.admin, "AD04", "APPROVED", "SKIPPED", None, "appeal was not created")

    if lab_group_id:
        new_rules = (
            "1. Use this group for product, QA, deployment, bug triage, and engineering decisions.\n"
            "2. No hate speech, identity-based attacks, or personal abuse.\n"
            "3. No advertisements, recruitment spam, or self-promotion without permission.\n"
            "4. Do not share credentials, tokens, or confidential production access.\n"
            "5. No memes or reaction-image dumps during release windows.\n"
            "6. Images and audio must stay relevant to engineering work."
        )
        status, data = put(client, f"/api/groups/{lab_group_id}/rules", {
            "rules": new_rules,
            "username": "kabir_admin",
            "moderation_sensitivity": "Strict",
        })
        actual = "success" if data.get("success") else f"HTTP_{status}"
        passed = status == 200 and data.get("success")
        results.record(results.admin, "AD05", "success", actual, passed, "update lab rules and sensitivity")
    else:
        results.record(results.admin, "AD05", "success", "SKIPPED", None, "group was not created")

    if lab_group_id:
        status, data = get(client, f"/api/groups/{lab_group_id}/summary", {"limit": 12})
        summary = data.get("summary", {})
        bullets = summary.get("bullets", [])
        passed = status == 200 and data.get("success") and isinstance(bullets, list) and len(bullets) >= 1
        note = summary.get("headline", "")
        results.record(results.admin, "AD06", ">=1 bullet", str(len(bullets)), passed, note)
    else:
        results.record(results.admin, "AD06", ">=1 bullet", "SKIPPED", None, "group was not created")


def run_error_tests(client, group_ids, results):
    header("ERROR HANDLING TESTS")
    campus_group_id = group_ids.get("campus_helpdesk")
    lab_group_id = group_ids.get("build_ship_lab")

    if campus_group_id:
        status, data = post(client, "/api/groups/join", {
            "group_id": campus_group_id,
            "password": "wrong-password",
            "username": "dev_p",
        })
        passed = status in (400, 403) or not data.get("success", True)
        results.record(results.errors, "N01", "denied", "denied" if passed else "allowed", passed,
                       f"status={status}")
    else:
        results.record(results.errors, "N01", "denied", "SKIPPED", None, "group was not created")

    if campus_group_id:
        status, data = post(client, f"/api/groups/{campus_group_id}/messages", {
            "username": "rohan_m",
            "message": "",
        })
        passed = status == 400 or not data.get("success", True)
        results.record(results.errors, "N02", "rejected", "rejected" if passed else "accepted", passed,
                       f"status={status}")
    else:
        results.record(results.errors, "N02", "rejected", "SKIPPED", None, "group was not created")

    status, data = post(client, "/api/auth/login", {
        "username": "meera_admin",
        "password": "WrongPass99",
    })
    passed = status == 401 or not data.get("success", True)
    results.record(results.errors, "N03", "denied", "denied" if passed else "allowed", passed, f"status={status}")

    if campus_group_id:
        status, data = put(client, f"/api/groups/{campus_group_id}/rules", {
            "rules": "Tampered rules",
            "username": "rohan_m",
        })
        passed = status == 403 or not data.get("success", True)
        results.record(results.errors, "N04", "denied", "denied" if passed else "allowed", passed,
                       f"status={status}")
    else:
        results.record(results.errors, "N04", "denied", "SKIPPED", None, "group was not created")

    if lab_group_id:
        status, data = post(client, f"/api/groups/{lab_group_id}/images", {
            "username": "dev_p",
            "image_data": "",
            "mime_type": "image/png",
        })
        passed = status == 400 or not data.get("success", True)
        results.record(results.errors, "N05", "rejected", "rejected" if passed else "accepted", passed,
                       f"status={status}")
    else:
        results.record(results.errors, "N05", "rejected", "SKIPPED", None, "group was not created")

    if lab_group_id:
        status, data = post(client, f"/api/groups/{lab_group_id}/audio", {
            "username": "dev_p",
            "audio_data": "",
            "mime_type": "audio/wav",
        })
        passed = status == 400 or not data.get("success", True)
        results.record(results.errors, "N06", "rejected", "rejected" if passed else "accepted", passed,
                       f"status={status}")
    else:
        results.record(results.errors, "N06", "rejected", "SKIPPED", None, "group was not created")


def write_results(results, output_path, runtime_root, require_real_media, use_live_data):
    counts = results.overall_counts()
    duration = (datetime.now() - results.start_time).total_seconds()
    executed = counts["passed"] + counts["failed"]
    accuracy = (counts["passed"] / executed * 100) if executed else 0.0

    lines = [
        "=" * 90,
        "CONVOEASE REAL-MEDIA AUTOMATED TEST RESULTS",
        "=" * 90,
        f"Started             : {results.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration            : {duration:.1f} seconds",
        f"Project root        : {PROJECT_ROOT}",
        f"Runtime sandbox     : {'LIVE_APPLICATION_DATA' if use_live_data else runtime_root}",
        f"Results file        : {output_path}",
        f"Use live data       : {use_live_data}",
        f"Require real media  : {require_real_media}",
        f"Image asset dir     : {IMAGE_ASSET_DIR}",
        f"Audio asset dir     : {AUDIO_ASSET_DIR}",
        "",
        "SETUP",
        "-" * 90,
    ]

    for step_id, entry in results.setup.items():
        lines.append(f"{step_id:<6} {'PASS' if entry['passed'] else 'FAIL':<6} {entry['note']}")

    def append_bucket(title, bucket):
        bucket_counts = results._bucket_counts(bucket)
        lines.extend([
            "",
            title,
            "-" * 90,
            f"{'ID':<8} {'Expected':<16} {'Actual':<16} {'Outcome':<8} Note",
            f"{'-' * 8} {'-' * 16} {'-' * 16} {'-' * 8} {'-' * 36}",
        ])
        for test_id, entry in bucket.items():
            if entry["passed"] is True:
                outcome = "PASS"
            elif entry["passed"] is False:
                outcome = "FAIL"
            else:
                outcome = "SKIP"
            lines.append(
                f"{test_id:<8} {entry['expected']:<16} {entry['actual']:<16} "
                f"{outcome:<8} {entry['note'][:120]}"
            )
        lines.append(
            f"Summary: total={bucket_counts['total']} passed={bucket_counts['passed']} "
            f"failed={bucket_counts['failed']} skipped={bucket_counts['skipped']}"
        )

    append_bucket("TEXT TESTS", results.text)
    append_bucket("IMAGE TESTS", results.image)
    append_bucket("AUDIO TESTS", results.audio)
    append_bucket("ADMIN TESTS", results.admin)
    append_bucket("ERROR TESTS", results.errors)

    lines.extend([
        "",
        "MEDIA SOURCE USAGE",
        "-" * 90,
        (
            "Images: "
            f"real_file={results.media_usage['image']['real_file']} "
            f"demo_fallback={results.media_usage['image']['demo_fallback']} "
            f"skipped={results.media_usage['image']['skipped']}"
        ),
        (
            "Audio : "
            f"real_file={results.media_usage['audio']['real_file']} "
            f"demo_fallback={results.media_usage['audio']['demo_fallback']} "
            f"skipped={results.media_usage['audio']['skipped']}"
        ),
        "",
        "OVERALL",
        "-" * 90,
        f"Executed tests      : {executed}",
        f"Passed              : {counts['passed']}",
        f"Failed              : {counts['failed']}",
        f"Skipped             : {counts['skipped']}",
        f"Accuracy            : {accuracy:.1f}%",
    ])

    if results.notes:
        lines.extend(["", "NOTES", "-" * 90])
        for note in results.notes:
            lines.append(f"- {note}")

    overall_status = "PASS" if counts["failed"] == 0 else ("PARTIAL" if counts["passed"] > 0 else "FAIL")
    lines.extend([
        "",
        f"Overall status      : {overall_status}",
        "=" * 90,
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return overall_status


def parse_args():
    parser = argparse.ArgumentParser(description="Run ConvoEase backend automation with real-media placeholders.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Path for the text results file.")
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT, help="Sandbox root for CSV/media data.")
    parser.add_argument(
        "--use-live-data",
        action="store_true",
        help="Write users, messages, flagged results, and media into the application's live CSV/media storage.",
    )
    parser.add_argument(
        "--require-real-media",
        action="store_true",
        help="Skip image/audio cases unless the configured file_path exists on disk.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    ensure_runtime_directories()

    print(f"\n{BOLD}ConvoEase Real-Media Automated Test Suite{RESET}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Runtime sandbox: {'LIVE_APPLICATION_DATA' if args.use_live_data else args.runtime_root}")
    print(f"Results file: {args.output}")
    print(f"Image assets: {IMAGE_ASSET_DIR}")
    print(f"Audio assets: {AUDIO_ASSET_DIR}")
    print(f"Use live data: {args.use_live_data}")
    print(f"Require real media: {args.require_real_media}\n")

    results = Results()
    results.add_note(f"Drop real image files under {IMAGE_ASSET_DIR}")
    results.add_note(f"Drop real audio files under {AUDIO_ASSET_DIR}")
    if args.use_live_data:
        results.add_note("Live-data mode is enabled, so test users, messages, moderation outcomes, and media persist in the real app storage.")
    else:
        results.add_note(f"Runtime sandbox: {args.runtime_root}")
    if not args.require_real_media:
        results.add_note("When a media file path is missing, the suite falls back to a demo payload and labels it clearly.")

    try:
        client = build_test_client(args.runtime_root, use_live_data=args.use_live_data)
    except Exception as exc:
        print(f"{RED}FATAL: could not build Flask app: {exc}{RESET}")
        traceback.print_exc()
        sys.exit(1)

    try:
        group_ids = run_setup(client, results)
        run_text_tests(client, group_ids, results)
        run_image_tests(client, group_ids, results, args.require_real_media)
        run_audio_tests(client, group_ids, results, args.require_real_media)
        run_admin_tests(client, group_ids, results)
        run_error_tests(client, group_ids, results)
    except Exception as exc:
        results.add_note(f"Run aborted by unexpected error: {exc}")
        traceback.print_exc()

    header("WRITING RESULTS")
    try:
        overall_status = write_results(
            results,
            args.output,
            args.runtime_root,
            args.require_real_media,
            args.use_live_data,
        )
        ok(f"Results written to {args.output}")
    except Exception as exc:
        overall_status = "FAIL"
        fail(f"Could not write results file: {exc}")

    counts = results.overall_counts()
    executed = counts["passed"] + counts["failed"]
    accuracy = (counts["passed"] / executed * 100) if executed else 0.0
    header("FINAL SUMMARY")
    print(f"  Executed : {executed}")
    print(f"  Passed   : {counts['passed']}")
    print(f"  Failed   : {counts['failed']}")
    print(f"  Skipped  : {counts['skipped']}")
    print(f"  Accuracy : {accuracy:.1f}%")
    print(
        "  Image src: "
        f"real={results.media_usage['image']['real_file']} "
        f"demo={results.media_usage['image']['demo_fallback']} "
        f"skip={results.media_usage['image']['skipped']}"
    )
    print(
        "  Audio src: "
        f"real={results.media_usage['audio']['real_file']} "
        f"demo={results.media_usage['audio']['demo_fallback']} "
        f"skip={results.media_usage['audio']['skipped']}"
    )
    color = GREEN if overall_status == "PASS" else (YELLOW if overall_status == "PARTIAL" else RED)
    print(f"\n  {color}{BOLD}Overall: {overall_status}{RESET}\n")


if __name__ == "__main__":
    main()
