"""
ConvoEase - AI-Driven Multimodal Content Moderation Chat System
Prototype Version 2.0 - Now with Image and Audio Support
"""

import streamlit as st
import json
import base64
import asyncio
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Union
import os
from groq import Groq
from dataclasses import dataclass, asdict
from enum import Enum
import io
from PIL import Image
import tempfile

# Configuration
CONFIG = {
    "APP_NAME": "ConvoEase",
    "VERSION": "2.0.0-prototype",
    "DEFAULT_TEXT_MODEL": "llama-3.1-70b-versatile",
    "DEFAULT_VISION_MODEL": "llama-3.2-11b-vision-preview",
    "DEFAULT_AUDIO_MODEL": "whisper-large-v3",
    "MAX_RULES_LENGTH": 1000,
    "MAX_MESSAGE_LENGTH": 500,
    "MAX_FILE_SIZE_MB": 25,
    "SUPPORTED_IMAGE_FORMATS": ["png", "jpg", "jpeg", "gif", "webp"],
    "SUPPORTED_AUDIO_FORMATS": ["mp3", "wav", "m4a", "ogg", "flac"],
}

# Message Types and Status
class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"

class MessageStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    PENDING = "pending"
    PROCESSING = "processing"

# Data Classes
@dataclass
class MediaContent:
    """Represents media content (image or audio)"""
    file_type: str
    file_name: str
    file_size: int
    processed_content: Optional[str] = None  # Caption for images, transcript for audio
    file_data: Optional[bytes] = None

@dataclass
class Message:
    """Represents a chat message with multimodal support"""
    id: str
    sender: str
    content: str
    timestamp: datetime
    status: MessageStatus
    message_type: MessageType
    media_content: Optional[MediaContent] = None
    reason: Optional[str] = None
    confidence: float = 1.0
    
    def to_dict(self):
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['status'] = self.status.value
        data['message_type'] = self.message_type.value
        if data['media_content'] and 'file_data' in data['media_content']:
            data['media_content']['file_data'] = None  # Don't serialize binary data
        return data

@dataclass
class ValidationResult:
    """Result from content validation"""
    is_valid: bool
    reason: str
    confidence: float = 1.0
    processed_content: Optional[str] = None

# Content Validator Class
class MultimodalContentValidator:
    """Handles message validation using multiple Groq models"""
    
    def __init__(self, api_key: str, text_model: str = CONFIG["DEFAULT_TEXT_MODEL"], 
                 vision_model: str = CONFIG["DEFAULT_VISION_MODEL"], 
                 audio_model: str = CONFIG["DEFAULT_AUDIO_MODEL"]):
        """Initialize the validator with Groq API"""
        self.client = None
        self.text_model = text_model
        self.vision_model = vision_model
        self.audio_model = audio_model
        
        if api_key:
            try:
                self.client = Groq(api_key=api_key)
            except Exception as e:
                st.error(f"Failed to initialize Groq client: {e}")
    
    async def process_image(self, image_data: bytes, image_format: str) -> str:
        """Process image using Groq vision model to generate caption"""
        if not self.client:
            return "Image uploaded (API not configured)"
        
        try:
            # Convert image to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Create the message for vision model
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Describe this image in 2-3 sentences. Focus on what you see, including any text, people, objects, or activities. Be concise and factual."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{image_format};base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.1,
                max_tokens=150
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"Failed to process image: {str(e)}"
    
    async def process_audio(self, audio_data: bytes, audio_format: str) -> str:
        """Process audio using Groq Whisper model to generate transcript"""
        if not self.client:
            return "Audio uploaded (API not configured)"
        
        try:
            # Create temporary file for audio processing
            with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_file.flush()
                
                # Transcribe audio
                with open(tmp_file.name, "rb") as audio_file:
                    response = self.client.audio.transcriptions.create(
                        file=audio_file,
                        model=self.audio_model,
                        temperature=0.1
                    )
                
                # Clean up temporary file
                os.unlink(tmp_file.name)
                
                transcript = response.text.strip()
                return transcript if transcript else "No speech detected in audio"
            
        except Exception as e:
            return f"Failed to process audio: {str(e)}"
    
    def validate_text_content(self, content: str, rules: str, content_type: str = "message") -> ValidationResult:
        """
        Validate text content against specified rules using LLM
        
        Args:
            content: The text content to validate (message, caption, or transcript)
            rules: The moderation rules
            content_type: Type of content being validated
            
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
                reason="No rules specified - all content allowed",
                confidence=1.0
            )
        
        try:
            # Construct validation prompt
            system_prompt = f"""You are a content moderation assistant. Your task is to validate {content_type} content against specific group rules.
            
