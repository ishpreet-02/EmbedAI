#!/bin/bash
# ══════════════════════════════════════════════════════════
# EC2 SETUP SCRIPT — Run once on a fresh Ubuntu 22.04 instance
# Usage: ssh into your EC2 → chmod +x setup-ec2.sh → ./setup-ec2.sh
# ══════════════════════════════════════════════════════════

set -e  # Exit on any error

echo "════════════════════════════════════════════"
echo "  AI Chatbot SaaS — EC2 Setup"
echo "════════════════════════════════════════════"

# ── 1. System updates ─────────────────────────────────────
echo "[1/7] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# ── 2. Install Docker ─────────────────────────────────────
echo "[2/7] Installing Docker..."
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Let current user run docker without sudo
sudo usermod -aG docker $USER

echo "[2/7] Docker installed: $(docker --version)"

# ── 3. Create swap file (critical for t2.micro 1GB RAM) ──
echo "[3/7] Creating 2GB swap file..."
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make swap permanent across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Optimize swap usage for low-memory server
echo 'vm.swappiness=60' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

echo "[3/7] Swap active: $(free -h | grep Swap)"

# ── 4. Install Nginx ──────────────────────────────────────
echo "[4/7] Installing Nginx..."
sudo apt install -y nginx

# ── 5. Install Certbot (HTTPS) ────────────────────────────
echo "[5/7] Installing Certbot..."
sudo apt install -y certbot python3-certbot-nginx

# ── 6. Install Git ────────────────────────────────────────
echo "[6/7] Installing Git..."
sudo apt install -y git

# ── 7. Create project directory ───────────────────────────
echo "[7/7] Setting up project directory..."
mkdir -p ~/chatbot-saas
cd ~/chatbot-saas

echo ""
echo "════════════════════════════════════════════"
echo "  Setup complete!"
echo "════════════════════════════════════════════"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. LOG OUT AND BACK IN (so Docker group takes effect):"
echo "   exit"
echo "   ssh -i your-key.pem ubuntu@YOUR_EC2_IP"
echo ""
echo "2. CLONE YOUR REPO:"
echo "   cd ~/chatbot-saas"
echo "   git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git ."
echo ""
echo "3. CREATE .env FILE:"
echo "   nano backend/.env"
echo "   (paste your env vars — Supabase, JWT, Groq keys)"
echo ""
echo "4. START EVERYTHING:"
echo "   docker compose up -d --build"
echo "   (first build takes 5-10 min — downloading PyTorch + model)"
echo ""
echo "5. SETUP NGINX:"
echo "   sudo cp nginx/chatbot-api.conf /etc/nginx/sites-available/chatbot-api"
echo "   sudo ln -s /etc/nginx/sites-available/chatbot-api /etc/nginx/sites-enabled/"
echo "   sudo nano /etc/nginx/sites-available/chatbot-api"
echo "   (replace YOUR_DOMAIN with your actual domain)"
echo "   sudo nginx -t"
echo "   sudo systemctl reload nginx"
echo ""
echo "6. SETUP HTTPS:"
echo "   sudo certbot --nginx -d YOUR_DOMAIN"
echo ""
echo "7. TEST:"
echo "   curl https://YOUR_DOMAIN/health"
echo ""
