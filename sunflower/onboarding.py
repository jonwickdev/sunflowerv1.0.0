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
    
    # Timezone
    print("\n🌍 Global Setup")
    timezone = input("Enter your Home Timezone (e.g., America/Chicago, Asia/Tokyo): ").strip() or "UTC"
    
    # We'll save this to a new config.json for persistency if not exists or update hq.db
    # For simplicity during onboarding, we can just print instructions or use a helper
    from sunflower.hq_manager import HqManager
    import asyncio
    
    async def save_tz():
        hq = HqManager()
        await hq.initialize()
        await hq.set_user_setting(0, "timezone", timezone) # Default user 0 for global if needed
        print(f"✅ Timezone set to {timezone}")
    
    try:
        asyncio.run(save_tz())
    except Exception:
        print("⚠️ Could not save timezone to DB yet (Bot not initialized). You can set it later with /timezone in Telegram.")

    print("\nSetup complete! Configuration saved to .env")
    print("You can now start the bot. In Telegram, open your bot and click 'Start' to begin chatting.")

if __name__ == "__main__":
    run_onboarding()
