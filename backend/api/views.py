from .repositories.factory import get_repo
from .services.prompts import extract_style as llm_extract_style, rewrite_content as llm_rewrite
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from io import BytesIO
from PyPDF2 import PdfReader
from docx import Document
from pptx import Presentation

# For chatbot
from django.shortcuts import get_object_or_404
from .models import ChatThread, ChatMessage
from .services.chat_llm import run_chat

# For chat stream
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import StreamingHttpResponse, HttpResponseBadRequest
from .services.llm_stream import stream_chat
from .services.sse import sse_format, sse_response
from .models import ChatThread, ChatMessage

# For Deep Research
import asyncio, threading, json
from queue import Queue, Empty
import time
import json, os
from .services.foundry_stream import stream_foundry_chat

repo = get_repo()

def _load_json_env(name: str) -> list[dict]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def extract_text_from_files(django_files):
    out = []
    for f in django_files:
        name = f.name.lower()
        data = f.read()
        if name.endswith(".pdf"):
            pdf = PdfReader(BytesIO(data))
            for p in pdf.pages:
                out.append((p.extract_text() or ""))
        elif name.endswith(".docx"):
            doc = Document(BytesIO(data))
            for p in doc.paragraphs:
                if p.text.strip(): out.append(p.text)
        elif name.endswith(".pptx"):
            prs = Presentation(BytesIO(data))
            for s in prs.slides:
                for sh in s.shapes:
                    txt = getattr(sh, "text", "")
                    if txt and txt.strip(): out.append(txt)
    return ("\n".join(out)).encode("ascii","ignore").decode("ascii")


class StylesAPI(APIView):
    def get(self, _):
        return Response(repo.list_styles())

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail":"name required"}, status=400)
        data = repo.create_or_update_style(name=name,
                                           style=request.data.get("style",""),
                                           example=request.data.get("example",""))
        return Response({"id": data["id"], "name": data["name"]})

class StyleDetailAPI(APIView):
    def delete(self, request, style_id):
        repo.delete_style(str(style_id))
        return Response(status=204)

class OutputsAPI(APIView):
    def get(self, _):
        return Response(repo.list_outputs())

class RewriteAPI(APIView):
    def post(self, request):
        content = request.data.get("content","")
        if not content.strip():
            return Response({"detail":"content empty"}, status=400)
        style      = request.data.get("style","")
        example    = request.data.get("example","")
        guidelines = request.data.get("guidelines","")
        style_id   = request.data.get("styleId","Style")

        from .services.prompts import rewrite_content as llm_rewrite
        rewritten = llm_rewrite(content_all=content, style=style, guidelines=guidelines, example=example)
        saved = repo.save_output(style_name=style_id, input_text=content, output_text=rewritten)
        return Response({"output": rewritten, "output_id": saved["id"]})

from .services.prompts import extract_style as llm_extract_style

class ExtractStyleAPI(APIView):
    def post(self, request):
        example_text = request.data.get("exampleText", "")
        files = request.FILES.getlist("files")
        combined = (example_text + "\n" + extract_text_from_files(files)).strip()
        if not combined:
            return Response({"detail": "empty input"}, status=status.HTTP_400_BAD_REQUEST)
        style_text = llm_extract_style(combined_text=combined, temperature=0.0)
        return Response({"style": style_text})


class ChatStartAPI(APIView):
    def post(self, request):
        user_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID", "")  # Azure header if present
        title = (request.data.get("title") or "").strip()
        th = ChatThread.objects.create(title=title, user_id=user_id)
        # seed with a system message if you want to customize per-thread
        ChatMessage.objects.create(thread=th, role="system", content="")
        return Response({"thread_id": th.id}, status=201)

# backend/api/views.py
class ChatHistoryAPI(APIView):
    def get(self, request):
        thread_id = request.query_params.get("thread_id")
        th = get_object_or_404(ChatThread, id=thread_id)
        msgs = [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),  # ← serialize
            }
            for m in th.messages.order_by("created_at")
        ]
        return Response({"thread_id": th.id, "messages": msgs})


class ChatMessageAPI(APIView):
    def post(self, request):
        """
        body: { thread_id, content, temperature? }
        """
        data = request.data
        thread_id = data.get("thread_id")
        content = (data.get("content") or "").strip()
        temperature = float(data.get("temperature") or 0.7)

        if not thread_id or not content:
            return Response({"detail": "thread_id and content required"}, status=400)

        th = get_object_or_404(ChatThread, id=thread_id)

        # Save user message
        ChatMessage.objects.create(thread=th, role="user", content=content)

        # Build history for LLM
        history = [
            {"role": m.role, "content": m.content}
            for m in th.messages.order_by("created_at")
            if m.content.strip()
        ]

        # Call Azure LLM
        assistant_text = run_chat(history, temperature=temperature)

        # Save assistant message
        ChatMessage.objects.create(thread=th, role="assistant", content=assistant_text or "")

        return Response({"output": assistant_text})

class ChatModelsAPI(APIView):
    """
    GET /api/chat/models/  ->  { models: LLM_CONFIG, workweb: LLM_WORKWEB }
    Used by frontend to populate the model selector and Work/Web toggle.
    """
    def get(self, _):
        return Response({
            "models": _load_json_env("LLM_CONFIG"),
            "workweb": _load_json_env("LLM_WORKWEB"),
        })


