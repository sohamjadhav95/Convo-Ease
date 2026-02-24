import random
import pandas as pd
from faker import Faker

fake = Faker()

# -----------------------------
# 1. Define 20 Rule Sets
# -----------------------------
rule_sets = {
    "education_forum": {
        "rules": [
            "General information is allowed regarding class and college.",
            "Personal messages are not allowed.",
            "Only educational and learning messages are allowed.",
            "Be respectful and kind.",
            "Advertisement and promotions are strictly prohibited."
        ]
    },
    "tech_forum": {
        "rules": [
            "Technical discussions about coding, AI, or data science are allowed.",
            "No political or religious discussions.",
            "No offensive or disrespectful language.",
            "No product promotions or marketing.",
            "Sharing learning resources is encouraged."
        ]
    },
    "career_forum": {
        "rules": [
            "Discussions about jobs, resumes, and internships are allowed.",
            "No personal or confidential data should be shared.",
            "No unrelated topics like memes or jokes.",
            "Respect all community members.",
            "No spamming or repeated posts."
        ]
    },
    "health_forum": {
        "rules": [
            "Only medical advice from certified sources is allowed.",
            "No self-promotion or product advertisements.",
            "Respect patient privacy and confidentiality.",
            "No misinformation or unverified health claims.",
            "Be supportive and empathetic."
        ]
    },
    "gaming_forum": {
        "rules": [
            "Game strategies and tips are allowed.",
            "No hacks, cheats, or exploit discussions.",
            "No bullying or toxic behavior.",
            "No advertisements or promotions.",
            "Respect all players and gaming preferences."
        ]
    },
    "research_forum": {
        "rules": [
            "Academic discussions only.",
            "Always cite sources and references.",
            "No plagiarism or copyright infringement.",
            "No personal attacks or disrespectful comments.",
            "Share knowledge constructively."
        ]
    },
    "finance_forum": {
        "rules": [
            "Investing and financial discussions are allowed.",
            "No financial scams or fraudulent schemes.",
            "No direct promotions or advertisements.",
            "Be respectful and professional.",
            "Disclaimer: Not professional financial advice."
        ]
    },
    "travel_forum": {
        "rules": [
            "Share travel experiences and recommendations.",
            "No fake promotions or misleading information.",
            "Respect cultural differences and sensitivities.",
            "No spam or repetitive posts.",
            "Be helpful and courteous."
        ]
    },
    "sports_forum": {
        "rules": [
            "Talk about matches, training, and sports news.",
            "No insults to players, teams, or fans.",
            "No unrelated spam or off-topic content.",
            "Keep discussions civil and respectful.",
            "No betting promotions or gambling links."
        ]
    },
    "art_forum": {
        "rules": [
            "Share artwork and constructive critiques.",
            "No plagiarism or stolen art.",
            "No hateful or offensive comments.",
            "Respect different artistic styles and opinions.",
            "No advertisements or self-promotion spam."
        ]
    },
    "parenting_forum": {
        "rules": [
            "Respectful parenting advice only.",
            "No medical misinformation.",
            "No product promotions or MLM schemes.",
            "Be supportive and non-judgmental.",
            "Respect different parenting approaches."
        ]
    },
    "food_forum": {
        "rules": [
            "Recipes and cooking discussions are welcome.",
            "No unrelated advertisements.",
            "Respect dietary choices and restrictions.",
            "No food shaming or negative comments.",
            "Share knowledge and experiences positively."
        ]
    },
    "startup_forum": {
        "rules": [
            "Business and entrepreneurship discussions allowed.",
            "No excessive spamming of your own startup.",
            "No irrelevant memes or off-topic content.",
            "Be constructive with feedback.",
            "No scams or pyramid schemes."
        ]
    },
    "book_forum": {
        "rules": [
            "Discuss books, reviews, and recommendations.",
            "No piracy links or illegal downloads.",
            "Be polite in disagreements.",
            "Use spoiler warnings when necessary.",
            "Respect different reading preferences."
        ]
    },
    "language_forum": {
        "rules": [
            "Only language learning discussions.",
            "No political or religious debates.",
            "No spamming or promotional content.",
            "Be patient and supportive with learners.",
            "Correct mistakes kindly and constructively."
        ]
    },
    "science_forum": {
        "rules": [
            "Science-only discussions and debates.",
            "No pseudoscience or conspiracy theories.",
            "Maintain a respectful and educational tone.",
            "Cite credible sources when making claims.",
            "Encourage curiosity and learning."
        ]
    },
    "film_forum": {
        "rules": [
            "Discuss movies, shows, and film industry.",
            "No spoilers without proper warnings.",
            "No piracy links or illegal streaming sites.",
            "No hate speech or personal attacks.",
            "Respect different tastes and opinions."
        ]
    },
    "coding_forum": {
        "rules": [
            "Share code, help others, and discuss programming.",
            "No offensive or inappropriate comments.",
            "No unrelated or off-topic content.",
            "Give credit when using others' code.",
            "Be patient with beginners."
        ]
    },
    "music_forum": {
        "rules": [
            "Share music recommendations and discussions.",
            "No piracy links or illegal downloads.",
            "No insulting artists or other members.",
            "Be kind and open to different music tastes.",
            "No spam or self-promotion without permission."
        ]
    },
    "philosophy_forum": {
        "rules": [
            "Respectful philosophical debates are encouraged.",
            "No hate speech or discriminatory comments.",
            "Stay on topic and relevant.",
            "Support arguments with reasoning.",
            "Be open-minded and considerate."
        ]
    }
}

