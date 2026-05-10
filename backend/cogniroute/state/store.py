from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class StatePaths:
    """
    Centralized paths to the shared state layer.

    Defaults assume the repo root contains `state/`.
    """

    root_dir: Path

    @classmethod
    def default(cls) -> "StatePaths":
        # backend/cogniroute/state/store.py -> backend/cogniroute/state -> backend/cogniroute -> backend -> repo root
        repo_root = Path(__file__).resolve().parents[3]
        return cls(root_dir=repo_root / "state")

    @property
    def implementation_plan(self) -> Path:
        return self.root_dir / "implementation_plan.md"

    @property
    def system_contracts(self) -> Path:
        return self.root_dir / "system_contracts.md"

    @property
    def telemetry_json(self) -> Path:
        return self.root_dir / "telemetry.json"


class StateStore:
    """
    Thin file-backed store for the shared state layer.

    MVP goal: readable + deterministic, not an advanced memory system.
    """

    def __init__(self, *, paths: Optional[StatePaths] = None) -> None:
        self._paths = paths or StatePaths.default()

    def read_plan_markdown(self) -> str:
        return self._paths.implementation_plan.read_text(encoding="utf-8")

    def write_plan_markdown(self, markdown: str) -> None:
        self._paths.implementation_plan.write_text(markdown, encoding="utf-8")

    def read_contracts_markdown(self) -> str:
        return self._paths.system_contracts.read_text(encoding="utf-8")

    def write_contracts_markdown(self, markdown: str) -> None:
        self._paths.system_contracts.write_text(markdown, encoding="utf-8")

    def append_telemetry_event(self, event: dict[str, Any]) -> None:
        p = self._paths.telemetry_json
        data = {"events": []}
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8") or '{"events":[]}')
        data.setdefault("events", []).append(event)
        p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