class ChatThreadsAPI(APIView):
    """List chat threads with metadata for the sidebar.
    GET /api/chat/threads/
    Returns: [{thread_id, title, last_message, last_updated, created_at}]
    """
    def get(self, request):
        threads = ChatThread.objects.order_by("-created_at").all()[:50]
        out = []
        for th in threads:
            last = th.messages.order_by("-created_at").first()
            out.append({
                "thread_id": th.id,
                "title": th.title or (last.content[:60] if last else "New chat"),
                "last_message": last.content if last else "",
                "last_updated": last.created_at.isoformat() if last else th.created_at.isoformat(),
                "created_at": th.created_at.isoformat(),
            })
        return Response(out)


@method_decorator(csrf_exempt, name="dispatch")
class ChatStreamAPI(APIView):
    """
    Minimal Server-Sent Events endpoint.
    Streams back tokens so your React UI can render progressively.
    Replace the generator body with your Foundry streaming later.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # Payload your UI sends:
        # { thread_id, content, provider: "foundry", model_deployment, mode }
        try:
            data = request.data if request.content_type != "application/x-www-form-urlencoded" else request.POST
            user_text = (data.get("content") or "").strip()
            thread_id = data.get("thread_id") or data.get("thread")
            provider = (data.get("provider") or "").lower()
            deployment = data.get("deployment") or data.get("model_deployment") or data.get("model")
            mode = (data.get("mode") or "work").lower()
        except Exception:
            user_text = ""

        def sse_event(name: str, data_str: str):
            yield f"event: {name}\n"
            # each line of data must be prefixed with "data: "
            for line in data_str.splitlines() or [""]:
                yield f"data: {line}\n"
            yield "\n"

        def gen():
            # tell client we’re ready
            yield from sse_event("ready", "{}")

            # If client requested Foundry provider, use the streaming implementation
            if provider == "foundry":
                if not thread_id:
                    yield from sse_event("error", json.dumps({"detail": "thread_id required for streaming"}))
                    yield from sse_event("done", "{}")
                    return

                try:
                    # stream_foundry_chat yields token strings (not SSE frames)
                    th = get_object_or_404(ChatThread, id=thread_id)
                    tokens = []
                    for token in stream_foundry_chat(thread_db_id=int(thread_id), user_text=user_text, model_deployment=deployment or "", mode=mode):
                        # each token is a string chunk
                        tokens.append(token)
                        yield from sse_event("token", token)
                    # persist final assistant message (merge tokens with spacing rules)
                    try:
                        def _merge_tokens(ts: list[str]) -> str:
                            if not ts:
                                return ""
                            out = ts[0]
                            for t in ts[1:]:
                                if out and out[-1].isalnum() and t and t[0].isalnum():
                                    out += " " + t
                                else:
                                    out += t
                            return out

                        assistant_text = _merge_tokens(tokens)
                        ChatMessage.objects.create(thread=th, role="assistant", content=assistant_text)
                    except Exception:
                        # don't crash the stream if DB save fails
                        pass
                    yield from sse_event("done", json.dumps({"ok": True}))
                    return
                except Exception as e:
                    try:
                        detail = {"detail": str(e)}
                        yield from sse_event("error", json.dumps(detail))
                    except Exception:
                        yield from sse_event("error", json.dumps({"detail": "streaming failed"}))
                    yield from sse_event("done", "{}")
                    return

            # Fallback demo stream when no provider or not foundry
            if not user_text:
                yield from sse_event("token", "Hello! 👋")
                yield from sse_event("done", "{}")
                return

            for word in (user_text.split() or []):
                yield from sse_event("token", word + " ")
                time.sleep(0.03)  # small drip so you see streaming

            # Example: send an extra completion suffix
            yield from sse_event("token", "\n\n(placeholder stream — wire Foundry here)")
            yield from sse_event("done", json.dumps({"ok": True}))

        resp = StreamingHttpResponse(gen(), content_type="text/event-stream; charset=utf-8")
        # important for proxies/buffers
        resp["Cache-Control"] = "no-cache"
        resp["X-Accel-Buffering"] = "no"
        return resp


@method_decorator(csrf_exempt, name="dispatch")
class ResearchStreamAPI(APIView):
    """
    POST /api/research/stream
    body: { topic: str }
    Streams SSE events from deep research pipeline.
    """
    def post(self, request):
        topic = (request.data.get("topic") or "").strip()
        if not topic:
            return Response({"detail": "topic required"}, status=400)

        q: Queue[bytes] = Queue(maxsize=100)

        # bridge: the notify callback enqueues SSE frames
        async def notify(event: str, payload: dict):
            try:
                frame = sse_format(json.dumps(payload), event=event)
                q.put(frame, timeout=2)
            except Exception:
                pass

        # run the async pipeline in a dedicated thread with its own loop
        def runner():
            import chatui.deep_research.pipeline as dr
            async def main():
                try:
                    result = await dr.run_deep_research(topic, notify=notify)
                    # final "done" event with summary
                    q.put(sse_format(json.dumps({"summary": result}), event="done"))
                except Exception as e:
                    q.put(sse_format(json.dumps({"error": str(e)}), event="error"))
                finally:
                    # sentinel to close the stream
                    q.put(b"__CLOSE__")

            asyncio.run(main())

        threading.Thread(target=runner, daemon=True).start()

        def gen():
            # immediate ack
            yield sse_format("started", event="ready")
            while True:
                try:
                    item = q.get(timeout=30)
                    if item == b"__CLOSE__":
                        break
                    yield item
                except Empty:
                    # keep-alive
                    yield sse_format("ping", event="keepalive")

        return sse_response(gen())