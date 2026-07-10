# OpenMontage Production Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make OpenMontage fully operational for video production on existing 2-machine LAN (DEV 10.20.10.103, GPU 10.20.10.210) with 9router LLM access, ComfyUI low-VRAM image/video gen, and n8n/Postiz publishing integration.

**Architecture:** OpenMontage agent (Claude Code via 9router) drives production from DEV. GPU-intensive tasks offload to GPU node. ComfyUI provides local image/video generation (low-VRAM workflow). n8n watches renders and calls Postiz API for social scheduling.

**Tech Stack:** OpenMontage (Python/FastAPI/Remotion), ComfyUI (low-VRAM Wan 2.1 1.3B, LTX-Video FP8), n8n, Postiz, Docker, UFW.

---

### Task 1: Commit Backlot + fix openmontage-status

**Files:**
- Modify: `/usr/local/sbin/openmontage-status` (lines 27, 42)

- [ ] **Step 1: Commit Backlot bind change**

```bash
cd /opt/openmontage
git add backlot/__main__.py && git commit -m "fix: bind Backlot to 0.0.0.0 for LAN access"
```

- [ ] **Step 2: Fix status script — systemctl scope**

```bash
sudo sed -i 's/systemctl --user is-active/systemctl is-active/' /usr/local/sbin/openmontage-status
```

- [ ] **Step 3: Fix status script — projects path**

```bash
sudo sed -i 's|/srv/openmontage/projects|/opt/openmontage/projects|' /usr/local/sbin/openmontage-status
```

- [ ] **Step 4: Verify**

```bash
sudo openmontage-status 2>&1 | grep -E "Backlot|project|RUNNING"
```

Expected: `openmontage-backlot: RUNNING`, path `/opt/openmontage/projects`.

---

### Task 2: Configure 9router + agent

**Files:**
- Modify: `/opt/openmontage/.env`, `config.yaml`
- Modify: `/usr/local/bin/openmontage-agent`

- [ ] **Step 1: Add 9router to .env**

```bash
cd /opt/openmontage
cat >> .env << 'EOF'

# 9router proxy for LLM agent
ANTHROPIC_BASE_URL=http://10.20.10.133:20128/v1
ANTHROPIC_API_KEY=sk-fcf5f1bbd05497aa-jntdu0-2727f473
EOF
```

- [ ] **Step 2: Update config.yaml LLM section**

```bash
cd /opt/openmontage
python3 -c "
import yaml
with open('config.yaml') as f: cfg = yaml.safe_load(f)
cfg['llm'] = {'provider': 'anthropic', 'model': 'claude-sonnet-4-6', 'temperature': 0.7, 'max_tokens': 4096}
with open('config.yaml', 'w') as f: yaml.dump(cfg, f, default_flow_style=False)
"
```

- [ ] **Step 3: Update openmontage-agent script**

```bash
sudo tee -a /usr/local/bin/openmontage-agent > /dev/null << 'EOF'

# 9router LLM proxy
export ANTHROPIC_BASE_URL="http://10.20.10.133:20128/v1"
export ANTHROPIC_API_KEY="sk-fcf5f1bbd05497aa-jntdu0-2727f473"
EOF
```

---

### Task 3: Deploy ComfyUI low-VRAM on GPU node

- [ ] **Step 1: Check GPU node prereqs**

```bash
ssh openmontage-gpu '
echo "=== NVIDIA Docker ===" && docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi 2>&1 | head -5 || echo "nvidia-container-toolkit missing"
echo "=== Disk ===" && df -h / | tail -1
echo "=== Python ===" && python3 --version
'
```

If nvidia-container-toolkit is installed and Docker GPU access works, use Docker. Otherwise install natively.

- [ ] **Step 2: Install ComfyUI (native or Docker)**

**Option A — Docker (if nvidia-container-toolkit works):**

