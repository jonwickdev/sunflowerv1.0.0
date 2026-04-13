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
                    "Launches a headless browser agent to perform a task on the live web. "
                    "The agent runs in the background and will message the user directly when done. "
                    "IMPORTANT: Call this tool ONCE, then immediately return a short confirmation "
                    "message to the user (e.g. 'I've started the browser mission — you'll get a "
                    "message when it's complete.'). Do NOT call any more tools after this. "
                    "There is no live browser view available over Telegram."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The natural language description of the web task to perform."
                        }
                    },
                    "required": ["task"]
                }
            }
        }

    @classmethod
    async def execute(cls, user_id: int = 0, **kwargs) -> str:
        task = kwargs.get("task", "")
        if not task:
            return "❌ No task provided to web_agent."

        config = Config()
        manager = BrowserManager(config)
        result = await manager.run_web_task(task, user_id)

        if "error" in result:
            return f"❌ Browser Mission Failed: {result['error']}"

        return result.get("output", "🚀 Browser mission started. You'll be messaged when complete.")
