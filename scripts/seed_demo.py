"""
Seed a ready-made demo community: users, groups, a week of chat history,
moderation results (held messages, appeals, deleted messages) and a few
images / voice notes. Handy for showing the app without setting anything up.

Usage:
    python scripts/seed_demo.py                 # into DATABASE_URL (or local SQLite)
    python scripts/seed_demo.py --reset         # wipe the demo data and rebuild it with fresh dates
    python scripts/seed_demo.py --reset --yes   # needed when DATABASE_URL is a hosted database
    python scripts/seed_demo.py --password "Demo@1234"

Only the demo users and the three demo groups below are ever touched. The
moderation results are written directly (no AI calls), so it is free, fast and
gives the same demo every time. Safe to run more than once.
"""

import argparse
import io
import math
import os
import struct
import sys
import uuid
import wave
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import delete, insert, select, update  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

import config  # noqa: E402
from database.Database_processing.db_manager import (  # noqa: E402
    DBManager,
    chat_groups,
    group_members,
    media,
    messages,
    normalize_database_url,
    users,
)
from database.Database_processing.user_store import hash_password  # noqa: E402

DEFAULT_PASSWORD = "Demo@1234"

# ── People ────────────────────────────────────────────────────────────────
# username, full name, bio, avatar
PEOPLE = [
    ("demo_priya", "Priya Sharma", "CS senior. Runs the study group and loves explaining algorithms.", "owl"),
    ("demo_aarav", "Aarav Mehta", "Founder building developer tools. Cricket on weekends.", "rocket"),
    ("demo_rohan", "Rohan Iyer", "Captain of the weekend cricket club.", "lion"),
    ("demo_meera", "Meera Nair", "Product designer and study-group scorekeeper.", "cat"),
    ("demo_kabir", "Kabir Singh", "Backend engineer. Posts a little too fast sometimes.", "fox"),
    ("demo_sana", "Sana Khan", "Building invoicing software for clinics.", "panda"),
    ("demo_vikram", "Vikram Rao", "Frequently trips the moderation rules (on purpose, for the demo).", "wolf"),
]

# ── Groups ────────────────────────────────────────────────────────────────
CS_RULES = "\n".join([
    "1. Keep discussion relevant to coursework, projects and campus academics.",
    "2. Be respectful. No insults, harassment or abusive language.",
    "3. No sharing exam answers or asking for help to cheat (academic integrity).",
    "4. No advertising, promotions or spam.",
    "5. Do not share personal data such as phone numbers or home addresses.",
])
STARTUP_RULES = "\n".join([
    "1. Stay on topic: building products, fundraising, hiring and tooling.",
    "2. Give constructive feedback only. No personal attacks.",
    "3. No unsolicited promotion, referral links, discount codes or get-rich-quick schemes.",
    "4. Do not share confidential investor or customer information.",
    "5. Do not present unverified claims or statistics as fact.",
])
CRICKET_RULES = "\n".join([
    "1. Cricket, match plans and friendly banter only.",
    "2. No abuse, slurs or threats. Banter is fine, hate is not.",
    "3. No politics or religion debates.",
    "4. No spam or advertising.",
    "5. Do not share private information such as phone numbers.",
])

# group_id, name, admin, sensitivity, rules, members (admin first)
GROUPS = [
    ("DEMOCS", "Campus CS Study Group", "demo_priya", "Moderate", CS_RULES,
     ["demo_priya", "demo_meera", "demo_sana", "demo_kabir", "demo_vikram", "demo_rohan", "demo_aarav"]),
    ("DEMOST", "Startup Builders Hub", "demo_aarav", "Strict", STARTUP_RULES,
     ["demo_aarav", "demo_priya", "demo_sana", "demo_kabir", "demo_meera", "demo_vikram"]),
    ("DEMOCR", "Weekend Cricket Club", "demo_rohan", "Relaxed", CRICKET_RULES,
     ["demo_rohan", "demo_kabir", "demo_aarav", "demo_meera", "demo_vikram"]),
]

# user -> {group_id: how many of the newest messages from others are still unread}
UNREAD = {
    "demo_meera": {"DEMOCS": 3},
    "demo_sana": {"DEMOST": 3, "DEMOCS": 1},
    "demo_kabir": {"DEMOCR": 2},
    "demo_vikram": {"DEMOCS": 4},
}


# ── Message builders ──────────────────────────────────────────────────────
class Entry(dict):
    pass


def ago(days=0, hours=0, minutes=0):
    return timedelta(days=days, hours=hours, minutes=minutes)


def ok(user, text, when):
    return Entry(user=user, text=text, when=when, status="PASS")


def deleted(user, when):
    return Entry(user=user, text="[deleted]", when=when, status="DELETED",
                 reason="Deleted by sender.", initial_status="PASS")


def held(user, text, reason, when, appeal=None):
    """A message the moderator held. `appeal` = (kind, user_text, ai_status, ai_reason, admin_note)."""
    return Entry(user=user, text=text, when=when, status="FLAGGED", reason=reason, appeal=appeal)


def image(user, key, summary, when, reason=""):
    return Entry(user=user, text="[IMAGE]", when=when, status="FLAGGED" if reason else "PASS",
                 reason=reason, summary=summary, media=("image", key))


def audio(user, key, summary, when, reason=""):
    return Entry(user=user, text="[AUDIO]", when=when, status="FLAGGED" if reason else "PASS",
                 reason=reason, summary=summary, media=("audio", key))


def appeal(kind, user_text, ai_status, ai_reason, admin_note=""):
    return (kind, user_text, ai_status, ai_reason, admin_note)


