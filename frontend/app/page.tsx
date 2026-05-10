"use client";

import { useRef, useState } from "react";

type StreamEvent = { type: string; [key: string]: any };
type GeneratedFile = { nodeId: string; filename: string; content: string; status: "pending" | "generating" | "verifying" | "passed" | "failed" | "retrying" };
type TraceItem = { id: string; text: string; type: string; ts: number };

const STATUS_ICON: Record<string, string> = { pending: "◻️", generating: "⏳", verifying: "🔍", passed: "✅", failed: "❌", retrying: "🔄" };

export default function HomePage() {
  const [prompt, setPrompt] = useState("Build a modern SaaS dashboard");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [files, setFiles] = useState<GeneratedFile[]>([]);
  const [activeFileIdx, setActiveFileIdx] = useState(0);
  const [trace, setTrace] = useState<TraceItem[]>([]);
  const [activeTab, setActiveTab] = useState<"code" | "trace">("code");
  const [finalStatus, setFinalStatus] = useState<string | null>(null);
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
        setStatusMsg(evt.message);
        break;

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
    <div className="h-screen w-screen flex flex-col overflow-hidden" style={{ background: "linear-gradient(145deg, #0a0a0f 0%, #0d1117 50%, #0a0f1a 100%)" }}>
      {/* ─── Top Bar ─── */}
      <header className="shrink-0 h-12 px-4 flex items-center justify-between border-b border-white/[0.06] bg-black/30 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="text-sm font-bold tracking-tight text-white">CogniRoute</div>
          <div className="text-[10px] px-2 py-0.5 rounded-full border border-cyan-500/20 bg-cyan-500/5 text-cyan-400">AI Orchestrator</div>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          {totalCount > 0 && <span>{passedCount}/{totalCount} files</span>}
          {finalStatus && (
            <span className={"px-2 py-0.5 rounded-full border text-[10px] font-medium " + (finalStatus === "PASS" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" : "border-red-500/30 bg-red-500/10 text-red-400")}>
              {finalStatus === "PASS" ? "✅ PASS" : "⚠️ ISSUES"}
            </span>
          )}
        </div>
      </header>

      {/* ─── Main ─── */}
      <div className="flex-1 min-h-0 flex">
        {/* ─── Left: Prompt + Trace ─── */}
        <div className="w-[340px] shrink-0 border-r border-white/[0.06] flex flex-col bg-black/20">
          {/* Prompt */}
          <div className="shrink-0 p-3 border-b border-white/[0.06]">
            <textarea
              className="w-full h-[72px] resize-none rounded-lg bg-white/[0.03] border border-white/[0.08] px-3 py-2 text-[13px] text-slate-200 outline-none focus:border-cyan-500/30 placeholder:text-slate-600 transition-colors"
              placeholder="Describe what to build..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
            <button
              onClick={onRun}
              disabled={loading}
              className="mt-2 w-full rounded-lg px-4 py-2 text-[13px] font-semibold border transition-all duration-200 disabled:opacity-40 border-cyan-500/25 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 hover:from-cyan-500/20 hover:to-blue-500/20 text-cyan-300"
            >
              {loading ? "⏳ Running..." : "▶ Run Orchestration"}
            </button>
            {error && <div className="mt-2 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-[11px] text-red-300">{error}</div>}
          </div>

          {/* Status */}
          {statusMsg && (
            <div className="shrink-0 px-3 py-2 border-b border-white/[0.06] bg-cyan-500/[0.03]">
              <div className="text-[11px] text-cyan-400 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                {statusMsg}
              </div>
            </div>
          )}

          {/* Live Trace */}
          <div ref={traceRef} className="flex-1 min-h-0 overflow-y-auto p-3 space-y-1">
            {trace.length === 0 && (
              <div className="text-[12px] text-slate-600 mt-4 text-center">Run orchestration to see live trace</div>
            )}
            {trace.map((t) => (
              <div key={t.id} className={"text-[11px] leading-relaxed px-2.5 py-1.5 rounded-md border " +
                (t.type === "pass" ? "border-emerald-500/15 bg-emerald-500/[0.04] text-emerald-400" :
                 t.type === "fail" || t.type === "retry" ? "border-red-500/15 bg-red-500/[0.04] text-red-400" :
                 t.type === "plan" ? "border-cyan-500/15 bg-cyan-500/[0.04] text-cyan-400" :
                 t.type === "worker" ? "border-amber-500/15 bg-amber-500/[0.04] text-amber-400" :
                 "border-white/[0.06] bg-white/[0.02] text-slate-400")}>
                {t.text}
              </div>
            ))}
          </div>
        </div>

        {/* ─── Right: Code Viewer ─── */}
        <div className="flex-1 min-h-0 flex flex-col">
          {/* File Tabs */}
          {files.length > 0 && (
            <div className="shrink-0 flex items-center border-b border-white/[0.06] overflow-x-auto bg-black/20">
              {files.map((f, i) => (
                <button
                  key={f.nodeId}
                  onClick={() => setActiveFileIdx(i)}
                  className={"shrink-0 px-3.5 py-2.5 text-[11px] font-mono border-b-2 transition-all whitespace-nowrap flex items-center gap-1.5 " +
                    (i === activeFileIdx
                      ? "border-cyan-400 text-cyan-300 bg-white/[0.03]"
                      : "border-transparent text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]")}
                >
                  <span className="text-[10px]">{STATUS_ICON[f.status]}</span>
                  {f.filename || f.nodeId}
                </button>
              ))}
              {/* Code/Trace toggle for mobile-like feel */}
              <div className="ml-auto pr-2 flex items-center gap-1">
                <button onClick={() => setActiveTab("code")} className={"text-[10px] px-2 py-1 rounded border " + (activeTab === "code" ? "border-cyan-500/20 bg-cyan-500/10 text-cyan-300" : "border-white/[0.06] text-slate-500")}>Code</button>
                <button onClick={() => setActiveTab("trace")} className={"text-[10px] px-2 py-1 rounded border " + (activeTab === "trace" ? "border-cyan-500/20 bg-cyan-500/10 text-cyan-300" : "border-white/[0.06] text-slate-500")}>Trace</button>
              </div>
            </div>
          )}

          {/* Code Content */}
          <div className="flex-1 min-h-0 overflow-hidden">
            {activeTab === "code" ? (
              activeFile ? (
                <pre ref={codeRef} className="h-full overflow-y-auto p-4 text-[12px] leading-[1.6] font-mono text-slate-300 whitespace-pre-wrap break-words selection:bg-cyan-500/20">
                  {activeFile.content || (
                    <span className="text-slate-600 italic">
                      {activeFile.status === "generating" ? "⏳ Worker is generating code..." :
                       activeFile.status === "pending" ? "Waiting in queue..." : "..."}
                    </span>
                  )}
                </pre>
              ) : (
                <div className="h-full flex items-center justify-center">
                  <div className="text-center">
                    <div className="text-2xl mb-3">🧠</div>
                    <div className="text-sm text-slate-500">Enter a prompt and run orchestration</div>
                    <div className="text-[11px] text-slate-600 mt-1">Architect → Workers → Verifier</div>
                  </div>
                </div>
              )
            ) : (
              <div className="h-full overflow-y-auto p-4 space-y-1.5">
                {trace.map((t) => (
                  <div key={t.id} className="text-[11px] text-slate-400">
                    <span className="text-slate-600 font-mono mr-2">{new Date(t.ts).toLocaleTimeString()}</span>
                    {t.text}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