```bash
ssh openmontage-gpu '
mkdir -p /opt/openmontage-gpu/comfyui/models
cat > /opt/openmontage-gpu/comfyui/docker-compose.yml << "DOCKER"
services:
  comfyui:
    image: comfyui/comfyui:latest
    ports:
      - "8188:8188"
    volumes:
      - /opt/openmontage-gpu/comfyui/models:/workspace/ComfyUI/models
      - /opt/openmontage-gpu/comfyui/output:/workspace/ComfyUI/output
      - /opt/openmontage-gpu/comfyui/custom_nodes:/workspace/ComfyUI/custom_nodes
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    command: ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
    restart: unless-stopped
DOCKER
'
```

**Option B — Native (if Docker GPU unsupported):**

```bash
ssh openmontage-gpu '
sudo apt-get install -y git python3-pip python3-venv wget
git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /opt/openmontage-gpu/comfyui
cd /opt/openmontage-gpu/comfyui
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu124
pip install xformers
'
```

- [ ] **Step 3: Download low-VRAM models**

Models that fit on RTX 3060 12GB:

| Model | Size | Type | Source |
|-------|------|------|--------|
| Wan 2.1 1.3B t2v | ~2.5GB | Diffusion model | `https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B` |
| LTX-Video 0.9.5 fp8 | ~3GB | Diffusion model | `https://huggingface.co/Lightricks/LTX-Video-0.9.5-fp8` |

Install huggingface-cli and download:

```bash
ssh openmontage-gpu '
cd /opt/openmontage-gpu/comfyui/models
pip install huggingface-hub 2>/dev/null

# Wan 2.1 1.3B text-to-video (fits 12GB easily)
huggingface-cli download Wan-AI/Wan2.1-T2V-1.3B \
  diffusion_pytorch_model.safetensors \
  --local-dir diffusion_models/ 2>&1 || \
echo "WILL FAIL — try ComfyUI Manager UI instead"

# LTX-Video 0.9.5 FP8 (fits 8-12GB)
huggingface-cli download Lightricks/LTX-Video-0.9.5-fp8 \
  ltx-video-2b-0.9.5-fp8.safetensors \
  --local-dir diffusion_models/ 2>&1 || \
echo "Will download via ComfyUI Manager"

echo "Models:"
ls -lh diffusion_models/ 2>&1
'
```

If `huggingface-cli` fails (auth/permissions), use **ComfyUI Manager** workflow: start ComfyUI, open `http://10.20.10.210:8188`, go to Manager → Install Models → search for "Wan 2.1 1.3B" and "LTX-Video 0.9.5".

- [ ] **Step 4: Start ComfyUI**

```bash
ssh openmontage-gpu '
cd /opt/openmontage-gpu/comfyui
# Docker:
# docker compose -f docker-compose.yml up -d
# Or native:
. venv/bin/activate
nohup python main.py --listen 0.0.0.0 --port 8188 > /tmp/comfyui.log 2>&1 &
echo "ComfyUI PID: $!"
'
```

- [ ] **Step 5: Create ComfyUI systemd service on GPU**

```bash
ssh openmontage-gpu 'sudo tee /etc/systemd/system/openmontage-comfyui.service > /dev/null << "EOF"
[Unit]
Description=OpenMontage ComfyUI — low-VRAM image/video generation
After=network.target

[Service]
Type=simple
User=dev
WorkingDirectory=/opt/openmontage-gpu/comfyui
ExecStart=/opt/openmontage-gpu/comfyui/venv/bin/python main.py --listen 0.0.0.0 --port 8188
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable openmontage-comfyui.service
sudo systemctl start openmontage-comfyui.service
'
```

- [ ] **Step 6: Open ComfyUI port in UFW on GPU**

```bash
ssh openmontage-gpu '
sudo ufw allow from 10.20.10.0/24 to any port 8188 proto tcp
sudo ufw status | grep 8188
'
```

- [ ] **Step 7: Add COMFYUI_SERVER_URL to DEV .env**

```bash
cd /opt/openmontage
echo '' >> .env
echo '# ComfyUI remote server' >> .env
echo 'COMFYUI_SERVER_URL=http://10.20.10.210:8188' >> .env
```

