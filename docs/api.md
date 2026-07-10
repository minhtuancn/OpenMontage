# API Reference

## Backlot API

Backlot runs on `http://10.20.10.103:4750/`.

### Health Check

```
GET /
```

Returns HTML page confirming the server is running.

---

### List Projects

```
GET /api/projects
```

**Response:**
```json
{
  "projects": ["animated-explainer", "demos"],
  "count": 2
}
```

---

### Get Project Status

```
GET /api/projects/{name}
```

**Response:**
```json
{
  "name": "animated-explainer",
  "status": "complete",
  "files": ["output/render.mp4", "output/thumbnail.png"],
  "created": "2026-07-10T01:15:00Z"
}
```

---

### Publish Notification

```
POST /api/publish
```

**Body:**
```json
{
  "renders": [
    {
      "project": "animated-explainer",
      "file": "output/render.mp4",
      "path": "/opt/openmontage/projects/animated-explainer/output/render.mp4"
    }
  ],
  "source": "n8n"
}
```

**Response:**
```json
{
  "status": "received",
  "count": 1
}
```

---

## ComfyUI API

ComfyUI runs on `http://10.20.10.210:8188/`.

### System Stats

```
GET /system_stats
```

**Response:**
```json
{
  "system": {
    "os": "linux",
    "ram_total": 20962091008,
    "ram_free": 11631198208,
    "comfyui_version": "0.27.0"
  }
}
```

### Queue Prompt

```
POST /prompt
```

**Body:** ComfyUI workflow JSON with `{ "prompt": {...}, "client_id": "..." }`

**Response:**
```json
{
  "prompt_id": "abc-123",
  "number": 1,
  "node_errors": []
}
```

### Get Image

```
GET /view?filename={filename}&type=output&subfolder=
```

Returns the generated image file.

### Get History

```
GET /history/{prompt_id}
```

Returns the execution history and output metadata.

---

## n8n API

n8n runs on `http://127.0.0.1:5678/` (localhost only).

### Health

```
GET /healthz
```

**Response:** `{"status":"ok"}`

### Webhook Endpoint

```
POST /webhook/openmontage-publish
```

**Body:**
```json
{
  "project": "animated-explainer",
  "file": "/opt/openmontage/projects/.../output/render.mp4",
  "file_size": 12345678,
  "file_type": "video/mp4",
  "mtime": 1689000000,
  "source": "openmontage-cli"
}
```

**Response:** `201 Created`

### Import Workflow

```
POST /rest/workflows
```

**Authentication:** Cookie-based (login first via `/rest/login`).

**Body:** Full n8n workflow JSON (nodes + connections).

### List Workflows

```
GET /rest/workflows
```

**Response:** Array of workflow objects with `id`, `name`, `active` status.

---

## Python Tool APIs (Internal)

These are CLI tools used by Claude Code via the 9Router agent.

### ComfyUIImage

**File:** `tools/graphics/comfyui_image.py`

Generates images using ComfyUI on the GPU node.

```python
from tools.graphics.comfyui_image import ComfyUIImage

result = await ComfyUIImage().generate(
    prompt="A cinematic wide shot of a futuristic city",
    workflow="wan2.1",  # or "sdxl", "ltx-video"
    width=1024,
    height=576
)
```

### ComfyUIVideo

**File:** `tools/video/comfyui_video.py`

Generates videos using ComfyUI's video models.

```python
from tools.video.comfyui_video import ComfyUIVideo

result = await ComfyUIVideo().generate(
    prompt="A serene waterfall in a bamboo forest",
    duration=5,
    fps=16,
    model="wan2.1-t2v-1.3b"
)
```

### Available Workflow Templates

| Workflow | Type | Model Required |
|----------|------|----------------|
| `wan2.1` | Text-to-Video | Wan 2.1 1.3B |
| `ltx-video` | Text-to-Video | LTX-Video 0.9.5 |
| `sdxl` | Text-to-Image | SDXL 1.0 |

Workflow JSONs: `tools/_comfyui/workflows/`

---

## Claude 9Router API

The 9Router at `10.20.10.133:20128/v1` provides OpenAI-compatible API for Anthropic models.

### Models

```
GET /v1/models
```

Returns list of all available models including:
- `claude-sonnet-4-6` (recommended for general use)
- `claude-opus-4-8` (heavy reasoning)
- `sonnet-codex` (optimized for Codex CLI)
- `ag/gemini-3-flash-agent` (Gemini via AG)
- `gc/gemini-3.1-pro-preview` (Google Gemini Pro)

### Chat Completions

```
POST /v1/chat/completions
```

**Headers:**
```
Authorization: Bearer sk-fcf5f1bbd05497aa-nthcqa-c324dad5
Content-Type: application/json
```

**Body:**
```json
{
  "model": "claude-sonnet-4-6",
  "messages": [{"role": "user", "content": "Hello"}],
  "max_tokens": 4096
}
```
