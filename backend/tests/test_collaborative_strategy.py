"""
Tests for the collaborative recommendation strategy (FR-506, FR-508, NFR-08, NFR-11).
Strategy tests build items directly; the integration test uses the database fixtures.
"""
import math
import uuid

from app.core.auth import get_password_hash
from app.modules.accounts.repository import AccountsRepository
from app.modules.content.schemas import ContentItemResponse, ContentItemCreate, CourseCreate, TopicCreate
from app.modules.content.service import ContentService
from app.modules.knowledge.schemas import InteractionEventCreate
from app.modules.knowledge.service import KnowledgeService
from app.modules.recommender.service import RecommenderService, clear_similarity_cache
from app.modules.recommender.strategies import STRATEGY_REGISTRY, CollaborativeStrategy, RuleBasedStrategy
from app.modules.recommender.strategies.base import LearnerContext
from app.modules.recommender.strategies.collaborative import compute_item_similarity

WEIGHTS = {"w1": 0.4, "w2": 0.3, "w3": 0.2, "w4": 0.1}


def make_item(topic_id, title="Item", difficulty=3) -> ContentItemResponse:
    return ContentItemResponse(
        content_id=uuid.uuid4(), topic_id=topic_id, title=title, type="video",
        difficulty=difficulty, duration=300, prerequisite_topic_ids=[],
    )


def make_ctx(done, similarity, weights=None) -> LearnerContext:
    return LearnerContext(
        user_id=uuid.uuid4(), mastery_map={}, completed_item_ids={i.content_id for i in done},
        dismissed_item_ids=set(), weights=weights or dict(WEIGHTS),
        overall_completion_rate=0.5, stretch=0.10, item_similarity=similarity,
    )


# ---- similarity table ------------------------------------------------------------------------

def test_fr508_cosine_similarity_known_values():
    completions = {"u1": {"A", "B"}, "u2": {"A", "B"}, "u3": {"A", "C"}}
    sim = compute_item_similarity(completions, min_support=1)
    assert math.isclose(sim["A"]["B"], 2 / math.sqrt(3 * 2))      # co=2, n(A)=3, n(B)=2
    assert math.isclose(sim["A"]["C"], 1 / math.sqrt(3 * 1))
    assert sim["B"]["A"] == sim["A"]["B"]                          # symmetric
    assert "C" not in sim["B"]                                     # never co-completed


def test_fr508_min_support_drops_single_coincidences():
    sim = compute_item_similarity({"u1": {"A", "B"}, "u2": {"A", "C"}, "u3": {"A", "B"}})
    assert "B" in sim["A"] and "C" not in sim["A"]                 # A-B seen twice, A-C once


def test_fr508_empty_input_gives_empty_table():
    assert compute_item_similarity({}) == {}


# ---- strategy --------------------------------------------------------------------------------

def test_fr508_item_completed_with_similar_items_ranks_higher():
    topic = uuid.uuid4()
    done = [make_item(topic) for _ in range(3)]
    liked, other = make_item(topic), make_item(topic)
    sim = {liked.content_id: {d.content_id: 0.9 for d in done}}
    ctx = make_ctx(done, sim)

    scored = {s.item.content_id: s for s in CollaborativeStrategy().score(ctx, [liked, other])}

    assert scored[liked.content_id].score > scored[other.content_id].score


def test_fr508_too_few_completions_equals_rule_based():
    topic = uuid.uuid4()
    done = [make_item(topic) for _ in range(2)]                    # below MIN_COMPLETIONS
    cands = [make_item(topic, difficulty=2), make_item(topic, difficulty=4)]
    ctx = make_ctx(done, {cands[0].content_id: {done[0].content_id: 1.0}})

    got = [(s.score, s.reason) for s in CollaborativeStrategy().score(ctx, cands)]
    want = [(s.score, s.reason) for s in RuleBasedStrategy().score(ctx, cands)]
    assert got == want


