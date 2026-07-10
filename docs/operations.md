# Operations Guide

Day-to-day operations for the OpenMontage production system.

## Service Management

### Status Check

```bash
# Quick summary
openmontage-status

# Or check individual services
systemctl status openmontage-backlot.service
ssh openmontage-gpu "systemctl status openmontage-comfyui.service"
docker ps --filter name=n8n
```

### Start/Stop/Restart

```bash
# Backlot
sudo systemctl start|stop|restart openmontage-backlot.service

# ComfyUI (on GPU)
ssh openmontage-gpu "sudo systemctl start|stop|restart openmontage-comfyui.service"

# n8n
docker compose -f /opt/openmontage/docker-compose.automation.yml up -d
docker compose -f /opt/openmontage/docker-compose.automation.yml down
docker compose -f /opt/openmontage/docker-compose.automation.yml restart n8n
```

### Enable on Boot

```bash
sudo systemctl enable openmontage-backlot.service
ssh openmontage-gpu "sudo systemctl enable openmontage-comfyui.service"
sudo systemctl enable openmontage-n8n.service  # starts Docker compose
```

## Logs

```bash
# Backlot
sudo journalctl -u openmontage-backlot.service -f

# ComfyUI
ssh openmontage-gpu "sudo journalctl -u openmontage-comfyui.service -f"

# n8n
docker logs -f n8n
```

## Disk Maintenance

### DEV Machine

The DEV root partition is 138GB. Key space hogs:

| Location | Typical Size | Notes |
|----------|-------------|-------|
| Docker images | 5-15GB | `docker system df` |
| Journal logs | 1-3GB | `journalctl --disk-usage` |
| npm cache | 1-2GB | `rm -rf ~/.npm/_cacache` |
| /tmp | 0-5GB | `sudo rm -rf /tmp/*` |

**Monthly cleanup:**

```bash
#!/bin/bash
# /opt/openmontage/scripts/cleanup.sh
echo "=== Cleanup ==="
sudo journalctl --vacuum-time=3d
sudo apt-get clean
docker system prune -af 2>/dev/null
sudo rm -rf /tmp/*
echo "Done. Available: $(df -h / | tail -1 | awk '{print $4}')"
```

### GPU Machine

GPU disk is 165GB. The filesystem may become read-only if it fills up.

**Warning signs:**
- `df -h` shows >95% usage
- `dmesg` shows `EXT4-fs error: Detected aborted journal`
- Can't write to `/tmp`

**Recovery:**

```bash
ssh openmontage-gpu
# 1. Free up space (remount rw first if read-only)
sudo mount -o remount,rw / 2>/dev/null || echo "Need fsck first"

# 2. If read-only, fix with fsck on reboot:
sudo touch /forcefsck
sudo reboot
# Wait for reboot, then SSH back
ssh openmontage-gpu

# 3. Clean up
sudo journalctl --vacuum-time=3d
sudo apt-get clean
df -h /
```

## Model Management

### Current Models

Models are stored at `/opt/openmontage-gpu/comfyui/models/`:

```
diffusion_models/    → Wan 2.1, LTX-Video, SDXL checkpoints
checkpoints/         → SDXL base models (if used)
vae/                 → VAE decoders
clip/                → CLIP text encoders
controlnet/          → ControlNet models
```

### Download Models

```bash
# Via HuggingFace
ssh openmontage-gpu
cd /opt/openmontage-gpu/comfyui/models
pip install huggingface-hub

huggingface-cli download Wan-AI/Wan2.1-T2V-1.3B --local-dir Wan2.1-T2V-1.3B

# Via HuggingFace mirror
HF_ENDPOINT=https://hf-mirror.com huggingface-cli download ...
```

### Model File Locations

ComfyUI expects models in specific subdirectories:

| Model Type | Directory |
|------------|-----------|
| Diffusion models | `models/diffusion_models/` |
| Checkpoints | `models/checkpoints/` |
| VAE | `models/vae/` |
| CLIP | `models/clip/` |
| ControlNet | `models/controlnet/` |
| LoRA | `models/loras/` |
| Text encoders | `models/text_encoders/` |

## Backup

### What to Back Up

| Item | Location | Frequency |
|------|----------|-----------|
| .env config | `/opt/openmontage/.env` | After changes |
| n8n data | `/srv/openmontage/n8n/` | Weekly |
| Docker compose | `/opt/openmontage/docker-compose.automation.yml` | After changes |
| ComfyUI workflows | `/opt/openmontage/tools/_comfyui/workflows/` | After changes |

### Quick Backup

```bash
# Config only (safe for git)
tar czf /tmp/openmontage-config-$(date +%Y%m%d).tar.gz \
  /opt/openmontage/.env \
  /opt/openmontage/config.yaml \
  /opt/openmontage/docker-compose.automation.yml \
  /etc/systemd/system/openmontage-*.service

# Full operational backup (n8n data)
tar czf /tmp/openmontage-data-$(date +%Y%m%d).tar.gz \
  /srv/openmontage/n8n/
```

## Network

### UFW Rules

**DEV:**
```
22/tcp                     ALLOW       Anywhere
4750/tcp                   ALLOW       10.20.10.0/24
```

**GPU:**
```
22/tcp                     ALLOW       Anywhere
8188/tcp                   ALLOW       10.20.10.0/24
8750/tcp                   ALLOW       10.20.10.0/24
```

### Add New IP

```bash
sudo ufw allow from <new-ip> to any port 4750 proto tcp
```

## Production Test Workflow

### End-to-End: Animated Explainer

```bash
# 1. Start agent with 9Router
openmontage-agent

# 2. Inside tmux, Claude Code will:
#    - Generate script via Claude 3.5 Sonnet
#    - Generate images via ComfyUI (if models available)
#    - Compose video via FFmpeg
#    - Save to projects/

# 3. Publish results
/opt/openmontage/scripts/publish-to-n8n.sh <project-name>

# 4. Check n8n for publishing workflow status
#    http://127.0.0.1:5678/ (requires SSH tunnel)
```

### Using API-Based Tools Instead of ComfyUI

If ComfyUI models are unavailable, Claude Code can use:

- **Gemini Omni** (`tools/video/gemini_omni_video.py`) — Via 9Router AG provider
- **Grok Video** (`tools/video/grok_video.py`) — Via 9Router
- **OpenAI Image** (`tools/graphics/openai_image.py`) — Via 9Router

## Recovery Scenarios

### Filesystem Corruption

```bash
# GPU node
ssh openmontage-gpu
sudo touch /forcefsck
sudo reboot
# System will run fsck on boot, then remount rw
```

### Docker Not Starting

```bash
# Check Docker daemon
sudo systemctl status docker
sudo journalctl -u docker -n 50

# Restart Docker
sudo systemctl restart docker

# Then restart services
docker compose -f /opt/openmontage/docker-compose.automation.yml up -d
```

### 9Router Down

If the 9Router at 10.20.10.133:20128 is unreachable:

```bash
# Check local proxy
curl -s http://10.20.10.133:20128/v1/models | head

# Fall back to direct API (native mode)
unset ANTHROPIC_BASE_URL
# This uses the default api.openai.com with ChatGPT+ subscription
codex
```

### Complete Rebuild

To rebuild everything from scratch:

```bash
# DEV
cd /opt/openmontage
git pull origin production
pip install -e .
docker compose -f docker-compose.automation.yml up -d

# GPU
ssh openmontage-gpu
cd /opt/openmontage-gpu/comfyui
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart openmontage-comfyui.service
```
