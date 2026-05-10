"use client";

import { useRef, useState, useEffect } from "react";

type StreamEvent = { type: string; [key: string]: any };
type GeneratedFile = { nodeId: string; filename: string; content: string; status: "pending" | "generating" | "verifying" | "passed" | "failed" | "retrying" };
type TraceItem = { id: string; text: string; type: string; ts: number };

const Icons = {
  Play: () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>,
  Brain: () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/></svg>,
  FileCode: () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><path d="m10 13-2 2 2 2"/><path d="m14 17 2-2-2-2"/></svg>,
  Activity: () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
  CheckCircle: () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>,
  XCircle: () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>,
  Loader: () => <svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></svg>,
  Refresh: () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>,
};

const STATUS_ICON: Record<string, JSX.Element> = { 
  pending: <span className="text-slate-500 opacity-50">○</span>, 
  generating: <span className="text-amber-400"><Icons.Loader /></span>, 
  verifying: <span className="text-blue-400"><Icons.Activity /></span>, 
  passed: <span className="text-emerald-400"><Icons.CheckCircle /></span>, 
  failed: <span className="text-red-400"><Icons.XCircle /></span>, 
  retrying: <span className="text-amber-500"><Icons.Refresh /></span> 
};

// Basic syntax highlighting helper
const escapeHtml = (unsafe: string) => unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
const highlightCode = (code: string) => {
  let highlighted = escapeHtml(code);
  highlighted = highlighted.replace(/\b(import|export|from|const|let|var|function|return|if|else|for|while|switch|case|break|continue|default|class|extends|implements|new|this|super|throw|try|catch|finally|typeof|instanceof|async|await)\b/g, '<span class="text-violet-400 font-medium">$1</span>');
  highlighted = highlighted.replace(/(['"`])(.*?)\1/g, '<span class="text-emerald-300">$1$2$1</span>'); // strings
  highlighted = highlighted.replace(/\b(\d+)\b/g, '<span class="text-amber-300">$1</span>'); // numbers
  highlighted = highlighted.replace(/(\/\/.*)/g, '<span class="text-slate-500 italic">$1</span>'); // comments
  return highlighted;
};

export default function HomePage() {
  const [prompt, setPrompt] = useState("Build a modern SaaS dashboard with authentication and charts");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [files, setFiles] = useState<GeneratedFile[]>([]);
  const [activeFileIdx, setActiveFileIdx] = useState(0);
  const [trace, setTrace] = useState<TraceItem[]>([]);
  const [activeTab, setActiveTab] = useState<"code" | "reasoning" | "trace">("code");
  const [finalStatus, setFinalStatus] = useState<string | null>(null);
  const [reasoning, setReasoning] = useState<string | null>(null);
  const traceRef = useRef<HTMLDivElement>(null);
  const codeRef = useRef<HTMLPreElement>(null);

  function addTrace(text: string, type: string) {
    const item = { id: crypto.randomUUID(), text, type, ts: Date.now() };
    setTrace((t) => [...t, item]);
    setTimeout(() => traceRef.current?.scrollTo({ top: traceRef.current.scrollHeight, behavior: "smooth" }), 50);
  }

  async function onRun() {
    setLoading(true);
    setError(null);
    setFiles([]);
    setActiveFileIdx(0);
    setTrace([]);
    setFinalStatus(null);
    setReasoning(null);
    setActiveTab("code");
    setStatusMsg("Connecting to orchestrator...");

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
      const res = await fetch(`${backendUrl}/generate/stream`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      if (!res.ok) throw new Error(`Backend error: ${res.status}`);

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ")) continue;
          try { handleEvent(JSON.parse(line.slice(6))); } catch {}
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
      setStatusMsg(null);
    }
  }

  function handleEvent(evt: StreamEvent) {
    switch (evt.type) {
      case "status":
        setStatusMsg(evt.message);
        addTrace(evt.message, "status");
        break;

      case "plan":
        setStatusMsg(`Architect planned ${evt.files.length} files`);
        addTrace(`📋 Planned ${evt.files.length} files: ${evt.files.map((f: any) => f.filename).join(", ")}`, "plan");
        setFiles(evt.files.map((f: any) => ({ nodeId: f.node_id, filename: f.filename, content: "", status: "pending" as const })));
        break;

      case "reasoning":
        setReasoning(evt.content);
        setStatusMsg("Architect reasoning complete — planning files...");
        addTrace("🧠 Architecture reasoning generated", "plan");
        setActiveTab("reasoning");
        break;

      case "file_start":
        setStatusMsg(`Generating ${evt.filename}...`);
        addTrace(`🔧 Worker started: ${evt.filename}`, "worker");
        setFiles((prev) => {
          const updated = prev.map((f) => f.nodeId === evt.node_id ? { ...f, status: "generating" as const } : f);
          const idx = updated.findIndex((f) => f.nodeId === evt.node_id);
          if (idx >= 0) setActiveFileIdx(idx);
          return updated;
        });
        break;

      case "file_generated":
        setFiles((prev) => {
          const updated = prev.map((f) => f.nodeId === evt.node_id ? { ...f, filename: evt.filename, content: evt.content, status: "verifying" as const } : f);
          const idx = updated.findIndex((f) => f.nodeId === evt.node_id);
          if (idx >= 0) setActiveFileIdx(idx);
          return updated;
        });
        setStatusMsg(`Verifying ${evt.filename}...`);
        addTrace(`📄 Generated: ${evt.filename} (${evt.content.length} chars)`, "worker");
        setTimeout(() => codeRef.current?.scrollTo({ top: 0 }), 50);
        break;

      case "file_verified":
        setFiles((prev) => prev.map((f) => f.nodeId === evt.node_id ? { ...f, status: evt.status === "PASS" ? "passed" : "failed" } : f));
        if (evt.status === "PASS") {
          addTrace(`✅ Verified: ${evt.filename}`, "pass");
        } else {
          addTrace(`❌ Failed: ${evt.filename} — ${evt.issues?.join("; ")}`, "fail");
        }
        break;

      case "file_retry":
        setFiles((prev) => prev.map((f) => f.nodeId === evt.node_id ? { ...f, status: "retrying" } : f));
        setStatusMsg(`Retrying (attempt ${evt.attempt})...`);
        addTrace(`🔄 Retry #${evt.attempt}: ${evt.issues?.join("; ")}`, "retry");
        break;

      case "worker_start":
      case "verify_start":
        setStatusMsg(evt.message);
        break;

      case "complete":
        const status = evt.run?.verifier_report?.status ?? "N/A";
        setFinalStatus(status);
        addTrace(`🏁 Complete — Final: ${status}`, status === "PASS" ? "pass" : "fail");
        break;

      case "error":
        setError(evt.message);
        addTrace(`💥 Error: ${evt.message}`, "fail");
        break;
    }
  }

  const activeFile = files[activeFileIdx] ?? null;
  const passedCount = files.filter((f) => f.status === "passed").length;
  const totalCount = files.length;

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-transparent text-slate-200">
      
      {/* ─── Top Bar ─── */}
      <header className="shrink-0 h-14 px-6 flex items-center justify-between border-b border-white/[0.05] bg-black/40 backdrop-blur-xl z-10 shadow-lg shadow-black/20">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Icons.Brain />
            </div>
            <div className="text-base font-bold tracking-tight bg-gradient-to-r from-white to-white/70 bg-clip-text text-transparent">CogniRoute</div>
          </div>
          <div className="h-4 w-px bg-white/10" />
          <div className="text-[11px] font-medium px-2.5 py-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-300 flex items-center gap-1.5 shadow-[0_0_10px_rgba(6,182,212,0.15)]">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_5px_rgba(34,211,238,0.8)]" />
            AI Orchestrator Runtime
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs font-medium">
          {totalCount > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10">
              <Icons.FileCode />
              <span>{passedCount} / {totalCount} Files Ready</span>
              <div className="w-16 h-1.5 bg-black/50 rounded-full overflow-hidden ml-2">
                <div className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400 transition-all duration-500 ease-out" style={{ width: `${(passedCount / totalCount) * 100}%` }} />
              </div>
            </div>
          )}
          {finalStatus && (
            <span className={"flex items-center gap-1.5 px-3 py-1.5 rounded-full border shadow-lg " + (finalStatus === "PASS" ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400 shadow-emerald-500/10" : "border-red-500/40 bg-red-500/10 text-red-400 shadow-red-500/10")}>
              {finalStatus === "PASS" ? <><Icons.CheckCircle /> All Passed</> : <><Icons.XCircle /> Issues Found</>}
            </span>
          )}
        </div>
      </header>

      {/* ─── Main ─── */}
      <div className="flex-1 min-h-0 flex bg-black/20 backdrop-blur-3xl relative">
        {/* Glow Effects */}
        <div className="absolute top-1/4 -left-32 w-64 h-64 bg-cyan-500/20 rounded-full blur-[100px] pointer-events-none" />
        <div className="absolute bottom-1/4 -right-32 w-64 h-64 bg-purple-500/20 rounded-full blur-[100px] pointer-events-none" />

        {/* ─── Left Panel: Orchestration Controls & Trace ─── */}
        <div className="w-[380px] shrink-0 border-r border-white/[0.05] flex flex-col bg-white/[0.01] shadow-2xl relative z-10">
          
          {/* Prompt Area */}
          <div className="shrink-0 p-5 border-b border-white/[0.05]">
            <div className="mb-2 text-xs font-medium text-slate-400 flex items-center justify-between">
              <span>Objective</span>
              <span className="text-[10px] bg-white/10 px-2 py-0.5 rounded text-slate-300">Natural Language</span>
            </div>
            <textarea
              className="w-full h-[90px] resize-none rounded-xl bg-black/40 border border-white/10 px-4 py-3 text-sm text-slate-200 outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 placeholder:text-slate-600 transition-all shadow-inner"
              placeholder="Describe what the multi-agent system should build..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
            <button
              onClick={onRun}
              disabled={loading || !prompt.trim()}
              className="mt-4 w-full rounded-xl px-4 py-3 text-sm font-semibold transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed border border-cyan-500/30 bg-gradient-to-r from-cyan-600/20 to-purple-600/20 hover:from-cyan-500/30 hover:to-purple-500/30 text-cyan-50 hover:text-white shadow-lg shadow-cyan-900/20 flex items-center justify-center gap-2 group overflow-hidden relative"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:animate-[shimmer_1.5s_infinite]" />
              {loading ? <Icons.Loader /> : <Icons.Play />}
              {loading ? "Orchestration Running..." : "Execute Orchestration"}
            </button>
            {error && <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-200 flex items-start gap-2 shadow-lg shadow-red-900/20"><Icons.XCircle /> {error}</div>}
          </div>

          {/* Status Indicator */}
          {statusMsg && (
            <div className="shrink-0 px-5 py-3 border-b border-white/[0.05] bg-gradient-to-r from-cyan-500/[0.05] to-transparent relative overflow-hidden">
              <div className="absolute left-0 top-0 bottom-0 w-1 bg-cyan-500 shadow-[0_0_10px_rgba(6,182,212,0.8)]" />
              <div className="text-xs text-cyan-300 flex items-center gap-2.5 font-medium tracking-wide">
                <Icons.Activity />
                {statusMsg}
              </div>
            </div>
          )}

          {/* Live Trace Area */}
          <div className="flex-1 min-h-0 flex flex-col">
            <div className="px-5 py-3 text-xs font-semibold tracking-wider text-slate-500 uppercase flex items-center justify-between border-b border-white/[0.05] bg-black/20">
              <span>Event Stream</span>
              <span className="text-[10px] bg-white/5 px-2 py-0.5 rounded-full">{trace.length} events</span>
            </div>
            <div ref={traceRef} className="flex-1 overflow-y-auto p-3 space-y-2 pb-6">
              {trace.length === 0 && (
                <div className="h-full flex flex-col items-center justify-center opacity-40 text-sm gap-3">
                  <Icons.Activity />
                  Awaiting execution...
                </div>
              )}
              {trace.map((t) => (
                <div key={t.id} className={"text-xs leading-relaxed px-3 py-2.5 rounded-lg border transition-all hover:scale-[1.01] shadow-sm backdrop-blur-sm " +
                  (t.type === "pass" ? "border-emerald-500/20 bg-emerald-500/[0.05] text-emerald-300" :
                   t.type === "fail" || t.type === "retry" ? "border-red-500/20 bg-red-500/[0.05] text-red-300" :
                   t.type === "plan" ? "border-purple-500/20 bg-purple-500/[0.05] text-purple-300" :
                   t.type === "worker" ? "border-amber-500/20 bg-amber-500/[0.05] text-amber-300" :
                   "border-white/[0.08] bg-white/[0.03] text-slate-300")}>
                  <div className="flex items-start gap-2">
                    <span className="opacity-40 text-[10px] font-mono mt-0.5 whitespace-nowrap">{new Date(t.ts).toLocaleTimeString(undefined, {hour12:false, hour:'2-digit', minute:'2-digit', second:'2-digit'})}</span>
                    <span className="flex-1 break-words">{t.text}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ─── Right Panel: Code & Details Viewer ─── */}
        <div className="flex-1 min-h-0 flex flex-col z-10 bg-black/40 shadow-[-10px_0_30px_-10px_rgba(0,0,0,0.5)]">
          
          {/* File Tabs & Views */}
          <div className="shrink-0 flex items-center justify-between border-b border-white/[0.05] bg-black/50 pr-4">
            <div className="flex overflow-x-auto custom-scrollbar flex-1 min-w-0">
              {files.map((f, i) => (
                <button
                  key={f.nodeId}
                  onClick={() => { setActiveFileIdx(i); setActiveTab("code"); }}
                  className={"shrink-0 px-5 py-3.5 text-xs font-mono border-b-2 transition-all whitespace-nowrap flex items-center gap-2.5 " +
                    (i === activeFileIdx && activeTab === "code"
                      ? "border-cyan-400 text-cyan-200 bg-cyan-500/[0.05] shadow-[inset_0_-15px_15px_-15px_rgba(6,182,212,0.2)]"
                      : "border-transparent text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]")}
                >
                  {STATUS_ICON[f.status]}
                  {f.filename || f.nodeId}
                </button>
              ))}
              {files.length === 0 && (
                <div className="px-5 py-3.5 text-xs font-mono text-slate-600 border-b-2 border-transparent">No files planned yet</div>
              )}
            </div>

            {/* View Toggles */}
            <div className="shrink-0 flex items-center gap-1.5 pl-4 ml-4 border-l border-white/10">
              <button 
                onClick={() => setActiveTab("code")} 
                className={"text-xs px-3 py-1.5 rounded-lg border transition-all flex items-center gap-1.5 font-medium " + (activeTab === "code" ? "border-cyan-500/30 bg-cyan-500/15 text-cyan-200 shadow-[0_0_10px_rgba(6,182,212,0.1)]" : "border-white/5 bg-white/5 text-slate-400 hover:bg-white/10")}
              >
                <Icons.FileCode /> Code
              </button>
              <button 
                onClick={() => setActiveTab("reasoning")} 
                className={"text-xs px-3 py-1.5 rounded-lg border transition-all flex items-center gap-1.5 font-medium " + (activeTab === "reasoning" ? "border-purple-500/30 bg-purple-500/15 text-purple-200 shadow-[0_0_10px_rgba(168,85,247,0.1)]" : "border-white/5 bg-white/5 text-slate-400 hover:bg-white/10")}
              >
                <Icons.Brain /> Arch
              </button>
            </div>
          </div>

          {/* Viewer Content */}
          <div className="flex-1 min-h-0 overflow-hidden bg-[#0d1117] relative">
            {/* Soft inner shadow for depth */}
            <div className="absolute inset-0 shadow-[inset_0_0_40px_rgba(0,0,0,0.5)] pointer-events-none" />

            {activeTab === "code" ? (
              activeFile ? (
                <div className="h-full flex flex-col relative z-10">
                  <div className="px-5 py-2 border-b border-white/[0.05] flex justify-between items-center bg-black/40 backdrop-blur-md">
                    <span className="text-xs font-mono text-slate-400">{activeFile.filename}</span>
                    <span className="text-[10px] bg-white/10 px-2 py-0.5 rounded text-slate-400">{activeFile.content.length} bytes</span>
                  </div>
                  <pre ref={codeRef} className="flex-1 overflow-y-auto p-5 text-[13px] leading-[1.6] font-mono text-slate-300 whitespace-pre-wrap break-words selection:bg-cyan-500/30 custom-scrollbar">
                    {activeFile.content ? (
                      <div dangerouslySetInnerHTML={{ __html: highlightCode(activeFile.content) }} />
                    ) : (
                      <div className="h-full flex items-center justify-center text-slate-500 flex-col gap-3 opacity-60">
                        {activeFile.status === "generating" ? (
                          <><Icons.Loader /><span className="animate-pulse">Worker agent is drafting code...</span></>
                        ) : (
                          <><Icons.Activity /><span>Awaiting worker assignment...</span></>
                        )}
                      </div>
                    )}
                  </pre>
                </div>
              ) : (
                <div className="h-full flex items-center justify-center relative z-10">
                  <div className="text-center p-8 rounded-2xl bg-white/[0.02] border border-white/[0.05] shadow-2xl backdrop-blur-xl max-w-sm w-full relative overflow-hidden">
                    <div className="absolute -top-10 -right-10 w-32 h-32 bg-cyan-500/10 rounded-full blur-3xl" />
                    <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-purple-500/10 rounded-full blur-3xl" />
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-purple-600/20 border border-white/10 flex items-center justify-center mx-auto mb-6 shadow-lg">
                      <div className="text-white/80"><Icons.Brain /></div>
                    </div>
                    <div className="text-lg font-semibold text-white mb-2">Ready to Build</div>
                    <div className="text-sm text-slate-400 leading-relaxed">
                      Enter a prompt on the left and run the orchestrator. Watch as autonomous agents plan, write, and verify your codebase in real-time.
                    </div>
                  </div>
                </div>
              )
            ) : activeTab === "reasoning" ? (
              <div className="h-full overflow-y-auto p-8 relative z-10 custom-scrollbar">
                {reasoning ? (
                  <div className="max-w-4xl mx-auto">
                    <div className="inline-flex items-center gap-3 mb-6 px-4 py-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-300 shadow-lg shadow-purple-900/20">
                      <Icons.Brain />
                      <span className="text-sm font-bold tracking-wide">Architect Reasoning Process</span>
                    </div>
                    <div className="bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6 shadow-xl">
                      <pre className="text-sm leading-relaxed text-slate-300 whitespace-pre-wrap break-words font-sans selection:bg-purple-500/30">
                        {reasoning}
                      </pre>
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-slate-500 opacity-60">
                    <Icons.Brain />
                    <div className="mt-4 text-sm">Architect reasoning will appear here after analysis.</div>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
