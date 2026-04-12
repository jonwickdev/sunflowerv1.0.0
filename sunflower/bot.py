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
    waiting_for_provider_models = State()

class SunflowerBot:
    instance = None # Global access for background tasks

    def __init__(self):
        SunflowerBot.instance = self
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
        self.dp.message(Command("models"))(self.cmd_models)
        self.dp.callback_query(F.data.startswith("provider_"))(self.process_provider_selection)
        self.dp.message(Command("config"))(self.cmd_config)
        self.dp.message(Command("help"))(self.cmd_help)
        self.dp.message(Command("commands"))(self.cmd_commands)
        self.dp.message(Command("whoami"))(self.cmd_whoami)
        self.dp.message(Command("stop"))(self.cmd_stop)
        self.dp.message(Command("compact"))(self.cmd_compact)
        self.dp.message(Command("restart"))(self.cmd_restart)
        
        # FSM and Callbacks
        self.dp.callback_query(F.data.startswith("select_model_"))(self.process_model_selection)
        
        # Fallback for all other messages
        self.dp.message()(self.handle_message)

    async def cmd_start(self, message: types.Message):
        user_id = message.from_user.id
        if user_id not in self.histories:
            self.histories[user_id] = []
            
        await message.answer(
            f"Sunflower is active. Using model: {self.config.default_model}\n\n"
            "Use /model to change brain.\n"
            "Just type a message to chat!"
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
        balance = await self.config.get_balance()
        
        status_text = (
            "🌻 *Sunflower System Status*\n\n"
            f"🧠 *Brain:* `{model}`\n"
            f"💰 *Balance:* `${balance}`\n"
            f"💭 *Think:* `{cfg['think'].upper()}`\n"
            f"📢 *Verbose:* `{'ON' if cfg['verbose'] else 'OFF'}`\n"
            f"📚 *Context:* `{memory_turns} turns`"
        )
        await message.answer(status_text, parse_mode="Markdown")
        await message.answer(status_text)

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
        await message.answer(f"Verbose Mode is now {new_state}.")

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
        await message.answer(f"Thinking Level set to: {level.upper()}")

    async def cmd_config(self, message: types.Message):
        """Administrative configuration manager."""
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            await message.answer("Usage: `/config show`, `/config get <path>`, `/config set <path>=<value>`", parse_mode="Markdown")
            return
            
        action = parts[1].lower()
        if action == "show":
            conf = self.config.get_safe_config()
            import json
            await message.answer(f"⚙️ *Current Configuration (Masked)*\n```json\n{json.dumps(conf, indent=2)}\n```", parse_mode="Markdown")
        elif action == "get":
            if len(parts) < 3:
                await message.answer("Usage: `/config get <path>`")
                return
            path = parts[2]
            val = self.config.get_path(path)
            # Mask if secret
            if self.config._is_secret(path):
                val = self.config._mask(val)
            await message.answer(f"Value for `{path}`: `{val}`", parse_mode="Markdown")
        elif action == "set":
            raw = parts[2]
            if "=" in raw:
                path, val = raw.split("=", 1)
            elif " " in raw:
                path, val = raw.split(" ", 1)
            else:
                await message.answer("Usage: `/config set <path>=<value>` or `/config set <path> <value>`", parse_mode="Markdown")
                return
            
            path, val = path.strip(), val.strip()
            self.config.set_path(path, val)
            # Mask the reporting if it's a secret
            display_val = self.config._mask(val) if self.config._is_secret(path) else val
            await message.answer(f"✅ Set `{path}` to `{display_val}`. Admin Tip: Run `/restart` to apply any deep engine changes.")

    async def cmd_restart(self, message: types.Message):
        """Restarts the bot gateway."""
        await message.answer("🔄 Rebooting Sunflower Engine...\n*(I will be back online in ~10 seconds)*")
        # Exit the process. The Docker 'restart: always' policy will handle the rest.
        import os
        os._exit(0)

    async def cmd_help(self, message: types.Message):
        """Sunflower Manifesto"""
        help_text = (
            "🌻 SUNFLOWER GLOBAL HQ\n"
            "The world is noisy; Sunflower is focused.\n\n"
            "I am your high-performance autonomous ecosystem. I don't just chat; I plan, delegate, and execute.\n\n"
            "QUICK START:\n"
            "• Just talk to me to brainstorm.\n"
            "• Use /delegate to start a background mission.\n"
            "• Use /status to check my health.\n"
            "• Use /commands to see my full power.\n\n"
            "Built for speed. Optimized for results."
        )
        await message.answer(help_text)

    async def cmd_commands(self, message: types.Message):
        """Shows the generated command catalog."""
        cmds = [
            "/start - Wake up the bot",
            "/new - Reset current session history",
            "/status - Check model and system health",
            "/models - Browse and pick AI brains",
            "/config - Manage HQ settings",
            "/plugins - List/Reload plugins",
            "/mcp - Manage MCP servers",
            "/bash - Run host shell command",
            "/delegate - Start background mission",
            "/tasks - List background tasks",
            "/stop - Abort active AI response",
            "/compact - Archive current context",
            "/help - Sunflower Manifesto",
            "/whoami - Show your user identity",
            "/restart - Reboot the bot gateway"
        ]
        await message.answer("Available Slash Commands:\n\n" + "\n".join(cmds))

    async def cmd_mcp(self, message: types.Message):
        """Dedicated MCP server manager."""
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
            name, val = parts[2].split("=", 1)
            try:
                import json
                obj = json.loads(val)
                self.config.set_mcp_config(name.strip(), obj)
                await message.answer(f"✅ Saved MCP config for `{name}`. Run `/restart` to apply.", parse_mode="Markdown")
            except Exception as e:
                await message.answer(f"❌ Invalid JSON or config error: {str(e)}")
        elif action == "unset":
            if len(parts) < 3:
                await message.answer("Usage: `/mcp unset <name>`", parse_mode="Markdown")
                return
            if self.config.delete_mcp_config(parts[2].strip()):
                await message.answer(f"✅ Removed MCP server. Run `/restart` to apply.")
            else:
                await message.answer("❌ Server not found.")

    async def cmd_whoami(self, message: types.Message):
        """Simple identification check."""
        await message.answer(f"Your Telegram ID: {message.from_user.id}")

    async def cmd_stop(self, message: types.Message):
        """Abort the active chat generation."""
        stopped = await self.llm.stop_chat(message.from_user.id)
        if stopped:
            await message.answer("🛑 Chat generation cancelled.")
        else:
            await message.answer("No active chat turn to stop.")

    async def cmd_compact(self, message: types.Message):
        """Summarize and archive chat context."""
        user_id = message.from_user.id
        history = self.histories.get(user_id, [])
        if not history:
            await message.answer("History is already empty. Nothing to compact.")
            return

        await message.answer("📦 Compacting session... generating summary anchor.")
        
        # 1. Generate Summary
        prompt = "Summarize the key decisions and topics from this conversation into several bullet points for a context.md file. Be concise."
        compaction_history = history + [{"role": "user", "content": prompt}]
        summary = await self.llm.chat(compaction_history, user_id=user_id)
        
        # 2. Write to context.md
        import os
        from datetime import datetime
        context_path = "sunflower/hq/context.md"
        os.makedirs(os.path.dirname(context_path), exist_ok=True)
        
        with open(context_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n### {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(summary)
            
        # 3. Clear History
        self.histories[user_id] = []
        await message.answer(f"✅ Context anchored to {context_path}. Session history cleared to prevent bleed.")

    async def cmd_tasks(self, message: types.Message):
        """Lists active background tasks."""
        try:
            tasks = await self.hq.get_active_tasks(message.from_user.id)
            if not tasks:
                await message.answer("No active background tasks.")
                return
            
            lines = ["Current Sunflower Missions:"]
            for t in tasks:
                icon = "⏳" if t['status'] == 'queued' else "⚙️"
                lines.append(f"{icon} Task #{t['id']}: {t['goal'][:60]}... (Status: {t['status'].upper()})")
            
            await message.answer("\n\n".join(lines))
        except Exception as e:
            await message.answer(f"System Error (tasks): {str(e)}")

    async def cmd_delegate(self, message: types.Message):
        """Hands a goal to the High-Command department."""
        try:
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                await message.answer("Usage: /delegate <your goal>")
                return
                
            task_id = await self.hq.create_task(parts[1], message.from_user.id)
            self.scheduler.trigger_update()
            await message.answer(f"Task #{task_id} successfully delegated to High-Command. The worker pool will start planning shortly.")
        except Exception as e:
            await message.answer(f"System Error (delegate): {str(e)}")

    async def cmd_timezone(self, message: types.Message):
        """Sets the user's home timezone for scheduling."""
        try:
            parts = message.text.split()
            if len(parts) < 2:
                await message.answer("Usage: /timezone America/Chicago")
                return
            
            tz = parts[1]
            await self.hq.set_user_setting(message.from_user.id, "timezone", tz)
            await message.answer(f"Timezone locked: {tz}")
        except Exception as e:
            await message.answer(f"System Error (timezone): {str(e)}")

    async def cmd_schedule(self, message: types.Message):
        """Schedules a recurring mission."""
        try:
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                await message.answer("Usage: /schedule <daily|weekly> <goal>")
                return
            
            freq, goal = parts[1].lower(), parts[2]
            import datetime
            # Default to 9 AM local time tomorrow
            run_at = datetime.datetime.now() + datetime.timedelta(days=1)
            run_at = run_at.replace(hour=9, minute=0, second=0, microsecond=0)
            
            await self.hq.add_schedule(message.from_user.id, goal, freq, run_at)
            self.scheduler.trigger_update()
            await message.answer(f"Mission scheduled: '{goal}' every {freq}. Next run scheduled (Server Time): {run_at}")
        except Exception as e:
            await message.answer(f"System Error (schedule): {str(e)}")

    async def cmd_review(self, message: types.Message):
        """Retrieves CEO Audit results for a specific task."""
        try:
            parts = message.text.split()
            if len(parts) < 2:
                await message.answer("Usage: /review <task_id>")
                return
            
            task_id = int(parts[1])
            t = await self.hq.get_task_details(task_id)
            if not t:
                await message.answer("Task ID not found.")
                return
            
            score = t.get('quality_score', 'Pending')
            fb = t.get('feedback', 'No feedback recorded.')
            report = t.get('report_path', 'No report generated.')
            
            resp = [
                f"CEO Audit for Task #{task_id}",
                f"Goal: {t['goal']}",
                f"Quality Score: {score}/10",
                f"CEO Feedback: {fb}",
                f"Report Location: {report}"
            ]
            await message.answer("\n\n".join(resp))
        except Exception as e:
            await message.answer(f"System Error (review): {str(e)}")

    async def cmd_models(self, message: types.Message):
        """Interactive model browser. Usage: /model [search]"""
        # Check if user provided an immediate search
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            term = parts[1].strip()
            models = await self.llm.get_available_models(search_term=term)
            await self._show_models_list(message, models, f"Search results for '{term}':")
            return

        providers = await self.llm.get_providers()
        if not providers:
            await message.answer("Unable to fetch provider list from OpenRouter.")
            return

        keyboard = []
        # Group providers into rows of 2 for better UX
        for i in range(0, len(providers), 2):
            row = [InlineKeyboardButton(text=p.capitalize(), callback_data=f"provider_{p}") for p in providers[i:i+2]]
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer("🌐 *Select a Provider*\n(Newest models first) or use `/model <search>`", reply_markup=reply_markup, parse_mode="Markdown")

    # Alias for both variants
    cmd_model = cmd_models

    async def process_provider_selection(self, callback: types.CallbackQuery):
        provider = callback.data.split("provider_")[1]
        models = await self.llm.get_available_models(provider=provider)
        await self._show_models_list(callback.message, models, f"Newest models from {provider.capitalize()}:")
        await callback.answer()

    async def _show_models_list(self, message, models, title):
        if not models:
            await message.answer("No active models found for this selection.")
            return

        keyboard = []
        for m in models:
            mid = m['id']
            name = m.get('name', mid)[:30]
            keyboard.append([InlineKeyboardButton(text=f"🧠 {name}", callback_data=f"select_model_{mid}")])
        
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(title, reply_markup=reply_markup)


    async def process_model_selection(self, callback: types.CallbackQuery):
        model_id = callback.data.split("select_model_")[1]
        self.config.save_default_model(model_id)
        self.llm.config = self.config 
        await callback.message.edit_text(f"✅ Brain updated: {model_id}\n\nI am now using this model as my default intelligence.")
        await callback.answer()

    async def handle_message(self, message: types.Message):
        user_id = message.from_user.id
        try:
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
                await message.answer("Context compiled. Sending to OpenRouter...")

            # Get response
            await self.bot.send_chat_action(user_id, "typing")
            response_text = await self.llm.chat(injected_history, user_id=user_id)

            if not response_text:
                response_text = "⚠️ Brain returned an empty response. Please try again or check `/config`."

            # Append assistant message (if not aborted)
            if "🛑 Mission Aborted" not in response_text:
                self.histories[user_id].append({"role": "assistant", "content": response_text})

            # Keep history manageable (last 10 turns)
            if len(self.histories[user_id]) > 20:
                self.histories[user_id] = self.histories[user_id][-20:]

            await message.answer(response_text)
        except Exception as e:
            import traceback
            print(f"Chat Error: {traceback.format_exc()}")
            await message.answer(f"❌ System Error: {str(e)}\n\nCheck logs for details.")

    async def _set_bot_commands(self):
        commands = [
            BotCommand(command="start", description="Start or wake up the bot"),
            BotCommand(command="new", description="Starts a new session"),
            BotCommand(command="status", description="Shows runtime status"),
            BotCommand(command="models", description="Browse and pick AI models (Provider Picker)"),
            BotCommand(command="model", description="Legacy search for a model (alias)"),
            BotCommand(command="config", description="View or update system settings"),
            BotCommand(command="think", description="Sets thinking level (off|minimal|low|medium|high|xhigh)"),
            BotCommand(command="verbose", description="Toggles verbose output"),
            BotCommand(command="tools", description="Shows available tools"),
            BotCommand(command="plugins", description="Inspect or reload plugins"),
            BotCommand(command="mcp", description="Manage MCP server connections"),
            BotCommand(command="bash", description="Run a host shell command"),
            BotCommand(command="skill", description="Run a specific plugin by name"),
            BotCommand(command="delegate", description="Delegate a mission to High-Command"),
            BotCommand(command="tasks", description="List active background tasks"),
            BotCommand(command="review", description="Review a mission quality audit"),
            BotCommand(command="timezone", description="Set your local timezone"),
            BotCommand(command="schedule", description="Schedule a recurring mission"),
            BotCommand(command="help", description="Show the sunflower manifesto"),
            BotCommand(command="commands", description="List the command catalog"),
            BotCommand(command="stop", description="Abort the current chat generation"),
            BotCommand(command="compact", description="Summarize and archive context"),
            BotCommand(command="whoami", description="Show your user identity"),
            BotCommand(command="restart", description="Restart the bot gateway"),
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
