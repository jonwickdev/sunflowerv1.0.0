import os
from dotenv import set_key

def run_onboarding():
    env_file = ".env"
    if not os.path.exists(env_file):
        with open(env_file, 'w') as f:
            pass # Create file

    print("🌻 Welcome to Sunflower v1.0.0 Setup 🌻")
    
    # API Key
    api_key = input("Enter your OpenRouter API Key: ").strip()
    set_key(env_file, "OPENROUTER_API_KEY", api_key)
    
    # Bot Token
    bot_token = input("Enter your Telegram Bot Token (from @BotFather): ").strip()
    set_key(env_file, "TELEGRAM_BOT_TOKEN", bot_token)
    
    print("\nSetup complete! Configuration saved to .env")
    print("You can now start the bot. In Telegram, open your bot and click 'Start' to begin chatting.")

if __name__ == "__main__":
    run_onboarding()
