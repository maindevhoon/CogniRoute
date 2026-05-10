"use client";

import { useMemo, useRef, useState } from "react";
import ReactFlow, { Background, Controls, Edge, MiniMap, Node } from "reactflow";
import "reactflow/dist/style.css";

type WorkerType = "frontend" | "backend" | "research" | "file" | "verifier";
type ModelTier = "architect" | "worker" | "verifier";
type TaskStatus = "pending" | "running" | "succeeded" | "failed" | "skipped";
type TaskNode = { id: string; title: string; description: string; worker_type: WorkerType; model_tier: ModelTier; depends_on: string[]; inputs_schema: Record<string, unknown>; outputs_schema: Record<string, unknown> };
type TaskGraph = { graph_id: string; user_goal: string; nodes: TaskNode[] };
type NodeExecution = { node_id: string; status: TaskStatus; started_at_ms?: number | null; ended_at_ms?: number | null; error?: string | null; artifacts: Record<string, unknown> };
type TelemetrySpan = { span_id: string; name: string; worker_type?: WorkerType | null; model_tier?: ModelTier | null; started_at_ms: number; ended_at_ms?: number | null; status: "ok" | "error"; meta: Record<string, unknown> };
type TraceEvent = { event_id: string; at_ms: number; role: "system" | "user" | "architect" | "worker" | "verifier"; title: string; detail: string; node_id?: string | null; worker_type?: WorkerType | null; model_tier?: ModelTier | null; meta: Record<string, unknown> };
type OrchestrationRun = { run_id: string; prompt: string; plan: TaskGraph; execution: Record<string, NodeExecution>; spans: TelemetrySpan[]; trace: TraceEvent[]; routing_log: Array<Record<string, unknown>>; verifier_report: Record<string, unknown> };
type GeneratedFile = { nodeId: string; filename: string; content: string; status: "generating" | "verifying" | "passed" | "failed" | "retrying" };
type StreamEvent = { type: string; [key: string]: any };

function statusColor(s: TaskStatus) {
  return s === "succeeded" ? "#22c55e" : s === "running" ? "#38bdf8" : s === "failed" ? "#ef4444" : s === "skipped" ? "#a1a1aa" : "#64748b";
}
function tierBadge(t: ModelTier) {
  if (t === "architect") return { label: "Architect (32B)", border: "border-cyan-400/40", bg: "bg-cyan-400/10" };
  if (t === "verifier") return { label: "Verifier (32B)", border: "border-fuchsia-400/40", bg: "bg-fuchsia-400/10" };
  return { label: "Worker (7B)", border: "border-emerald-400/30", bg: "bg-emerald-400/10" };
}
function langFromFilename(f: string) {
  if (f.endsWith(".py")) return "python";
  if (f.endsWith(".tsx") || f.endsWith(".ts")) return "typescript";
  if (f.endsWith(".jsx") || f.endsWith(".js")) return "javascript";
  if (f.endsWith(".css")) return "css";
  if (f.endsWith(".json")) return "json";
  if (f.endsWith(".md")) return "markdown";
  return "plaintext";
}

export default function HomePage() {
  const [prompt, setPrompt] = useState("Build a modern SaaS dashboard");
  const [run, setRun] = useState<OrchestrationRun | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"files" | "transcript" | "routing" | "spans" | "graph">("files");
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [files, setFiles] = useState<GeneratedFile[]>([]);
  const [activeFileIdx, setActiveFileIdx] = useState(0);
  const [liveTrace, setLiveTrace] = useState<Array<{ id: string; text: string; type: string }>>([]);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const codeScrollRef = useRef<HTMLPreElement | null>(null);

  const [chat, setChat] = useState<Array<{ id: string; role: "user" | "assistant"; content: string; at: number }>>([
    { id: "seed_u", role: "user", content: "Build a modern SaaS dashboard", at: Date.now() },
    { id: "seed_a", role: "assistant", content: "Run orchestration to see the Architect plan, worker execution, and verifier results.", at: Date.now() },
  ]);

  const nodesAndEdges = useMemo(() => {
    if (!run) return { nodes: [] as Node[], edges: [] as Edge[] };
    const nodes: Node[] = run.plan.nodes.map((n, idx) => {
      const ex = run.execution[n.id];
      const badge = tierBadge(n.model_tier);
      return {
        id: n.id,
        position: { x: 220 * (idx % 3), y: 140 * Math.floor(idx / 3) },
        data: {
          label: (
            <div className="w-[220px]">
              <div className="flex items-center justify-between gap-1">
                <div className="font-semibold text-xs text-slate-100 truncate">{n.title}</div>
                <span className="text-[9px] px-1.5 py-0.5 rounded-full border border-white/10 bg-white/5 shrink-0">{n.worker_type}</span>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <span className={"text-[9px] px-1.5 py-0.5 rounded-full border " + badge.border + " " + badge.bg}>{badge.label}</span>
                <span className="text-[9px] text-slate-400">{ex?.status ?? "pending"}</span>
              </div>
            </div>
          ),
        },
        style: { border: `1px solid ${statusColor(ex?.status ?? "pending")}55`, background: "rgba(255,255,255,0.03)", borderRadius: 14, padding: 10 },
      };
    });
    const edges: Edge[] = [];
    for (const n of run.plan.nodes) for (const dep of n.depends_on ?? []) edges.push({ id: `${dep}->${n.id}`, source: dep, target: n.id, animated: run.execution[n.id]?.status === "running", style: { stroke: "rgba(148,163,184,0.6)" } });
    return { nodes, edges };
  }, [run]);

  const selected = useMemo(() => {
    if (!run || !selectedNodeId) return null;
    return { node: run.plan.nodes.find((n) => n.id === selectedNodeId) ?? null, ex: run.execution[selectedNodeId] ?? null };
  }, [run, selectedNodeId]);

  async function onRun() {
    setLoading(true);
    setError(null);
    setSelectedNodeId(null);
    setRun(null);
    setFiles([]);
    setActiveFileIdx(0);
    setLiveTrace([]);
    setActiveTab("files");
    setStatusMsg("Connecting...");

    const userMsg = { id: crypto.randomUUID(), role: "user" as const, content: prompt, at: Date.now() };
    setChat((c) => [...c, userMsg]);

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
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          const dataLine = line.trim();
          if (!dataLine.startsWith("data: ")) continue;
          try {
            const evt: StreamEvent = JSON.parse(dataLine.slice(6));
            handleEvent(evt);
          } catch { /* skip malformed */ }
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
    const traceId = crypto.randomUUID();
    switch (evt.type) {
      case "status":
        setStatusMsg(evt.message);
        setLiveTrace((t) => [...t, { id: traceId, text: evt.message, type: "status" }]);
        break;
      case "plan":
        setStatusMsg(`Planned ${evt.files.length} files`);
        setLiveTrace((t) => [...t, { id: traceId, text: `Architect planned ${evt.files.length} files: ${evt.files.map((f: any) => f.filename).join(", ")}`, type: "plan" }]);
        setFiles(evt.files.map((f: any) => ({ nodeId: f.node_id, filename: f.filename, content: "", status: "generating" as const })));
        break;
      case "file_start":
        setStatusMsg(`Generating ${evt.filename}...`);
        setLiveTrace((t) => [...t, { id: traceId, text: `Worker started: ${evt.filename}`, type: "worker" }]);
        setFiles((prev) => prev.map((f) => f.nodeId === evt.node_id ? { ...f, status: "generating" } : f));
        setActiveFileIdx((prev) => {
          const idx = files.findIndex((f) => f.nodeId === evt.node_id);
          return idx >= 0 ? idx : prev;
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
        setLiveTrace((t) => [...t, { id: traceId, text: `Code generated: ${evt.filename} (${evt.content.length} chars)`, type: "worker" }]);
        break;
      case "file_verified":
        setFiles((prev) => prev.map((f) => f.nodeId === evt.node_id ? { ...f, status: evt.status === "PASS" ? "passed" : "failed" } : f));
        setLiveTrace((t) => [...t, { id: traceId, text: `Verified ${evt.filename}: ${evt.status}${evt.issues ? " — " + evt.issues.join("; ") : ""}`, type: evt.status === "PASS" ? "pass" : "fail" }]);
        break;
      case "file_retry":
        setFiles((prev) => prev.map((f) => f.nodeId === evt.node_id ? { ...f, status: "retrying" } : f));
        setStatusMsg(`Retrying (attempt ${evt.attempt})...`);
        setLiveTrace((t) => [...t, { id: traceId, text: `Retrying with feedback: ${evt.issues?.join("; ")}`, type: "retry" }]);
        break;
      case "worker_start":
        setStatusMsg(evt.message);
        break;
      case "verify_start":
        setStatusMsg(evt.message);
        break;
      case "complete":
        setRun(evt.run);
        const ok = evt.run?.verifier_report?.status === "PASS";
        const fileCount = Object.keys(evt.run?.execution ?? {}).length;
        setChat((c) => [...c, { id: crypto.randomUUID(), role: "assistant", content: `Generated ${fileCount} tasks. Final verification: ${ok ? "PASS ✅" : "Issues detected ⚠️"}`, at: Date.now() }]);
        setLiveTrace((t) => [...t, { id: traceId, text: `Orchestration complete — ${ok ? "PASS" : "FAIL"}`, type: ok ? "pass" : "fail" }]);
        break;
      case "error":
        setError(evt.message);
        break;
    }
  }

  const activeFile = files[activeFileIdx] ?? null;

  return (
    <div className="h-screen w-screen">
      <div className="h-full grid grid-cols-[380px_1fr]">
        {/* ─── Left: Chat + Live Trace ─── */}
        <div className="h-full border-r border-white/10 bg-black/25 backdrop-blur flex flex-col">
          <div className="px-4 py-3 border-b border-white/10">
            <div className="text-lg font-semibold">CogniRoute</div>
            <div className="mt-0.5 text-[11px] text-slate-400">AI orchestration runtime — Architect → Workers → Verifier</div>
          </div>

          <div ref={chatScrollRef} className="flex-1 overflow-auto px-3 py-3 space-y-2">
            {chat.map((m) => (
              <div key={m.id} className={"flex " + (m.role === "user" ? "justify-end" : "justify-start")}>
                <div className={"max-w-[85%] rounded-2xl border px-3 py-2 text-sm leading-5 " + (m.role === "user" ? "border-cyan-400/25 bg-cyan-400/10" : "border-white/10 bg-white/5")}>
                  <div className="text-[10px] uppercase tracking-wide text-slate-400">{m.role}</div>
                  <div className="mt-1 whitespace-pre-wrap">{m.content}</div>
                </div>
              </div>
            ))}
            {/* Live trace feed */}
            {liveTrace.length > 0 && (
              <div className="mt-2 space-y-1">
                {liveTrace.map((t) => (
                  <div key={t.id} className={"text-[11px] px-2 py-1 rounded-lg border " +
                    (t.type === "pass" ? "border-emerald-400/20 bg-emerald-400/5 text-emerald-300" :
                     t.type === "fail" || t.type === "retry" ? "border-red-400/20 bg-red-400/5 text-red-300" :
                     t.type === "plan" ? "border-cyan-400/20 bg-cyan-400/5 text-cyan-300" :
                     t.type === "worker" ? "border-amber-400/20 bg-amber-400/5 text-amber-300" :
                     "border-white/10 bg-white/5 text-slate-300")}>
                    {t.text}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Status bar */}
          {statusMsg && (
            <div className="px-3 py-2 border-t border-white/10 bg-cyan-400/5">
              <div className="text-[11px] text-cyan-300 flex items-center gap-2">
                <span className="inline-block w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                {statusMsg}
              </div>
            </div>
          )}

          <div className="p-3 border-t border-white/10">
            <textarea
              className="w-full min-h-[60px] resize-none rounded-xl bg-black/40 border border-white/10 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400/40"
              placeholder="Describe what to build..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
            <div className="mt-2 flex items-center justify-between">
              <div className="text-[10px] text-slate-500 font-mono">{run ? `run=${run.run_id}` : "ready"}</div>
              <button onClick={onRun} disabled={loading} className="rounded-xl px-4 py-1.5 text-sm font-semibold border border-cyan-400/30 bg-cyan-400/10 hover:bg-cyan-400/15 disabled:opacity-50 transition-colors">
                {loading ? "Running…" : "Run"}
              </button>
            </div>
            {error && <div className="mt-2 rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-200">{error}</div>}
          </div>
        </div>

        {/* ─── Right: Code Viewer + Tabs ─── */}
        <div className="h-full bg-black/10 flex flex-col">
          <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-slate-200">Output</div>
            <div className="flex items-center gap-1.5">
              {(["files", "transcript", "routing", "spans", "graph"] as const).map((t) => (
                <button key={t} onClick={() => setActiveTab(t)} className={"text-[11px] px-2.5 py-1 rounded-lg border transition-colors " + (activeTab === t ? "border-cyan-400/30 bg-cyan-400/10 text-cyan-300" : "border-white/10 bg-white/5 text-slate-400 hover:text-slate-200")}>
                  {t}
                </button>
              ))}
            </div>
          </div>

          {activeTab === "files" ? (
            <div className="flex-1 min-h-0 flex flex-col">
              {/* File tabs */}
              {files.length > 0 && (
                <div className="flex items-center gap-0 border-b border-white/10 overflow-x-auto px-2 shrink-0">
                  {files.map((f, i) => {
                    const statusIcon = f.status === "passed" ? "✅" : f.status === "failed" ? "❌" : f.status === "verifying" ? "🔍" : f.status === "retrying" ? "🔄" : "⏳";
                    return (
                      <button key={f.nodeId} onClick={() => setActiveFileIdx(i)} className={"px-3 py-2 text-[11px] font-mono border-b-2 transition-colors whitespace-nowrap " + (i === activeFileIdx ? "border-cyan-400 text-cyan-300 bg-white/5" : "border-transparent text-slate-400 hover:text-slate-200")}>
                        {statusIcon} {f.filename || f.nodeId}
                      </button>
                    );
                  })}
                </div>
              )}
              {/* Code display */}
              <div className="flex-1 min-h-0 overflow-auto">
                {activeFile ? (
                  <pre ref={codeScrollRef} className="p-4 text-[12px] leading-5 font-mono text-slate-200 whitespace-pre-wrap break-words">
                    {activeFile.content || (
                      <span className="text-slate-500 italic">
                        {activeFile.status === "generating" ? "⏳ Worker is generating code..." : "Waiting..."}
                      </span>
                    )}
                  </pre>
                ) : (
                  <div className="p-6 text-sm text-slate-400">Run orchestration to generate files.</div>
                )}
              </div>
            </div>
          ) : activeTab === "graph" && run ? (
            <div className="flex-1 min-h-0">
              <ReactFlow nodes={nodesAndEdges.nodes} edges={nodesAndEdges.edges} onNodeClick={(_, n) => setSelectedNodeId(n.id)} fitView>
                <Background gap={18} size={1} color="rgba(148,163,184,0.25)" />
                <MiniMap pannable zoomable style={{ backgroundColor: "rgba(0,0,0,0.35)" }} />
                <Controls />
              </ReactFlow>
            </div>
          ) : run ? (
            <div className="flex-1 min-h-0 grid grid-cols-[1fr_360px]">
              <div className="h-full overflow-auto px-4 py-4 space-y-2">
                {activeTab === "transcript" && run.trace?.map((e) => (
                  <div key={e.event_id} className="rounded-xl border border-white/10 bg-white/5 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-[10px] text-slate-400 uppercase tracking-wide">{e.role}</div>
                      <div className="text-[9px] text-slate-500 font-mono">{e.model_tier ?? "—"}</div>
                    </div>
                    <div className="mt-1 text-sm font-semibold text-slate-100">{e.title}</div>
                    <div className="mt-1 text-xs text-slate-300 whitespace-pre-wrap">{e.detail}</div>
                  </div>
                ))}
                {activeTab === "routing" && run.routing_log.map((e, i) => (
                  <div key={i} className="text-xs text-slate-200 rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                    <span className="font-mono">{String((e as any).node_id)}</span>
                    <span className="text-slate-400"> → </span>
                    <span className="font-semibold">{String((e as any).chosen_worker)}</span>
                  </div>
                ))}
                {activeTab === "spans" && run.spans.map((s) => (
                  <div key={s.span_id} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-xs font-mono text-slate-100">{s.name}</div>
                      <div className="text-[10px] text-slate-400">{s.ended_at_ms ? `${s.ended_at_ms - s.started_at_ms}ms` : "…"}</div>
                    </div>
                    <div className="mt-1 text-[10px] text-slate-400">
                      {s.worker_type ? `worker=${s.worker_type}` : "—"} · {s.model_tier ? `tier=${s.model_tier}` : "—"} · {s.status}
                    </div>
                  </div>
                ))}
              </div>
              <div className="h-full border-l border-white/10 bg-black/25 px-4 py-4 overflow-auto">
                <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                  <div className="text-xs text-slate-400">Run</div>
                  <div className="mt-1 text-sm text-slate-100 font-mono">{run.run_id}</div>
                  <div className="mt-2 text-xs text-slate-400">Verifier</div>
                  <div className="mt-1">
                    <span className={"text-xs px-2 py-0.5 rounded-full border " + ((run.verifier_report as any)?.status === "PASS" ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300" : "border-red-400/30 bg-red-400/10 text-red-300")}>
                      {(run.verifier_report as any)?.status === "PASS" ? "PASS ✅" : "Issues ⚠️"}
                    </span>
                  </div>
                </div>
                {selected?.node && (
                  <div className="mt-3 rounded-xl border border-white/10 bg-white/5 p-3">
                    <div className="text-xs font-semibold">{selected.node.title}</div>
                    <div className="mt-1 text-[11px] text-slate-400">{selected.node.description}</div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-6 text-sm text-slate-400">Run orchestration to see results.</div>
          )}
        </div>
      </div>
    </div>
  );
}
