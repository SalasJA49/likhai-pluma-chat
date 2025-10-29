import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { startThread, getHistory, streamChat, uploadChatFiles, uploadChatFilesFoundry, streamResearch, streamReasoning, edaProcess } from "../lib/api";
import DataTable from "../components/DataTable";
import StatsTable from "../components/StatsTable";
import PlotlyChart from "../components/PlotlyChart";
import Markdown from "../components/Markdown";

type Attachment = { id: number; filename: string; blob_url: string; content_type: string };
type Msg = {
  role: "user" | "assistant";
  content: string;
  attachments?: Attachment[];
  pending?: boolean;
  completed?: boolean;
  figure?: any;
  title?: string;
  dataTable?: { title?: string; columns: string[]; rows: Array<Record<string, any>> } | null;
  stats?: Record<string, any> | null;
};

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
  const [feature, setFeature] = useState<string>("none");
  const scrollRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const [, setIsStreaming] = useState(false);
  const [debugEvents, setDebugEvents] = useState<Array<{time:number; type:string; payload:any}>>([]);
  const [showDebug, setShowDebug] = useState(false);

  // Track indices of placeholder messages for live step updates
  const stepIdxRef = useRef<Record<string, number | undefined>>({});

  // Helper to push assistant message and optionally remember its index under a key
  const pushAssistantMsg = (content: string, opts?: { pending?: boolean; key?: string }) => {
    setMessages((prev) => {
      const idx = prev.length;
      if (opts?.key) stepIdxRef.current[opts.key] = idx;
      return [...prev, { role: "assistant", content, pending: !!opts?.pending }];
    });
  };

  // Helpers to render pipeline steps as conversation bubbles
  const replaceOrPushAssistant = (content: string, opts?: { pending?: boolean; key?: string; completed?: boolean }) =>
    setMessages((prev) => {
      const clone = prev.slice();
      const last = clone[clone.length - 1];
      if (last?.role === "assistant" && (!last.content || String(last.content).trim() === "")) {
        last.content = content;
        if (opts?.pending) last.pending = true; else delete last.pending;
        if (opts?.completed) last.completed = true; else delete last.completed;
        if (opts?.key) stepIdxRef.current[opts.key] = clone.length - 1;
        return clone;
      }
      const idx = clone.length;
      if (opts?.key) stepIdxRef.current[opts.key] = idx;
      return [...clone, { role: "assistant", content, pending: !!opts?.pending, completed: !!opts?.completed }];
    });

  // Replace content of a remembered step message
  const replaceStep = (key: string, content: string, opts?: { pending?: boolean; completed?: boolean }) => {
    setMessages((prev) => {
      const idx = stepIdxRef.current[key];
      if (idx === undefined) return prev;
      const clone = prev.slice();
      const msg = clone[idx];
      if (!msg) return prev;
      msg.content = content;
      if (opts?.pending) msg.pending = true; else delete msg.pending;
      if (opts?.completed) msg.completed = true; else delete msg.completed;
      return clone;
    });
  };
  const safeJSON = (s: string) => { try { return JSON.parse(s); } catch { return null; } };
  const fmt = (s: string) => (s || "").trim();

  // Smarter concatenation to avoid breaking acronyms like "BSP" while still inserting
  // spaces between normal word boundaries when providers stream chunks without them.
  const concatChunk = (prevText: string, chunk: string) => {
    if (!chunk) return prevText;
    if (!prevText) return chunk;

    // If either side already has whitespace at the boundary, just join.
    if (/\s$/.test(prevText) || /^\s/.test(chunk)) return prevText + chunk;

    const prevEndsAlnum = /[A-Za-z0-9]$/.test(prevText);
    const chunkStartsAlnum = /^[A-Za-z0-9]/.test(chunk);

    if (prevEndsAlnum && chunkStartsAlnum) {
      const lastToken = (prevText.match(/[A-Za-z0-9]+$/) || [""])[0];
      const firstToken = (chunk.match(/^[A-Za-z0-9]+/) || [""])[0];
      const isAllCapsOrDigits = (s: string) => /^[A-Z0-9]+$/.test(s);
      const firstTokenStartsUpperThenLower = /^[A-Z][a-z]/.test(firstToken);

      // If both sides look like an acronym/code (no lowercase), don't insert a space.
      // Examples: "B"+"SP" -> BSP, "ISO"+"9001" -> ISO9001
      if (isAllCapsOrDigits(lastToken) && isAllCapsOrDigits(firstToken)) {
        return prevText + chunk;
      }

      // If the incoming token looks like a Capitalized word (e.g., "Assistant"),
      // insert a space so we get "AI Assistant", not "AIAssistant".
      if (firstTokenStartsUpperThenLower) {
        return prevText + " " + chunk;
      }

      // Default: add a space between alnum boundaries
      return prevText + " " + chunk;
    }

    // Punctuation or other characters — join as-is
    return prevText + chunk;
  };

  // Plotly rendering handled by shared component (react-plotly.js lazy loaded)

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

      // If EDA is selected, skip the generic attachment pipeline (Foundry upload/extract)
      // so the attached file is handled by the EDA flow below.
      if (feature !== "eda" && attachments && attachments.length > 0) {
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
                      last.content = concatChunk(last.content || "", chunk);
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
                  // Refresh sidebar and reload history so the final, canonical
                  // assistant message from the backend is displayed.
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
      // If an advanced feature is selected, route to its stream endpoint.
      if (feature === "deep_research") {
        const sse = streamResearch(String(finalUserText || ""));
        sse.on(
          async (ev) => {
              // Log raw events for debugging (keeps the most recent 50)
              try {
                const parsed = JSON.parse(String(ev.data || ""));
                setDebugEvents((prev) => [{ time: Date.now(), type: ev.type || "message", payload: parsed }, ...prev].slice(0, 50));
              } catch (e) {
                setDebugEvents((prev) => [{ time: Date.now(), type: ev.type || "message", payload: String(ev.data || "") }, ...prev].slice(0, 50));
              }

            const type = ev.type || "message";
            if (type === "ready") {
              setIsStreaming(true);
              // fresh run: clear step indices and create a status message
              stepIdxRef.current = {};
              // replace the initial empty assistant bubble with a status row
              replaceOrPushAssistant("Starting deep research…", { pending: true, key: "status" });
              return;
            }
            if (type === "token") {
              const chunk = String(ev.data || "");
              setMessages((prev) => {
                const clone = prev.slice();
                const last = clone[clone.length - 1];
                if (last?.role === "assistant") {
                  last.content = concatChunk(last.content || "", chunk);
                }
                return clone;
              });
            }
            else if (type === "thinking") {
              const parsed = safeJSON(String(ev.data || ""));
              const thoughts = fmt(parsed?.thoughts || parsed?.thought || String(ev.data || ""));
              // push a separate step message; keep status bubble
              pushAssistantMsg(`Step: Thinking\n\n${thoughts}`);
            } else if (type === "debug_model_response" || type === "debug") {
              // Don't surface internal debug frames in the chat; they remain in the debug panel
              // (We still capture them below in debugEvents.)
            }
            // Handle structured pipeline events as separate, human-readable steps
            else if (type === "generate_query") {
              const p = safeJSON(String(ev.data || "")) || {};
              const q = fmt(p.query || "");
              const r = fmt(p.rationale || "");
              pushAssistantMsg(`Step: Initial query\n\nQuery: ${q}\nRationale: ${r}`);
              // anticipate next step: searching the web…
              pushAssistantMsg("Searching the web…", { pending: true, key: "web" });
            } else if (type === "web_research") {
              const p = safeJSON(String(ev.data || "")) || {};
              const sources: any[] = Array.isArray(p.sources) ? p.sources : [];
              const lines = sources.slice(0, 3).map((s, i) => `- ${s.title || s.url || `Source ${i+1}`}${s.url ? `\n  ${s.url}` : ""}`).join("\n");
              // update web placeholder if present, else push
              if (stepIdxRef.current["web"] !== undefined) {
                replaceStep("web", `Step: Web research\n\nSources:\n${lines || "(no sources)"}`);
              } else {
                pushAssistantMsg(`Step: Web research\n\nSources:\n${lines || "(no sources)"}`);
              }
              // anticipate summarize step
              pushAssistantMsg("Summarizing sources…", { pending: true, key: "sum" });
            } else if (type === "summarize") {
              const p = safeJSON(String(ev.data || "")) || {};
              const summary = fmt(p.summary || String(ev.data || ""));
              if (stepIdxRef.current["sum"] !== undefined) {
                replaceStep("sum", `Step: Summary update\n\n${summary}`);
              } else {
                pushAssistantMsg(`Step: Summary update\n\n${summary}`);
              }
              // anticipate reflection step
              pushAssistantMsg("Reflecting on gaps…", { pending: true, key: "refl" });
            } else if (type === "reflection") {
              const p = safeJSON(String(ev.data || "")) || {};
              const gap = fmt(p.knowledge_gap || "");
              const q2 = fmt(p.query || "");
              if (stepIdxRef.current["refl"] !== undefined) {
                replaceStep("refl", `Step: Reflection\n\nKnowledge gap: ${gap}\nFollow-up query: ${q2}`);
              } else {
                pushAssistantMsg(`Step: Reflection\n\nKnowledge gap: ${gap}\nFollow-up query: ${q2}`);
              }
            } else if (type === "finalize") {
              const p = safeJSON(String(ev.data || "")) || {};
              const summary = fmt(p.summary || String(ev.data || ""));
              const imgs: string[] = Array.isArray(p.images) ? p.images.slice(0,2) : [];
              const imgLines = imgs.map((u,i)=>`Image ${i+1}: ${u}`).join("\n");
              // if we had a finalize placeholder, replace it; otherwise push
              if (stepIdxRef.current["finalize"] !== undefined) {
                replaceStep("finalize", `Final summary\n\n${summary}${imgLines? `\n\n${imgLines}`: ""}`);
              } else {
                pushAssistantMsg(`Final summary\n\n${summary}${imgLines? `\n\n${imgLines}`: ""}`);
              }
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
              // If backend sent a final summary in the 'done' frame, surface it
              const p = safeJSON(String(ev.data || ""));
              if (p && p.summary) {
                const finalText = `Final summary\n\n${fmt(p.summary)}`;
                setMessages((prev) => {
                  const clone = prev.slice();
                  const last = clone[clone.length - 1];
                  if (last?.role === "assistant" && typeof last.content === "string" && last.content.startsWith("Final summary")) {
                    return clone; // avoid duplicate
                  }
                  return [...clone, { role: "assistant", content: finalText }];
                });
              }
              // update status row to completed with a check icon
              if (stepIdxRef.current["status"] !== undefined) {
                replaceStep("status", "Deep Research Complete", { pending: false, completed: true });
              }
              // We intentionally avoid replacing messages with history here to prevent races.
              try { window.dispatchEvent(new CustomEvent('threads:changed')); } catch(e) {}
            }
          },
          (e) => {
            console.error("Deep research SSE failed:", e);
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
      } else if (feature === "reasoning") {
        const useFoundry = (deployment || "").toLowerCase().startsWith("foundry/");
        const sse = streamReasoning({
          query: String(finalUserText || ""),
          provider: useFoundry ? "foundry" : undefined,
          model_deployment: useFoundry ? deployment : undefined,
          mode: useFoundry ? mode : undefined,
        });
        sse.on(
          async (ev) => {
            // Log events for debugging (keeps the most recent 50)
            try {
              const parsed = JSON.parse(String(ev.data || ""));
              setDebugEvents((prev) => [{ time: Date.now(), type: ev.type || "message", payload: parsed }, ...prev].slice(0, 50));
            } catch (e) {
              setDebugEvents((prev) => [{ time: Date.now(), type: ev.type || "message", payload: String(ev.data || "") }, ...prev].slice(0, 50));
            }

            const type = ev.type || "message";
            if (type === "ready") {
              setIsStreaming(true);
              stepIdxRef.current = {};
              replaceOrPushAssistant("Starting reasoning…", { pending: true, key: "r-status" });
              return;
            }
            if (type === "thinking") {
              const parsed = safeJSON(String(ev.data || ""));
              const msg = fmt(parsed?.message || parsed?.detail || "Thinking…");
              // Keep a single thinking bubble updated
              replaceOrPushAssistant(`Step: Thinking\n\n${msg}`, { key: "r-thinking" });
            } else if (type === "fallback") {
              const parsed = safeJSON(String(ev.data || ""));
              const msg = fmt(parsed?.message || "Using fallback.");
              pushAssistantMsg(msg);
            } else if (type === "finalize") {
              const parsed = safeJSON(String(ev.data || ""));
              const msg = fmt(parsed?.message || "Formatting reasoning output.");
              pushAssistantMsg(msg);
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
              const p = safeJSON(String(ev.data || ""));
              const mk = fmt(p?.markdown || "");
              if (mk) {
                setMessages((prev) => [...prev, { role: "assistant", content: mk }]);
              }
              if (stepIdxRef.current["r-status"] !== undefined) {
                replaceStep("r-status", "Reasoning Complete", { completed: true });
              }
              try { window.dispatchEvent(new CustomEvent('threads:changed')); } catch(e) {}
            }
          },
          (e) => {
            console.error("Reasoning SSE failed:", e);
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
      } else if (feature === "eda") {
        // EDA flow: if a file is attached, send it; otherwise expect JSON in the prompt or simple demo data
        try {
          let payload: any;
          if (attachments && attachments.length > 0) {
            const fd = new FormData();
            fd.append("prompt", finalUserText || "");
            fd.append("file", attachments[0]);
            // If using Foundry, pass provider + mapping inputs so backend can resolve agent id
            const isFoundry = (deployment || "").toLowerCase().startsWith("foundry/");
            if (isFoundry) {
              fd.append("provider", "foundry");
              fd.append("model_deployment", deployment);
              fd.append("mode", mode);
            }
            payload = fd;
          } else {
            // try to parse JSON array/object from the prompt; if not, return a friendly hint
            let data: any = undefined;
            try {
              data = JSON.parse(finalUserText);
            } catch {}
            if (!data) {
              setMessages((prev) => [...prev, { role: "assistant", content: "📁 For EDA, attach a CSV/XLSX file or paste JSON data in the message." }]);
              return;
            }
            const isFoundry = (deployment || "").toLowerCase().startsWith("foundry/");
            payload = isFoundry ? { data, prompt: "", provider: "foundry", model_deployment: deployment, mode } : { data, prompt: "" };
          }

          // Add a status row with spinner
          replaceOrPushAssistant("Starting EDA…", { pending: true, key: "eda-status" });
          const res = await edaProcess(payload);
          // Update status
          replaceStep("eda-status", "EDA Complete", { completed: true });

          // Render charts: each chart is a Plotly figure JSON
          const charts = (res?.charts?.charts || []) as Array<{ figure: any; title?: string; reason?: string; type?: string }>;
          if (charts.length > 0) {
            charts.forEach((c, i) => {
              setMessages((prev) => [
                ...prev,
                { role: "assistant", content: `Chart ${i + 1}${c.title ? `: ${c.title}` : ""}${c.reason ? `\n\n_${c.reason}_` : ""}`, figure: c.figure, title: c.title },
              ]);
            });
          }

          // Render tables (Top-N + statistics) when present
          const tables: any = (res as any)?.tables || {};
          const topN = tables?.top_n;
          if (topN && Array.isArray(topN.columns) && Array.isArray(topN.rows)) {
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content: topN.title ? topN.title : "Top-N table",
                dataTable: { title: topN.title, columns: topN.columns, rows: topN.rows },
              },
            ]);
          }
          const stats = tables?.statistics;
          if (stats && typeof stats === "object") {
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content: "Descriptive statistics",
                stats,
              },
            ]);
          }

          // Show SQL transformation info if any
          const anyRes: any = res as any;
          if (anyRes?.sql_transformation) {
            const info = anyRes.sql_transformation;
            const sqlMd = `## Data Transformation Applied\n\n**SQL Query:**\n\n\`\`\`sql\n${info.query}\n\`\`\`\n\n**Summary:** ${info.summary}\n\n**Shape:** Original ${info.original_shape?.[0]}×${info.original_shape?.[1]} → Result ${info.result_shape?.[0]}×${info.result_shape?.[1]}`;
            setMessages((prev) => [...prev, { role: "assistant", content: sqlMd }]);
          }

          // Render insights synopsis
          const insights = res?.insights?.data;
          if (insights) {
            const parts: string[] = [];
            if (insights.key_findings) parts.push(`## Key findings\n${insights.key_findings}`);
            if (Array.isArray(insights.insights) && insights.insights.length) {
              parts.push(`### Insights\n${insights.insights.map((x: string, idx: number) => `${idx + 1}. ${x}`).join("\n")}`);
            }
            if (Array.isArray(insights.recommendations) && insights.recommendations.length) {
              parts.push(`### Recommendations\n${insights.recommendations.map((x: string, idx: number) => `${idx + 1}. ${x}`).join("\n")}`);
            }
            setMessages((prev) => [...prev, { role: "assistant", content: parts.join("\n\n") }]);
          }
        } catch (err: any) {
          setMessages((prev) => [...prev, { role: "assistant", content: `⚠️ EDA error: ${err?.message || err}` }]);
        }
      } else {
        const sse = streamChat({
          thread_id: threadId,
          content: finalUserText,
          // always Foundry:
          provider: "foundry",
          mode, // "work" or "web"
          deployment,
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
                  last.content = concatChunk(last.content || "", chunk);
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
            } else if (type === "thinking") {
              try {
                const parsed = JSON.parse(String(ev.data || "{}"));
                const thoughts = parsed?.thoughts || parsed?.thought || String(ev.data || "");
                setMessages((prev) => {
                  const clone = prev.slice();
                  const last = clone[clone.length - 1];
                  if (last?.role === "assistant") last.content = (last.content || "") + "\n\n[Thinking]\n" + thoughts;
                  return clone;
                });
              } catch (e) {
                const chunk = String(ev.data || "");
                setMessages((prev) => {
                  const clone = prev.slice();
                  const last = clone[clone.length - 1];
                  if (last?.role === "assistant") last.content = (last.content || "") + "\n\n[Thinking]\n" + chunk;
                  return clone;
                });
              }
            } else if (type === "debug_model_response" || type === "debug") {
              try {
                const parsed = JSON.parse(String(ev.data || "{}"));
                const text = parsed?.raw || parsed?.detail || String(ev.data || "");
                setMessages((prev) => {
                  const clone = prev.slice();
                  const last = clone[clone.length - 1];
                  if (last?.role === "assistant") last.content = (last.content || "") + "\n\n[Model]\n" + text;
                  return clone;
                });
              } catch (e) {
                const chunk = String(ev.data || "");
                setMessages((prev) => {
                  const clone = prev.slice();
                  const last = clone[clone.length - 1];
                  if (last?.role === "assistant") last.content = (last.content || "") + "\n\n[Model]\n" + chunk;
                  return clone;
                });
              }
            } else if (type === "done") {
              setIsStreaming(false);
              // Refresh sidebar and reload history for the final message
              try { window.dispatchEvent(new CustomEvent("threads:changed")); } catch (e) {}
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
      }
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
    <div className="max-w-7xl mx-auto p-6 space-y-4">
      {/* Top toolbar: model (left) · Work/Web (center) */}
      <div className="flex items-center justify-between">
        {/* Model selector (left) */}
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500">Model</label>
          <select
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          >
            {MODEL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        {/* Work/Web toggle (center) */}
        <div className="flex-1 flex items-center justify-center">
          <div className="inline-flex rounded-full border border-slate-200 bg-white overflow-hidden">
            <button
              className={`px-4 py-1.5 text-sm ${mode === "work" ? "bg-blue-600 text-white" : "text-slate-700"}`}
              onClick={() => setMode("work")}
            >
              Work
            </button>
            <button
              className={`px-4 py-1.5 text-sm ${mode === "web" ? "bg-blue-600 text-white" : "text-slate-700"}`}
              onClick={() => setMode("web")}
            >
              Web
            </button>
          </div>
        </div>
        {/* Right side spacer for symmetry */}
        <div className="w-[140px]" />
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      {/* Conversation panel */}
      <div className="bg-white rounded-2xl shadow-sm ring-1 ring-slate-200 p-4">
        <div
          ref={scrollRef}
          className="h-[58vh] overflow-y-auto rounded-xl bg-slate-50 p-4"
        >
          {messages.length === 0 ? (
            <div className="h-full w-full flex flex-col items-center justify-center select-none">
              <div className="w-40 h-40 rounded-full bg-gradient-to-br from-blue-100 to-blue-200 flex items-center justify-center ring-1 ring-slate-200">
                <span className="text-4xl">🦅</span>
              </div>
              <div className="mt-4 text-slate-500 text-sm">Type your message to start</div>
            </div>
          ) : (
            <div className="space-y-3">
              {messages.map((m, i) => (
                <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] whitespace-pre-wrap px-3 py-2 rounded-2xl shadow-sm ${
                      m.role === "user"
                        ? "bg-blue-600 text-white rounded-br-md"
                        : "bg-white border border-slate-200 text-slate-800 rounded-bl-md"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      {m.pending ? (
                        <span className="mt-1 inline-block w-4 h-4 rounded-full border-2 border-slate-300 border-t-blue-500 animate-spin" aria-label="loading" />
                      ) : m.completed ? (
                        <span className="mt-1 inline-flex items-center justify-center w-4 h-4 text-green-600" aria-label="done">✓</span>
                      ) : null}
                      <div className="flex-1 min-w-0">
                        {m.content ? <Markdown>{m.content}</Markdown> : <div>{m.role === "assistant" ? "…" : ""}</div>}
                        {m.figure ? (
                          <div className="mt-2 border border-slate-200 rounded">
                            <PlotlyChart figure={m.figure} />
                          </div>
                        ) : null}
                        {m.dataTable ? (
                          <div className="mt-3">
                            <DataTable title={m.dataTable.title} columns={m.dataTable.columns} rows={m.dataTable.rows} />
                          </div>
                        ) : null}
                        {m.stats ? (
                          <div className="mt-3">
                            <StatsTable statistics={m.stats} />
                          </div>
                        ) : null}
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
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Composer */}
        {/* Debug event log (shows raw SSE frames) */}
        {debugEvents.length > 0 && (
          <div className="mt-3 p-3 rounded border border-slate-200 bg-slate-50 text-xs">
            <div className="flex items-center justify-between mb-2">
              <div className="font-medium">SSE events (recent)</div>
              <div className="space-x-2">
                <button onClick={()=>setShowDebug(s=>!s)} className="px-2 py-1 rounded bg-white border text-xs">{showDebug? 'Hide':'Show'}</button>
                <button onClick={()=>setDebugEvents([])} className="px-2 py-1 rounded bg-white border text-xs">Clear</button>
              </div>
            </div>
            {showDebug ? (
              <div className="max-h-40 overflow-y-auto">
                {debugEvents.map((e, idx) => (
                  <div key={idx} className="mb-2">
                    <div className="text-[11px] text-slate-500">{new Date(e.time).toLocaleTimeString()} · <strong>{e.type}</strong></div>
                    <pre className="whitespace-pre-wrap text-xs mt-1 bg-white border rounded p-2">{typeof e.payload === 'string' ? e.payload : JSON.stringify(e.payload, null, 2)}</pre>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-500">Events received: {debugEvents.length}</div>
            )}
          </div>
        )}
        <div className="mt-4">
          <div className="flex items-end gap-2">
            <div className="flex-1 bg-white rounded-2xl ring-1 ring-slate-200 px-3 py-2 flex items-end">
              <button
                onClick={()=>fileRef.current?.click()}
                className="mr-2 p-2 rounded-full hover:bg-slate-100 text-slate-600"
                title="Attach"
              >📎</button>
              <textarea
                className="flex-1 outline-none p-2 min-h-[54px] max-h-[160px] resize-y text-sm"
                placeholder="Type your message here…"
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
                className="ml-2 h-10 w-10 rounded-full bg-blue-600 text-white grid place-items-center disabled:opacity-50 disabled:cursor-not-allowed"
                title="Send"
                aria-label="Send"
              >➤</button>
            </div>
          </div>
          <div className="mt-2 flex items-center justify-between">
            {/* Features dropdown under the input */}
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-500">Feature</label>
              <select
                className="rounded-lg border border-slate-200 px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={feature}
                onChange={(e) => setFeature(e.target.value)}
              >
                <option value="none">None</option>
                <option value="deep_research">Deep Research</option>
                <option value="reasoning">Reasoning</option>
                <option value="eda">EDA</option>
              </select>
            </div>
            {/* Attachment preview text */}
            <div className="text-xs text-slate-400 truncate max-w-[60%]">
              {attachments.length>0 ? attachments.map(a=>a.name).join(', ') : 'You can attach .pdf, .docx, images'}
            </div>
          </div>
          <input ref={fileRef} type="file" className="hidden" onChange={(e)=>onSelectFiles(e.target.files)} multiple />
        </div>
      </div>
    </div>
  );
}
