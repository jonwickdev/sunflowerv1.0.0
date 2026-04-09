This is an excellent starting point. Building a solid foundation with proper onboarding and configuration management is crucial for a system that will eventually become complex and autonomous.

I have designed **Sunflower v1.0.0** with the following architecture:

1.  **Separation of Concerns**: Configuration (secrets) is separated from State (user preferences like the selected model).
2.  **Async First**: Using `aiogram` 3.x for Telegram ensures the bot is responsive and ready for future autonomous tasks.
3.  **OpenRouter Integration**: Uses the `openai` Python library with the OpenRouter base URL for maximum compatibility.
4.  **Model Selection UX**: Since OpenRouter has hundreds of models, a simple "dropdown" would be overwhelming. I have implemented a **Search & Select** flow using Telegram's Inline Keyboards. You type `/model`, then search for "claude" or "gpt-4", and it presents buttons for matching models.

*Note on "Pairing Code":* Standard Telegram bots do not use pairing codes like Discord or Slack. The "pairing" is handled by the **Bot Token** provided by BotFather. Once you enter the token in the onboarding, the bot is connected. You simply open the chat in Telegram and click Start.

Here is your complete codebase.

### Project Structure
```text
sunflower-v1.0.0/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
└── sunflower/
    ├── __init__.py
    ├── main.py
    ├── bot.py
    ├── config.py
    ├── llm.py
    └── onboarding.py
```

### 1. Setup Files

**`requirements.txt`**
```text
aiogram==3.4.1
openai==1.14.0
python-dotenv==1.0.1
requests==2.31.0
```

**`.gitignore`**
```text
# Python
__pycache__/
*.py[cod]
venv/
.env

# Config (contains user preferences)
config.json
```

**`.env.example`**
```text
# Get your OpenRouter key from https://openrouter.ai/keys
OPENROUTER_API_KEY=

# Get your Telegram Bot Token from @BotFather
TELEGRAM_BOT_TOKEN=
```

### 2. Core Application Code

**`sunflower/config.py`**
This handles separating secrets (`.env`) from state (`config.json`).

```python
import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.config_file = "config.json"
        self.default_model = self.load_default_model()

    def load_default_model(self):
        if not os.path.exists(self.config_file):
            return "openai/gpt-3.5-turbo" # Fallback default
        with open(self.config_file, 'r') as f:
            data = json.load(f)
            return data.get("default_model", "openai/gpt-3.5-turbo")

    def save_default_model(self, model_id):
        self.default_model = model_id
        with open(self.config_file, 'w') as f:
            json.dump({"default_model": model_id}, f, indent=4)

    def validate(self):
        missing = []
        if not self.api_key: missing.append("OPENROUTER_API_KEY")
        if not self.bot_token: missing.append("TELEGRAM_BOT_TOKEN")
        if missing:
            raise ValueError(f"Missing configuration: {', '.join(missing)}. Please run onboarding or check .env file.")
```

**`sunflower/onboarding.py`**
This runs if the `.env` file is missing data.

```python
import os
from dotenv import set_key

def run_onboarding():
    env_file = ".env"
    if not os.path.exists(env_file):
        with open(env_file, 'w') as f:
            pass # Create file

    print("🌻 Welcome to Sunflower v1.0.0 Setup 🌻")
    
    # API Key
    api_key = input("Enter your OpenRouter API Key: ").strip()
    set_key(env_file, "OPENROUTER_API_KEY", api_key)
    
    # Bot Token
    bot_token = input("Enter your Telegram Bot Token (from @BotFather): ").strip()
    set_key(env_file, "TELEGRAM_BOT_TOKEN", bot_token)
    
    print("\nSetup complete! Configuration saved to .env")
    print("You can now start the bot. In Telegram, open your bot and click 'Start' to begin chatting.")

if __name__ == "__main__":
    run_onboarding()
```

**`sunflower/llm.py`**
Handles communication with OpenRouter.

