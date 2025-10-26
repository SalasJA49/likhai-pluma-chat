# backend/api/services/sse.py
from django.http import StreamingHttpResponse

def sse_format(data: str, event: str | None = None) -> bytes:
    parts = []
    if event:
        parts.append(f"event: {event}")
    for line in (data.splitlines() or [""]):
        parts.append(f"data: {line}")
    parts.append("")
    return ("\n".join(parts) + "\n").encode("utf-8")

def sse_response(generator):
    resp = StreamingHttpResponse(generator, content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp
