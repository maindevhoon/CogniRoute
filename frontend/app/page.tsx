"use client";

import { useMemo, useRef, useState } from "react";
import ReactFlow, { Background, Controls, Edge, MiniMap, Node } from "reactflow";
import "reactflow/dist/style.css";

type WorkerType = "frontend" | "backend" | "research" | "file" | "verifier";
type ModelTier = "architect" | "worker" | "verifier";
type TaskStatus = "pending" | "running" | "succeeded" | "failed" | "skipped";

type TaskNode = {
  id: string;
  title: string;
  description: string;
  worker_type: WorkerType;
  model_tier: ModelTier;
  depends_on: string[];
  inputs_schema: Record<string, unknown>;
  outputs_schema: Record<string, unknown>;
};

type TaskGraph = {
  graph_id: string;
  user_goal: string;
  nodes: TaskNode[];
};

type NodeExecution = {
  node_id: string;
  status: TaskStatus;
  started_at_ms?: number | null;
  ended_at_ms?: number | null;
  error?: string | null;
  artifacts: Record<string, unknown>;
};

type TelemetrySpan = {
  span_id: string;
  name: string;
  worker_type?: WorkerType | null;
  model_tier?: ModelTier | null;
  started_at_ms: number;
  ended_at_ms?: number | null;
  status: "ok" | "error";
  meta: Record<string, unknown>;
};

type OrchestrationRun = {
  run_id: string;
  prompt: string;
  plan: TaskGraph;
  execution: Record<string, NodeExecution>;
  spans: TelemetrySpan[];
  trace: Array<{
    event_id: string;
    at_ms: number;
    role: "system" | "user" | "architect" | "worker" | "verifier";
    title: string;
    detail: string;
    node_id?: string | null;
    worker_type?: WorkerType | null;
    model_tier?: ModelTier | null;
    meta: Record<string, unknown>;
  }>;
  routing_log: Array<Record<string, unknown>>;
  verifier_report: Record<string, unknown>;
};

function statusColor(status: TaskStatus): string {
  switch (status) {
    case "succeeded":
      return "#22c55e";
    case "running":
      return "#38bdf8";
    case "failed":
      return "#ef4444";
    case "skipped":
      return "#a1a1aa";
    case "pending":
    default:
      return "#64748b";
  }
}

function tierBadge(tier: ModelTier): { label: string; border: string; bg: string } {
  if (tier === "architect") return { label: "Architect (heavy)", border: "border-cyan-400/40", bg: "bg-cyan-400/10" };
  if (tier === "verifier") return { label: "Verifier (heavy)", border: "border-fuchsia-400/40", bg: "bg-fuchsia-400/10" };
  return { label: "Worker (light)", border: "border-emerald-400/30", bg: "bg-emerald-400/10" };
}

