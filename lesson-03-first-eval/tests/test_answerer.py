"""Retrieval feeds the model. These tests prove what actually reaches it."""
from __future__ import annotations

from src.answerer import Answerer
from src.llm import ScriptedLLM


class TestRetrieval:
    def test_identifier_question_retrieves_that_claim(self, documents) -> None:
        a = Answerer(documents, ScriptedLLM())
        assert any(d.startswith("C-1042") for d in a.retrieve("reserve on claim C-1042?"))

    def test_top_k_is_respected(self, documents) -> None:
        assert len(Answerer(documents, ScriptedLLM(), top_k=3).retrieve("claim C-1042")) <= 3


class TestPromptConstruction:
    def test_prompt_carries_the_retrieved_documents(self, documents) -> None:
        llm = ScriptedLLM()
        a = Answerer(documents, llm)
        _, doc_ids = a.answer("What is the reserve amount on claim C-1042?")
        prompt = llm.calls[0]
        for doc_id in doc_ids:
            assert f"[{doc_id}]" in prompt

    def test_prompt_states_the_question(self, documents) -> None:
        llm = ScriptedLLM()
        Answerer(documents, llm).answer("Who is the adjuster handling claim C-1005?")
        assert "Question: Who is the adjuster handling claim C-1005?" in llm.calls[0]

    def test_prompt_instructs_a_refusal(self, documents) -> None:
        """Without this line the model guesses, and a guess in a claim file is worse
        than a blank."""
        llm = ScriptedLLM()
        Answerer(documents, llm).answer("anything")
        assert "does not contain the answer" in llm.calls[0]

    def test_question_matching_nothing_still_produces_a_prompt(self, documents) -> None:
        """A real failure: retrieval returns nothing and the system must not crash."""
        llm = ScriptedLLM()
        completion, doc_ids = Answerer(documents, llm).answer("xylophone quantum ferret")
        assert doc_ids == []
        assert "(no documents found)" in llm.calls[0]
        assert completion.text
