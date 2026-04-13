import os
import json
import sys

def run_onboarding():
    env_file = ".env"
    config_file = "config.json"

    if not os.path.exists(env_file):
        with open(env_file, 'w') as f:
            f.write("")

    # Load any existing config
    config_data = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
        except Exception:
            config_data = {}

    print("\n🌻 Sunflower Setup 🌻")
    print("───────────────────────────────────────────")

    # ── Step 1: Core Secrets ──────────────────────────────────────────────────
    print("\n🔑 Step 1: Core Secrets")
    api_key = input("OpenRouter API Key (openrouter.ai/keys): ").strip()
    bot_token = input("Telegram Bot Token (@BotFather): ").strip()
    vps_ip = input("VPS/Server IP Address (press Enter to skip): ").strip()

    with open(env_file, 'w') as f:
        f.write(f"OPENROUTER_API_KEY={api_key}\n")
        f.write(f"TELEGRAM_BOT_TOKEN={bot_token}\n")
        if vps_ip:
            f.write(f"VPS_IP={vps_ip}\n")

    # ── Step 2: Regional Setup ────────────────────────────────────────────────
    print("\n🌍 Step 2: Regional Setup")
    timezone = input("Your Timezone (e.g. America/Chicago) [UTC]: ").strip() or "UTC"
    config_data["timezone"] = timezone
    config_data["default_model"] = config_data.get("default_model", "openai/gpt-3.5-turbo")

    # ── Step 3: Agent Profile (Sunflower's Own Identity) ─────────────────────
    print("\n🤖 Step 3: Agent Profile (Recommended)")
    print("   Sunflower works best with its own social accounts.")
    print("   Create dedicated accounts for Sunflower on the platforms you want")
    print("   it to use (X/Twitter, Reddit, LinkedIn, etc.).")
    print("   It can use these for research, posting, and general tasks,")
    print("   without ever touching your personal accounts.")
    print("   (Press Enter to skip any platform — you can add these later via /connect)")
    print()

    if "profiles" not in config_data:
        config_data["profiles"] = {}
    if "agent" not in config_data["profiles"]:
        config_data["profiles"]["agent"] = {
            "display_name": "🤖 Agent Profile",
            "accounts": {}
        }

    platforms_raw = input("Which platforms should Sunflower have its own accounts on?\n(e.g. x, reddit, linkedin — comma-separated, or Enter to skip): ").strip().lower()

    if platforms_raw:
        for p in [p.strip() for p in platforms_raw.split(",") if p.strip()]:
            print(f"\n  ── {p.upper()} ──")
            user = input(f"  Username/Email for Sunflower's {p} account: ").strip()
            password = input(f"  Password: ").strip()
            totp = input(f"  TOTP Secret (optional, press Enter to skip): ").strip()

            if user and password:
                entry = {"user": user, "pass": password}
                if totp:
                    entry["totp"] = totp
                config_data["profiles"]["agent"]["accounts"][p] = entry
                print(f"  ✅ {p.upper()} saved to Agent Profile.")

    # ── Step 4: Personal Profile (Optional) ───────────────────────────────────
    print("\n👤 Step 4: Your Personal Profile (Optional)")
    print("   If you want Sunflower to act AS YOU on your personal accounts")
    print("   (e.g. grow your personal X following), connect them here.")
    print("   Skip this if you're only using the Agent Profile.")
    print()

    add_personal = input("Connect your personal accounts? (y/N): ").strip().lower()
    if add_personal == "y":
        if "personal" not in config_data["profiles"]:
            config_data["profiles"]["personal"] = {
                "display_name": "👤 My Personal Profile",
                "accounts": {}
            }

        personal_platforms = input("Which platforms? (e.g. x, reddit — comma-separated): ").strip().lower()
        if personal_platforms:
            for p in [p.strip() for p in personal_platforms.split(",") if p.strip()]:
                print(f"\n  ── Your {p.upper()} ──")
                user = input(f"  Username/Email: ").strip()
                password = input(f"  Password: ").strip()
                totp = input(f"  TOTP Secret (optional): ").strip()

                if user and password:
                    entry = {"user": user, "pass": password}
                    if totp:
                        entry["totp"] = totp
                    config_data["profiles"]["personal"]["accounts"][p] = entry
                    print(f"  ✅ {p.upper()} saved to Personal Profile.")

    # ── Save Everything ───────────────────────────────────────────────────────
    with open(config_file, 'w') as f:
        json.dump(config_data, f, indent=4)

    print("\n\n✨ Setup complete! Sunflower is ready.")
    print("\n💡 TIP: You can add more platform accounts anytime with:")
    print("   /connect <profile> reddit    — Add Reddit API tokens")
    print("\n🚀 TO START:")
    print("   docker compose up -d --build")
    print("\n📖 Full documentation: github.com/your-repo/sunflower")

if __name__ == "__main__":
    run_onboarding()
