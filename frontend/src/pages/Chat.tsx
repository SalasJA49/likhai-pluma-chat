import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { startThread, getHistory, streamChat, uploadChatFiles, uploadChatFilesFoundry } from "../lib/api";

type Attachment = { id: number; filename: string; blob_url: string; content_type: string };
type Msg = { role: "user" | "assistant"; content: string; attachments?: Attachment[] };

// If you want these from env later, you can fetch them from an endpoint.
// For now, keep simple + explicit.
const MODEL_OPTIONS = [
  { value: "foundry/gpt-4.1-mini", label: "foundry/gpt-4.1-mini" },
  { value: "foundry/gpt-4o", label: "foundry/gpt-4o" },
];

export default function Chat() {
  const [threadId, setThreadId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<File[]>([]);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // UI controls
  const [model, setModel] = useState<string>(MODEL_OPTIONS[0].value);
  const [mode, setMode] = useState<"work" | "web">("work");
  const [deployment] = useState<string>("foundry/gpt-4.1-mini");
  const scrollRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        // if a thread_id is provided in the query params, use it; otherwise create a new thread
        const params = new URLSearchParams(window.location.search);
        const q = params.get("thread_id");
        let thread_id: number;
        if (q) {
          thread_id = Number(q);
        } else {
          const res = await startThread("New conversation");
          thread_id = res.thread_id;
          // push new url
          const u = new URL(window.location.href);
          u.searchParams.set("thread_id", String(thread_id));
          window.history.replaceState({}, "", u.toString());
        }
        setThreadId(thread_id);
        const hist = await getHistory(thread_id);
        setMessages(
          ((hist.messages || []) as any)
            .filter((m: any) => m.role === "user" || m.role === "assistant")
            .map((m: any) => ({ role: m.role as Msg["role"], content: m.content, attachments: m.attachments || [] }))
        );
        // signal threads loading finished (if sidebar triggered a loading state)
        try{ window.dispatchEvent(new CustomEvent('thread:loading:done', { detail: thread_id })); }catch(e){}
      } catch (e: any) {
        console.error("Failed to start thread:", e);
        setError("Failed to create chat session — check backend (see console)");
      }
    })();
  }, []);

  // react to URL thread_id changes (when user clicks sidebar links)
  useEffect(() => {
    (async () => {
      try {
        const params = new URLSearchParams(location.search);
        const q = params.get("thread_id");
        if (q) {
          const tid = Number(q);
          if (tid && tid !== threadId) {
            setThreadId(tid);
            const hist = await getHistory(tid);
            setMessages(
              ((hist.messages || []) as any)
                .filter((m: any) => m.role === "user" || m.role === "assistant")
                .map((m: any) => ({ role: m.role as Msg["role"], content: m.content, attachments: m.attachments || [] }))
            );
            try{ window.dispatchEvent(new CustomEvent('thread:loading:done', { detail: tid })); }catch(e){}
          }
        }
      } catch (e) {
        // ignore
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if (!threadId || sending) return;

    setSending(true);
    let finalUserText = (input || "").trim();
      if ((!finalUserText || finalUserText.length === 0) && attachments.length === 0) {
        // nothing to send
        setSending(false);
        return;
      }

      if (attachments && attachments.length > 0) {
        try {
          // If using Foundry provider, directly upload files to Foundry and stream the run.
          const isFoundry = (deployment || "").toLowerCase().startsWith("foundry/");
          if (isFoundry) {
            const fd = new FormData();
            fd.append("thread_id", String(threadId));
            fd.append("model_deployment", deployment);
            fd.append("mode", mode);
            if (finalUserText) fd.append("content", finalUserText);
            for (const f of attachments) fd.append("files", f);

            // Use FormData-based SSE helper
            const sse = uploadChatFilesFoundry(fd);
            // Optimistic UI: we already appended a user+assistant placeholder below; we'll stream tokens into the assistant placeholder
            sse.on(
              async (ev) => {
                const type = ev.type || "message";
                if (type === "ready") {
                  setIsStreaming(true);
                  return;
                }
                if (type === "token") {
                  const chunk = String(ev.data || "");
                  setMessages((prev) => {
                    const clone = prev.slice();
                    const last = clone[clone.length - 1];
                    if (last?.role === "assistant") {
                      const prevText = last.content || "";
                      const prevEndsAlnum = /[A-Za-z0-9]$/.test(prevText);
                      const chunkStartsAlnum = /^[A-Za-z0-9]/.test(chunk);
                      if (prevEndsAlnum && chunkStartsAlnum) {
                        last.content += " " + chunk;
                      } else {
                        last.content += chunk;
                      }
                    }
                    return clone;
                  });
                } else if (type === "error") {
                  try {
                    const parsed = JSON.parse(String(ev.data || "{}"));
                    setMessages((prev) => {
                      const clone = prev.slice();
                      const last = clone[clone.length - 1];
                      if (last?.role === "assistant" && !last.content) last.content = `⚠️ ${parsed?.detail || "stream error"}`;
                      return clone;
                    });
                  } catch {
                    // ignore
                  }
                } else if (type === "done") {
                  setIsStreaming(false);
                  try { window.dispatchEvent(new CustomEvent('threads:changed')); } catch(e){}
                  try {
                    if (threadId) {
                      const hist = await getHistory(threadId);
                      setMessages(
                        (hist.messages || [])
                          .filter((m) => m.role === "user" || m.role === "assistant")
                          .map((m) => ({ role: m.role as Msg["role"], content: m.content }))
                      );
                    }
                  } catch (e) {}
                }
              },
              (e) => {
                console.error("SSE failed:", e);
                setIsStreaming(false);
                setMessages((prev) => {
                  const clone = prev.slice();
                  const last = clone[clone.length - 1];
                  if (last?.role === "assistant" && !last.content) {
                    last.content = "⚠️ Sorry, something went wrong.";
                  }
                  return clone;
                });
              }
            );

            // clear attachments handled in finally
            setSending(false);
            setAttachments([]);
            if (fileRef.current) fileRef.current.value = "";
            return; // we've handled streaming via Foundry upload — exit send()
          }

          // Fallback: non-Foundry, server will extract text and return it
          const fd = new FormData();
          for (const f of attachments) fd.append("files", f);
          const res = await uploadChatFiles(fd);
          if (res && res.text) {
            finalUserText = (finalUserText ? finalUserText + "\n\n" : "") + res.text;
          }
        } catch (e) {
          // if upload/extract fails, still proceed with whatever text we have
        }
      }

    
    // clear input immediately for UX
    setInput("");

    // Optimistic UI
    setMessages((prev) => [...prev, { role: "user", content: finalUserText }, { role: "assistant", content: "" }]);

    try {
      const sse = streamChat({
        thread_id: threadId,
        content: finalUserText,
        // always Foundry:
        provider: "foundry",
        mode,               // "work" or "web"
        deployment  
      } as any);

      sse.on(
        async (ev) => {
          const type = ev.type || "message";

          if (type === "ready") {
            setIsStreaming(true);
            return;
          }

          if (type === "token") {
            const chunk = String(ev.data || "");
            setMessages((prev) => {
              const clone = prev.slice();
              const last = clone[clone.length - 1];
              if (last?.role === "assistant") {
                const prevText = last.content || "";
                // Only insert a space when both the previous char and the chunk start are alphanumeric
                const prevEndsAlnum = /[A-Za-z0-9]$/.test(prevText);
                const chunkStartsAlnum = /^[A-Za-z0-9]/.test(chunk);
                if (prevEndsAlnum && chunkStartsAlnum) {
                  last.content += " " + chunk;
                } else {
                  last.content += chunk;
                }
              }
              return clone;
            });
          } else if (type === "error") {
            let msg = "⚠️ Sorry, something went wrong.";
            try {
              const parsed = JSON.parse(String(ev.data || "{}"));
              if (parsed?.detail) msg = `⚠️ ${parsed.detail}`;
            } catch {}
            setMessages((prev) => {
              const clone = prev.slice();
              const last = clone[clone.length - 1];
              if (last?.role === "assistant" && !last.content) last.content = msg;
              return clone;
            });
          } else if (type === "done") {
            setIsStreaming(false);
            try { window.dispatchEvent(new CustomEvent('threads:changed')); } catch(e) {}
            // Ensure we refresh canonical history from the server so persisted user messages
            // saved by the streaming endpoint are reflected in the UI.
            try {
              if (threadId) {
                const hist = await getHistory(threadId);
                setMessages(
                  (hist.messages || [])
                    .filter((m) => m.role === "user" || m.role === "assistant")
                    .map((m) => ({ role: m.role as Msg["role"], content: m.content }))
                );
              }
            } catch (e) {
              // ignore refresh errors
            }
          }
          // ignore "ready", "keepalive" in the UI; "done" triggers threads refresh
        },
  (e) => {
          console.error("SSE failed:", e);
          setIsStreaming(false);
          setMessages((prev) => {
            const clone = prev.slice();
            const last = clone[clone.length - 1];
            if (last?.role === "assistant" && !last.content) {
              last.content = "⚠️ Sorry, something went wrong.";
            }
            return clone;
          });
        }
      );
    } finally {
      setSending(false);
      // clear attachments after attempt
      setAttachments([]);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onSelectFiles = (files: FileList | null) => {
    if (!files) return;
    const arr = Array.from(files);
    setAttachments(arr);
  };

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Title */}
      <div className="flex items-center gap-3">
        <span className="text-2xl">💬</span>
        <h1 className="text-2xl font-semibold">Chatbot</h1>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      {/* Controls (Foundry implied) */}
      <div className="bg-white rounded-xl shadow-sm ring-1 ring-slate-200 p-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Model (Foundry only) */}
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-slate-700 mb-2">Model</label>
            <select
              className="w-full rounded-lg border border-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            >
              {MODEL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-2">
              Foundry routing for Work/Web is applied using your environment mapping.
            </p>
          </div>

          {/* Mode */}
          <div className="flex flex-col">
            <label className="block text-sm font-medium text-slate-700 mb-2">Mode</label>
            <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden w-max">
              <button
                className={`px-4 py-2 text-sm ${mode === "work" ? "bg-blue-600 text-white" : "bg-white text-slate-700"}`}
                onClick={() => setMode("work")}
              >
                Work
              </button>
              <button
                className={`px-4 py-2 text-sm ${mode === "web" ? "bg-blue-600 text-white" : "bg-white text-slate-700"}`}
                onClick={() => setMode("web")}
              >
                Web
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Conversation */}
      <div className="bg-white rounded-xl shadow-sm ring-1 ring-slate-200 p-5">
        <h2 className="text-sm font-semibold text-slate-700 mb-3">Conversation</h2>

        {isStreaming && (
          <div className="text-xs text-slate-500 mb-2">Assistant is typing…</div>
        )}

        <div
          ref={scrollRef}
          className="h-[54vh] overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-4"
        >
          {messages.length === 0 && (
            <p className="text-slate-500 text-sm">Ask me anything to get started…</p>
          )}

          <div className="space-y-3">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`max-w-[85%] whitespace-pre-wrap px-3 py-2 rounded-lg ${
                  m.role === "user"
                    ? "bg-blue-600 text-white ml-auto"
                    : "bg-white border border-slate-200 text-slate-800"
                }`}
              >
                <div>{m.content || (m.role === "assistant" ? "…" : "")}</div>
                {m.attachments && m.attachments.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {m.attachments.map((a) => (
                      <div key={a.id} className="text-xs text-slate-500">
                        {a.blob_url ? (
                          <a href={a.blob_url} target="_blank" rel="noreferrer" className="underline">
                            {a.filename}
                          </a>
                        ) : (
                          <span>{a.filename}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Composer */}
        <div className="mt-4 flex items-end gap-3">
          <textarea
            className="flex-1 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 p-3 h-[64px] resize-y"
            placeholder="Type a message…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          <button
            onClick={send}
            disabled={!threadId || (!input.trim() && attachments.length === 0) || sending}
            className="h-[44px] min-w-[80px] rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending ? "Sending…" : "Send"}
          </button>
        </div>
        {/* Attachment area below composer */}
        <div className="mt-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <input ref={fileRef} type="file" className="hidden" onChange={(e)=>onSelectFiles(e.target.files)} multiple />
            <button onClick={()=>fileRef.current?.click()} className="text-sm text-slate-600 hover:underline">Attach files</button>
            <div className="text-xs text-slate-400">{attachments.length>0 ? attachments.map(a=>a.name).join(', ') : ''}</div>
          </div>
          <div className="text-xs text-slate-400">You can attach .pdf, .docx, images</div>
        </div>
      </div>
    </div>
  );
}