CAMPUS = [
    ok("demo_priya", "Welcome everyone! This is our space for DSA, OS and DBMS coursework. Please read the group rules.", ago(6, 0)),
    ok("demo_meera", "Thanks for setting this up, Priya! Has anyone started on DSA assignment 3 yet?", ago(5, 23, 40)),
    ok("demo_sana", "Yes, I'm stuck on the balanced BST question. Do we need to implement AVL rotations by hand?", ago(5, 23, 10)),
    ok("demo_priya", "Yes, at least left-left and right-right. The week 5 lecture slides cover the rotations.", ago(5, 22, 30)),
    image("demo_sana", "bst_notes", "Handwritten-style notes showing a binary search tree with its inorder traversal order.", ago(5, 21, 50)),
    ok("demo_meera", "These notes are super clear, thank you!", ago(5, 21, 20)),
    ok("demo_kabir", "Has anyone done the OS scheduling lab? The round robin time quantum is confusing me.", ago(5, 20, 0)),
    held("demo_vikram", "BUY NOTES + ANSWERS for ALL semesters, 50% OFF. DM me or visit studyhub-deals.example",
         "Rule 4 violation: Advertising and spam.", ago(5, 18, 45)),
    ok("demo_priya", "Heads up: the ad above was held automatically. Please keep promotions out of this group.", ago(5, 18, 30)),
    held("demo_kabir", "Does anyone have the answers to tomorrow's DBMS internal? I will pay for the answer key.",
         "Rule 3 violation: Asks for exam answers, which breaks academic integrity.", ago(4, 22, 0),
         appeal("REJECTED", "I only meant last year's paper solutions, not tomorrow's key.", "FLAGGED",
                "The message explicitly asks for the answer key to an upcoming internal exam, which the rules prohibit.",
                "Please use the practice papers on the department drive instead.")),
    ok("demo_sana", "The practice papers for DBMS are on the department drive. That's the best way to prep.", ago(4, 21, 30)),
    ok("demo_meera", "+1. Normalisation questions repeat every year too, so revise 3NF and BCNF.", ago(4, 20, 40)),
    held("demo_vikram", "you people are such useless nerds, nobody even reads these notes lol",
         "Rule 2 violation: Contains insults and abusive language.", ago(3, 23, 0)),
    ok("demo_rohan", "Quick question: is the OS lab on Thursday or Friday?", ago(3, 22, 0)),
    ok("demo_priya", "Thursday, 2 PM in Lab 3.", ago(3, 21, 45)),
    held("demo_rohan", "What's everyone's plan for the weekend cricket match?",
         "Rule 1 violation: Off-topic, not related to coursework.", ago(3, 20, 0),
         appeal("APPROVED", "It's the CS department team match, so it's campus related.", "PASS",
                "The message refers to a department event, which could reasonably count as campus related.",
                "Department events are fine. Approved this once.")),
    held("demo_kabir", "Sana, my number is 98765 43210 if you want to coordinate the lab project.",
         "Rule 5 violation: Shares a phone number (personal data).", ago(2, 23, 0),
         appeal("PENDING_ADMIN", "Sana asked me to share it for the project. Can this be allowed?", "FLAGGED",
                "Even with consent, posting a number exposes it to every member. A direct message is safer.")),
    ok("demo_sana", "Kabir, DM me and I'll coordinate there!", ago(2, 22, 15)),
    ok("demo_meera", "Anyone up for a study group before the OS midterm? Saturday 5 PM on Meet?", ago(2, 20, 0)),
    ok("demo_sana", "Count me in!", ago(2, 19, 40)),
    ok("demo_kabir", "In too.", ago(2, 19, 20)),
    ok("demo_priya", "Reminder: assignment 3 is due Monday 11:59 PM. Late submissions lose 10% per day.", ago(1, 22, 0)),
    ok("demo_aarav", "Can someone explain the difference between a mutex and a semaphore with an example?", ago(1, 21, 0)),
    ok("demo_priya", "A mutex has an owner, one holder at a time. A semaphore is a counter for N resources. Think single bathroom key vs a parking lot with N spots.", ago(1, 20, 0)),
    ok("demo_aarav", "The parking lot analogy finally made it click, thanks!", ago(1, 19, 30)),
    deleted("demo_meera", ago(1, 18, 0)),
    ok("demo_meera", "Meet link for Saturday's study session is in the calendar invite. 5 PM sharp.", ago(0, 22, 0)),
    image("demo_vikram", "free_iphone", "A promotional banner advertising a free iPhone giveaway with a click-now call to action.",
          ago(0, 5, 0), reason="Rule 4 violation: Image is a promotional giveaway banner (spam)."),
    ok("demo_sana", "Quick poll: should we move Saturday's study session to 6 PM?", ago(0, 3, 0)),
    ok("demo_priya", "6 PM works for me.", ago(0, 2, 0)),
    ok("demo_kabir", "6 is fine by me.", ago(0, 1, 0)),
    ok("demo_meera", "Great, 6 PM it is. I'll update the invite.", ago(0, 0, 30)),
]

