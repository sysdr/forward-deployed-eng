"""The shape a proposed change arrives in."""
from __future__ import annotations

from src.change import FileChange, Operation, ProposedChange


def _change(*files: FileChange) -> ProposedChange:
    return ProposedChange(title="t", asked_for="a", files=list(files))


class TestFileCount:
    def test_it_counts_the_files(self) -> None:
        assert _change(
            FileChange(path="a.py", operation=Operation.EDIT),
            FileChange(path="b.py", operation=Operation.ADD),
        ).file_count == 2

    def test_an_empty_change_touches_nothing(self) -> None:
        assert _change().file_count == 0


class TestAddedText:
    def test_it_joins_every_added_line_across_files(self) -> None:
        change = _change(
            FileChange(path="a.py", operation=Operation.EDIT, added_lines=["one", "two"]),
            FileChange(path="b.py", operation=Operation.ADD, added_lines=["three"]),
        )
        assert change.added_text() == "one\ntwo\nthree"

    def test_removed_lines_are_not_added_text(self) -> None:
        """A line the change deletes is not a line the change introduces."""
        change = _change(
            FileChange(path="a.py", operation=Operation.EDIT, removed_lines=["api_key = 'x'"]),
        )
        assert change.added_text() == ""