export default function HomePage() {
  const [prompt, setPrompt] = useState("Build a modern SaaS dashboard");
  const [run, setRun] = useState<OrchestrationRun | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"transcript" | "routing" | "spans" | "graph">("transcript");
  const chatScrollRef = useRef<HTMLDivElement | null>(null);

  const [chat, setChat] = useState<
    Array<{ id: string; role: "user" | "assistant"; content: string; at: number }>
  >([
    {
      id: "seed_u",
      role: "user",
      content: "Build a modern SaaS dashboard",
      at: Date.now()
    },
    {
      id: "seed_a",
      role: "assistant",
      content:
        "Run orchestration to see the Architect plan, capability routing, worker execution, and verifier checkpoint.",
      at: Date.now()
    }
  ]);

  const nodesAndEdges = useMemo(() => {
    if (!run) return { nodes: [] as Node[], edges: [] as Edge[] };
    const plan = run.plan;
    const exec = run.execution;

    const nodes: Node[] = plan.nodes.map((n, idx) => {
      const ex = exec[n.id];
      const badge = tierBadge(n.model_tier);
      return {
        id: n.id,
        position: { x: 220 * (idx % 3), y: 140 * Math.floor(idx / 3) },
        data: {
          label: (
            <div className="w-[240px]">
              <div className="flex items-center justify-between gap-2">
                <div className="font-semibold text-sm text-slate-100">{n.title}</div>
                <span className="text-[10px] px-2 py-0.5 rounded-full border border-white/10 bg-white/5">
                  {n.worker_type}
                </span>
              </div>
              <div className="mt-1 flex items-center justify-between gap-2">
                <span className={"text-[10px] px-2 py-0.5 rounded-full border " + badge.border + " " + badge.bg}>
                  {badge.label}
                </span>
                <span className="text-[10px] text-slate-300">{ex?.status ?? "pending"}</span>
              </div>
              <div className="mt-2 h-1.5 w-full rounded bg-white/5 overflow-hidden">
                <div
                  className="h-1.5"
                  style={{ width: ex?.status === "succeeded" ? "100%" : ex?.status === "running" ? "65%" : "20%", background: statusColor(ex?.status ?? "pending") }}
                />
              </div>
            </div>
          )
        },
        style: {
          border: `1px solid ${statusColor(ex?.status ?? "pending")}55`,
          background: "rgba(255,255,255,0.03)",
          borderRadius: 14,
          padding: 10,
          boxShadow: "0 10px 30px rgba(0,0,0,0.25)"
        }
      };
    });

    const edges: Edge[] = [];
    for (const n of plan.nodes) {
      for (const dep of n.depends_on ?? []) {
        edges.push({
          id: `${dep}->${n.id}`,
          source: dep,
          target: n.id,
          animated: run.execution[n.id]?.status === "running",
          style: { stroke: "rgba(148,163,184,0.6)" }
        });
      }
    }

    return { nodes, edges };
  }, [run]);

  const selected = useMemo(() => {
    if (!run || !selectedNodeId) return null;
    const node = run.plan.nodes.find((n) => n.id === selectedNodeId) ?? null;
    const ex = run.execution[selectedNodeId] ?? null;
    return { node, ex };
  }, [run, selectedNodeId]);

  async function onRun() {
    setLoading(true);
    setError(null);
    setSelectedNodeId(null);
    try {
      const userMsg = { id: crypto.randomUUID(), role: "user" as const, content: prompt, at: Date.now() };
      setChat((c) => [...c, userMsg]);

      const res = await fetch(process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000/run", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ prompt })
      });
      if (!res.ok) throw new Error(`Backend error: ${res.status}`);
      const data = (await res.json()) as { run: OrchestrationRun };
      setRun(data.run);
      setActiveTab("transcript");

      const ok = Boolean((data.run.verifier_report as any)?.ok);
      const assistantMsg = {
        id: crypto.randomUUID(),
        role: "assistant" as const,
        content: `Planned ${data.run.plan.nodes.length} tasks, routed to scoped workers, and ran verifier checkpoint: ${ok ? "OK" : "Issues detected"}.`,
        at: Date.now()
      };
      setChat((c) => [...c, assistantMsg]);
      setTimeout(() => chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: "smooth" }), 0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="h-screen w-screen">
      <div className="h-full grid grid-cols-[420px_1fr]">
        {/* Left: Chat */}
        <div className="h-full border-r border-white/10 bg-black/25 backdrop-blur flex flex-col">
          <div className="px-4 py-4 border-b border-white/10">
            <div className="text-lg font-semibold">CogniRoute</div>
            <div className="mt-1 text-xs text-slate-300">Chat + cognitive orchestration runtime (MVP)</div>
          </div>

          <div ref={chatScrollRef} className="flex-1 overflow-auto px-4 py-4 space-y-3">
            {chat.map((m) => (
              <div key={m.id} className={"flex " + (m.role === "user" ? "justify-end" : "justify-start")}>
                <div
                  className={
                    "max-w-[85%] rounded-2xl border px-3 py-2 text-sm leading-5 " +
                    (m.role === "user"
                      ? "border-cyan-400/25 bg-cyan-400/10 text-slate-100"
                      : "border-white/10 bg-white/5 text-slate-100")
                  }
                >
                  <div className="text-[10px] uppercase tracking-wide text-slate-300">
                    {m.role === "user" ? "User" : "Assistant"}
                  </div>
                  <div className="mt-1 whitespace-pre-wrap">{m.content}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 border-t border-white/10">
            <div className="rounded-2xl border border-white/10 bg-black/30 px-3 py-3">
              <div className="text-xs text-slate-300">Message</div>
              <textarea
                className="mt-2 w-full min-h-[84px] resize-none rounded-xl bg-black/40 border border-white/10 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400/40"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
              />
              <div className="mt-3 flex items-center justify-between gap-3">
                <div className="text-xs text-slate-400">
                  {run ? (
                    <span className="font-mono">last_run={run.run_id}</span>
                  ) : (
                    <span>no run yet</span>
                  )}
                </div>
                <button
                  onClick={onRun}
                  disabled={loading}
                  className="rounded-xl px-4 py-2 text-sm font-semibold border border-cyan-400/30 bg-cyan-400/10 hover:bg-cyan-400/15 disabled:opacity-60"
                >
                  {loading ? "Running…" : "Run"}
                </button>
              </div>
            </div>
            {error ? (
              <div className="mt-3 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                {error}
              </div>
            ) : null}
          </div>
        </div>

        {/* Right: Decision + Observability */}
        <div className="h-full bg-black/10 flex flex-col">
          <div className="px-4 py-4 border-b border-white/10 flex items-center justify-between gap-3">
            <div>
              <div className="text-lg font-semibold">Decision window</div>
              <div className="mt-1 text-xs text-slate-300">
                Architect planning → capability routing → scoped workers → verifier checkpoint
              </div>
            </div>
            <div className="flex items-center gap-2">
              {(["transcript", "routing", "spans", "graph"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setActiveTab(t)}
                  className={
                    "text-xs px-3 py-1.5 rounded-xl border " +
                    (activeTab === t ? "border-cyan-400/30 bg-cyan-400/10" : "border-white/10 bg-white/5")
                  }
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {!run ? (
            <div className="p-6 text-sm text-slate-300">Run an orchestration to populate the decision trace.</div>
          ) : (
            <div className="flex-1 min-h-0">
              {activeTab === "graph" ? (
                <div className="h-full">
                  <ReactFlow
                    nodes={nodesAndEdges.nodes}
                    edges={nodesAndEdges.edges}
                    onNodeClick={(_, n) => setSelectedNodeId(n.id)}
                    fitView
                  >
                    <Background gap={18} size={1} color="rgba(148,163,184,0.25)" />
                    <MiniMap pannable zoomable style={{ backgroundColor: "rgba(0,0,0,0.35)" }} />
                    <Controls />
                  </ReactFlow>
                </div>
              ) : (
                <div className="h-full grid grid-cols-[1fr_420px]">
                  <div className="h-full overflow-auto px-4 py-4">
                    {activeTab === "transcript" ? (
                      <div className="space-y-3">
                        {run.trace?.map((e) => (
                          <div key={e.event_id} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-xs text-slate-300 uppercase tracking-wide">{e.role}</div>
                              <div className="text-[10px] text-slate-400 font-mono">{e.model_tier ?? "—"}</div>
                            </div>
                            <div className="mt-1 text-sm font-semibold text-slate-100">{e.title}</div>
                            <div className="mt-1 text-xs text-slate-300 whitespace-pre-wrap">{e.detail}</div>
                            {e.node_id ? (
                              <div className="mt-2 text-[11px] text-slate-300">
                                node=<span className="font-mono">{e.node_id}</span>{" "}
                                {e.worker_type ? (
                                  <span className="text-slate-400">· worker={e.worker_type}</span>
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : null}

                    {activeTab === "routing" ? (
                      <div className="space-y-2">
                        {run.routing_log.map((e, i) => (
                          <div key={i} className="text-xs text-slate-200 rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
                            <span className="font-mono">{String((e as any).node_id)}</span>
                            <span className="text-slate-400"> → </span>
                            <span className="font-semibold">{String((e as any).chosen_worker)}</span>
                            <span className="text-slate-400"> ({String((e as any).reason)})</span>
                          </div>
                        ))}
                      </div>
                    ) : null}

                    {activeTab === "spans" ? (
                      <div className="space-y-2">
                        {run.spans.map((s) => (
                          <div key={s.span_id} className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-xs font-mono text-slate-100">{s.name}</div>
                              <div className="text-[10px] text-slate-300">
                                {s.ended_at_ms ? `${s.ended_at_ms - s.started_at_ms}ms` : "…"}
                              </div>
                            </div>
                            <div className="mt-1 text-[10px] text-slate-300">
                              {s.worker_type ? `worker=${s.worker_type}` : "worker=—"} ·{" "}
                              {s.model_tier ? `tier=${s.model_tier}` : "tier=—"} · status={s.status}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div className="h-full border-l border-white/10 bg-black/25 backdrop-blur px-4 py-4 overflow-auto">
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                      <div className="text-xs text-slate-300">Run</div>
                      <div className="mt-1 text-sm text-slate-100 font-mono">{run.run_id}</div>
                      <div className="mt-2 text-xs text-slate-300">Verifier</div>
                      <div className="mt-1 text-sm">
                        <span
                          className={
                            "px-2 py-0.5 rounded-full border " +
                            ((run.verifier_report as any)?.ok
                              ? "border-emerald-400/30 bg-emerald-400/10"
                              : "border-red-400/30 bg-red-400/10")
                          }
                        >
                          {(run.verifier_report as any)?.ok ? "OK" : "Issues"}
                        </span>
                      </div>
                    </div>

                    <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3">
                      <div className="text-sm font-semibold">Selected node</div>
                      {selected?.node ? (
                        <div className="mt-2">
                          <div className="text-sm text-slate-100 font-semibold">{selected.node.title}</div>
                          <div className="mt-1 text-xs text-slate-300">{selected.node.description}</div>
                          <div className="mt-3 text-xs text-slate-300">Artifacts</div>
                          <pre className="mt-2 text-[11px] leading-4 text-slate-200 rounded-xl border border-white/10 bg-black/30 p-3 overflow-auto">
                            {JSON.stringify(selected.ex?.artifacts ?? {}, null, 2)}
                          </pre>
                          {selected.ex?.error ? <div className="mt-2 text-xs text-red-200">{selected.ex.error}</div> : null}
                        </div>
                      ) : (
                        <div className="mt-2 text-xs text-slate-300">Open the Graph tab and click a node.</div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

