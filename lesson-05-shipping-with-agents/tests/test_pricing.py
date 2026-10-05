"""Prices are the one perishable thing in this lesson, so the maths on them
has to be right and the numbers themselves have to live in one file."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.pricing import FREE, HOSTED, LAPTOP, PRICES_CHECKED, MachinePrice, TokenPrice


class TestTokenPrice:
    def test_a_million_tokens_costs_the_stated_rate(self) -> None:
        p = TokenPrice(label="x", input_per_million=3.0, output_per_million=15.0)
        assert p.cost(1_000_000, 0) == (3.0, 0.0)
        assert p.cost(0, 1_000_000) == (0.0, 15.0)

    def test_output_usually_costs_more_than_input(self) -> None:
        i, o = HOSTED.cost(1000, 1000)
        assert o > i

    def test_free_is_free(self) -> None:
        assert FREE.cost(5_000_000, 5_000_000) == (0.0, 0.0)

    def test_negative_rates_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TokenPrice(label="x", input_per_million=-1, output_per_million=1)


class TestCaching:
    def test_a_cached_prefix_is_billed_at_the_cheaper_rate(self) -> None:
        p = TokenPrice(label="x", input_per_million=3.0, output_per_million=15.0,
                       cached_input_per_million=0.30)
        plain, _ = p.cost(1_000_000, 0)
        cached, _ = p.cost(1_000_000, 0, cached_tokens=900_000)
        assert cached < plain
        # 100k at $3 plus 900k at $0.30
        assert cached == pytest.approx(0.3 + 0.27, abs=1e-6)

    def test_no_cache_rate_means_everything_is_billed_normally(self) -> None:
        p = TokenPrice(label="x", input_per_million=3.0, output_per_million=0.0)
        assert p.cost(1_000_000, 0, cached_tokens=900_000)[0] == 3.0


class TestMachinePrice:
    def test_an_hour_costs_the_hourly_rate(self) -> None:
        assert MachinePrice(label="x", per_hour=0.05).cost(3600) == 0.05

    def test_a_machine_you_already_own_still_has_a_number(self) -> None:
        """It happens to be zero here, which is the cheapest option, not no option."""
        assert LAPTOP.cost(3600) == 0.0


class TestTheFileItself:
    def test_the_price_book_carries_a_date(self) -> None:
        """Prices go stale. A reader has to be able to see how stale."""
        assert len(PRICES_CHECKED) == 10 and PRICES_CHECKED.startswith("20")
