import requests
import json
import pandas as pd
import os
from datetime import datetime
import hashlib
import uuid
import random
from openai import OpenAI

# Configuration
OPENROUTER_API_KEY = "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"
API_URL = "https://openrouter.ai/api/v1" # Base URL for SDK
MODEL_NAME = "openai/gpt-oss-120b:free"

# Initialize Client
client = OpenAI(
    base_url=API_URL,
    api_key=OPENROUTER_API_KEY
)

DATA_DIR = "e:/Projects/Master Projects (Core)/Convo-Ease/Phase 3 User Application"
USERS_FILE = os.path.join(DATA_DIR, "users.csv")
GROUPS_FILE = os.path.join(DATA_DIR, "groups.csv")
MEMBERS_FILE = os.path.join(DATA_DIR, "group_members.csv")
CHATS_FILE = os.path.join(DATA_DIR, "group_chats.csv")

class Utils:
    @staticmethod
    def get_time():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def generate_random_color():
        return "#{:06x}".format(random.randint(0, 0xFFFFFF))

class DataManager:
    @staticmethod
    def initialize_files():
        if not os.path.exists(USERS_FILE):
             pd.DataFrame(columns=['username', 'password', 'full_name', 'bio', 'profile_pic_color', 'created_at']).to_csv(USERS_FILE, index=False)
        if not os.path.exists(GROUPS_FILE):
             pd.DataFrame(columns=['group_id', 'group_name', 'admin_username', 'password', 'rules', 'created_at']).to_csv(GROUPS_FILE, index=False)
        if not os.path.exists(MEMBERS_FILE):
             pd.DataFrame(columns=['group_id', 'username', 'joined_at']).to_csv(MEMBERS_FILE, index=False)
        if not os.path.exists(CHATS_FILE):
             pd.DataFrame(columns=['message_id', 'group_id', 'username', 'message', 'status', 'reason', 'timestamp']).to_csv(CHATS_FILE, index=False)

    # --- User Management ---
    @staticmethod
    def load_users():
        if os.path.exists(USERS_FILE):
            return pd.read_csv(USERS_FILE).astype(str) # Force string to avoid type issues
        return pd.DataFrame(columns=['username', 'password', 'full_name', 'bio', 'profile_pic_color', 'created_at'])

    @staticmethod
    def register_user(username, password, full_name, bio=""):
        users = DataManager.load_users()
        if username in users['username'].values:
            return False, "Username already exists."
        
        hashed_pw = Utils.hash_password(password)
        new_user = pd.DataFrame({
            'username': [username], 'password': [hashed_pw], 
            'full_name': [full_name], 'bio': [bio], 
            'profile_pic_color': [Utils.generate_random_color()],
            'created_at': [Utils.get_time()]
        })
        users = pd.concat([users, new_user], ignore_index=True)
        users.to_csv(USERS_FILE, index=False)
        return True, "Registration successful."

    @staticmethod
    def validate_login(username, password):
        users = DataManager.load_users()
        hashed_pw = Utils.hash_password(password)
        user = users[(users['username'] == username) & (users['password'] == hashed_pw)]
        if not user.empty:
            return True, user.iloc[0].to_dict()
        return False, None

    # --- Group Management ---
    @staticmethod
    def load_groups():
        if os.path.exists(GROUPS_FILE):
            return pd.read_csv(GROUPS_FILE).astype(str)
        return pd.DataFrame(columns=['group_id', 'group_name', 'admin_username', 'password', 'rules', 'created_at'])

    @staticmethod
    def load_members():
        if os.path.exists(MEMBERS_FILE):
            return pd.read_csv(MEMBERS_FILE).astype(str)
        return pd.DataFrame(columns=['group_id', 'username', 'joined_at'])

    @staticmethod
    def create_group(group_name, password, admin_username, initial_rules="Be respectful."):
        groups = DataManager.load_groups()
        group_id = str(uuid.uuid4())[:6].upper() # 6 char ID
        
        new_group = pd.DataFrame({
            'group_id': [group_id], 'group_name': [group_name], 
            'admin_username': [admin_username], 'password': [password], # Plain text for simplicity as per prototype
            'rules': [initial_rules], 'created_at': [Utils.get_time()]
        })
        groups = pd.concat([groups, new_group], ignore_index=True)
        groups.to_csv(GROUPS_FILE, index=False)
        
        # Add admin as member
        DataManager.add_member(group_id, admin_username)
        return True, group_id

    @staticmethod
    def join_group(group_id, password, username):
        groups = DataManager.load_groups()
        target_group = groups[groups['group_id'] == group_id]
        
        if target_group.empty:
            return False, "Group not found."
        
        if target_group.iloc[0]['password'] != password and password != "": # Empty password allows open groups if we wanted, but sticking to logic
             return False, "Incorrect Group Password."
             
        members = DataManager.load_members()
        if not members[(members['group_id'] == group_id) & (members['username'] == username)].empty:
            return True, "Already a member."
            
        DataManager.add_member(group_id, username)
        return True, "Joined successfully."

    @staticmethod
    def add_member(group_id, username):
        members = DataManager.load_members()
        new_member = pd.DataFrame({
            'group_id': [group_id], 'username': [username], 'joined_at': [Utils.get_time()]
        })
        members = pd.concat([members, new_member], ignore_index=True)
        members.to_csv(MEMBERS_FILE, index=False)

    @staticmethod
    def get_user_groups(username):
        members = DataManager.load_members()
        user_memberships = members[members['username'] == username]
        
        groups = DataManager.load_groups()
        # Join to get group details
        result = pd.merge(user_memberships, groups, on='group_id')
        return result[['group_id', 'group_name', 'admin_username']]

    @staticmethod
    def get_group_details(group_id):
        groups = DataManager.load_groups()
        grp = groups[groups['group_id'] == group_id]
        if not grp.empty:
            return grp.iloc[0].to_dict()
        return None

    @staticmethod
    def update_group_rules(group_id, new_rules):
        groups = DataManager.load_groups()
        groups.loc[groups['group_id'] == group_id, 'rules'] = new_rules
        groups.to_csv(GROUPS_FILE, index=False)

    # --- Message Management ---
    @staticmethod
    def load_messages(group_id=None):
        if os.path.exists(CHATS_FILE):
             df = pd.read_csv(CHATS_FILE).astype(str)
             if group_id:
                 return df[df['group_id'] == group_id]
             return df
        return pd.DataFrame(columns=['message_id', 'group_id', 'username', 'message', 'status', 'reason', 'timestamp'])

    @staticmethod
    def save_message(group_id, username,message, status, reason=""):
        chats = DataManager.load_messages() # Load all to append
        new_msg = pd.DataFrame({
            'message_id': [str(uuid.uuid4())],
            'group_id': [group_id],
            'username': [username], 
            'message': [message], 
            'status': [status],
            'reason': [reason],
            'timestamp': [Utils.get_time()]
        })
        chats = pd.concat([chats, new_msg], ignore_index=True)
        chats.to_csv(CHATS_FILE, index=False)

