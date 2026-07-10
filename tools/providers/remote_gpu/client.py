"""HTTP client for the remote GPU node API."""

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

logger = logging.getLogger("remote_gpu")


@dataclass
class RemoteGPUSettings:
    """Settings for remote GPU connectivity."""
    enabled: bool = True
    base_url: str = "http://10.20.10.210:8750"
    timeout: int = 1800
    max_retries: int = 2
    shared_secret: str = ""
    ssh_host: str = "openmontage-gpu"

    @classmethod
    def from_env(cls) -> "RemoteGPUSettings":
        """Load settings from environment variables."""
        return cls(
            enabled=os.environ.get("REMOTE_GPU_ENABLED", "true").lower() == "true",
            base_url=os.environ.get("REMOTE_GPU_BASE_URL", "http://10.20.10.210:8750"),
            timeout=int(os.environ.get("REMOTE_GPU_TIMEOUT", "1800")),
            max_retries=int(os.environ.get("REMOTE_GPU_MAX_RETRIES", "2")),
            shared_secret=os.environ.get("REMOTE_GPU_SHARED_SECRET", ""),
            ssh_host=os.environ.get("REMOTE_GPU_SSH_HOST", "openmontage-gpu"),
        )


# Global singleton settings cache
_settings: Optional[RemoteGPUSettings] = None


def get_settings() -> RemoteGPUSettings:
    """Get cached GPU settings."""
    global _settings
    if _settings is None:
        _settings = RemoteGPUSettings.from_env()
    return _settings


def reset_settings() -> None:
    """Reset cached settings (e.g., after .env reload)."""
    global _settings
    _settings = None


class RemoteGPUError(Exception):
    """Base exception for remote GPU operations."""
    pass


class RemoteGPUHealthError(RemoteGPUError):
    """GPU node is not healthy."""
    pass


class RemoteGPUTimeoutError(RemoteGPUError):
    """GPU operation timed out."""
    pass


class RemoteGPUClient:
    """HTTP client for the GPU node API."""

    def __init__(self, settings: Optional[RemoteGPUSettings] = None):
        self.settings = settings or get_settings()
        self.session = requests.Session()
        self.session.timeout = (10, self.settings.timeout)

        if self.settings.shared_secret:
            self.session.headers["Authorization"] = (
                f"Bearer {self.settings.shared_secret}"
            )

    def _url(self, path: str) -> str:
        """Build full URL."""
        base = self.settings.base_url.rstrip("/")
        path = path.lstrip("/")
        return f"{base}/{path}"

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an HTTP request with retry logic."""
        url = self._url(path)
        last_error: Optional[Exception] = None

        for attempt in range(self.settings.max_retries + 1):
            try:
                resp = self.session.request(
                    method,
                    url,
                    timeout=kwargs.pop("timeout", self.settings.timeout),
                    **kwargs,
                )
                if resp.status_code >= 500:
                    raise RemoteGPUError(
                        f"GPU node error {resp.status_code}: {resp.text[:200]}"
                    )
                return resp
            except requests.ConnectionError as e:
                last_error = RemoteGPUHealthError(
                    f"Cannot connect to GPU node at {url}: {e}"
                )
            except requests.Timeout as e:
                last_error = RemoteGPUTimeoutError(
                    f"GPU node timeout at {url}: {e}"
                )
            except RemoteGPUError:
                raise
            except Exception as e:
                last_error = RemoteGPUError(f"GPU request failed: {e}")

            if attempt < self.settings.max_retries:
                wait = 2 ** attempt
                logger.warning(
                    "GPU request failed (attempt %d/%d), retrying in %ds: %s",
                    attempt + 1,
                    self.settings.max_retries + 1,
                    wait,
                    last_error,
                )
                time.sleep(wait)

        raise RemoteGPUError(
            f"GPU request failed after {self.settings.max_retries + 1} attempts: "
            f"{last_error}"
        )

    def check_health(self) -> dict:
        """Check GPU node health."""
        resp = self._request("GET", "health")
        data = resp.json()
        if data.get("status") != "ok":
            raise RemoteGPUHealthError(
                f"GPU node unhealthy: {data.get('status')}"
            )
        return data

    def get_gpu_info(self) -> dict:
        """Get GPU status."""
        resp = self._request("GET", "gpu")
        return resp.json()

    def tts(
        self,
        text: str,
        voice: str = "vi-VN-HoaiMyNeural",
        speed: float = 1.0,
        output_format: str = "wav",
    ) -> dict:
        """Generate TTS audio on GPU node.

        Returns dict with job_id, status, and output info.
        """
        resp = self._request(
            "POST",
            "v1/tts",
            json={
                "text": text,
                "voice": voice,
                "speed": speed,
                "output_format": output_format,
            },
        )
        return resp.json()

    def transcribe(
        self,
        audio_path: str,
        language: str = "vi",
        model_size: str = "base",
        word_timestamps: bool = True,
    ) -> dict:
        """Transcribe audio file using GPU node's Whisper.

        Args:
            audio_path: Local path to audio file (will be uploaded)
            language: Language code (vi, en, etc.)
            model_size: Whisper model size (tiny, base, small, medium, large-v3)
            word_timestamps: Include word-level timestamps

        Returns:
            Dict with transcript, segments, files
        """
        import os as _os

        url = self._url("v1/transcribe")

        with open(audio_path, "rb") as f:
            files = {"file": (_os.path.basename(audio_path), f, "audio/wav")}
            data = {
                "language": language,
                "model_size": model_size,
                "word_timestamps": str(word_timestamps).lower(),
            }

            last_error: Optional[Exception] = None
            for attempt in range(self.settings.max_retries + 1):
                try:
                    resp = self.session.post(
                        url,
                        files=files,
                        data=data,
                        timeout=self.settings.timeout,
                    )
                    if resp.status_code >= 500:
                        raise RemoteGPUError(
                            f"GPU node transcribe error {resp.status_code}: "
                            f"{resp.text[:200]}"
                        )
                    return resp.json()
                except (requests.ConnectionError, requests.Timeout) as e:
                    last_error = e
                    if attempt < self.settings.max_retries:
                        wait = 2 ** attempt
                        logger.warning(
                            "Transcribe failed (attempt %d/%d), retry in %ds: %s",
                            attempt + 1,
                            self.settings.max_retries + 1,
                            wait,
                            e,
                        )
                        time.sleep(wait)
                    else:
                        raise RemoteGPUError(
                            f"Transcribe failed after {self.settings.max_retries + 1} "
                            f"attempts: {e}"
                        )
                except Exception as e:
                    raise RemoteGPUError(f"Transcribe failed: {e}")

        raise RemoteGPUError("Transcribe failed (unreachable)")

    def image_generate(
        self,
        prompt: str,
        model: str = "stabilityai/stable-diffusion-2-1",
        width: int = 512,
        height: int = 512,
        num_inference_steps: int = 25,
        negative_prompt: str = "",
    ) -> dict:
        """Generate image on GPU node.

        Returns dict with job_id, status, image_url.
        """
        resp = self._request(
            "POST",
            "v1/image/generate",
            json={
                "prompt": prompt,
                "model": model,
                "width": width,
                "height": height,
                "num_inference_steps": num_inference_steps,
                "negative_prompt": negative_prompt,
            },
        )
        return resp.json()

    def get_fallback_info(self) -> dict:
        """Get fallback configuration from GPU node."""
        resp = self._request("GET", "v1/fallback")
        return resp.json()
