# OpenClaw Agent Stack Bridge

An experimental PoC that integrates [OpenClaw](https://github.com/openclaw/openclaw) AI assistant as an unmanaged agent within the [Agent Stack](https://github.com/i-am-bee/agentstack) framework.

## Overview

This project bridges OpenClaw's AI capabilities with Agent Stack's agent orchestration platform. It runs OpenClaw as a local gateway inside a Docker container and exposes it as an Agent Stack-compatible HTTP agent.

## Tech Stack

- **Python 3.13** — agent implementation using `agentstack-sdk`
- **Node.js 22** — OpenClaw CLI runtime
- **Docker** — containerized deployment

## Quick Start

1. Copy `.env.example` to `.env` and set your API key:

   ```bash
   cp .env.example .env
   # Edit .env and set OPENROUTER_API_KEY
   ```

2. Run with Docker Compose:

   ```bash
   docker-compose up --build
   ```

The agent server starts on `localhost:8000`.

## Environment Variables

| Variable                 | Required | Default                                          | Description                      |
| ------------------------ | -------- | ------------------------------------------------ | -------------------------------- |
| `OPENROUTER_API_KEY`     | Yes      | —                                                | OpenRouter API key               |
| `OPENCLAW_MODEL`         | No       | `openrouter/arcee-ai/trinity-large-preview:free` | LLM model to use                 |
| `OPENCLAW_VERSION`       | No       | `latest`                                         | OpenClaw CLI version             |
| `OPENCLAW_AGENT_TIMEOUT` | No       | `180`                                            | Agent response timeout (seconds) |
| `HOST`                   | No       | `0.0.0.0`                                        | Agent server bind address        |
| `PORT`                   | No       | `8000`                                           | Agent server port                |

## Architecture

The container runs two services:

1. **OpenClaw Gateway** (port 18789) — local OpenClaw instance handling LLM interactions
2. **Agent Server** (port 8000) — Agent Stack-compatible HTTP endpoint that forwards requests to the gateway via the OpenClaw CLI
