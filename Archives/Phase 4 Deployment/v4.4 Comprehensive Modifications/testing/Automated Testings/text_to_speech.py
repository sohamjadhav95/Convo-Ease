import os
import pyttsx3

# Absolute output directory (use raw string for Windows paths)
OUTPUT_DIR = r"E:\Projects\Personal\Convo-Ease\Phase 4 Deployment\v4.4 Comprehensive Modifications\testing\Automated Testings\assets\audio"

# Ensure directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize engine
engine = pyttsx3.init()

# Optional tuning
engine.setProperty('rate', 180)
engine.setProperty('volume', 1.0)

# Optional: choose voice (0 = default, change if needed)
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[0].id)

# File mapping: filename → spoken text
audio_jobs = {
    "campus_exam_room_update.wav": "Please note the viva room has changed to B210 for tomorrow morning.",
    "release_status_update.wav": "The payment fix is ready and QA starts at four PM today.",
    "weekend_meetup_plan.wav": "Let’s meet at the cafe by six and leave together from there.",
    "promo_bootcamp_pitch.wav": "Buy my internship bootcamp today, huge discount for this team only.",
    "threatening_voice_note.wav": "If you come late again, I will make you regret it.",
    "medical_misinformation_forward.wav": "Stop all medicines immediately because a forwarded reel said they are dangerous."
}

# Generate all files
for filename, text in audio_jobs.items():
    output_path = os.path.join(OUTPUT_DIR, filename)
    
    engine.save_to_file(text, output_path)
    print(f"Queued: {output_path}")

# Execute all queued conversions
engine.runAndWait()

print("\n✅ All audio files generated successfully.")