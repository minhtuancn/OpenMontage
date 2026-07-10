# Setup Guide

Complete guide to deploy OpenMontage across two Ubuntu LAN machines.

## Prerequisites

- **DEV machine**: Ubuntu 24.04+, Docker 29+, Python 3.10+, Node 22+
- **GPU machine**: Ubuntu 24.04+, NVIDIA RTX 3060 12GB+, CUDA 12+, Docker (optional)
- **Network**: Both machines on same LAN (10.20.10.0/24)
- **SSH**: Passwordless SSH from DEV to GPU via `openmontage-gpu` alias

## 1. Configure SSH Access (DEV → GPU)

```bash
# Generate SSH key on DEV
ssh-keygen -t ed25519 -f ~/.ssh/openmontage_gpu -N ""

# Copy to GPU
ssh-copy-id -i ~/.ssh/openmontage_gpu.pub ubuntu@10.20.10.210

# Create SSH config
cat >> ~/.ssh/config << "EOF"
Host openmontage-gpu
    HostName 10.20.10.210
    User ubuntu
    IdentityFile ~/.ssh/openmontage_gpu
    StrictHostKeyChecking no
EOF

# Verify
ssh openmontage-gpu "hostname"
```

## 2. Clone Repository

```bash
sudo mkdir -p /opt/openmontage
sudo chown dev:dev /opt/openmontage
git clone https://github.com/minhtuancn/OpenMontage.git /opt/openmontage
cd /opt/openmontage
git checkout production
```

## 3. Configure 9Router (LLM Proxy)

Edit `/opt/openmontage/.env` (gitignored):

```bash
# 9Router Anthropic configuration
ANTHROPIC_BASE_URL=http://10.20.10.133:20128/v1
ANTHROPIC_API_KEY=sk-fcf5f1bbd05497aa-nthcqa-c324dad5

# ComfyUI remote server
COMFYUI_SERVER_URL=http://10.20.10.210:8188

# Remote GPU access
REMOTE_GPU_HOST=10.20.10.210
REMOTE_GPU_USER=ubuntu
```

Set `config.yaml`:

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-6
```

```bash
chmod 600 /opt/openmontage/.env
```

## 4. Install Backlot (Systemd Service)

Backlot is the HTTP API server for OpenMontage.

```bash
# Ensure service file exists
sudo cp /opt/openmontage/contrib/openmontage-backlot.service /etc/systemd/system/

# Start and enable
sudo systemctl daemon-reload
sudo systemctl enable --now openmontage-backlot.service

# Verify
curl http://127.0.0.1:4750/
```

The service file:

```ini
[Unit]
Description=OpenMontage Backlot — HTTP Storyboard API
After=network.target

[Service]
Type=simple
User=dev
Group=dev
WorkingDirectory=/opt/openmontage
ExecStart=/opt/openmontage/.venv/bin/python -m backlot.cli serve --host 0.0.0.0 --port 4750
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 5. Install ComfyUI on GPU Node

### Option A: Native Install (Recommended)

```bash
# SSH into GPU
ssh openmontage-gpu

# Install dependencies
sudo apt-get update
sudo apt-get install -y git python3-pip python3-venv wget

# Clone ComfyUI
sudo mkdir -p /opt/openmontage-gpu/comfyui
sudo chown ubuntu:ubuntu /opt/openmontage-gpu
git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /opt/openmontage-gpu/comfyui

# Setup venv
cd /opt/openmontage-gpu/comfyui
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu124
pip install xformers

# Create systemd service
sudo tee /etc/systemd/system/openmontage-comfyui.service > /dev/null << "SERVICEEOF"
[Unit]
Description=OpenMontage ComfyUI — low-VRAM image/video generation
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/openmontage-gpu/comfyui
ExecStart=/opt/openmontage-gpu/comfyui/venv/bin/python main.py --listen 0.0.0.0 --port 8188
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF

sudo systemctl daemon-reload
sudo systemctl enable --now openmontage-comfyui.service

# Open firewall
sudo ufw allow from 10.20.10.0/24 to any port 8188 proto tcp

# Verify
curl http://127.0.0.1:8188/system_stats
```

### Option B: Docker (Alternative)

```yaml
# docker-compose.yml on GPU
services:
  comfyui:
    image: comfyui/comfyui:latest
    ports:
      - "8188:8188"
    volumes:
      - /opt/openmontage-gpu/comfyui/models:/workspace/ComfyUI/models
      - /opt/openmontage-gpu/comfyui/output:/workspace/ComfyUI/output
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    restart: unless-stopped
```

```bash
docker compose up -d
```

## 6. Download Low-VRAM Models

These models fit on RTX 3060 12GB VRAM:

