import { useState } from "react";
import { streamResearch } from "../lib/api";

type Ev = { time: number; type: string; payload: any };

export default function Research(){
  const [topic, setTopic] = useState("");
  const [events, setEvents] = useState<Ev[]>([]);
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState(false);

  const run = () => {
    if (!topic.trim() || busy) return;
    setEvents([]); setSummary("");
    setBusy(true);
    const sse = streamResearch(topic);
    sse.on(
      (ev) => {
        if (ev.type === "done") {
          const data = JSON.parse(ev.data || "{}");
          setSummary(data.summary || "");
          setBusy(false);
          sse.close();
          return;
        }
        if (ev.type !== "keepalive" && ev.type !== "ready") {
          setEvents((arr)=>[...arr, { time: Date.now(), type: ev.type, payload: safeJSON(ev.data) }]);
        }
      },
      () => setBusy(false)
    );
  };

  return (
    <div className="max-w-5xl">
      <h1 className="text-2xl font-semibold mb-4">📈 Market Research</h1>
      <div className="flex gap-2 mb-3">
        <input className="flex-1 border rounded-md p-2" placeholder="Topic…" value={topic} onChange={e=>setTopic(e.target.value)}/>
        <button className="px-4 rounded-md bg-blue-600 text-white disabled:bg-blue-300" onClick={run} disabled={busy || !topic.trim()}>
          {busy ? "Running…" : "Run"}
        </button>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="border rounded-lg bg-white p-3 h-[60vh] overflow-auto">
          <h2 className="font-medium mb-2">Events</h2>
          <ul className="space-y-2 text-sm">
            {events.map((e,i)=>(
              <li key={i} className="border rounded p-2">
                <div className="text-gray-500">{e.type}</div>
                <pre className="whitespace-pre-wrap">{JSON.stringify(e.payload, null, 2)}</pre>
              </li>
            ))}
          </ul>
        </div>
        <div className="border rounded-lg bg-white p-3 h-[60vh] overflow-auto">
          <h2 className="font-medium mb-2">Summary</h2>
          <div className="prose prose-sm max-w-none">
            <pre className="whitespace-pre-wrap">{summary}</pre>
          </div>
        </div>
      </div>
    </div>
  );
}

function safeJSON(s?: string) {
  try { return JSON.parse(s || "{}"); } catch { return s; }
}
