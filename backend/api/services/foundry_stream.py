# backend/api/services/foundry_stream.py
import json, os
from typing import Iterable, Dict, Any
from collections import defaultdict

from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import (
    MessageInputTextBlock,
    MessageInputContentBlock,
    MessageAttachment,
    CodeInterpreterTool,
    FilePurpose,
    MessageImageFileParam,
    MessageInputImageFileBlock,
    AgentStreamEvent,
    MessageDeltaChunk,
    ThreadRun,
)

# ---- Parse env JSON safely ----
def _load_json_env(name: str) -> list[dict]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []

_LLM_CONFIG = _load_json_env("LLM_CONFIG")
_LLM_WORKWEB = _load_json_env("LLM_WORKWEB")

def resolve_foundry(model_deployment: str, mode: str) -> dict:
    """
    Given a deployment like 'foundry/gpt-4o' and mode ('work'|'web'), return:
      { endpoint: str, model_id: str }
    """
    # 1) endpoint from LLM_CONFIG by matching model_deployment
    cfg = next((c for c in _LLM_CONFIG if c.get("model_deployment") == model_deployment), None)
    if not cfg:
        raise RuntimeError(f"Model deployment not found in LLM_CONFIG: {model_deployment}")
    endpoint = cfg.get("api_endpoint")
    if not endpoint:
        raise RuntimeError("Missing api_endpoint in LLM_CONFIG for " + model_deployment)

    # 2) model_id from LLM_WORKWEB by (deployment, mode)
    ww = next((w for w in _LLM_WORKWEB
               if w.get("model_deployment") == model_deployment and w.get("mode") == mode), None)
    if not ww or not ww.get("model_id"):
        raise RuntimeError(f"Missing model_id in LLM_WORKWEB for {model_deployment} / {mode}")

    return {"endpoint": endpoint, "model_id": ww["model_id"]}

# ---- Per-Django-process map: ChatThread.id -> Foundry thread_id ----
_FOUNDATION_THREADS: dict[int, str] = {}

# Single credential instance
_CRED = DefaultAzureCredential(exclude_shared_token_cache_credential=True)

# Cache of AgentsClient per endpoint to avoid re-creating
_CLIENTS: dict[str, AgentsClient] = {}

def _client_for(endpoint: str) -> AgentsClient:
    cli = _CLIENTS.get(endpoint)
    if not cli:
        cli = AgentsClient(endpoint=endpoint, credential=_CRED)
        _CLIENTS[endpoint] = cli
    return cli

def stream_foundry_chat(
    *,
    thread_db_id: int,
    user_text: str,
    model_deployment: str,
    mode: str,
) -> Iterable[str]:
    """
    Yields SSE 'token' chunks from Azure AI Foundry Agents, mirroring your Chainlit flow.
    """
    if not user_text.strip():
        return

    resolved = resolve_foundry(model_deployment=model_deployment, mode=mode)
    endpoint = resolved["endpoint"]
    agent_id = resolved["model_id"]

    client = _client_for(endpoint)

    # Ensure a Foundry thread exists for this Django ChatThread
    f_thread_id = _FOUNDATION_THREADS.get(thread_db_id)
    if not f_thread_id:
        thread = client.threads.create()
        f_thread_id = thread.id
        _FOUNDATION_THREADS[thread_db_id] = f_thread_id

    # Build content blocks (text only for now; hook in files here later if needed)
    content_blocks: list[MessageInputContentBlock] = [MessageInputTextBlock(text=user_text)]
    attachments: list[MessageAttachment] = []

    # If you later pass files, you can upload like this:
    # file = client.files.upload_and_poll(file_path=path, purpose=FilePurpose.AGENTS)
    # attachments.append(MessageAttachment(file_id=file.id, tools=CodeInterpreterTool().definitions))
    # If image, you can add MessageInputImageFileBlock with MessageImageFileParam

    client.messages.create(
        thread_id=f_thread_id,
        role="user",
        content=content_blocks,
        attachments=attachments,
    )

    # Stream the run
    full = []
    with client.runs.stream(thread_id=f_thread_id, agent_id=agent_id) as stream:
        for event_type, event_data, _ in stream:
            if isinstance(event_data, MessageDeltaChunk):
                token = event_data.text or ""
                if token:
                    full.append(token)
                    yield token
            elif isinstance(event_data, ThreadRun):
                if event_data.status == "failed":
                    raise RuntimeError(str(event_data.last_error))
            elif event_type == AgentStreamEvent.ERROR:
                raise RuntimeError(str(event_data))

    # Done – caller can save `''.join(full)` if desired
