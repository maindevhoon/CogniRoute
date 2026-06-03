"use client";

import { useRef, useState, useEffect } from "react";

/* ═══════════════════════════════════════
   Types
   ═══════════════════════════════════════ */
type StreamEvent = { type: string; [key: string]: any };
type GeneratedFile = {
  nodeId: string;
  filename: string;
  content: string;
  status: "pending" | "generating" | "verifying" | "passed" | "failed" | "retrying";
};
type TraceItem = { id: string; text: string; type: string; ts: number };

/* ═══════════════════════════════════════
   Icons — minimal, clean, 20×20 strokes
   ═══════════════════════════════════════ */
const Icon = {
  Sparkle: ({ size = 18 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v18M3 12h18M5.636 5.636l12.728 12.728M18.364 5.636L5.636 18.364" />
    </svg>
  ),
  Play: ({ size = 16 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M6.906 4.537A.6.6 0 0 0 6 5.053v13.894a.6.6 0 0 0 .906.516l11.723-6.947a.6.6 0 0 0 0-1.032L6.906 4.537Z" />
    </svg>
  ),
  Stop: ({ size = 16 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="6" width="12" height="12" rx="1" />
    </svg>
  ),
  File: ({ size = 14 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  ),
  Check: ({ size = 14 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
  X: ({ size = 14 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  ),
  Loader: ({ size = 14 }: { size?: number }) => (
    <svg className="animate-spin-slow" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M12 2a10 10 0 0 1 10 10" />
    </svg>
  ),
  Refresh: ({ size = 14 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" />
    </svg>
  ),
  Brain: ({ size = 16 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z" />
      <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z" />
    </svg>
  ),
  Terminal: ({ size = 14 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="4 17 10 11 4 5" /><line x1="12" y1="19" x2="20" y2="19" />
    </svg>
  ),
  Send: ({ size = 16 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M3.478 2.405a.75.75 0 0 0-.926.94l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.405Z" />
    </svg>
  ),
};

/* ═══════════════════════════════════════
   Status helpers
   ═══════════════════════════════════════ */
const STATUS_DOT: Record<string, { color: string; animate?: boolean }> = {
  pending: { color: "#444" },
  generating: { color: "#f59e0b", animate: true },
  verifying: { color: "#6366f1", animate: true },
  passed: { color: "#22c55e" },
  failed: { color: "#ef4444" },
  retrying: { color: "#f59e0b", animate: true },
};

const TRACE_STYLES: Record<string, { border: string; bg: string; text: string; dot: string }> = {
  pass: { border: "border-green-500/15", bg: "bg-green-500/[0.04]", text: "text-green-400", dot: "bg-green-500" },
  fail: { border: "border-red-500/15", bg: "bg-red-500/[0.04]", text: "text-red-400", dot: "bg-red-500" },
  retry: { border: "border-amber-500/15", bg: "bg-amber-500/[0.04]", text: "text-amber-400", dot: "bg-amber-500" },
  plan: { border: "border-indigo-500/15", bg: "bg-indigo-500/[0.04]", text: "text-indigo-400", dot: "bg-indigo-500" },
  worker: { border: "border-sky-500/15", bg: "bg-sky-500/[0.04]", text: "text-sky-400", dot: "bg-sky-500" },
  status: { border: "border-white/[0.04]", bg: "bg-white/[0.015]", text: "text-neutral-400", dot: "bg-neutral-500" },
};

/* ═══════════════════════════════════════
   Syntax Highlighting
   ═══════════════════════════════════════ */
const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const highlight = (code: string) => {
  let h = esc(code);
  h = h.replace(
    /\b(import|export|from|const|let|var|function|return|if|else|for|while|switch|case|break|continue|default|class|extends|implements|new|this|super|throw|try|catch|finally|typeof|instanceof|async|await|type|interface|enum)\b/g,
    '<span style="color:var(--code-keyword)">$1</span>'
  );
  h = h.replace(/(['"`])(.*?)\1/g, '<span style="color:var(--code-string)">$1$2$1</span>');
  h = h.replace(/\b(\d+\.?\d*)\b/g, '<span style="color:var(--code-number)">$1</span>');
  h = h.replace(/(\/\/.*)/g, '<span style="color:var(--code-comment);font-style:italic">$1</span>');
  h = h.replace(/\b([A-Za-z_]\w*)\s*(?=\()/g, '<span style="color:var(--code-function)">$1</span>');
  return h;
};

/* ═══════════════════════════════════════
   Main Component
   ═══════════════════════════════════════ */
export default function HomePage() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [files, setFiles] = useState<GeneratedFile[]>([]);
  const [activeFileIdx, setActiveFileIdx] = useState(0);
  const [trace, setTrace] = useState<TraceItem[]>([]);
  const [activeTab, setActiveTab] = useState<"code" | "reasoning">("code");
  const [finalStatus, setFinalStatus] = useState<string | null>(null);
  const [reasoning, setReasoning] = useState<string | null>(null);
  const traceRef = useRef<HTMLDivElement>(null);
  const codeRef = useRef<HTMLPreElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /* Auto-resize textarea */
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
  }, [prompt]);

  function addTrace(text: string, type: string) {
    const item = { id: crypto.randomUUID(), text, type, ts: Date.now() };
    setTrace((t) => [...t, item]);
    setTimeout(() => traceRef.current?.scrollTo({ top: traceRef.current.scrollHeight, behavior: "smooth" }), 50);
  }

  async function onRun() {
    if (!prompt.trim()) return;
    setLoading(true);
    setError(null);
    setFiles([]);
    setActiveFileIdx(0);
    setTrace([]);
    setFinalStatus(null);
    setReasoning(null);
    setActiveTab("code");
    setStatusMsg("Connecting…");

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
        setStatusMsg(`Planned ${evt.files.length} files`);
        addTrace(`Planned ${evt.files.length} files: ${evt.files.map((f: any) => f.filename).join(", ")}`, "plan");
        setFiles(evt.files.map((f: any) => ({ nodeId: f.node_id, filename: f.filename, content: "", status: "pending" as const })));
        break;
      case "reasoning":
        setReasoning(evt.content);
        setStatusMsg("Architecture analysis complete");
        addTrace("Architecture reasoning generated", "plan");
        setActiveTab("reasoning");
        break;
      case "file_start":
        setStatusMsg(`Generating ${evt.filename}`);
        addTrace(`Worker started: ${evt.filename}`, "worker");
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
        setStatusMsg(`Verifying ${evt.filename}`);
        addTrace(`Generated: ${evt.filename} (${evt.content.length} chars)`, "worker");
        setTimeout(() => codeRef.current?.scrollTo({ top: 0 }), 50);
        break;
      case "file_verified":
        setFiles((prev) => prev.map((f) => f.nodeId === evt.node_id ? { ...f, status: evt.status === "PASS" ? "passed" : "failed" } : f));
        if (evt.status === "PASS") {
          addTrace(`Verified: ${evt.filename}`, "pass");
        } else {
          addTrace(`Failed: ${evt.filename} — ${evt.issues?.join("; ")}`, "fail");
        }
        break;
      case "file_retry":
        setFiles((prev) => prev.map((f) => f.nodeId === evt.node_id ? { ...f, status: "retrying" } : f));
        setStatusMsg(`Retrying (attempt ${evt.attempt})`);
        addTrace(`Retry #${evt.attempt}: ${evt.issues?.join("; ")}`, "retry");
        break;
      case "worker_start":
      case "verify_start":
        setStatusMsg(evt.message);
        break;
      case "complete":
        const status = evt.run?.verifier_report?.status ?? "N/A";
        setFinalStatus(status);
        addTrace(`Complete — Final: ${status}`, status === "PASS" ? "pass" : "fail");
        break;
      case "error":
        setError(evt.message);
        addTrace(`Error: ${evt.message}`, "fail");
        break;
    }
  }

  const activeFile = files[activeFileIdx] ?? null;
  const passedCount = files.filter((f) => f.status === "passed").length;
  const totalCount = files.length;
  const hasStarted = trace.length > 0 || loading;

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden" style={{ background: "var(--bg-primary)", color: "var(--text-primary)" }}>

      {/* ═══ Navigation Bar ═══ */}
      <header
        className="shrink-0 h-[52px] px-5 flex items-center justify-between z-20"
        style={{ borderBottom: "1px solid var(--border-subtle)", background: "rgba(10,10,10,0.8)", backdropFilter: "blur(20px) saturate(180%)" }}
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2.5">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: "var(--accent)", color: "white" }}
            >
              <Icon.Sparkle size={14} />
            </div>
            <span className="text-[15px] font-semibold tracking-[-0.01em]" style={{ color: "var(--text-primary)" }}>
              CogniRoute
            </span>
          </div>

          {statusMsg && (
            <div className="flex items-center gap-2 ml-3 pl-3" style={{ borderLeft: "1px solid var(--border-subtle)" }}>
              <div className="w-1.5 h-1.5 rounded-full animate-pulse-glow" style={{ background: "var(--accent)" }} />
              <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>{statusMsg}</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          {totalCount > 0 && (
            <div className="flex items-center gap-2.5 text-xs" style={{ color: "var(--text-secondary)" }}>
              <span className="font-medium">{passedCount}/{totalCount} files</span>
              <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border-default)" }}>
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${(passedCount / totalCount) * 100}%`, background: "var(--accent)" }}
                />
              </div>
            </div>
          )}
          {finalStatus && (
            <div
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
              style={{
                background: finalStatus === "PASS" ? "var(--success-subtle)" : "var(--error-subtle)",
                color: finalStatus === "PASS" ? "var(--success)" : "var(--error)",
              }}
            >
              {finalStatus === "PASS" ? <Icon.Check size={12} /> : <Icon.X size={12} />}
              {finalStatus === "PASS" ? "Passed" : "Issues"}
            </div>
          )}
        </div>
      </header>

      {/* ═══ Main Content ═══ */}
      <div className="flex-1 min-h-0 flex">

        {/* ─── Left Sidebar ─── */}
        <div
          className="flex flex-col shrink-0"
          style={{ width: 400, borderRight: "1px solid var(--border-subtle)", background: "var(--bg-secondary)" }}
        >
          {/* Prompt Input */}
          <div className="p-4" style={{ borderBottom: "1px solid var(--border-subtle)" }}>
            <div
              className="rounded-xl overflow-hidden transition-all duration-300"
              style={{
                border: "1px solid var(--border-default)",
                background: "var(--bg-primary)",
                boxShadow: "0 0 0 0 transparent",
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = "var(--accent)";
                e.currentTarget.style.boxShadow = "0 0 0 3px var(--accent-subtle)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = "var(--border-default)";
                e.currentTarget.style.boxShadow = "0 0 0 0 transparent";
              }}
            >
              <textarea
                ref={textareaRef}
                className="w-full resize-none px-4 pt-3.5 pb-1.5 text-sm leading-relaxed outline-none"
                style={{
                  background: "transparent",
                  color: "var(--text-primary)",
                  fontFamily: "var(--font-sans)",
                  minHeight: 52,
                  maxHeight: 160,
                }}
                placeholder="Describe what to build…"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    onRun();
                  }
                }}
              />
              <div className="flex items-center justify-between px-3 pb-2.5">
                <span className="text-[11px] font-medium" style={{ color: "var(--text-quaternary)" }}>
                  Shift+Enter for new line
                </span>
                <button
                  onClick={onRun}
                  disabled={loading || !prompt.trim()}
                  className="w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed"
                  style={{
                    background: prompt.trim() ? "var(--accent)" : "var(--bg-tertiary)",
                    color: prompt.trim() ? "white" : "var(--text-quaternary)",
                  }}
                  aria-label="Run orchestration"
                >
                  {loading ? <Icon.Loader size={14} /> : <Icon.Send size={14} />}
                </button>
              </div>
            </div>

            {error && (
              <div
                className="mt-3 rounded-lg px-3.5 py-2.5 text-xs flex items-start gap-2 animate-fade-in"
                style={{ background: "var(--error-subtle)", color: "var(--error)", border: "1px solid rgba(239,68,68,0.15)" }}
              >
                <Icon.X size={12} />
                <span className="flex-1">{error}</span>
              </div>
            )}
          </div>

          {/* Event Stream */}
          <div className="flex-1 min-h-0 flex flex-col">
            <div
              className="px-4 py-2.5 flex items-center justify-between"
              style={{ borderBottom: "1px solid var(--border-subtle)" }}
            >
              <span className="text-[11px] font-semibold tracking-[0.08em] uppercase" style={{ color: "var(--text-tertiary)" }}>
                Activity
              </span>
              {trace.length > 0 && (
                <span
                  className="text-[10px] font-medium px-1.5 py-0.5 rounded"
                  style={{ background: "var(--bg-surface)", color: "var(--text-tertiary)" }}
                >
                  {trace.length}
                </span>
              )}
            </div>

            <div ref={traceRef} className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
              {trace.length === 0 && (
                <div className="h-full flex flex-col items-center justify-center gap-4 px-8">
                  <div
                    className="w-12 h-12 rounded-2xl flex items-center justify-center"
                    style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
                  >
                    <Icon.Terminal size={20} />
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                      No activity yet
                    </p>
                    <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
                      Enter a prompt to start the orchestration pipeline
                    </p>
                  </div>
                </div>
              )}
              {trace.map((t, i) => {
                const s = TRACE_STYLES[t.type] || TRACE_STYLES.status;
                return (
                  <div
                    key={t.id}
                    className={`text-xs leading-relaxed px-3 py-2 rounded-lg border ${s.border} ${s.bg} animate-fade-in`}
                    style={{ animationDelay: `${Math.min(i * 20, 200)}ms` }}
                  >
                    <div className="flex items-start gap-2.5">
                      <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${s.dot}`} />
                      <span className={`flex-1 break-words ${s.text}`}>{t.text}</span>
                      <span className="text-[10px] font-mono shrink-0 mt-0.5" style={{ color: "var(--text-quaternary)" }}>
                        {new Date(t.ts).toLocaleTimeString(undefined, { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* ─── Main Panel ─── */}
        <div className="flex-1 min-h-0 flex flex-col" style={{ background: "var(--bg-primary)" }}>

          {/* File Tabs + View Switcher */}
          <div
            className="shrink-0 flex items-center justify-between"
            style={{ borderBottom: "1px solid var(--border-subtle)", background: "var(--bg-secondary)" }}
          >
            <div className="flex overflow-x-auto flex-1 min-w-0">
              {files.map((f, i) => {
                const isActive = i === activeFileIdx && activeTab === "code";
                const dot = STATUS_DOT[f.status];
                return (
                  <button
                    key={f.nodeId}
                    onClick={() => { setActiveFileIdx(i); setActiveTab("code"); }}
                    className="shrink-0 px-4 py-2.5 text-xs font-mono flex items-center gap-2 transition-all duration-200 relative"
                    style={{
                      color: isActive ? "var(--text-primary)" : "var(--text-tertiary)",
                      background: isActive ? "var(--bg-primary)" : "transparent",
                    }}
                  >
                    <span
                      className={`w-2 h-2 rounded-full shrink-0 ${dot.animate ? "animate-pulse" : ""}`}
                      style={{ background: dot.color }}
                    />
                    {f.filename || f.nodeId}
                    {isActive && (
                      <span
                        className="absolute bottom-0 left-0 right-0 h-[2px]"
                        style={{ background: "var(--accent)" }}
                      />
                    )}
                  </button>
                );
              })}
              {files.length === 0 && (
                <div className="px-4 py-2.5 text-xs font-mono" style={{ color: "var(--text-quaternary)" }}>
                  No files generated
                </div>
              )}
            </div>

            {/* View toggles */}
            <div className="shrink-0 flex items-center gap-1 px-3" style={{ borderLeft: "1px solid var(--border-subtle)" }}>
              {(["code", "reasoning"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className="text-xs px-3 py-1.5 rounded-md flex items-center gap-1.5 font-medium transition-all duration-200"
                  style={{
                    color: activeTab === tab ? "var(--text-primary)" : "var(--text-tertiary)",
                    background: activeTab === tab ? "var(--bg-surface-hover)" : "transparent",
                  }}
                >
                  {tab === "code" ? <Icon.File size={12} /> : <Icon.Brain size={12} />}
                  {tab === "code" ? "Code" : "Reasoning"}
                </button>
              ))}
            </div>
          </div>

          {/* Content Viewer */}
          <div className="flex-1 min-h-0 overflow-hidden relative" style={{ background: "var(--code-bg)" }}>

            {activeTab === "code" ? (
              activeFile ? (
                <div className="h-full flex flex-col">
                  {/* File info bar */}
                  <div
                    className="px-5 py-2 flex justify-between items-center"
                    style={{ borderBottom: "1px solid var(--border-subtle)", background: "rgba(0,0,0,0.3)" }}
                  >
                    <div className="flex items-center gap-2">
                      <Icon.File size={12} />
                      <span className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
                        {activeFile.filename}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono" style={{ color: "var(--text-quaternary)" }}>
                      {activeFile.content.length > 0 ? `${activeFile.content.split("\n").length} lines` : "—"}
                    </span>
                  </div>

                  {/* Code content */}
                  <pre
                    ref={codeRef}
                    className="flex-1 overflow-y-auto p-5 text-[13px] leading-[1.7] whitespace-pre-wrap break-words"
                    style={{ fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}
                  >
                    {activeFile.content ? (
                      <code dangerouslySetInnerHTML={{ __html: highlight(activeFile.content) }} />
                    ) : (
                      <div className="h-full flex items-center justify-center">
                        <div className="text-center" style={{ color: "var(--text-quaternary)" }}>
                          {activeFile.status === "generating" ? (
                            <div className="flex flex-col items-center gap-3">
                              <Icon.Loader size={20} />
                              <span className="text-sm">Generating code…</span>
                            </div>
                          ) : (
                            <div className="flex flex-col items-center gap-3">
                              <Icon.File size={20} />
                              <span className="text-sm">Waiting for worker assignment</span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </pre>
                </div>
              ) : (
                /* Empty state */
                <div className="h-full flex items-center justify-center">
                  <div className="text-center max-w-md px-8">
                    <div
                      className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6"
                      style={{ background: "var(--accent-subtle)", border: "1px solid var(--border-active)" }}
                    >
                      <Icon.Sparkle size={28} />
                    </div>
                    <h1 className="text-xl font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
                      Multi-Agent Code Generation
                    </h1>
                    <p className="text-sm leading-relaxed" style={{ color: "var(--text-tertiary)" }}>
                      Describe what you want to build. The orchestrator will plan the architecture,
                      generate each file with specialized AI agents, and verify the output automatically.
                    </p>
                    <div
                      className="mt-6 inline-flex items-center gap-2 text-xs font-medium px-3.5 py-2 rounded-lg"
                      style={{ background: "var(--bg-surface)", color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}
                    >
                      <Icon.Terminal size={12} />
                      Architect → Workers → Verifier Pipeline
                    </div>
                  </div>
                </div>
              )
            ) : (
              /* Reasoning tab */
              <div className="h-full overflow-y-auto p-8">
                {reasoning ? (
                  <div className="max-w-3xl mx-auto animate-fade-in">
                    <div className="flex items-center gap-2.5 mb-5">
                      <div
                        className="w-7 h-7 rounded-lg flex items-center justify-center"
                        style={{ background: "var(--info-subtle)", border: "1px solid rgba(99,102,241,0.2)" }}
                      >
                        <Icon.Brain size={14} />
                      </div>
                      <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                        Architect Reasoning
                      </span>
                    </div>
                    <div
                      className="rounded-xl p-6"
                      style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
                    >
                      <pre
                        className="text-sm leading-[1.8] whitespace-pre-wrap break-words"
                        style={{ fontFamily: "var(--font-sans)", color: "var(--text-secondary)" }}
                      >
                        {reasoning}
                      </pre>
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center" style={{ color: "var(--text-quaternary)" }}>
                    <Icon.Brain size={24} />
                    <p className="mt-4 text-sm">Architect reasoning appears here after analysis</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
