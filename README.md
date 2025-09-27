# Convo-Ease

**AI-Driven Content Moderation Chat System**

## Overview
Convo-Ease is a prototype chat application that leverages LLMs (Groq API) for real-time, rule-based content moderation. It allows users to define custom moderation rules and ensures that all chat messages comply with these rules before being accepted. Flagged messages are blocked and displayed separately for review.

## Features
- **AI-Powered Content Moderation:** Uses LLMs (Groq API) to validate messages against user-defined rules.
- **Customizable Moderation Rules:** Easily edit or select templates for chat moderation rules.
- **User-Friendly Chat Interface:** Modern UI built with Streamlit.
- **Flagged Message Handling:** Blocked messages are stored and visible for admin review.
- **Session Statistics:** View stats on valid/blocked messages and approval rates.
- **Planned Features:** Image/audio moderation, user authentication, organization management, and local model support.

## How It Works
1. **Set Up Rules:** Define or select moderation rules in the sidebar.
2. **Enter API Key:** Provide your Groq API key for LLM-based validation.
3. **Chat:** Send messages. Each message is validated in real-time.
4. **Review Flagged Messages:** Blocked messages are shown separately with reasons.

## Setup Instructions
1. **Install Dependencies:**
   - Python 3.8+
   - `streamlit`
   - `groq`
   - Install with:
     ```bash
     pip install streamlit groq
     ```
2. **Run the App:**
   ```bash
   streamlit run v1_prototype_buildup.py
   ```
3. **Open in Browser:**
   - The app will open in your default browser.

## Usage
- Enter your name and Groq API key in the sidebar.
- Choose or edit moderation rules.
- Start chatting! Messages violating rules will be blocked and shown in the "Flagged Messages" section.
- Clear chat at any time using the sidebar button.

## Configuration
- **Groq API Key:** Required for LLM validation. (Get one at [Groq API](https://console.groq.com/))
- **Model Selection:** Choose from supported models in the sidebar.

## Roadmap / Coming Soon
- 🖼️ Image moderation
- 🎵 Audio analysis
- 👥 User authentication
- 🏢 Organization management
- 🤖 Local model support

## License
Prototype for demonstration purposes only. Not for production use.

---

*Built with ❤️ using Streamlit and Groq LLMs.*