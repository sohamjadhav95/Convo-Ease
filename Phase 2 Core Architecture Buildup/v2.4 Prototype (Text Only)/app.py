"""
ConvoEase - Multi-User Message Validator Streamlit UI
AI-powered content moderation for group forums and communities
"""

import streamlit as st
import time
from processing_engine import MessageValidator, validate_message, split_rules_with_ids

# -----------------------------------
# Page Config
# -----------------------------------
st.set_page_config(
    page_title="ConvoEase - Group Message Validator",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------
# User Configuration
# -----------------------------------
USERS = {
    "admin": {"name": "Admin", "color": "#ff6b6b", "icon": "👑"},
    "user1": {"name": "User 1", "color": "#4ecdc4", "icon": "👤"},
    "user2": {"name": "User 2", "color": "#95e1d3", "icon": "👥"}
}

# -----------------------------------
# Custom CSS
# -----------------------------------
st.markdown("""
    <style>
    /* Main styling */
    .valid-msg {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .invalid-msg {
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .stAlert {
        margin-top: 10px;
    }
    .metric-container {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    
    /* WhatsApp-like message styling */
    .message-container {
        margin: 10px 0;
        clear: both;
    }
    
    .message-own {
        background-color: #dcf8c6;
        border-radius: 8px;
        padding: 8px 12px;
        margin-left: 20%;
        float: right;
        max-width: 75%;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }
    
    .message-other {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 8px 12px;
        margin-right: 20%;
        float: left;
        max-width: 75%;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        border: 1px solid #e0e0e0;
    }
    
    .message-sender {
        font-weight: bold;
        font-size: 0.9em;
        margin-bottom: 4px;
    }
    
    .message-text {
        font-size: 1em;
        line-height: 1.4;
    }
    
    .message-time {
        font-size: 0.75em;
        color: #666;
        text-align: right;
        margin-top: 4px;
    }
    
    /* User selector styling */
    .user-selector {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        color: white;
    }
    
    /* Chat message styling */
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        padding-top: 1rem;
    }
    
    /* Footer styling */
    .footer {
        text-align: center;
        padding: 1rem;
        color: #666;
    }
    
    /* User badge */
    .user-badge {
        display: inline-block;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
        margin: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------
# Initialize Model (with caching)
# -----------------------------------
@st.cache_resource
def load_model():
    """Load the validation model. Cached to avoid reloading."""
    try:
        validator = MessageValidator()
        tokenizer, model = validator.load_model()
        return tokenizer, model, validator
    except Exception as e:
        st.error(f"Error loading model: {str(e)}")
        return None, None, None

# -----------------------------------
# Session State Initialization
# -----------------------------------
def initialize_session_state():
    """Initialize all session state variables."""
    if "current_user" not in st.session_state:
        st.session_state.current_user = "admin"
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "flagged_messages" not in st.session_state:
        st.session_state.flagged_messages = []
    if "validation_history" not in st.session_state:
        st.session_state.validation_history = []
    if "stats" not in st.session_state:
        st.session_state.stats = {"valid": 0, "invalid": 0, "total": 0}
    if "user_stats" not in st.session_state:
        st.session_state.user_stats = {
            "admin": {"valid": 0, "invalid": 0, "total": 0},
            "user1": {"valid": 0, "invalid": 0, "total": 0},
            "user2": {"valid": 0, "invalid": 0, "total": 0}
        }
    if "show_notification" not in st.session_state:
        st.session_state.show_notification = False
    if "notification_data" not in st.session_state:
        st.session_state.notification_data = None
    if "last_rules" not in st.session_state:
        st.session_state.last_rules = ""

# Initialize session state
initialize_session_state()

# -----------------------------------
# Helper Functions
# -----------------------------------
def clear_all_history():
    """Clear all history and reset statistics."""
    st.session_state.messages = []
    st.session_state.flagged_messages = []
    st.session_state.validation_history = []
    st.session_state.stats = {"valid": 0, "invalid": 0, "total": 0}
    st.session_state.user_stats = {
        "admin": {"valid": 0, "invalid": 0, "total": 0},
        "user1": {"valid": 0, "invalid": 0, "total": 0},
        "user2": {"valid": 0, "invalid": 0, "total": 0}
    }
    st.session_state.show_notification = False
    st.session_state.notification_data = None

def update_statistics(decision, user_id):
    """Update validation statistics."""
    st.session_state.stats["total"] += 1
    st.session_state.user_stats[user_id]["total"] += 1
    
    if decision == "VALID":
        st.session_state.stats["valid"] += 1
        st.session_state.user_stats[user_id]["valid"] += 1
    else:
        st.session_state.stats["invalid"] += 1
        st.session_state.user_stats[user_id]["invalid"] += 1

def get_user_flagged_messages(user_id):
    """Get flagged messages visible to the current user."""
    if user_id == "admin":
        # Admin sees all flagged messages
        return st.session_state.flagged_messages
    else:
        # Regular users see only their own flagged messages
        return [msg for msg in st.session_state.flagged_messages if msg.get("user_id") == user_id]

def display_notification(notif_data):
    """Display notification for flagged messages."""
    alert_container = st.empty()
    with alert_container.container():
        st.error("🚫 **Message Flagged - Violation Detected**")
        st.write(f"**Reason:** {notif_data['reason']}")
        if notif_data['violated_rules']:
            st.warning("**Violated Rules:**")
            for rule in notif_data['violated_rules']:
                st.markdown(f"- {rule}")
        st.caption(f"Message moved to Flagged Messages section | Latency: {notif_data['latency_ms']}ms")
    
    # Clear notification after 3 seconds
    time.sleep(3)
    st.session_state.show_notification = False
    st.session_state.notification_data = None
    alert_container.empty()

# -----------------------------------
# Main UI - Header with User Selector
# -----------------------------------
st.title("🛡️ ConvoEase - Group Message Validator")
st.markdown("**AI-powered content moderation for group forums and communities**")

# User Selector
col1, col2, col3, col4 = st.columns([1, 1, 1, 2])

with col1:
    if st.button(f"{USERS['admin']['icon']} {USERS['admin']['name']}", 
                 use_container_width=True,
                 type="primary" if st.session_state.current_user == "admin" else "secondary"):
        st.session_state.current_user = "admin"
        st.rerun()

with col2:
    if st.button(f"{USERS['user1']['icon']} {USERS['user1']['name']}", 
                 use_container_width=True,
                 type="primary" if st.session_state.current_user == "user1" else "secondary"):
        st.session_state.current_user = "user1"
        st.rerun()

with col3:
    if st.button(f"{USERS['user2']['icon']} {USERS['user2']['name']}", 
                 use_container_width=True,
                 type="primary" if st.session_state.current_user == "user2" else "secondary"):
        st.session_state.current_user = "user2"
        st.rerun()

with col4:
    current_user_info = USERS[st.session_state.current_user]
    st.markdown(f"""
        <div style='background-color: {current_user_info['color']}; padding: 10px; 
                    border-radius: 10px; text-align: center; color: white; font-weight: bold;'>
            {current_user_info['icon']} Currently logged in as: {current_user_info['name']}
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# -----------------------------------
# Sidebar Configuration
# -----------------------------------
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Model Loading Status
    with st.spinner("Loading model..."):
        tokenizer, model, validator = load_model()
    
    if tokenizer is None or model is None:
        st.error("❌ Failed to load model. Please check the model path.")
        st.stop()
    else:
        st.success("✅ Model loaded successfully")
        st.info(f"**Model:** {validator.model_version}")
    
    st.divider()
    
    # -----------------------------------
    # Current User Stats
    # -----------------------------------
    st.header(f"{current_user_info['icon']} Your Statistics")
    user_stat = st.session_state.user_stats[st.session_state.current_user]
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("✅ Valid", user_stat["valid"])
        st.metric("❌ Invalid", user_stat["invalid"])
    with col2:
        st.metric("📝 Total", user_stat["total"])
        if user_stat["total"] > 0:
            invalid_rate = (user_stat["invalid"] / user_stat["total"]) * 100
            st.metric("🚫 Block Rate", f"{invalid_rate:.1f}%")
        else:
            st.metric("🚫 Block Rate", "0.0%")
    
    st.divider()
    
    # -----------------------------------
    # Rules Input Section
    # -----------------------------------
    st.header("📋 Forum Rules")
    st.markdown("Enter rules separated by `|`")
    
    default_rules = """General information is allowed regarding class and college. |
Personal messages are not allowed. |
Only educational and learning-related messages are allowed. |
Be respectful and kind. |
Advertisements and promotions are strictly prohibited."""
    
    rules_input = st.text_area(
        "Rules Configuration",
        value=default_rules,
        height=200,
        help="Separate each rule with a pipe symbol (|)",
        key="rules_input"
    )
    
    # Display parsed rules
    if rules_input and rules_input.strip():
        try:
            parsed_rules = split_rules_with_ids(rules_input)
            with st.expander("📜 View Parsed Rules", expanded=False):
                for rule in parsed_rules:
                    st.markdown(f"- **{rule['id']}:** {rule['text']}")
        except Exception as e:
            st.error(f"Error parsing rules: {str(e)}")
    else:
        st.warning("⚠️ Please enter forum rules to enable validation.")
    
    st.divider()
    
    # -----------------------------------
    # Overall Statistics Section
    # -----------------------------------
    st.header("📊 Overall Statistics")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("✅ Valid", st.session_state.stats["valid"])
        st.metric("❌ Invalid", st.session_state.stats["invalid"])
    with col2:
        st.metric("📝 Total", st.session_state.stats["total"])
        if st.session_state.stats["total"] > 0:
            invalid_rate = (st.session_state.stats["invalid"] / st.session_state.stats["total"]) * 100
            st.metric("🚫 Block Rate", f"{invalid_rate:.1f}%")
        else:
            st.metric("🚫 Block Rate", "0.0%")
    
    # All Users Stats
    with st.expander("👥 All Users Statistics", expanded=False):
        for user_id, user_info in USERS.items():
            stat = st.session_state.user_stats[user_id]
            st.markdown(f"**{user_info['icon']} {user_info['name']}**")
            st.text(f"Valid: {stat['valid']} | Invalid: {stat['invalid']} | Total: {stat['total']}")
            st.markdown("---")
    
    # Clear History Button
    if st.button("🗑️ Clear All History", use_container_width=True, type="secondary"):
        clear_all_history()
        st.success("History cleared!")
        st.rerun()
    
    st.divider()
    
    # -----------------------------------
    # Flagged Messages Section (Filtered by User)
    # -----------------------------------
    st.header("🚨 Your Flagged Messages")
    
    user_flagged = get_user_flagged_messages(st.session_state.current_user)
    
    if user_flagged:
        st.metric("Total Flagged", len(user_flagged))
        
        # Display flagged messages
        for idx, flagged in enumerate(user_flagged):
            val = flagged['validation']
            sender_info = USERS.get(flagged.get('user_id', 'admin'), USERS['admin'])
            
            with st.expander(f"❌ {sender_info['icon']} {sender_info['name']} - {val['timestamp']}", expanded=False):
                st.write(f"**Message:**")
                st.info(flagged['message'])
                
                st.write(f"**Reason:** {val['reason']}")
                
                if val['violated_rules']:
                    st.warning("**Violated Rules:**")
                    for rule in val['violated_rules']:
                        st.markdown(f"- {rule}")
                
                st.caption(f"⏱️ Processing time: {val['latency_ms']}ms")
    else:
        if st.session_state.current_user == "admin":
            st.info("No flagged messages in the group yet!")
        else:
            st.info("You haven't had any messages flagged. Great job!")
    
    st.divider()

# -----------------------------------
# Check if Rules Changed
# -----------------------------------
if rules_input != st.session_state.last_rules:
    st.session_state.last_rules = rules_input
    st.rerun()

# -----------------------------------
# Main Chat Interface
# -----------------------------------
st.header("💬 Group Chat - Message Validator")
st.markdown("Send messages to the group. Valid messages appear here, invalid ones are flagged privately.")

# Display notification for invalid messages (3 seconds)
if st.session_state.show_notification and st.session_state.notification_data:
    display_notification(st.session_state.notification_data)
    st.rerun()

# Display chat history (WhatsApp-like interface)
chat_container = st.container()
with chat_container:
    if not st.session_state.messages:
        st.info("👋 Be the first to send a message to the group!")
    else:
        for idx, msg_data in enumerate(st.session_state.messages):
            user_id = msg_data.get("user_id", "admin")
            user_info = USERS.get(user_id, USERS['admin'])
            is_own_message = user_id == st.session_state.current_user
            
            if is_own_message:
                # Own message - right aligned, green background
                with st.chat_message("user", avatar=user_info['icon']):
                    st.markdown(f"**You** ({user_info['name']})")
                    st.write(msg_data["content"])
                    st.caption(msg_data.get("timestamp", ""))
            else:
                # Other's message - left aligned, white background
                with st.chat_message("assistant", avatar=user_info['icon']):
                    st.markdown(f"**{user_info['name']}**")
                    st.write(msg_data["content"])
                    st.caption(msg_data.get("timestamp", ""))

# -----------------------------------
# Chat Input Handler
# -----------------------------------
user_input = st.chat_input(f"Type your message as {current_user_info['name']}...")

if user_input:
    if not rules_input or not rules_input.strip():
        st.error("⚠️ Please configure forum rules in the sidebar first!")
    else:
        # Validate message
        with st.spinner("🔍 Validating message..."):
            try:
                validation_result = validate_message(tokenizer, model, rules_input, user_input)
                
                # Add user information to validation result
                validation_result["user_id"] = st.session_state.current_user
                validation_result["user_name"] = current_user_info["name"]
                
                # Update statistics
                update_statistics(validation_result["decision"], st.session_state.current_user)
                
                if validation_result["decision"] == "VALID":
                    # Add user message to group chat
                    st.session_state.messages.append({
                        "user_id": st.session_state.current_user,
                        "content": user_input,
                        "timestamp": validation_result["timestamp"]
                    })
                else:
                    # Add to flagged messages with user info
                    st.session_state.flagged_messages.append({
                        "user_id": st.session_state.current_user,
                        "message": user_input,
                        "validation": validation_result
                    })
                    
                    # Set notification to show
                    st.session_state.show_notification = True
                    st.session_state.notification_data = validation_result
                
                # Add to validation history
                st.session_state.validation_history.append(validation_result)
                
            except Exception as e:
                st.error(f"Error during validation: {str(e)}")
                st.exception(e)
        
        st.rerun()

# -----------------------------------
# Footer
# -----------------------------------
st.markdown("---")
st.markdown(
    f"""
    <div class='footer'>
        <p>Powered by Gemma-2-9B-IT | ConvoEase v3.0 Multi-User</p>
        <p>🛡️ Real-time AI content moderation for group forums</p>
        <p>👥 Currently: {len([m for m in st.session_state.messages])} valid messages | 
           🚫 {len(st.session_state.flagged_messages)} flagged messages</p>
    </div>
    """,
    unsafe_allow_html=True
)

# -----------------------------------
# Debug Information (Optional)
# -----------------------------------
if st.sidebar.checkbox("🐛 Show Debug Info", value=False):
    st.sidebar.markdown("### Debug Information")
    st.sidebar.json({
        "Current User": st.session_state.current_user,
        "Total Messages": len(st.session_state.messages),
        "Flagged Messages": len(st.session_state.flagged_messages),
        "Validation History": len(st.session_state.validation_history),
        "Overall Statistics": st.session_state.stats,
        "User Statistics": st.session_state.user_stats,
        "Model Loaded": validator.is_loaded() if validator else False
    })