import asyncio
import datetime
from typing import Optional
from sunflower.hq_manager import HqManager
from sunflower.config import Config

class MasterScheduler:
    """
    The 'Calendar' of the office. 
    It doesn't do the work; it just watches the clock and yells when a task is due.
    """
    def __init__(self):
        self.hq = HqManager()
        self.config = Config()
        self.interrupt_event = asyncio.Event()

    async def run(self, bot):
        print("⏰ Master Scheduler is now watching the clock...")
        await self.hq.initialize()

        while True:
            # 1. Start by checking if we have any recurring schedules that are due
            due_schedules = await self.hq.get_due_schedules()
            for schedule in due_schedules:
                print(f"📅 Schedule '{schedule['goal']}' is due! Creating task...")
                task_id = await self.hq.create_task(
                    goal=schedule['goal'],
                    user_id=schedule['user_id']
                )
                await bot.send_message(schedule['user_id'], f"🚀 *Scheduled Mission Triggered*: {schedule['goal']}\nTask ID: #{task_id}", parse_mode="Markdown")
                
                # Calculate next run time (Simple daily for now, can be expanded)
                next_run = datetime.datetime.now() + datetime.timedelta(days=1)
                if schedule['frequency'] == 'weekly':
                    next_run = datetime.datetime.now() + datetime.timedelta(weeks=1)
                
                await self.hq.update_schedule_next_run(schedule['id'], next_run)

            # 2. Check for the single most urgent task (queued or waiting to wake up)
            # We look for the smallest wait_up_at OR the oldest queued task
            # For simplicity in v4.1, we poll every 10 seconds for the 'next task' 
            # while we wait for the interrupt event.
            try:
                # We wait for 10 seconds OR until a new task is added
                await asyncio.wait_for(self.interrupt_event.wait(), timeout=10)
                self.interrupt_event.clear()
            except asyncio.TimeoutError:
                # Time's up, loop again to see if anything is due
                pass

    def trigger_update(self):
        """Called whenever a new task is added to wake the scheduler early."""
        self.interrupt_event.set()
