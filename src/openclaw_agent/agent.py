# Copyright 2025 © BeeAI a Series of LF Projects, LLC
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import logging
import os

from agentstack_sdk.a2a.types import AgentMessage, Message
from agentstack_sdk.server import Server

logger = logging.getLogger(__name__)

server = Server()


async def _run_openclaw_agent(message: str, session_id: str = "default") -> str:
    """Send a message to the OpenClaw gateway via CLI and return the response."""
    proc = await asyncio.create_subprocess_exec(
        "openclaw",
        "agent",
        "--message",
        message,
        "--session-id",
        session_id,
        "--json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode().strip()
        raise RuntimeError(f"OpenClaw agent failed (exit {proc.returncode}): {error_msg}")

    result = json.loads(stdout.decode())
    payloads = result.get("result", {}).get("payloads", [])
    texts = [p.get("text", "") for p in payloads if p.get("text")]
    return "\n".join(texts) if texts else "No response from OpenClaw."


@server.agent(
    name="OpenClaw",
    description="An experimental agent powered by OpenClaw AI assistant with OpenRouter LLM provider.",
)
async def openclaw_agent(input: Message):
    """Forwards user messages to an OpenClaw instance and returns the response."""
    user_input = input.parts[0].root.text if input.parts else ""
    if not user_input:
        yield AgentMessage(text="No input provided.")
        return

    session_id = input.context_id or input.message_id or "default"

    yield AgentMessage(text="Thinking...")

    try:
        response = await _run_openclaw_agent(user_input, session_id=session_id)
        yield AgentMessage(text=response)
    except Exception as e:
        logger.exception("OpenClaw agent error")
        yield AgentMessage(text=f"Error: {e}")


def run():
    server.run(host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 8000)))


if __name__ == "__main__":
    run()
