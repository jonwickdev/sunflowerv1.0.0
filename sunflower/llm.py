import asyncio
from openai import AsyncOpenAI
from sunflower.config import Config

class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.config.api_key,
        )
        # Tracking active chat tasks to allow cancellation via /stop
        self._active_tasks = {}

    async def chat(self, history: list, user_id: int = 0) -> str:
        """Core chat loop with tool-calling support. Non-blocking & cancellable."""
        # Wrap the chat logic in a cancelable task
        task = asyncio.create_task(self._run_chat_loop(history, user_id))
        self._active_tasks[user_id] = task
        
        try:
            return await task
        except asyncio.CancelledError:
            return "🛑 Mission Aborted: Chat session terminated by user."
        finally:
            self._active_tasks.pop(user_id, None)

    async def stop_chat(self, user_id: int) -> bool:
        """Force-stop the active chat turn for a user."""
        task = self._active_tasks.get(user_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def _run_chat_loop(self, history: list, user_id: int) -> str:
        from sunflower.tools import PluginManager
        import json
        MAX_HOPS = 10
        
        for hop in range(MAX_HOPS):
            tools = await PluginManager.get_all_schemas()
            
            # Non-blocking request via async client
            response = await self.client.chat.completions.create(
                model=self.config.default_model,
                messages=history,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None
            )

            # Guard: some models return null choices (e.g. after tool calls).
            # Log the model name so we can identify the culprit quickly.
            if not response or not response.choices:
                model = self.config.default_model
                print(f"[LLM Warning] Empty response from {model} on hop {hop}. Returning graceful error.")
                return (
                    f"⚠️ The AI brain (`{model}`) returned an empty response. "
                    "This usually means the model doesn't fully support tool-calling. "
                    "Try switching to a more capable model with `/models` "
                    "(e.g. `google/gemini-2.5-pro` or `anthropic/claude-3-5-sonnet`)."
                )

            msg = response.choices[0].message
            if msg.tool_calls:
                history.append(msg)
                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    try:
                        arg_str = tool_call.function.arguments.strip()
                        if arg_str.startswith("```json"): arg_str = arg_str[7:].rstrip("`").strip()
                        elif arg_str.startswith("```"): arg_str = arg_str[3:].rstrip("`").strip()
                        
                        args = json.loads(arg_str)
                        print(f"[PLUGIN] Executing: {name}")
                        result = await PluginManager.execute_tool(name, args, user_id=user_id)
                    except json.JSONDecodeError as je:
                        print(f"[LLM Error] Malformed tool arguments: {tool_call.function.arguments[:200]}")
                        result = f"Error: The AI sent malformed tool arguments. ({str(je)})"
                    except Exception as e:
                        result = f"Error: {str(e)}"
                        
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": str(result)
                    })
                continue
            else:
                return msg.content or ""
                
        return "❌ Hop limit reached. The task may be too complex for the current model. Try /delegate for long-running jobs."

    async def get_providers(self) -> list:
        """Extract unique provider names from the OpenRouter model list."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://openrouter.ai/api/v1/models") as resp:
                    resp.raise_for_status()
                    data_json = await resp.json()
                    models = data_json.get('data', [])
                    # Provider is the prefix before the /
                    providers = sorted(list(set(m['id'].split('/')[0] for m in models if '/' in m['id'])))
                    return providers
        except Exception as e:
            print(f"Error fetching providers: {e}")
            return []

    async def get_available_models(self, search_term: str = "", provider: str = "") -> list:
        """Fetch models, optionally filtered by provider/term, sorted by newest first."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://openrouter.ai/api/v1/models") as resp:
                    resp.raise_for_status()
                    data_json = await resp.json()
                    data = data_json.get('data', [])
            
            # Sort all models by 'created' descending (Newest First)
            data.sort(key=lambda x: x.get('created', 0), reverse=True)

            if provider:
                provider = provider.lower()
                data = [m for m in data if m['id'].startswith(f"{provider}/")]

            if search_term:
                search_term = search_term.lower()
                data = [m for m in data if search_term in m['id'].lower() or search_term in m.get('name', '').lower()]
            
            return data[:10] # Return top 10 for the UI
        except Exception as e:
            print(f"Error fetching models: {e}")
            return []
