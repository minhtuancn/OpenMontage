# OpenMontage Production Setup

**Date:** 2026-07-10  
**Author:** OpenMontage team  
**Status:** Design (pending review)

---

## Motivation

OpenMontage is deployed across two LAN machines (DEV 10.20.10.103, GPU 10.20.10.210)
but has never been exercised end-to-end. This spec covers the remaining work to
make the system directly usable for video production on existing resources.

---

## 1. Commit + Fix Status Script

### Backlot bind address
File `backlot/__main__.py` line 85: changed `host="127.0.0.1"` → `host="0.0.0.0"`.
Currently uncommitted on `production` branch.

### openmontage-status fixes
File `/usr/local/sbin/openmontage-status`:

1. **Service check scope** (line 26-28): uses `systemctl --user is-active` but
   `openmontage-backlot.service` is a system service. Change to `systemctl is-active`.
2. **Projects path** (line 42): hardcodes `/srv/openmontage/projects` but actual
   projects are at `/opt/openmontage/projects`. Update path.

---

## 2. LLM Configuration + Full Production Test

### 9router proxy credentials
- **LAN URL:** `http://10.20.10.133:20128/v1`
- **Public URL:** `https://9router.go7s.net/v1`
- **API key:** (user-provided, stored in `.env` only)

### Configuration
- `.env`: `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL=http://10.20.10.133:20128/v1`
- `config.yaml`: `llm.provider: anthropic`, `llm.model: claude-sonnet-4-6`
- `openmontage-agent` script exports these vars before launching tmux

### Test production: animated-explainer pipeline
Launch `claude` (Claude Code) in tmux session at `/opt/openmontage`, configured
to use 9router as its API endpoint. Agent reads the `animated-explainer` pipeline
manifest and drives it end-to-end:

| Stage | Tools exercised | Provider |
|---|---|---|
| research | web search (if available) | agent LLM |
| script | agent writing | agent LLM |
| scene_plan | planning | agent LLM |
| assets | tts_selector → RemoteGPTTS | remote GPU |
| assets | image_selector → RemoteGPUImageGen | remote GPU |
| compose | video_compose → Remotion | DEV local |
| publish | publish tools | n/a |

**Backlot live board:** `http://10.20.10.103:4750/p/<project-id>`

---

## 3. ComfyUI Low-VRAM + OpenMontage Adapter

### GPU node deployment
- **RTX 3060 12GB** — cannot run WAN 2.2 14B (needs ~16GB).
- **Low-VRAM profile:** Wan 2.1 1.3B + LTX-Video FP8.
- **Docker:** ComfyUI container, port `8188`, bind `0.0.0.0`.
  UFW allow `8188/tcp` from `10.20.10.0/24` (same pattern as GPU API).
- **Disk:** 39GB free on GPU — enough for models (~8-10GB total).

### OpenMontage adapter tools
Per `docs/comfyui-adapter-plan.md`:

| Component | File | Purpose |
|---|---|---|
| Shared client | `tools/_comfyui/client.py` | ComfyUI REST API client (submit/poll/download) |
| Metadata | `tools/_comfyui/metadata.py` | Setup offer, model stack helpers |
| Image tool | `tools/graphics/comfyui_image.py` | `capability=image_generation`, `provider=comfyui` |
| Video tool | `tools/video/comfyui_video.py` | `capability=video_generation`, `provider=comfyui` |
| Workflows | `tools/_comfyui/workflows/*.json` | Low-VRAM templates |
| Register | `tools/providers/__init__.py` | Import + export new providers |
| Env | `.env` | `COMFYUI_SERVER_URL=http://10.20.10.210:8188` |

*Note: `tools/_comfyui/client.py` and `tools/_comfyui/metadata.py` scaffolding
already exists; the image/video tool files and workflows need creation.*

### Verification
- `curl http://10.20.10.210:8188/system_stats` → OK
- OpenMontage tool registry shows `comfyui_image`, `comfyui_video` as `AVAILABLE`
- Generate one image + one short video (few seconds) from DEV

---

## 4. n8n + Postiz + OpenMontage Integration

### Deployment (DEV machine, Docker)

| Service | Port | Image | Purpose |
|---|---|---|---|
| n8n | 5678 | `n8nio/n8n` | Workflow automation, webhook receiver |
| Postiz | 3001 | `ghcr.io/postiz-app/postiz` | Social media scheduling |

*Port 3000 is occupied on GPU node → both services on DEV. Postiz uses 3001.*

### Integration approach: file-polling (decoupled)

**Chosen approach** (over direct callback or n8n-triggers-agent):

```
OpenMontage publish stage
  → writes render.mp4 + publish_log.json to projects/<id>/renders/
  → n8n cron/polling workflow detects new file
  → n8n POST to Postiz API: schedule post(mp4, caption, platforms)
  → Postiz handles actual social publishing at scheduled time
```

**No changes to OpenMontage core code.** n8n watches filesystem via standard
Watch node or cron; Postiz REST API via HTTP Request node.

### n8n workflow
1. **Trigger:** Poll `projects/*/renders/` for new `.mp4` files (every 5 min)
2. **Read metadata:** Parse `publish_log.json` or sibling for title/caption
3. **Ship to Postiz:** POST to Postiz API: create scheduled post with video

### Postiz configuration
- Connect social accounts (YouTube, TikTok, Instagram, etc.) via Postiz UI
- Schedule posts or queue for manual review

---

## Order of Execution

| Order | Task | Est. time | Dependencies |
|---|---|---|---|
| 1 | Commit + fix status script | 5 min | None |
| 2 | Configure 9router + test full production | 30 min | Task 1 |
| 3 | Deploy ComfyUI + adapter | 90 min | Task 2 (parallel OK) |
| 4 | Deploy n8n + Postiz + integrate | 45 min | Tasks 1-3 done |

---

## Security

- **9router key:** `.env` (chmod 600, gitignored). Never committed.
- **GPU API:** `GPU_API_SECRET` should be set in `/etc/default/openmontage-gpu`
  (currently empty). Post-deployment hardening.
- **ComfyUI:** Bind to `127.0.0.1` by default; expose to LAN only if needed.
- **n8n/Postiz:** Local access only; expose via SSH tunnel or auth proxy.

---

## Verification

1. `systemctl status openmontage-backlot` → active; `http://10.20.10.103:4750/` → renders HTML
2. `openmontage-status` → Backlot shows RUNNING, path correct
3. Pipeline test produces a playable `.mp4` in `projects/<id>/renders/`
4. `curl http://10.20.10.210:8188/system_stats` → ComfyUI alive
5. OpenMontage registry shows ComfyUI providers as `AVAILABLE` or `DEGRADED` (depends on models)
6. `http://10.20.10.103:5678` → n8n login
7. `http://10.20.10.103:3001` → Postiz login
