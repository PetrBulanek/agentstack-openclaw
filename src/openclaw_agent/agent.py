import json
import logging
import os
from typing import Annotated, Any, AsyncGenerator, AsyncIterator

from agentstack_sdk.a2a.types import AgentMessage, Message, RunYield
from agentstack_sdk.a2a.extensions import TrajectoryExtensionServer, TrajectoryExtensionSpec
from agentstack_sdk.server import Server

logger = logging.getLogger(__name__)

server = Server()


def _extract_error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message:
            return message

    message = payload.get("message")
    if isinstance(message, str) and message:
        return message

    return json.dumps(payload, ensure_ascii=True)


async def _stream_openclaw_agent(message: str, session_id: str = "default") -> AsyncIterator[dict[str, Any]]:
    """Send a message to the OpenClaw gateway via HTTP SSE and yield incremental events."""
    import httpx

    gateway_port = os.getenv("OPENCLAW_GATEWAY_PORT", "18789")
    gateway_token = os.getenv("OPENCLAW_GATEWAY_TOKEN", "").strip()
    timeout_seconds = float(os.getenv("OPENCLAW_AGENT_TIMEOUT", "180"))
    if not gateway_token:
        raise RuntimeError("OPENCLAW_GATEWAY_TOKEN is not configured")

    url = f"http://127.0.0.1:{gateway_port}/v1/responses"
    payload = {"model": "openclaw:main", "input": message, "stream": True}
    headers = {
        "Authorization": f"Bearer {gateway_token}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "x-openclaw-session-key": session_id,
    }

    timeout = httpx.Timeout(timeout=timeout_seconds, connect=min(timeout_seconds, 10.0))
    logger.info(
        "OpenClaw stream start session=%s url=%s timeout=%ss",
        session_id,
        url,
        timeout_seconds,
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                logger.info(
                    "OpenClaw stream connected session=%s status=%s",
                    session_id,
                    response.status_code,
                )
                if response.status_code != 200:
                    body = await response.aread()
                    error_text = body.decode().strip()
                    if error_text:
                        try:
                            error_payload = json.loads(error_text)
                        except json.JSONDecodeError:
                            pass
                        else:
                            error_text = _extract_error_message(error_payload)
                    logger.error(
                        "OpenClaw stream HTTP error session=%s status=%s error=%s",
                        session_id,
                        response.status_code,
                        error_text,
                    )
                    raise RuntimeError(f"OpenClaw gateway request failed ({response.status_code}): {error_text}")

                event_type: str | None = None
                data_lines: list[str] = []
                saw_any_event = False

                async for line in response.aiter_lines():
                    if not line:
                        if not data_lines:
                            event_type = None
                            continue

                        raw_data = "\n".join(data_lines)
                        if raw_data == "[DONE]":
                            data_lines = []
                            event_type = None
                            continue

                        try:
                            event = json.loads(raw_data)
                        except json.JSONDecodeError as exc:
                            raise RuntimeError(f"OpenClaw gateway returned invalid SSE payload: {raw_data}") from exc

                        resolved_type = event_type or event.get("type")
                        if not isinstance(resolved_type, str) or not resolved_type:
                            raise RuntimeError(f"OpenClaw gateway returned an event without a type: {event}")

                        if not saw_any_event:
                            logger.info("OpenClaw stream first event session=%s", session_id)
                            saw_any_event = True

                        event["type"] = resolved_type
                        yield event

                        data_lines = []
                        event_type = None
                        continue

                    if line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        event_type = line.split(":", 1)[1].strip() or None
                        continue
                    if line.startswith("data:"):
                        data_lines.append(line.split(":", 1)[1].lstrip())

                if data_lines:
                    logger.error("OpenClaw stream incomplete SSE frame session=%s", session_id)
                    raise RuntimeError("OpenClaw gateway stream ended with an incomplete SSE frame")
                logger.info(
                    "OpenClaw stream done session=%s saw_events=%s",
                    session_id,
                    saw_any_event,
                )
    except httpx.TimeoutException as exc:
        logger.error("OpenClaw stream timeout session=%s timeout=%ss", session_id, timeout_seconds)
        raise RuntimeError(f"OpenClaw agent timed out after {timeout_seconds:g}s") from exc


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
        completed = False
        streamed_text = False
        emitted_stream_connected = False
        emitted_first_chunk = False

        async for event in _stream_openclaw_agent(user_input, session_id=session_id):
            event_type = event["type"]

            if not emitted_stream_connected:
                metadata = trajectory.trajectory_metadata(
                    title="OpenClaw stream connected",
                    content=f"Connected to the local OpenClaw gateway for session `{session_id}`.",
                    group_id="openclaw-request",
                )
                yield metadata
                emitted_stream_connected = True

            if event_type == "response.output_text.delta":
                text = event.get("delta")
                if isinstance(text, str) and text:
                    if not emitted_first_chunk:
                        metadata = trajectory.trajectory_metadata(
                            title="OpenClaw response streaming",
                            content="Received the first streamed response chunk from the local OpenClaw gateway.",
                            group_id="openclaw-request",
                        )
                        yield metadata
                        emitted_first_chunk = True
                    streamed_text = True
                    yield AgentMessage(text=text)
            elif event_type == "response.output_text.done" and not streamed_text:
                text = event.get("text")
                if isinstance(text, str) and text:
                    if not emitted_first_chunk:
                        metadata = trajectory.trajectory_metadata(
                            title="OpenClaw response streaming",
                            content="Received the first streamed response chunk from the local OpenClaw gateway.",
                            group_id="openclaw-request",
                        )
                        yield metadata
                        emitted_first_chunk = True
                    streamed_text = True
                    yield AgentMessage(text=text)
            elif event_type == "response.failed":
                raise RuntimeError(_extract_error_message(event))
            elif event_type == "response.completed":
                completed = True

        if not completed:
            logger.error("OpenClaw stream missing completion session=%s", session_id)
            raise RuntimeError("OpenClaw gateway stream ended before completion")

        logger.info(
            "OpenClaw response ready session=%s streamed_text=%s",
            session_id,
            streamed_text,
        )
        metadata = trajectory.trajectory_metadata(
            title="OpenClaw response ready",
            content="Received a response from the local OpenClaw gateway.",
            group_id="openclaw-request",
        )
        yield metadata
        if not streamed_text:
            yield AgentMessage(text="No response from OpenClaw.")
    except Exception as e:
        logger.exception("OpenClaw agent error")
        metadata = trajectory.trajectory_metadata(
            title="OpenClaw request failed",
            content=f"The OpenClaw gateway request failed: `{e}`",
            group_id="openclaw-request",
        )
        yield metadata
        raise


def run():
    server.run(host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
