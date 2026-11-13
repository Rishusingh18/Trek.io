
import uuid
from unittest.mock import patch

import numpy as np

from app.modules.content.schemas import ContentItemResponse
from app.modules.recommender.strategies.base import LearnerContext
from app.modules.recommender.strategies.embeddings import EmbeddingsStrategy


def make_item(title, topic_id=None):
    return ContentItemResponse(
        content_id=uuid.uuid4(),
        topic_id=topic_id or uuid.uuid4(),
        title=title,
        type="video",
        difficulty=3,
        duration=300,
        prerequisite_topic_ids=[],
    )


def make_context(completed_items=None):
    completed_items = completed_items or []
    return LearnerContext(
        user_id=uuid.uuid4(),
        mastery_map={},
        completed_item_ids={item.content_id for item in completed_items},
        dismissed_item_ids=set(),
        weights={"w1": 0.4, "w2": 0.3, "w3": 0.2, "w4": 0.1},
        completed_items=completed_items,
    )


def test_embeddings_returns_rule_scores_without_history():
    candidate = make_item("Introduction to Python")
    ctx = make_context()

    result = EmbeddingsStrategy().score(ctx, [candidate])

    assert len(result) == 1
    assert result[0].item.content_id == candidate.content_id
    assert 0.0 <= result[0].score <= 1.0


def test_embeddings_ranks_semantically_similar_content_higher():
    completed = make_item("Python programming fundamentals")
    similar = make_item("Introduction to Python coding")
    unrelated = make_item("Basics of organic chemistry")
    ctx = make_context([completed])

    # History embedding is [1, 0]. Similar candidate aligns with it;
    # unrelated candidate is orthogonal to it.
    fake_model = type(
        "FakeModel",
        (),
        {
            "encode": lambda self, texts, **kwargs: np.array(
                [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
            )
        },
    )()

    with patch(
        "app.modules.recommender.strategies.embeddings._load_model",
        return_value=fake_model,
    ):
        results = EmbeddingsStrategy().score(ctx, [similar, unrelated])

    scores = {result.item.content_id: result.score for result in results}
    assert scores[similar.content_id] > scores[unrelated.content_id]


def test_embeddings_empty_candidates_returns_empty_list():
    assert EmbeddingsStrategy().score(make_context(), []) == []
