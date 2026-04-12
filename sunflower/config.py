import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.config_file = "config.json"
        
        # Load core settings via the unified path engine
        self.default_model = self.get_path("default_model", "openai/gpt-3.5-turbo")
        self.browser_api_key = os.getenv("BROWSER_USE_API_KEY")

    async def get_balance(self) -> float:
        """Fetch current OpenRouter credit balance."""
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/credits",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10.0
                )
                if resp.status_code == 200 and "application/json" in resp.headers.get("content-type", ""):
                    data = resp.json().get("data", {})
                    # Balance = Purchased - Usage
                    return round(data.get("total_credits", 0) - data.get("total_usage", 0), 2)
        except Exception as e:
            print(f"[Balance Error] {str(e)}")
        return 0.0

    def _read_config(self):
        if not os.path.exists(self.config_file):
            return {}
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
            
    def _write_config(self, data):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def get_path(self, path: str, default=None):
        """Retrieve a value from a nested path like 'plugins.mcp.key'."""
        data = self._read_config()
        # Also check env for top-level keys
        if "." not in path:
            env_val = os.getenv(path.upper())
            if env_val: return env_val

        parts = path.split(".")
        for part in parts:
            if isinstance(data, dict):
                data = data.get(part)
            else:
                return default
        return data if data is not None else default

    def set_path(self, path: str, value):
        """Set a value at a nested path, creating parents if needed."""
        data = self._read_config()
        parts = path.split(".")
        curr = data
        for i, part in enumerate(parts[:-1]):
            if part not in curr or not isinstance(curr[part], dict):
                curr[part] = {}
            curr = curr[part]
        
        # Try to parse value as JSON if possible (for objects/lists)
        try:
            if isinstance(value, str) and (value.startswith("{") or value.startswith("[")):
                value = json.loads(value)
        except:
            pass
            
        curr[parts[-1]] = value
        self._write_config(data)
        
        # Sync core fields
        if path == "default_model":
            self.default_model = value

    def get_safe_config(self):
        """Returns the full config with all sensitive tokens masked."""
        data = self._read_config()
        # Inject current env vars for completeness in the view
        data["_env"] = {
            "OPENROUTER_API_KEY": self._mask(self.api_key),
            "TELEGRAM_BOT_TOKEN": self._mask(self.bot_token)
        }
        return self._recursive_mask(data)

    def _recursive_mask(self, data):
        if isinstance(data, dict):
            return {k: self._recursive_mask(v) if not self._is_secret(k) else self._mask(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._recursive_mask(i) for i in data]
        return data

    def _is_secret(self, key: str) -> bool:
        k = key.lower()
        return any(s in k for s in ["key", "token", "secret", "password", "auth", "api"])

    def _mask(self, val) -> str:
        if not val or not isinstance(val, str): return "None"
        if len(val) < 8: return "****"
        return f"{val[:4]}...{val[-4:]}"

    def save_default_model(self, model_id):
        self.set_path("default_model", model_id)

    def get_mcp_config(self):
        return self.get_path("mcp_servers", {})
        
    def set_mcp_config(self, name, config_dict):
        self.set_path(f"mcp_servers.{name}", config_dict)
        
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
