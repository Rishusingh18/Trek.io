"""
Tests for the embeddings recommendation strategy (FR-506, FR-507, NFR-08, NFR-11).
Unit tests build items directly, so they need no database.
"""
import uuid

from app.modules.content.schemas import ContentItemResponse
from app.modules.recommender.strategies import STRATEGY_REGISTRY, EmbeddingsStrategy, RuleBasedStrategy
from app.modules.recommender.strategies.base import LearnerContext

WEIGHTS = {"w1": 0.4, "w2": 0.3, "w3": 0.2, "w4": 0.1}


def make_item(title: str, topic_id: uuid.UUID, difficulty: int = 3, type_: str = "article") -> ContentItemResponse:
    return ContentItemResponse(
        content_id=uuid.uuid4(), topic_id=topic_id, title=title, type=type_,
        difficulty=difficulty, duration=300, prerequisite_topic_ids=[],
    )


def make_ctx(catalog, completed=(), weights=None) -> LearnerContext:
    return LearnerContext(
        user_id=uuid.uuid4(),
        mastery_map={},                      # same topic mastery for every item, so only similarity differs
        completed_item_ids={i.content_id for i in completed},
        dismissed_item_ids=set(),
        weights=weights or dict(WEIGHTS),
        overall_completion_rate=0.5,
        stretch=0.10,
        catalog=list(catalog),
    )


def test_fr507_similar_to_completed_ranks_higher():
    topic = uuid.uuid4()
    done = make_item("Python loops and iteration", topic)
    similar = make_item("Advanced Python loops", topic)
    unrelated = make_item("Database indexing basics", topic)
    ctx = make_ctx([done, similar, unrelated], completed=[done])

    scored = {s.item.content_id: s for s in EmbeddingsStrategy().score(ctx, [similar, unrelated])}

    assert scored[similar.content_id].score > scored[unrelated.content_id].score


def test_fr507_cold_start_equals_rule_based():
    topic = uuid.uuid4()
    items = [make_item("Python loops", topic), make_item("Database indexing", topic, difficulty=2)]
    ctx = make_ctx(items, completed=[])

    emb = EmbeddingsStrategy().score(ctx, items)
    rules = RuleBasedStrategy().score(ctx, items)

    assert [(s.score, s.reason) for s in emb] == [(s.score, s.reason) for s in rules]


def test_nfr11_similarity_reason_when_similarity_dominates():
    topic = uuid.uuid4()
    done = make_item("Python loops and iteration", topic)
    similar = make_item("Python loops and iteration practice", topic)
    # gap/ready/eng weights zero so the similarity term must be the dominant factor
    weights = {"w1": 0.0, "w2": 1.0, "w3": 0.0, "w4": 0.0, "alpha": 1.0}
    ctx = make_ctx([done, similar], completed=[done], weights=weights)

    [item] = EmbeddingsStrategy().score(ctx, [similar])

    assert item.dominant_factor == "similar"
    assert item.reason == "Similar to content you finished"


def test_scores_stay_in_unit_interval_and_every_item_has_a_reason():
    topic = uuid.uuid4()
    items = [make_item(f"Topic {i} lesson on python", topic, difficulty=1 + i % 5) for i in range(8)]
    ctx = make_ctx(items, completed=items[:2])

    for s in EmbeddingsStrategy().score(ctx, items[2:]):
        assert 0.0 <= s.score <= 1.0
        assert len(s.reason) > 5


def test_works_without_catalog_in_context():
    """ctx.catalog is optional; completed items missing from it simply give no profile."""
    topic = uuid.uuid4()
    items = [make_item("Python loops", topic), make_item("Python functions", topic)]
    ctx = make_ctx([], completed=[])
    ctx.completed_item_ids = {items[0].content_id}

    scored = EmbeddingsStrategy().score(ctx, items)

    assert len(scored) == 2


def test_embeddings_registered_and_no_longer_a_stub():
    assert isinstance(STRATEGY_REGISTRY["embeddings"], EmbeddingsStrategy)
