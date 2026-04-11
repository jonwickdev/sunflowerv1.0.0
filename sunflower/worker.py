import asyncio
import json
import os
import datetime
from aiogram import Bot
from sunflower.config import Config
from sunflower.llm import LLMClient
from sunflower.tools import PluginManager
from sunflower.hq_manager import HqManager

class HighCommandWorker:
    def __init__(self, config: Config, hq: HqManager, bot: Bot):
        self.config = config
        self.hq = hq
        self.bot = bot
        self.llm = LLMClient(config)
        self.is_running = True

    async def start_loop(self):
        """Main polling loop for the background worker."""
        print("🏗️ High-Command Worker is active and polling for missions...")
        while self.is_running:
            try:
                task = await self.hq.get_queued_task()
                if task:
                    await self.process_task(task)
                else:
                    await asyncio.sleep(5) # Poll every 5 seconds
            except Exception as e:
                print(f"❌ Worker Loop Error: {e}")
                await asyncio.sleep(10)

    async def process_task(self, task: dict):
        """Execute a mission using the Plan-Action-Report protocol."""
        task_id = task['id']
        user_id = task['user_id']
        goal = task['goal']
        
        # 1. Setup Task Workspace
        os.makedirs(f"sunflower/hq/tasks/T-{task_id}", exist_ok=True)
        plan_path = f"sunflower/hq/tasks/T-{task_id}/plan.md"
        log_path = f"sunflower/hq/tasks/T-{task_id}/log.md"
        report_path = f"sunflower/hq/tasks/T-{task_id}/report.md"
        
        await self.hq.update_task_status(task_id, "planning", plan_path, report_path)
        await self.bot.send_message(user_id, f"🏗️ *High-Command Task #{task_id} Started*\nGoal: {goal}", parse_mode="Markdown")

        # 2. Phase: Planning
        await self.hq.log_action(task_id, "Planning Phase Start")
        plan_content = await self.generate_plan(goal)
        with open(plan_path, "w") as f:
            f.write(plan_content)
        
        await self.hq.update_task_status(task_id, "executing")
        await self.bot.send_message(user_id, f"📋 *Task #{task_id} Plan Generated*\nDetails: `{plan_path}`\n\nStarting execution...", parse_mode="Markdown")

        # 3. Phase: Execution Loop
        server_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history = [
            {"role": "system", "content": (
                f"You are a High-Command Specialist. Your mission: {goal}.\n"
                f"Your strategy is in {plan_path}.\n"
                f"RULES:\n"
                f"1. Update {log_path} and {report_path} after EVERY successful tool use.\n"
                f"2. Use the `wait_until` tool if you need to schedule a message or wait for a specific time.\n"
                f"3. Use the `send_message_to_user` tool to actually deliver messages or alerts to the boss.\n"
                f"4. NEVER use linux 'cron' or 'at' commands. They do not work in this container.\n"
                f"5. SERVER CONTEXT: The current server time is {server_now}. If the user specified a timezone (e.g. CST), calculate the offset carefully before using `wait_until`.\n"
                "6. Do not stop until the mission is 100% complete."
            )},
            {"role": "user", "content": f"Begin execution. Current goal: {goal}"}
        ]
        
        # We allow a much higher limit for High-Command (500 steps instead of chat's 7)
        MAX_STEPS = 500 
        for step in range(MAX_STEPS):
            try:
                # Use the LLM to decide the next action
                tools = await PluginManager.get_all_schemas()
                response = self.llm.client.chat.completions.create(
                    model=self.config.default_model,
                    messages=history,
                    tools=tools,
                    tool_choice="auto"
                )
                
                msg = response.choices[0].message
                history.append(msg)

                if msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        name = tool_call.function.name
                        args = json.loads(tool_call.function.arguments)
                        
                        await self.hq.log_action(task_id, f"Invoking Tool: {name}", f"Args: {args}")
                        result = await PluginManager.execute_tool(name, args, user_id=user_id)
                        
                        # Update the log file (Cumulative)
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(f"\n## Step {step+1}: {name}\nArgs: {args}\nResult: {result}\n")
                        
                        # Intermediate Save: Also update the report with current progress
                        with open(report_path, "w", encoding="utf-8") as f:
                            f.write(f"# High-Command Production Report: Task #{task_id}\n*Last Update: {datetime.datetime.now()}*\n\n## Progress Log\nCurrently at step {step+1}. The work is persisting on disk.\n\n## Current Findings\n{msg.content or 'Processing tools...'}")

                        history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": name,
                            "content": str(result)
                        })
                else:
                    # Final text response from the agent
                    final_report = msg.content
                    with open(report_path, "w", encoding="utf-8") as f:
                        f.write(f"# Final Report - Task #{task_id}\n\n{final_report}")
                    break
                    
                # Periodic heartbeats to user every 5 steps
                if step % 5 == 0 and step > 0:
                    await self.bot.send_message(user_id, f"💓 *Task #{task_id} Heartbeat*: Completed step {step}. I have {len(history)} messages of context. Still grinding...", parse_mode="Markdown")
            except Exception as e:
                await self.hq.log_action(task_id, f"Error at step {step}", str(e))
                await asyncio.sleep(5) # Brief cooldown on error

        # 4. Phase: Finalize
        await self.hq.update_task_status(task_id, "complete")
        await self.bot.send_message(user_id, f"✅ *Task #{task_id} Mission Accomplished!*\n\n{report_path}", parse_mode="Markdown")

    async def generate_plan(self, goal: str) -> str:
        """Use the LLM to generate a structured markdown plan."""
        prompt = f"Create a multi-step plan to achieve this goal: {goal}. Return only the Markdown plan."
        response = self.llm.client.chat.completions.create(
            model=self.config.default_model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    def stop(self):
        self.is_running = False
