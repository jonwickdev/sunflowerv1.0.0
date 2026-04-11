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

    def _read_config(self):
        if not os.path.exists(self.config_file):
            return {}
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
            
    def _write_config(self, data):
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=4)

    def save_default_model(self, model_id):
        self.default_model = model_id
        data = self._read_config()
        data["default_model"] = model_id
        self._write_config(data)
        
    def get_mcp_config(self):
        data = self._read_config()
        return data.get("mcp_servers", {})
        
    def set_mcp_config(self, name, config_dict):
        data = self._read_config()
        if "mcp_servers" not in data:
            data["mcp_servers"] = {}
        data["mcp_servers"][name] = config_dict
        self._write_config(data)
        
    def delete_mcp_config(self, name):
        data = self._read_config()
        if "mcp_servers" in data and name in data["mcp_servers"]:
            del data["mcp_servers"][name]
            self._write_config(data)
            return True
        return False

    def validate(self):
        missing = []
        if not self.api_key: missing.append("OPENROUTER_API_KEY")
        if not self.bot_token: missing.append("TELEGRAM_BOT_TOKEN")
        if missing:
            raise ValueError(f"Missing configuration: {', '.join(missing)}. Please run onboarding or check .env file.")
