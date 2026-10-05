"""The customer's current process, in code.

Meridian's adjusters use the document store's built-in keyword search. This is
that search: tokenise, drop stopwords, weight terms by how rare they are, rank.

It is not a strawman. Inverse document frequency is what most enterprise
document stores actually do, and on identifier lookups it is genuinely hard to
beat. Measuring it honestly is what makes the later comparison credible.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from src.models import Document, RankedHit

# Ordinary English stopwords, plus two domain words that appear in nearly every
# document here and therefore carry no signal at all.
STOPWORDS: frozenset[str] = frozenset(
    """
    a an the is are was were be been being of on in at to for from with by and or
    what which who whom whose how when where why did does do has have had
    this that these those it its as
    claim policy
    """.split()
)

_TOKEN = re.compile(r"[a-z0-9][a-z0-9\-]*")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens, stopwords removed.

    Hyphens are kept so that `c-1042` survives as one token. Splitting it would
    make every claim identifier collide with every other one.
    """
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


class KeywordIndex:
    """An in-memory TF-IDF index. No service, no network, no cost."""

    def __init__(self, documents: list[Document]) -> None:
        if not documents:
            raise ValueError("Cannot build an index over zero documents")
        self.documents = documents
        self._tokens: dict[str, Counter[str]] = {
            d.doc_id: Counter(tokenize(d.text)) for d in documents
        }
        n = len(documents)
        appearances: Counter[str] = Counter()
        for counts in self._tokens.values():
            appearances.update(counts.keys())
        # Smoothed IDF. Rare terms — identifiers especially — dominate the score.
        self._idf: dict[str, float] = {
            term: math.log((n + 1) / (df + 1)) + 1.0 for term, df in appearances.items()
        }

    def search(self, query: str, top_k: int = 5) -> list[RankedHit]:
        """Return the top_k documents by TF-IDF score, highest first."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        q_terms = tokenize(query)
        if not q_terms:
            return []
        scored: list[RankedHit] = []
        for doc_id, counts in self._tokens.items():
            total = sum(counts.values()) or 1
            score = 0.0
            for term in q_terms:
                tf = counts.get(term, 0)
                if tf:
                    score += (tf / total) * self._idf.get(term, 0.0)
            if score > 0:
                scored.append(RankedHit(doc_id=doc_id, score=score))
        # Sort by score, then doc_id, so ties are broken deterministically and
        # a rerun of the baseline is byte-comparable with the last one.
        scored.sort(key=lambda h: (-h.score, h.doc_id))
        return scored[:top_k]