Analyze the content and determine if it violates any of the provided rules.
Respond in JSON format with exactly these fields:
- "valid": boolean (true if content is acceptable, false if it violates rules)
- "reason": string (brief explanation of your decision)
- "confidence": number between 0 and 1 (how confident you are in your decision)

Be strict but fair. Consider context and intent. For image captions and audio transcripts, focus on the actual content being described or spoken."""

            user_prompt = f"""Group Rules:
{rules}

{content_type.title()} content to validate:
"{content}"

Validate this {content_type} content against the rules above."""

            # Call Groq API
            response = self.client.chat.completions.create(
                model=self.text_model,
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
class MultimodalChatManager:
    """Manages chat messages and history with multimodal support"""
    
    def __init__(self):
        """Initialize chat manager"""
        self.messages: List[Message] = []
        self.flagged_messages: List[Message] = []
        self.message_counter = 0
    
    def add_message(self, sender: str, content: str, message_type: MessageType, 
                   validation_result: ValidationResult, media_content: Optional[MediaContent] = None) -> Message:
        """
        Add a new message to the chat
        
        Args:
            sender: Name of the message sender
            content: Message content (text, caption, or transcript)
            message_type: Type of message
            validation_result: Validation result from ContentValidator
            media_content: Optional media content object
            
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
            message_type=message_type,
            media_content=media_content,
            reason=validation_result.reason,
            confidence=validation_result.confidence
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
class MultimodalUIComponents:
    """Reusable UI components for multimodal chat"""
    
    @staticmethod
    def render_message(message: Message, is_flagged: bool = False):
        """Render a single message in the chat with multimodal support"""
        
        # Color scheme
        if is_flagged:
            bg_color = "#ffebee"
            border_color = "#f44336"
            text_color = "#d32f2f"
            icon = "🚫"
        else:
            bg_color = "#e8f5e9"
            border_color = "#4caf50"
            text_color = "#2e7d32"
            icon = "✅"
        
        with st.container():
            # Message header
            st.markdown(
                f"""
                <div style="background-color: {bg_color}; padding: 10px; border-radius: 10px; margin: 5px 0; border-left: 3px solid {border_color};">
                    <strong style="color: {text_color};">{icon} {message.sender}</strong>
                    <span style="color: #757575; font-size: 0.8em;"> • {message.timestamp.strftime('%H:%M:%S')}</span>
                    <span style="color: #757575; font-size: 0.8em;"> • {message.message_type.value.title()}</span>
                """,
                unsafe_allow_html=True
            )
            
            # Message content based on type
            if message.message_type == MessageType.TEXT:
                content_style = "text-decoration: line-through;" if is_flagged else ""
                st.markdown(
                    f'<div style="color: #1b5e20; margin-top: 5px; {content_style}">{message.content}</div>',
                    unsafe_allow_html=True
                )
            
            elif message.message_type == MessageType.IMAGE:
                if not is_flagged and message.media_content and message.media_content.file_data:
                    # Show image preview
                    image = Image.open(io.BytesIO(message.media_content.file_data))
                    st.image(image, width=300, caption=f"📷 {message.media_content.file_name}")
                
                # Show caption
                content_style = "text-decoration: line-through;" if is_flagged else ""
                st.markdown(
                    f'<div style="color: #1b5e20; margin-top: 5px; {content_style}"><strong>Caption:</strong> {message.content}</div>',
                    unsafe_allow_html=True
                )
            
            elif message.message_type == MessageType.AUDIO:
                if not is_flagged and message.media_content and message.media_content.file_data:
                    # Show audio player
                    st.audio(message.media_content.file_data, format=f"audio/{message.media_content.file_type}")
                    st.caption(f"🎤 {message.media_content.file_name}")
                
                # Show transcript
                content_style = "text-decoration: line-through;" if is_flagged else ""
                st.markdown(
                    f'<div style="color: #1b5e20; margin-top: 5px; {content_style}"><strong>Transcript:</strong> {message.content}</div>',
                    unsafe_allow_html=True
                )
            
            # Show reason if flagged
            if is_flagged:
                st.markdown(
                    f'<div style="color: #d32f2f; font-size: 0.85em; margin-top: 5px;">⚠️ Blocked: {message.reason}</div>',
                    unsafe_allow_html=True
                )
            
            st.markdown("</div>", unsafe_allow_html=True)
    
    @staticmethod
    def render_rules_editor() -> str:
        """Render the rules editor in the sidebar"""
        st.sidebar.markdown("### 📋 Group Rules")
        st.sidebar.markdown("*Define moderation rules for all content types*")
        
        # Predefined rule templates
        rule_templates = {
            "Professional": "Only professional and work-related content is allowed. No personal discussions, jokes, or casual content. Images must be work-related. Audio must be professional.",
            "Educational": "Only educational content is allowed. All content must be informative, constructive, and relevant to learning. Images and audio should support educational goals.",
            "No Spam": "No spam, promotional content, or repetitive messages. No inappropriate images or audio. No links without context.",
            "Respectful": "Be respectful and courteous. No offensive language, hate speech, personal attacks, inappropriate images, or disturbing audio content.",
            "Safe Space": "Create a safe environment. No violence, adult content, disturbing imagery, offensive language, or harmful audio content.",
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
            help="Enter the rules that all messages, images, and audio must follow"
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
            help="Enter your Groq API key for multimodal content validation"
        )
        
        if api_key:
            st.session_state.api_key = api_key
        
        # Model selection
        with st.sidebar.expander("Model Settings", expanded=False):
            text_model = st.selectbox(
                "Text Model:",
                options=[
                    "llama-3.1-70b-versatile",
                    "llama-3.1-8b-instant",
                    "mixtral-8x7b-32768",
                    "gemma2-9b-it",
                    "openai/gpt-oss-120b"
                ],
                index=0
            )
            
            vision_model = st.selectbox(
                "Vision Model:",
                options=[
                    "llama-3.2-11b-vision-preview",
                    "llama-3.2-90b-vision-preview"
                ],
                index=0
            )
            
            audio_model = st.selectbox(
                "Audio Model:",
                options=[
                    "whisper-large-v3"
                ],
                index=0
            )
        
        return api_key, text_model, vision_model, audio_model
    
    @staticmethod
    def render_media_upload_buttons():
        """Render media upload buttons"""
        col1, col2, col3 = st.columns([1, 1, 4])
        
        with col1:
            uploaded_image = st.file_uploader(
                "📷",
                type=CONFIG["SUPPORTED_IMAGE_FORMATS"],
                help="Upload an image",
                label_visibility="collapsed",
                key="image_uploader"
            )
        
        with col2:
            uploaded_audio = st.file_uploader(
                "🎤",
                type=CONFIG["SUPPORTED_AUDIO_FORMATS"],
                help="Upload an audio file",
                label_visibility="collapsed",
                key="audio_uploader"
            )
        
        return uploaded_image, uploaded_audio

