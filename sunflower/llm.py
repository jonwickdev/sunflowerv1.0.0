from openai import OpenAI
from sunflower.config import Config

class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.config.api_key,
        )

    async def chat(self, history: list, user_id: int = 0) -> str:
        try:
            from sunflower.tools import PluginManager
            
            MAX_HOPS = 7
            for hop in range(MAX_HOPS):
                tools = await PluginManager.get_all_schemas()
                
                if tools:
                    response = self.client.chat.completions.create(
                        model=self.config.default_model,
                        messages=history,
                        tools=tools,
                        tool_choice="auto"
                    )
                else:
                    response = self.client.chat.completions.create(
                        model=self.config.default_model,
                        messages=history
                    )
                
                msg = response.choices[0].message
                
                if msg.tool_calls:
                    history.append(msg)
                    import json
                    from sunflower.tools import PluginManager
                    
                    for tool_call in msg.tool_calls:
                        name = tool_call.function.name
                        try:
                            args = json.loads(tool_call.function.arguments)
                            print(f"[PLUGIN EXECUTION] AI invoked {name}")
                            result = await PluginManager.execute_tool(name, args, user_id=user_id)
                        except Exception as e:
                            result = f"Error parsing tool args or executing: {str(e)}"
                            
                        history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.function.name,
                            "content": result
                        })
                    continue 
                else:
                    return msg.content
                    
            return "❌ Agent reached the maximum tool loop limit (7 hops) without returning a final text answer."
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
