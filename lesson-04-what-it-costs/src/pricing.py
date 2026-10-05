"""What running a model costs, in one file with a date on it.

Prices change. Keeping them here, dated, means the rest of the lesson never
states a perishable fact and a reader in six months updates one file rather than
hunting through prose.

Two ways of paying, and the lesson prices both.

  hosted   you pay per token, and nothing when idle
  local    you pay for the machine by the hour whether it is busy or not,
           so the cost of a call is its share of that hour
"""
from __future__ import annotations

from pydantic import BaseModel, Field

PRICES_CHECKED = "2026-09-08"
"""Update this date whenever you touch the numbers below."""


class TokenPrice(BaseModel):
    """Dollars per million tokens, as published."""

    label: str
    input_per_million: float = Field(ge=0)
    output_per_million: float = Field(ge=0)
    cached_input_per_million: float | None = None

    def cost(
        self, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0
    ) -> tuple[float, float]:
        """Return input and output cost in dollars."""
        billable_prompt = max(0, prompt_tokens - cached_tokens)
        rate = self.cached_input_per_million
        cached_cost = (cached_tokens / 1_000_000) * rate if rate is not None else 0.0
        if rate is None:
            billable_prompt = prompt_tokens
        input_cost = (billable_prompt / 1_000_000) * self.input_per_million + cached_cost
        output_cost = (completion_tokens / 1_000_000) * self.output_per_million
        return round(input_cost, 6), round(output_cost, 6)


class MachinePrice(BaseModel):
    """Dollars per hour for the machine the model runs on.

    A laptop you already own is not free. It is the cheapest option and it has a
    number, and putting one on it is what lets you compare it with a hosted API
    instead of waving at "it's free".
    """

    label: str
    per_hour: float = Field(ge=0)

    def cost(self, seconds: float) -> float:
        return round((seconds / 3600.0) * self.per_hour, 6)


# Replace these with the figures you can currently verify, and move the date.
# The point of the lesson is the method, not these numbers.
HOSTED = TokenPrice(
    label="a hosted API, illustrative rates",
    input_per_million=3.00,
    output_per_million=15.00,
    cached_input_per_million=0.30,
)

LAPTOP = MachinePrice(label="the laptop you already have", per_hour=0.00)
SMALL_SERVER = MachinePrice(label="a small always-on CPU server", per_hour=0.05)
FREE = TokenPrice(label="local inference, no per-token charge",
                  input_per_million=0.0, output_per_million=0.0)
