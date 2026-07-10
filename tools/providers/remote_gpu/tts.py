"""Remote GPU TTS provider using GPU node's edge-tts."""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
    ResourceProfile,
)
from tools.providers.remote_gpu.client import (
    RemoteGPUClient,
    RemoteGPUError,
    get_settings,
)

logger = __import__("logging").getLogger("remote_gpu.tts")


class RemoteGPTTS(BaseTool):
    """Text-to-Speech via remote GPU node (edge-tts with Vietnamese support).

    Falls back to local Piper TTS when the GPU node is unavailable.
    """

    name = "remote_gpu_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "remote_gpu"
    stability = ToolStability.BETA
    runtime = ToolRuntime.API
    fallback = "piper_tts"
    fallback_tools = ["piper_tts", "openai_tts", "google_tts", "elevenlabs_tts"]
    dependencies = []

    capabilities = ["text_to_speech", "multilingual", "vietnamese_tts"]
    supports = {
        "vietnamese": True,
        "languages": ["vi", "en", "ja", "ko", "zh", "fr", "de", "es"],
        "offline_fallback": True,
    }
    best_for = [
        "Vietnamese text-to-speech",
        "GPU-accelerated TTS",
        "Multi-language narration",
    ]
    not_good_for = [
        "Very long-form content (>30 min)",
        "Voice cloning",
    ]

    resource_profile = ResourceProfile(
        cpu_cores=0,
        ram_mb=0,
        vram_mb=0,
        disk_mb=50,
        network_required=True,
    )

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to synthesize"},
            "voice": {
                "type": "string",
                "description": "Voice to use. Default vi-VN-HoaiMyNeural for Vietnamese.",
                "default": "vi-VN-HoaiMyNeural",
            },
            "speed": {
                "type": "number",
                "description": "Speaking speed (0.5-2.0)",
                "default": 1.0,
            },
            "output_format": {
                "type": "string",
                "description": "Output audio format",
                "default": "wav",
                "enum": ["wav", "mp3", "ogg"],
            },
            "output_path": {
                "type": "string",
                "description": "Local path to save the audio file",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "duration_seconds": {"type": "number"},
            "voice": {"type": "string"},
        },
    }

    def get_status(self):
        """Check if GPU node is reachable."""
        if not get_settings().enabled:
            return __import__("tools.base_tool", fromlist=["ToolStatus"]).ToolStatus.UNAVAILABLE
        try:
            client = RemoteGPUClient()
            client.check_health()
            return __import__("tools.base_tool", fromlist=["ToolStatus"]).ToolStatus.AVAILABLE
        except Exception:
            return __import__("tools.base_tool", fromlist=["ToolStatus"]).ToolStatus.UNAVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        """Execute TTS on remote GPU node."""
        text = inputs.get("text", "")
        if not text:
            return ToolResult(success=False, error="text is required")

        voice = inputs.get("voice", "vi-VN-HoaiMyNeural")
        speed = float(inputs.get("speed", 1.0))
        output_format = inputs.get("output_format", "wav")
        output_path = inputs.get("output_path")

        if not get_settings().enabled:
            return ToolResult(
                success=False,
                error="Remote GPU is disabled. Set REMOTE_GPU_ENABLED=true in .env",
            )

        try:
            client = RemoteGPUClient()
            result = client.tts(text, voice=voice, speed=speed, output_format=output_format)

            if result.get("status") != "completed":
                return ToolResult(
                    success=False,
                    error=f"GPU TTS failed: {result.get('status')}",
                )

            # Download the result file
            output_info = result.get("output", {})
            file_url = output_info.get("file", "")
            duration = output_info.get("duration_seconds", 0)

            if output_path:
                local_path = Path(output_path)
            else:
                output_dir = Path("/srv/openmontage/cache")
                os.makedirs(str(output_dir), exist_ok=True)
                local_path = output_dir / f"gpu_tts_{result['job_id']}.{output_format}"

            # Download from GPU node
            download_url = f"{client.settings.base_url.rstrip('/')}/{file_url.lstrip('/')}"
            resp = client.session.get(download_url, timeout=300)
            with open(str(local_path), "wb") as f:
                f.write(resp.content)

            # Get actual duration via ffprobe
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json",
                     "-show_format", str(local_path)],
                    capture_output=True, text=True, timeout=15,
                )
                import json
                info = json.loads(probe.stdout) if probe.stdout else {}
                actual_duration = float(info.get("format", {}).get("duration", duration))
            except Exception:
                actual_duration = duration

            return ToolResult(
                success=True,
                data={
                    "file_path": str(local_path),
                    "duration_seconds": actual_duration,
                    "voice": voice,
                    "job_id": result.get("job_id"),
                    "provider": "remote_gpu",
                },
                artifacts=[str(local_path)],
            )

        except RemoteGPUError as e:
            logger.warning(f"Remote GPU TTS failed, will use fallback: {e}")
            return ToolResult(
                success=False,
                error=f"Remote GPU TTS unavailable: {e}",
            )
        except Exception as e:
            logger.error(f"Remote GPU TTS error: {e}")
            return ToolResult(
                success=False,
                error=f"Remote GPU TTS error: {e}",
            )
