"""
ConvoEase — Message Store
All message-related database operations: save, load, flagged, analytics report.
"""

import uuid
from datetime import datetime
from config import CHATS_FILE, setup_logging
from .db_manager import DBManager

logger = setup_logging("message_store")


class MessageStore:
    """Handles all message CRUD operations."""

    @staticmethod
    def _now():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def load_messages(group_id=None):
        """Load messages. If group_id is provided, filter by group."""
        df = DBManager.read_csv(CHATS_FILE)
        if group_id:
            df = df[df["group_id"] == group_id]
        return df

    @staticmethod
    def save_message(group_id, username, message, status, reason="", summary="", media_url="", group_rules=""):
        """Save a new message to the database.

        Args:
            group_id:    Group the message belongs to.
            username:    Sender's username.
            message:     The stored message content (for images: "[IMAGE]", audio: "[AUDIO]").
            status:      "PASS" or "FLAGGED".
            reason:      Moderation block reason (for FLAGGED messages).
            summary:     AI summary of image/audio (stored separate from display message).
            media_url:   Server-relative URL to the saved media file, or "".
            group_rules: The group's active moderation rules at send time (for analysis).
        """
        new_msg = {
            "message_id": str(uuid.uuid4()),
            "group_id":   group_id,
            "username":   username,
            "message":    message,
            "status":     status,
            "reason":     reason,
            "summary":    summary,        # AI image/audio summary (empty for text messages)
            "media_url":  media_url,      # Persistent file URL ("/media/image/...") or ""
            "group_rules": group_rules,   # Active rules snapshot for analysis
            "timestamp":  MessageStore._now()
        }
        DBManager.append_row(CHATS_FILE, new_msg)
        logger.info(f"Message saved: [{status}] {username} in group {group_id}")
        return new_msg["message_id"]


    @staticmethod
    def get_visible_messages(group_id):
        """Get only PASS messages for a group, sorted by timestamp. Returns list of dicts."""
        msgs = MessageStore.load_messages(group_id)
        visible = msgs[msgs["status"] == "PASS"].sort_values("timestamp")
        return visible.to_dict("records")

    @staticmethod
    def get_flagged_messages(group_id):
        """Get only FLAGGED messages for a group. Returns list of dicts."""
        msgs = MessageStore.load_messages(group_id)
        flagged = msgs[msgs["status"] == "FLAGGED"]
        cols = [c for c in ["timestamp", "username", "message", "reason", "summary"] if c in flagged.columns]
        return flagged[cols].to_dict("records")

    @staticmethod
    def get_moderation_report(group_id):
        """
        Generate a moderation analytics report for a group.

        Returns a dict with:
          - total_messages:    Total messages attempted (PASS + FLAGGED)
          - pass_count:        Messages that passed moderation
          - flagged_count:     Messages blocked by moderation
          - pass_rate:         Percentage of messages that passed (0-100, rounded)
          - flagged_rate:      Percentage of messages flagged (0-100, rounded)
          - text_count:        Text messages (doesn't start with [IMAGE])
          - image_count:       Image messages (starts with [IMAGE])
          - top_flagged_users: List of {username, count} sorted by most flagged
          - flagged_reasons:   List of {reason, count} sorted by frequency
          - member_activity:   List of {username, sent, flagged} per member
          - passed_messages:   Recent passed messages with content/summary for reporting
          - flagged_messages:  All flagged messages with reason/summary for reporting
        """
        msgs = MessageStore.load_messages(group_id)
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
            "member_activity": [],
            "passed_messages": [],
            "flagged_messages": [],
        }
        if msgs.empty:
            return empty

        total       = len(msgs)
        pass_df     = msgs[msgs["status"] == "PASS"]
        flagged_df  = msgs[msgs["status"] == "FLAGGED"]

        pass_count    = len(pass_df)
        flagged_count = len(flagged_df)
        pass_rate     = round((pass_count / total) * 100) if total > 0 else 0
        flagged_rate  = 100 - pass_rate

        # Image vs audio vs text (detected by message prefix)
        image_mask  = msgs["message"].str.startswith("[IMAGE]", na=False)
        audio_mask  = msgs["message"].str.startswith("[AUDIO]", na=False)
        image_count = int(image_mask.sum())
        audio_count = int(audio_mask.sum())
        text_count  = total - image_count - audio_count

        # Top flagged users
        if not flagged_df.empty:
            fu = flagged_df.groupby("username").size().reset_index(name="count")
            fu = fu.sort_values("count", ascending=False)
            top_flagged_users = fu.head(10).to_dict("records")
        else:
            top_flagged_users = []

        # Flagged reasons frequency
        if not flagged_df.empty:
            reasons = (
                flagged_df["reason"]
                .dropna()
                .str.strip()
                .replace("", "Unknown")
            )
            reasons_counts = reasons.value_counts().reset_index()
            reasons_counts.columns = ["reason", "count"]
            flagged_reasons = reasons_counts.head(10).to_dict("records")
        else:
            flagged_reasons = []

        # Per-member activity
        all_users = msgs["username"].unique()
        member_activity = []
        for user in all_users:
            user_msgs = msgs[msgs["username"] == user]
            sent    = len(user_msgs[user_msgs["status"] == "PASS"])
            flagged = len(user_msgs[user_msgs["status"] == "FLAGGED"])
            member_activity.append({
                "username":       user,
                "sent":           sent,
                "flagged":        flagged,
                "total_attempts": sent + flagged,
            })
        member_activity.sort(key=lambda x: x["total_attempts"], reverse=True)

        # ── Passed messages (for report display) ────────────────────────────
        # Show last 20, most recent first. For images, use the AI summary.
        def _build_message_entry(row):
            is_image = str(row.get("message", "")).startswith("[IMAGE]")
            is_audio = str(row.get("message", "")).startswith("[AUDIO]")
            summary_col = row.get("summary", "")
            if is_image:
                display  = summary_col if summary_col else "[Image]"
                msg_type = "image"
            elif is_audio:
                display  = summary_col if summary_col else "[Audio transcription unavailable]"
                msg_type = "audio"
            else:
                display  = str(row.get("message", ""))
                msg_type = "text"
            return {
                "timestamp": str(row.get("timestamp", "")),
                "username":  str(row.get("username", "")),
                "display":   display,
                "type":      msg_type,
                "reason":    str(row.get("reason", "")),
            }

        passed_messages = []
        if not pass_df.empty:
            for _, row in pass_df.sort_values("timestamp", ascending=False).head(20).iterrows():
                entry = _build_message_entry(row)
                entry["reason"] = "Meets group rules"
                passed_messages.append(entry)

        flagged_messages = []
        if not flagged_df.empty:
            for _, row in flagged_df.sort_values("timestamp", ascending=False).iterrows():
                flagged_messages.append(_build_message_entry(row))

        return {
            "total_messages":    total,
            "pass_count":        pass_count,
            "flagged_count":     flagged_count,
            "pass_rate":         pass_rate,
            "flagged_rate":      flagged_rate,
            "text_count":        text_count,
            "image_count":       image_count,
            "audio_count":       audio_count,
            "top_flagged_users": top_flagged_users,
            "flagged_reasons":   flagged_reasons,
            "member_activity":   member_activity,
            "passed_messages":   passed_messages,
            "flagged_messages":  flagged_messages,
        }
