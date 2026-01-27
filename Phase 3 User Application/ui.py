import streamlit as st
import time
from main import DataManager, ModerationService, Utils

# --- Page Config & Styling ---
st.set_page_config(page_title="ConvoEase", page_icon="💬", layout="wide")

# Modern WhatsApp-like CSS
st.markdown("""
<style>
    /* Global Reset & Font */
    body {
        font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
        background-color: #d1d7db;
    }
    .stApp {
        background-color: #d1d7db; /* WhatsApp Web background */
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e9edef;
    }

    /* Chat Container */
    .chat-container {
        background-color: #efeae2; /* WhatsApp Chat Background */
        background-image: url("https://user-images.githubusercontent.com/15075759/28719144-86dc0f70-73b1-11e7-911d-60d936a2eb2d.png"); /* Subtle pattern */
        border-radius: 0;
        padding: 20px;
        height: 70vh;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
    }

    /* Message Bubbles */
    .message-bubble {
        max-width: 65%;
        padding: 8px 12px;
        margin: 4px 0;
        border-radius: 7.5px;
        position: relative;
        font-size: 14.2px;
        line-height: 19px;
        color: #111b21;
        box-shadow: 0 1px 0.5px rgba(11,20,26,.13);
    }
    
    .my-message {
        background-color: #d9fdd3;
        align-self: flex-end; /* Flex alignment */
        margin-left: auto;
        border-top-right-radius: 0;
    }
    
    .other-message {
        background-color: #ffffff;
        align-self: flex-start;
        margin-right: auto;
        border-top-left-radius: 0;
    }

    .msg-sender {
        font-size: 12.8px;
        font-weight: bold;
        color: #5d6d76; /* Darker grey */
        margin-bottom: 2px;
    }
    
    .msg-sender-me {
         display: none;
    }

    .msg-time {
        font-size: 11px;
        color: #667781;
        text-align: right;
        margin-top: 4px;
        float: right;
    }

    /* Input Area */
    .input-area {
        background-color: #f0f2f5;
        padding: 10px;
        border-left: 1px solid rgba(0,0,0,0.08);
    }

    /* Headers */
    .chat-header {
        background-color: #f0f2f5;
        padding: 10px 16px;
        border-left: 1px solid #d1d7db;
        display: flex;
        align-items: center;
        width: 100%;
    }
    
    /* Buttons */
    .stButton button {
        border-radius: 20px;
    }

</style>
""", unsafe_allow_html=True)

# --- Session Management ---
if 'user' not in st.session_state:
    st.session_state['user'] = None # stored as dict
if 'current_group_id' not in st.session_state:
    st.session_state['current_group_id'] = None

# --- Helper Functions ---
def logout():
    st.session_state['user'] = None
    st.session_state['current_group_id'] = None
    st.rerun()

def login_form():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("ConvoEase Login")
        with st.container(border=True):
            tab1, tab2 = st.tabs(["Login", "Sign Up"])
            
            with tab1:
                username = st.text_input("Username", key="login_u")
                password = st.text_input("Password", type="password", key="login_p")
                if st.button("Login", use_container_width=True):
                    success, user_data = DataManager.validate_login(username, password)
                    if success:
                        st.session_state['user'] = user_data
                        st.rerun()
                    else:
                        st.error("Invalid credentials")

            with tab2:
                new_u = st.text_input("Username", key="reg_u")
                new_p = st.text_input("Password", type="password", key="reg_p")
                full_name = st.text_input("Full Name", key="reg_fn")
                bio = st.text_area("Bio (Optional)", key="reg_bio")
                if st.button("Create Account", use_container_width=True):
                    if new_u and new_p and full_name:
                        success, msg = DataManager.register_user(new_u, new_p, full_name, bio)
                        if success:
                            st.success("Account created! Please login.")
                        else:
                            st.error(msg)
                    else:
                        st.error("Please fill required fields.")

# --- Main App Logic ---

if not st.session_state['user']:
    login_form()
