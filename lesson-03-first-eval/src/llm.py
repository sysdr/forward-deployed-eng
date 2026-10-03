"""Talking to a model, and not talking to one.

Three implementations of the same tiny interface:

  OllamaClient  a real model running on your machine. Free, offline, no key.
  ScriptedLLM   fixed replies. Used by tests, so the suite never needs a model.
  OracleLLM     answers correctly whenever the answer is actually in the prompt,
                and admits it cannot otherwise.

OracleLLM is the interesting one. Running the eval against it tells you the best
score any model could achieve given what retrieval put in front of it. If that
ceiling is low, the model is not your problem.
"""
from __future__ import annotations

import os
import re
import time
from typing import Protocol

import httpx

from src.models import Completion

DEFAULT_ENDPOINT = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:8b"


def resolve_endpoint(endpoint: str | None = None) -> str:
    """Prefer an explicit endpoint, then OLLAMA_HOST, then the local lab default."""
    chosen = endpoint or os.environ.get("OLLAMA_HOST") or DEFAULT_ENDPOINT
    return chosen.rstrip("/")


class LLMClient(Protocol):
    """Everything the rest of the lesson knows about a model."""

    name: str

    def complete(self, prompt: str) -> Completion: ...


class OllamaClient:
    """Talks to an Ollama host. Set OLLAMA_HOST for a remote machine."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 120.0,
        num_predict: int = 96,
    ) -> None:
        self.name = model
        self.endpoint = endpoint.rstrip("/")
        self.num_predict = num_predict
        self._client = httpx.Client(timeout=timeout)

    def complete(self, prompt: str) -> Completion:
        started = time.monotonic()
        response = self._client.post(
            f"{self.endpoint}/api/generate",
            json={
                "model": self.name,
                "prompt": prompt,
                "stream": False,
                # Temperature zero so a rerun of the eval is comparable to the
                # last one. Sampling turns your eval into a coin toss.
                "options": {"temperature": 0.0, "num_predict": self.num_predict},
            },
        )
        response.raise_for_status()
        body = response.json()
        return Completion(
            text=body.get("response", "").strip(),
            prompt_tokens=int(body.get("prompt_eval_count", 0)),
            completion_tokens=int(body.get("eval_count", 0)),
            seconds=round(time.monotonic() - started, 3),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OllamaClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class ScriptedLLM:
    """Fixed replies, chosen by the first script key found in the prompt.

    This is what every test in this lesson uses. A test that calls a real model
    is measuring the model, not your code.
    """

    def __init__(
        self, script: dict[str, str] | None = None, default: str = "I don't know."
    ) -> None:
        self.name = "scripted"
        self.script = script or {}
        self.default = default
        self.calls: list[str] = []

    def complete(self, prompt: str) -> Completion:
        self.calls.append(prompt)
        for key, reply in self.script.items():
            if key in prompt:
                return Completion(text=reply, prompt_tokens=len(prompt.split()),
                                  completion_tokens=len(reply.split()), seconds=0.0)
        return Completion(text=self.default, prompt_tokens=len(prompt.split()),
                          completion_tokens=len(self.default.split()), seconds=0.0)


class OracleLLM:
    """A model that is right whenever the answer is in front of it.

    It does not read, reason or guess. It checks whether the expected fact is
    present in the prompt and repeats it if so. The score it produces is the
    ceiling your retrieval imposes on every real model.
    """

    def __init__(self, expected_by_question: dict[str, str]) -> None:
        self.name = "oracle"
        self._expected = expected_by_question

    def complete(self, prompt: str) -> Completion:
        question = ""
        m = re.search(r"Question:\s*(.+)", prompt)
        if m:
            question = m.group(1).strip()
        expected = self._expected.get(question)
        if expected and _loosely_present(expected, prompt):
            return Completion(text=expected, prompt_tokens=len(prompt.split()),
                              completion_tokens=len(expected.split()))
        return Completion(text="The context does not contain the answer.",
                          prompt_tokens=len(prompt.split()), completion_tokens=7)


def _loosely_present(needle: str, haystack: str) -> bool:
    """Substring match that ignores case, commas and spacing."""
    def norm(s: str) -> str:
        return re.sub(r"[,\s]", "", s).lower()

    return norm(needle) in norm(haystack)
