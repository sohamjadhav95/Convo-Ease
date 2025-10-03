"""
ConvoEase - AI-Driven Content Moderation Chat System
Streamlit UI for Message Validation
"""

import streamlit as st
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
from groq import Groq

# Configuration
CONFIG = {
    "APP_NAME": "ConvoEase",
    "VERSION": "1.0.0",
    "MAX_RULES_LENGTH": 1000,
    "MAX_MESSAGE_LENGTH": 500,
}

# Core validation logic
DEFAULT_SYSTEM_PROMPT = "You are a messages validator system. Only messages align to the below rules mark them as valid else mark as Invalid. *ONLY RESPOND WITH VALID OR INVALID WORD*"

def groq_response(api_key: str, rules: str, user_message: str):
    """Yield streamed response chunks from Groq chat completion API."""
    system_prompt = DEFAULT_SYSTEM_PROMPT
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt + rules},
            {"role": "user", "content": user_message}
        ],
        temperature=0.5,
        max_tokens=8192, 
        top_p=1,
        stream=True,
        stop=None
    )
    for chunk in completion:
        yield chunk.choices[0].delta.content or ""

def validate_message(api_key: str, rules: str, user_message: str):
    """Validate message and return either the message or 'Invalid Message'."""
    response_chunks = []
    for chunk in groq_response(api_key, rules, user_message):
        response_chunks.append(chunk)
    full_response = "".join(response_chunks).strip().upper()
    if full_response == "VALID":
        return True
    else:
        return False

# Data Classes
@dataclass
class Message:
    """Represents a chat message"""
    sender: str
    content: str
    timestamp: datetime
    is_valid: bool

class ChatManager:
    """Manages chat messages and history"""
    
    def __init__(self):
        self.valid_messages: List[Message] = []
        self.blocked_messages: List[Message] = []
    
    def add_message(self, sender: str, content: str, is_valid: bool):
        """Add a new message to appropriate list"""
        message = Message(
            sender=sender,
            content=content,
            timestamp=datetime.now(),
            is_valid=is_valid
        )
        
        if is_valid:
            self.valid_messages.append(message)
        else:
            self.blocked_messages.append(message)
        
        return message
    
    def clear_chat(self):
        """Clear all messages"""
        self.valid_messages = []
        self.blocked_messages = []

# UI Components
def render_message(message: Message, is_blocked: bool = False):
    """Render a single message"""
    if is_blocked:
        st.markdown(
            f"""
            <div style="background-color: #ffebee; padding: 10px; border-radius: 10px; margin: 5px 0; border-left: 3px solid #f44336;">
                <strong style="color: #d32f2f;">🚫 {message.sender}</strong>
                <span style="color: #757575; font-size: 0.8em;"> • {message.timestamp.strftime('%H:%M:%S')}</span>
                <div style="color: #424242; text-decoration: line-through; margin-top: 5px;">{message.content}</div>
                <div style="color: #d32f2f; font-size: 0.85em; margin-top: 5px;">⚠️ Blocked: Violates group rules</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
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

def render_rules_editor() -> str:
    """Render the rules editor in sidebar"""
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

def render_api_config():
    """Render API configuration in sidebar"""
    st.sidebar.markdown("### 🔧 Configuration")
    
    api_key = st.sidebar.text_input(
        "Groq API Key:",
        type="password",
        value=st.session_state.get('api_key', ''),
        help="Enter your Groq API key for content validation"
    )
    
    if api_key:
        st.session_state.api_key = api_key
    
    return api_key

# Initialize session state
def init_session_state():
    """Initialize session state variables"""
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        st.session_state.chat_manager = ChatManager()
        st.session_state.rules = ""
        st.session_state.api_key = ""
        st.session_state.username = "User"

# Main Application
def main():
    """Run the main application"""
    # Initialize session state
    init_session_state()
    
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
        api_key = render_api_config()
        
        st.divider()
        
        # Rules Editor
        rules = render_rules_editor()
        
        st.divider()
        
        # Blocked Messages Section
        st.markdown("### 🚫 Blocked Messages")
        blocked = st.session_state.chat_manager.blocked_messages
        if blocked:
            st.markdown(f"*{len(blocked)} message(s) blocked*")
            with st.expander("View blocked messages", expanded=False):
                for msg in blocked[-5:]:  # Show last 5
                    st.error(f"**{msg.sender}:** {msg.content[:50]}...")
                    st.caption(f"Blocked at: {msg.timestamp.strftime('%H:%M:%S')}")
        else:
            st.info("No blocked messages")
        
        st.divider()
        
        # Actions
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_manager.clear_chat()
            st.rerun()
    
    # Main chat area
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # API key check
        if not api_key:
            st.warning("⚠️ Please configure your Groq API key in the sidebar for content validation")
        
        # Chat display
        st.markdown("### 💬 Chat Room")
        
        chat_container = st.container()
        with chat_container:
            messages = st.session_state.chat_manager.valid_messages
            if messages:
                for msg in messages:
                    render_message(msg, is_blocked=False)
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
                if not api_key:
                    st.error("❌ Please configure your Groq API key first!")
                elif not rules.strip():
                    st.warning("⚠️ Please set up moderation rules first!")
                else:
                    # Validate message
                    with st.spinner("Validating message..."):
                        is_valid = validate_message(api_key, rules, message_input)
                    
                    # Add message to chat
                    st.session_state.chat_manager.add_message(
                        sender=st.session_state.username,
                        content=message_input,
                        is_valid=is_valid
                    )
                    
                    if not is_valid:
                        st.error("❌ Your message was blocked - it violates group rules")
                    else:
                        st.success("✅ Message sent successfully!")
                    
                    st.rerun()
    
    with col2:
        # Stats panel
        st.markdown("### 📊 Session Stats")
        
        valid_count = len(st.session_state.chat_manager.valid_messages)
        blocked_count = len(st.session_state.chat_manager.blocked_messages)
        total_count = valid_count + blocked_count
        
        col_stat1, col_stat2 = st.columns(2)
        with col_stat1:
            st.metric("Valid", valid_count)
        with col_stat2:
            st.metric("Blocked", blocked_count)
        
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
        
        # Info
        st.markdown("### ℹ️ How It Works")
        st.markdown("""
        1. Set your **API key**
        2. Define **group rules**
        3. Send messages
        4. AI validates instantly
        5. Valid messages appear in chat
        """)

if __name__ == "__main__":
    main()