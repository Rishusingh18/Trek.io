"""
Unit tests and acceptance tests for Experiments Module and Background Worker.
Traces to FR-801 to FR-807, FR-305, FR-307, NFR-02, NFR-13, and UC-05.
"""
import uuid
import math
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.auth import create_access_token, get_password_hash
from app.modules.accounts.repository import AccountsRepository
from app.modules.content.service import ContentService
from app.modules.content.schemas import CourseCreate, TopicCreate, ContentItemCreate
from app.modules.knowledge.service import KnowledgeService
from app.modules.knowledge.schemas import InteractionEventCreate
from app.modules.experiments.service import ExperimentsService
from app.modules.experiments.schemas import ExperimentCreate, ArmCreate
from app.modules.recommender.service import RecommenderService
from app.worker.locks import WorkerLock
from app.worker.jobs import (
    run_mastery_decay_job,
    run_rollup_job,
    run_experiment_metrics_job,
    run_guardrails_check,
    run_retention_job,
)
from app.db.models.experiments import Experiment, ExperimentAssignment
from app.db.models.rollups import ExperimentMetricsRollup, ClassTopicMasteryRollup


def setup_base_data(db_session: Session):
    accounts_repo = AccountsRepository(db_session)
    content_svc = ContentService(db_session)

    suffix = uuid.uuid4().hex[:6]

    admin = accounts_repo.create_user(f"admin_{suffix}@test.com", get_password_hash("pass123"), "administrator")
    learner = accounts_repo.create_user(f"learner_{suffix}@test.com", get_password_hash("pass123"), "learner")
    accounts_repo.record_consent(learner.user_id)

    course = content_svc.create_course(CourseCreate(title=f"Course {suffix}", description="Test course"))
    topic = content_svc.create_topic(TopicCreate(course_id=course.course_id, name="Foundations"))
    content = content_svc.create_content_item(ContentItemCreate(
        topic_id=topic.topic_id,
        title="Intro Lesson",
        type="video",
        difficulty=1,
        duration=300
    ))

    db_session.commit()

    return {
        "admin": admin,
        "learner": learner,
        "course": course,
        "topic": topic,
        "content": content,
        "admin_token": create_access_token(admin.user_id, role="administrator"),
        "learner_token": create_access_token(learner.user_id, role="learner"),
    }


# ==================== Test 1: Admin Creates Experiment (FR-801) ====================
def test_fr801_admin_creates_experiment(client: TestClient, db_session: Session):
    """
    FR-801: Admin creates an experiment with arms, allocation split, primary metric, start/stop dates.
    Learner receives 403 Forbidden.
    """
    data = setup_base_data(db_session)
    admin_auth = {"Authorization": f"Bearer {data['admin_token']}"}
    learner_auth = {"Authorization": f"Bearer {data['learner_token']}"}

    payload = {
        "name": f"Ranking Strategy Test {uuid.uuid4().hex[:4]}",
        "primary_metric": "post_test_gain",
        "arms": [
            {"name": "Control (Rule-Based)", "strategy": "rule_based", "parameters": {}, "allocation_share": 0.5},
            {"name": "Variant (Embeddings)", "strategy": "embeddings", "parameters": {"threshold": 0.75}, "allocation_share": 0.5}
        ],
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    }

    # Learner attempt -> 403
    res_l = client.post("/v1/admin/experiments", json=payload, headers=learner_auth)
    assert res_l.status_code == 403

    # Admin attempt -> 200
    res_a = client.post("/v1/admin/experiments", json=payload, headers=admin_auth)
    assert res_a.status_code == 200
    res_json = res_a.json()
    assert res_json["name"] == payload["name"]
    assert res_json["status"] == "active"
    assert len(res_json["arms"]) == 2
    assert res_json["arms"][0]["allocation_share"] == 0.5


# ==================== Test 2: Persistent Assignment (FR-802, UC-05) ====================
def test_fr802_learner_stays_in_one_arm_persistently(client: TestClient, db_session: Session):
    """
    FR-802, UC-05: A learner is assigned to one arm at random and keeps that assignment
    fixed permanently for the entire duration of the experiment.
    """
    data = setup_base_data(db_session)
    exp_svc = ExperimentsService(db_session)

    exp = exp_svc.create_experiment(ExperimentCreate(
        name=f"Persistent Test {uuid.uuid4().hex[:4]}",
        primary_metric="completion_rate_8w",
        arms=[
            ArmCreate(name="Arm A", strategy="rule_based", allocation_share=0.5),
            ArmCreate(name="Arm B", strategy="embeddings", allocation_share=0.5),
        ]
    ))

    # First lookup: draws arm at random and persists in experiment_assignments
    info_1 = exp_svc.get_learner_arm_and_strategy(data["learner"].user_id)
    assert info_1 is not None
    arm_id_1 = info_1["arm_id"]
    exp_id_1 = info_1["experiment_id"]
    assert exp_id_1 == exp.experiment_id

    # Second lookup: must return the exact same arm_id
    info_2 = exp_svc.get_learner_arm_and_strategy(data["learner"].user_id)
    assert info_2 is not None
    assert info_2["arm_id"] == arm_id_1

    # Third lookup via RecommenderService: must also preserve the arm_id
    rec_svc = RecommenderService(db_session)
    recs = rec_svc.get_recommendations(data["learner"].user_id, data["course"].course_id)
    assert recs.arm_id == arm_id_1

    # Verify directly in experiment_assignments table
    assignment = db_session.execute(
        select(ExperimentAssignment).where(
            ExperimentAssignment.user_id == data["learner"].user_id,
            ExperimentAssignment.experiment_id == exp.experiment_id
        )
    ).scalar_one_or_none()
    assert assignment is not None
    assert assignment.arm_id == arm_id_1


