import { NavLink, useNavigate } from "react-router-dom";
import clsx from "clsx";
import { useEffect, useState } from "react";
import { listThreads, startThread } from "../lib/api";

const LinkItem = ({to, children}:{to:string; children:React.ReactNode}) => (
  <NavLink
    to={to}
    className={({isActive})=>clsx(
      "block px-3 py-2 text-sm rounded-xl hover:bg-slate-100 transition",
      isActive ? "bg-slate-100 font-semibold text-slate-900" : "text-slate-700"
    )}
  >
    {children}
  </NavLink>
);

export default function Layout({children}:{children:React.ReactNode}){
  const [openWriter, setOpenWriter] = useState(true);
  const [threads, setThreads] = useState<Array<any>>([]);
  const navigate = useNavigate();

  useEffect(()=>{
    (async ()=>{
      try{
        const t = await listThreads();
        setThreads(t);
      }catch(e){
        // ignore
      }
    })();
    const onChanged = async ()=>{
      try{ setThreads(await listThreads()); }catch(e){}
    };
    window.addEventListener('threads:changed', onChanged as EventListener);
    return ()=> window.removeEventListener('threads:changed', onChanged as EventListener);
  },[]);

  const onNewChat = async ()=>{
    const r = await startThread("New conversation");
    const id = r.thread_id;
    // refresh threads and navigate
    try{ setThreads(await listThreads()); }catch(e){}
    navigate(`/chat?thread_id=${id}`);
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b bg-white/80 backdrop-blur">
        <div className="mx-auto max-w-7xl h-14 flex items-center px-4">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-emerald-100 flex items-center justify-center">
              <span className="text-emerald-600 text-lg">📈</span>
            </div>
            <div className="text-lg font-semibold">Financial Markets</div>
          </div>
          <div className="ml-auto text-sm text-slate-500">BSP AI Assistant</div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-4">
        <div className="grid grid-cols-12 gap-6 py-6">
          {/* Sidebar */}
          <aside className="col-span-12 md:col-span-3 lg:col-span-3">
            <div className="rounded-2xl border border-slate-100 bg-white p-3 shadow-sm">
              <div className="flex items-center justify-between">
                <NavLink to="/chat" className="text-sm font-semibold text-slate-700">💬 Chatbot</NavLink>
                <button onClick={onNewChat} className="px-3 py-1 rounded-md bg-blue-600 text-white text-sm">New</button>
              </div>

              {/* Threads list */}
              <div className="mt-3 max-h-72 overflow-y-auto space-y-2">
                {threads.map((t)=> (
                  <NavLink
                    key={t.thread_id}
                    to={`/chat?thread_id=${t.thread_id}`}
                    className={({isActive})=>clsx("block px-3 py-2 text-sm rounded-xl hover:bg-slate-100 transition truncate", isActive?"bg-slate-100 font-semibold":"text-slate-700")}
                  >
                    <div className="truncate">{t.title || `Chat ${t.thread_id}`}</div>
                    <div className="text-xs text-slate-400 truncate">{t.last_message || ""}</div>
                  </NavLink>
                ))}
              </div>

              <button
                onClick={()=>setOpenWriter(v=>!v)}
                className="w-full text-left mt-2 mb-1 px-3 py-2 text-sm rounded-xl bg-slate-50 hover:bg-slate-100"
              >
                ✍️ Writer
              </button>
              {openWriter && (
                <div className="ml-2 space-y-1">
                  <LinkItem to="/writer">Style Writer</LinkItem>
                  <LinkItem to="/reader">Style Reader</LinkItem>
                  <LinkItem to="/outputs">Generated Outputs</LinkItem>
                </div>
              )}

              <div className="mt-2">
                <LinkItem to="/research">📊 Market Report</LinkItem>
              </div>
            </div>
          </aside>

          {/* Main content */}
          <main className="col-span-12 md:col-span-9 lg:col-span-9">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
