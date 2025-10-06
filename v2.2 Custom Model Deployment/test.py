import random
from core_processing_engine import validate_message

api_key = input("Enter your Groq API key: ")

# Sample rules and messages for testing
rules = """
General information is also allowed regarding class and college. Personal Messages are not allowed. Only educational and Learning messages are allowed. Be respectful and Kind. Advertisement and promotions are strictly prohibited.
"""

# 100 sample messages (50 valid, 50 invalid for demonstration)
valid_messages = [
    "What time does the math class start?",
    "Can anyone share the notes from today's lecture?",
    "Is there a study group for computer science?",
    "Who is the professor for the chemistry course?",
    "Where can I find the syllabus for the new semester?",
    "Are there any workshops on machine learning?",
    "How do I register for the online course?",
    "What is the deadline for assignment submission?",
    "Can someone explain the last topic?",
    "Is there a library orientation this week?",
    "Are guest lectures open to all students?",
    "How do I access the college Wi-Fi?",
    "Where is the exam center located?",
    "What are the lab timings?",
    "Is attendance mandatory for all classes?",
    "Who is the class representative?",
    "How do I join the coding club?",
    "Are there any scholarships available?",
    "What is the process for getting transcripts?",
    "Can we get extra classes for difficult subjects?",
    "Is there a placement cell in the college?",
    "How do I contact the administration office?",
    "What are the rules for the hostel?",
    "Is there a canteen menu online?",
    "How do I update my contact information?",
    "Where can I find previous years' question papers?",
    "Are there any online resources for learning Python?",
    "What is the grading system?",
    "How do I apply for leave?",
    "Are there any upcoming educational events?",
    "Is there a lost and found in the college?",
    "How do I reset my college email password?",
    "What is the fee structure for the next semester?",
    "Where can I get my ID card reissued?",
    "How do I participate in the annual tech fest?",
    "Are there any rules for classroom behavior?",
    "Can I get a soft copy of the textbook?",
    "How do I submit my project online?",
    "Is there a helpline for mental health support?",
    "What are the timings for the computer lab?",
    "Are there any online quizzes this month?",
    "How do I join the alumni network?",
    "What are the library rules?",
    "Is there a dress code for college?",
    "How do I get a bonafide certificate?",
    "Are there any inter-college competitions?",
    "What is the process for exam revaluation?",
    "Can I get a concession on bus fare?",
    "How do I access the e-learning portal?",
    "What are the timings for the gym?"
]

invalid_messages = [
    "Hey, can you send me your phone number?",
    "Let's meet at the cafe after class.",
    "Check out this amazing sale on shoes!",
    "Can you promote my new YouTube channel?",
    "Buy 1 get 1 free offer at Pizza Place!",
    "I'm selling my old laptop, anyone interested?",
    "Let's plan a party this weekend!",
    "Send me your address, I'll visit.",
    "Follow me on Instagram for updates.",
    "Anyone wants to go shopping tomorrow?",
    "Share this link to win prizes!",
    "This is a sponsored message.",
    "Looking for a roommate for my apartment.",
    "Join my WhatsApp group for fun!",
    "Contact me for personal coaching.",
    "Get discounts on branded clothes!",
    "Who wants to watch a movie tonight?",
    "Let's play online games after class.",
    "I'm available for freelance work.",
    "Check out my latest blog post!",
    "Anyone up for a road trip?",
    "DM me for more details.",
    "Special offer: Free trial for 1 month!",
    "Subscribe to my channel for more.",
    "Looking for a date for prom night.",
    "Promote your business here!",
    "Send gifts to your friends.",
    "Let's hang out this weekend.",
    "Contact me for party invites.",
    "Check my profile for updates.",
    "I'm organizing a private event.",
    "Share your contact details please.",
    "Want to join my private group?",
    "I'm selling concert tickets.",
    "Let's go for a drive.",
    "Share this post with friends.",
    "Looking for someone to chill with.",
    "Anyone wants to join my startup?",
    "Buy now and save big!",
    "Get your free samples today.",
    "Let's meet outside college.",
    "Who wants to party tonight?",
    "Send me your location.",
    "Contact for paid promotions.",
    "Join the fun at my place!",
    "Special price for students only!",
    "DM for collaboration.",
    "Promotional offer ends soon!",
    "Let's celebrate together!"
]

# Combine and shuffle messages
test_data = [(msg, "VALID") for msg in valid_messages] + [(msg, "INVALID") for msg in invalid_messages]
random.shuffle(test_data)

def test_accuracy():
    correct = 0
    total = len(test_data)
    for msg, expected in test_data:
        print(f"\nTesting message: {msg}")
        result = validate_message(api_key, rules, msg)
        if result == msg and expected == "VALID":
            correct += 1
        elif result != msg and expected == "INVALID":
            correct += 1
    accuracy = (correct / total) * 100
    print(f"\nAccuracy: {accuracy:.2f}% ({correct}/{total} correct)")

if __name__ == "__main__":
    test_accuracy()


'''
GPT-OSS-120B
Accuracy: 92.93% (92/99 correct)

GPT-OSS-20B
Accuracy: 93.94% (93/99 correct)

Gemma2-9b-it
Accuracy: 94.95% (94/99 correct)
'''