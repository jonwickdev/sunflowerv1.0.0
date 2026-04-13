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

async def wait_until(target_time: str, task_id: int = 0, **kwargs) -> str:
    """Calculates delay until a target time. If delay > 5 minutes, persists
    wake_up_at to the DB and defers — freeing the desk for other agents.
    The scheduler's SQL gate (wake_up_at <= now) handles the actual wake-up.

    Args:
        target_time (str): The time to wake up (HH:MM, 24h clock).
        task_id (int): The current task ID, needed to stamp wake_up_at in the DB.
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

        if delay > 300:  # More than 5 minutes -> defer, don't block
            from sunflower.hq_manager import HqManager
            hq = HqManager()
            await hq.initialize()
            # Stamp the wake_up_at so get_queued_task()'s SQL gate suppresses
            # this task until the target time. Without this, the task would be
            # immediately re-picked up, causing an infinite execution loop.
            await hq.update_task_status(task_id=task_id, status="queued", wake_up_at=target)
            print(f"[HQ WORKER] Task #{task_id} deferred until {target_time} ({delay:.0f}s). Desk freed.")
            return f"DEFERRED: Task #{task_id} sleeping until {target_time}. The scheduler will wake it."
        else:
            # Short wait (< 5 min) - hold the desk, sleep in place
            print(f"[HQ WORKER] Short wait: {delay:.0f}s until {target_time}. Holding desk.")
            await asyncio.sleep(delay)
            return f"Wake up! It is now {target_time}."
    except Exception as e:
        return f"Error parsing time: {str(e)}. Use HH:MM format."

class TimeManagementPlugin(BasePlugin):
    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "wait_until",
                "description": "Schedules the worker to resume at a specific time. Short waits (under 5 min) hold the desk; longer waits free the desk for other agents.",
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
        # Pass task_id through so wait_until can stamp wake_up_at in the DB
        return await wait_until(target_time, task_id=kwargs.get('task_id', 0))

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

class InternPlugin(BasePlugin):
    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "spawn_intern",
                "description": "Delegates a sub-task to an 'Intern'. Use this to parallelize work (e.g., scrape one site out of 50).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sub_goal": {"type": "string", "description": "The specific task for the intern."},
                        "department": {"type": "string", "description": "The department the intern belongs to (research, marketing, cto)."}
                    },
                    "required": ["sub_goal"]
                }
            }
        }

    @classmethod
    async def execute(cls, sub_goal: str = "", department: str = "general", task_id: int = 0, user_id: int = 0, **kwargs) -> str:
        from sunflower.hq_manager import HqManager
        hq = HqManager()
        await hq.initialize()
        new_id = await hq.create_task(goal=sub_goal, user_id=user_id, parent_id=task_id, department_id=department)
        return f"Intern spawned (Task #{new_id}) to handle: {sub_goal}"

class SchedulerPlugin(BasePlugin):
    @classmethod
    def get_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "schedule_recurring_task",
                "description": "Sets up a recurring mission (daily, weekly) for the future.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mission_goal": {"type": "string", "description": "The goal of the task."},
                        "frequency": {"type": "string", "enum": ["daily", "weekly", "monthly"], "description": "How often to run."},
                        "start_time": {"type": "string", "description": "When to first run (HH:MM format, 24h)."}
                    },
                    "required": ["mission_goal", "frequency", "start_time"]
                }
            }
        }

    @classmethod
    async def execute(cls, mission_goal: str = "", frequency: str = "daily", start_time: str = "", user_id: int = 0, **kwargs) -> str:
        from sunflower.hq_manager import HqManager
        import datetime
        hq = HqManager()
        await hq.initialize()
        
        now = datetime.datetime.now()
        target = datetime.datetime.strptime(start_time, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )
        if target < now:
            target += datetime.timedelta(days=1)
            
        await hq.add_schedule(user_id, mission_goal, frequency, target)
        return f"Recurring mission scheduled: '{mission_goal}' every {frequency} starting at {start_time}."
