from main import ModerationService, DataManager
import os

# Mock the API key for testing if it's not set
if "YOUR_OPENROUTER_API_KEY" in open("e:/Projects/Master Projects (Core)/Convo-Ease/Phase 3 User Application/main.py").read():
    print("WARNING: API Key not set. Verification will likely fail on API call step unless we mock the request.")

def test_backend():
    print("Testing DataManager...")
    DataManager.initialize_files()
    
    # Test User Creation
    success, msg = DataManager.register_user("testuser", "testpass", "Test User")
    print(f"User Creation: {success} - {msg}")
    
    # Test Login
    success, user_data = DataManager.validate_login("testuser", "testpass")
    print(f"Login: {success}, User Data: {user_data}")
    
    # Test Rules (Need a group first, but we can test get_group_details if we had an ID)
    # Skipping rules check as it needs a group ID and setup.
    print("Skipping rules check (requires group setup).")
    
    # Test Moderation (This will fail without real API key, so we wrap in try/except or just print intention)
    print("\nTesting Moderation Service (Requires Valid API Key)...")
    msg = "Hello everyone, hope you are learning well!"
    try:
        # We can't actually call this without a group ID either.
        print("Skipping moderation check (requires group setup).")
    except Exception as e:
        print(f"Moderation Error: {e}")

if __name__ == "__main__":
    test_backend()
