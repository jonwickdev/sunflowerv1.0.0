from sunflower.tools import BasePlugin
from sunflower.hq_manager import HqManager

class DelegationPlugin(BasePlugin):
    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "delegate_task",
                "description": "Delegates complex or long-running tasks to the background High-Command orchestrator. Use this for research, social media campaigns, coding projects, or anything that takes more than a few minutes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "goal": {"type": "string", "description": "The specific objective to achieve."},
                        "persona": {"type": "string", "description": "The type of agent to use (general, cto, researcher, marketer).", "enum": ["general", "cto", "researcher", "marketer"]}
                    },
                    "required": ["goal"]
                }
            }
        }

    @classmethod
    async def execute(cls, user_id: int = 0, goal: str = "", persona: str = "general", **kwargs) -> str:
        """Delegates a complex, long-running task to the background High-Command orchestrator."""
        hq = HqManager()
        await hq.initialize()
        
        task_id = await hq.create_task(goal, user_id=user_id, persona_id=persona)
        
        return f"🚀 Task #{task_id} successfully delegated to High-Command. The background worker is now taking over. The user has been notified."