STARTUP = [
    ok("demo_aarav", "Welcome to Startup Builders Hub! Share what you're building, ask for feedback and trade hiring and fundraising lessons.", ago(6, 0)),
    ok("demo_sana", "I'm building a B2B invoicing tool for small clinics. 12 pilot customers so far. Would love feedback on onboarding.", ago(5, 23, 0)),
    ok("demo_priya", "Nice! What's the biggest drop-off, account setup or the first invoice?", ago(5, 22, 0)),
    ok("demo_sana", "First invoice. About 40% of users stall there.", ago(5, 21, 40)),
    ok("demo_priya", "Try a pre-filled sample invoice. We saw a similar drop and that fixed most of it.", ago(5, 20, 50)),
    ok("demo_kabir", "We're hiring our first backend engineer, ideally strong with Postgres and queues. Where should we look?", ago(5, 19, 0)),
    ok("demo_aarav", "Post in niche communities and ask your first customers' engineers for referrals.", ago(5, 18, 20)),
    held("demo_vikram", "Guaranteed 10x returns in 30 days! Invest in my crypto coin, DM me for the referral link.",
         "Rule 3 violation: Promotion of a get-rich-quick crypto scheme.", ago(4, 23, 0)),
    image("demo_aarav", "mrr_growth", "A bar chart of monthly recurring revenue growing from about $2k to $9k over six months.", ago(4, 22, 0)),
    ok("demo_meera", "Congrats! That's solid growth. What drove the jump in month 5?", ago(4, 21, 20)),
    ok("demo_aarav", "Mostly the partnership channel plus a pricing change.", ago(4, 20, 30)),
    held("demo_kabir", "Heard from an investor that they're leading Acme's Series B at a 40M valuation. Keep it confidential, don't repeat it.",
         "Rule 4 violation: Shares confidential investor information.", ago(3, 23, 0),
         appeal("APPROVED", "It was announced publicly on TechCrunch this morning.", "PASS",
                "If the round was publicly announced, the information is no longer confidential.",
                "Verified that the round is public. Approved.")),
    ok("demo_priya", "Interesting. Is Acme seed stage or growth stage?", ago(3, 22, 0)),
    held("demo_vikram", "Your product is trash and so are your founders, quit now.",
         "Rule 2 violation: Personal insults instead of constructive feedback.", ago(3, 21, 0)),
    ok("demo_sana", "Does anyone have experience preparing a tiny team for SOC 2?", ago(2, 23, 0)),
    ok("demo_priya", "Use a compliance automation tool and start with a policy baseline. It took us about 6 weeks.", ago(2, 22, 0)),
    held("demo_sana", "Studies show 90% of startups that skip SOC 2 lose enterprise deals, it's proven.",
         "Rule 5 violation: Unverified statistic presented as fact.", ago(2, 20, 0),
         appeal("PENDING_ADMIN", "It comes from a 2024 compliance vendor report. I can link the source.", "FLAGGED",
                "No source is cited in the message, so the statistic cannot be verified as written.")),
    ok("demo_meera", "Weekly check-in: we shipped our beta to 50 waitlist users. Feedback welcome!", ago(1, 22, 0)),
    ok("demo_aarav", "Congrats Meera! Collect feedback through short calls rather than surveys.", ago(1, 21, 0)),
    deleted("demo_kabir", ago(1, 20, 0)),
    ok("demo_aarav", "Lunch and learn on pricing next Friday. Anyone want to present their pricing story?", ago(1, 3, 0)),
    ok("demo_sana", "I can present ours.", ago(0, 20, 0)),
    audio("demo_kabir", "hiring_tips", "Kabir shares three tips for hiring a first backend engineer: use referrals, run a paid trial project and be clear about equity.",
          ago(0, 19, 0)),
    ok("demo_priya", "Count me in as a listener.", ago(0, 4, 0)),
    held("demo_vikram", "Check out my brand new course: learn dropshipping in 3 days, use code VIK50 for a discount!",
         "Rule 3 violation: Unsolicited promotion with a discount code.", ago(0, 2, 0)),
    ok("demo_aarav", "Reminder: no promotions here, the rules are strict. Thanks all.", ago(0, 1, 0)),
    ok("demo_meera", "Thanks for the feedback tips, Aarav. Trying short calls this week.", ago(0, 0, 40)),
    ok("demo_kabir", "Same, will book five calls tomorrow.", ago(0, 0, 20)),
]