# ==================== Test 3: 50/50 Split is Roughly Even (FR-802, UC-05) ====================
def test_fr802_50_50_split_distribution(db_session: Session):
    """
    FR-802, UC-05: Given a 50/50 split, random assignments across many learners are
    roughly even (binomial test within statistical tolerance).
    """
    exp_svc = ExperimentsService(db_session)
    suffix = uuid.uuid4().hex[:4]

    exp = exp_svc.create_experiment(ExperimentCreate(
        name=f"Split Distribution Test {suffix}",
        primary_metric="post_test_gain",
        arms=[
            ArmCreate(name="Control", strategy="rule_based", allocation_share=0.5),
            ArmCreate(name="Treatment", strategy="embeddings", allocation_share=0.5),
        ]
    ))

    arm_a_id = exp.arms[0].arm_id
    arm_b_id = exp.arms[1].arm_id

    arm_a_count = 0
    arm_b_count = 0
    num_learners = 100

    for _ in range(num_learners):
        test_uid = uuid.uuid4()
        chosen = exp_svc.get_learner_arm_and_strategy(test_uid)
        assert chosen is not None
        if chosen["arm_id"] == arm_a_id:
            arm_a_count += 1
        elif chosen["arm_id"] == arm_b_id:
            arm_b_count += 1

    assert arm_a_count + arm_b_count == num_learners
    # For N=100 and p=0.5, mean=50, std=5. 3-sigma range is [35, 65]
    assert 35 <= arm_a_count <= 65, f"Arm A count {arm_a_count} outside expected 50/50 range [35, 65]"
    assert 35 <= arm_b_count <= 65, f"Arm B count {arm_b_count} outside expected 50/50 range [35, 65]"


# ==================== Test 4: With No Active Experiment, Default Strategy Used ====================
def test_no_active_experiment_uses_default_strategy(db_session: Session):
    """
    SRS & Architecture: With no experiment running, the default strategy (rule_based) is used.
    """
    from sqlalchemy import update
    exp_svc = ExperimentsService(db_session)
    test_uid = uuid.uuid4()

    # Pause any running experiments to test no-experiment condition
    db_session.execute(update(Experiment).where(Experiment.status == "active").values(status="paused"))
    db_session.commit()

    arm_info = exp_svc.get_learner_arm_and_strategy(test_uid)
    assert arm_info is None


# ==================== Test 5: Guardrail Breach Auto-Pauses Experiment (FR-806, UC-05) ====================
def test_fr806_guardrail_breach_auto_pauses_experiment(db_session: Session):
    """
    FR-806, UC-05: If dropout or quiz abandonment worsens by more than 5% (0.05),
    the worker automatically pauses the experiment.
    """
    exp_svc = ExperimentsService(db_session)
    suffix = uuid.uuid4().hex[:4]

    exp = exp_svc.create_experiment(ExperimentCreate(
        name=f"Guardrail Test {suffix}",
        primary_metric="post_test_gain",
        arms=[
            ArmCreate(name="Control", strategy="rule_based", allocation_share=0.5),
            ArmCreate(name="Treatment", strategy="embeddings", allocation_share=0.5),
        ]
    ))
    arm_ctrl = exp.arms[0]
    arm_treat = exp.arms[1]

    # Pre-populate metrics rollups where Treatment dropout worsened by 7% (0.07 > 0.05 breach)
    exp_svc.repo.upsert_experiment_metrics_rollup(
        experiment_id=exp.experiment_id,
        arm_id=arm_ctrl.arm_id,
        acceptance_rate=0.40,
        completion_rate_8w=0.60,
        post_test_gain=0.15,
        sample_size=150,
        guardrail_dropout_rate=0.03,
        guardrail_abandonment_rate=0.02
    )
    exp_svc.repo.upsert_experiment_metrics_rollup(
        experiment_id=exp.experiment_id,
        arm_id=arm_treat.arm_id,
        acceptance_rate=0.45,
        completion_rate_8w=0.55,
        post_test_gain=0.18,
        sample_size=150,
        guardrail_dropout_rate=0.11,  # 0.11 - 0.03 = 0.08 > 0.05 breach!
        guardrail_abandonment_rate=0.02
    )

    # Run guardrails check worker job
    paused = run_guardrails_check(db_session)
    assert exp.experiment_id in paused

    # Verify status in database
    exp_orm = db_session.execute(select(Experiment).where(Experiment.experiment_id == exp.experiment_id)).scalar_one()
    assert exp_orm.status == "paused"


