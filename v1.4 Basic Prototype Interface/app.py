import streamlit as st
from core_processing_engine import stream_groq_response

st.title("Groq Streaming Chat Prototype")

api_key = st.text_input("Enter API Key", type="password")
system_message = st.text_area("System Message", height=100)
user_message = st.text_area("User Message", height=100)

if st.button("Send"):
    if not api_key or not system_message or not user_message:
        st.warning("Please fill in all fields.")
    else:
        st.info("Streaming response:")
        response_placeholder = st.empty()
        full_response = ""
        for chunk in stream_groq_response(api_key, system_message, user_message):
            full_response += chunk
            response_placeholder.markdown(full_response)