CRICKET = [
    ok("demo_rohan", "Welcome to the Weekend Cricket Club! Matches every Sunday at 7 AM, Shivaji Park.", ago(6, 0)),
    ok("demo_kabir", "Count me in. I'll bring the stumps.", ago(5, 23, 0)),
    ok("demo_aarav", "Can I bowl first change this time? Last week's death overs were a disaster \U0001F605", ago(5, 21, 0)),
    ok("demo_meera", "I'll handle scoring and water.", ago(5, 20, 0)),
    ok("demo_vikram", "Bhai kal ka match mast tha, kya six maara Kabir ne!", ago(4, 22, 0)),
    ok("demo_kabir", "Haha thanks yaar, bas timing sahi thi.", ago(4, 21, 30)),
    image("demo_rohan", "scorecard", "A scorecard showing 142 for 6 in 20 overs with a top score of 58 runs.", ago(3, 22, 0)),
    ok("demo_aarav", "Great effort team. 142 is a decent total.", ago(3, 21, 0)),
    held("demo_vikram", "That umpire was blind, the LBW was missing leg stump by a mile. You idiots all cheated.",
         "Rule 2 violation: Abusive language directed at the umpire and teammates.", ago(2, 23, 0),
         appeal("REJECTED", "I was only joking, it's banter.", "FLAGGED",
                "Calling teammates idiots and accusing them of cheating goes beyond friendly banter.",
                "Banter is fine, calling people idiots isn't.")),
    ok("demo_meera", "Let's not blame the umpire. Who's in for nets on Wednesday?", ago(2, 22, 0)),
    ok("demo_kabir", "Wednesday 6 PM works for me.", ago(2, 21, 0)),
    held("demo_aarav", "Election results are out! Let's talk about which party should win next. Vote for X!",
         "Rule 3 violation: Political campaigning is off-topic for this group.", ago(1, 20, 0)),
    ok("demo_rohan", "Folks, politics out please. Let's keep it cricket.", ago(1, 19, 30)),
    image("demo_vikram", "rally_poster", "A political rally poster urging people to vote for change this Sunday.", ago(1, 18, 0),
          reason="Rule 3 violation: Political poster, off-topic for this group."),
    audio("demo_rohan", "sunday_plan", "Rohan shares the Sunday plan: nets at 6, toss at 7, and everyone should bring white clothes.", ago(1, 6, 0)),
    ok("demo_kabir", "Got it, I'll be there.", ago(1, 5, 0)),
    held("demo_meera", "Hey, my number is 91234 56789, call me if you're running late.",
         "Rule 5 violation: Shares a phone number (personal data).", ago(0, 23, 0),
         appeal("APPROVED", "Members agreed to share numbers for match-day coordination.", "FLAGGED",
                "The message posts a personal number to the whole group, which the rules prohibit.",
                "The team agreed on this for match days. Approved.")),
    ok("demo_aarav", "Who's keeping wickets on Sunday?", ago(0, 12, 0)),
    ok("demo_kabir", "I'll keep wickets. Aarav can open the bowling.", ago(0, 11, 0)),
    held("demo_vikram", "BUY cricket bats 70% off! www.batsale.example click now!!!",
         "Rule 4 violation: Advertising and spam.", ago(0, 4, 0)),
    ok("demo_rohan", "Weather says clear skies for Sunday \U0001F324️ See you all at 7.", ago(0, 2, 0)),
    ok("demo_aarav", "Perfect. Bringing the kit bag.", ago(0, 1, 0)),
]

CONVERSATIONS = {"DEMOCS": CAMPUS, "DEMOST": STARTUP, "DEMOCR": CRICKET}


# ── Generated media ───────────────────────────────────────────────────────
def _font(size):
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


def _png(draw_fn, size=(640, 400), background=(250, 250, 247)):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", size, background)
    draw_fn(ImageDraw.Draw(img), size)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def _draw_bst(d, size):
    d.text((24, 18), "BST notes: inorder = left, root, right", fill=(40, 40, 120), font=_font(22))
    nodes = {50: (320, 90), 30: (200, 190), 70: (440, 190), 20: (140, 290), 40: (260, 290), 60: (380, 290), 80: (500, 290)}
    edges = [(50, 30), (50, 70), (30, 20), (30, 40), (70, 60), (70, 80)]
    for a, b in edges:
        d.line([nodes[a], nodes[b]], fill=(90, 90, 90), width=3)
    for value, (x, y) in nodes.items():
        d.ellipse([x - 26, y - 26, x + 26, y + 26], fill=(255, 255, 255), outline=(40, 40, 120), width=3)
        d.text((x - 12, y - 11), str(value), fill=(20, 20, 20), font=_font(20))
    d.text((24, 350), "Inorder: 20, 30, 40, 50, 60, 70, 80", fill=(160, 40, 40), font=_font(20))


