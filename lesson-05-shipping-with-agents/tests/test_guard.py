"""What the guard catches, and the one thing it provably cannot."""
from __future__ import annotations

from src.change import FileChange, Operation, ProposedChange
from src.guard import check
from src.policy import MERIDIAN, ScopePolicy

CLAIMS = "services/claims-assistant"


def _change(*files: FileChange, asked: str = "add a log line") -> ProposedChange:
    return ProposedChange(title="t", asked_for=asked, files=list(files))


def _edit(path: str, *added: str) -> FileChange:
    return FileChange(path=path, operation=Operation.EDIT, added_lines=list(added))


class TestPaths:
    def test_a_change_inside_the_agreement_is_allowed(self) -> None:
        assert check(_change(_edit(f"{CLAIMS}/a.py", "x = 1")), MERIDIAN).allowed

    def test_a_change_outside_it_is_named_with_its_path(self) -> None:
        result = check(_change(_edit("services/billing/ledger.py", "x = 1")), MERIDIAN)
        assert result.kinds() == {"out-of-scope-path"}
        assert result.violations[0].path == "services/billing/ledger.py"


class TestDeletes:
    def test_a_delete_is_refused_when_the_agreement_did_not_include_one(self) -> None:
        change = _change(FileChange(path=f"{CLAIMS}/old.py", operation=Operation.DELETE))
        assert "deletion" in check(change, MERIDIAN).kinds()

    def test_a_delete_is_fine_once_the_agreement_says_so(self) -> None:
        policy = MERIDIAN.model_copy(update={"may_delete": True})
        change = _change(FileChange(path=f"{CLAIMS}/old.py", operation=Operation.DELETE))
        assert check(change, policy).allowed


class TestDependencies:
    def test_adding_a_line_to_requirements_is_refused(self) -> None:
        change = _change(_edit(f"{CLAIMS}/requirements.txt", "tenacity==9.0.0"))
        assert "new-dependency" in check(change, MERIDIAN).kinds()

    def test_touching_a_dependency_file_without_adding_anything_is_fine(self) -> None:
        """Reordering or removing lines is not the same as pulling in new code."""
        change = _change(FileChange(path=f"{CLAIMS}/pyproject.toml",
                                    operation=Operation.EDIT, removed_lines=["old==1.0"]))
        assert check(change, MERIDIAN).allowed


class TestSize:
    def test_more_files_than_agreed_is_refused_with_both_numbers(self) -> None:
        files = [_edit(f"{CLAIMS}/h{i}.py", "log = x") for i in range(13)]
        result = check(_change(*files), MERIDIAN)
        assert "too-many-files" in result.kinds()
        assert "13 files" in result.violations[-1].detail

    def test_exactly_the_limit_is_allowed(self) -> None:
        files = [_edit(f"{CLAIMS}/h{i}.py", "log = x") for i in range(12)]
        assert check(_change(*files), MERIDIAN).allowed


class TestForbiddenContent:
    def test_a_credential_shaped_line_is_refused(self) -> None:
        change = _change(_edit(f"{CLAIMS}/a.py", 'api_key = "sk-live-9f2c41"'))
        result = check(change, MERIDIAN)
        assert "forbidden-content" in result.kinds()
        assert "api_key =" in result.violations[0].detail

    def test_the_needle_has_to_be_in_an_added_line(self) -> None:
        change = _change(FileChange(path=f"{CLAIMS}/a.py", operation=Operation.EDIT,
                                    removed_lines=['api_key = "sk-live-9f2c41"']))
        assert check(change, MERIDIAN).allowed


class TestSeveralAtOnce:
    def test_every_check_runs_rather_than_stopping_at_the_first(self) -> None:
        change = _change(
            FileChange(path="infra/main.tf", operation=Operation.DELETE),
            _edit(f"{CLAIMS}/requirements.txt", "tenacity==9.0.0"),
        )
        assert check(change, MERIDIAN).kinds() == {
            "out-of-scope-path", "deletion", "new-dependency"}


class TestWhatItCannotSee:
    def test_a_change_that_does_more_than_asked_passes_every_rule(self) -> None:
        """The finding this lesson exists for. One file, in scope, no delete,
        no dependency, no credential, and nobody asked for the second half."""
        change = ProposedChange(
            title="Add the log line and rewrite the answerer",
            asked_for="Add a log line recording how long an answer took.",
            files=[_edit(f"{CLAIMS}/answerer.py",
                         "    log.info('answered')",
                         "class AnswerPipeline:",
                         "    def run(self, q): return self._finish(q)")],
        )
        assert check(change, MERIDIAN).allowed

    def test_removing_a_check_inside_an_edit_is_not_a_deletion(self) -> None:
        change = ProposedChange(
            title="Speed up the answer path", asked_for="make it faster",
            files=[FileChange(path=f"{CLAIMS}/answerer.py", operation=Operation.EDIT,
                              added_lines=["    return self._model.answer(q)"],
                              removed_lines=["    if not self._policy.permits(q): raise Nope"])],
        )
        assert check(change, MERIDIAN).allowed


class TestThePolicyIsTheInput:
    def test_widening_may_edit_changes_the_verdict_and_nothing_else(self) -> None:
        change = _change(_edit("services/search-gateway/retry.py", "def retry(): ..."))
        assert not check(change, MERIDIAN).allowed
        wider: ScopePolicy = MERIDIAN.model_copy(
            update={"may_edit": [*MERIDIAN.may_edit, "services/search-gateway/**"]})
        assert check(change, wider).allowed
