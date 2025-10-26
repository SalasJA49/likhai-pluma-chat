import { useEffect, useState } from "react";
import { fetchStyles, deleteStyle } from "../lib/api";

export default function Settings(){
  const [styles, setStyles] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = async ()=>{
    setLoading(true);
    try{ setStyles(await fetchStyles()); }catch(e){ console.error('fetchStyles', e); }
    setLoading(false);
  };

  useEffect(()=>{ void load(); },[]);

  const handleDelete = async (id:string, name?:string)=>{
    if(!confirm(`Delete style '${name || id}'? This cannot be undone.`)) return;
    setDeleting(id);
    try{
      await deleteStyle(id);
      await load();
      try{ window.dispatchEvent(new CustomEvent('styles:changed')); }catch(e){}
    }catch(e:any){ console.error(e); alert('Delete failed'); }
    setDeleting(null);
  };

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <div className="flex items-center gap-3">
        <div className="text-2xl">⚙️</div>
        <h1 className="text-2xl font-semibold">Settings</h1>
      </div>

      <div className="bg-white rounded-xl shadow-sm ring-1 ring-slate-200 p-5">
        <h2 className="text-sm font-semibold mb-3">Saved Styles</h2>
        {loading ? <div>Loading…</div> : (
          <ul className="space-y-2">
            {styles.map(s=> (
              <li key={s.id} className="flex items-center justify-between border p-3 rounded">
                <div>
                  <div className="font-medium">{s.name}</div>
                  <div className="text-xs text-slate-500 truncate max-w-lg">{(s.style||"").slice(0,300)}</div>
                </div>
                <div>
                  <button onClick={()=>handleDelete(s.id, s.name)} disabled={deleting===s.id} className="px-3 py-1 rounded bg-red-600 text-white text-sm">{deleting===s.id? 'Deleting...' : 'Delete'}</button>
                </div>
              </li>
            ))}
            {!styles.length && <li className="text-sm text-slate-500">No styles found.</li>}
          </ul>
        )}
      </div>
    </div>
  );
}