class ModerationService:
    @staticmethod
    def validate_message(message_content, group_id):
        """
        Validates a message against the specific rules of a group.
        """
        group = DataManager.get_group_details(group_id)
        rules = group.get('rules', '') if group else ""
        
        if not rules:
            return True, "No rules set."

        system_prompt = f"""
        You are a strict Group Chat Moderator.
        Your task is to validate user messages against the following Admin Rules:
        {rules}

        If the message follows the rules, output PASS.
        If the message violates any rule, output FLAGGED followed by a short explanation for the user.
        Do not explain if it passes.
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Message to validate: '{message_content}'"}
        ]

        try:
            # Log attempt
            with open(os.path.join(DATA_DIR, "debug_log.txt"), "a") as log:
                 log.write(f"Validating msg: '{message_content}' for group {group_id}\n")

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages
            )
            
            content = response.choices[0].message.content.strip()
            
            # Log response
            with open(os.path.join(DATA_DIR, "debug_log.txt"), "a") as log:
                 log.write(f"API Response: {content}\n")

            if content.startswith("PASS"):
                return True, "Message allowed."
            elif content.startswith("FLAGGED"):
                reason = content.replace("FLAGGED", "", 1).strip()
                return False, reason.lstrip(":- ")
            else:
                 # Heuristic
                 lower_content = content.lower()
                 if "violate" in lower_content or "not allowed" in lower_content or "flagged" in lower_content:
                     return False, "Message flagged by content filter."
                 
                 return True, "Message allowed (Default)."

        except Exception as e:
            with open(os.path.join(DATA_DIR, "debug_log.txt"), "a") as log:
                 log.write(f"Exception: {str(e)}\n")
            return False, f"Moderation Error: {str(e)}"
