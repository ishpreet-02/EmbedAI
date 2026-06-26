#!/bin/bash
# ══════════════════════════════════════════════════════════
# EmbedAI — EC2 SETUP SCRIPT
# Run once on a fresh Ubuntu 24.04 t2.micro instance
# Usage: ssh into EC2 → chmod +x setup-ec2.sh → ./setup-ec2.sh
# ══════════════════════════════════════════════════════════

set -e  # Exit on any error

echo "════════════════════════════════════════════"
echo "  EmbedAI — EC2 Setup"
echo "════════════════════════════════════════════"

# ── 1. System updates ─────────────────────────────────────
echo "[1/6] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# ── 2. Install Docker ─────────────────────────────────────
echo "[2/6] Installing Docker..."
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Let current user run docker without sudo
sudo usermod -aG docker $USER

echo "[2/6] Docker installed: $(docker --version)"

# ── 3. Create swap file (CRITICAL for t2.micro 1GB RAM) ──
echo "[3/6] Creating 2GB swap file..."
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make swap permanent across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Optimize swap usage for low-memory server
echo 'vm.swappiness=60' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

echo "[3/6] Swap active: $(free -h | grep Swap)"

# ── 4. Install Nginx ──────────────────────────────────────
echo "[4/6] Installing Nginx..."
sudo apt install -y nginx

# ── 5. Install Certbot (free HTTPS) ──────────────────────
echo "[5/6] Installing Certbot..."
sudo apt install -y certbot python3-certbot-nginx

# ── 6. Install Git ────────────────────────────────────────
echo "[6/6] Installing Git..."
sudo apt install -y git

# ── Create project directory ─────────────────────────────
mkdir -p ~/embedai
cd ~/embedai

echo ""
echo "════════════════════════════════════════════"
echo "  ✅ Setup complete!"
echo "════════════════════════════════════════════"
echo ""
echo "IMPORTANT: Log out and back in for Docker group to take effect:"
echo "  exit"
echo "  ssh -i your-key.pem ubuntu@YOUR_EC2_IP"
echo ""
echo "Then follow the deployment guide (AWS_DEPLOYMENT_GUIDE.md)"
echo ""
