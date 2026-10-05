"""Retrieve, then ask. The smallest system that could answer a claims question.

Two moving parts, which is exactly why this lesson can tell them apart: keyword
search picks the documents, and the model reads them. When the answer is wrong,
one of those two failed, and the eval says which.
"""
from __future__ import annotations

from src.llm import LLMClient
from src.models import Completion, Document
from src.search import KeywordIndex

PROMPT = """You are helping a claims adjuster at an insurance company.
Answer using only the context below. If the answer is not in the context, say
"The context does not contain the answer." Answer in one short sentence.

Context:
{context}

Question: {question}
Answer:"""


class Answerer:
    """Keyword retrieval feeding a model."""

    def __init__(self, documents: list[Document], client: LLMClient, top_k: int = 5) -> None:
        self.index = KeywordIndex(documents)
        self.client = client
        self.top_k = top_k
        self._text = {d.doc_id: d.text for d in documents}

    def retrieve(self, question: str) -> list[str]:
        """Document ids the current search puts in front of the model."""
        return [h.doc_id for h in self.index.search(question, top_k=self.top_k)]

    def answer(self, question: str) -> tuple[Completion, list[str]]:
        doc_ids = self.retrieve(question)
        context = "\n\n".join(f"[{d}] {self._text[d]}" for d in doc_ids)
        prompt = PROMPT.format(context=context or "(no documents found)", question=question)
        return self.client.complete(prompt), doc_ids
