import streamlit as st
import time
import html
from main import DataManager, ModerationService, Utils

# --- Page Config ---
st.set_page_config(page_title="ConvoEase", page_icon="💬", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS (The Magic) ---
st.markdown("""
<style>
    /* IMPORT FONTS */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

    /* GLOBAL VARS */
    :root {
        --primary-color: #7C3AED; /* Violet-600 */
        --primary-light: #8B5CF6; /* Violet-500 */
        --bg-color: #F3F4F6; /* Gray-100 */
        --sidebar-bg: #FFFFFF;
        --text-color: #1F2937; /* Gray-800 */
        --text-secondary: #6B7280; /* Gray-500 */
    }

    /* GLOBAL RESET */
    .stApp {
        background-color: var(--bg-color);
        font-family: 'Inter', sans-serif;
    }

    /* HIDE DEFAULT STREAMLIT ELEMENTS */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* SIDEBAR STYLING */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-bg);
        border-right: 1px solid #E5E7EB;
    }
    
    [data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }

    /* CUSTOM GROUP LIST ITEM */
    .group-item {
        display: flex;
        align-items: center;
        padding: 10px;
        border-radius: 12px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: background 0.2s;
        text-decoration: none;
        color: inherit;
    }
    
    .group-item:hover {
        background-color: #F9FAFB;
    }

    .group-item.active {
        background-color: #ede9fe; /* Violet-50 */
    }

    .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
        font-size: 14px;
        margin-right: 12px;
        flex-shrink: 0;
    }

    .group-info {
        flex-grow: 1;
        overflow: hidden;
    }

    .group-name {
        font-weight: 600;
        font-size: 14px;
        color: var(--text-color);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .last-msg {
        font-size: 12px;
        color: var(--text-secondary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    /* CHAT AREA STYLING */
    .chat-header {
        background: white;
        padding: 15px 20px;
        border-bottom: 1px solid #E5E7EB;
        display: flex;
        align-items: center;
        justify-content: space-between;
        position: sticky;
        top: 0;
        z-index: 10;
    }

    .chat-convo-area {
        padding: 20px;
        height: 65vh;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
    }

    .msg-bubble {
        max-width: 60%;
        padding: 10px 16px;
        border-radius: 16px;
        font-size: 14px;
        line-height: 1.5;
        margin-bottom: 8px;
        position: relative;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }

    .msg-me {
        background-color: var(--primary-color);
        color: white;
        align-self: flex-end;
        border-bottom-right-radius: 4px;
    }

    .msg-other {
        background-color: white;
        color: var(--text-color);
        align-self: flex-start;
        border-bottom-left-radius: 4px;
        border: 1px solid #F3F4F6;
    }

    .msg-meta {
        font-size: 10px;
        margin-top: 4px;
        opacity: 0.8;
        text-align: right;
    }

    /* INPUT AREA */
    .stTextInput input {
        border-radius: 24px !important;
        border: 1px solid #E5E7EB !important;
        padding: 10px 20px !important;
        background-color: white !important;
    }
    
    .stTextInput input:focus {
        border-color: var(--primary-color) !important;
        box-shadow: 0 0 0 1px var(--primary-color) !important;
    }
    
    .stButton button {
        border-radius: 24px;
        background-color: var(--primary-color);
        color: white;
        border: none;
        padding: 10px 24px;
        font-weight: 500;
    }
    .stButton button:hover {
        background-color: var(--primary-light);
    }

    /* CUSTOM EXTRAS */
    .badge {
        background: #EF4444; /* Red */
        color: white;
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 10px;
        margin-left: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- Session Init ---
if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'current_group_id' not in st.session_state:
    st.session_state['current_group_id'] = None

# --- Helper Methods ---
def get_initials(name):
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper()

def get_avatar_color(name):
    colors = ['#EF4444', '#F59E0B', '#10B981', '#3B82F6', '#6366F1', '#8B5CF6', '#EC4899']
    return colors[hash(name) % len(colors)]

# --- Views ---
def login_view():
    col1, col2, col3 = st.columns([3, 4, 3])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background: white; padding: 40px; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
            <h2 style="text-align: center; color: #7C3AED; margin-bottom: 30px;">ConvoEase</h2>
        </div>
        """, unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        with tab1:
            u = st.text_input("Username", key="l_u")
            p = st.text_input("Password", type="password", key="l_p")
            if st.button("Login", use_container_width=True):
                success, data = DataManager.validate_login(u, p)
                if success:
                    st.session_state['user'] = data
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        with tab2:
            nu = st.text_input("Username", key="r_u")
            np = st.text_input("Password", type="password", key="r_p")
            fn = st.text_input("Full Name", key="r_fn")
            if st.button("Create Account", use_container_width=True):
                 if nu and np and fn:
                     success, msg = DataManager.register_user(nu, np, fn)
                     if success: st.success("Created! Login now.")
                     else: st.error(msg)
                 else:
                     st.error("All fields required")

def main_view():
    user = st.session_state['user']
    username = user['username']
    
    # --- SIDEBAR (Custom Implementation) ---
    with st.sidebar:
        st.markdown("## Chats")
        
        # New Chat Button
        with st.expander("📝 New Chat"):
             tab1, tab2 = st.tabs(["Create", "Join"])
             with tab1:
                 gn = st.text_input("Name", key="gn")
                 gp = st.text_input("Pass", key="gp")
                 if st.button("Create"):
                     ok, gid = DataManager.create_group(gn, gp, username)
                     if ok: 
                         st.session_state['current_group_id'] = gid
                         st.rerun()
             with tab2:
                 jid = st.text_input("ID", key="jid")
                 jp = st.text_input("Pass", key="jp")
                 if st.button("Join"):
                     ok, msg = DataManager.join_group(jid, jp, username)
                     if ok: st.rerun()
                     else: st.error(msg)
        
        st.markdown("<br>", unsafe_allow_html=True)

        my_groups = DataManager.get_user_groups(username)
        # Using radio button to manage state but hiding it visually or styling it differently? 
        # Actually standard st.buttons are cleaner for "Action" but managing "Active" state visually is hard.
        # Let's iterate and use columns/custom HTML buttons? No, Streamlit events are hard with HTML.
        # We will use st.button but inject 'active' style logic if possible or just use emojis.
        
        if my_groups.empty:
            st.info("No chats yet.")
        
        for idx, row in my_groups.iterrows():
            gid = row['group_id']
            gname = row['group_name']
            admin = row['admin_username']
            
            # Styling
            is_active = (st.session_state['current_group_id'] == gid)
            active_mark = "🟣" if is_active else "⚪"
            
            # We use a container button approach
            if st.button(f"{active_mark} {gname}", key=f"nav_{gid}", use_container_width=True):
                st.session_state['current_group_id'] = gid
                st.rerun()

        st.divider()
        st.caption(f"Logged in as {user['full_name']}")
        if st.button("Log Out"):
            st.session_state['user'] = None
            st.session_state['current_group_id'] = None
            st.rerun()

    # --- MAIN CONTENT ---
    if st.session_state['current_group_id']:
        gid = st.session_state['current_group_id']
        gdata = DataManager.get_group_details(gid)
        
        if not gdata:
             st.warning("Chat not found")
             st.stop()
             
        # Header
        st.markdown(f"""
        <div class="chat-header">
            <div style="display:flex; align-items:center;">
                <div class="avatar" style="background-color: {get_avatar_color(gdata['group_name'])}; margin-right: 15px;">
                    {get_initials(gdata['group_name'])}
                </div>
                <div>
                    <div style="font-weight:600; font-size:16px;">{gdata['group_name']}</div>
                    <div style="font-size:12px; color:#6B7280;">ID: {gid} • Admin: {gdata['admin_username']}</div>
                </div>
            </div>
            <div>
                 <!-- Could put settings icon here -->
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Admin Panel
        if gdata['admin_username'] == username:
            with st.expander("⚙️ Admin Settings"):
                curr_rules = gdata.get('rules', '')
                new_rules = st.text_area("Group Rules", value=curr_rules)
                if st.button("Save Rules"):
                    DataManager.update_group_rules(gid, new_rules)
                    st.success("Updated")
                
                st.subheader("Flagged Messages")
                msgs = DataManager.load_messages(gid)
                flagged = msgs[msgs['status'] == 'FLAGGED']
                if not flagged.empty:
                    st.dataframe(flagged[['timestamp', 'username', 'message', 'reason']], hide_index=True)
                else:
                    st.info("Great! No flagged messages.")

        # Chat Area
        msgs = DataManager.load_messages(gid)
        visible = msgs[msgs['status'] == 'PASS'].sort_values('timestamp')
        
        chat_html = '<div class="chat-convo-area">'
        for _, m in visible.iterrows():
            is_me = m['username'] == username
            cls = "msg-me" if is_me else "msg-other"
            
            safe_msg = html.escape(str(m['message']))
            safe_usr = html.escape(str(m['username']))
            time_str = m['timestamp'][11:16] # HH:MM
            
            sender_div = "" if is_me else f"<div style='font-size:11px; font-weight:600; margin-bottom:2px; color:#7C3AED'>{safe_usr}</div>"
            
            chat_html += f"""
<div style="display:flex; flex-direction:column;">
<div class="msg-bubble {cls}">
{sender_div}
{safe_msg}
<div class="msg-meta">{time_str}</div>
</div>
</div>
"""
        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)
        
        # Input
        with st.form("chat_in", clear_on_submit=True):
            col_in1, col_in2 = st.columns([10, 1])
            with col_in1:
                txt = st.text_input("Type a message...", label_visibility="collapsed")
            with col_in2:
                send = st.form_submit_button("➤")
            
            if send and txt:
                with st.spinner("Analyzing..."):
                    ok, rsn = ModerationService.validate_message(txt, gid)
                if ok:
                    DataManager.save_message(gid, username, txt, "PASS")
                    st.rerun()
                else:
                    DataManager.save_message(gid, username, txt, "FLAGGED", rsn)
                    st.error(f"Blocked: {rsn}")

    else:
        # Empty State
        st.markdown("""
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:80vh; text-align:center;">
            <div style="font-size:80px; margin-bottom:20px;">👋</div>
            <h1 style="color:#7C3AED;">Welcome to ConvoEase</h1>
            <p style="color:#6B7280; max-width:400px;">
                Select a chat from the sidebar to start messaging. 
                Your conversations are secure and moderated by AI.
            </p>
        </div>
        """, unsafe_allow_html=True)

# --- Entry Point ---
if __name__ == "__main__":
    if not st.session_state['user']:
        login_view()
    else:
        main_view()
