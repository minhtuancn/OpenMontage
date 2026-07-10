"""OpenMontage GPU Providers Package.

This package contains provider implementations for remote GPU compute,
allowing the DEV node to offload GPU-intensive tasks to the GPU node.
"""

# Import remote GPU providers so they register with the tool registry
from tools.providers.remote_gpu import (
    RemoteGPTTS,
    RemoteGPUWhisper,
    RemoteGPUImageGen,
)

__all__ = [
    "RemoteGPTTS",
    "RemoteGPUWhisper",
    "RemoteGPUImageGen",
]
