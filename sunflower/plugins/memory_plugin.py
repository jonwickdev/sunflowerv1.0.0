from sunflower.tools import BasePlugin
from sunflower.memory_manager import MemoryManager

class MemoryPlugin(BasePlugin):
    """
    Allows the AI CEO to autonomously commit facts, constraints, and project rules 
    to Long-Term Memory (Vector DB + Markdown).
    """

    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "remember_fact",
                "description": "Save an important user preference, fact, constraint, or business rule to Long-Term Memory so you don't forget it on the next conversation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Short 2-3 word summary of what this fact is about (e.g. 'dietary preference', 'openclaw architecture')."},
                        "content": {"type": "string", "description": "The full detailed fact/constraint to burn into memory."},
                        "category": {"type": "string", "description": "The PARA methodology category.", "enum": ["projects", "areas", "resources"]}
                    },
                    "required": ["topic", "content", "category"]
                }
            }
        }

    @classmethod
    async def execute(cls, user_id: int = 0, topic: str = "", content: str = "", category: str = "resources", **kwargs) -> str:
        manager = MemoryManager()
        return await manager.save_memory(user_id, topic, content, category)
