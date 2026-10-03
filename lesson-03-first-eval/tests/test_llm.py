"""The stubs. These are what let the suite run with no model and no network."""
from __future__ import annotations

from src.llm import DEFAULT_MODEL, OllamaClient, OracleLLM, ScriptedLLM


class TestScriptedLLM:
    def test_returns_the_scripted_reply_for_a_matching_prompt(self) -> None:
        llm = ScriptedLLM({"C-1042": "Reserve is 1,234.00."})
        assert "1,234.00" in llm.complete("Question: reserve on C-1042?").text

    def test_falls_back_to_the_default(self) -> None:
        llm = ScriptedLLM({"C-1042": "x"}, default="no idea")
        assert llm.complete("Question: something else").text == "no idea"

    def test_is_deterministic(self) -> None:
        llm = ScriptedLLM({"a": "b"})
        assert llm.complete("a").text == llm.complete("a").text

    def test_records_calls_for_inspection(self) -> None:
        llm = ScriptedLLM()
        llm.complete("first")
        llm.complete("second")
        assert llm.calls == ["first", "second"]


class TestOracleLLM:
    def test_answers_when_the_fact_is_in_the_prompt(self) -> None:
        llm = OracleLLM({"What is the reserve on C-1?": "12,345.67"})
        prompt = ("Context:\n[C-1-NOT] Reserve set at 12,345.67.\n\n"
                  "Question: What is the reserve on C-1?")
        assert "12,345.67" in llm.complete(prompt).text

    def test_refuses_when_the_fact_is_absent(self) -> None:
        """This is the whole point of the oracle: it cannot rescue bad retrieval."""
        llm = OracleLLM({"What is the reserve on C-1?": "12,345.67"})
        prompt = "Context:\n[C-9-NOT] Something unrelated.\n\nQuestion: What is the reserve on C-1?"
        assert "does not contain" in llm.complete(prompt).text

    def test_tolerates_comma_and_space_differences(self) -> None:
        llm = OracleLLM({"q": "12,345.67"})
        assert "12,345.67" in llm.complete("Context: reserve 12345.67\n\nQuestion: q").text

    def test_unknown_question_is_refused(self) -> None:
        llm = OracleLLM({})
        assert "does not contain" in llm.complete("Question: anything").text


class TestOllamaClientConfiguration:
    """Constructed but never called. A test that hits the model is not a test."""

    def test_defaults_point_at_the_local_lab(self) -> None:
        client = OllamaClient()
        assert client.endpoint == "http://localhost:11434"
        assert client.name == DEFAULT_MODEL
        client.close()

    def test_trailing_slash_is_trimmed(self) -> None:
        client = OllamaClient(endpoint="http://localhost:11434/")
        assert client.endpoint == "http://localhost:11434"
        client.close()
