# OpenMontage — Production AI Video Pipeline

**OpenMontage** is a production-grade AI video generation pipeline. It orchestrates LLMs (Claude via 9Router), local ComfyUI image/video generation on a GPU node, and n8n-based publishing workflows.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  9Router     │────▶│  DEV Server  │────▶│  GPU Node       │
│  (Anthropic  │     │  10.20.10.103│     │  10.20.10.210   │
│   Claude)    │     │              │     │                 │
│  :9999       │     │  Backlot    │     │  ComfyUI       │
│              │     │  :4750      │     │  :8188         │
│              │     │  n8n       │     │  RTX 3060 12GB │
│              │     │  :5678     │     │                 │
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │
                    ┌──────▼───────┐
                    │  Publishing  │
                    │  (YouTube,   │
                    │   TikTok...) │
                    └──────────────┘
```

## Components

| Component | Machine | Port | Status |
|-----------|---------|------|--------|
| **Backlot** | DEV | 4750 | Systemd service — HTTP Storyboard API |
| **ComfyUI** | GPU | 8188 | Low-VRAM image/video gen (RTX 3060) |
| **n8n** | DEV | 5678 (localhost) | Workflow automation & publishing |
| **9Router** | LAN | 9999 | Claude API proxy (Anthropic models) |
| **UFW** | Both | — | LAN-only access (10.20.10.0/24) |

## Quick Start

```bash
# 1. SSH into DEV
ssh dev@10.20.10.103

# 2. Launch the Claude agent with 9Router
openmontage-agent

# 3. Inside tmux, Claude Code will have full tool access
claude
```

## Architecture

### DEV Machine (10.20.10.103)
- **Backlot**: Python FastAPI web server for storyboard/project management
- **n8n**: Docker container for automation workflows
- **Projects**: `/opt/openmontage/projects/` — all renders and outputs
- **9Router**: Proxy running at 10.20.10.133:20128 (external) or :9999 (local)

### GPU Machine (10.20.10.210)
- **ComfyUI**: Native Python (venv) deployment with low-VRAM optimizations
- **Models**: `/opt/openmontage-gpu/comfyui/models/`
- **Systemd**: `openmontage-comfyui.service`

### Network Security
- UFW active on both machines
- LAN-only access (10.20.10.0/24)
- n8n bound to localhost only

## Setup

See [docs/setup-guide.md](docs/setup-guide.md) for full setup instructions.

## API

See [docs/api.md](docs/api.md) for API reference.

## Operations

See [docs/operations.md](docs/operations.md) for day-to-day operations.

## Git Branches

| Branch | Purpose |
|--------|---------|
| `production` | Deployed on DEV server |
| `develop` | Active development |
| `custom` | Custom modifications |
| `upstream-main` | Original upstream repo |

## Troubleshooting

**GPU filesystem read-only:**
```bash
# The root filesystem has an ext4 journal error
# Fix requires reboot + fsck:
sudo touch /forcefsck
sudo reboot
```

**Model downloads failing:**
```bash
# Filesystem must be writable first, then:
ssh openmontage-gpu 'sudo mount -o remount,rw /'
ssh openmontage-gpu 'pip install huggingface-hub && \
  huggingface-cli download Wan-AI/Wan2.1-T2V-1.3B \
  --local-dir /opt/openmontage-gpu/comfyui/models/Wan2.1-T2V-1.3B'
```

**n8n not responding:**
```bash
docker compose -f /opt/openmontage/docker-compose.automation.yml restart
```

## License

See [LICENSE](LICENSE) file.
