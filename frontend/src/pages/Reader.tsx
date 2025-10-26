// frontend/src/pages/Reader.tsx
import { useState, type DragEvent, type ChangeEvent } from "react";
import { extractStyle } from "../lib/api";

export default function Reader() {
  const [exampleText, setExampleText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [styleName, setStyleName] = useState("");
  const [result, setResult] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files || []).filter((f) => {
      const n = f.name.toLowerCase();
      return n.endsWith(".pdf") || n.endsWith(".docx") || n.endsWith(".pptx");
    });
    if (dropped.length) setFiles((prev) => [...prev, ...dropped]);
  };

  const onBrowse = (e: ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files || []);
    if (picked.length) setFiles((prev) => [...prev, ...picked]);
  };

  const removeFile = (name: string) =>
    setFiles((prev) => prev.filter((f) => f.name !== name));

  const go = async () => {
    setLoading(true);
    setResult("");
    try {
      const fd = new FormData();
      fd.append("exampleText", exampleText);
      files.forEach((f) => fd.append("files", f));
      const r = await extractStyle(fd);
      setResult(r.style);
    } finally {
      setLoading(false);
    }
  };

  const disabledExtract = loading || (!exampleText && files.length === 0);

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Title */}
      <div className="flex items-center gap-3">
        <span className="text-2xl">🔎</span>
        <h1 className="text-2xl font-semibold">Style Reader</h1>
      </div>

      {/* Single 12-col grid:
          1) Input (col-span-8)
          2) Upload (col-span-4)
          3) Style Name + Button (col-span-8, sits beneath input)
      */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Input Content */}
        <div className="lg:col-span-8 bg-white rounded-xl shadow-sm ring-1 ring-slate-200 p-5">
          <label className="block text-sm font-medium text-slate-600 mb-2">
            Input Content
          </label>
          <textarea
            className="w-full h-64 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 p-3 resize-vertical"
            placeholder="Paste example writing here…"
            value={exampleText}
            onChange={(e) => setExampleText(e.target.value)}
          />
        </div>

        {/* Upload Files */}
        <div className="lg:col-span-4 bg-white rounded-xl shadow-sm ring-1 ring-slate-200 p-5">
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-medium text-slate-600">
              Upload Files
            </label>
            <span className="text-xs text-slate-400">PDF, DOCX, PPTX</span>
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
                accept=".pdf,.docx,.pptx"
                className="hidden"
                onChange={onBrowse}
              />
              <span className="px-3 py-2 rounded-md bg-white border border-slate-200 text-sm cursor-pointer hover:bg-slate-50">
                Browse files
              </span>
            </label>
          </div>

          {/* File chips */}
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
        </div>

        {/* Style Name + Button (below input) */}
        <div className="lg:col-span-8 bg-white rounded-xl shadow-sm ring-1 ring-slate-200 p-5">
          <label className="block text-sm font-medium text-slate-600 mb-2">
            Style Name
          </label>
          <input
            className="w-full rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 p-3"
            placeholder="e.g., House Style A"
            value={styleName}
            onChange={(e) => setStyleName(e.target.value)}
          />
          <p className="mt-1 text-xs text-slate-400">
            (Optional for now — we’ll use this when saving styles.)
          </p>

          <button
            onClick={go}
            disabled={disabledExtract}
            className="mt-4 w-full h-[44px] rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Extracting…" : "Extract Writing Style"}
          </button>
        </div>
      </div>

      {/* Result */}
      {result && (
        <div className="bg-white rounded-xl shadow-sm ring-1 ring-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-2">
            Extracted Style
          </h2>
          <pre className="whitespace-pre-wrap text-sm text-slate-800">
            {result}
          </pre>
        </div>
      )}
    </div>
  );
}
