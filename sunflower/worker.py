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
        # The 'Office Desks' - limits how many agents work at once
        self.semaphore = asyncio.Semaphore(config.get('max_concurrent_workers', 5))

    async def start_loop(self):
        """Main polling loop. Spawns tasks as desks become available."""
        print(f"🏗️ High-Command Worker Pool active (Max desks: {self.config.get('max_concurrent_workers', 5)})")
        await self.hq.initialize()

        while self.is_running:
            try:
                task = await self.hq.get_queued_task()
                if task:
                    # Fire and forget - the semaphore inside handled the 'desk' limit
                    asyncio.create_task(self.run_task_with_semaphore(task))
                
                await asyncio.sleep(2) # Frequent shallow poll
            except Exception as e:
                print(f"❌ Worker Pool Error: {e}")
                await asyncio.sleep(5)

    async def run_task_with_semaphore(self, task: dict):
        """Attempts to seat an agent at a desk."""
        async with self.semaphore:
            await self.process_task(task)

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
        from sunflower.departments import DEPARTMENTS
        dept = DEPARTMENTS.get(task.get('department_id', 'general'), DEPARTMENTS['general'])
        
        await self.hq.log_action(task_id, f"Planning Phase Start | Dept: {dept['name']}")
        plan_content = await self.generate_plan(goal, dept)
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan_content)
        
        await self.hq.update_task_status(task_id, "executing")
        await self.bot.send_message(user_id, f"📋 *Task #{task_id} Plan Generated* ({dept['name']})\nDetails: `{plan_path}`\n\nStarting execution...", parse_mode="Markdown")

        # 3. Phase: Execution Loop
        server_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history = [
            {"role": "system", "content": (
                f"You are an expert {dept['persona']} in the {dept['name']}.\n"
                f"SOPs for your department:\n{dept['sop']}\n\n"
                f"MISSION: {goal}\n"
                f"STRATEGY: {plan_path}\n\n"
                f"RULES:\n"
                f"1. Update {log_path} and {report_path} after EVERY tool use.\n"
                f"2. Use `wait_until` to schedule future work. This FREEES your desk for others.\n"
                f"3. Use `spawn_intern` if you need to parallelize a large mission.\n"
                f"4. SERVER TIME: {server_now}. User timezone is handled by the HQ.\n"
                f"5. SUBMISSION: When complete, provide a final answer. The CEO will audit it for 'Slop'."
            )},
            {"role": "user", "content": f"Begin mission."}
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
