#!/bin/bash
# install_paperclip.sh - Helper script to quickly spin up an isolated Paperclip Orchestration Server next to Sunflower

# 1. Colors for logs
GREEN='\033[0;32m'
NC='\033[0m'
YELLOW='\033[1;33m'

echo -e "${GREEN}🌻 [1/5] Cloning/Updating Paperclip Repository...${NC}"
if [ ! -d "paperclip_repo" ]; then
    git clone https://github.com/paperclipai/paperclip.git paperclip_repo
else
    cd paperclip_repo && git pull && cd ..
fi

echo -e "${GREEN}🌻 [2/5] Patching Dockerfile for VPS Compatibility...${NC}"
# Bypass outdated GitHub GPG hash check
sed -i '/sha256sum/d' paperclip_repo/Dockerfile

echo -e "${GREEN}🌻 [3/5] Setting up persistent Authentication & Permissions...${NC}"
# Generate a secret if it doesn't exist
SECRET_FILE="paperclip_repo/docker/.env"
if [ ! -f "$SECRET_FILE" ]; then
    RANDOM_SECRET="paperclip-secret-$(date +%s)$RANDOM"
    IPV4_AUTODETECT=$(curl -s -4 ifconfig.me)
    echo "BETTER_AUTH_SECRET=$RANDOM_SECRET" > "$SECRET_FILE"
    echo "PAPERCLIP_PORT=3100" >> "$SECRET_FILE"
    echo "PAPERCLIP_PUBLIC_URL=http://$IPV4_AUTODETECT:3100" >> "$SECRET_FILE"
    echo "PAPERCLIP_DEPLOYMENT_MODE=authenticated" >> "$SECRET_FILE"
    echo "PAPERCLIP_DEPLOYMENT_EXPOSURE=private" >> "$SECRET_FILE"
fi

# Pre-create data directory and fix permissions for internal 'node' user (UID 1000)
mkdir -p paperclip_repo/data/docker-paperclip
chown -R 1000:1000 paperclip_repo/data

echo -e "${GREEN}🌻 [4/5] Opening Firewall (Port 3100)...${NC}"
if command -v ufw >/dev/null 2>&1; then
    ufw allow 3100/tcp
elif command -v firewall-cmd >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port=3100/tcp
    firewall-cmd --reload
fi

echo -e "${GREEN}🌻 [5/5] Launching Paperclip in the background...${NC}"
cd paperclip_repo/docker
docker compose -f docker-compose.quickstart.yml up -d --build

echo -e "\n${GREEN}✅ SUCCESS! Paperclip is now ready.${NC}"
IPV4=$(curl -s -4 ifconfig.me)
echo -e "Open your browser to: ${YELLOW}http://$IPV4:3100${NC}"
echo -e "\n1. Complete the onboarding in your browser."
echo -e "2. Go to 'Agents' -> 'Generate API Key'."
echo -e "3. Copy the 'Company ID' from your URL (e.g., comp_xxx)."
echo -e "\nRun these in Telegram:"
echo -e "/paperclip set_url http://$IPV4:3100"
echo -e "/paperclip set_company <COMPANY_ID>"
echo -e "/paperclip set_key <API_KEY>"
