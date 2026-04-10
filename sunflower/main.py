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
        print(f"\n[Error] {e}")
    except KeyboardInterrupt:
        print("\n🌻 Sunflower is shutting down. Goodbye!")

if __name__ == "__main__":
    main()
