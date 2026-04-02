"""
ConvoEase — Backend Tests
Unit and integration tests for database stores and Flask API endpoints.
"""

import os
import sys
import shutil
import tempfile
import unittest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestUserStore(unittest.TestCase):
    """Test user registration and login."""

    def setUp(self):
        """Create a temporary database directory."""
        import config
        self.original_db_dir = config.DATABASE_DIR
        self.temp_dir = tempfile.mkdtemp()
        config.DATABASE_DIR = self.temp_dir
        config.USERS_FILE = os.path.join(self.temp_dir, "users.csv")
        config.GROUPS_FILE = os.path.join(self.temp_dir, "groups.csv")
        config.MEMBERS_FILE = os.path.join(self.temp_dir, "group_members.csv")
        config.CHATS_FILE = os.path.join(self.temp_dir, "group_chats.csv")

        # Re-import to pick up new paths
        from database.Database_processing import db_manager
        db_manager.SCHEMAS["users"]["path"] = config.USERS_FILE
        db_manager.SCHEMAS["groups"]["path"] = config.GROUPS_FILE
        db_manager.SCHEMAS["members"]["path"] = config.MEMBERS_FILE
        db_manager.SCHEMAS["chats"]["path"] = config.CHATS_FILE

        from database.Database_processing import DBManager
        DBManager.initialize()

    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_user(self):
        from database.Database_processing import UserStore
        success, msg = UserStore.register("testuser", "testpass", "Test User")
        self.assertTrue(success)
        self.assertEqual(msg, "Registration successful.")

    def test_duplicate_user(self):
        from database.Database_processing import UserStore
        UserStore.register("duplicate", "pass", "Dup User")
        success, msg = UserStore.register("duplicate", "pass2", "Dup User 2")
        self.assertFalse(success)
        self.assertIn("already exists", msg)

    def test_login_success(self):
        from database.Database_processing import UserStore
        UserStore.register("logintest", "mypass", "Login Test")
        success, user_data = UserStore.validate_login("logintest", "mypass")
        self.assertTrue(success)
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data["username"], "logintest")

    def test_login_failure(self):
        from database.Database_processing import UserStore
        UserStore.register("logintest2", "mypass", "Login Test 2")
        success, user_data = UserStore.validate_login("logintest2", "wrongpass")
        self.assertFalse(success)
        self.assertIsNone(user_data)


class TestGroupStore(unittest.TestCase):
    """Test group creation and membership."""

    def setUp(self):
        import config
        self.temp_dir = tempfile.mkdtemp()
        config.DATABASE_DIR = self.temp_dir
        config.USERS_FILE = os.path.join(self.temp_dir, "users.csv")
        config.GROUPS_FILE = os.path.join(self.temp_dir, "groups.csv")
        config.MEMBERS_FILE = os.path.join(self.temp_dir, "group_members.csv")
        config.CHATS_FILE = os.path.join(self.temp_dir, "group_chats.csv")

        from database.Database_processing import db_manager
        db_manager.SCHEMAS["users"]["path"] = config.USERS_FILE
        db_manager.SCHEMAS["groups"]["path"] = config.GROUPS_FILE
        db_manager.SCHEMAS["members"]["path"] = config.MEMBERS_FILE
        db_manager.SCHEMAS["chats"]["path"] = config.CHATS_FILE

        from database.Database_processing import DBManager
        DBManager.initialize()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_group(self):
        from database.Database_processing import GroupStore
        success, gid = GroupStore.create_group("Test Group", "pass", "admin1")
        self.assertTrue(success)
        self.assertEqual(len(gid), 6)

    def test_join_group(self):
        from database.Database_processing import GroupStore
        _, gid = GroupStore.create_group("Join Test", "secret", "admin1")
        success, msg = GroupStore.join_group(gid, "secret", "user2")
        self.assertTrue(success)

    def test_join_wrong_password(self):
        from database.Database_processing import GroupStore
        _, gid = GroupStore.create_group("PW Test", "correct", "admin1")
        success, msg = GroupStore.join_group(gid, "wrong", "user2")
        self.assertFalse(success)

    def test_get_group_details(self):
        from database.Database_processing import GroupStore
        _, gid = GroupStore.create_group("Detail Test", "pass", "admin1")
        details = GroupStore.get_group_details(gid)
        self.assertIsNotNone(details)
        self.assertEqual(details["group_name"], "Detail Test")

    def test_group_sensitivity_defaults_and_updates(self):
        from database.Database_processing import GroupStore
        _, gid = GroupStore.create_group("Sensitive Group", "pass", "admin1", moderation_sensitivity="strict")
        details = GroupStore.get_group_details(gid)
        self.assertEqual(details["moderation_sensitivity"], "Strict")

        GroupStore.update_group_rules(gid, "Stay on topic.", "relaxed")
        updated = GroupStore.get_group_details(gid)
        self.assertEqual(updated["moderation_sensitivity"], "Relaxed")


class TestMessageStore(unittest.TestCase):
    """Test message operations."""

    def setUp(self):
        import config
        self.temp_dir = tempfile.mkdtemp()
        config.DATABASE_DIR = self.temp_dir
        config.USERS_FILE = os.path.join(self.temp_dir, "users.csv")
        config.GROUPS_FILE = os.path.join(self.temp_dir, "groups.csv")
        config.MEMBERS_FILE = os.path.join(self.temp_dir, "group_members.csv")
        config.CHATS_FILE = os.path.join(self.temp_dir, "group_chats.csv")

        from database.Database_processing import db_manager
        db_manager.SCHEMAS["users"]["path"] = config.USERS_FILE
        db_manager.SCHEMAS["groups"]["path"] = config.GROUPS_FILE
        db_manager.SCHEMAS["members"]["path"] = config.MEMBERS_FILE
        db_manager.SCHEMAS["chats"]["path"] = config.CHATS_FILE

        from database.Database_processing import DBManager
        DBManager.initialize()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_load(self):
        from database.Database_processing import MessageStore
        MessageStore.save_message("GRP1", "user1", "Hello!", "PASS")
        msgs = MessageStore.get_visible_messages("GRP1")
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["message"], "Hello!")

    def test_flagged_messages(self):
        from database.Database_processing import MessageStore
        MessageStore.save_message("GRP1", "user1", "Bad msg", "FLAGGED", "Offensive")
        flagged = MessageStore.get_flagged_messages("GRP1")
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0]["reason"], "Offensive")

    def test_appeal_submission_and_resolution(self):
        from database.Database_processing import MessageStore
        message_id = MessageStore.save_message(
            "GRP1",
            "user1",
            "Bad msg",
            "FLAGGED",
            "Offensive",
            initial_status="FLAGGED",
            initial_reason="Offensive",
            detected_language="hi",
            translated_message="Bad msg",
        )

        submitted = MessageStore.submit_appeal(
            "GRP1",
            message_id,
            "It was a movie quote.",
            {"status": "PASS", "reason": "Quoted dialogue in context."},
        )
        self.assertTrue(submitted)

        flagged = MessageStore.get_flagged_messages("GRP1")
        self.assertEqual(flagged[0]["appeal_status"], "PENDING_ADMIN")
        self.assertEqual(flagged[0]["appeal_ai_status"], "PASS")

        resolved = MessageStore.resolve_appeal("GRP1", message_id, True, "admin1", "Approved by admin.")
        self.assertTrue(resolved)

        visible = MessageStore.get_visible_messages("GRP1")
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