else:
    # Authenticated View
    user = st.session_state['user']
    username = user['username']

    # --- SIDEBAR: Group Navigation ---
    with st.sidebar:
        # Profile Header
        st.markdown(f"### 👋 Hi, {user['full_name']}")
        st.caption(f"@{username}")
        if st.button("Logout"):
            logout()
        st.divider()

        # My Groups Section
        st.subheader("My Groups")
        my_groups = DataManager.get_user_groups(username)
        
        # Group Selection
        if not my_groups.empty:
            for idx, row in my_groups.iterrows():
                grp_name = row['group_name']
                grp_id = row['group_id']
                is_admin = row['admin_username'] == username
                label = f"{'👑 ' if is_admin else '# '}{grp_name}"
                
                # Active style
                is_active = st.session_state['current_group_id'] == grp_id
                btn_type = "primary" if is_active else "secondary"
                
                if st.button(label, key=f"grp_{grp_id}", use_container_width=True, type=btn_type):
                    st.session_state['current_group_id'] = grp_id
                    st.rerun()
        else:
            st.info("You haven't joined any groups yet.")

        st.divider()
        
        # Join/Create Tools
        with st.expander("➕ Join or Create Group"):
            tab_join, tab_create = st.tabs(["Join", "Create"])
            with tab_join:
                j_id = st.text_input("Group ID", key="j_id")
                j_pass = st.text_input("Password", key="j_pass", type="password")
                if st.button("Join Group"):
                    success, msg = DataManager.join_group(j_id, j_pass, username)
                    if success:
                        st.success("Joined!")
                        st.rerun()
                    else:
                        st.error(msg)
            
            with tab_create:
                c_name = st.text_input("Group Name", key="c_name")
                c_pass = st.text_input("Group Password", key="c_pass")
                if st.button("Create Group"):
                    if c_name and c_pass:
                        success, gid = DataManager.create_group(c_name, c_pass, username)
                        if success:
                            st.success(f"Created! ID: {gid}")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.error("Name and Password required.")

    # --- MAIN AREA ---
    if st.session_state['current_group_id']:
        group_id = st.session_state['current_group_id']
        group_details = DataManager.get_group_details(group_id)
        
        if not group_details:
             st.error("Group not found. It may have been deleted.")
             st.stop()

        is_admin = group_details['admin_username'] == username

        # Header
        col_h1, col_h2 = st.columns([6,1])
        with col_h1:
            st.markdown(f"## 👥 {group_details['group_name']}")
            st.caption(f"Group ID: `{group_id}` | Admin: @{group_details['admin_username']}")
        with col_h2:
            if st.button("Refresh 🔄"):
                st.rerun()

        # Admin Panel (Expander)
        if is_admin:
            with st.expander("🛡️ Admin Controls (Only visible to you)"):
                st.write("**Edit Group Rules**")
                new_rules = st.text_area("Rules", value=group_details['rules'], height=100)
                if st.button("Update Rules"):
                    DataManager.update_group_rules(group_id, new_rules)
                    st.success("Rules updated!")
                
                st.divider()
                st.write("**🗑️ Flagged Messages Bucket** (Blocked messages)")
                all_msgs = DataManager.load_messages(group_id)
                flagged = all_msgs[all_msgs['status'] == 'FLAGGED']
                if not flagged.empty:
                    st.dataframe(flagged[['timestamp', 'username', 'message', 'reason']], hide_index=True)
                else:
                    st.info("No flagged messages.")

        st.divider()

        # Chat Area
        chat_msgs = DataManager.load_messages(group_id)
        visible_msgs = chat_msgs[chat_msgs['status'] == 'PASS']
        
        # Sort and Display
        # We manually render HTML for the best "Chat" look
        chat_html = "<div class='chat-container'>"
        import html
        for _, msg in visible_msgs.sort_values('timestamp').iterrows():
            is_me = msg['username'] == username
            align_cls = "my-message" if is_me else "other-message"
            sender_cls = "msg-sender-me" if is_me else "msg-sender"
            
            safe_msg = html.escape(str(msg['message']))
            safe_user = html.escape(str(msg['username']))
            
            chat_html += f"""
<div style="display:flex; flex-direction:column;">
    <div class="message-bubble {align_cls}">
        <div class="{sender_cls}">{safe_user}</div>
        {safe_msg}
        <div class="msg-time">{msg['timestamp'][11:16]}</div>
    </div>
</div>
"""
        chat_html += "</div>"
        st.markdown(chat_html, unsafe_allow_html=True)

        # Input Area
        with st.form("msg_form", clear_on_submit=True):
            col_in1, col_in2 = st.columns([8, 1])
            with col_in1:
                txt_input = st.text_input("Message...", label_visibility="collapsed", placeholder="Type a message")
            with col_in2:
                sent = st.form_submit_button("➤")
            
            if sent and txt_input:
                with st.spinner("Moderating..."):
                   allowed, reason = ModerationService.validate_message(txt_input, group_id)
                
                if allowed:
                    DataManager.save_message(group_id, username, txt_input, "PASS")
                    st.rerun()
                else:
                    DataManager.save_message(group_id, username, txt_input, "FLAGGED", reason)
                    st.error(f"🚫 Message Blocked: {reason}")
    else:
        # Welcome Screen
        st.markdown("""
        <div style="text-align: center; margin-top: 100px;">
            <h1>Welcome to ConvoEase</h1>
            <p style="font-size: 1.2rem; color: #666;">
                Select a group from the sidebar or create a new one to start chatting.<br>
                Secure, Moderated, and Easy.
            </p>
            <div style="font-size: 5rem;">📱</div>
        </div>
        """, unsafe_allow_html=True)
