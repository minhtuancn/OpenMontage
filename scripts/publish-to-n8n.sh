#!/bin/bash
# publish-to-n8n.sh — Send a render notification to n8n for publishing
# Usage: publish-to-n8n.sh <project-name> [file-path]
#
# This triggers the n8n publishing workflow with render metadata.
# n8n can then POST to YouTube, TikTok, or social media APIs.

set -euo pipefail

PROJECT="${1:-}"
FILE="${2:-}"
N8N_WEBHOOK_URL="http://127.0.0.1:5678/webhook/openmontage-publish"

if [ -z "$PROJECT" ]; then
  echo "Usage: $0 <project-name> [file-path]"
  echo "Example: $0 animated-explainer /opt/openmontage/projects/animated-explainer/output/render.mp4"
  exit 1
fi

if [ -z "$FILE" ]; then
  # Auto-detect the latest render
  FILE=$(ls -t /opt/openmontage/projects/"$PROJECT"/output/*.{mp4,webm,gif} 2>/dev/null | head -1 || echo "")
fi

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "Error: Render file not found: $FILE"
  exit 1
fi

FILE_SIZE=$(stat -c%s "$FILE" 2>/dev/null || echo "unknown")
FILE_MTIME=$(stat -c%Y "$FILE" 2>/dev/null || echo "0")
FILE_TYPE=$(file --mime-type -b "$FILE" 2>/dev/null || echo "application/octet-stream")

echo "=== Publishing render to n8n ==="
echo "  Project: $PROJECT"
echo "  File:    $FILE"
echo "  Size:    $FILE_SIZE bytes"
echo "  Type:    $FILE_TYPE"

# Send to n8n webhook
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$N8N_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "{
    \"project\": \"$PROJECT\",
    \"file\": \"$FILE\",
    \"file_size\": $FILE_SIZE,
    \"file_type\": \"$FILE_TYPE\",
    \"mtime\": $FILE_MTIME,
    \"source\": \"openmontage-cli\"
  }")

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
  echo "  Status: Published to n8n (HTTP $HTTP_CODE) ✓"
else
  echo "  Status: n8n returned HTTP $HTTP_CODE"
fi
echo "=== Done ==="
