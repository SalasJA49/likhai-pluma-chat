import { useEffect, useState } from "react";
import { listOutputs } from "../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";

export default function Outputs(){
  const [rows,setRows]=useState<any[]>([]);
  useEffect(()=>{ listOutputs().then(setRows); },[]);
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="text-2xl">📰</div>
        <h1 className="text-2xl font-semibold">Generated Outputs</h1>
      </div>

      <Card>
        <CardHeader><CardTitle>Latest</CardTitle></CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {rows.map(r=>(
              <li key={r.id} className="rounded-xl border border-slate-200 bg-white/80 p-3">
                <div className="font-medium">{r.style_name}</div>
                <div className="text-sm text-slate-600">{r.preview}</div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