def _draw_banner(d, size):
    d.rectangle([0, 0, *size], fill=(220, 30, 60))
    d.text((60, 80), "WIN A FREE iPHONE!", fill=(255, 255, 255), font=_font(52))
    d.text((60, 170), "Limited offer. Click now to claim!", fill=(255, 235, 120), font=_font(30))
    d.rounded_rectangle([60, 250, 360, 320], radius=14, fill=(255, 235, 120))
    d.text((100, 268), "CLAIM NOW", fill=(160, 20, 40), font=_font(32))


def _draw_growth(d, size):
    d.text((24, 16), "Monthly recurring revenue ($k)", fill=(30, 30, 30), font=_font(24))
    values = [2.1, 3.0, 3.8, 5.2, 7.4, 9.1]
    base, top = 360, 70
    for i, value in enumerate(values):
        x = 60 + i * 95
        y = base - (value / 10) * (base - top)
        d.rectangle([x, y, x + 62, base], fill=(40, 130, 90))
        d.text((x + 8, y - 28), f"{value:.1f}", fill=(30, 30, 30), font=_font(20))
        d.text((x + 8, base + 6), f"M{i + 1}", fill=(90, 90, 90), font=_font(18))
    d.line([(40, base), (620, base)], fill=(120, 120, 120), width=2)


def _draw_scorecard(d, size):
    d.rectangle([0, 0, size[0], 70], fill=(20, 90, 50))
    d.text((24, 18), "Weekend Cricket Club - Match Scorecard", fill=(255, 255, 255), font=_font(26))
    rows = [("Kabir S", "58", "34"), ("Aarav M", "31", "22"), ("Rohan I", "24", "19"), ("Meera N", "12", "10"), ("Extras", "17", "")]
    d.text((40, 100), "Batter", fill=(60, 60, 60), font=_font(20))
    d.text((300, 100), "Runs", fill=(60, 60, 60), font=_font(20))
    d.text((420, 100), "Balls", fill=(60, 60, 60), font=_font(20))
    for i, (name, runs, balls) in enumerate(rows):
        y = 140 + i * 40
        d.text((40, y), name, fill=(20, 20, 20), font=_font(22))
        d.text((300, y), runs, fill=(20, 20, 20), font=_font(22))
        d.text((420, y), balls, fill=(20, 20, 20), font=_font(22))
    d.text((40, 350), "Total: 142 / 6 (20 overs)", fill=(160, 40, 40), font=_font(26))


def _draw_poster(d, size):
    d.rectangle([0, 0, *size], fill=(30, 60, 140))
    d.text((60, 60), "VOTE FOR CHANGE", fill=(255, 255, 255), font=_font(54))
    d.text((60, 160), "Grand rally this Sunday", fill=(255, 200, 60), font=_font(32))
    d.text((60, 220), "Join us. Make your voice count.", fill=(230, 230, 255), font=_font(26))
    d.rectangle([60, 300, 580, 308], fill=(255, 200, 60))


IMAGES = {
    "bst_notes": _draw_bst,
    "free_iphone": _draw_banner,
    "mrr_growth": _draw_growth,
    "scorecard": _draw_scorecard,
    "rally_poster": _draw_poster,
}

# A short tune per voice note (note frequencies in Hz, 0 = rest).
TUNES = {
    "hiring_tips": [392, 440, 494, 523, 494, 440, 392, 0, 330, 392, 440, 392],
    "sunday_plan": [330, 392, 440, 523, 440, 392, 330, 0, 392, 494, 523, 659],
}


