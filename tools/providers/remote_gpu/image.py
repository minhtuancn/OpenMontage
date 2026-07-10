"""Remote GPU Image Generation provider."""

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

logger = __import__("logging").getLogger("remote_gpu.image")


class RemoteGPUImageGen(BaseTool):
    """Image generation via remote GPU node (diffusers with CUDA).

    Falls back to cloud image APIs when GPU node is unavailable.
    """

    name = "remote_gpu_image_gen"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_gen"
    provider = "remote_gpu"
    stability = ToolStability.EXPERIMENTAL
    runtime = ToolRuntime.API
    fallback = None
    fallback_tools = [
        "flux_image",
        "openai_image",
        "google_imagen",
        "dashscope_image",
    ]
    dependencies = []

    capabilities = ["image_generation", "gpu_accelerated"]
    supports = {
        "models": ["stabilityai/stable-diffusion-2-1"],
        "offline_fallback": True,
    }
    best_for = [
        "GPU-accelerated image generation",
        "Free local image generation (no API key)",
    ]
    not_good_for = [
        "Very high resolution (>1024x1024)",
        "Commercial-grade quality (use cloud APIs)",
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
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text prompt for image generation",
            },
            "model": {
                "type": "string",
                "description": "Diffusion model to use",
                "default": "stabilityai/stable-diffusion-2-1",
            },
            "width": {
                "type": "integer",
                "description": "Image width",
                "default": 512,
            },
            "height": {
                "type": "integer",
                "description": "Image height",
                "default": 512,
            },
            "num_inference_steps": {
                "type": "integer",
                "description": "Number of denoising steps",
                "default": 25,
            },
            "negative_prompt": {
                "type": "string",
                "description": "Negative prompt",
                "default": "",
            },
            "output_path": {
                "type": "string",
                "description": "Local path to save the image",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "image_path": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "model": {"type": "string"},
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
        """Generate image via remote GPU node."""
        prompt = inputs.get("prompt", "")
        if not prompt:
            return ToolResult(success=False, error="prompt is required")

        model = inputs.get("model", "stabilityai/stable-diffusion-2-1")
        width = int(inputs.get("width", 512))
        height = int(inputs.get("height", 512))
        num_inference_steps = int(inputs.get("num_inference_steps", 25))
        negative_prompt = inputs.get("negative_prompt", "")
        output_path = inputs.get("output_path")

        if not get_settings().enabled:
            return ToolResult(
                success=False,
                error="Remote GPU is disabled. Set REMOTE_GPU_ENABLED=true in .env",
            )

        try:
            client = RemoteGPUClient()
            result = client.image_generate(
                prompt=prompt,
                model=model,
                width=width,
                height=height,
                num_inference_steps=num_inference_steps,
                negative_prompt=negative_prompt,
            )

            if result.get("status") != "completed":
                return ToolResult(
                    success=False,
                    error=f"GPU image gen failed: {result.get('status')}",
                )

            # Download the result
            image_url = result.get("image_url", "")
            if not image_url:
                return ToolResult(
                    success=False,
                    error="GPU image gen returned no image URL",
                )

            if output_path:
                local_path = Path(output_path)
            else:
                output_dir = Path("/srv/openmontage/cache")
                os.makedirs(str(output_dir), exist_ok=True)
                local_path = output_dir / f"gpu_img_{result['job_id']}.png"

            download_url = f"{client.settings.base_url.rstrip('/')}/{image_url.lstrip('/')}"
            resp = client.session.get(download_url, timeout=300)
            with open(str(local_path), "wb") as f:
                f.write(resp.content)

            return ToolResult(
                success=True,
                data={
                    "image_path": str(local_path),
                    "width": width,
                    "height": height,
                    "model": model,
                    "job_id": result.get("job_id"),
                    "provider": "remote_gpu",
                },
                artifacts=[str(local_path)],
            )

        except RemoteGPUError as e:
            logger.warning(f"Remote GPU Image gen failed, will use fallback: {e}")
            return ToolResult(
                success=False,
                error=f"Remote GPU Image gen unavailable: {e}",
            )
        except Exception as e:
            logger.error(f"Remote GPU Image gen error: {e}")
            return ToolResult(
                success=False,
                error=f"Remote GPU Image gen error: {e}",
            )
