from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional


class ChecklistStatus(str, Enum):
    todo = "todo"
    done = "done"


@dataclass(frozen=True)
class PlanItem:
    section: str
    text: str
    status: ChecklistStatus

    def key(self) -> str:
        """
        Stable-ish identifier used for scoped updates.

        Not meant to be globally perfect; good enough for a hackathon demo.
        """

        normalized = re.sub(r"[^a-z0-9]+", "-", self.text.strip().lower()).strip("-")
        return f"{self.section.lower()}::{normalized}"


@dataclass(frozen=True)
class ImplementationPlan:
    """
    Parsed view of `state/implementation_plan.md`.

    We keep parsing intentionally simple:
    - Sections are headings like `## Backend`
    - Items are checklist bullets like `* [ ] Task` or `- [x] Task`
    """

    sections: dict[str, list[PlanItem]]
    raw_markdown: str

    def all_items(self) -> list[PlanItem]:
        out: list[PlanItem] = []
        for items in self.sections.values():
            out.extend(items)
        return out

    def items_in(self, section: str) -> list[PlanItem]:
        return list(self.sections.get(section, []))

    def first_todo_in(self, section: str) -> Optional[PlanItem]:
        for item in self.sections.get(section, []):
            if item.status == ChecklistStatus.todo:
                return item
        return None


_SECTION_RE = re.compile(r"^\s*##\s+(?P<title>.+?)\s*$")
_ITEM_RE = re.compile(r"^\s*[-*]\s+\[(?P<mark>[ xX])\]\s+(?P<text>.+?)\s*$")


def parse_implementation_plan(markdown: str) -> ImplementationPlan:
    sections: dict[str, list[PlanItem]] = {}
    current_section: str | None = None

    for line in markdown.splitlines():
        m = _SECTION_RE.match(line)
        if m:
            current_section = m.group("title").strip()
            sections.setdefault(current_section, [])
            continue

        m = _ITEM_RE.match(line)
        if m and current_section:
            status = ChecklistStatus.done if m.group("mark").strip().lower() == "x" else ChecklistStatus.todo
            sections[current_section].append(
                PlanItem(section=current_section, text=m.group("text").strip(), status=status)
            )

    return ImplementationPlan(sections=sections, raw_markdown=markdown)


def _render_item(item: PlanItem) -> str:
    mark = "x" if item.status == ChecklistStatus.done else " "
    return f"* [{mark}] {item.text}"


def apply_checklist_updates(
    markdown: str,
    *,
    updates: dict[str, ChecklistStatus],
    allowed_keys: Optional[set[str]] = None,
) -> str:
    """
    Apply checklist status updates by matching on computed PlanItem keys.

    - **updates**: map from `PlanItem.key()` -> status
    - **allowed_keys**: optional guardrail for scoped workers; if provided,
      only keys in this set can be updated.
    """

    plan = parse_implementation_plan(markdown)
    if not updates:
        return markdown

    # Build a quick lookup from (section, line text) key to new status.
    desired: dict[str, ChecklistStatus] = {}
    for k, st in updates.items():
        if allowed_keys is not None and k not in allowed_keys:
            continue
        desired[k] = st

    if not desired:
        return markdown

    # Re-render using original markdown with minimal rewriting:
    # only update checklist markers on matching items.
    out_lines: list[str] = []
    current_section: str | None = None

    for line in markdown.splitlines():
        sec = _SECTION_RE.match(line)
        if sec:
            current_section = sec.group("title").strip()
            out_lines.append(line)
            continue

        item_m = _ITEM_RE.match(line)
        if item_m and current_section:
            tmp_item = PlanItem(
                section=current_section,
                text=item_m.group("text").strip(),
                status=ChecklistStatus.done if item_m.group("mark").strip().lower() == "x" else ChecklistStatus.todo,
            )
            k = tmp_item.key()
            if k in desired:
                out_lines.append(_render_item(PlanItem(section=current_section, text=tmp_item.text, status=desired[k])))
            else:
                out_lines.append(line)
            continue

        out_lines.append(line)

    return "\n".join(out_lines) + ("\n" if markdown.endswith("\n") else "")


def scoped_keys_for_items(items: Iterable[PlanItem]) -> set[str]:
    return {i.key() for i in items}