def make_wav(notes, rate=8000, note_seconds=0.22):
    frames = bytearray()
    for freq in notes:
        count = int(rate * note_seconds)
        for n in range(count):
            envelope = min(1.0, n / 200, (count - n) / 200)
            sample = 0.0 if not freq else math.sin(2 * math.pi * freq * n / rate) * 0.35 * envelope
            frames += struct.pack("<h", int(sample * 32767))
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))
    return out.getvalue()


def build_media(kind, key):
    """Return (bytes, mime_type, extension) or None when it can't be generated."""
    if kind == "image":
        try:
            return _png(IMAGES[key]), "image/png", "png"
        except ImportError:
            return None
    return make_wav(TUNES[key]), "audio/wav", "wav"


# ── Seeding ───────────────────────────────────────────────────────────────
def stamp(moment):
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def describe_target():
    url = make_url(normalize_database_url(config.DATABASE_URL))
    if url.drivername.startswith("sqlite"):
        return f"SQLite file {url.database}", False
    return f"{url.drivername.split('+')[0]} database on {url.host}/{url.database}", True


def wipe_demo_data(conn):
    group_ids = [g[0] for g in GROUPS]
    conn.execute(delete(messages).where(messages.c.group_id.in_(group_ids)))
    conn.execute(delete(media).where(media.c.group_id.in_(group_ids)))
    conn.execute(delete(group_members).where(group_members.c.group_id.in_(group_ids)))
    conn.execute(delete(chat_groups).where(chat_groups.c.group_id.in_(group_ids)))
    conn.execute(delete(users).where(users.c.username.in_([p[0] for p in PEOPLE])))


