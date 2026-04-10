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
            # Maximum reasoning hops to prevent infinite tool loops
            MAX_HOPS = 7
            for hop in range(MAX_HOPS):
                response = self.client.chat.completions.create(
                    model=self.config.default_model,
                    messages=history,
                    tools=[
                        {
                            "type": "function",
                            "function": {
                                "name": "execute_bash",
                                "description": "Executes a shell command in the local environment to read files, run scripts, or check status.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "command": {
                                            "type": "string",
                                            "description": "The explicit internal bash command to execute"
                                        }
                                    },
                                    "required": ["command"]
                                }
                            }
                        }
                    ],
                    # Force model to decide whether to use tools or reply
                    tool_choice="auto"
                )
                
                msg = response.choices[0].message
                
                # If there are tool calls, intercept and execute them
                if msg.tool_calls:
                    # Append the AI's tool request to history
                    history.append(msg)
                    
                    import json
                    from sunflower.tools import ToolRegistry
                    
                    for tool_call in msg.tool_calls:
                        if tool_call.function.name == "execute_bash":
                            try:
                                args = json.loads(tool_call.function.arguments)
                                cmd = args.get("command", "")
                                print(f"[TOOL EXECUTION] {cmd}")
                                result = await ToolRegistry.execute_bash(cmd)
                            except Exception as e:
                                result = f"Error parsing tool args or executing: {str(e)}"
                                
                            # Feed the terminal result back into history
                            history.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.function.name,
                                "content": result
                            })
                    # Loop automatically continues to feed the new history back to OpenRouter
                    continue 
                else:
                    # It responded with standard text! Break loop.
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
