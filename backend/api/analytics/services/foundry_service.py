"""
Azure AI Foundry adapter (synchronous) for Django backend.

This wraps a minimal subset of the AgentsClient usage to:
- run a single-turn completion based on a prompt
- be resilient: if any SDK call fails, raise a RuntimeError which callers can catch

Environment variables expected:
- FOUNDRY_API_ENDPOINT: e.g. https://<your-project>.services.ai.azure.com
- FOUNDRY_AGENT_ID: Agent identifier for the Agents service (workweb/agent id)

Note: If these are not set or SDK is missing, the service will raise at runtime.
Callers should catch and fallback to deterministic logic.
"""
from __future__ import annotations
import os
import time
from typing import Optional

try:
    # Resolve model_id and endpoint via backend mapping
    from ...services.foundry_stream import resolve_foundry  # type: ignore
except Exception:
    resolve_foundry = None  # type: ignore


class FoundryService:
    def __init__(self,
                 endpoint: Optional[str] = None,
                 agent_id: Optional[str] = None,
                 model_deployment: Optional[str] = None,
                 mode: Optional[str] = None):
        # If model_deployment+mode provided and resolver available, derive endpoint+agent_id from mapping
        if model_deployment and mode and resolve_foundry is not None:
            try:
                resolved = resolve_foundry(model_deployment=model_deployment, mode=mode)
                endpoint = resolved.get("endpoint") or endpoint
                agent_id = resolved.get("model_id") or agent_id
            except Exception:
                # fall back to env-based wiring below
                pass

        self.endpoint = endpoint or os.getenv("FOUNDRY_API_ENDPOINT")
        self.agent_id = agent_id or os.getenv("FOUNDRY_AGENT_ID")

        if not self.endpoint or not self.agent_id:
            raise RuntimeError("FoundryService misconfigured: provide model_deployment+mode or set FOUNDRY_API_ENDPOINT and FOUNDRY_AGENT_ID")

        # Import lazily so backend can run without the SDK when not needed
        try:
            from azure.identity import DefaultAzureCredential  # noqa: F401
            from azure.ai.agents import AgentsClient  # noqa: F401
            from azure.ai.agents.models import (  # noqa: F401
                MessageInputTextBlock,
                MessageRole,
            )
        except Exception as e:
            raise RuntimeError(f"Azure AI Agents SDK not available: {e}")

        # Create client lazily
        self._client = None

    def _client_or_create(self):
        if self._client is None:
            from azure.identity import DefaultAzureCredential
            from azure.ai.agents import AgentsClient
            self._client = AgentsClient(endpoint=self.endpoint, credential=DefaultAzureCredential())
        return self._client

    def complete(self, prompt: str, timeout_seconds: int = 45) -> str:
        """
        Send a single prompt to the Foundry agent and return the response text.
        Creates a transient thread for this request.
        """
        if not prompt or not prompt.strip():
            raise ValueError("prompt is required")

        client = self._client_or_create()

        # Create thread
        thread = client.threads.create()
        thread_id = getattr(thread, "id", None)
        if not thread_id:
            raise RuntimeError("Failed to create Foundry thread")

        # Post user message
        from azure.ai.agents.models import MessageInputTextBlock
        client.messages.create(
            thread_id=thread_id,
            role="user",
            content=[MessageInputTextBlock(text=prompt)],
        )

        # Run the agent
        run = client.runs.create(thread_id=thread_id, agent_id=self.agent_id)
        run_id = getattr(run, "id", None)
        if not run_id:
            raise RuntimeError("Failed to start Foundry run")

        # Poll until completed
        start = time.time()
        status = getattr(run, "status", None)
        while status not in ("completed", "failed", "canceled"):
            if time.time() - start > timeout_seconds:
                raise RuntimeError("Foundry run timed out")
            time.sleep(0.75)
            run = client.runs.get(thread_id=thread_id, run_id=run_id)
            status = getattr(run, "status", None)

        if status != "completed":
            last_error = getattr(run, "last_error", None)
            raise RuntimeError(f"Foundry run did not complete: {status} | {last_error}")

        # Fetch last agent message
        from azure.ai.agents.models import MessageRole
        msg = client.messages.get_last_message_text_by_role(thread_id=thread_id, role=MessageRole.AGENT)
        if msg and getattr(msg, "text", None) and getattr(msg.text, "value", None):
            return msg.text.value
        # Fallback: list messages and take last agent message text-like content
        messages = client.messages.list(thread_id=thread_id) or []
        for m in reversed(messages):
            if getattr(m, "role", None) == "agent":
                # Attempt to extract text field
                try:
                    return m.text.value
                except Exception:
                    pass
        raise RuntimeError("No agent response text returned from Foundry")
