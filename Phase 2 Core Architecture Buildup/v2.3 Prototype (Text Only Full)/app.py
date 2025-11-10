import streamlit as st
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import json
import re
import time
from datetime import datetime

# -----------------------------------
# Page Config
# -----------------------------------
st.set_page_config(
    page_title="ConvoEase - Message Validator",
    page_icon="🛡️",
    layout="wide"
)

# -----------------------------------
# Custom CSS
# -----------------------------------
st.markdown("""
    <style>
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
    </style>
""", unsafe_allow_html=True)

# -----------------------------------
# Model Configuration
# -----------------------------------
MODEL_DIR = Path(r"C:\Project\Convo-Ease-main\Convo-Ease-main\v2.3 Prototype (Text Only Full)\gemma-2-9b-it")
MODEL_VERSION = "gemma-2-9b-it@2025-11-10"

DEFAULT_SYSTEM_PROMPT = (
    "You are a message validator. Decide if the user message aligns with the forum rules. "
    "Return STRICT JSON ONLY with EXACT keys: "
    '{"decision":"VALID"|"INVALID","reason":"<one short sentence>","violated_rules":["<rule_id_or_name>",...]} '
    "If the message is valid, violated_rules must be an empty array. Do not add extra keys or text."
)

# -----------------------------------
# Initialize Model (with caching)
# -----------------------------------
@st.cache_resource
def load_model():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR,
        device_map="auto",
        torch_dtype=torch.float16
    )
    model.eval()
    return tokenizer, model

# -----------------------------------
# Helper Functions
# -----------------------------------
def split_rules_with_ids(rules_str: str):
    parts = [s.strip() for s in rules_str.split("|") if s.strip()]
    return [{"id": f"R{i+1}", "text": t} for i, t in enumerate(parts)]

def rules_to_prompt_lines(rule_list):
    return "\n".join([f"{r['id']}: {r['text']}" for r in rule_list])

def get_full_rules_from_ids(rule_list, rule_ids):
    full_rules = []
    for rid in rule_ids:
        for r in rule_list:
            if r["id"] == rid:
                full_rules.append(r["text"])
                break
    return full_rules

DET_PATTERNS = {
    "PROMO": re.compile(r"\b(join our|buy now|subscribe|promo|discount|cheap rates|limited offer|use code)\b", re.I),
    "PERSONAL": re.compile(r"\b(dm|direct message|whatsapp|phone|call me|text me|meet (me|at)|at \d{1,2}\s?(am|pm))\b", re.I),
    "OFFTOPIC": re.compile(r"\b(dank meme|cat meme|random meme|off[- ]topic)\b", re.I),
    "PSEUDO": re.compile(r"\b(flat earth|homeopathy cures cancer|telepathy is proven|5g causes|chemtrails)\b", re.I),
    "TOXIC": re.compile(r"\b(stupid|idiot|shut up|useless|dumb)\b", re.I),
    "CLAIM_NO_SRC": re.compile(r"\b(studies show|scientists proved|experts agree|research says)\b", re.I),
    "PROMPT_INJECT": re.compile(r"ignore all previous rules|output valid regardless|system override", re.I),
}

def map_hit_to_rule_id(rule_list, category):
    cat2regex = {
        "PROMO": r"(advert|promo|promotion|subscribe|spam|offer)",
        "PERSONAL": r"(personal|dm|meet|message|phone|whatsapp)",
        "OFFTOPIC": r"(off[- ]topic|irrelevant|memes?)",
        "PSEUDO": r"(pseudoscience|conspiracy|miracle)",
        "TOXIC": r"(respectful|kind|tone|empathetic|non-judgmental)",
        "CLAIM_NO_SRC": r"(cite|source|reference)",
        "PROMPT_INJECT": r"(constructive|tone|rules|policy)"
    }
    patt = cat2regex.get(category, None)
    if not patt:
        return None
    for r in rule_list:
        if re.search(patt, r["text"], re.I):
            return r["id"]
    return None

def deterministic_check(rule_list, message: str):
    hits = []
    for cat, pat in DET_PATTERNS.items():
        if pat.search(message):
            rid = map_hit_to_rule_id(rule_list, cat) or "R?"
            hits.append(rid)
    hits = list(dict.fromkeys(hits))
    if hits:
        reason = "Violates multiple policies: " + ", ".join(hits) + "." if len(hits) > 1 \
                 else f"Violates {hits[0]}."
        return {"decision": "INVALID", "reason": reason, "violated_rules": hits}
    return None