# ==================== Test 6: Precomputed Results & 200-Learner Minimum (FR-804, FR-805) ====================
def test_fr804_fr805_experiment_results_and_200_sample_check(client: TestClient, db_session: Session):
    """
    FR-804, FR-805, PRD section 7:
    GET /v1/admin/experiments/{id}/results reads stored metrics only (NFR-02),
    reports 95% confidence intervals, and checks against the 200-learners-per-arm minimum.
    """
    data = setup_base_data(db_session)
    exp_svc = ExperimentsService(db_session)
    admin_auth = {"Authorization": f"Bearer {data['admin_token']}"}

    exp = exp_svc.create_experiment(ExperimentCreate(
        name=f"Results Test {uuid.uuid4().hex[:4]}",
        primary_metric="post_test_gain",
        arms=[
            ArmCreate(name="Control", strategy="rule_based", allocation_share=0.5),
            ArmCreate(name="Treatment", strategy="embeddings", allocation_share=0.5),
        ]
    ))
    arm_ctrl = exp.arms[0]
    arm_treat = exp.arms[1]

    # Arm 1 has 150 (< 200), Arm 2 has 250 (>= 200)
    exp_svc.repo.upsert_experiment_metrics_rollup(
        experiment_id=exp.experiment_id,
        arm_id=arm_ctrl.arm_id,
        acceptance_rate=0.35,
        completion_rate_8w=0.50,
        post_test_gain=0.10,
        sample_size=150,
        guardrail_dropout_rate=0.02,
        guardrail_abandonment_rate=0.01
    )
    exp_svc.repo.upsert_experiment_metrics_rollup(
        experiment_id=exp.experiment_id,
        arm_id=arm_treat.arm_id,
        acceptance_rate=0.48,
        completion_rate_8w=0.62,
        post_test_gain=0.22,
        sample_size=250,
        guardrail_dropout_rate=0.03,
        guardrail_abandonment_rate=0.01
    )

    res = client.get(f"/v1/admin/experiments/{exp.experiment_id}/results", headers=admin_auth)
    assert res.status_code == 200
    body = res.json()
    assert body["experiment_id"] == str(exp.experiment_id)
    assert body["total_learners"] == 400
    assert body["meets_minimum_sample_size_all_arms"] is False  # Because Arm 1 has 150 < 200

    metrics = {m["arm_id"]: m for m in body["arms_metrics"]}
    ctrl_m = metrics[str(arm_ctrl.arm_id)]
    treat_m = metrics[str(arm_treat.arm_id)]

    assert ctrl_m["meets_min_sample_size"] is False
    assert treat_m["meets_min_sample_size"] is True
    assert "lower" in treat_m["acceptance_rate_ci"]
    assert "upper" in treat_m["acceptance_rate_ci"]
    assert treat_m["acceptance_rate_ci"]["lower"] <= 0.48 <= treat_m["acceptance_rate_ci"]["upper"]


# ==================== Test 7: Mastery Decay Worker Job (FR-305) ====================
def test_fr305_mastery_decay_job(db_session: Session):
    """
    FR-305: Decay mastery for idle topics: m_new = m_last * exp(-lambda * days).
    For lambda=0.01 and days=10: m = 0.80 * exp(-0.1) ~ 0.7239.
    """
    data = setup_base_data(db_session)
    k_svc = KnowledgeService(db_session)

    # Set mastery to 0.80 with timestamp 10 days in the past
    past_date = datetime.now(timezone.utc) - timedelta(days=10)
    score_row = k_svc.repo.upsert_mastery(data["learner"].user_id, data["topic"].topic_id, score=0.80, confidence=0.9)
    score_row.updated_at = past_date
    db_session.commit()

    # Run mastery decay worker job
    decayed = run_mastery_decay_job(db_session)
    assert decayed >= 1

    db_session.refresh(score_row)
    from app.core.config_client import ConfigClient
    decay_cfg = ConfigClient(db_session).get("mastery_parameters", {"decay_rate": 0.01})
    lam = float(decay_cfg.get("decay_rate", 0.01))
    expected_decay = 0.80 * math.exp(-lam * 10.0)
    assert math.isclose(score_row.score, expected_decay, abs_tol=1e-2)


# ==================== Test 8: Worker Redis Distributed Locking ====================
def test_worker_redis_distributed_locking():
    """
    Architecture Worker: Worker jobs are claimed by one worker at a time via Redis distributed lock.
    """
    job_name = f"test_job_{uuid.uuid4().hex[:6]}"
    lock1 = WorkerLock(job_name=job_name, ttl_seconds=10, worker_id="worker-A")
    lock2 = WorkerLock(job_name=job_name, ttl_seconds=10, worker_id="worker-B")

    # Worker 1 acquires
    assert lock1.acquire() is True

    # Worker 2 attempts same job -> rejected
    assert lock2.acquire() is False

    # Worker 1 releases
    lock1.release()

    # Worker 2 attempts again -> acquired
    assert lock2.acquire() is True
    lock2.release()
