from sunflower.tools import BasePlugin
from sunflower.browser_manager import BrowserManager
from sunflower.config import Config

class BrowserPlugin(BasePlugin):
    """
    Plugin for autonomous web browsing and task execution.
    Can be used for data extraction, form filling, and multi-step web research.
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
                            "description": "The natural language description of the web task (e.g. 'Go to Amazon and find the best selling laptop under $500')"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["silent", "collaborative"],
                            "default": "silent",
                            "description": "Silent for background work (headless), Collaborative for human-in-the-loop (headed/live link)"
                        }
                    },
                    "required": ["task"]
                }
            }
        }

    @classmethod
    async def execute(cls, user_id: int = 0, **kwargs) -> str:
        task = kwargs.get("task")
        mode = kwargs.get("mode", "silent")
        
        config = Config()
        manager = BrowserManager(config)
        
        # Start the task
        result = await manager.run_web_task(task, user_id, mode)
        
        if "error" in result:
            return result["error"]
            
        output = result.get("output", "Task initiated.")
        live_url = result.get("live_url")
        
        response = f"🌐 *Browser Mission Initiated*\nGoal: {task}\n\n"
        if live_url:
            response += f"🎬 *Live Interaction Link:* [Open Browser Preview]({live_url})\n"
            response += "_Note: Use this link to solve CAPTCHAs or watch progress._\n"
        
        response += f"\nResult Summary: {output}"
        return response
