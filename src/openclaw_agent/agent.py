import asyncio
import json
import logging
import os
from typing import Annotated, Any, AsyncGenerator

from agentstack_sdk.a2a.types import AgentMessage, Message, RunYield
from agentstack_sdk.a2a.extensions import TrajectoryExtensionServer, TrajectoryExtensionSpec
from agentstack_sdk.server import Server

logger = logging.getLogger(__name__)

server = Server()
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("OPENCLAW_AGENT_TIMEOUT", "90"))


def _extract_text_response(result: dict[str, Any]) -> str:
    payloads = result.get("result", {}).get("payloads", [])
    texts = [payload.get("text", "") for payload in payloads if payload.get("text")]
    return "\n".join(texts) if texts else "No response from OpenClaw."


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

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=DEFAULT_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise RuntimeError(f"OpenClaw agent timed out after {DEFAULT_TIMEOUT_SECONDS:g}s")

    if proc.returncode != 0:
        error_msg = stderr.decode().strip()
        raise RuntimeError(f"OpenClaw agent failed (exit {proc.returncode}): {error_msg}")

    raw_output = stdout.decode().strip()
    if not raw_output:
        raise RuntimeError("OpenClaw agent returned an empty response")

    try:
        result = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenClaw agent returned invalid JSON: {raw_output}") from exc

    return _extract_text_response(result)


@server.agent(
    name="OpenClaw",
    description="An experimental agent powered by OpenClaw AI assistant with OpenRouter LLM provider.",
)
async def openclaw_agent(
    input: Message,
    trajectory: Annotated[TrajectoryExtensionServer, TrajectoryExtensionSpec()],
) -> AsyncGenerator[RunYield, Message]:
    """Forwards user messages to an OpenClaw instance and returns the response."""
    user_input = input.parts[0].root.text if input.parts else ""
    if not user_input:
        yield AgentMessage(text="No input provided.")
        return

    session_id = input.context_id or input.message_id or "default"

    metadata = trajectory.trajectory_metadata(
        title="OpenClaw request",
        content=f"Forwarding the message to the local OpenClaw gateway using conversation session `{session_id}`.",
        group_id="openclaw-request",
    )
    yield metadata

    try:
        response = await _run_openclaw_agent(user_input, session_id=session_id)
        metadata = trajectory.trajectory_metadata(
            title="OpenClaw response ready",
            content="Received a response from the local OpenClaw gateway.",
            group_id="openclaw-request",
        )
        yield metadata
        yield AgentMessage(text=response)
    except Exception as e:
        logger.exception("OpenClaw agent error")
        metadata = trajectory.trajectory_metadata(
            title="OpenClaw request failed",
            content=f"The OpenClaw gateway request failed: `{e}`",
            group_id="openclaw-request",
        )
        yield metadata
        yield AgentMessage(text=f"Error: {e}")


def run():
    server.run(host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 8000)))


if __name__ == "__main__":
    run()
