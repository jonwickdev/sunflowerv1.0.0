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

async def wait_until(target_time: str) -> str:
    """Pauses execution until a specific time is reached (HH:MM format, 24h).
    
    Args:
        target_time (str): The time to wake up (e.g., '05:00', '14:30').
        
    Returns:
        str: Confirmation message.
    """
    import datetime
    import asyncio
    
    now = datetime.datetime.now()
    try:
        target = datetime.datetime.strptime(target_time, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )
        if target < now:
            target += datetime.timedelta(days=1)
            
        delay = (target - now).total_seconds()
        print(f"[HQ WORKER] Sleeping for {delay} seconds until {target_time}...")
        await asyncio.sleep(delay)
        return f"⏰ Wake up! It is now {target_time}."
    except Exception as e:
        return f"Error parsing time: {str(e)}. Use HH:MM format."

class TimeManagementPlugin(BasePlugin):
    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "wait_until",
                "description": "Pauses the worker until a specific time. Use this for scheduled messages, reports, or time-locked tasks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_time": {"type": "string", "description": "The time to wake up (HH:MM format, 24h clock, e.g. 05:00)."}
                    },
                    "required": ["target_time"]
                }
            }
        }

    @classmethod
    async def execute(cls, target_time: str = "", **kwargs) -> str:
        return await wait_until(target_time)

class MessengerPlugin(BasePlugin):
    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "send_message_to_user",
                "description": "Sends a message directly to the user's Telegram. Use this to report findings, send alerts, or complete a 'Wait and Message' mission.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "The message content to send."}
                    },
                    "required": ["text"]
                }
            }
        }

    @classmethod
    async def execute(cls, user_id: int = 0, text: str = "", **kwargs) -> str:
        # Since plugins are used by the worker, we need a way to access the bot instance.
        # However, for a simple implementation, we can use the bot token from Config.
        from sunflower.config import Config
        from aiogram import Bot
        config = Config()
        bot = Bot(token=config.bot_token)
        try:
            await bot.send_message(user_id, text, parse_mode="Markdown")
            await bot.session.close()
            return f"✅ Message sent to user {user_id}: {text}"
        except Exception as e:
            await bot.session.close()
            return f"❌ Failed to send message: {str(e)}"
