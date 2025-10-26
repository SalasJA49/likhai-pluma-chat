import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { startThread, getHistory, streamChat } from "../lib/api";

type Msg = { role: "user" | "assistant"; content: string };

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
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // UI controls
  const [model, setModel] = useState<string>(MODEL_OPTIONS[0].value);
  const [mode, setMode] = useState<"work" | "web">("work");
  const [deployment, setDeployment] = useState<string>("foundry/gpt-4.1-mini");
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
          (hist.messages || [])
            .filter((m) => m.role === "user" || m.role === "assistant")
            .map((m) => ({ role: m.role as Msg["role"], content: m.content }))
        );
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
              (hist.messages || [])
                .filter((m) => m.role === "user" || m.role === "assistant")
                .map((m) => ({ role: m.role as Msg["role"], content: m.content }))
            );
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
    if (!threadId || !input.trim() || sending) return;

    const userText = input.trim();
    setInput("");
    setSending(true);

    // Optimistic UI
    setMessages((prev) => [...prev, { role: "user", content: userText }, { role: "assistant", content: "" }]);

    try {
      const sse = streamChat({
        thread_id: threadId,
        content: userText,
        // always Foundry:
        provider: "foundry",
        mode,               // "work" or "web"
        deployment  
      } as any);

      sse.on(
        (ev) => {
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
    }
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
                {m.content || (m.role === "assistant" ? "…" : "")}
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
            disabled={!threadId || !input.trim() || sending}
            className="h-[44px] min-w-[80px] rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending ? "Sending…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
