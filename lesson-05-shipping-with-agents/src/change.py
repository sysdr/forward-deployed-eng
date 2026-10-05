"""A proposed change, before it lands.

Deliberately not a git diff. An agent proposes edits, and you want to check them
in the same shape whether they came from a patch file, a pull request or an agent
holding them in memory.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, computed_field


class Operation(StrEnum):
    ADD = "add"
    EDIT = "edit"
    DELETE = "delete"


class FileChange(BaseModel):
    path: str
    operation: Operation
    added_lines: list[str] = Field(default_factory=list)
    removed_lines: list[str] = Field(default_factory=list)


class ProposedChange(BaseModel):
    """What the agent wants to do, and what it was asked to do."""

    title: str
    asked_for: str
    files: list[FileChange]

    @computed_field
    @property
    def file_count(self) -> int:
        return len(self.files)

    def added_text(self) -> str:
        return "\n".join(line for f in self.files for line in f.added_lines)
