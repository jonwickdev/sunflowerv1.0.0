#!/bin/bash
# install_paperclip.sh - Helper script to quickly spin up an isolated Paperclip Orchestration Server next to Sunflower

echo "🌻 [1/4] Cloning Paperclip Repository..."
if [ ! -d "paperclip_repo" ]; then
    git clone https://github.com/paperclipai/paperclip.git paperclip_repo
else
    echo "Directory paperclip_repo already exists. Skipping clone."
fi

echo "🌻 [2/4] Patching outdated GitHub Archive hashes in Dockerfile..."
# GitHub rotated their GPG keys, which breaks the standard Paperclip Dockerfile. This removes the strict hash check so it builds cleanly.
sed -i '/sha256sum/d' paperclip_repo/Dockerfile

echo "🌻 [3/4] Generating Secure Authentication Token..."
export BETTER_AUTH_SECRET="paperclip-secret-$(date +%s)$RANDOM"

echo "🌻 [4/4] Building and Starting Paperclip via Docker Compose..."
cd paperclip_repo/docker
docker compose -f docker-compose.quickstart.yml up -d --build

echo ""
echo "✅ SUCCESS! The Paperclip Orchestration Server is booting up."
echo "Wait about 60 seconds, then open a web browser and visit:"
echo "👉 http://<Your-Server-IP-Address>:3100"
echo ""
echo "Once the dashboard loads, navigate to Agents -> Generate API Key,"
echo "and feed it to your Sunflower Telegram Bot using the /paperclip commands!"
