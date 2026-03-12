# OpenClaw Agent Stack Bridge

An experimental PoC that integrates [OpenClaw](https://github.com/openclaw/openclaw) AI assistant as an unmanaged agent within the [Agent Stack](https://github.com/i-am-bee/agentstack) framework.

## Overview

This project bridges OpenClaw's AI capabilities with Agent Stack's agent orchestration platform. It runs OpenClaw as a local gateway inside a Docker container and exposes it as an Agent Stack-compatible HTTP agent with streamed replies over A2A.

## Tech Stack

- **Python 3.13** — agent implementation using `agentstack-sdk`
- **Node.js 22** — OpenClaw CLI runtime
- **Docker** — containerized deployment

## Quick Start

1. Copy `.env.example` to `.env` and set your API key:

   ```bash
   cp .env.example .env
   # Edit .env and set OPENROUTER_API_KEY and OPENCLAW_GATEWAY_TOKEN
   ```

2. Run with Docker Compose:

   ```bash
   docker-compose up --build
   ```

The agent server starts on `localhost:8000`.
Inside the container, the agent always listens on `0.0.0.0:8000`; `PORT` only changes the host-side Docker publish port.

## Runtime Configuration

| Variable                 | Required | Default                                          | Description                                           |
| ------------------------ | -------- | ------------------------------------------------ | ----------------------------------------------------- |
| `OPENROUTER_API_KEY`     | Yes      | —                                                | OpenRouter API key                                    |
| `OPENCLAW_GATEWAY_TOKEN` | Yes      | —                                                | Shared gateway token for the bridge and browser relay |
| `OPENCLAW_MODEL`         | No       | `openrouter/arcee-ai/trinity-large-preview:free` | Default model configured into the OpenClaw gateway    |
| `OPENCLAW_GATEWAY_PORT`  | No       | `18789`                                          | Local OpenClaw gateway port shared by the bridge      |
| `OPENCLAW_AGENT_TIMEOUT` | No       | `180`                                            | Agent streaming timeout (seconds)                     |

Most setups only need `OPENROUTER_API_KEY`. The other runtime variables are optional overrides.

## Docker Overrides

| Variable           | Default  | Description                                         |
| ------------------ | -------- | --------------------------------------------------- |
| `OPENCLAW_VERSION` | `latest` | OpenClaw CLI version used when building the image   |
| `PORT`             | `8000`   | Host port published by Docker Compose for the agent |

## Architecture

The container runs two services:

1. **OpenClaw Gateway** (port `18789`) — local OpenClaw instance handling LLM interactions
2. **Agent Server** (port `8000`) — Agent Stack-compatible HTTP endpoint that forwards requests to the gateway's OpenResponses HTTP API and relays streamed reply chunks over A2A

The gateway uses token auth. If you want to use the Chrome extension relay, configure the extension with the same `OPENCLAW_GATEWAY_TOKEN`.
