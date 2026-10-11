"""
ConvoEase - Message Store
All message-related database operations: save, load, flagged, summaries, analytics.
"""

import uuid
from collections import Counter, defaultdict

from sqlalchemy import and_, insert, or_, select, update

from config import setup_logging
from .db_manager import DBManager, messages, utc_now

logger = setup_logging("message_store")


class MessageStore:
    """Handles all message CRUD operations."""

    _SYSTEM_FAILURE_MARKERS = (
        "moderation error:",
        "invalid api key",
        "temporarily unavailable",
        "processing error:",
    )

    @staticmethod
    def load_messages(group_id=None):
        """All messages (any status), oldest first."""
        query = select(messages).order_by(messages.c.seq)
        if group_id:
            query = query.where(messages.c.group_id == group_id)
        return DBManager.fetch_all(query)

    @staticmethod
    def save_message(
        group_id,
        username,
        message,
        status,
        reason="",
        summary="",
        media_url="",
        group_rules="",
        initial_status="",
        initial_reason="",
        detected_language="",
        language_confidence="",
        translated_message="",
        appeal_status="",
        appeal_text="",
        appeal_ai_status="",
        appeal_ai_reason="",
        appeal_submitted_at="",
        appeal_reviewed_by="",
        appeal_reviewed_at="",
        appeal_admin_note="",
    ):
        message_id = str(uuid.uuid4())
        DBManager.execute(insert(messages).values(
            message_id=message_id,
            group_id=group_id,
            username=username,
            message=message or "",
            status=status,
            reason=reason or "",
            summary=summary or "",
            media_url=media_url or "",
            group_rules=group_rules or "",
            timestamp=utc_now(),
            initial_status=initial_status or status,
            initial_reason=initial_reason if initial_reason != "" else (reason or ""),
            detected_language=detected_language or "",
            language_confidence=str(language_confidence or ""),
            translated_message=translated_message or "",
            appeal_status=appeal_status or "",
            appeal_text=appeal_text or "",
            appeal_ai_status=appeal_ai_status or "",
            appeal_ai_reason=appeal_ai_reason or "",
            appeal_submitted_at=appeal_submitted_at or "",
            appeal_reviewed_by=appeal_reviewed_by or "",
            appeal_reviewed_at=appeal_reviewed_at or "",
            appeal_admin_note=appeal_admin_note or "",
        ))
        logger.info("Message saved: [%s] %s in group %s", status, username, group_id)
        return message_id

    @staticmethod
    def get_visible_messages(group_id, after_seq=0, limit=None, own_flagged_for=None):
        """Messages members can see (PASS and DELETED), oldest first.

        own_flagged_for: also include that user's own FLAGGED messages, so they
        can see what was held and appeal it.
        limit: return only the newest N matching messages.
        """
        visible = messages.c.status.in_(["PASS", "DELETED"])
        if own_flagged_for:
            visible = or_(visible, and_(messages.c.status == "FLAGGED", messages.c.username == own_flagged_for))
        query = select(messages).where(and_(messages.c.group_id == group_id, visible))
        if after_seq:
            query = query.where(messages.c.seq > after_seq)
        if limit:
            rows = DBManager.fetch_all(query.order_by(messages.c.seq.desc()).limit(limit))
            return rows[::-1]
        return DBManager.fetch_all(query.order_by(messages.c.seq))

    @staticmethod
    def get_recent_messages(group_id, limit=25, include_flagged=False):
        query = select(messages).where(messages.c.group_id == group_id)
        if not include_flagged:
            query = query.where(messages.c.status == "PASS")
        query = query.order_by(messages.c.seq.desc())
        if limit > 0:
            query = query.limit(limit)
        return DBManager.fetch_all(query)[::-1]

    @staticmethod
    def get_flagged_messages(group_id):
        query = (
            select(messages)
            .where(and_(messages.c.group_id == group_id, messages.c.status == "FLAGGED"))
            .order_by(messages.c.seq.desc())
        )
        records = []
        for row in DBManager.fetch_all(query):
            if MessageStore._is_system_failure_reason(row.get("reason", "")):
                continue
            row["category"] = MessageStore._categorize_reason(
                row.get("reason", ""),
                row.get("message", ""),
                row.get("summary", "")
            )
            row["appeal_pending"] = str(row.get("appeal_status", "")).upper() == "PENDING_ADMIN"
            records.append(row)
        return records

    @staticmethod
    def build_summary_payload(group_id, limit=25):
        recent = MessageStore.get_recent_messages(group_id, limit=limit, include_flagged=False)
        timeline = []
        for row in recent:
            display = MessageStore._display_message(row)
            if display:
                timeline.append({
                    "timestamp": row.get("timestamp", ""),
                    "username": row.get("username", ""),
                    "content": display,
                    "type": MessageStore._message_type(row.get("message", "")),
                })
        return timeline

    @staticmethod
    def _message_type(message):
        value = str(message or "")
        if value.startswith("[IMAGE]"):
            return "image"
        if value.startswith("[AUDIO]"):
            return "audio"
        return "text"

    @staticmethod
    def _display_message(row):
        message = str(row.get("message", ""))
        summary = str(row.get("summary", ""))
        if message.startswith("[IMAGE]"):
            return summary or "Shared an image."
        if message.startswith("[AUDIO]"):
            return summary or "Shared an audio message."
        return message

    @staticmethod
    def _categorize_reason(reason, message="", summary=""):
        text = " ".join([
            str(reason or "").lower(),
            str(message or "").lower(),
            str(summary or "").lower(),
        ])

        keyword_groups = {
            "spam": ["spam", "repeat", "repeated", "advert", "promotion", "flood"],
            "hate": ["hate", "abuse", "harass", "insult", "slur", "toxic", "bully"],
            "sensitive": ["sexual", "violence", "self-harm", "gore", "explicit", "sensitive", "unsafe"],
            "off-topic": ["off-topic", "not related", "not relevant", "irrelevant", "outside rules", "outside scope"],
            "privacy": ["private", "personal data", "dox", "phone number", "address", "leak"],
        }

        for category, keywords in keyword_groups.items():
            if any(keyword in text for keyword in keywords):
                return category
        return "policy"

    @staticmethod
    def _is_system_failure_reason(reason):
        text = str(reason or "").strip().lower()
        if not text:
            return False
        return any(marker in text for marker in MessageStore._SYSTEM_FAILURE_MARKERS)

    @staticmethod
    def _member_trust_profile(pass_count, flagged_count):
        total = pass_count + flagged_count
        if total == 0:
            return {
                "trust_score": 100,
                "compliance_rate": 100,
                "badge": "trusted",
                "risk_level": "low",
            }

        compliance_rate = round((pass_count / total) * 100)
        penalty = min(45, flagged_count * 8)
        trust_score = max(5, min(100, compliance_rate - penalty + 25))

        if trust_score >= 85:
            badge = "trusted"
            risk = "low"
        elif trust_score >= 65:
            badge = "watch"
            risk = "moderate"
        else:
            badge = "warning"
            risk = "high"

        return {
            "trust_score": trust_score,
            "compliance_rate": compliance_rate,
            "badge": badge,
            "risk_level": risk,
        }

    @staticmethod
    def _build_message_entry(row):
        display = MessageStore._display_message(row)
        category = MessageStore._categorize_reason(
            row.get("reason", ""),
            row.get("message", ""),
            row.get("summary", "")
        )
        return {
            "timestamp": str(row.get("timestamp", "")),
            "message_id": str(row.get("message_id", "")),
            "username": str(row.get("username", "")),
            "display": display,
            "type": MessageStore._message_type(row.get("message", "")),
            "media_url": str(row.get("media_url", "")),
            "reason": str(row.get("reason", "")),
            "category": category,
            "detected_language": str(row.get("detected_language", "")),
            "appeal_status": str(row.get("appeal_status", "")),
            "appeal_text": str(row.get("appeal_text", "")),
            "appeal_ai_status": str(row.get("appeal_ai_status", "")),
            "appeal_ai_reason": str(row.get("appeal_ai_reason", "")),
        }

    @staticmethod
    def get_message(group_id, message_id):
        return DBManager.fetch_one(select(messages).where(and_(
            messages.c.group_id == group_id,
            messages.c.message_id == message_id,
        )))

    @staticmethod
    def find_by_media_url(media_url):
        return DBManager.fetch_one(select(messages).where(messages.c.media_url == media_url).limit(1))

    @staticmethod
    def _update_message(group_id, message_id, **values):
        DBManager.execute(
            update(messages)
            .where(and_(messages.c.group_id == group_id, messages.c.message_id == message_id))
            .values(**values)
        )

    @staticmethod
    def soft_delete_message(group_id, message_id, requesting_username):
        """Soft-delete a message. Replaces content with [deleted]. Returns (success, message)."""
        row = MessageStore.get_message(group_id, message_id)
        if not row:
            return False, "Message not found."
        if str(row.get("username", "")) != requesting_username:
            return False, "You can only delete your own messages."
        if str(row.get("message", "")) == "[deleted]":
            return False, "Message already deleted."

        MessageStore._update_message(
            group_id, message_id,
            message="[deleted]", summary="", media_url="", status="DELETED", reason="Deleted by sender.",
        )
        logger.info("Message %s soft-deleted by %s in group %s", message_id, requesting_username, group_id)
        return True, "Message deleted."

    @staticmethod
    def submit_appeal(group_id, message_id, appeal_text, appeal_result):
        if not MessageStore.get_message(group_id, message_id):
            return False
        MessageStore._update_message(
            group_id, message_id,
            appeal_text=appeal_text,
            appeal_status="PENDING_ADMIN",
            appeal_ai_status=appeal_result.get("status", ""),
            appeal_ai_reason=appeal_result.get("reason", ""),
            appeal_submitted_at=utc_now(),
            appeal_reviewed_by="",
            appeal_reviewed_at="",
            appeal_admin_note="",
        )
        return True

    @staticmethod
    def resolve_appeal(group_id, message_id, approved, admin_username, admin_note=""):
        row = MessageStore.get_message(group_id, message_id)
        if not row:
            return False

        values = {
            "appeal_status": "APPROVED" if approved else "REJECTED",
            "appeal_reviewed_by": admin_username,
            "appeal_reviewed_at": utc_now(),
            "appeal_admin_note": admin_note,
        }
        if approved:
            values["status"] = "PASS"
            values["reason"] = admin_note or "Approved on appeal by admin."
        else:
            ai_reason = str(row.get("appeal_ai_reason") or "").strip()
            values["status"] = "FLAGGED"
            values["reason"] = admin_note or ai_reason or str(row.get("initial_reason") or "")

        MessageStore._update_message(group_id, message_id, **values)
        return True

    @staticmethod
    def get_moderation_report(group_id):
        rows = [
            row for row in MessageStore.load_messages(group_id)
            if row["status"] in ("PASS", "FLAGGED")
            and not MessageStore._is_system_failure_reason(row.get("reason", ""))
        ]
        empty = {
            "total_messages": 0,
            "pass_count": 0,
            "flagged_count": 0,
            "pass_rate": 0,
            "flagged_rate": 0,
            "text_count": 0,
            "image_count": 0,
            "audio_count": 0,
            "pending_appeals": 0,
            "top_flagged_users": [],
            "flagged_reasons": [],
            "flag_categories": [],
            "member_activity": [],
            "member_heatmap": [],
            "trend_points": [],
            "passed_messages": [],
            "flagged_messages": [],
        }
        if not rows:
            return empty

        pass_rows = [row for row in rows if row["status"] == "PASS"]
        flagged_rows = [row for row in rows if row["status"] == "FLAGGED"]
        total = len(rows)
        pass_count = len(pass_rows)
        flagged_count = len(flagged_rows)
        pass_rate = round((pass_count / total) * 100) if total else 0
        flagged_rate = 100 - pass_rate if total else 0

        types = Counter(MessageStore._message_type(row["message"]) for row in rows)

        flagged_by_user = Counter(row["username"] for row in flagged_rows)
        top_flagged_users = [
            {"username": username, "count": count}
            for username, count in sorted(flagged_by_user.items(), key=lambda item: (-item[1], item[0]))[:10]
        ]

        flagged_reason_counts = Counter()
        flag_category_counts = Counter()
        flagged_messages = []
        for row in flagged_rows:
            reason = str(row.get("reason", "")).strip() or "Unknown"
            category = MessageStore._categorize_reason(reason, row.get("message", ""), row.get("summary", ""))
            flagged_reason_counts[reason] += 1
            flag_category_counts[category] += 1
            flagged_messages.append(MessageStore._build_message_entry(row))

        flagged_reasons = [
            {"reason": reason, "count": count}
            for reason, count in flagged_reason_counts.most_common(10)
        ]
        flag_categories = [
            {"category": category, "count": count}
            for category, count in flag_category_counts.most_common()
        ]

        per_user = defaultdict(lambda: {"PASS": 0, "FLAGGED": 0})
        for row in rows:
            per_user[row["username"]][row["status"]] += 1

        member_activity = []
        member_heatmap = []
        for username, counts in per_user.items():
            profile = MessageStore._member_trust_profile(counts["PASS"], counts["FLAGGED"])
            member_activity.append({
                "username": username,
                "sent": counts["PASS"],
                "flagged": counts["FLAGGED"],
                "total_attempts": counts["PASS"] + counts["FLAGGED"],
                **profile,
            })
            member_heatmap.append({
                "username": username,
                "trust_score": profile["trust_score"],
                "flagged": counts["FLAGGED"],
                "compliance_rate": profile["compliance_rate"],
                "risk_level": profile["risk_level"],
            })

        member_activity.sort(key=lambda row: (-row["trust_score"], row["username"]))
        member_heatmap.sort(key=lambda row: (row["trust_score"], -row["flagged"], row["username"]))

        trend_buckets = defaultdict(lambda: {"date": "", "passed": 0, "flagged": 0})
        for row in rows:
            date_key = str(row.get("timestamp", ""))[:10]
            if not date_key:
                continue
            trend_buckets[date_key]["date"] = date_key
            if row["status"] == "PASS":
                trend_buckets[date_key]["passed"] += 1
            else:
                trend_buckets[date_key]["flagged"] += 1
        trend_points = [trend_buckets[key] for key in sorted(trend_buckets.keys())][-10:]

        passed_messages = []
        for row in pass_rows[-20:][::-1]:
            entry = MessageStore._build_message_entry(row)
            entry["reason"] = "Meets group rules"
            passed_messages.append(entry)

        return {
            "total_messages": total,
            "pass_count": pass_count,
            "flagged_count": flagged_count,
            "pass_rate": pass_rate,
            "flagged_rate": flagged_rate,
            "text_count": types["text"],
            "image_count": types["image"],
            "audio_count": types["audio"],
            "pending_appeals": sum(
                1 for row in flagged_rows if str(row.get("appeal_status", "")).upper() == "PENDING_ADMIN"
            ),
            "top_flagged_users": top_flagged_users,
            "flagged_reasons": flagged_reasons,
            "flag_categories": flag_categories,
            "member_activity": member_activity,
            "member_heatmap": member_heatmap,
            "trend_points": trend_points,
            "passed_messages": passed_messages,
            "flagged_messages": flagged_messages[::-1],
        }