- [ ] **Step 8: Verify from DEV**

```bash
curl -s http://10.20.10.210:8188/system_stats 2>&1
```

Expected: JSON response with ComfyUI system stats.

---

### Task 4: Deploy n8n + Postiz on DEV + publish integration

- [ ] **Step 1: Create Docker Compose for n8n + Postiz**

```yaml
# /opt/openmontage-gpu/docker-compose.automation.yml on DEV (not GPU)
```

Wait — n8n/Postiz go on DEV, not GPU. Let me put them in `/opt/openmontage/`.

```bash
cat > /opt/openmontage/docker-compose.automation.yml << "DOCKEREOF"
version: "3.8"
services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    ports:
      - "127.0.0.1:5678:5678"
    volumes:
      - /srv/openmontage/n8n:/home/node/.n8n
      - /opt/openmontage/projects:/opt/openmontage/projects:ro
    environment:
      - N8N_SECURE_COOKIE=false
      - N8N_METRICS=false
    restart: unless-stopped

  postiz:
    image: ghcr.io/postiz-app/postiz:latest
    container_name: postiz
    ports:
      - "127.0.0.1:3001:3000"
    volumes:
      - /srv/openmontage/postiz:/data
    environment:
      - DATABASE_URL=sqlite:///data/postiz.db
      - JWT_SECRET=changeme-in-production
      - NODE_ENV=production
    restart: unless-stopped
DOCKEREOF
```

- [ ] **Step 2: Create data directories**

```bash
mkdir -p /srv/openmontage/n8n /srv/openmontage/postiz
```

- [ ] **Step 3: Start services**

```bash
cd /opt/openmontage
docker compose -f docker-compose.automation.yml up -d
sleep 5
docker ps | grep -E "n8n|postiz"
```

- [ ] **Step 4: Open UFW ports for n8n + Postiz**

```bash
sudo ufw allow from 10.20.10.0/24 to any port 5678 proto tcp
sudo ufw allow from 10.20.10.0/24 to any port 3001 proto tcp
sudo ufw status | grep -E "5678|3001"
```

- [ ] **Step 5: Verify services**

```bash
# n8n
curl -s http://127.0.0.1:5678/healthz && echo ' n8n OK'
# Postiz
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3001/ && echo ' Postiz OK'
```

- [ ] **Step 6: Create n8n integration workflow (importable JSON)**

The n8n workflow watches for new renders and publishes via Postiz:

**Workflow design (create in n8n UI):**
1. **Cron trigger** — every 5 minutes
2. **Execute Command** — `find /opt/openmontage/projects -name "*.mp4" -newer /tmp/n8n_watch_stamp -type f`
3. **Code** — parse file list, extract project name/caption
4. **HTTP Request** — POST to Postiz API:
   - URL: `http://postiz:3000/api/posts` (adjust for Postiz API version)
   - Headers: `Authorization: Bearer {{Postiz API key}}`
   - Body: `{ "title": "{{$json.title}}", "content": "New video: {{$json.title}}", "mediaUrls": ["{{$json.filePath}}"] }`
5. **Execute Command** — `touch /tmp/n8n_watch_stamp` (update timestamp)

Importable workflow JSON:

