"""
One-time import of v4 data (CSV files + media folder) into the v5 database.

Usage:
    python scripts/import_legacy_csv.py                 # into DATABASE_URL (or local SQLite)
    python scripts/import_legacy_csv.py --utc-offset +05:30

Old timestamps were saved in the server's local time. By default they are
treated as this computer's local time zone and converted to UTC; pass
--utc-offset to say which zone they were recorded in.

Safe to run more than once: rows that already exist are skipped.
"""

import argparse
import csv
import mimetypes
import os
import re
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import select  # noqa: E402

import config  # noqa: E402
from database.Database_processing.db_manager import (  # noqa: E402
    DBManager,
    chat_groups,
    group_members,
    media,
    messages,
    users,
)

csv.field_size_limit(10 * 1024 * 1024)


def read_csv(name):
    path = os.path.join(config.LEGACY_CSV_DIR, name)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return [{key: (value or "") for key, value in row.items()} for row in csv.DictReader(handle)]


def parse_offset(text):
    match = re.fullmatch(r"([+-])(\d{1,2}):?(\d{2})", text.strip())
    if not match:
        raise argparse.ArgumentTypeError("Use a format like +05:30 or -04:00")
    sign = 1 if match.group(1) == "+" else -1
    return timezone(sign * timedelta(hours=int(match.group(2)), minutes=int(match.group(3))))


def to_utc(value, source_tz):
    value = (value or "").strip()
    if not value:
        return ""
    try:
        local = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value
    aware = local.replace(tzinfo=source_tz) if source_tz else local.astimezone()
    return aware.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def existing(column):
    return {row[column.name] for row in DBManager.fetch_all(select(column))}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--utc-offset", type=parse_offset, default=None,
                        help="Time zone the old timestamps were recorded in, e.g. +05:30")
    args = parser.parse_args()
    tz = args.utc_offset

    DBManager.initialize()
    print(f"Importing into: {config.DATABASE_URL.split('@')[-1]}")

    known_users = existing(users.c.username)
    new_users = []
    for row in read_csv("users.csv"):
        name = row.get("username", "").strip()
        if not name or name in known_users:
            continue
        known_users.add(name)
        new_users.append({
            "username": name,
            # Old unsalted hashes still work and are upgraded at next login.
            "password": row.get("password", ""),
            "full_name": row.get("full_name", "") or name,
            "bio": row.get("bio", ""),
            "profile_pic_color": row.get("profile_pic_color", ""),
            "avatar": row.get("avatar", ""),
            "created_at": to_utc(row.get("created_at", ""), tz),
        })

    known_groups = existing(chat_groups.c.group_id)
    new_groups = []
    for row in read_csv("groups.csv"):
        group_id = row.get("group_id", "").strip()
        if not group_id or group_id in known_groups:
            continue
        known_groups.add(group_id)
        sensitivity = (row.get("moderation_sensitivity", "") or "Moderate").strip().title()
        new_groups.append({
            "group_id": group_id,
            "group_name": row.get("group_name", "") or group_id,
            "admin_username": row.get("admin_username", ""),
            "password": row.get("password", ""),
            "rules": row.get("rules", ""),
            "moderation_sensitivity": sensitivity if sensitivity in {"Strict", "Moderate", "Relaxed"} else "Moderate",
            "created_at": to_utc(row.get("created_at", ""), tz),
        })

    known_members = {(r["group_id"], r["username"]) for r in DBManager.fetch_all(select(group_members))}
    new_members = []
    for row in read_csv("group_members.csv"):
        key = (row.get("group_id", "").strip(), row.get("username", "").strip())
        if not all(key) or key in known_members or key[0] not in known_groups:
            continue
        known_members.add(key)
        new_members.append({"group_id": key[0], "username": key[1],
                            "joined_at": to_utc(row.get("joined_at", ""), tz), "last_read_seq": 0})

    known_messages = existing(messages.c.message_id)
    message_columns = [c.name for c in messages.columns if c.name != "seq"]
    chat_rows = sorted(read_csv("group_chats.csv"), key=lambda r: r.get("timestamp", ""))
    new_messages = []
    media_groups = {}
    for row in chat_rows:
        message_id = row.get("message_id", "").strip()
        if not message_id or message_id in known_messages or row.get("group_id", "") not in known_groups:
            continue
        known_messages.add(message_id)
        record = {name: row.get(name, "") for name in message_columns}
        for name in ("timestamp", "appeal_submitted_at", "appeal_reviewed_at"):
            record[name] = to_utc(record[name], tz)
        record["initial_status"] = record["initial_status"] or record["status"]
        new_messages.append(record)
        if record["media_url"]:
            media_groups[record["media_url"]] = (record["group_id"], record["username"])

    known_media = existing(media.c.media_id)
    new_media = []
    for url, (group_id, username) in media_groups.items():
        match = re.fullmatch(r"/media/(image|audio)/([\w.-]+)", url)
        if not match:
            continue
        kind, media_id = match.groups()
        path = os.path.join(config.MEDIA_DIR, kind, media_id)
        if media_id in known_media or not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            data = handle.read()
        mime_type = mimetypes.guess_type(media_id)[0] or ("image/png" if kind == "image" else "audio/mpeg")
        new_media.append({
            "media_id": media_id, "kind": kind, "group_id": group_id, "username": username,
            "mime_type": mime_type, "size": len(data), "data": data, "created_at": "",
        })

    with DBManager.begin() as conn:
        for table, rows in ((users, new_users), (chat_groups, new_groups), (group_members, new_members),
                            (messages, new_messages), (media, new_media)):
            if rows:
                conn.execute(table.insert(), rows)

    # Mark imported history as read so nobody starts with hundreds of unread messages.
    if new_messages:
        with DBManager.begin() as conn:
            for (group_id, username) in known_members:
                top = conn.execute(
                    select(messages.c.seq).where(messages.c.group_id == group_id)
                    .order_by(messages.c.seq.desc()).limit(1)
                ).scalar()
                if top:
                    conn.execute(
                        group_members.update()
                        .where((group_members.c.group_id == group_id) & (group_members.c.username == username))
                        .values(last_read_seq=top)
                    )

    print(f"Users: {len(new_users)}  Groups: {len(new_groups)}  Memberships: {len(new_members)}  "
          f"Messages: {len(new_messages)}  Media files: {len(new_media)}")
    print("Done.")


if __name__ == "__main__":
    main()
