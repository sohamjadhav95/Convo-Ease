"""
ConvoEase - AI-Driven Content Moderation Chat System
Prototype Version 1.0
"""

import streamlit as st
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import os
from groq import Groq
from dataclasses import dataclass, asdict
from enum import Enum

# Configuration
CONFIG = {
    "APP_NAME": "ConvoEase",
    "VERSION": "1.0.0-prototype",
    "DEFAULT_MODEL": "llama-3.1-70b-versatile",  # Groq model
    "MAX_RULES_LENGTH": 1000,
    "MAX_MESSAGE_LENGTH": 500,
}

# Message Status Enum
class MessageStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    PENDING = "pending"

# Data Classes
@dataclass
class Message:
    """Represents a chat message"""
    id: str
    sender: str
    content: str
    timestamp: datetime
    status: MessageStatus
    reason: Optional[str] = None
    
    def to_dict(self):
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['status'] = self.status.value
        return data

@dataclass
class ValidationResult:
    """Result from content validation"""
    is_valid: bool
    reason: str
    confidence: float = 1.0

# Content Validator Class
class ContentValidator:
    """Handles message validation using LLM"""
    
    def __init__(self, api_key: str, model: str = CONFIG["DEFAULT_MODEL"]):
        """Initialize the validator with Groq API"""
        self.client = None
        self.model = model
        if api_key:
            try:
                self.client = Groq(api_key=api_key)
            except Exception as e:
                st.error(f"Failed to initialize Groq client: {e}")
    
    def validate_message(self, message: str, rules: str) -> ValidationResult:
        """
        Validate a message against specified rules using LLM
        
        Args:
            message: The message to validate
            rules: The moderation rules
            
        Returns:
            ValidationResult object
        """
        if not self.client:
            return ValidationResult(
                is_valid=True,
                reason="No API key configured - defaulting to allow",
                confidence=0.0
            )
        
        if not rules.strip():
            return ValidationResult(
                is_valid=True,
                reason="No rules specified - all messages allowed",
                confidence=1.0
            )
        
        try:
            # Construct validation prompt
            system_prompt = """You are a content moderation assistant. Your task is to validate messages against specific group rules.
            
Analyze the message and determine if it violates any of the provided rules.
Respond in JSON format with exactly these fields:
- "valid": boolean (true if message is acceptable, false if it violates rules)
- "reason": string (brief explanation of your decision)
- "confidence": number between 0 and 1 (how confident you are in your decision)

Be strict but fair. Consider context and intent."""

            user_prompt = f"""Group Rules:
{rules}

Message to validate:
"{message}"

Validate this message against the rules above."""

            # Call Groq API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=200,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            
            return ValidationResult(
                is_valid=result.get("valid", True),
                reason=result.get("reason", "No reason provided"),
                confidence=result.get("confidence", 0.5)
            )
            
        except json.JSONDecodeError:
            return ValidationResult(
                is_valid=True,
                reason="Failed to parse validation response",
                confidence=0.0
            )
        except Exception as e:
            return ValidationResult(
                is_valid=True,
                reason=f"Validation error: {str(e)}",
                confidence=0.0
            )

# Chat Manager Class
class ChatManager:
    """Manages chat messages and history"""
    
    def __init__(self):
        """Initialize chat manager"""
        self.messages: List[Message] = []
        self.flagged_messages: List[Message] = []
        self.message_counter = 0
    
    def add_message(self, sender: str, content: str, validation_result: ValidationResult) -> Message:
        """
        Add a new message to the chat
        
        Args:
            sender: Name of the message sender
            content: Message content
            validation_result: Validation result from ContentValidator
            
        Returns:
            The created Message object
        """
        self.message_counter += 1
        
        message = Message(
            id=f"msg_{self.message_counter}",
            sender=sender,
            content=content,
            timestamp=datetime.now(),
            status=MessageStatus.VALID if validation_result.is_valid else MessageStatus.INVALID,
            reason=validation_result.reason
        )
        
        if validation_result.is_valid:
            self.messages.append(message)
        else:
            self.flagged_messages.append(message)
        
        return message
    
    def get_valid_messages(self) -> List[Message]:
        """Get all valid messages"""
        return self.messages
    
    def get_flagged_messages(self) -> List[Message]:
        """Get all flagged messages"""
        return self.flagged_messages
    
    def clear_chat(self):
        """Clear all messages"""
        self.messages = []
        self.flagged_messages = []
        self.message_counter = 0

