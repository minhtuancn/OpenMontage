# OpenMontage Two-Node Deployment

## Architecture

```
┌─────────────────────────────────┐     ┌─────────────────────────────────┐
│   DEV / CONTROL NODE            │     │   GPU / COMPUTE NODE            │
│   10.20.10.103                  │     │   10.20.10.210                  │
│                                 │     │                                 │
│   Roles:                        │     │   Roles:                        │
│   - Source code management      │     │   - GPU compute (CUDA)          │
│   - Development & orchestration │     │   - TTS (edge-tts)              │
│   - Remotion rendering (CPU)    │     │   - Speech-to-text (Whisper)    │
│   - Backlot storyboard          │     │   - Image generation (diffusers)│
│   - FFmpeg video processing     │     │   - AI inference                │
│   - Git / CI pipeline           │     │                                 │
│                                 │     │   GPU: RTX 3060 (12GB VRAM)     │
│                                 │     │   OS: Ubuntu 22.04              │
│   OS: Ubuntu 24.04              │     │                                 │
│   RAM: 10GB, CPU: 10 vCores     │     │   RAM: 19GB, CPU: 12 Cores     │
└─────────────────────────────────┘     └─────────────────────────────────┘
         │                                        │
         └────────── LAN (10.20.10.0/24) ─────────┘
                    SSH + HTTP API (port 8750)
```

## Communication

- DEV → GPU: HTTP API at `http://10.20.10.210:8750` (with optional shared secret)
- DEV → GPU: SSH via `ssh openmontage-gpu` (key-based auth)
- GPU → DEV: Not initiated (DEV always initiates)

## Directory Structure

### DEV Machine
- `/opt/openmontage/` - Source code (Git repository)
- `/srv/openmontage/projects/` - Video projects
- `/srv/openmontage/cache/` - Cache files
- `/srv/openmontage/logs/` - Application logs
- `/srv/openmontage/models/` - AI models
- `/srv/openmontage/shared/` - Shared files (for rsync transfer)
- `/srv/backups/openmontage/` - Backups

### GPU Machine
- `/opt/openmontage-gpu/services/` - GPU API services
- `/opt/openmontage-gpu/models/` - AI models
- `/opt/openmontage-gpu/cache/` - Cache
- `/opt/openmontage-gpu/logs/` - GPU service logs
- `/srv/openmontage-gpu/jobs/` - Incoming jobs
- `/srv/openmontage-gpu/results/` - Completed job results

## Ports

| Port | Machine | Service | Access |
|------|---------|---------|--------|
| 22 | Both | SSH | Any (firewalled) |
| 8750 | GPU | GPU API | Only from 10.20.10.103 |
| 4750 | DEV | Backlot | 127.0.0.1 only (SSH tunnel) |

## Services

### DEV Machine
- `openmontage-backlot.service` - Backlot storyboard (user service)

### GPU Machine
- `openmontage-gpu-api.service` - GPU compute API (system service)
