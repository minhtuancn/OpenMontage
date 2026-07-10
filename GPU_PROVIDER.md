# GPU Provider Documentation

## Overview

The Remote GPU Provider allows OpenMontage to offload GPU-intensive tasks to a dedicated GPU compute node (10.20.10.210).

## Provider Files

Located in `tools/providers/remote_gpu/`:

- `__init__.py` - Package initialization
- `client.py` - HTTP client for GPU node API
- `tts.py` - Text-to-Speech via edge-tts
- `transcribe.py` - Speech-to-Text via faster-whisper
- `image.py` - Image generation via diffusers

## Configuration

Set these in `.env`:

```env
REMOTE_GPU_ENABLED=true
REMOTE_GPU_BASE_URL=http://10.20.10.210:8750
REMOTE_GPU_TIMEOUT=1800
REMOTE_GPU_MAX_RETRIES=2
REMOTE_GPU_SHARED_SECRET=
REMOTE_GPU_SSH_HOST=openmontage-gpu
```

## Fallback Behavior

Each provider declares its fallback chain:

| Provider | Fallback Tools | Type |
|----------|---------------|------|
| TTS | piper_tts, openai_tts, google_tts, elevenlabs_tts | Optional |
| Whisper | dashscope_asr, openai_whisper | Optional |
| Image Gen | flux_image, openai_image, google_imagen | Optional |

When the GPU node is offline, the pipeline automatically uses fallback providers.

## GPU API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Service health check |
| GET | /gpu | Detailed GPU info |
| POST | /v1/tts | Text-to-Speech |
| POST | /v1/transcribe | Speech-to-Text |
| POST | /v1/image/generate | Image generation |
| GET | /v1/jobs | List jobs |
| GET | /v1/jobs/{id} | Job status |
| GET | /v1/jobs/{id}/result | Get result file |

## Adding a New Provider

1. Create a new file in `tools/providers/remote_gpu/`
2. Create a `BaseTool` subclass with `capability`, `provider`, `fallback_tools`
3. Add the GPU API endpoint in `/opt/openmontage-gpu/services/gpu_api.py`
4. Restart GPU service: `systemctl restart openmontage-gpu-api`
