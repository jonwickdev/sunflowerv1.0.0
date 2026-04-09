# VPS Deployment Guide (Docker)

Here are the step-by-step instructions to get your **Sunflower** bot fully deployed using Docker on a fresh Linux VPS (like Ubuntu or Debian):

## 1. SSH into Your VPS
Open your terminal and connect to your server using its IP address:
```bash
ssh root@<your-vps-ip>
```

## 2. Install Docker & Git
If your VPS is brand new, you'll need to install Git and Docker. Run these commands:
```bash
# Update your server packages
apt update && apt upgrade -y

# Install Git
apt install git -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

## 3. Clone Your Repository
Download your codebase directly from your GitHub repository onto the VPS:
```bash
git clone https://github.com/jonwickdev/sunflowerv1.0.0.git
cd sunflowerv1.0.0
```

## 4. Configure Your API Keys
Your `.env` file is correctly excluded from GitHub so your keys don't leak. You will need to create the `.env` file manually on the VPS:

```bash
nano .env
```
Paste your keys into the file:
```text
OPENROUTER_API_KEY=your_openrouter_key_here
TELEGRAM_BOT_TOKEN=your_telegram_token_here
```
*(To save and exit in nano, press `CTRL + X`, then `Y`, then `Enter`)*

## 5. Start the Bot!
Instruct Docker to build and run the bot in the background:
```bash
docker compose up -d
```

## You're Done! 🎉
Your bot is now alive and running! It automatically restarts if it crashes or if the server reboots. 

### Useful Commands
*   **View live logs**: `docker logs -f sunflower_bot`
*   **Stop the bot**: `docker compose down`
*   **Update the bot**: Pull the latest changes from GitHub and rebuild:
    ```bash
    git pull
    docker compose up -d --build
    ```
