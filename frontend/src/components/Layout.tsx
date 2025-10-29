import { NavLink, useNavigate, Link, useLocation } from "react-router-dom";
import clsx from "clsx";
import { useEffect, useState } from "react";
import { listThreads, startThread, renameThread } from "../lib/api";

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
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const currentThreadId = Number(params.get("thread_id")) || null;
  const [openWriter, setOpenWriter] = useState(true);
  const [openChat, setOpenChat] = useState(true);
  const [threads, setThreads] = useState<Array<any>>([]);
  const [loadingThread, setLoadingThread] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingText, setEditingText] = useState<string>("");
  const [showConfirm, setShowConfirm] = useState(false);
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
    const onThreadLoaded = () => {
      try{
        // when chat signals it's done loading, clear the loading overlay
        setLoadingThread(null);
      }catch(e){}
    };
    window.addEventListener('thread:loading:done', onThreadLoaded as EventListener);
    return ()=>{
      window.removeEventListener('threads:changed', onChanged as EventListener);
      window.removeEventListener('thread:loading:done', onThreadLoaded as EventListener);
    };
  },[]);

  const onNewChat = async ()=>{
    // This function is triggered after the user confirms in the modal
    try{
      const r = await startThread("New conversation");
      const id = r.thread_id;
      // refresh threads and navigate
      try{ setThreads(await listThreads()); }catch(e){}
      // notify other UI pieces (e.g., Chat page) that threads changed
      try{ window.dispatchEvent(new CustomEvent('threads:changed')); }catch(e){}
      navigate(`/chat?thread_id=${id}`);
    }catch(e){
      // ignore errors for now (could show a toast)
    }
  };

  const handleConfirmNew = async () => {
    setShowConfirm(false);
    await onNewChat();
  };

  const handleCancelNew = () => {
    setShowConfirm(false);
  };

  const startEdit = (t:any)=>{
    setEditingId(t.thread_id);
    setEditingText(t.title || "");
  };

  const saveEdit = async (id:number)=>{
    try{
      await renameThread(id, editingText);
      setThreads(await listThreads());
    }catch(e){}
    setEditingId(null);
    setEditingText("");
  };

  const cancelEdit = ()=>{ setEditingId(null); setEditingText(""); };

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
                <div className="flex items-center gap-3">
                  <NavLink to="/chat" className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                    <span className="text-sm">💬</span>
                    <span>Chatbot</span>
                  </NavLink>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={()=> setShowConfirm(true)}
                    className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400"
                  >
                    New
                  </button>

                  <button
                    onClick={() => setOpenChat((v) => !v)}
                    aria-expanded={openChat}
                    className="p-2 rounded hover:bg-slate-100"
                    title={openChat ? "Collapse Chatbot" : "Expand Chatbot"}
                  >
                    {/* Chevron: down when open, right when closed */}
                    <svg className={"h-4 w-4 transform transition-transform " + (openChat ? "rotate-0" : "-rotate-90")} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Threads list (collapsible) */}
              {openChat && (
                <div className="mt-3 max-h-72 overflow-y-auto space-y-2">
                  {threads.map((t)=> (
                    <div key={t.thread_id} className="relative">
                      {editingId === t.thread_id ? (
                        <div className="flex gap-2 items-center">
                          <input
                            autoFocus
                            value={editingText}
                            onChange={(e)=>setEditingText(e.target.value)}
                            onKeyDown={(e)=>{ if(e.key === 'Enter'){ saveEdit(t.thread_id); } if(e.key === 'Escape'){ cancelEdit(); } }}
                            className="w-full px-3 py-2 rounded-lg border"
                          />
                          <button onClick={()=>saveEdit(t.thread_id)} className="px-2 py-1 rounded bg-blue-600 text-white">Save</button>
                          <button onClick={cancelEdit} className="px-2 py-1 rounded bg-slate-200">Cancel</button>
                        </div>
                      ) : (
                        <Link
                          to={`/chat?thread_id=${t.thread_id}`}
                          onClick={() => setLoadingThread(t.thread_id)}
                          className={clsx(
                            "block px-3 py-2 text-sm rounded-xl transition truncate cursor-pointer",
                            currentThreadId === t.thread_id ? "bg-slate-100 font-semibold text-slate-900" : "text-slate-700 hover:bg-slate-100"
                          )}
                        >
                          <div className="flex justify-between items-center">
                            <div className="truncate">{t.title || `Chat ${t.thread_id}`}</div>
                            <button type="button" onClick={(e)=>{ e.preventDefault(); e.stopPropagation(); startEdit(t); }} className="ml-2 text-xs text-slate-400 hover:text-slate-600">Edit</button>
                          </div>
                          <div className="text-xs text-slate-400 truncate">{t.last_message || ""}</div>
                        </Link>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Loading overlay when a thread is being loaded */}
              {loadingThread && (
                <div className="fixed inset-0 z-50 pointer-events-none flex items-start md:items-center justify-center">
                  <div className="mt-20 md:mt-0 bg-black/30 w-full h-full" />
                  <div className="absolute top-1/3 md:top-1/2 transform -translate-y-1/2">
                    <div className="inline-flex items-center gap-3 bg-white/90 px-4 py-3 rounded-lg shadow-lg">
                      <div className="w-5 h-5 border-2 border-t-blue-600 border-slate-200 rounded-full animate-spin" />
                      <div className="text-sm text-slate-800">Loading conversation…</div>
                    </div>
                  </div>
                </div>
              )}

              <button
                onClick={()=>setOpenWriter(v=>!v)}
                className="w-full text-left mt-2 mb-1 px-3 py-2 text-sm rounded-xl bg-slate-50 hover:bg-slate-100 flex items-center justify-between"
                aria-expanded={openWriter}
                title={openWriter ? "Collapse Writer" : "Expand Writer"}
              >
                <div className="flex items-center gap-3">
                  <span>✍️</span>
                  <span className="font-medium">Writer</span>
                </div>
                <svg className={"h-4 w-4 transform transition-transform " + (openWriter ? "rotate-0" : "-rotate-90")} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {openWriter && (
                <div className="ml-2 space-y-1">
                  <LinkItem to="/writer">Style Writer</LinkItem>
                  <LinkItem to="/reader">Style Reader</LinkItem>
                  <LinkItem to="/outputs">Generated Outputs</LinkItem>
                  <LinkItem to="/settings">Settings</LinkItem>
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
      {/* Confirmation modal for creating a new thread */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black opacity-30" onClick={handleCancelNew} />
          <div className="relative bg-white rounded-lg shadow-xl p-6 w-full max-w-md m-4">
            <h3 className="text-lg font-semibold mb-2">Create new conversation</h3>
            <p className="text-sm text-slate-600 mb-4">Are you sure you want to create a new thread?</p>
            <div className="flex justify-end gap-3">
              <button onClick={handleCancelNew} className="px-3 py-2 rounded bg-slate-100">Cancel</button>
              <button onClick={handleConfirmNew} className="px-3 py-2 rounded bg-blue-600 text-white">Yes, create</button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
