from main import ModerationService, DataManager
import os

# Mock the API key for testing if it's not set
if "YOUR_OPENROUTER_API_KEY" in open("e:/Projects/Master Projects (Core)/Convo-Ease/Phase 3 User Application/main.py").read():
    print("WARNING: API Key not set. Verification will likely fail on API call step unless we mock the request.")

def test_backend():
    print("Testing DataManager...")
    DataManager.initialize_files()
    
    # Test User Creation
    success, msg = DataManager.save_user("testuser", "testpass")
    print(f"User Creation: {success} - {msg}")
    
    # Test Login
    success, role = DataManager.validate_login("testuser", "testpass")
    print(f"Login: {success}, Role: {role}")
    
    # Test Rules
    rules = DataManager.get_group_rules()
    print(f"Current Rules: {rules}")
    
    # Test Moderation (This will fail without real API key, so we wrap in try/except or just print intention)
    print("\nTesting Moderation Service (Requires Valid API Key)...")
    msg = "Hello everyone, hope you are learning well!"
    try:
        # We can't actually call this without a key.
        # But we can call it and expect an error or check if it crashes.
        # For now, let's just print that we are skipping the actual network call to avoid noise/errors if key is missing.
        print("Skipping actual network call in basic verification script.")
    except Exception as e:
        print(f"Moderation Error: {e}")

if __name__ == "__main__":
    test_backend()
