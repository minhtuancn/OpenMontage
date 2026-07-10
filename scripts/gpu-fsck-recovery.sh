#!/bin/bash
# GPU Filesystem Recovery Script
# Run this when the GPU node's root filesystem is read-only
# due to ext4 journal errors (common after disk-full condition).
#
# Usage: ./gpu-fsck-recovery.sh

set -euo pipefail

echo "=== GPU Filesystem Recovery ==="
echo ""

# Check if GPU is reachable
if ! ssh openmontage-gpu "hostname" > /dev/null 2>&1; then
    echo "ERROR: Cannot reach GPU node. Check SSH config."
    exit 1
fi

echo "1. Checking current filesystem state..."
FS_STATE=$(ssh openmontage-gpu "mount | grep ' / ' | grep -o 'rw\|ro'")
echo "   Current mount: $FS_STATE"

if [ "$FS_STATE" = "rw" ]; then
    echo "   Filesystem is already read-write. No recovery needed."
    exit 0
fi

echo ""
echo "2. Checking dmesg for errors..."
ssh openmontage-gpu "dmesg | grep 'ext4.*error\|journal' | tail -3"

echo ""
echo "3. Scheduling forced fsck on next reboot..."
ssh openmontage-gpu "sudo touch /forcefsck && echo '  /forcefsck created'"
ssh openmontage-gpu "sudo sync && echo '  sync done'"

echo ""
echo "4. Rebooting GPU node..."
read -p "   Reboot GPU node now? (y/N): " confirm
if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    ssh openmontage-gpu "sudo reboot"
    echo "   Reboot issued. Waiting 30s for shutdown..."
    sleep 10
    
    # Wait for GPU to come back
    echo "   Waiting for GPU to come back..."
    for i in {1..30}; do
        if ssh openmontage-gpu "hostname" > /dev/null 2>&1; then
            echo "   GPU is back online!"
            
            # Check filesystem
            FS_STATE=$(ssh openmontage-gpu "mount | grep ' / ' | grep -o 'rw\|ro'")
            echo "   Filesystem is now: $FS_STATE"
            
            if [ "$FS_STATE" = "rw" ]; then
                echo ""
                echo "=== Recovery successful! ==="
                echo "Now download models:"
                echo "  ssh openmontage-gpu"
                echo "  cd /opt/openmontage-gpu/comfyui/models"
                echo "  pip install huggingface-hub"
                echo "  huggingface-cli download Wan-AI/Wan2.1-T2V-1.3B --local-dir Wan2.1-T2V-1.3B"
            fi
            exit 0
        fi
        sleep 5
    done
    echo "   WARNING: GPU did not come back within timeout."
    echo "   Check manually: ssh openmontage-gpu"
else
    echo "   Skipped reboot. To reboot manually:"
    echo "   ssh openmontage-gpu 'sudo touch /forcefsck && sudo reboot'"
fi

echo ""
echo "=== Done ==="
