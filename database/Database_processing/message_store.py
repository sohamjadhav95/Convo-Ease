"""
ConvoEase - Message Store
All message-related database operations: save, load, flagged, summaries, analytics.
"""

import uuid
from collections import Counter, defaultdict
from datetime import datetime

from config import CHATS_FILE, setup_logging
from .db_manager import DBManager

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
    def _now():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def load_messages(group_id=None):
        df = DBManager.read_csv(CHATS_FILE)
        if group_id:
            df = df[df["group_id"] == group_id]
        return df

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
        initial_status = initial_status or status
        initial_reason = initial_reason if initial_reason != "" else reason
        new_msg = {
            "message_id": str(uuid.uuid4()),
            "group_id": group_id,
            "username": username,
            "message": message,
            "status": status,
            "reason": reason,
            "summary": summary,
            "media_url": media_url,
            "group_rules": group_rules,
            "timestamp": MessageStore._now(),
            "initial_status": initial_status,
            "initial_reason": initial_reason,
            "detected_language": detected_language,
            "language_confidence": language_confidence,
            "translated_message": translated_message,
            "appeal_status": appeal_status,
            "appeal_text": appeal_text,
            "appeal_ai_status": appeal_ai_status,
            "appeal_ai_reason": appeal_ai_reason,
            "appeal_submitted_at": appeal_submitted_at,
            "appeal_reviewed_by": appeal_reviewed_by,
            "appeal_reviewed_at": appeal_reviewed_at,
            "appeal_admin_note": appeal_admin_note,
        }
        DBManager.append_row(CHATS_FILE, new_msg)
        logger.info("Message saved: [%s] %s in group %s", status, username, group_id)
        return new_msg["message_id"]

    @staticmethod
    def get_visible_messages(group_id):
        msgs = MessageStore.load_messages(group_id)
        visible = msgs[msgs["status"].isin(["PASS", "DELETED"])].sort_values("timestamp")
        return visible.to_dict("records")

    @staticmethod
    def get_recent_messages(group_id, limit=25, include_flagged=False):
        msgs = MessageStore.load_messages(group_id).sort_values("timestamp")
        if not include_flagged:
            msgs = msgs[msgs["status"] == "PASS"]
        if limit > 0:
            msgs = msgs.tail(limit)
        return msgs.to_dict("records")

    @staticmethod
    def get_flagged_messages(group_id):
        msgs = MessageStore.load_messages(group_id)
        flagged = msgs[msgs["status"] == "FLAGGED"].sort_values("timestamp", ascending=False)
        records = []
        for row in flagged.to_dict("records"):
            if MessageStore._is_system_failure_reason(row.get("reason", "")):
                continue
            category = MessageStore._categorize_reason(
                row.get("reason", ""),
                row.get("message", ""),
                row.get("summary", "")
            )
            row["category"] = category
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
        msgs = MessageStore.load_messages(group_id)
        target = msgs[msgs["message_id"] == message_id]
        if target.empty:
            return None
        return target.iloc[0].to_dict()

    @staticmethod
    def soft_delete_message(group_id, message_id, requesting_username):
        """Soft-delete a message. Replaces content with [deleted]. Returns (success, message)."""
        msgs = DBManager.read_csv(CHATS_FILE)
        mask = (msgs["group_id"] == group_id) & (msgs["message_id"] == message_id)
        if mask.sum() == 0:
            return False, "Message not found."

        row = msgs.loc[mask].iloc[0]
        if str(row.get("username", "")) != requesting_username:
            return False, "You can only delete your own messages."

        if str(row.get("message", "")) == "[deleted]":
            return False, "Message already deleted."

        msgs.loc[mask, "message"] = "[deleted]"
        msgs.loc[mask, "summary"] = ""
        msgs.loc[mask, "status"] = "DELETED"
        msgs.loc[mask, "reason"] = "Deleted by sender."
        DBManager.write_csv(CHATS_FILE, msgs)
        logger.info(f"Message {message_id} soft-deleted by {requesting_username} in group {group_id}")
        return True, "Message deleted."

    @staticmethod
    def submit_appeal(group_id, message_id, appeal_text, appeal_result):
        msgs = MessageStore.load_messages(group_id)
        mask = (msgs["group_id"] == group_id) & (msgs["message_id"] == message_id)
        if mask.sum() == 0:
            return False

        msgs.loc[mask, "appeal_text"] = appeal_text
        msgs.loc[mask, "appeal_status"] = "PENDING_ADMIN"
        msgs.loc[mask, "appeal_ai_status"] = appeal_result.get("status", "")
        msgs.loc[mask, "appeal_ai_reason"] = appeal_result.get("reason", "")
        msgs.loc[mask, "appeal_submitted_at"] = MessageStore._now()
        msgs.loc[mask, "appeal_reviewed_by"] = ""
        msgs.loc[mask, "appeal_reviewed_at"] = ""
        msgs.loc[mask, "appeal_admin_note"] = ""
        DBManager.write_csv(CHATS_FILE, msgs)
        return True

    @staticmethod
    def resolve_appeal(group_id, message_id, approved, admin_username, admin_note=""):
        msgs = MessageStore.load_messages(group_id)
        mask = (msgs["group_id"] == group_id) & (msgs["message_id"] == message_id)
        if mask.sum() == 0:
            return False

        review_status = "APPROVED" if approved else "REJECTED"
        msgs.loc[mask, "appeal_status"] = review_status
        msgs.loc[mask, "appeal_reviewed_by"] = admin_username
        msgs.loc[mask, "appeal_reviewed_at"] = MessageStore._now()
        msgs.loc[mask, "appeal_admin_note"] = admin_note

        if approved:
            msgs.loc[mask, "status"] = "PASS"
            msgs.loc[mask, "reason"] = admin_note or "Approved on appeal by admin."
        else:
            ai_reason = str(msgs.loc[mask, "appeal_ai_reason"].iloc[0] or "").strip()
            msgs.loc[mask, "status"] = "FLAGGED"
            msgs.loc[mask, "reason"] = admin_note or ai_reason or str(msgs.loc[mask, "initial_reason"].iloc[0] or "")

        DBManager.write_csv(CHATS_FILE, msgs)
        return True

    @staticmethod
    def get_moderation_report(group_id):
        msgs = MessageStore.load_messages(group_id)
        if not msgs.empty:
            msgs = msgs[~msgs["reason"].apply(MessageStore._is_system_failure_reason)]
        empty = {
            "total_messages": 0,
            "pass_count": 0,
            "flagged_count": 0,
            "pass_rate": 0,
            "flagged_rate": 0,
            "text_count": 0,
            "image_count": 0,
            "audio_count": 0,
            "top_flagged_users": [],
            "flagged_reasons": [],
            "flag_categories": [],
            "member_activity": [],
            "member_heatmap": [],
            "trend_points": [],
            "passed_messages": [],
            "flagged_messages": [],
        }
        if msgs.empty:
            return empty

        msgs = msgs.sort_values("timestamp")
        total = len(msgs)
        pass_df = msgs[msgs["status"] == "PASS"]
        flagged_df = msgs[msgs["status"] == "FLAGGED"]

        pass_count = len(pass_df)
        flagged_count = len(flagged_df)
        pass_rate = round((pass_count / total) * 100) if total else 0
        flagged_rate = 100 - pass_rate if total else 0

        image_mask = msgs["message"].astype(str).str.startswith("[IMAGE]", na=False)
        audio_mask = msgs["message"].astype(str).str.startswith("[AUDIO]", na=False)
        image_count = int(image_mask.sum())
        audio_count = int(audio_mask.sum())
        text_count = total - image_count - audio_count

        top_flagged_users = []
        if not flagged_df.empty:
            flagged_user_counts = flagged_df.groupby("username").size().reset_index(name="count")
            flagged_user_counts = flagged_user_counts.sort_values("count", ascending=False)
            top_flagged_users = flagged_user_counts.head(10).to_dict("records")

        flagged_reason_counts = Counter()
        flag_category_counts = Counter()
        flagged_messages = []
        for row in flagged_df.to_dict("records"):
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

        member_activity = []
        member_heatmap = []
        for username in msgs["username"].unique():
            user_msgs = msgs[msgs["username"] == username]
            user_pass = len(user_msgs[user_msgs["status"] == "PASS"])
            user_flagged = len(user_msgs[user_msgs["status"] == "FLAGGED"])
            profile = MessageStore._member_trust_profile(user_pass, user_flagged)
            item = {
                "username": username,
                "sent": user_pass,
                "flagged": user_flagged,
                "total_attempts": user_pass + user_flagged,
                **profile,
            }
            member_activity.append(item)
            member_heatmap.append({
                "username": username,
                "trust_score": profile["trust_score"],
                "flagged": user_flagged,
                "compliance_rate": profile["compliance_rate"],
                "risk_level": profile["risk_level"],
            })

        member_activity.sort(key=lambda row: (-row["trust_score"], row["username"]))
        member_heatmap.sort(key=lambda row: (row["trust_score"], -row["flagged"], row["username"]))

        trend_buckets = defaultdict(lambda: {"date": "", "passed": 0, "flagged": 0})
        for row in msgs.to_dict("records"):
            date_key = str(row.get("timestamp", ""))[:10]
            if not date_key:
                continue
            trend_buckets[date_key]["date"] = date_key
            if row.get("status") == "PASS":
                trend_buckets[date_key]["passed"] += 1
            else:
                trend_buckets[date_key]["flagged"] += 1
        trend_points = [trend_buckets[key] for key in sorted(trend_buckets.keys())][-10:]

        passed_messages = []
        for row in pass_df.tail(20).to_dict("records")[::-1]:
            entry = MessageStore._build_message_entry(row)
            entry["reason"] = "Meets group rules"
            passed_messages.append(entry)

        return {
            "total_messages": total,
            "pass_count": pass_count,
            "flagged_count": flagged_count,
            "pass_rate": pass_rate,
            "flagged_rate": flagged_rate,
            "text_count": text_count,
            "image_count": image_count,
            "audio_count": audio_count,
            "top_flagged_users": top_flagged_users,
            "flagged_reasons": flagged_reasons,
            "flag_categories": flag_categories,
            "member_activity": member_activity,
            "member_heatmap": member_heatmap,
            "trend_points": trend_points,
            "passed_messages": passed_messages,
            "flagged_messages": flagged_messages,
        }