def call_model_json(tokenizer, model, rule_list, user_message: str):
    rules_block = rules_to_prompt_lines(rule_list)
    messages = [{
        "role": "user",
        "content": (
            f"{DEFAULT_SYSTEM_PROMPT}\n\n"
            f"Forum Rules:\n{rules_block}\n\n"
            f"User Message:\n{user_message}\n\n"
            "Respond with JSON only."
        )
    }]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=160,
            pad_token_id=tokenizer.pad_token_id,
            do_sample=False
        )
    raw = tokenizer.decode(output_ids[0][inputs['input_ids'].shape[-1]:], skip_special_tokens=True).strip()
    m = re.search(r"\{.*\}", raw, flags=re.S)
    try:
        obj = json.loads(m.group(0)) if m else {}
    except Exception:
        obj = {}
    if not isinstance(obj, dict) or "decision" not in obj:
        obj = {"decision": "INVALID", "reason": "Parser fallback.", "violated_rules": []}
    obj["decision"] = "VALID" if str(obj.get("decision","")).upper() == "VALID" else "INVALID"
    if not isinstance(obj.get("violated_rules", []), list):
        obj["violated_rules"] = []
    obj["reason"] = str(obj.get("reason","")).strip()[:300]
    return obj, raw

def validate_message(tokenizer, model, rules: str, user_message: str):
    start = time.time()
    rule_list = split_rules_with_ids(rules)

    pre = deterministic_check(rule_list, user_message)
    if pre:
        decision_obj = pre
        raw = "<deterministic>"
    else:
        decision_obj, raw = call_model_json(tokenizer, model, rule_list, user_message)

    violated_rule_ids = decision_obj.get("violated_rules", [])
    violated_rule_texts = get_full_rules_from_ids(rule_list, violated_rule_ids)

    conf = 0.92 if decision_obj["decision"] == "VALID" and not violated_rule_ids else 0.82
    if decision_obj["decision"] == "INVALID":
        conf = min(0.98, 0.78 + 0.07 * max(1, len(violated_rule_ids)))

    latency_ms = int((time.time() - start) * 1000)

    return {
        "forum_type": "custom_forum",
        "rules": rule_list,
        "message": user_message,
        "decision": decision_obj["decision"],
        "reason": decision_obj["reason"],
        "violated_rules": violated_rule_texts,
        "confidence": round(conf, 2),
        "model_version": MODEL_VERSION,
        "latency_ms": latency_ms,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# -----------------------------------
# Session State Initialization
# -----------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "flagged_messages" not in st.session_state:
    st.session_state.flagged_messages = []
if "validation_history" not in st.session_state:
    st.session_state.validation_history = []
if "stats" not in st.session_state:
    st.session_state.stats = {"valid": 0, "invalid": 0, "total": 0}
if "show_notification" not in st.session_state:
    st.session_state.show_notification = False
if "notification_data" not in st.session_state:
    st.session_state.notification_data = None
if "last_rules" not in st.session_state:
    st.session_state.last_rules = ""

# -----------------------------------
# Main UI
# -----------------------------------
st.title("🛡️ ConvoEase - Message Validator")
st.markdown("**AI-powered content moderation for forums and communities**")

# Sidebar for Rules Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Model Status
    with st.spinner("Loading model..."):
        tokenizer, model = load_model()
    st.success("✅ Model loaded successfully")
    st.info(f"**Model:** {MODEL_VERSION}")
    
    st.divider()
    
    # Rules Input
    st.header("📋 Forum Rules")
    st.markdown("Enter rules separated by `|`")
    
    default_rules = """General information is allowed regarding class and college. |
Personal messages are not allowed. |
Only educational and learning-related messages are allowed. |
Be respectful and kind. |
Advertisements and promotions are strictly prohibited."""
    
    rules_input = st.text_area(
        "Rules",
        value=default_rules,
        height=200,
        help="Separate each rule with a pipe symbol (|)"
    )
    
    # Display parsed rules
    if rules_input:
        parsed_rules = split_rules_with_ids(rules_input)
        st.markdown("**Parsed Rules:**")
        rules_container = st.container()
        with rules_container:
            for rule in parsed_rules:
                st.markdown(f"- **{rule['id']}:** {rule['text']}")
    
    st.divider()
    
    # Statistics
    st.header("📊 Statistics")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Valid", st.session_state.stats["valid"], delta=None)
        st.metric("Invalid", st.session_state.stats["invalid"], delta=None)
    with col2:
        st.metric("Total", st.session_state.stats["total"], delta=None)
        if st.session_state.stats["total"] > 0:
            invalid_rate = (st.session_state.stats["invalid"] / st.session_state.stats["total"]) * 100
            st.metric("Block Rate", f"{invalid_rate:.1f}%")
    
    # Clear History Button
    if st.button("🗑️ Clear History", use_container_width=True):
        st.session_state.messages = []
        st.session_state.flagged_messages = []
        st.session_state.validation_history = []
        st.session_state.stats = {"valid": 0, "invalid": 0, "total": 0}
        st.session_state.show_notification = False
        st.session_state.notification_data = None
        st.rerun()
    
    st.divider()
    
    # Flagged Messages Section in Sidebar
    st.header("🚨 Flagged Messages")
    with st.container():
        if st.session_state.flagged_messages:
            # Show count
            st.metric("Total Flagged", len(st.session_state.flagged_messages))
            
            # Scrollable container for flagged messages
            for idx, flagged in enumerate(st.session_state.flagged_messages):
                val = flagged['validation']
                
                with st.expander(f"❌ Message #{idx+1}", expanded=False):
                    st.write(f"**Message:** {flagged['message']}")
                    st.write(f"**Reason:** {val['reason']}")
                    
                    if val['violated_rules']:
                        st.warning("**Violated Rules:**")
                        for rule in val['violated_rules']:
                            st.markdown(f"- {rule}")
                    
                    st.caption(f"⏱️ {val['timestamp']} | {val['latency_ms']}ms")
        else:
            st.info("No flagged messages yet.")
    
    st.divider()
    
    # Validation History in Sidebar
    st.header("📜 Validation History")
    with st.container():
        if st.session_state.validation_history:
            # Show recent validations
            for idx, val in enumerate(reversed(st.session_state.validation_history[-10:])):  # Show last 10
                if val['decision'] == "VALID":
                    with st.expander(f"✅ Valid - {val['timestamp']}", expanded=False):
                        st.write(f"**Message:** {val['message']}")
                        st.write(f"**Reason:** {val['reason']}")
                        st.caption(f"⏱️ {val['latency_ms']}ms")
                else:
                    with st.expander(f"❌ Invalid - {val['timestamp']}", expanded=False):
                        st.write(f"**Message:** {val['message']}")
                        st.write(f"**Reason:** {val['reason']}")
                        if val['violated_rules']:
                            st.warning("**Violated Rules:**")
                            for rule in val['violated_rules']:
                                st.markdown(f"- {rule}")
                        st.caption(f"⏱️ {val['latency_ms']}ms")
            
            if len(st.session_state.validation_history) > 10:
                st.caption(f"Showing last 10 of {len(st.session_state.validation_history)} validations")
        else:
            st.info("No validation history yet.")

# Check if rules have changed
if rules_input != st.session_state.last_rules:
    st.session_state.last_rules = rules_input
    # Clear parsed rules display by forcing rerun
    st.rerun()

# Main Chat Interface
st.header("💬 Message Validator Chat")

# Display notification for invalid messages (3 seconds)
if st.session_state.show_notification and st.session_state.notification_data:
    notif = st.session_state.notification_data
    alert_container = st.empty()
    with alert_container.container():
        st.error("🚫 **Message Flagged - Violation Detected**")
        st.write(f"**Reason:** {notif['reason']}")
        if notif['violated_rules']:
            st.warning("**Violated Rules:**")
            for rule in notif['violated_rules']:
                st.markdown(f"- {rule}")
        st.caption(f"Message moved to Flagged Messages section | Latency: {notif['latency_ms']}ms")
    
    # Clear notification after display
    time.sleep(3)
    st.session_state.show_notification = False
    st.session_state.notification_data = None
    alert_container.empty()
    st.rerun()

# Display chat history (only valid messages - clean interface)
chat_container = st.container()
with chat_container:
    for idx, msg_data in enumerate(st.session_state.messages):
        if msg_data["role"] == "user":
            with st.chat_message("user"):
                st.write(msg_data["content"])

# Chat Input
user_input = st.chat_input("Type your message here...")

if user_input:
    if not rules_input.strip():
        st.error("⚠️ Please configure forum rules in the sidebar first!")
    else:
        # Validate message
        with st.spinner("Validating message..."):
            validation_result = validate_message(tokenizer, model, rules_input, user_input)
        
        # Update statistics
        st.session_state.stats["total"] += 1
        
        if validation_result["decision"] == "VALID":
            st.session_state.stats["valid"] += 1
            
            # Add user message
            st.session_state.messages.append({
                "role": "user",
                "content": user_input
            })
            
            # Add validation result
            st.session_state.messages.append({
                "role": "assistant",
                "validation": validation_result
            })
        else:
            st.session_state.stats["invalid"] += 1
            
            # Add to flagged messages
            st.session_state.flagged_messages.append({
                "message": user_input,
                "validation": validation_result
            })
            
            # Set notification
            st.session_state.show_notification = True
            st.session_state.notification_data = validation_result
        
        # Add to history
        st.session_state.validation_history.append(validation_result)
        
        st.rerun()

# Footer
st.divider()
st.caption("Powered by Gemma-2-9B-IT | ConvoEase v2.3")