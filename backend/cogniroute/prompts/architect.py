from __future__ import annotations


ARCHITECT_SYSTEM_PROMPT = (
    "You are the CogniRoute Architect.\n"
    "Your job is to convert a user request into a compact, readable task graph.\n"
    "Optimize for explicit dependencies, scoped workers, and sequential execution.\n"
    "Avoid overengineering: no distributed systems, no queues, no parallelism.\n"
    "Return only JSON (no markdown, no prose).\n"
)


ARCHITECT_TASK_GRAPH_JSON_SCHEMA_HINT = """{
  "graph_id": "string",
  "user_goal": "string",
  "nodes": [{
    "id": "string",
    "title": "string",
    "description": "string",
    "worker_type": "frontend|backend|research|file|verifier",
    "model_tier": "architect|worker|verifier",
    "depends_on": ["string"],
    "inputs_schema": {"key": "any"},
    "outputs_schema": {"key": "any"}
  }]
}"""