# UI Components
class UIComponents:
    """Reusable UI components"""
    
    @staticmethod
    def render_message(message: Message, is_flagged: bool = False):
        """Render a single message in the chat"""
        if is_flagged:
            with st.container():
                st.markdown(
                    f"""
                    <div style="background-color: #ffebee; padding: 10px; border-radius: 10px; margin: 5px 0; border-left: 3px solid #f44336;">
                        <strong style="color: #d32f2f;">🚫 {message.sender}</strong>
                        <span style="color: #757575; font-size: 0.8em;"> • {message.timestamp.strftime('%H:%M:%S')}</span>
                        <div style="color: #424242; text-decoration: line-through; margin-top: 5px;">{message.content}</div>
                        <div style="color: #d32f2f; font-size: 0.85em; margin-top: 5px;">⚠️ Blocked: {message.reason}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            with st.container():
                st.markdown(
                    f"""
                    <div style="background-color: #e8f5e9; padding: 10px; border-radius: 10px; margin: 5px 0; border-left: 3px solid #4caf50;">
                        <strong style="color: #2e7d32;">✅ {message.sender}</strong>
                        <span style="color: #757575; font-size: 0.8em;"> • {message.timestamp.strftime('%H:%M:%S')}</span>
                        <div style="color: #1b5e20; margin-top: 5px;">{message.content}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
    
    @staticmethod
    def render_rules_editor() -> str:
        """Render the rules editor in the sidebar"""
        st.sidebar.markdown("### 📋 Group Rules")
        st.sidebar.markdown("*Define moderation rules for this chat*")
        
        # Predefined rule templates
        rule_templates = {
            "Professional": "Only professional and work-related content is allowed. No personal discussions, jokes, or casual chat.",
            "Educational": "Only educational content is allowed. Messages must be informative, constructive, and relevant to learning.",
            "No Spam": "No spam, promotional content, or repetitive messages. No links without context.",
            "Respectful": "Be respectful and courteous. No offensive language, hate speech, or personal attacks.",
            "Custom": ""
        }
        
        template = st.sidebar.selectbox(
            "Choose a template:",
            options=list(rule_templates.keys()),
            index=len(rule_templates) - 1
        )
        
        initial_rules = rule_templates[template] if template != "Custom" else st.session_state.get('rules', '')
        
        rules = st.sidebar.text_area(
            "Moderation Rules:",
            value=initial_rules,
            height=150,
            max_chars=CONFIG["MAX_RULES_LENGTH"],
            help="Enter the rules that all messages must follow"
        )
        
        if st.sidebar.button("💾 Save Rules", use_container_width=True):
            st.session_state.rules = rules
            st.sidebar.success("Rules saved successfully!")
        
        return st.session_state.get('rules', rules)
    
    @staticmethod
    def render_api_config():
        """Render API configuration in the sidebar"""
        st.sidebar.markdown("### 🔧 Configuration")
        
        api_key = st.sidebar.text_input(
            "Groq API Key:",
            type="password",
            value=st.session_state.get('api_key', ''),
            help="Enter your Groq API key for content validation"
        )
        
        if api_key:
            st.session_state.api_key = api_key
        
        model = st.sidebar.selectbox(
            "Model:",
            options=[
                "llama-3.1-70b-versatile",
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768",
                "gemma2-9b-it"
            ],
            index=0
        )
        
        return api_key, model

# Main Application
class ConvoEaseApp:
    """Main application class"""
    
    def __init__(self):
        """Initialize the application"""
        self.setup_session_state()
        self.validator = None
        self.chat_manager = None
    
    def setup_session_state(self):
        """Initialize session state variables"""
        if 'initialized' not in st.session_state:
            st.session_state.initialized = True
            st.session_state.chat_manager = ChatManager()
            st.session_state.rules = ""
            st.session_state.api_key = ""
            st.session_state.username = "User"
    
    def run(self):
        """Run the main application"""
        # Page configuration
        st.set_page_config(
            page_title=CONFIG["APP_NAME"],
            page_icon="💬",
            layout="wide"
        )
        
        # Custom CSS
        st.markdown("""
            <style>
            .main {padding-top: 0;}
            .stButton > button {width: 100%;}
            </style>
        """, unsafe_allow_html=True)
        
        # Header
        st.title(f"💬 {CONFIG['APP_NAME']}")
        st.markdown("*AI-Driven Content Moderation Chat System*")
        st.divider()
        
        # Sidebar
        with st.sidebar:
            st.markdown(f"### {CONFIG['APP_NAME']} v{CONFIG['VERSION']}")
            
            # User configuration
            username = st.text_input("Your Name:", value=st.session_state.username)
            if username:
                st.session_state.username = username
            
            st.divider()
            
            # API Configuration
            api_key, model = UIComponents.render_api_config()
            
            st.divider()
            
            # Rules Editor
            rules = UIComponents.render_rules_editor()
            
            st.divider()
            
            # Flagged Messages Section
            st.markdown("### 🚫 Flagged Messages")
            flagged = st.session_state.chat_manager.get_flagged_messages()
            if flagged:
                st.markdown(f"*{len(flagged)} message(s) blocked*")
                with st.expander("View blocked messages", expanded=False):
                    for msg in flagged[-5:]:  # Show last 5
                        st.error(f"**{msg.sender}:** {msg.content[:50]}...")
                        st.caption(f"Reason: {msg.reason}")
            else:
                st.info("No flagged messages")
            
            st.divider()
            
            # Actions
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.chat_manager.clear_chat()
                st.rerun()
        
        # Main chat area
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Initialize validator
            if api_key:
                self.validator = ContentValidator(api_key, model)
            else:
                st.warning("⚠️ Please configure your Groq API key in the sidebar for content validation")
                self.validator = ContentValidator("")
            
            # Chat display
            st.markdown("### 💬 Chat Room")
            
            chat_container = st.container()
            with chat_container:
                messages = st.session_state.chat_manager.get_valid_messages()
                if messages:
                    for msg in messages:
                        UIComponents.render_message(msg, is_flagged=False)
                else:
                    st.info("No messages yet. Start a conversation!")
            
            # Message input
            with st.form("message_form", clear_on_submit=True):
                col_input, col_send = st.columns([5, 1])
                with col_input:
                    message_input = st.text_input(
                        "Type your message:",
                        max_chars=CONFIG["MAX_MESSAGE_LENGTH"],
                        label_visibility="collapsed",
                        placeholder="Type your message here..."
                    )
                with col_send:
                    send_button = st.form_submit_button("📤 Send", use_container_width=True)
                
                if send_button and message_input:
                    # Validate message
                    validation_result = self.validator.validate_message(message_input, rules)
                    
                    # Add message to chat
                    message = st.session_state.chat_manager.add_message(
                        sender=st.session_state.username,
                        content=message_input,
                        validation_result=validation_result
                    )
                    
                    if not validation_result.is_valid:
                        st.error(f"❌ Your message couldn't be delivered - violates group rules: {validation_result.reason}")
                    else:
                        st.success("✅ Message sent successfully!")
                    
                    st.rerun()
        
        with col2:
            # Stats and info panel
            st.markdown("### 📊 Session Stats")
            
            valid_count = len(st.session_state.chat_manager.get_valid_messages())
            flagged_count = len(st.session_state.chat_manager.get_flagged_messages())
            total_count = valid_count + flagged_count
            
            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                st.metric("Valid", valid_count, delta=None)
            with col_stat2:
                st.metric("Blocked", flagged_count, delta=None)
            
            if total_count > 0:
                approval_rate = (valid_count / total_count) * 100
                st.progress(approval_rate / 100)
                st.caption(f"Approval Rate: {approval_rate:.1f}%")
            
            st.divider()
            
            # Active Rules Display
            st.markdown("### 📜 Active Rules")
            if rules:
                st.info(rules[:200] + "..." if len(rules) > 200 else rules)
            else:
                st.warning("No rules configured")
            
            st.divider()
            
            # Future Features Placeholder
            st.markdown("### 🚀 Coming Soon")
            st.markdown("""
            - 🖼️ Image moderation
            - 🎵 Audio analysis
            - 👥 User authentication
            - 🏢 Organization management
            - 🤖 Local model support
            """)

# Run the application
if __name__ == "__main__":
    app = ConvoEaseApp()
    app.run()