# -----------------------------
# 2. Helper Functions
# -----------------------------
def generate_valid_message(forum_type):
    """Generate a valid message following the rules of a forum."""
    valid_templates = {
        "education_forum": [
            f"Can someone share the notes for {fake.word()} subject?",
            f"What is the timetable for {fake.word()} class?",
            f"How do I prepare for the {fake.word()} exam?",
            f"Does anyone know when the college event starts?",
            f"Can we have a study group for {fake.word()}?",
            "What are good resources for learning calculus?",
            "Is anyone attending the seminar tomorrow?"
        ],
        "tech_forum": [
            f"Can someone explain how {fake.word()} algorithm works?",
            f"Here's a Python code snippet for sorting data structures.",
            "What's the difference between supervised and unsupervised learning?",
            f"Has anyone tried using TensorFlow in production?",
            f"Check out this GitHub repo for {fake.word()} resources.",
            "How do I optimize database queries?",
            "Best practices for API development?"
        ],
        "career_forum": [
            f"Can someone review my resume for {fake.job()} role?",
            f"What are common interview questions for software engineering?",
            f"Which sites are best for finding internships?",
            f"Does anyone know about {fake.company()} hiring process?",
            "Tips for preparing for technical interviews?",
            "How to negotiate salary offers?",
            "Advice for career transitions?"
        ],
        "health_forum": [
            "What are the symptoms of vitamin D deficiency?",
            "How can I improve my sleep quality?",
            "Recommended exercises for back pain?",
            "Has anyone tried meditation for anxiety?",
            "Healthy meal prep ideas for busy schedules?",
            "When should I see a doctor for persistent headaches?",
            "Benefits of regular health checkups?"
        ],
        "gaming_forum": [
            f"Best strategy for beating level 10 in {fake.word()}?",
            "What are your favorite indie games?",
            "Tips for improving aim in FPS games?",
            "Recommended gaming keyboards under $100?",
            "How to build a team composition effectively?",
            "Discussion: Best game soundtracks of all time",
            "Looking for co-op game recommendations"
        ],
        "research_forum": [
            "Can someone recommend papers on quantum computing?",
            "What methodology is best for qualitative research?",
            "How to properly cite sources in APA format?",
            "Looking for datasets on climate change",
            "Peer review process explained?",
            "Statistical significance in experimental design",
            "Research grant application tips?"
        ],
        "finance_forum": [
            "What's a good strategy for long-term investing?",
            "How to diversify investment portfolio?",
            "Differences between 401k and Roth IRA?",
            "Tips for creating a monthly budget?",
            "Is real estate a good investment right now?",
            "Understanding compound interest",
            "How to start investing with limited capital?"
        ],
        "travel_forum": [
            f"Best time to visit {fake.city()}?",
            "Budget travel tips for Europe?",
            "Must-see attractions in Tokyo?",
            "Solo travel safety recommendations?",
            "How to find affordable accommodation?",
            "Travel insurance - is it necessary?",
            "Best travel credit cards for rewards?"
        ],
        "sports_forum": [
            "What training routine do you follow?",
            "Best moments from yesterday's match!",
            "How to improve running endurance?",
            "Discussion: Greatest athletes of all time",
            "Injury prevention tips for runners?",
            "What's your favorite sports team?",
            "Analysis of recent game tactics"
        ],
        "art_forum": [
            "Critique my latest painting please",
            "What brushes do you recommend for watercolor?",
            "How to improve perspective in drawings?",
            "Favorite art movements and why?",
            "Digital vs traditional art - your thoughts?",
            "Tips for drawing realistic portraits?",
            "Where to find art inspiration?"
        ],
        "parenting_forum": [
            "How to handle toddler tantrums?",
            "Bedtime routine suggestions?",
            "Balancing work and parenting?",
            "Age-appropriate chores for kids?",
            "Dealing with picky eaters?",
            "When to start potty training?",
            "Positive discipline strategies?"
        ],
        "food_forum": [
            "Quick dinner recipes for weeknights?",
            f"How to make perfect {fake.word()} pasta?",
            "Best way to store fresh herbs?",
            "Vegetarian protein sources?",
            "Baking tips for beginners?",
            "How to meal prep effectively?",
            "Favorite kitchen gadgets?"
        ],
        "startup_forum": [
            "How to validate a business idea?",
            "Advice on finding co-founders?",
            "Best practices for MVP development?",
            "Fundraising tips for early-stage startups?",
            "How to price your product?",
            "Marketing strategies on a tight budget?",
            "Legal considerations when starting?"
        ],
        "book_forum": [
            f"Just finished reading {fake.word()}, amazing!",
            "Book recommendations for mystery lovers?",
            "Discussion: Themes in classic literature",
            "What are you currently reading?",
            "Best science fiction novels?",
            "How to join a book club?",
            "Author recommendations similar to Tolkien?"
        ],
        "language_forum": [
            "How to improve Spanish pronunciation?",
            "Best apps for learning vocabulary?",
            "Grammar tips for beginners?",
            "How long to become fluent?",
            "Immersion vs classroom learning?",
            "Language exchange partner recommendations?",
            "Common mistakes to avoid in French?"
        ],
        "science_forum": [
            "Can someone explain quantum entanglement?",
            "Latest discoveries in astronomy?",
            "How does CRISPR technology work?",
            "Climate change evidence and data?",
            "Fascinating biology facts?",
            "Physics concepts explained simply?",
            "Scientific method in practice?"
        ],
        "film_forum": [
            "[SPOILER] Discussion about the ending",
            "Best cinematography of 2024?",
            "Underrated movies you should watch",
            "What makes a good film score?",
            "Director recommendations?",
            "Analysis of film techniques",
            "Your favorite movie quotes?"
        ],
        "coding_forum": [
            "How to implement binary search in Python?",
            "Help with debugging this JavaScript function",
            "Best practices for code documentation?",
            "How to optimize algorithm complexity?",
            "Git workflow for beginners?",
            "Recommended coding bootcamps?",
            "Understanding object-oriented programming"
        ],
        "music_forum": [
            "What genre should I explore next?",
            "Best albums released this year?",
            "How to learn music theory?",
            "Beginner-friendly instruments?",
            "Concert experiences you'll never forget",
            "How to find new artists to listen to?",
            "Production techniques for home recording"
        ],
        "philosophy_forum": [
            "What is the nature of consciousness?",
            "Discussion: Existentialism vs Nihilism",
            "How do we define morality?",
            "Thoughts on free will?",
            "Introduction to Stoic philosophy",
            "Ethics in modern technology",
            "What makes a life meaningful?"
        ]
    }
    
    return random.choice(valid_templates.get(forum_type, ["Generic valid message"]))