def seed(password, reset):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    DBManager.initialize()

    with DBManager.begin() as conn:
        if reset:
            wipe_demo_data(conn)

        existing_users = {r[0] for r in conn.execute(select(users.c.username))}
        existing_groups = {r[0] for r in conn.execute(select(chat_groups.c.group_id))}

        pw_hash = hash_password(password)
        for i, (username, full_name, bio, avatar) in enumerate(PEOPLE):
            if username in existing_users:
                continue
            conn.execute(insert(users).values(
                username=username, password=pw_hash, full_name=full_name, bio=bio,
                profile_pic_color="#%06x" % ((0x3366CC + i * 0x151515) & 0xFFFFFF),
                avatar=avatar, created_at=stamp(now - ago(7)),
            ))

        seeded, skipped = [], []
        for group_id, name, admin, sensitivity, rules, members in GROUPS:
            if group_id in existing_groups:
                skipped.append(name)
                continue
            conn.execute(insert(chat_groups).values(
                group_id=group_id, group_name=name, admin_username=admin, password="",
                rules=rules, moderation_sensitivity=sensitivity, created_at=stamp(now - ago(7)),
            ))
            for n, member in enumerate(members):
                conn.execute(insert(group_members).values(
                    group_id=group_id, username=member,
                    joined_at=stamp(now - ago(6, 23) + timedelta(minutes=n)), last_read_seq=0,
                ))

            # Oldest first, so message numbers (seq) follow the conversation order.
            entries = sorted(CONVERSATIONS[group_id], key=lambda e: e["when"], reverse=True)
            ids = []
            for entry in entries:
                media_url = ""
                if entry.get("media"):
                    kind, key = entry["media"]
                    built = build_media(kind, key)
                    if built is None:  # Pillow missing: keep the text, skip the picture
                        continue
                    data, mime, ext = built
                    media_id = f"{uuid.uuid4()}.{ext}"
                    moment = stamp(now - entry["when"])
                    conn.execute(insert(media).values(
                        media_id=media_id, kind=kind, group_id=group_id, username=entry["user"],
                        mime_type=mime, size=len(data), data=data, created_at=moment,
                    ))
                    media_url = f"/media/{kind}/{media_id}"

                message_id = str(uuid.uuid4())
                moment = now - entry["when"]
                row = dict(
                    message_id=message_id, group_id=group_id, username=entry["user"],
                    message=entry["text"], status=entry["status"], reason=entry.get("reason", ""),
                    summary=entry.get("summary", ""), media_url=media_url, group_rules=rules,
                    timestamp=stamp(moment),
                    initial_status=entry.get("initial_status") or entry["status"],
                    initial_reason=entry.get("reason", ""),
                    detected_language="", language_confidence="", translated_message="",
                    appeal_status="", appeal_text="", appeal_ai_status="", appeal_ai_reason="",
                    appeal_submitted_at="", appeal_reviewed_by="", appeal_reviewed_at="", appeal_admin_note="",
                )
                if entry.get("appeal"):
                    kind, text, ai_status, ai_reason, note = entry["appeal"]
                    submitted = moment + timedelta(minutes=25)
                    row.update(
                        appeal_status=kind, appeal_text=text, appeal_ai_status=ai_status,
                        appeal_ai_reason=ai_reason, appeal_submitted_at=stamp(submitted),
                    )
                    if kind in ("APPROVED", "REJECTED"):
                        row.update(
                            appeal_reviewed_by=admin, appeal_reviewed_at=stamp(submitted + timedelta(hours=3)),
                            appeal_admin_note=note,
                        )
                        if kind == "APPROVED":
                            row.update(status="PASS", reason=note)
                        else:
                            row.update(status="FLAGGED", reason=note)
                conn.execute(insert(messages).values(**row))
                ids.append((message_id, entry["user"], row["status"]))

            # Read positions: everyone is caught up except the people listed in UNREAD.
            seq_by_id = {r[0]: r[1] for r in conn.execute(
                select(messages.c.message_id, messages.c.seq).where(messages.c.group_id == group_id))}
            visible = [(seq_by_id[mid], user) for mid, user, status in ids if status == "PASS"]
            last_seq = max((s for s, _ in visible), default=0)
            for member in members:
                unread = UNREAD.get(member, {}).get(group_id, 0)
                others = sorted(s for s, u in visible if u != member)
                if not unread:
                    read_to = last_seq
                elif unread >= len(others):
                    read_to = 0
                else:
                    read_to = others[-unread - 1]
                conn.execute(
                    update(group_members)
                    .where((group_members.c.group_id == group_id) & (group_members.c.username == member))
                    .values(last_read_seq=read_to)
                )
            seeded.append((name, len(ids)))
    return seeded, skipped


def main():
    parser = argparse.ArgumentParser(description="Seed a demo community.")
    parser.add_argument("--reset", action="store_true", help="delete the demo users/groups first and rebuild with fresh dates")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help=f"password for every demo user (default {DEFAULT_PASSWORD})")
    parser.add_argument("--yes", action="store_true", help="confirm writing to a hosted (non-SQLite) database")
    args = parser.parse_args()

    if len(args.password) < 6:
        parser.error("password must be at least 6 characters")

    target, hosted = describe_target()
    print(f"Target: {target}")
    if hosted and not args.yes:
        print("This is a hosted database. Re-run with --yes to confirm.")
        return 1

    seeded, skipped = seed(args.password, args.reset)
    for name, count in seeded:
        print(f"  seeded  {name}: {count} messages")
    for name in skipped:
        print(f"  exists  {name} (use --reset to rebuild it)")

    print("\nLogins (password for all: %s)" % args.password)
    for username, full_name, _bio, _avatar in PEOPLE:
        groups = ", ".join(f"{g[1]}{' (admin)' if g[2] == username else ''}" for g in GROUPS if username in g[5])
        print(f"  {username:<12} {full_name:<14} {groups}")
    print("\nGroup IDs: " + ", ".join(f"{g[0]} = {g[1]}" for g in GROUPS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
