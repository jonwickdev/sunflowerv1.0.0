import asyncio
import os
from sunflower.onboarding import run_onboarding
from sunflower.bot import SunflowerBot
from sunflower.config import Config

def main():
    # Check if onboarding is needed
    if not os.path.exists(".env") or not os.getenv("OPENROUTER_API_KEY") or not os.getenv("TELEGRAM_BOT_TOKEN"):
        run_onboarding()
        # Reload env vars after onboarding
        from dotenv import load_dotenv
        load_dotenv(override=True)

    try:
        bot = SunflowerBot()
        asyncio.run(bot.run())
    except ValueError as e:
        print(f"\n[Configuration Error] {e}")
    except Exception as e:
        if "Unauthorized" in str(e):
            print("\n❌ FATAL: Your Telegram Bot Token is invalid. Please check @BotFather and re-run onboarding.")
        else:
            print(f"\n[System Error] {e}")

if __name__ == "__main__":
    main()
