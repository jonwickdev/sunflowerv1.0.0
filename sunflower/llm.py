from openai import OpenAI
from sunflower.config import Config

class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.config.api_key,
        )

    async def chat(self, history: list) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.config.default_model,
                messages=history,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error communicating with OpenRouter: {str(e)}"

    async def get_available_models(self, search_term: str = "") -> list:
        import requests
        try:
            # OpenRouter public endpoint for models
            resp = requests.get("https://openrouter.ai/api/v1/models")
            resp.raise_for_status()
            data = resp.json().get('data', [])
            
            if search_term:
                search_term = search_term.lower()
                # Filter by id or name containing search term
                filtered = [m for m in data if search_term in m['id'].lower() or search_term in m.get('name', '').lower()]
                return filtered[:10] # Limit to 10 results for Telegram UI
            
            # Return top models if no search term
            return data[:5]
        except Exception as e:
            print(f"Error fetching models: {e}")
            return []
