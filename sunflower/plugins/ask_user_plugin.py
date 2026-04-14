import sys
import os

# Add parent dir to path so we can import BasePlugin if running directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from sunflower.tools import BasePlugin
except ImportError:
    # Fallback if imports are weird
    class BasePlugin:
        pass

class AskUserPlugin(BasePlugin):
    """
    A plugin that allows the agent to explicitly pause its execution and ask
    the human user for permission, missing credentials, or to perform a manual task.
    """
    
    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "ask_user",
                "description": "HALT EXECUTION and ask the user a question. Use this ONLY when you lack the necessary tools, credentials, or permissions to complete a task, and you cannot proceed without user input. Do NOT simulate work.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The exact question, request for permission, or information needed from the user."
                        },
                        "reason": {
                            "type": "string",
                            "description": "Explanation of why the execution must be paused and what tool/permission is missing."
                        }
                    },
                    "required": ["question", "reason"]
                }
            }
        }

    @classmethod
    async def execute(cls, user_id: int = 0, question: str = "", reason: str = "", **kwargs) -> str:
        """
        Returns a special flag that the orchestrator will intercept to block the task.
        """
        print(f"[AskUserPlugin] Agent attempting to pause. Reason: {reason}")
        return f"DEFERRED_USER_INPUT: {question}"