def test_fr508_no_similarity_data_equals_rule_based():
    topic = uuid.uuid4()
    done = [make_item(topic) for _ in range(4)]
    cands = [make_item(topic, difficulty=2)]
    for sim in (None, {}, {uuid.uuid4(): {uuid.uuid4(): 1.0}}):     # missing, empty, unrelated
        ctx = make_ctx(done, sim)
        assert [s.score for s in CollaborativeStrategy().score(ctx, cands)] == \
               [s.score for s in RuleBasedStrategy().score(ctx, cands)]


def test_nfr11_similar_learners_reason_when_it_dominates():
    topic = uuid.uuid4()
    done = [make_item(topic) for _ in range(3)]
    cand = make_item(topic)
    ctx = make_ctx(done, {cand.content_id: {d.content_id: 1.0 for d in done}},
                   weights={"w1": 0.0, "w2": 1.0, "w3": 0.0, "w4": 0.0, "alpha": 1.0})

    [item] = CollaborativeStrategy().score(ctx, [cand])

    assert item.dominant_factor == "similar_learners"
    assert item.reason == "Learners like you completed this"
    assert 0.0 <= item.score <= 1.0


def test_collaborative_registered_and_no_longer_a_stub():
    assert isinstance(STRATEGY_REGISTRY["collaborative"], CollaborativeStrategy)


# ---- integration: successful completions -> similarity -> recommendations ---------------------

def _learner(db, name):
    repo = AccountsRepository(db)
    user = repo.create_user(f"{name}_{uuid.uuid4().hex[:8]}@test.com", get_password_hash("pass123"), "learner")
    repo.record_consent(user.user_id)
    return user


def test_fr508_only_successful_completions_count_and_service_uses_them(client, db_session):
    clear_similarity_cache()
    content = ContentService(db_session)
    know = KnowledgeService(db_session)
    course = content.create_course(CourseCreate(title=f"CF {uuid.uuid4().hex[:6]}", description="x"))
    topic = content.create_topic(TopicCreate(course_id=course.course_id, name="Topic"))
    items = [
        content.create_content_item(ContentItemCreate(
            topic_id=topic.topic_id, title=f"Item {i}", type="video", difficulty=2, duration=200))
        for i in range(5)
    ]
    a, b, c, d, e = items

    # Three strong learners completed A, B and C together; one weak learner completed D and E.
    for n in range(3):
        u = _learner(db_session, f"strong{n}")
        know.repo.upsert_mastery(u.user_id, topic.topic_id, score=0.8, confidence=0.8)
        for it in (a, b, c):
            know.log_interaction_event(u.user_id, InteractionEventCreate(content_id=it.content_id, event_type="completed"))
    weak = _learner(db_session, "weak")
    know.repo.upsert_mastery(weak.user_id, topic.topic_id, score=0.1, confidence=0.8)
    for it in (d, e):
        know.log_interaction_event(weak.user_id, InteractionEventCreate(content_id=it.content_id, event_type="completed"))
    db_session.commit()

    successful = know.get_successful_completions(min_mastery=0.4)
    assert {frozenset(v) for v in successful.values()} == {frozenset({a.content_id, b.content_id, c.content_id})}
    assert weak.user_id not in successful                           # weak learner's completions excluded

    # A new learner who completed A, B and C is steered toward nothing new here, but the pipeline
    # must run end to end with the collaborative strategy and still return reasoned items.
    newbie = _learner(db_session, "newbie")
    know.repo.upsert_mastery(newbie.user_id, topic.topic_id, score=0.5, confidence=0.8)
    for it in (a, b, c):
        know.log_interaction_event(newbie.user_id, InteractionEventCreate(content_id=it.content_id, event_type="completed"))
    db_session.commit()

    res = RecommenderService(db_session).get_recommendations(
        user_id=newbie.user_id, course_id=course.course_id, strategy_name="collaborative")

    assert res.strategy_used == "collaborative"
    assert res.fallback_step is None
    assert len(res.items) > 0 and all(len(i.reason) > 5 for i in res.items)
    clear_similarity_cache()
