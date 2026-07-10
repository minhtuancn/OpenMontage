"""Remote GPU Whisper transcription provider."""

import os
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

logger = __import__("logging").getLogger("remote_gpu.transcribe")


class RemoteGPUWhisper(BaseTool):
    """Speech-to-text via remote GPU node (faster-whisper with CUDA).

    Provides transcription, SRT/VTT generation.
    Falls back to cloud APIs or CPU whisper when GPU node is unavailable.
    """

    name = "remote_gpu_whisper"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "transcribe"
    provider = "remote_gpu"
    stability = ToolStability.BETA
    runtime = ToolRuntime.API
    fallback = None
    fallback_tools = ["dashscope_asr", "openai_whisper"]
    dependencies = ["cmd:ffprobe"]

    capabilities = [
        "speech_to_text",
        "word_timestamps",
        "multilingual",
        "vietnamese_asr",
        "srt_generation",
        "vtt_generation",
    ]
    supports = {
        "languages": ["vi", "en", "ja", "zh", "fr", "de", "es", "ko"],
        "word_timestamps": True,
        "output_formats": ["txt", "srt", "vtt", "json"],
        "offline_fallback": True,
    }
    best_for = [
        "Vietnamese speech-to-text",
        "GPU-accelerated transcription",
        "Word-level timestamps",
    ]
    not_good_for = [
        "Real-time streaming transcription",
        "Speaker diarization (not implemented)",
    ]

    resource_profile = ResourceProfile(
        cpu_cores=0,
        ram_mb=0,
        vram_mb=0,
        disk_mb=500,
        network_required=True,
    )

    input_schema = {
        "type": "object",
        "required": ["audio_path"],
        "properties": {
            "audio_path": {
                "type": "string",
                "description": "Path to audio/video file to transcribe",
            },
            "language": {
                "type": "string",
                "description": "Language code (vi, en, etc.)",
                "default": "vi",
            },
            "model_size": {
                "type": "string",
                "description": "Whisper model size",
                "default": "base",
                "enum": ["tiny", "base", "small", "medium", "large-v2", "large-v3"],
            },
            "word_timestamps": {
                "type": "boolean",
                "description": "Include word-level timestamps",
                "default": True,
            },
            "output_dir": {
                "type": "string",
                "description": "Directory to save output files",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "segments": {"type": "array"},
            "srt_path": {"type": "string"},
            "vtt_path": {"type": "string"},
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
        """Transcribe audio via remote GPU node."""
        audio_path = inputs.get("audio_path", "")
        if not audio_path:
            return ToolResult(success=False, error="audio_path is required")

        if not Path(audio_path).exists():
            return ToolResult(
                success=False, error=f"Audio file not found: {audio_path}"
            )

        language = inputs.get("language", "vi")
        model_size = inputs.get("model_size", "base")
        word_timestamps = bool(inputs.get("word_timestamps", True))
        output_dir = inputs.get("output_dir", "")

        if not get_settings().enabled:
            return ToolResult(
                success=False,
                error="Remote GPU is disabled. Set REMOTE_GPU_ENABLED=true in .env",
            )

        try:
            client = RemoteGPUClient()
            result = client.transcribe(
                audio_path,
                language=language,
                model_size=model_size,
                word_timestamps=word_timestamps,
            )

            if result.get("status") != "completed":
                return ToolResult(
                    success=False,
                    error=f"GPU transcription failed: {result.get('status')}",
                )

            # Save local copies of transcript files
            if output_dir:
                save_dir = Path(output_dir)
            else:
                save_dir = Path("/srv/openmontage/cache")
            os.makedirs(str(save_dir), exist_ok=True)

            base_name = f"transcript_{result.get('job_id', 'unknown')}"

            # Save text
            text = result.get("text", "")
            txt_path = save_dir / f"{base_name}.txt"
            with open(str(txt_path), "w", encoding="utf-8") as f:
                f.write(text)

            artifacts = [str(txt_path)]

            # Download SRT if available
            srt_url = result.get("files", {}).get("srt", "")
            if srt_url:
                srt_path = save_dir / f"{base_name}.srt"
                try:
                    download_url = (
                        f"{client.settings.base_url.rstrip('/')}/{srt_url.lstrip('/')}"
                    )
                    resp = client.session.get(download_url, timeout=60)
                    with open(str(srt_path), "wb") as f:
                        f.write(resp.content)
                    artifacts.append(str(srt_path))
                except Exception as e:
                    logger.warning(f"Could not download SRT: {e}")

            # Download VTT if available
            vtt_url = result.get("files", {}).get("vtt", "")
            if vtt_url:
                vtt_path = save_dir / f"{base_name}.vtt"
                try:
                    download_url = (
                        f"{client.settings.base_url.rstrip('/')}/{vtt_url.lstrip('/')}"
                    )
                    resp = client.session.get(download_url, timeout=60)
                    with open(str(vtt_path), "wb") as f:
                        f.write(resp.content)
                    artifacts.append(str(vtt_path))
                except Exception as e:
                    logger.warning(f"Could not download VTT: {e}")

            return ToolResult(
                success=True,
                data={
                    "text": text,
                    "segments": result.get("segments", []),
                    "language": result.get("language", language),
                    "language_probability": result.get("language_probability", 0),
                    "word_count": result.get("word_count", 0),
                    "txt_path": str(txt_path) if txt_path.exists() else None,
                    "srt_path": str(
                        save_dir / f"{base_name}.srt"
                    ) if srt_url else None,
                    "vtt_path": str(
                        save_dir / f"{base_name}.vtt"
                    ) if vtt_url else None,
                    "job_id": result.get("job_id"),
                    "provider": "remote_gpu",
                },
                artifacts=artifacts,
            )

        except RemoteGPUError as e:
            logger.warning(f"Remote GPU Whisper failed, will use fallback: {e}")
            return ToolResult(
                success=False,
                error=f"Remote GPU Whisper unavailable: {e}",
            )
        except Exception as e:
            logger.error(f"Remote GPU Whisper error: {e}")
            return ToolResult(
                success=False,
                error=f"Remote GPU Whisper error: {e}",
            )
