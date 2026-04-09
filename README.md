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
