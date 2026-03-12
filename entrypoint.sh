#!/usr/bin/env bash
set -euo pipefail

# Full provider/model string; default to OpenRouter free model
MODEL="${OPENCLAW_MODEL:-openrouter/arcee-ai/trinity-large-preview:free}"
GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
GATEWAY_TOKEN="${OPENCLAW_GATEWAY_TOKEN:?Set OPENCLAW_GATEWAY_TOKEN in .env or environment}"

# Generate OpenClaw config at runtime with the chosen model
cat > /root/.openclaw/openclaw.json <<EOF
{
  "gateway": {
    "mode": "local",
    "auth": {
      "mode": "token",
      "token": "${GATEWAY_TOKEN}"
    },
    "http": {
      "endpoints": {
        "responses": {
          "enabled": true
        }
      }
    }
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
openclaw gateway --port "${GATEWAY_PORT}" &

# Wait for the gateway to become healthy
echo "Waiting for OpenClaw gateway..."
if ! curl --retry 60 --retry-delay 1 --retry-connrefused -sf \
    "http://127.0.0.1:${GATEWAY_PORT}/healthz" > /dev/null; then
    echo "ERROR: OpenClaw gateway did not start within 60s."
    exit 1
fi
echo "OpenClaw gateway is ready."

# Start the Python agent directly from the venv
exec /app/.venv/bin/agent