```bash
cat > /opt/openmontage/n8n-workflow-openmontage-publish.json << "WFEOF"
{
  "name": "OpenMontage Render → Postiz Publish",
  "nodes": [
    {
      "name": "Every 5 min",
      "type": "n8n-nodes-base.cron",
      "position": [250, 300],
      "parameters": { "triggerTimes": { "item": [{ "mode": "everyMinute", "value": 5 }] } }
    },
    {
      "name": "Find new renders",
      "type": "n8n-nodes-base.executeCommand",
      "position": [450, 300],
      "parameters": {
        "command": "find",
        "commandArguments": "/opt/openmontage/projects -name *.mp4 -newer /tmp/n8n_watch_stamp -type f",
        "options": {}
      }
    },
    {
      "name": "Parse output",
      "type": "n8n-nodes-base.code",
      "position": [650, 300],
      "parameters": {
        "language": "javaScript",
        "code": "const lines = $input.first().json.stdout.trim().split('\\n').filter(Boolean);\nreturn lines.map(p => ({\n  json: {\n    filePath: p,\n    fileName: p.split('/').pop(),\n    projectId: p.replace('/opt/openmontage/projects/', '').split('/')[0],\n    title: p.split('/').pop().replace('.mp4', '').replace(/-/g, ' ')\n  }\n}));"
      }
    },
    {
      "name": "Post to Postiz",
      "type": "n8n-nodes-base.httpRequest",
      "position": [850, 300],
      "parameters": {
        "method": "POST",
        "url": "http://postiz:3000/api/posts",
        "authentication": "none",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            { "name": "title", "value": "={{$json.title}}" },
            { "name": "content", "value": "={{'New render from OpenMontage: ' + $json.title}}" },
            { "name": "scheduledAt", "value": "={{new Date(Date.now() + 7200000).toISOString()}}" }
          ]
        }
      }
    },
    {
      "name": "Update stamp",
      "type": "n8n-nodes-base.executeCommand",
      "position": [850, 500],
      "parameters": {
        "command": "touch",
        "commandArguments": "/tmp/n8n_watch_stamp"
      }
    }
  ],
  "connections": {
    "Every 5 min": { "main": [[ { "node": "Find new renders", "type": "main", "index": 0 } ]] },
    "Find new renders": { "main": [[ { "node": "Parse output", "type": "main", "index": 0 } ]] },
    "Parse output": { "main": [[ { "node": "Post to Postiz", "type": "main", "index": 0 } ]] },
    "Post to Postiz": { "main": [[ { "node": "Update stamp", "type": "main", "index": 0 } ]] }
  }
}
WFEOF
```

Import this JSON into n8n at `http://10.20.10.103:5678` → Workflows → Import.

- [ ] **Step 7: Provide Postiz setup URL**

```bash
echo "=== n8n ==="
echo "  URL: http://10.20.10.103:5678"
echo "  First visit: create admin account"
echo "  Import workflow: n8n-workflow-publish-to-social.json"
echo ""
echo "=== Postiz ==="
echo "  URL: http://10.20.10.103:3001"
echo "  First visit: create admin account"
echo "  Connect social accounts (YouTube, TikTok, Instagram, etc.)"
```

---

### Task 5: Run full production test

- [ ] **Step 1: Launch agent in tmux**

```bash
openmontage-agent
```

This opens tmux session `openmontage` at `/opt/openmontage` with .venv + 9router env vars.

- [ ] **Step 2: Inside tmux, run Claude Code**

```bash
claude
```

Then instruct Claude:
> "Make a 60-second animated explainer video about [topic]. Use the animated-explainer pipeline. Use remote GPU for TTS and image generation. Use Backlot to show progress."

- [ ] **Step 3: Verify Backlot live board**

Open `http://10.20.10.103:4750/` in browser. The production should appear as a live board.

- [ ] **Step 4: Verify GPU API usage**

```bash
ssh openmontage-gpu "journalctl -u openmontage-gpu-api.service --no-pager -n 20"
```

Should show TTS and image gen requests.

- [ ] **Step 5: Verify render output**

```bash
ls -la /opt/openmontage/projects/*/renders/*.mp4 2>&1 | tail -5
```

Should list generated MP4 files.

---

## Order of Execution

1. **Task 1** (commit + fix) — 2 min, no deps
2. **Task 2** (9router config) — 2 min, no deps
3. **Task 3** (ComfyUI deploy on GPU) — 15 min, parallel with Task 4
4. **Task 4** (n8n + Postiz on DEV) — 10 min, parallel with Task 3
5. **Task 5** (production test) — 30 min, after all above

Total estimated time: ~60 min
