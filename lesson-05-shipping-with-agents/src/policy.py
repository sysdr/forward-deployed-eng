"""What you are allowed to touch, written down before you start.

On an engagement you are a guest in a repository someone else is on call for.
The agreement about what you may change is usually a sentence in a kickoff call,
which means it is not an agreement at all. This file makes it a file.
"""
from __future__ import annotations

import fnmatch

from pydantic import BaseModel, Field


class ScopePolicy(BaseModel):
    """The written agreement, in a form a program can check."""

    engagement: str
    may_edit: list[str] = Field(default_factory=list)
    never_touch: list[str] = Field(default_factory=list)
    may_delete: bool = False
    may_add_dependencies: bool = False
    max_files_per_change: int = 12
    forbidden_content: list[str] = Field(default_factory=list)

    def allows_path(self, path: str) -> bool:
        """True when the path is inside what was agreed."""
        if any(fnmatch.fnmatch(path, p) for p in self.never_touch):
            return False
        return any(fnmatch.fnmatch(path, p) for p in self.may_edit)


MERIDIAN = ScopePolicy(
    engagement="Meridian Mutual claims assistant",
    may_edit=[
        "services/claims-assistant/**", "docs/claims-assistant/**", "tests/claims_assistant/**",
    ],
    never_touch=[
        "**/secrets/**", "**/.env*", "infra/**", ".github/workflows/**",
        "services/billing/**", "services/policy-admin/**",
    ],
    may_delete=False,
    may_add_dependencies=False,
    max_files_per_change=12,
    # Strings that must never leave the customer's repository in a change.
    forbidden_content=["BEGIN PRIVATE KEY", "AKIA", "password =", "api_key ="],
)
