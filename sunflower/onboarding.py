import os
import json
import sys

def run_onboarding():
    env_file = ".env"
    config_file = "config.json"
    
    # Ensure files exist
    if not os.path.exists(env_file):
        with open(env_file, 'w') as f: f.write("")

    print("\n🌻 Sunflower Sovereign Setup (v9.0) 🌻")
    print("------------------------------------------")
    
    # 1. Host Secrets (.env)
    print("\n🔑 Step 1: Core Secrets")
    api_key = input("Enter your OpenRouter API Key: ").strip()
    bot_token = input("Enter your Telegram Bot Token (@BotFather): ").strip()
    vps_ip = input("Enter your VPS IP Address (for Visual Rescue): ").strip()

    # Save to .env
    with open(env_file, 'w') as f:
        f.write(f"OPENROUTER_API_KEY={api_key}\n")
        f.write(f"TELEGRAM_BOT_TOKEN={bot_token}\n")
        f.write(f"VPS_IP={vps_ip}\n")
    
    # 2. Regional Setup
    print("\n🌍 Step 2: Regional Setup")
    timezone = input("Enter your Home Timezone (e.g., America/Chicago) [UTC]: ").strip() or "UTC"

    # 3. Sovereign Identity (config.json)
    print("\n🔐 Step 3: Sovereign Identity Keyring")
    print("Which platforms will you automate? (e.g., 'x, linkedin, reddit')")
    platforms_raw = input("Selection: ").strip().lower()

    # Load existing config or create new
    config_data = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f: config_data = json.load(f)
        except: config_data = {}

    config_data["default_model"] = config_data.get("default_model", "openai/gpt-3.5-turbo")
    
    if platforms_raw:
        platforms = [p.strip() for p in platforms_raw.split(",")]
        if "browser" not in config_data: config_data["browser"] = {"accounts": {}}
        if "accounts" not in config_data["browser"]: config_data["browser"]["accounts"] = {}
        
        for p in platforms:
            print(f"\n--- {p.upper()} Configuration ---")
            user = input(f"Username for {p}: ").strip()
            password = input(f"Password for {p}: ").strip()
            totp = input(f"TOTP Secret (optional): ").strip()
            
            config_data["browser"]["accounts"][p] = {
                "user": user,
                "pass": password
            }
            if totp: config_data["browser"]["accounts"][p]["totp"] = totp
            print(f"✅ {p.upper()} credentials stored in config.")

    # Save to config.json
    with open(config_file, 'w') as f:
        json.dump(config_data, f, indent=4)

    print("\n✨ Setup complete! Sunflower is ready for ignition.")
    print("\n🚀 TO START:")
    print("1. docker compose up -d --build")
    print("2. Message your bot in Telegram to begin.")

if __name__ == "__main__":
    run_onboarding()