| Model | Size | Description |
|-------|------|-------------|
| Wan 2.1 1.3B T2V | ~2.5GB | Text-to-video, quality + speed balance |
| LTX-Video 0.9.5 FP8 | ~3GB | Fast video generation, lower quality |

**Note:** If the GPU filesystem is read-only (ext4 journal error), fix it first:

```bash
ssh openmontage-gpu
sudo touch /forcefsck
sudo reboot
# After reboot, continue:
```

```bash
# Download models
ssh openmontage-gpu
cd /opt/openmontage-gpu/comfyui/models

pip install huggingface-hub

# Wan 2.1 1.3B
huggingface-cli download Wan-AI/Wan2.1-T2V-1.3B \
  --local-dir Wan2.1-T2V-1.3B

# LTX-Video 0.9.5 FP8
huggingface-cli download Lightricks/LTX-Video-0.9.5-fp8 \
  --local-dir LTX-Video-0.9.5-fp8
```

If HuggingFace is blocked, use a mirror:

```bash
HF_ENDPOINT=https://hf-mirror.com huggingface-cli download Wan-AI/Wan2.1-T2V-1.3B \
  --local-dir Wan2.1-T2V-1.3B
```

Or manually download from CivitAI and SCP to GPU:

```bash
# On a machine with internet:
wget https://civitai.com/api/download/models/...

# Transfer to GPU:
scp model.safetensors ubuntu@10.20.10.210:/opt/openmontage-gpu/comfyui/models/diffusion_models/
```

## 7. Deploy n8n (Docker)

```bash
# Pull and start
cd /opt/openmontage
docker compose -f docker-compose.automation.yml up -d

# Wait for initialization, then create admin account
curl -s -X POST http://127.0.0.1:5678/rest/owner/setup \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@openmontage.local","password":"<your-password>","firstName":"Admin","lastName":"OpenMontage"}'

# Verify
curl http://127.0.0.1:5678/healthz
```

### Import Workflows

Via CLI:

```bash
docker exec -i n8n n8n import:workflow --input=- < scripts/n8n-publish-workflow.json
```

Or via Web UI at `http://10.20.10.103:5678/` (requires SSH tunnel if bound to localhost).

### Publish Script

```bash
# Trigger publishing for a project
/opt/openmontage/scripts/publish-to-n8n.sh animated-explainer
```

## 8. Configure Firewall (UFW)

### DEV Machine

```bash
sudo ufw allow ssh
sudo ufw allow from 10.20.10.0/24 to any port 4750 proto tcp  # Backlot
sudo ufw enable
```

### GPU Machine

```bash
sudo ufw allow ssh
sudo ufw allow from 10.20.10.0/24 to any port 8188 proto tcp  # ComfyUI
sudo ufw from 10.20.10.0/24 to any port 8750 proto tcp         # GPU API (if used)
sudo ufw enable
```

## 9. Create openmontage-agent Script

```bash
cat > /usr/local/bin/openmontage-agent << "SCRIPT"
#!/bin/bash
# OpenMontage Agent Launcher
# Sets up 9Router proxy environment and launches Claude Code in tmux

export ANTHROPIC_BASE_URL="http://10.20.10.133:20128/v1"
export ANTHROPIC_API_KEY="sk-fcf5f1bbd05497aa-nthcqa-c324dad5"
export COMFYUI_SERVER_URL="http://10.20.10.210:8188"

# Source .env if it exists
[ -f /opt/openmontage/.env ] && source /opt/openmontage/.env

exec tmux new -A -s openmontage
SCRIPT
chmod +x /usr/local/bin/openmontage-agent
```

## 10. Verify Complete Setup

```bash
# Check all services
openmontage-status

# Expected output:
# Backlot:     active
# ComfyUI:     active (on GPU)
# n8n:         running
# UFW:         active
# 9Router:     configured

# Test Backlot API
curl http://10.20.10.103:4750/

# Test ComfyUI
curl http://10.20.10.210:8188/system_stats

# Test n8n
curl http://127.0.0.1:5678/healthz

# Launch Claude agent
openmontage-agent
```

## Troubleshooting

### GPU Filesystem Read-Only

```
EXT4-fs error: Detected aborted journal
```

**Fix:** Remount with force fsck on next reboot:

```bash
ssh openmontage-gpu
sudo touch /forcefsck
sudo reboot
# After reboot, verify:
touch /tmp/test
echo "Writable"
```

### n8n Docker Pull Fails

If DNS resolution fails intermittently:

```bash
# Retry pull
docker compose -f /opt/openmontage/docker-compose.automation.yml pull

# Check Docker DNS
docker info | grep -i dns

# Alternative: install n8n natively
sudo npm install -g n8n
n8n start
```

### Disk Space Alert

```bash
# DEV machine cleanup
sudo journalctl --vacuum-time=3d
sudo apt-get clean
docker system prune -af

# Check space
df -h /
```
