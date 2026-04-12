import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand

from sunflower.config import Config
from sunflower.llm import LLMClient
from sunflower.tools import PluginManager
from sunflower.mcp_manager import McpManager
from sunflower.hq_manager import HqManager
from sunflower.worker import HighCommandWorker
from sunflower.scheduler import MasterScheduler

# States for Model Selection
class ModelStates(StatesGroup):
    waiting_for_search = State()

class SunflowerBot:
    def __init__(self):
        self.config = Config()
        self.config.validate() # Ensure we have keys before starting
        
        self.bot = Bot(token=self.config.bot_token)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.llm = LLMClient(self.config)
        self.hq = HqManager()
        self.worker = HighCommandWorker(self.config, self.hq, self.bot)
        self.scheduler = MasterScheduler()
        
        self.histories = {}
        # Per-user routing configs (e.g. verbose, think mode)
        self.session_configs = {}

        # Scan the sunflower/plugins folder and dynamically load all capabilities
        PluginManager.load_plugins()

        self._register_handlers()

    def _register_handlers(self):
        self.dp.message(Command("start"))(self.cmd_start)
        self.dp.message(Command("new"))(self.cmd_new)
        self.dp.message(Command("status"))(self.cmd_status)
        self.dp.message(Command("plugins"))(self.cmd_plugins)
        self.dp.message(Command("skill"))(self.cmd_skill)
        self.dp.message(Command("tools"))(self.cmd_tools)
        self.dp.message(Command("verbose"))(self.cmd_verbose)
        self.dp.message(Command("think"))(self.cmd_think)
        self.dp.message(Command("model"))(self.cmd_model)
        self.dp.message(Command("bash"))(self.cmd_bash)
        self.dp.message(Command("mcp"))(self.cmd_mcp)
        self.dp.message(Command("tasks"))(self.cmd_tasks)
        self.dp.message(Command("delegate"))(self.cmd_delegate)
        self.dp.message(Command("timezone"))(self.cmd_timezone)
        self.dp.message(Command("schedule"))(self.cmd_schedule)
        self.dp.message(Command("review"))(self.cmd_review)
        self.dp.message(Command("restart"))(self.cmd_restart)
        self.dp.message(ModelStates.waiting_for_search)(self.process_model_search)
        self.dp.callback_query(F.data.startswith("select_model_"))(self.process_model_selection)
        self.dp.message(F.text.startswith("/"))(self.unimplemented_command)
        self.dp.message()(self.handle_message)

    async def unimplemented_command(self, message: types.Message):
        cmd = message.text.split()[0]
        await message.answer(
            f"🚧 *Command not implemented natively yet!*\n\n"
            f"The command `{cmd}` is registered in the menu, but its internal logic hasn't been built into Sunflower yet. Stay tuned!",
            parse_mode="Markdown"
        )

    async def cmd_start(self, message: types.Message):
        user_id = message.from_user.id
        if user_id not in self.histories:
            self.histories[user_id] = []
            
        await message.answer(
            "🌻 Hello! I am Sunflower. I am currently using the model: `{}`.\n\n"
            "Use /model to change my brain.\n"
            "Just type a message to chat!".format(self.config.default_model),
            parse_mode="Markdown"
        )

    async def cmd_bash(self, message: types.Message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Please provide a command to run (e.g. `/bash ls -la`)", parse_mode="Markdown")
            return
            
        cmd = parts[1]
        await message.answer(f"⚙️ Executing: `{cmd}`...", parse_mode="Markdown")
        
        result = await PluginManager.execute_tool("execute_bash", {"command": cmd})
        await message.answer(result[:4000], parse_mode="Markdown")

    async def cmd_new(self, message: types.Message):
        user_id = message.from_user.id
        self.histories[user_id] = []
        await message.answer("✨ Session reset. All previous memory has been cleared! I am ready for a new task.", parse_mode="Markdown")

    async def cmd_status(self, message: types.Message):
        user_id = message.from_user.id
        memory_turns = len(self.histories.get(user_id, [])) // 2
        model = self.config.default_model
        cfg = self.session_configs.get(user_id, {"verbose": False, "think": "off"})
        
        status_text = (
            f"📊 *Sunflower Status*\n\n"
            f"🧠 Model: `{model}`\n"
            f"💭 Think Level: `{cfg['think'].upper()}`\n"
            f"🔍 Verbose Mode: `{'ON' if cfg['verbose'] else 'OFF'}`\n"
            f"📁 Memory Used: `{memory_turns}` conversational turns"
        )
        await message.answer(status_text, parse_mode="Markdown")

    async def cmd_tools(self, message: types.Message):
        schemas = await PluginManager.get_all_schemas()
        if not schemas:
            await message.answer("No active plugins/tools loaded.")
            return
            
        text = "🛠️ *Autonomous Tools*\n\n"
        for s in schemas:
            name = s.get("function", {}).get("name", "Unknown")
            desc = s.get("function", {}).get("description", "No description")
            text += f"• `{name}`: {desc}\n\n"
        text += "The AI evaluates your questions and calls these tools silently in the background."
        await message.answer(text, parse_mode="Markdown")

    async def cmd_plugins(self, message: types.Message):
        parts = message.text.split()
        if len(parts) > 1 and parts[1].lower() == "reload":
            PluginManager.load_plugins()
            await message.answer("🔄 Plugins directory re-scanned and hot-reloaded.")
            
        schemas = await PluginManager.get_all_schemas()
        if not schemas:
            await message.answer("📁 No active plugins loaded.\nUse `/plugins reload` to rescan.", parse_mode="Markdown")
            return
            
        text = "🔌 *Active Plugins*\n\n"
        for s in schemas:
            name = s.get("function", {}).get("name", "Unknown")
            text += f"• `{name}`\n"
            
        await message.answer(text, parse_mode="Markdown")

    async def cmd_skill(self, message: types.Message):
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("Usage: `/skill <plugin_name> <json_args>`", parse_mode="Markdown")
            return
            
        name = parts[1]
        try:
            import json
            args = json.loads(parts[2])
            result = await PluginManager.execute_tool(name, args)
            await message.answer(f"⚙️ Execution Result:\n{str(result)[:3900]}", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"❌ Skill Error: {str(e)}")

    async def cmd_verbose(self, message: types.Message):
        user_id = message.from_user.id
        if user_id not in self.session_configs:
            self.session_configs[user_id] = {"verbose": False, "think": "off"}
            
        current = self.session_configs[user_id]["verbose"]
        self.session_configs[user_id]["verbose"] = not current
        new_state = "ON" if not current else "OFF"
        await message.answer(f"🔍 Verbose Mode is now *{new_state}*.", parse_mode="Markdown")

    async def cmd_think(self, message: types.Message):
        user_id = message.from_user.id
        if user_id not in self.session_configs:
            self.session_configs[user_id] = {"verbose": False, "think": "off"}
            
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("Please provide a level:\n`/think off|minimal|low|medium|high|xhigh`", parse_mode="Markdown")
            return
            
        level = parts[1].lower()
        if level not in ["off", "minimal", "low", "medium", "high", "xhigh"]:
            await message.answer("Invalid level. Choose: `off|minimal|low|medium|high|xhigh`", parse_mode="Markdown")
            return
            
        self.session_configs[user_id]["think"] = level
        await message.answer(f"💭 Thinking Level set to: *{level.upper()}*", parse_mode="Markdown")

    async def cmd_mcp(self, message: types.Message):
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            await message.answer("Usage: `/mcp show`, `/mcp set <name>=<json>`, `/mcp unset <name>`", parse_mode="Markdown")
            return
            
        action = parts[1].lower()
        if action == "show":
            config = self.config.get_mcp_config()
            import json
            await message.answer(f"🔌 *MCP Servers*\n```json\n{json.dumps(config, indent=2)}\n```", parse_mode="Markdown")
        elif action == "set":
            if len(parts) < 3 or "=" not in parts[2]:
                await message.answer("Usage: `/mcp set <name>=<json>`", parse_mode="Markdown")
                return
            kw = parts[2].split("=", 1)
            name = kw[0].strip()
            val = kw[1].strip()
            import json
            try:
                config_dict = json.loads(val)
                self.config.set_mcp_config(name, config_dict)
                await message.answer(f"✅ Saved MCP config for `{name}`. Please run `/restart` to apply.", parse_mode="Markdown")
            except json.JSONDecodeError as e:
                await message.answer(f"❌ Invalid JSON format: {str(e)}")
        elif action == "unset":
            if len(parts) < 3:
                await message.answer("Usage: `/mcp unset <name>`", parse_mode="Markdown")
                return
            name = parts[2].strip()
            if self.config.delete_mcp_config(name):
                await message.answer(f"✅ Removed MCP config for `{name}`. Please run `/restart` to apply.", parse_mode="Markdown")
            else:
                await message.answer(f"❌ MCP config `{name}` not found.", parse_mode="Markdown")

    async def cmd_restart(self, message: types.Message):
        await message.answer("🔄 Restarting bot gateway...\n*(It will be back online in a few seconds)*", parse_mode="Markdown")
        await self.dp.stop_polling()

    async def cmd_tasks(self, message: types.Message):
        user_id = message.from_user.id
        tasks = await self.hq.get_active_tasks(user_id)
        
        if not tasks:
            await message.answer("📭 No active background tasks for you.")
            return
            
        text = "📊 *Active High-Command Missions*\n\n"
        for t in tasks:
            status_emoji = "⏳" if t['status'] == 'queued' else "⚙️"
            text += f"{status_emoji} *T-{t['id']}*: {t['goal'][:50]}...\n   Status: `{t['status'].upper()}`\n\n"
        
        await message.answer(text, parse_mode="Markdown")

    async def cmd_delegate(self, message: types.Message):
        user_id = message.from_user.id
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Usage: `/delegate <major_goal>`", parse_mode="Markdown")
            return
            
        goal = parts[1]
        task_id = await self.hq.create_task(goal, user_id)
        self.scheduler.trigger_update() # Wake up scheduler to see if we should start now
        await message.answer(f"🚀 *Task #{task_id} Delegated*\nThe background High-Command worker has received your goal and will start planning shortly.", parse_mode="Markdown")

    async def cmd_timezone(self, message: types.Message):
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("🌍 *Timezone Selection*\n\nPlease specify your timezone (e.g., `America/Chicago`, `Asia/Tokyo`).\n\nUsage: `/timezone America/Chicago`", parse_mode="Markdown")
            return
        
        tz = parts[1]
        # Basic validation with pytz could be added here
        await self.hq.set_user_setting(message.from_user.id, "timezone", tz)
        await message.answer(f"✅ *Timezone Saved*: `{tz}`\nSunflower will now use this for all your scheduled tasks.", parse_mode="Markdown")

    async def cmd_schedule(self, message: types.Message):
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("📅 *Schedule a Recurring Mission*\n\nUsage: `/schedule <frequency> <goal>`\nExample: `/schedule daily Scrape 500 sites in AI niche`", parse_mode="Markdown")
            return
        
        frequency = parts[1].lower()
        goal = parts[2]
        import datetime
        # Default to 9:00 AM next day for now
        next_run = datetime.datetime.now() + datetime.timedelta(days=1)
        next_run = next_run.replace(hour=9, minute=0, second=0, microsecond=0)
        
        await self.hq.add_schedule(message.from_user.id, goal, frequency, next_run)
        self.scheduler.trigger_update()
        await message.answer(f"✅ *Recurring Mission Scheduled*\nGoal: {goal}\nFrequency: `{frequency}`\nNext run: {next_run} (Server Time)", parse_mode="Markdown")

    async def cmd_review(self, message: types.Message):
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("Usage: `/review <task_id>`")
            return
        
        task_id = int(parts[1])
        details = await self.hq.get_task_details(task_id)
        if not details:
            await message.answer("Task not found.")
            return
        
        text = f"🕵️ *CEO Audit Review: Task #{task_id}*\n"
        text += f"Goal: {details['goal']}\n"
        text += f"Quality Score: `{details.get('quality_score', 'N/A')}/10`\n"
        text += f"Feedback: {details.get('feedback', 'No feedback provided.')}\n\n"
        text += f"Report Path: `{details['report_path']}`"
        
        await message.answer(text, parse_mode="Markdown")

    async def cmd_model(self, message: types.Message, state: FSMContext):
        await state.set_state(ModelStates.waiting_for_search)
        await message.answer(
            "Please type part of the model name you are looking for (e.g., `claude`, `gpt-4`, `llama`):",
            parse_mode="Markdown"
        )

    async def process_model_search(self, message: types.Message, state: FSMContext):
        search_term = message.text
        
        # If the user typed a command instead of a search term, cancel the search
        # and let the command handlers process it on the next message
        if search_term and search_term.startswith("/"):
            await state.clear()
            await message.answer("🔄 Model search cancelled. Processing your command...")
            # Re-dispatch: manually call the right handler
            # The simplest approach is to just tell the user to re-send
            return
        
        models = await self.llm.get_available_models(search_term)
        
        if not models:
            await message.answer("No models found. Try another search term (or type /new to cancel):")
            return

        keyboard = []
        for m in models:
            model_id = m['id']
            # Truncate name if too long for button
            model_name = m.get('name', model_id)[:30] 
            keyboard.append([InlineKeyboardButton(text=model_name, callback_data=f"select_model_{model_id}")])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(f"Search results for '{search_term}':", reply_markup=reply_markup)
        await state.clear() # Exit search state once results are shown

    async def process_model_selection(self, callback: types.CallbackQuery):
        model_id = callback.data.split("select_model_")[1]
        self.config.save_default_model(model_id)
        
        # Update LLM client reference is not strictly needed if config is read on the fly, 
        # but good practice to ensure consistency if we add caching later.
        self.llm.config = self.config 

        await callback.message.edit_text(f"✅ Model changed to: `{model_id}`\n\nThis is now my default brain.", parse_mode="Markdown")
        await callback.answer()

    async def handle_message(self, message: types.Message):
        user_id = message.from_user.id
        if user_id not in self.histories:
            self.histories[user_id] = []
        if user_id not in self.session_configs:
            self.session_configs[user_id] = {"verbose": False, "think": "off"}

        user_cfg = self.session_configs[user_id]

        # Append user message
        self.histories[user_id].append({"role": "user", "content": message.text})
        
        # Build injected history for API call
        injected_history = self.histories[user_id].copy()
        if user_cfg["think"] != "off":
            think_instructions = {
                "minimal": "Take a brief moment to reason step-by-step before answering.",
                "low": "Reason clearly step-by-step in <think> tags before answering.",
                "medium": "Reason extensively step-by-step in <think> tags considering alternatives before answering.",
                "high": "Perform a massive multi-step logical deduction in <think> tags prior to answering.",
                "xhigh": "You are in maximum reasoning mode. Output exhaustive stream-of-consciousness logic in <think> tags. Do not skip any thought."
            }
            system_msg = {"role": "system", "content": think_instructions[user_cfg["think"]]}
            injected_history.insert(0, system_msg)

        if user_cfg["verbose"]:
            await message.answer("⚙️ *Verbose:* Compiling context and sending to OpenRouter...", parse_mode="Markdown")

        # Get response
        await self.bot.send_chat_action(user_id, "typing")
        response_text = await self.llm.chat(injected_history, user_id=user_id)

        # Append assistant message
        self.histories[user_id].append({"role": "assistant", "content": response_text})

        # Keep history manageable for v1 (last 10 turns)
        if len(self.histories[user_id]) > 20:
            self.histories[user_id] = self.histories[user_id][-20:]

        await message.answer(response_text)

    async def _set_bot_commands(self):
        commands = [
            BotCommand(command="start", description="Start or wake up the bot"),
            BotCommand(command="new", description="Starts a new session"),
            BotCommand(command="compact", description="Compacts the session context"),
            BotCommand(command="stop", description="Aborts the current run"),
            BotCommand(command="think", description="Sets the thinking level (off|minimal|low|medium|high|xhigh)"),
            BotCommand(command="verbose", description="Toggles verbose output"),
            BotCommand(command="fast", description="Shows or sets fast mode"),
            BotCommand(command="reasoning", description="Toggles reasoning visibility"),
            BotCommand(command="elevated", description="Toggles elevated mode"),
            BotCommand(command="exec", description="Shows or sets exec defaults"),
            BotCommand(command="model", description="Shows or sets the artificial intelligence model"),
            BotCommand(command="models", description="Lists providers or models for a provider"),
            BotCommand(command="queue", description="Manages queue behavior"),
            BotCommand(command="help", description="Shows the short help summary"),
            BotCommand(command="commands", description="Shows the generated command catalog"),
            BotCommand(command="tools", description="Shows what the current agent can use right now"),
            BotCommand(command="status", description="Shows runtime status and provider usage"),
            BotCommand(command="tasks", description="Lists active/recent background tasks"),
            BotCommand(command="delegate", description="Delegates a mission to High-Command"),
            BotCommand(command="context", description="Explains how context is assembled"),
            BotCommand(command="export", description="Exports the current session to HTML"),
            BotCommand(command="whoami", description="Shows your sender id"),
            BotCommand(command="skill", description="Runs a skill by name"),
            BotCommand(command="allowlist", description="Manages allowlist entries"),
            BotCommand(command="approve", description="Resolves exec approval prompts"),
            BotCommand(command="btw", description="Asks a side question without changing context"),
            BotCommand(command="subagents", description="Manages sub-agent runs for the current session"),
            BotCommand(command="acp", description="Manages ACP sessions and runtime options"),
            BotCommand(command="focus", description="Binds the current chat to a session target"),
            BotCommand(command="unfocus", description="Removes the current binding"),
            BotCommand(command="agents", description="Lists thread-bound agents for the current session"),
            BotCommand(command="kill", description="Aborts one or all running sub-agents"),
            BotCommand(command="steer", description="Sends steering to a running sub-agent"),
            BotCommand(command="config", description="Reads or writes system config"),
            BotCommand(command="mcp", description="Reads or writes MCP config"),
            BotCommand(command="plugins", description="Inspects or mutates plugin state"),
            BotCommand(command="debug", description="Manages runtime-only config overrides"),
            BotCommand(command="usage", description="Controls the per-response usage footer"),
            BotCommand(command="tts", description="Controls Text-to-Speech"),
            BotCommand(command="restart", description="Restarts the bot gateway"),
            BotCommand(command="timezone", description="Set your local timezone"),
            BotCommand(command="schedule", description="Schedule a recurring mission"),
            BotCommand(command="review", description="Review a mission's quality audit"),
            BotCommand(command="activation", description="Sets group activation mode"),
            BotCommand(command="send", description="Sets send policy"),
            BotCommand(command="bash", description="Runs a host shell command")
        ]
        await self.bot.set_my_commands(commands)

    async def run(self):
        print("🌻 Sunflower is starting...")
        try:
            await self.hq.initialize()
            # Start the background worker pool and the master scheduler
            asyncio.create_task(self.worker.start_loop())
            asyncio.create_task(self.scheduler.run(self.bot))
            
            await McpManager.start_all(self.config)
            await self._set_bot_commands()
            await self.dp.start_polling(self.bot)
        finally:
            self.worker.stop()
            await McpManager.close()
            await self.bot.session.close()
