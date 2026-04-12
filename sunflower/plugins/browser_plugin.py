from sunflower.tools import BasePlugin
from sunflower.browser_manager import BrowserManager
from sunflower.config import Config

class BrowserPlugin(BasePlugin):
    """
    Plugin for autonomous web browsing and task execution (v6.0).
    Stripped of legacy bloat for high-confidence autonomous missions.
    """
    
    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "web_agent",
                "description": "Start an autonomous browser agent to perform tasks on the live web.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The natural language description of the web task."
                        }
                    },
                    "required": ["task"]
                }
            }
        }

    @classmethod
    async def execute(cls, user_id: int = 0, **kwargs) -> str:
        task = kwargs.get("task")
        config = Config()
        manager = BrowserManager(config)
        
        result = await manager.run_web_task(task, user_id)
        
        if "error" in result:
            return f"❌ Mission Failed: {result['error']}"
            
        output = result.get("output", "Mission initiated.")
        live_url = result.get("live_url")
        
        response = f"🌐 *Sovereign Mission Engaged*\nGoal: {task}\n\n"
        response += output
        
        if live_url:
            response += f"\n\n📺 *Visual Rescue Portal*: [Open VPS Browser]({live_url})\n"
            response += "_Use this to solve CAPTCHA walls or watch the agent live._"
        
        return response
