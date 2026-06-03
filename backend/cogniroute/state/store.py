from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