# Main Application
class ConvoEaseMultimodalApp:
    """Main multimodal application class"""
    
    def __init__(self):
        """Initialize the application"""
        self.setup_session_state()
        self.validator = None
    
    def setup_session_state(self):
        """Initialize session state variables"""
        if 'initialized' not in st.session_state:
            st.session_state.initialized = True
            st.session_state.chat_manager = MultimodalChatManager()
            st.session_state.rules = ""
            st.session_state.api_key = ""
            st.session_state.username = "User"
            st.session_state.processing_media = False
    
    def check_file_size(self, file) -> bool:
        """Check if file size is within limits"""
        if file.size > CONFIG["MAX_FILE_SIZE_MB"] * 1024 * 1024:
            st.error(f"File size exceeds {CONFIG['MAX_FILE_SIZE_MB']}MB limit")
            return False
        return True
    
    async def process_media_content(self, file, media_type: MessageType, rules: str) -> Tuple[bool, str, Optional[MediaContent]]:
        """Process uploaded media content"""
        if not self.check_file_size(file):
            return False, "File size exceeds limit", None
        
        # Read file data
        file_data = file.read()
        file_format = file.name.split('.')[-1].lower()
        
        # Create media content object
        media_content = MediaContent(
            file_type=file_format,
            file_name=file.name,
            file_size=len(file_data),
            file_data=file_data
        )
        
        try:
            # Process based on media type
            if media_type == MessageType.IMAGE:
                with st.spinner("🔍 Analyzing image..."):
                    processed_content = await self.validator.process_image(file_data, file_format)
            elif media_type == MessageType.AUDIO:
                with st.spinner("🎵 Transcribing audio..."):
                    processed_content = await self.validator.process_audio(file_data, file_format)
            else:
                return False, "Unsupported media type", None
            
            media_content.processed_content = processed_content
            
            # Validate processed content
            content_type = "image caption" if media_type == MessageType.IMAGE else "audio transcript"
            validation_result = self.validator.validate_text_content(
                processed_content, rules, content_type
            )
            
            return validation_result.is_valid, processed_content, media_content
            
        except Exception as e:
            return False, f"Processing error: {str(e)}", None
    
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
            .stFileUploader > label {
                font-size: 24px !important;
                text-align: center !important;
                padding: 10px !important;
            }
            .stFileUploader > div {
                text-align: center !important;
            }
            </style>
        """, unsafe_allow_html=True)
        
        # Header
        st.title(f"💬 {CONFIG['APP_NAME']}")
        st.markdown("*AI-Driven Multimodal Content Moderation Chat System*")
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
            api_key, text_model, vision_model, audio_model = MultimodalUIComponents.render_api_config()
            
            st.divider()
            
            # Rules Editor
            rules = MultimodalUIComponents.render_rules_editor()
            
            st.divider()
            
            # Flagged Messages Section
            st.markdown("### 🚫 Flagged Content")
            flagged = st.session_state.chat_manager.get_flagged_messages()
            if flagged:
                st.markdown(f"*{len(flagged)} item(s) blocked*")
                with st.expander("View blocked content", expanded=False):
                    for msg in flagged[-5:]:  # Show last 5
                        content_preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                        st.error(f"**{msg.sender}** ({msg.message_type.value}): {content_preview}")
                        st.caption(f"Reason: {msg.reason}")
            else:
                st.info("No flagged content")
            
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
                self.validator = MultimodalContentValidator(api_key, text_model, vision_model, audio_model)
            else:
                st.warning("⚠️ Please configure your Groq API key in the sidebar for content validation")
                self.validator = MultimodalContentValidator("")
            
            # Chat display
            st.markdown("### 💬 Chat Room")
            
            chat_container = st.container()
            with chat_container:
                messages = st.session_state.chat_manager.get_valid_messages()
                if messages:
                    for msg in messages:
                        MultimodalUIComponents.render_message(msg, is_flagged=False)
                else:
                    st.info("No messages yet. Start a conversation with text, images, or audio!")
            
            # Media upload area
            st.markdown("### 📎 Share Content")
            uploaded_image, uploaded_audio = MultimodalUIComponents.render_media_upload_buttons()
            
            # Process uploaded media
            if uploaded_image and not st.session_state.processing_media:
                st.session_state.processing_media = True
                is_valid, content, media_content = asyncio.run(
                    self.process_media_content(uploaded_image, MessageType.IMAGE, rules)
                )
                
                validation_result = ValidationResult(is_valid=is_valid, reason="Image processed" if is_valid else content)
                
                message = st.session_state.chat_manager.add_message(
                    sender=st.session_state.username,
                    content=content,
                    message_type=MessageType.IMAGE,
                    validation_result=validation_result,
                    media_content=media_content
                )
                
                if not is_valid:
                    st.error(f"🚫 Your image could not be delivered: {content}")
                else:
                    st.success("✅ Image shared successfully!")
                
                st.session_state.processing_media = False
                st.rerun()
            
            if uploaded_audio and not st.session_state.processing_media:
                st.session_state.processing_media = True
                is_valid, content, media_content = asyncio.run(
                    self.process_media_content(uploaded_audio, MessageType.AUDIO, rules)
                )
                
                validation_result = ValidationResult(is_valid=is_valid, reason="Audio processed" if is_valid else content)
                
                message = st.session_state.chat_manager.add_message(
                    sender=st.session_state.username,
                    content=content,
                    message_type=MessageType.AUDIO,
                    validation_result=validation_result,
                    media_content=media_content
                )
                
                if not is_valid:
                    st.error(f"🚫 Your audio message could not be delivered: {content}")
                else:
                    st.success("✅ Audio message shared successfully!")
                
                st.session_state.processing_media = False
                st.rerun()
            
            # Text message input
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
                    validation_result = self.validator.validate_text_content(message_input, rules, "message")
                    
                    # Add message to chat
                    message = st.session_state.chat_manager.add_message(
                        sender=st.session_state.username,
                        content=message_input,
                        message_type=MessageType.TEXT,
                        validation_result=validation_result
                    )
                    
                    if not validation_result.is_valid:
                        st.error(f"🚫 Your message couldn't be delivered: {validation_result.reason}")
                    else:
                        st.success("✅ Message sent successfully!")
                    
                    st.rerun()
        
        with col2:
            # Stats and info panel
            st.markdown("### 📊 Session Stats")
            
            valid_messages = st.session_state.chat_manager.get_valid_messages()
            flagged_messages = st.session_state.chat_manager.get_flagged_messages()
            
            # Count by type
            text_count = len([m for m in valid_messages if m.message_type == MessageType.TEXT])
            image_count = len([m for m in valid_messages if m.message_type == MessageType.IMAGE])
            audio_count = len([m for m in valid_messages if m.message_type == MessageType.AUDIO])
            flagged_count = len(flagged_messages)
            
            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                st.metric("💬 Text", text_count)
                st.metric("📷 Images", image_count)
            with col_stat2:
                st.metric("🎤 Audio", audio_count)
                st.metric("🚫 Blocked", flagged_count)
            
            total_count = text_count + image_count + audio_count + flagged_count
            if total_count > 0:
                approval_rate = ((text_count + image_count + audio_count) / total_count) * 100
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
            
            # Features
            st.markdown("### ✨ Supported Features")
            st.markdown("""
            **Text Messages** 📝
            - Real-time moderation
            - Custom rule validation
            
            **Images** 📷
            - AI-powered captioning
            - Visual content analysis
            - Preview & validation
            
            **Audio** 🎤
            - Speech-to-text transcription
            - Audio content moderation
            - Playback controls
            """)
            
            st.divider()
            
            # Coming Soon
            st.markdown("### 🚀 Coming Soon")
            st.markdown("""
            - 🎥 Video moderation
            - 📄 Document analysis  
            - 👥 User authentication
            - 🏢 Organization management
            - 🤖 Local model support
            - 📈 Analytics dashboard
            """)

# Run the application
if __name__ == "__main__":
    app = ConvoEaseMultimodalApp()
    app.run()