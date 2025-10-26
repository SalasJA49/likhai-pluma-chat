// frontend/src/pages/Writer.tsx
import { useEffect, useState, type DragEvent, type ChangeEvent } from "react";
import { fetchStyles, rewrite } from "../lib/api";

export default function Writer() {
  const [content, setContent] = useState("");
  const [styles, setStyles] = useState<any[]>([]);
  const [sel, setSel] = useState<any | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);

  const [maxChars, setMaxChars] = useState<number>(800);
  const [out, setOut] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchStyles().then(setStyles);
    const onStylesChanged = async () => { try{ setStyles(await fetchStyles()); }catch(e){} };
    window.addEventListener('styles:changed', onStylesChanged as EventListener);
    return ()=> window.removeEventListener('styles:changed', onStylesChanged as EventListener);
  }, []);

  // --- Upload handlers (reads text-like files client-side) ---
  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files || []);
    if (dropped.length) {
      setFiles((prev) => [...prev, ...dropped]);
      void appendTextFilesToContent(dropped);
    }
  };

  const onBrowse = (e: ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files || []);
    if (picked.length) {
      setFiles((prev) => [...prev, ...picked]);
      void appendTextFilesToContent(picked);
    }
  };

  async function appendTextFilesToContent(fls: File[]) {
    const textLike = fls.filter((f) => {
      const n = f.name.toLowerCase();
      return (
        f.type.startsWith("text/") ||
        n.endsWith(".txt") ||
        n.endsWith(".md") ||
        n.endsWith(".csv") ||
        n.endsWith(".json")
      );
    });
    if (!textLike.length) return;

    const chunks: string[] = [];
    for (const f of textLike) {
      try {
        const t = await f.text();
        chunks.push(`\n\n[file:${f.name}]\n${t}`);
      } catch {
        // ignore read errors
      }
    }
    if (chunks.length) setContent((prev) => (prev ? prev + chunks.join("") : chunks.join("")));
  }

  const removeFile = (name: string) =>
    setFiles((prev) => prev.filter((f) => f.name !== name));

  // --- Call backend ---
  const go = async () => {
    if (!content.trim() || !sel) return;
    setLoading(true);
    setOut("");
    try {
      const guideline = `Limit the output to approximately ${maxChars} characters. If needed, be concise while preserving key points.`;
      const res = await rewrite({
        content,
        style: sel?.style || "",
        example: sel?.example || "",
        guidelines: guideline,
        styleId: sel?.name || "Style",
      });
      setOut(res.output);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Title */}
      <div className="flex items-center gap-3">
        <span className="text-2xl">📝</span>
        <h1 className="text-2xl font-semibold">Style Writer</h1>
      </div>

      {/* Row 1: Input (8) | Upload (4) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Input */}
        <div className="lg:col-span-8 bg-white rounded-xl shadow-sm ring-1 ring-slate-200 p-5">
          <label className="block text-sm font-medium text-slate-600 mb-2">
            Input Content
          </label>
          <textarea
            className="w-full h-64 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 p-3 resize-vertical"
            placeholder="Paste or type the text you want rewritten…"
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
        </div>

        {/* Upload */}
        <div className="lg:col-span-4 bg-white rounded-xl shadow-sm ring-1 ring-slate-200 p-5">
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-medium text-slate-600">
              Upload Files
            </label>
            <span className="text-xs text-slate-400">TXT, MD, CSV, JSON</span>
          </div>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            className={`mt-2 border-2 border-dashed rounded-lg p-6 text-center transition ${
              dragOver
                ? "border-blue-500 bg-blue-50"
                : "border-slate-200 bg-slate-50"
            }`}
          >
            <p className="text-sm text-slate-600 mb-1">Drag & drop files here</p>
            <p className="text-xs text-slate-400 mb-3">or</p>
            <label className="inline-block">
              <input
                type="file"
                multiple
                accept=".txt,.md,.csv,.json"
                className="hidden"
                onChange={onBrowse}
              />
              <span className="px-3 py-2 rounded-md bg-white border border-slate-200 text-sm cursor-pointer hover:bg-slate-50">
                Browse files
              </span>
            </label>
          </div>

          {!!files.length && (
            <ul className="mt-3 flex flex-wrap gap-2">
              {files.map((f) => (
                <li
                  key={f.name + f.size}
                  className="text-xs bg-slate-100 border border-slate-200 rounded-md px-2 py-1 flex items-center gap-2"
                >
                  <span className="truncate max-w-[180px]">{f.name}</span>
                  <button
                    onClick={() => removeFile(f.name)}
                    className="text-slate-500 hover:text-red-500"
                    title="Remove"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}

          <p className="mt-3 text-[11px] text-slate-400">
            Tip: Non-text files (PDF/DOCX/PPTX) aren’t parsed here. If you want
            server-side parsing, we can extend the `/rewrite/` endpoint similar
            to the Style Reader.
          </p>
        </div>

        {/* Row 2: Slider (under Input, spans 8) */}
        <div className="lg:col-span-8 bg-white rounded-xl shadow-sm ring-1 ring-slate-200 p-5">
          <label className="block text-sm font-medium text-slate-600 mb-2">
            Max Output Characters
          </label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={100}
              max={4000}
              step={50}
              value={maxChars}
              onChange={(e) => setMaxChars(parseInt(e.target.value, 10))}
              className="w-full"
            />
            <span className="w-20 text-right text-sm text-slate-700">
              {maxChars}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            The assistant will try to keep the rewritten output around this length.
          </p>
        </div>

        {/* Row 3: Style selector (under slider, spans 8) */}
        <div className="lg:col-span-8 bg-white rounded-xl shadow-sm ring-1 ring-slate-200 p-5">
          <label className="block text-sm font-medium text-slate-600 mb-2">
            Choose Style
          </label>
          <select
            className="w-full rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 p-3"
            value={sel?.name || ""}
            onChange={(e) =>
              setSel(styles.find((s) => s.name === e.target.value) || null)
            }
          >
            <option value="">Select a Style…</option>
            {styles.map((s) => (
              <option key={s.id} value={s.name}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        {/* Row 4: Button (full width under selector, spans 8) */}
        <div className="lg:col-span-8">
          <button
            onClick={go}
            disabled={loading || !sel || !content.trim()}
            className="w-full h-[46px] rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Rewriting…" : "Rewrite Content"}
          </button>
        </div>
      </div>

      {/* Output */}
      {out && (
        <div className="bg-white rounded-xl shadow-sm ring-1 ring-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-2">
            Rewritten Output
          </h2>
          <pre className="whitespace-pre-wrap text-sm text-slate-800">{out}</pre>
        </div>
      )}
    </div>
  );
}