def generate_invalid_message(forum_type):
    """Generate an invalid message that breaks at least one rule."""
    
    # Generic violations that apply to most forums
    generic_violations = [
        f"🔥 BUY NOW! Limited offer at {fake.url()} - 50% OFF!!!",
        f"Call me personally at {fake.phone_number()} for business opportunity",
        f"Let's meet up at {fake.address()}, I'll be there at 8 PM",
        "This is absolutely stupid and you're all idiots!",
        "😂😂😂 Check out this hilarious meme (totally unrelated)",
        f"VOTE FOR {fake.name()} - Support our political movement!",
        "Spam spam spam buy this buy that click here now!!!",
        f"My religion is better than yours, convert now!",
        "You're all wrong and I'm right, deal with it losers!",
        f"GET RICH QUICK! Work from home! Contact {fake.email()}",
    ]
    
    # Forum-specific violations
    specific_violations = {
        "education_forum": [
            f"DM me at {fake.phone_number()} for homework answers $$$",
            "Let's party tonight! Who's coming to my place?",
            "Buy essay writing services - guaranteed A+ grades!",
            "Teachers are useless, just cheat on exams lol"
        ],
        "tech_forum": [
            "Republicans/Democrats ruined the tech industry!",
            "Anyone who uses Windows is an idiot",
            "Buy my course on becoming a millionaire coder!",
            "Religion should guide all programming decisions"
        ],
        "health_forum": [
            "Buy my miracle cure supplement! No FDA approval needed!",
            f"Share your medical records with me at {fake.email()}",
            "Vaccines cause autism - wake up people!",
            "Doctors are just trying to steal your money, avoid them all"
        ],
        "gaming_forum": [
            "Use this hack to get unlimited coins: [link]",
            "Mobile gamers aren't real gamers, you all suck!",
            "Buy cheap game accounts with stolen credit cards",
            "I'll boost your rank for $50, DM me"
        ],
        "research_forum": [
            "I copied this entire paper from Wikipedia without citing",
            "Your research is trash and you're incompetent",
            "Just make up data to support your hypothesis",
            "Who needs peer review? Just publish anything!"
        ],
        "finance_forum": [
            "Invest in my cryptocurrency pyramid scheme!",
            "Send me money and I'll triple it - guaranteed!",
            "This stock tip will make you rich overnight!",
            "I hacked the stock market, join my insider group"
        ],
        "travel_forum": [
            "This hotel pays me to promote them - book now!",
            "All people from [country] are terrible, avoid them",
            "Here's how to scam free hotel stays illegally",
            "Buy my travel guide full of fake information"
        ],
        "sports_forum": [
            "[Team name] fans are all idiots and losers!",
            "Bet on this game using my illegal gambling site",
            "That player should die for missing that shot",
            "spam spam spam click my betting link spam"
        ],
        "art_forum": [
            "I'm selling this art I stole from another artist",
            "Your art is garbage, you have no talent whatsoever",
            "Buy my art course MLM - recruit 5 friends!",
            "Modern art is stupid and all artists are pretentious"
        ],
        "parenting_forum": [
            "Never vaccinate your kids, trust me!",
            "Buy my essential oils to cure your child's illness",
            "Your parenting style is abusive and you're a bad parent",
            "Join my MLM for stay-at-home moms - get rich!"
        ],
        "food_forum": [
            "Buy my weight loss pills - eat whatever you want!",
            "People who eat [diet type] are stupid",
            "Check out my restaurant spam spam spam",
            "Vegans are all annoying and preachy idiots"
        ],
        "startup_forum": [
            "Join my pyramid scheme disguised as a startup!",
            "😂😂😂 Look at this cat meme (totally off-topic)",
            "spam spam investing in my startup spam spam",
            "Your business idea is worthless and will fail"
        ],
        "book_forum": [
            "Download free pirated ebooks at [illegal-site].com",
            "If you like [genre], you have terrible taste",
            "MAJOR SPOILER: Everyone dies at the end!",
            "Your book recommendation is trash and so are you"
        ],
        "language_forum": [
            "Let's discuss the upcoming election politics!",
            "My religion has the best language for prayer",
            "Buy my language course MLM spam spam spam",
            "You're pronouncing it wrong, you're hopeless"
        ],
        "science_forum": [
            "Climate change is a hoax invented by scientists",
            "The Earth is flat, wake up sheeple!",
            "Crystals heal all diseases, forget actual science",
            "All scientists are part of a global conspiracy"
        ],
        "film_forum": [
            "The hero kills the villain - haha spoiled it for you!",
            "Watch movies free at [piracy-site].com",
            "If you like Marvel movies you're a brainless idiot",
            "Anyone who disagrees with me about this film is stupid"
        ],
        "coding_forum": [
            "If you code in Python you're not a real programmer",
            "Here's malware code to hack your school's system",
            "I stole this code from GitHub without attribution",
            "Beginners should just quit, you're too dumb for this"
        ],
        "music_forum": [
            "Download pirated music from this torrent site",
            "Your music taste is awful and you should feel bad",
            "Buy my music promotion bot service spam spam",
            "[Genre] is trash music and all fans are idiots"
        ],
        "philosophy_forum": [
            "Anyone who believes [philosophy] is a moron",
            "You're all stupid for not agreeing with me",
            "Buy my philosophy course pyramid scheme!",
            "People of [group] are inherently less intelligent"
        ]
    }
    
    # Mix generic and specific violations
    violations = generic_violations + specific_violations.get(forum_type, [])
    return random.choice(violations)


