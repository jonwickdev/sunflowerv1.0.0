from sunflower.tools import BasePlugin
from sunflower.web_agent import WebAgent
from sunflower.config import Config

class BrowserPlugin(BasePlugin):
    """
    Plugin for autonomous web browsing via raw Playwright + Vision.
    """

    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "web_agent",
                "description": (
                    "Launches a headless browser agent with vision capabilities to perform a task "
                    "on the live web that requires interacting with a page (clicking, form filling). "
                    "For pure research, use web_search instead — it is faster. "
                    "For Reddit tasks, use the specialized reddit_* tools. "
                    "IMPORTANT: This tool REQUIRES you to have vision capabilities. If you are a text-only "
                    "model, you must return an error instructing the user to switch to a vision model (like gemini-2.5-pro). "
                    "Call this tool ONCE, then immediately return a short confirmation to the user."
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
                            "description": "Identity profile to use ('agent', 'personal', etc)."
                        },
                        "platform": {
                            "type": "string",
                            "description": "The platform you are accessing (e.g. 'x', 'linkedin'). Forms the session filename."
                        }
                    },
                    "required": ["task", "platform"]
                }
            }
        }

    @classmethod
    async def execute(cls, user_id: int = 0, **kwargs) -> str:
        task = kwargs.get("task", "")
        profile = kwargs.get("profile", "agent")
        platform = kwargs.get("platform", "default")

        if not task:
            return "❌ No task provided to web_agent."

        config = Config()
        
        # We start the agent in the background so it doesn't block the LLM hop loop
        import asyncio
        asyncio.create_task(cls._run_and_report(task, profile, platform, user_id, config))
        
        return "🚀 Browser mission started in the background. Generating vision context... You will be messaged when complete."

    @classmethod
    async def _run_and_report(cls, task, profile, platform, user_id, config):
        from sunflower.bot import SunflowerBot
        agent = WebAgent(config)
        result = await agent.run(task, profile=profile, platform=platform)
        
        bot_instance = SunflowerBot.instance
        if bot_instance:
            if "error" in result:
                msg = f"❌ *Browser Mission Failed:* {result['error']}"
            else:
                msg = f"✅ *Mission Complete (Profile: {profile})*\n\n{result['output']}"
            
            await bot_instance.bot.send_message(user_id, msg, parse_mode="Markdown")
