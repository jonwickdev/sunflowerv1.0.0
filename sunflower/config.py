import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.config_file = "config.json"
        self.default_model = self.load_default_model()

    def load_default_model(self):
        if not os.path.exists(self.config_file):
            return "openai/gpt-3.5-turbo" # Fallback default
        with open(self.config_file, 'r') as f:
            data = json.load(f)
            return data.get("default_model", "openai/gpt-3.5-turbo")

    def save_default_model(self, model_id):
        self.default_model = model_id
        with open(self.config_file, 'w') as f:
            json.dump({"default_model": model_id}, f, indent=4)

    def validate(self):
        missing = []
        if not self.api_key: missing.append("OPENROUTER_API_KEY")
        if not self.bot_token: missing.append("TELEGRAM_BOT_TOKEN")
        if missing:
            raise ValueError(f"Missing configuration: {', '.join(missing)}. Please run onboarding or check .env file.")
