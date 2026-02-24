import streamlit as st
from core_processing_engine import validate_and_stream_message

st.set_page_config(page_title="Groq Streaming Chat", page_icon="💬", layout="wide")
st.title("💬 Groq Streaming Chat Prototype")

# --- Session State ---
if 'api_key' not in st.session_state:
    st.session_state.api_key = ''
if 'username' not in st.session_state:
    st.session_state.username = 'User'
if 'rules' not in st.session_state:
    st.session_state.rules = ''
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []  # list of dicts: {sender, system_message, user_message, response, valid, reason}
if 'flagged_messages' not in st.session_state:
    st.session_state.flagged_messages = []

# --- Sidebar ---
with st.sidebar:
    st.header("Settings")
    st.session_state.api_key = st.text_input("API Key", value=st.session_state.api_key, type="password")
    st.session_state.username = st.text_input("Username", value=st.session_state.username)
    st.session_state.rules = st.text_area("Moderation Rules", value=st.session_state.rules, height=100, help="Rules for message validation")
    st.markdown("---")
    st.write(f"**Total messages:** {len(st.session_state.chat_history)}")
    st.write(f"**Flagged:** {len(st.session_state.flagged_messages)}")
    if st.button("Clear Chat"):
        st.session_state.chat_history = []
        st.session_state.flagged_messages = []
        st.experimental_rerun()

# --- Main Chat Area ---
st.subheader("Chat Room")

# Display chat history
# --- Chat UI (WhatsApp/Telegram style) ---
chat_bubble_style = """
<style>
.user-bubble {
    background: #dcf8c6;
    color: #222;
    padding: 10px 14px;
    border-radius: 18px 18px 4px 18px;
    margin: 8px 0 8px 40%;
    max-width: 60%;
    text-align: right;
    box-shadow: 0 1px 1px rgba(0,0,0,0.04);
    font-size: 1.05em;
}
.assistant-bubble {
    background: #fff;
    color: #222;
    padding: 10px 14px;
    border-radius: 18px 18px 18px 4px;
    margin: 8px 40% 8px 0;
    max-width: 60%;
    text-align: left;
    box-shadow: 0 1px 1px rgba(0,0,0,0.04);
    font-size: 1.05em;
}
</style>
"""
st.markdown(chat_bubble_style, unsafe_allow_html=True)

for entry in st.session_state.chat_history:
    st.markdown(f"<div class='user-bubble'><b>{entry['sender']}:</b> {entry['user_message']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='assistant-bubble'>{entry['response']}</div>", unsafe_allow_html=True)

# --- Message Input ---
st.markdown("---")
st.write("**Send a message:**")
with st.form("send_message_form", clear_on_submit=True):
    user_message = st.text_area("User Message", height=80, key="user_msg_input")
    send_btn = st.form_submit_button("Send")

import time

if send_btn:
    api_key = st.session_state.api_key
    username = st.session_state.username
    rules = st.session_state.rules
    if not api_key or not user_message:
        st.warning("Please fill in all fields.")
    else:
        with st.spinner("Validating and streaming response..."):
            is_valid, reason, stream_gen = validate_and_stream_message(api_key, rules, user_message)
            if is_valid:
                response_placeholder = st.empty()
                full_response = ""
                for chunk in stream_gen:
                    full_response += chunk
                    response_placeholder.markdown(full_response)
                st.session_state.chat_history.append({
                    'sender': username,
                    'rules': rules,
                    'user_message': user_message,
                    'response': full_response
                })
                st.rerun()
            else:
                st.toast(f"❌ Message blocked: {reason}", icon="🚫")
                time.sleep(2)
                st.session_state.flagged_messages.append({
                    'sender': username,
                    'user_message': user_message,
                    'reason': reason
                })
