from sunflower.tools import BasePlugin
from sunflower.browser_manager import BrowserManager
from sunflower.config import Config

class BrowserPlugin(BasePlugin):
    """
    Plugin for autonomous web browsing and task execution.
    The browser runs headlessly in the background and messages
    the user directly when the mission is complete.
    """

    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "web_agent",
                "description": (
                    "Launches a headless browser agent to perform a task on the live web "
                    "that requires interacting with a page (clicking, form filling, logging in, posting). "
                    "For pure research or information lookup, use web_search instead — it is faster. "
                    "The agent runs in the background and messages the user when done. "
                    "IMPORTANT: Call this tool ONCE, then immediately return a short confirmation "
                    "to the user. Do NOT call any more tools after this."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The natural language description of the web task to perform."
                        },
                        "profile": {
                            "type": "string",
                            "description": (
                                "Which identity profile to use. "
                                "'agent' = Sunflower's own accounts (default, use for general tasks). "
                                "'personal' = The user's personal accounts. "
                                "Other named profiles as set up by the user (e.g. 'work'). "
                                "Only specify this if the user explicitly says which profile to use."
                            )
                        }
                    },
                    "required": ["task"]
                }
            }
        }

    @classmethod
    async def execute(cls, user_id: int = 0, **kwargs) -> str:
        task = kwargs.get("task", "")
        profile = kwargs.get("profile", "agent")

        if not task:
            return "❌ No task provided to web_agent."

        config = Config()
        manager = BrowserManager(config)
        result = await manager.run_web_task(task, user_id, profile=profile)

        if "error" in result:
            return f"❌ Browser Mission Failed: {result['error']}"

        return result.get("output", "🚀 Browser mission started. You'll be messaged when complete.")
