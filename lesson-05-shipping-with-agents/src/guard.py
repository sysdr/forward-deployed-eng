"""Checking a proposed change against the policy, before it lands.

Every check here is mechanical, which is the point. You will not read four hundred
lines of agent output carefully at five o'clock on a Thursday, and neither will
the customer's reviewer. What you will do is run this.
"""
from __future__ import annotations

from pydantic import BaseModel

from src.change import Operation, ProposedChange
from src.policy import ScopePolicy

DEPENDENCY_FILES = ("requirements.txt", "pyproject.toml", "package.json", "go.mod", "Gemfile")


class Violation(BaseModel):
    kind: str
    detail: str
    path: str | None = None


class GuardResult(BaseModel):
    title: str
    violations: list[Violation]

    @property
    def allowed(self) -> bool:
        return not self.violations

    def kinds(self) -> set[str]:
        return {v.kind for v in self.violations}


def check(change: ProposedChange, policy: ScopePolicy) -> GuardResult:
    """Run every mechanical check. Order does not matter; all of them run."""
    found: list[Violation] = []

    for f in change.files:
        if not policy.allows_path(f.path):
            found.append(Violation(kind="out-of-scope-path",
                                   detail="not inside what was agreed", path=f.path))
        if f.operation is Operation.DELETE and not policy.may_delete:
            found.append(Violation(
                kind="deletion",
                detail="the agreement did not include deleting files", path=f.path))
        if not policy.may_add_dependencies and f.path.endswith(DEPENDENCY_FILES) and f.added_lines:
            found.append(Violation(
                kind="new-dependency",
                detail="a dependency is someone else's supply chain", path=f.path))

    if change.file_count > policy.max_files_per_change:
        found.append(Violation(
            kind="too-many-files",
            detail=f"{change.file_count} files, the agreement says {policy.max_files_per_change}"))

    body = change.added_text()
    for needle in policy.forbidden_content:
        if needle in body:
            found.append(Violation(kind="forbidden-content",
                                   detail=f"the change adds a line containing {needle!r}"))

    return GuardResult(title=change.title, violations=found)
