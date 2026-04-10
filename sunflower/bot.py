import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand

from sunflower.config import Config
from sunflower.llm import LLMClient
from sunflower.tools import ToolRegistry

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
        
        # Chat histories (Simple dict for v1.0.0)
        self.histories = {}

        self._register_handlers()

    def _register_handlers(self):
        self.dp.message(Command("start"))(self.cmd_start)
        self.dp.message(Command("model"))(self.cmd_model)
        self.dp.message(Command("bash"))(self.cmd_bash)
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
        # Notify user that execution has started
        await message.answer(f"⚙️ Executing: `{cmd}`...", parse_mode="Markdown")
        
        # Run command securely and return output
        result = await ToolRegistry.execute_bash(cmd)
        await message.answer(result, parse_mode="Markdown")

    async def cmd_model(self, message: types.Message, state: FSMContext):
        await state.set_state(ModelStates.waiting_for_search)
        await message.answer(
            "Please type part of the model name you are looking for (e.g., `claude`, `gpt-4`, `llama`):",
            parse_mode="Markdown"
        )

    async def process_model_search(self, message: types.Message, state: FSMContext):
        search_term = message.text
        models = await self.llm.get_available_models(search_term)
        
        if not models:
            await message.answer("No models found. Try another search term:")
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

        # Append user message
        self.histories[user_id].append({"role": "user", "content": message.text})

        # Get response
        await self.bot.send_chat_action(user_id, "typing")
        response_text = await self.llm.chat(self.histories[user_id])

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
            BotCommand(command="activation", description="Sets group activation mode"),
            BotCommand(command="send", description="Sets send policy"),
            BotCommand(command="bash", description="Runs a host shell command")
        ]
        await self.bot.set_my_commands(commands)

    async def run(self):
        print("🌻 Sunflower is starting...")
        try:
            await self._set_bot_commands()
            await self.dp.start_polling(self.bot)
        finally:
            await self.bot.session.close()
