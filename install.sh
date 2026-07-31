#!/usr/bin/env bash
# VPS Control Panel - One-Line Installer
# Usage: curl -sSL https://raw.githubusercontent.com/.../install.sh | bash

set -e

PANEL_DIR="/opt/vps-panel"
REPO_URL="https://github.com/yourusername/vps-panel.git" # Replace with actual repo or zip
PORT=3000

echo "====================================================="
echo "  VPS Management Control Panel Installer"
echo "====================================================="

# 1. Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Unsupported OS. Could not detect OS."
    exit 1
fi

echo "[*] Detected OS: $OS"

# 2. Install Dependencies
echo "[*] Installing system dependencies..."
if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
    apt-get update -y
    apt-get install -y curl wget git nginx certbot python3-certbot-nginx ufw
    # Install Node.js 20.x
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
elif [[ "$OS" == "centos" || "$OS" == "almalinux" || "$OS" == "rocky" ]]; then
    dnf install -y epel-release
    dnf install -y curl wget git nginx certbot python3-certbot-nginx firewalld
    # Install Node.js 20.x
    curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
    dnf install -y nodejs
else
    echo "Unsupported OS: $OS. Please install manually."
    exit 1
fi

# 3. Setup Application Directory
echo "[*] Setting up application directory..."
if [ -d "$PANEL_DIR" ]; then
    echo "[*] Backing up existing installation..."
    mv "$PANEL_DIR" "${PANEL_DIR}_backup_$(date +%s)"
fi

mkdir -p "$PANEL_DIR"
# For production, you would clone the repo here:
# git clone $REPO_URL $PANEL_DIR
echo "[*] Workspace ready at $PANEL_DIR. (Assuming files are transferred)"

# 4. Install Node Modules & Build (Placeholder for actual source code)
# cd $PANEL_DIR
# npm install
# npm run build

# 5. Create Systemd Service
echo "[*] Creating Systemd service..."
cat <<EOF > /etc/systemd/system/vps-panel.service
[Unit]
Description=VPS Management Control Panel
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PANEL_DIR
Environment=NODE_ENV=production
Environment=PORT=$PORT
# Generate a random JWT secret on install
Environment=JWT_SECRET=$(openssl rand -hex 32)
ExecStart=/usr/bin/node dist/server.cjs
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable vps-panel
# systemctl start vps-panel

# 6. Configure Nginx (Basic placeholder, user will configure Let's Encrypt later)
echo "[*] Setting up Nginx reverse proxy..."
cat <<EOF > /etc/nginx/sites-available/vps-panel
server {
    listen 80;
    server_name _; # Replace with actual domain during setup

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF

if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
    ln -sf /etc/nginx/sites-available/vps-panel /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    systemctl restart nginx
elif [[ "$OS" == "centos" || "$OS" == "almalinux" || "$OS" == "rocky" ]]; then
    cp /etc/nginx/sites-available/vps-panel /etc/nginx/conf.d/vps-panel.conf
    systemctl restart nginx
fi

echo "====================================================="
echo "  Installation Complete!"
echo "  Start the service using: systemctl start vps-panel"
echo "  Access the panel at: http://YOUR_SERVER_IP"
echo "====================================================="