```python
from openai import OpenAI
from config import Config

class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.config.api_key,
        )

    async def chat(self, history: list) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.config.default_model,
                messages=history,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error communicating with OpenRouter: {str(e)}"

    async def get_available_models(self, search_term: str = "") -> list:
        import requests
        try:
            # OpenRouter public endpoint for models
            resp = requests.get("https://openrouter.ai/api/v1/models")
            resp.raise_for_status()
            data = resp.json().get('data', [])
            
            if search_term:
                search_term = search_term.lower()
                # Filter by id or name containing search term
                filtered = [m for m in data if search_term in m['id'].lower() or search_term in m.get('name', '').lower()]
                return filtered[:10] # Limit to 10 results for Telegram UI
            
            # Return top models if no search term
            return data[:5]
        except Exception as e:
            print(f"Error fetching models: {e}")
            return []
```

**`sunflower/bot.py`**
The Telegram interface and logic.

```python
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
```

**`sunflower/main.py`**
The entry point.

```python
import asyncio
import os
from onboarding import run_onboarding
from bot import SunflowerBot
from config import Config

def main():
    # Check if onboarding is needed
    if not os.path.exists(".env") or not os.getenv("OPENROUTER_API_KEY") or not os.getenv("TELEGRAM_BOT_TOKEN"):
        run_onboarding()
        # Reload env vars after onboarding
        from dotenv import load_dotenv
        load_dotenv(override=True)

    try:
        bot = SunflowerBot()
        asyncio.run(bot.run())
    except ValueError as e:
        print(f"\n[Error] {e}")
    except KeyboardInterrupt:
        print("\n🌻 Sunflower is shutting down. Goodbye!")

if __name__ == "__main__":
    main()
```

**`sunflower/__init__.py`**
```python
# Empty file to make it a package
```

### 3. Documentation

**`README.md`**
```markdown
# Sunflower v1.0.0

A secure, autonomous AI Agent starting as a Telegram Chatbot with OpenRouter integration.

## Features (v1.0.0)
- Connect to Telegram
- Use any model on OpenRouter
- `/model` command to search and switch models via Inline Buttons
- Persistent model selection (remembers your choice after restart)
- Simple onboarding setup

## Installation

### 1. Prerequisites
- Python 3.9+
- A Telegram Account
- An OpenRouter API Key

### 2. Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/sunflower-v1.0.0.git
cd sunflower-v1.0.0

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

# Install dependencies
pip install -r requirements.txt
```

### 3. First Run (Onboarding)
Run the application for the first time. It will detect missing credentials and start the onboarding wizard.

```bash
python -m sunflower.main
```

The wizard will ask for:
1. **OpenRouter API Key**: Found at [openrouter.ai/keys](https://openrouter.ai/keys)
2. **Telegram Bot Token**: Create a new bot via [@BotFather](https://t.me/botfather) on Telegram.

### 4. Start Chatting
1. Open Telegram and find your bot.
2. Click **Start** or type `/start`.
3. You are now chatting with Sunflower!

## Usage
- **Chat**: Just send a message.
- **Change Model**: Type `/model`, then type a search term (e.g., "claude"), and click the button for the model you want.

## Architecture
- `main.py`: Entry point and startup logic.
- `bot.py`: Telegram handlers and FSM (Finite State Machine) for conversations.
- `llm.py`: OpenRouter API client.
- `config.py`: Manages secrets (`.env`) and state (`config.json`).
- `onboarding.py`: CLI wizard for first-time setup.
```

### How to Run This on Your VPS

1. Upload this folder structure to your VPS (e.g., using `git clone` or `scp`).
2. `cd sunflower-v1.0.0`
3. `python3 -m venv venv`
4. `source venv/bin/activate`
5. `pip install -r requirements.txt`
6. `python -m sunflower.main`

The first time you run it, it will stop and ask for your keys. Once you enter them, it will save them to `.env` and start the bot.

To run it in the background permanently on a VPS, you can use `tmux` or `systemd`.
Example with `tmux`:
```bash
tmux new -s sunflower
python -m sunflower.main
# Press Ctrl+B then D to detach
```

Let me know when you have this running, and we can move on to adding persistent memory or improving the self-repair capabilities!