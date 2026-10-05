"""The written agreement, checked the way a program checks it."""
from __future__ import annotations

from src.policy import MERIDIAN, ScopePolicy


class TestWhatAPathIsAllowedToBe:
    def test_a_path_inside_may_edit_is_allowed(self) -> None:
        assert MERIDIAN.allows_path("services/claims-assistant/answerer.py")

    def test_a_path_nobody_mentioned_is_not_allowed(self) -> None:
        assert not MERIDIAN.allows_path("services/search-gateway/retry.py")

    def test_never_touch_beats_may_edit(self) -> None:
        """The two lists overlap on purpose, and the refusal has to win."""
        policy = ScopePolicy(
            engagement="overlap",
            may_edit=["services/**"],
            never_touch=["services/billing/**"],
        )
        assert policy.allows_path("services/claims-assistant/a.py")
        assert not policy.allows_path("services/billing/ledger.py")

    def test_an_empty_may_edit_allows_nothing(self) -> None:
        assert not ScopePolicy(engagement="empty").allows_path("anything.py")


class TestTheMeridianPolicy:
    def test_it_refuses_deletes_and_dependencies_by_default(self) -> None:
        assert MERIDIAN.may_delete is False
        assert MERIDIAN.may_add_dependencies is False

    def test_it_names_the_engagement(self) -> None:
        assert "Meridian" in MERIDIAN.engagement

    def test_secrets_and_workflows_are_off_limits(self) -> None:
        assert not MERIDIAN.allows_path("services/claims-assistant/secrets/token")
        assert not MERIDIAN.allows_path(".github/workflows/deploy.yml")
