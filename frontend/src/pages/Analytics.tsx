import { useState } from "react";
import { edaProcess } from "../lib/api";
import PlotlyChart from "../components/PlotlyChart";
import DataTable from "../components/DataTable";
import StatsTable from "../components/StatsTable";

export default function Analytics() {
  const [file, setFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [charts, setCharts] = useState<any[]>([]);
  const [insights, setInsights] = useState<any | null>(null);
  const [tables, setTables] = useState<any | null>(null);
  const [sqlInfo, setSqlInfo] = useState<any | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setCharts([]);
    setInsights(null);
  setSqlInfo(null);
  setTables(null);
    try {
  let result: { charts: any; insights: any; sql_transformation?: any; tables?: any };
      if (file) {
        const fd = new FormData();
        fd.append("file", file);
        if (prompt) fd.append("prompt", prompt);
        result = await edaProcess(fd);
      } else {
        const payload: any = { };
        if (prompt) payload.prompt = prompt;
        result = await edaProcess(payload);
      }
  if (result.sql_transformation) setSqlInfo(result.sql_transformation);
      const list = result.charts?.charts || [];
      setCharts(list);
      setInsights(result.insights?.data || null);
  setTables(result.tables || null);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "Failed to process EDA request.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold mb-3">Exploratory Data Analysis</h2>
        <form onSubmit={onSubmit} className="space-y-3">
          <div className="grid md:grid-cols-3 gap-3">
            <div>
              <label className="block text-sm text-slate-600 mb-1">Dataset (CSV/XLSX)</label>
              <input type="file" accept=".csv,.xlsx,.xls" onChange={(e)=>setFile(e.target.files?.[0]||null)} className="w-full text-sm" />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm text-slate-600 mb-1">Prompt (optional)
                <span className="ml-2 text-xs text-slate-400">Try: "Show USD/PHP trend in 2024" or paste a SELECT query</span>
              </label>
              <input value={prompt} onChange={(e)=>setPrompt(e.target.value)} placeholder="Describe what to analyze or paste a SQL SELECT…" className="w-full px-3 py-2 rounded-lg border" />
            </div>
          </div>
          <div>
            <button type="submit" disabled={loading} className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60">
              {loading ? "Analyzing…" : "Analyze"}
            </button>
          </div>
        </form>
        {error && <div className="mt-3 text-sm text-red-600">{error}</div>}
      </div>

      {sqlInfo && (
        <div className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
          <h3 className="font-semibold mb-2">SQL Transformation</h3>
          <pre className="text-xs bg-slate-50 p-3 rounded border overflow-auto"><code>{sqlInfo.query}</code></pre>
          <div className="text-sm text-slate-600">{sqlInfo.summary}</div>
          <div className="text-xs text-slate-500 mt-1">Original: {sqlInfo.original_shape?.[0]}×{sqlInfo.original_shape?.[1]} → Result: {sqlInfo.result_shape?.[0]}×{sqlInfo.result_shape?.[1]}</div>
        </div>
      )}

      {charts?.length > 0 && (
        <div className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
          <h3 className="font-semibold mb-3">Charts ({charts.length})</h3>
          <div className="grid gap-6">
            {charts.map((c:any, idx:number)=> (
              <div key={idx} className="space-y-2">
                <div className="text-sm font-medium">{c.title || `Chart ${idx+1}`}</div>
                {c.reason && <div className="text-xs text-slate-500">{c.reason}</div>}
                <PlotlyChart figure={c.figure} title={c.title} />
              </div>
            ))}
          </div>
        </div>
      )}

      {tables?.top_n && (
        <div className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
          <h3 className="font-semibold mb-3">Table</h3>
          <DataTable title={tables.top_n.title} columns={tables.top_n.columns} rows={tables.top_n.rows} />
          {tables.top_n.note && <div className="text-xs text-slate-500 mt-2">{tables.top_n.note}</div>}
        </div>
      )}

      {(insights || tables?.statistics) && (
        <div className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
          <h3 className="font-semibold mb-2">Insights</h3>
          {insights?.key_findings && (
            <div className="mb-2 text-slate-700">{insights.key_findings}</div>
          )}
          {Array.isArray(insights?.insights) && insights.insights.length > 0 && (
            <div className="mt-2">
              <div className="font-medium">Detailed Analysis</div>
              <ul className="list-disc pl-5 text-sm text-slate-700 space-y-1">
                {insights.insights.map((it:string, i:number)=> <li key={i}>{it}</li>)}
              </ul>
            </div>
          )}
          {Array.isArray(insights?.recommendations) && insights.recommendations.length > 0 && (
            <div className="mt-3">
              <div className="font-medium">Recommendations</div>
              <ul className="list-disc pl-5 text-sm text-slate-700 space-y-1">
                {insights.recommendations.map((it:string, i:number)=> <li key={i}>{it}</li>)}
              </ul>
            </div>
          )}
          {tables?.statistics && (
            <div className="mt-6">
              <StatsTable statistics={tables.statistics} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
