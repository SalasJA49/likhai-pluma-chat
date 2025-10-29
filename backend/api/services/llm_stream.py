# backend/api/services/llm_stream.py
"""
Foundry streaming for /api/chat/stream/.
Reads model mapping from env:
  - LLM_CONFIG   : list of deployments (gives api_endpoint)
  - LLM_WORKWEB  : list of {"model_id","model_deployment","mode"} to choose agent id
"""

from __future__ import annotations

import json
from typing import Dict, Generator, Optional

from django.core.cache import cache
from django.utils.timezone import now

from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import (
    MessageInputTextBlock,
    MessageInputContentBlock,
    AgentStreamEvent,
    MessageDeltaChunk,
    ThreadRun,
    MessageRole,
)

import os


# ---------- helpers ----------

def _load_env_json(name: str) -> list:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def _pick_endpoint_for_deployment(deployment: str) -> Optional[str]:
    """
    From LLM_CONFIG, find api_endpoint for a given model_deployment
    (e.g., "foundry/gpt-4.1-mini").
    """
    cfg = _load_env_json("LLM_CONFIG")
    for item in cfg:
        if str(item.get("model_deployment", "")).strip() == deployment:
            ep = item.get("api_endpoint")
            if ep:
                return ep
    # fallback: first with endpoint
    for item in cfg:
        ep = item.get("api_endpoint")
        if ep:
            return ep
    return None


def _pick_agent_id(deployment: str, mode: str) -> Optional[str]:
    """
    From LLM_WORKWEB, pick model_id where model_deployment matches and mode is 'work' or 'web'.
    """
    mode = (mode or "work").lower()
    ww = _load_env_json("LLM_WORKWEB")
    for item in ww:
        if (
            str(item.get("model_deployment", "")).strip() == deployment
            and str(item.get("mode", "")).lower() == mode
        ):
            return item.get("model_id")
    # fallback: same deployment regardless of mode
    for item in ww:
        if str(item.get("model_deployment", "")).strip() == deployment:
            return item.get("model_id")
    return None


# We map your app thread_id -> foundry_thread_id in cache
def _get_or_create_foundry_thread_id(client: AgentsClient, app_thread_id: int) -> str:
    key = f"foundry_thread:{app_thread_id}"
    thread_id = cache.get(key)
    if thread_id:
        return thread_id
    thread = client.threads.create()
    cache.set(key, thread.id, timeout=60 * 60 * 24)  # 24h
    return thread.id


# ---------- public entry used by the Django view ----------

def stream_foundry_tokens(
    app_thread_id: int,
    user_text: str,
    mode: str,
    deployment: str,
) -> Generator[bytes, None, None]:
    """
    Yields SSE frames as bytes (b'event: token\\ndata: ...\\n\\n', etc.)
    """
    endpoint = _pick_endpoint_for_deployment(deployment)
    agent_id = _pick_agent_id(deployment, mode)

    if not endpoint or not agent_id:
        detail = {
            "detail": "Foundry model mapping not found. Check LLM_CONFIG/LLM_WORKWEB environment variables."
        }
        yield _sse("error", json.dumps(detail).encode("utf-8"))
        return

    # init client
    client = AgentsClient(endpoint=endpoint, credential=DefaultAzureCredential())

    # ensure per-app thread has a Foundry thread
    f_thread_id = _get_or_create_foundry_thread_id(client, app_thread_id)

    # send user message
    content_blocks: list[MessageInputContentBlock] = [MessageInputTextBlock(text=user_text)]
    client.messages.create(thread_id=f_thread_id, role="user", content=content_blocks)

    # notify ready
    yield _sse("ready", b"ok")

    # stream run
    with client.runs.stream(thread_id=f_thread_id, agent_id=agent_id) as stream:
        for event_type, event_data, _ in stream:
            if isinstance(event_data, MessageDeltaChunk):
                if event_data.text:
                    yield _sse("token", event_data.text.encode("utf-8"))
            elif isinstance(event_data, ThreadRun):
                if event_data.status == "failed":
                    detail = {"detail": str(event_data.last_error or 'Run failed')}
                    yield _sse("error", json.dumps(detail).encode("utf-8"))
                    break
            elif event_type == AgentStreamEvent.ERROR:
                detail = {"detail": str(event_data)}
                yield _sse("error", json.dumps(detail).encode("utf-8"))
                break

    # final answer (optional – we already streamed tokens)
    last = client.messages.get_last_message_text_by_role(
        thread_id=f_thread_id, role=MessageRole.AGENT
    )
    if last and last.text and last.text.value:
        # make sure last token chunk ends with newline for clean markdown
        yield _sse("token", b"\n")

    yield _sse("done", b"ok")


# ---------- SSE formatting ----------

def _sse(event: str, data: bytes) -> bytes:
    # event: <name>\n data: <utf8>\n\n
    return b"event: " + event.encode("utf-8") + b"\n" + b"data: " + data + b"\n\n"


# Backwards-compatible alias expected by views
def stream_chat(app_thread_id: int, user_text: str, mode: str, deployment: str):
    """Compatibility wrapper: older code imports `stream_chat` from this module.
    It yields SSE-formatted bytes, same as `stream_foundry_tokens`.
    """
    return stream_foundry_tokens(app_thread_id=app_thread_id, user_text=user_text, mode=mode, deployment=deployment)
