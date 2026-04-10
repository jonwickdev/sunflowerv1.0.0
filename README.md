# Sunflower v1.0.0

A secure, autonomous AI Agent starting as a Telegram Chatbot with OpenRouter integration.

## Features (v1.0.0)
- Connect to Telegram
- Use any model on OpenRouter
- `/model` command to search and switch models via Inline Buttons
- Persistent model selection (remembers your choice after restart)
- Simple onboarding setup

## Installation Options

You can run Sunflower locally on your laptop, or deploy it permanently to a cloud VPS server using Docker.

---

### Option A: Local Machine Setup (Windows/Mac/Linux)
*Best for development and testing.*

**1. Prerequisites**
- Python 3.9+
- A Telegram Account
- An OpenRouter API Key ([openrouter.ai/keys](https://openrouter.ai/keys))

**2. Setup Environment**
```bash
git clone https://github.com/jonwickdev/sunflowerv1.0.0.git
cd sunflowerv1.0.0

# Create a virtual environment
python -m venv venv

# Activate it (Windows)
venv\Scripts\activate
# Activate it (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**3. First Run (Onboarding)**
Run the application for the first time. It will detect missing credentials and start the setup wizard.
```bash
python -m sunflower.main
```
Provide your API keys when prompted. The bot will save them to a `.env` file and start chatting!

---

### Option B: VPS Server Deployment (Docker)
*Best for running 24/7 in the background.*

**1. Install Git & Docker**
If your server is fresh, install the required packages:
```bash
apt update && apt upgrade -y
apt install git docker.io docker-compose-v2 -y
```

**2. Clone the Repository**
```bash
git clone https://github.com/jonwickdev/sunflowerv1.0.0.git
cd sunflowerv1.0.0
```

**3. Configure Credentials & State**
Your server needs a `.env` file for secrets, and a `config.json` file for state. The easiest way to create them from the terminal is to run these commands (replace the placeholder text in the first two lines with your actual keys):
```bash
# Insert your real keys inside the quotes!
echo "OPENROUTER_API_KEY=your_openrouter_key" > .env
echo "TELEGRAM_BOT_TOKEN=your_telegram_token" >> .env

# Create empty config file (prevents Docker from creating it as a directory)
echo "{}" > config.json
```

**4. Start the Bot**
Build and start the container in the background:
```bash
docker compose up -d --build
```
Your bot is now alive 24/7! It will automatically restart on server reboots.

**Helpful Docker Commands:**
- View live logs: `docker logs -f sunflower_bot`
- Stop the bot: `docker compose down`

---

## Usage
1. Open Telegram and find your bot (via [@BotFather](https://t.me/botfather)).
2. Click **Start** or type `/start`.
3. Just send a message to chat, or type `/model` to search and switch between AI brains!

## Architecture
- `sunflower/main.py`: Python module entry point.
- `sunflower/bot.py`: Telegram handlers and FSM (Finite State Machine).
- `sunflower/llm.py`: OpenRouter API client.
- `sunflower/config.py`: Manages secrets (`.env`) and state (`config.json`).
- `Dockerfile` & `docker-compose.yml`: VPS container definitions.
