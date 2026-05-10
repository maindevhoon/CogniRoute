from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from ..schemas import ModelTier, TelemetrySpan, TraceEvent, TraceRole, WorkerType


def now_ms() -> int:
    return int(time.time() * 1000)


def token_estimate(text: str) -> int:
    """
    A cheap token estimate for demo telemetry.

    We intentionally avoid tokenizer dependencies in Phase 1.
    """

    # Heuristic: ~4 characters/token for English-ish text.
    return max(1, len(text) // 4) if text else 0


def span_start(
    spans: list[TelemetrySpan],
    *,
    name: str,
    role: Optional[str],
    worker_type: Optional[WorkerType],
    model_tier: Optional[ModelTier],
    model: Optional[str],
    meta: Optional[dict[str, Any]] = None,
) -> str:
    span_id = str(uuid.uuid4())
    spans.append(
        TelemetrySpan(
            span_id=span_id,
            name=name,
            role=role,
            worker_type=worker_type,
            model_tier=model_tier,
            model=model,
            started_at_ms=now_ms(),
            meta=meta or {},
        )
    )
    return span_id


def span_end(
    spans: list[TelemetrySpan],
    span_id: str,
    *,
    status: str = "ok",
    meta: Optional[dict[str, Any]] = None,
    latency_ms: Optional[int] = None,
    token_estimate_in: Optional[int] = None,
    token_estimate_out: Optional[int] = None,
) -> None:
    for s in spans:
        if s.span_id == span_id:
            s.ended_at_ms = now_ms()
            s.status = status  # type: ignore[assignment]
            if latency_ms is not None:
                s.latency_ms = latency_ms
            if token_estimate_in is not None:
                s.token_estimate_in = token_estimate_in
            if token_estimate_out is not None:
                s.token_estimate_out = token_estimate_out
            if meta:
                s.meta.update(meta)
            return


def trace_emit(
    trace: list[TraceEvent],
    *,
    role: TraceRole,
    title: str,
    detail: str,
    node_id: Optional[str] = None,
    worker_type: Optional[WorkerType] = None,
    model_tier: Optional[ModelTier] = None,
    model: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    trace.append(
        TraceEvent(
            event_id=str(uuid.uuid4()),
            at_ms=now_ms(),
            role=role,
            title=title,
            detail=detail,
            node_id=node_id,
            worker_type=worker_type,
            model_tier=model_tier,
            model=model,
            meta=meta or {},
        )
    )

