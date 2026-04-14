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
        """Main polling loop. Queue depth and task status are the natural governors."""
        print("🏗️ High-Command Worker Pool active. Concurrency governed by queue depth.")
        await self.hq.initialize()

        while self.is_running:
            try:
                task = await self.hq.get_queued_task()
                if task:
                    # Fire and forget. A task moves off 'queued' immediately, so
                    # it cannot be double-dispatched on the next poll cycle.
                    asyncio.create_task(self.process_task(task))
                
                await asyncio.sleep(2)
            except Exception as e:
                print(f"❌ Worker Pool Error: {e}")
                await asyncio.sleep(5)

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
        
        if not os.path.exists(plan_path):
            await self.hq.log_action(task_id, f"Planning Phase Start | Dept: {dept['name']}")
            plan_content = await self.generate_plan(goal, dept)
            with open(plan_path, "w", encoding="utf-8") as f:
                f.write(plan_content)
            await self.bot.send_message(user_id, f"📋 *Task #{task_id} Plan Generated* ({dept['name']})\nDetails: `{plan_path}`\n\nStarting execution...", parse_mode="Markdown")
        else:
            await self.hq.log_action(task_id, f"Resuming Execution | Dept: {dept['name']}")
            with open(plan_path, "r", encoding="utf-8") as f:
                plan_content = f.read()

        await self.hq.update_task_status(task_id, "executing")

        # 3. Phase: Execution Loop
        server_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                past_logs = f.read()
        except FileNotFoundError:
            past_logs = "No previous steps taken."
            
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
                f"4. SERVER TIME: {server_now}. (All times are calculated relative to Server Time unless otherwise specified).\n"
                f"5. SUBMISSION: When complete, provide a final answer. The CEO will audit it for 'Slop'.\n"
                f"6. NO HALLUCINATION POLICY: You are strictly forbidden from simulating actions or faking tool output.\n\n"
                f"PAST EXECUTION LOG (Crucial string to avoid amnesia):\n{past_logs}\n"
                f"If the past execution log shows you recently woke up from a `wait_until` sleep, DO NOT sleep again! Immediately proceed with the actual task."
            )},
            {"role": "user", "content": f"Begin mission."}
        ]
        
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
                        
                        # Add task context to tools
                        args['task_id'] = task_id
                        args['user_id'] = user_id
                        
                        await self.hq.log_action(task_id, f"Invoking Tool: {name}", f"Args: {args}")
                        result = await PluginManager.execute_tool(name, args, user_id=user_id)
                        
                        # Check for special 'ask_user' signal
                        if "DEFERRED_USER_INPUT:" in str(result):
                            question = str(result).split("DEFERRED_USER_INPUT:", 1)[1].strip()
                            await self.hq.update_task_status(task_id, "blocked_on_user")
                            await self.bot.send_message(user_id, f"⚠️ *Task #{task_id} Paused!*\nAgent asks: _{question}_\n\n(Please provide the needed context or grant permission, then re-queue or restart the task)", parse_mode="Markdown")
                            return

                        # Check for special 'wait_until' signal to free desk
                        if name == "wait_until" and "DEFERRED" in str(result):
                            await self.hq.update_task_status(task_id, "queued")
                            return

                        # Update the log file (Cumulative)
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(f"\n## Step {step+1}: {name}\nArgs: {args}\nResult: {result}\n")
                        
                        history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": name,
                            "content": str(result)
                        })
                else:
                    # Final text response from the agent (The Submission)
                    final_report = msg.content
                    with open(report_path, "w", encoding="utf-8") as f:
                        f.write(f"# Department Report: {dept['name']}\nGoal: {goal}\n\n{final_report}")
                    break
                    
                if step % 5 == 0 and step > 0:
                    await self.bot.send_message(user_id, f"💓 *Task #{task_id} Heartbeat*: Step {step} complete ({dept['name']}).", parse_mode="Markdown")
            except Exception as e:
                await self.hq.log_action(task_id, f"Error at step {step}", str(e))
                await asyncio.sleep(5)

        # 4. Phase: CEO Review (The Auditor)
        from sunflower.auditor import AntiSlopAuditor
        auditor = AntiSlopAuditor(self.config, self.hq)
        passed = await auditor.review_task(task)

        if passed:
            await self.hq.update_task_status(task_id, "complete")
            await self.bot.send_message(user_id, f"Approved by CEO: Task #{task_id}\nDepartment: {dept['name']}\nReport: {report_path}")
        else:
            # Auto-redo once logic
            redo_count = task.get('redo_count', 0) or 0
            if redo_count < 1:
                await self.hq.increment_redo_count(task_id)
                await self.hq.update_task_status(task_id, "queued")
                await self.bot.send_message(user_id, f"Task #{task_id} rejected by CEO slop test. Sending back for redo #1.")
            else:
                await self.hq.update_task_status(task_id, "failed")
                await self.bot.send_message(user_id, f"Task #{task_id} failed CEO review twice. Intervene needed.")

    async def generate_plan(self, goal: str, dept: dict = None) -> str:
        """Use the LLM to generate a structured markdown plan."""
        dept_context = ""
        if dept:
            dept_context = f" You are operating as {dept['persona']} in the {dept['name']}. Follow these SOPs: {dept['sop']}"
        prompt = f"Create a multi-step plan to achieve this goal: {goal}.{dept_context} Return only the Markdown plan."
        response = self.llm.client.chat.completions.create(
            model=self.config.default_model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    def stop(self):
        self.is_running = False
