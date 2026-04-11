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
        history = [
            {"role": "system", "content": f"You are a High-Command Agent. Your goal is: {goal}. Your current plan is in {plan_path}. You must update {log_path} and {report_path} as you work. You have full autonomous power. Do not stop until the mission is 100% complete."},
            {"role": "user", "content": f"Begin execution of the goal: {goal}"}
        ]
        
        # We manually run a loop for the worker to provide more control/logging
        MAX_STEPS = 50 
        for step in range(MAX_STEPS):
            await self.hq.log_action(task_id, f"Step {step+1} Execution")
            
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
                    result = await PluginManager.execute_tool(name, args)
                    
                    # Update the log file
                    with open(log_path, "a") as f:
                        f.write(f"\n## Step {step+1}: {name}\nArgs: {args}\nResult: {result}\n")
                    
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": str(result)
                    })
            
            # Check if the agent is done (no more tool calls and it says it's done)
            if not msg.tool_calls and ("complete" in msg.content.lower() or "mission accomplished" in msg.content.lower()):
                final_report = msg.content
                with open(report_path, "w") as f:
                    f.write(f"# Final Report - Task #{task_id}\n\n{final_report}")
                break
                
            # Periodic heartbeats to user every 5 steps
            if step % 5 == 0 and step > 0:
                await self.bot.send_message(user_id, f"💓 *Task #{task_id} Heartbeat*: Step {step} complete. Still working...", parse_mode="Markdown")

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
