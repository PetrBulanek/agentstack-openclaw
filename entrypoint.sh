#!/usr/bin/env bash
set -euo pipefail

# Full provider/model string; default to OpenRouter free model
MODEL="${OPENCLAW_MODEL:-openrouter/arcee-ai/trinity-large-preview:free}"

# Generate OpenClaw config at runtime with the chosen model
cat > /root/.openclaw/openclaw.json <<EOF
{
  "gateway": {
    "mode": "local"
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "${MODEL}"
      }
    }
  }
}
EOF

echo "OpenClaw configured with model: ${MODEL}"

# Start OpenClaw gateway in the background
openclaw gateway --port 18789 &

# Wait for the gateway to become healthy
echo "Waiting for OpenClaw gateway..."
if ! curl --retry 60 --retry-delay 1 --retry-connrefused -sf \
    http://127.0.0.1:18789/healthz > /dev/null; then
    echo "ERROR: OpenClaw gateway did not start within 60s."
    exit 1
fi
echo "OpenClaw gateway is ready."

# Start the Python agent directly from the venv
exec /app/.venv/bin/agent
