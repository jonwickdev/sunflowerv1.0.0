import os
import json
from dotenv import set_key

def run_onboarding():
    env_file = ".env"
    if not os.path.exists(env_file):
        with open(env_file, 'w') as f:
            pass # Create file

    print("\n🌻 Welcome to Sunflower Sovereign Setup 🌻")
    print("------------------------------------------")
    
    # 1. Core Secrets (.env)
    api_key = input("\n🔑 Enter your OpenRouter API Key: ").strip()
    set_key(env_file, "OPENROUTER_API_KEY", api_key)
    
    bot_token = input("🤖 Enter your Telegram Bot Token (@BotFather): ").strip()
    set_key(env_file, "TELEGRAM_BOT_TOKEN", bot_token)
    
    vps_ip = input("🌐 Enter your VPS IP Address (for Visual Rescue Link): ").strip()
    set_key(env_file, "VPS_IP", vps_ip)

    # 2. Timezone
    print("\n🌍 Regional Setup")
    timezone = input("Enter your Home Timezone (e.g., America/Chicago, Asia/Tokyo) [UTC]: ").strip() or "UTC"
    
    # 3. Sovereign Identity (config.json)
    print("\n🔐 Sovereign Identity Keyring")
    print("Sunflower can autonomously manage multiple social platforms.")
    print("Enter the platforms you want to set up (separated by commas, e.g., 'x, linkedin, reddit')")
    platforms_raw = input("Selection: ").strip().lower()
    
    from sunflower.config import Config
    config = Config()
    
    if platforms_raw:
        platforms = [p.strip() for p in platforms_raw.split(",")]
        for p in platforms:
            print(f"\n--- {p.upper()} Configuration ---")
            user = input(f"Username for {p}: ").strip()
            password = input(f"Password for {p}: ").strip()
            totp = input(f"TOTP Secret (for 2FA Autonomy) [Optional]: ").strip()
            
            # Save to the structured keyring
            config.set_path(f"browser.accounts.{p}.user", user)
            config.set_path(f"browser.accounts.{p}.pass", password)
            if totp:
                config.set_path(f"browser.accounts.{p}.totp", totp)
            print(f"✅ {p.upper()} credentials locked in the vault.")

    # 4. Finalize
    from sunflower.hq_manager import HqManager
    import asyncio
    
    async def save_tz():
        hq = HqManager()
        await hq.initialize()
        await hq.set_user_setting(0, "timezone", timezone)
        print(f"✅ Master Timezone set to {timezone}")
    
    try:
        asyncio.run(save_tz())
    except Exception:
        pass

    print("\n✨ Setup complete! Sunflower is ready for ignition.")
    print("Run './start.sh' or 'docker compose up -d' to begin.")
    print("In Telegram, type /status to verify your balance and connection.")

if __name__ == "__main__":
    run_onboarding()
