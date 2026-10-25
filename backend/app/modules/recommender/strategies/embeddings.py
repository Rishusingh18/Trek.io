"""
Embeddings-based recommendation strategy (FR-506, FR-507).

Content similarity is computed from each item's text (title and type, plus description and tags
when the content model carries them) using TF-IDF vectors and cosine similarity. A learner
profile is the average vector of the items they completed. The similarity is blended into the
fit(i) term of the SRS section 7.2 formula:

    fit'(i) = (1 - alpha) * fit(i) + alpha * sim(i)
    S(i)    = w1*gap + w2*fit' + w3*ready + w4*eng

A learner with no completed items has no profile, so the rule-based scores are returned unchanged.
The vectors are plain Python (no extra dependency) and can later be replaced by a sentence-embedding
model without changing the strategy interface.
"""
import math
import re
from collections import Counter
from functools import lru_cache
from typing import Dict, List, Tuple

from app.modules.content.schemas import ContentItemResponse
from app.modules.recommender.strategies.base import RecommendationStrategy, LearnerContext, ScoredItem
from app.modules.recommender.strategies.rules import RuleBasedStrategy

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are as at be by for from how in into is it of on or the to with your you what why".split()
)
DEFAULT_ALPHA = 0.5
SIMILAR_REASON = "Similar to content you finished"

SparseVec = Dict[str, float]


def item_text(item: ContentItemResponse) -> str:
    """Text used for similarity. description and tags are used once the content model has them."""
    parts = [item.title, item.type]
    parts.append(getattr(item, "description", None) or "")
    parts.append(" ".join(getattr(item, "tags", None) or []))
    return " ".join(p for p in parts if p)


def tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN.findall(text.lower()) if len(t) > 1 and t not in _STOPWORDS]


def _normalize(vec: SparseVec) -> SparseVec:
    norm = math.sqrt(sum(v * v for v in vec.values()))
    return {k: v / norm for k, v in vec.items()} if norm else {}


@lru_cache(maxsize=16)
def _build_index(docs: Tuple[Tuple[str, str], ...]) -> Dict[str, SparseVec]:
    """docs: ((content_id, text), ...) -> {content_id: L2-normalised TF-IDF vector}. Cached per catalog."""
    tokenized = {cid: tokenize(text) for cid, text in docs}
    n = len(tokenized)
    df: Counter = Counter()
    for toks in tokenized.values():
        df.update(set(toks))
    idf = {term: math.log((1 + n) / (1 + count)) + 1.0 for term, count in df.items()}
    index: Dict[str, SparseVec] = {}
    for cid, toks in tokenized.items():
        tf = Counter(toks)
        index[cid] = _normalize({t: c * idf[t] for t, c in tf.items()})
    return index


def _cosine(a: SparseVec, b: SparseVec) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


class EmbeddingsStrategy(RecommendationStrategy):
    name: str = "embeddings"

    def __init__(self) -> None:
        self._rules = RuleBasedStrategy()

    def score(self, ctx: LearnerContext, candidates: List[ContentItemResponse]) -> List[ScoredItem]:
        """FR-507: rank candidates by rule terms with content similarity blended into fit(i)."""
        # The index covers the whole catalog, because candidates may exclude completed items.
        catalog = list(ctx.catalog or [])
        known = {i.content_id for i in catalog}
        catalog += [c for c in candidates if c.content_id not in known]
        index = _build_index(tuple(sorted((str(i.content_id), item_text(i)) for i in catalog)))

        # Learner profile: sum of the completed items' vectors, re-normalised.
        profile: SparseVec = {}
        for cid in ctx.completed_item_ids:
            for term, val in index.get(str(cid), {}).items():
                profile[term] = profile.get(term, 0.0) + val
        profile = _normalize(profile)
        if not profile:
            return self._rules.score(ctx, candidates)  # cold start: nothing to compare against

        w1 = ctx.weights.get("w1", 0.4)
        w2 = ctx.weights.get("w2", 0.3)
        w3 = ctx.weights.get("w3", 0.2)
        w4 = ctx.weights.get("w4", 0.1)
        alpha = min(1.0, max(0.0, ctx.weights.get("alpha", DEFAULT_ALPHA)))
        templates = ctx.templates or {}

        scored: List[ScoredItem] = []
        for item in candidates:
            t = self._rules.terms(ctx, item)
            sim = max(0.0, min(1.0, _cosine(profile, index.get(str(item.content_id), {}))))
            weighted = {
                "gap": w1 * t["gap"],
                "fit": w2 * (1 - alpha) * t["fit"],
                "similar": w2 * alpha * sim,
                "ready": w3 * t["ready"],
                "eng": w4 * t["eng"],
            }
            total = max(0.0, min(1.0, sum(weighted.values())))
            dominant = max(weighted, key=weighted.get)
            if dominant == "similar":
                reason = templates.get("similar", SIMILAR_REASON)
            else:
                reason = templates.get(dominant, RuleBasedStrategy.DEFAULT_TEMPLATES.get(dominant, "Recommended for you"))
            scored.append(ScoredItem(item=item, score=total, dominant_factor=dominant, reason=reason))
        return scored
