import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from llm import LLMClient

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
        self.dp.message(ModelStates.waiting_for_search)(self.process_model_search)
        self.dp.callback_query(F.data.startswith("select_model_"))(self.process_model_selection)
        self.dp.message()(self.handle_message)

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

    async def run(self):
        print("🌻 Sunflower is starting...")
        try:
            await self.dp.start_polling(self.bot)
        finally:
            await self.bot.session.close()