# -----------------------------
# 3. Dataset Generator
# -----------------------------
def generate_dataset(n_samples=100000):
    """Generate a dataset with n_samples entries."""
    data = []
    
    for _ in range(n_samples):
        # Randomly select a forum type
        forum_type = random.choice(list(rule_sets.keys()))
        rules = rule_sets[forum_type]["rules"]
        
        # Decide if message should be valid or invalid (50/50 split)
        label = random.choice(["valid", "invalid"])
        
        if label == "valid":
            message = generate_valid_message(forum_type)
        else:
            message = generate_invalid_message(forum_type)
        
        data.append({
            "forum_type": forum_type,
            "rules": " | ".join(rules),
            "message": message,
            "label": label
        })
    
    df = pd.DataFrame(data)
    return df


# -----------------------------
# 4. Generate & Save Dataset
# -----------------------------
if __name__ == "__main__":
    print("🚀 Starting dataset generation...")
    print(f"📊 Generating 100,000 samples across {len(rule_sets)} different forum types...")
    
    dataset = generate_dataset(100000)
    
    # Save to CSV
    dataset.to_csv("multi_rule_forum_dataset.csv", index=False)
    
    print("\n✅ Dataset generated successfully!")
    print(f"📁 Saved as: multi_rule_forum_dataset.csv")
    print(f"\n📈 Dataset Statistics:")
    print(f"   Total samples: {len(dataset)}")
    print(f"   Valid messages: {len(dataset[dataset['label'] == 'valid'])}")
    print(f"   Invalid messages: {len(dataset[dataset['label'] == 'invalid'])}")
    print(f"   Number of forum types: {dataset['forum_type'].nunique()}")
    
    print(f"\n🔍 Sample distribution by forum type:")
    print(dataset['forum_type'].value_counts())
    
    print(f"\n📋 First 10 samples:")
    print(dataset.head(10).to_string())
    
    print("\n💡 Dataset is ready for training!")