"""
Remote GPU Provider for OpenMontage.

Provides GPU-accelerated services (TTS, transcription, image generation)
by calling the GPU node API at http://10.20.10.210:8750.

Configuration:
  REMOTE_GPU_ENABLED=true
  REMOTE_GPU_BASE_URL=http://10.20.10.210:8750
  REMOTE_GPU_TIMEOUT=1800
  REMOTE_GPU_MAX_RETRIES=2
  REMOTE_GPU_SHARED_SECRET=
"""

from tools.providers.remote_gpu.client import RemoteGPUClient, get_settings
from tools.providers.remote_gpu.tts import RemoteGPTTS
from tools.providers.remote_gpu.transcribe import RemoteGPUWhisper
from tools.providers.remote_gpu.image import RemoteGPUImageGen

__all__ = [
    "RemoteGPUClient",
    "get_settings",
    "RemoteGPTTS",
    "RemoteGPUWhisper",
    "RemoteGPUImageGen",
]
