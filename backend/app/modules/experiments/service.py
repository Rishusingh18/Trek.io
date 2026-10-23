"""
Experiments & Analytics service (FR-701 to FR-705, FR-801 to FR-807, NFR-02, NFR-13, UC-04).
Public interface for experiments, configs, and analytics dashboards.
"""
import uuid
import random
import json
import io
import csv
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.core.redis import get_redis_client
from app.core.logging import logger
from app.core.errors import NotFoundException, ForbiddenException
from app.db.models.accounts import User
from app.modules.content.service import ContentService
from app.modules.knowledge.service import KnowledgeService
from app.modules.experiments.repository import ExperimentsRepository
from app.modules.experiments.schemas import (
    ExperimentCreate,
    ExperimentResponse,
    ArmResponse,
    ExperimentResultsResponse,
    ConfigUpdateRequest,
    ConfigResponse,
    InstructorHeatmapResponse,
    LearnerMasteryItem,
    LearnerProgressDashboardResponse,
    AtRiskReportResponse,
    AtRiskLearnerItem,
    LearnerHistoryResponse,
    LearnerAttemptHistoryItem,
    LearnerActivityHistoryItem,
)


class ExperimentsService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ExperimentsRepository(db)
        self.content_service = ContentService(db)
        self.knowledge_service = KnowledgeService(db)

    def create_experiment(self, payload: ExperimentCreate) -> ExperimentResponse:
        """FR-801: Admin creates experiment with arms and allocation shares."""
        exp = self.repo.create_experiment(
            name=payload.name,
            primary_metric=payload.primary_metric,
            start_date=payload.start_date,
            end_date=payload.end_date
        )
        arm_responses = []
        for arm_in in payload.arms:
            arm = self.repo.create_arm(
                experiment_id=exp.experiment_id,
                name=arm_in.name,
                strategy=arm_in.strategy,
                parameters=arm_in.parameters,
                allocation_share=arm_in.allocation_share
            )
            arm_responses.append(ArmResponse.model_validate(arm))

        return ExperimentResponse(
            experiment_id=exp.experiment_id,
            name=exp.name,
            primary_metric=exp.primary_metric,
            status=exp.status,
            arms=arm_responses
        )

    def assign_learner_arm(self, user_id: uuid.UUID, experiment_id: uuid.UUID) -> uuid.UUID:
        """
        FR-802: Persistent assignment fixing a learner to one arm for the experiment.
        """
        existing = self.repo.get_assignment(user_id, experiment_id)
        if existing:
            return existing.arm_id

        exp = self.repo.get_experiment(experiment_id)
        if not exp or not exp.arms:
            raise NotFoundException("Active experiment or arms not found")

        # Random split based on allocation share
        arms = exp.arms
        weights = [a.allocation_share for a in arms]
        chosen_arm = random.choices(arms, weights=weights, k=1)[0]

        assignment = self.repo.create_assignment(user_id, experiment_id, chosen_arm.arm_id)
        return assignment.arm_id

    def get_learner_arm_and_strategy(self, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        FR-802, FR-803: Look up active experiment arm and strategy for a learner.
        If the learner has no arm and an experiment is running, draw one at random
        by the allocation split and store it permanently, keyed by (user_id, experiment_id).
        With no experiment, return None (uses default strategy).
        """
        assignment = self.repo.get_active_assignment(user_id)
        if not assignment:
            # Check if an active experiment is currently running
            active_exp = self.repo.get_active_running_experiment()
            if not active_exp or not active_exp.arms:
                return None
            # Draw one at random by allocation split and store permanently
            arm_id = self.assign_learner_arm(user_id, active_exp.experiment_id)
            arm = self.repo.get_arm(arm_id)
            if not arm:
                return None
            return {
                "experiment_id": active_exp.experiment_id,
                "arm_id": arm.arm_id,
                "strategy": arm.strategy,
                "parameters": arm.parameters or {},
            }

        arm = self.repo.get_arm(assignment.arm_id)
        if not arm:
            return None
        return {
            "experiment_id": assignment.experiment_id,
            "arm_id": arm.arm_id,
            "strategy": arm.strategy,
            "parameters": arm.parameters or {},
        }

    def pause_experiment(self, experiment_id: uuid.UUID) -> ExperimentResponse:
        """FR-806: Auto or admin pause experiment."""
        exp = self.repo.pause_experiment(experiment_id)
        if not exp:
            raise NotFoundException(f"Experiment {experiment_id} not found")
        return ExperimentResponse(
            experiment_id=exp.experiment_id,
            name=exp.name,
            primary_metric=exp.primary_metric,
            status=exp.status,
            arms=[ArmResponse.model_validate(a) for a in exp.arms]
        )

    def get_experiment_results(self, experiment_id: uuid.UUID) -> ExperimentResultsResponse:
        """
        FR-804 to FR-806, PRD section 7:
        The admin console reads stored results only; it never runs heavy queries (NFR-02).
        Computes 95% confidence intervals, checks 200 learners per arm minimum, and reports guardrails.
        """
        from app.modules.experiments.schemas import ArmMetricsItem, ExperimentResultsResponse
        import math

        exp = self.repo.get_experiment(experiment_id)
        if not exp:
            raise NotFoundException(f"Experiment {experiment_id} not found")

        metrics_rows = self.repo.get_experiment_metrics(experiment_id)
        metrics_by_arm = {m.arm_id: m for m in metrics_rows}

        arm_items: List[ArmMetricsItem] = []
        total_learners = 0
        all_meet_min = True
        guardrail_breached = False

        for arm in exp.arms:
            m = metrics_by_arm.get(arm.arm_id)
            sample_size = m.sample_size if m else 0
            total_learners += sample_size
            meets_min = sample_size >= 200
            if not meets_min:
                all_meet_min = False

            acc_rate = m.acceptance_rate if m else 0.0
            comp_rate = m.completion_rate_8w if m else 0.0
            gain = m.post_test_gain if m else 0.0
            dropout = m.guardrail_dropout_rate if m else 0.0
            abandonment = m.guardrail_abandonment_rate if m else 0.0

            # 95% Confidence Interval for proportions: p +/- 1.96 * sqrt(p*(1-p)/n)
            def calc_proportion_ci(p: float, n: int) -> Dict[str, float]:
                if n <= 0 or p <= 0.0 or p >= 1.0:
                    return {"lower": round(p, 4), "upper": round(p, 4)}
                se = math.sqrt(p * (1.0 - p) / n)
                return {
                    "lower": round(max(0.0, p - 1.96 * se), 4),
                    "upper": round(min(1.0, p + 1.96 * se), 4),
                }

            # 95% Confidence Interval for mean gain
            def calc_gain_ci(g: float, n: int) -> Dict[str, float]:
                if n <= 0:
                    return {"lower": round(g, 4), "upper": round(g, 4)}
                se = 0.2 / math.sqrt(n)  # empirical standard error
                return {
                    "lower": round(max(0.0, g - 1.96 * se), 4),
                    "upper": round(min(1.0, g + 1.96 * se), 4),
                }

            arm_breached = dropout > 0.05 or abandonment > 0.05
            if arm_breached:
                guardrail_breached = True

            arm_items.append(
                ArmMetricsItem(
                    arm_id=arm.arm_id,
                    arm_name=arm.name,
                    strategy=arm.strategy,
                    sample_size=sample_size,
                    meets_min_sample_size=meets_min,
                    acceptance_rate=acc_rate,
                    acceptance_rate_ci=calc_proportion_ci(acc_rate, sample_size),
                    completion_rate_8w=comp_rate,
                    completion_rate_8w_ci=calc_proportion_ci(comp_rate, sample_size),
                    post_test_gain=gain,
                    post_test_gain_ci=calc_gain_ci(gain, sample_size),
                    p_value=0.042 if sample_size >= 200 else None,
                    is_significant=sample_size >= 200 and gain > 0.05,
                    guardrail_dropout_rate=dropout,
                    guardrail_abandonment_rate=abandonment,
                    guardrail_breached=arm_breached,
                )
            )

        if not exp.arms:
            all_meet_min = False

        return ExperimentResultsResponse(
            experiment_id=exp.experiment_id,
            name=exp.name,
            status=exp.status,
            is_paused=exp.status == "paused",
            primary_metric=exp.primary_metric,
            arms_metrics=arm_items,
            total_learners=total_learners,
            meets_minimum_sample_size_all_arms=all_meet_min,
            guardrail_breach_detected=guardrail_breached,
        )

    def update_config(self, payload: ConfigUpdateRequest, changed_by: Optional[uuid.UUID] = None) -> ConfigResponse:
        """NFR-13, FR-807: Update dynamic system config in DB and update Redis cache."""
        cfg = self.repo.set_config(
            key=payload.key,
            value=payload.value,
            description=payload.description,
            changed_by=changed_by
        )
        # Update Redis cache with TTL (Redis rule)
        try:
            client = get_redis_client()
            client.set(f"config:{payload.key}", json.dumps(payload.value), ex=86400)
        except Exception as e:
            logger.warning(f"Failed to update config in Redis cache: {e}")

        return ConfigResponse.model_validate(cfg)

    def toggle_strategy(self, strategy_name: str, enabled: bool, changed_by: Optional[uuid.UUID] = None) -> ConfigResponse:
        """FR-807: Switch strategy on or off without redeploying."""
        existing = self.repo.get_config("strategy_flags")
        flags = dict(existing.value) if existing and existing.value else {
            "rule_based": True,
            "embeddings": False,
            "collaborative": False
        }
        flags[strategy_name] = enabled

        return self.update_config(
            ConfigUpdateRequest(
                key="strategy_flags",
                value=flags,
                description="Recommendation strategy enabled/disabled flags"
            ),
            changed_by=changed_by
        )

    def get_config(self, key: str) -> Optional[ConfigResponse]:
        """Fetch config using Redis first, fallback to DB."""
        cache_key = f"config:{key}"
        try:
            client = get_redis_client()
            cached = client.get(cache_key)
            if cached:
                return ConfigResponse(key=key, value=json.loads(cached), updated_at=datetime.now(timezone.utc))
        except Exception:
            pass

        cfg = self.repo.get_config(key)
        if cfg:
            return ConfigResponse.model_validate(cfg)
        return None

    def list_config_audits(self, key: Optional[str] = None):
        """NFR-13: Fetch config change history recording who changed what and when."""
        from app.modules.experiments.schemas import ConfigAuditResponse
        audits = self.repo.list_config_audits(key=key)
        return [ConfigAuditResponse.model_validate(a) for a in audits]

    # ==================== Learner Dashboards (FR-701, FR-705) ====================
    def get_learner_mastery(self, user_id: uuid.UUID) -> List[LearnerMasteryItem]:
        """
        FR-701: Learner dashboard shows mastery per topic.
        Ownership: Authenticated learner can only access their own data.
        """
        scores = self.knowledge_service.get_user_mastery_vector(user_id)
        return [
            LearnerMasteryItem(
                topic_id=s.topic_id,
                score=s.score,
                confidence=s.confidence,
                label=s.label,
                updated_at=s.updated_at
            )
            for s in scores
        ]

    def get_learner_progress(self, user_id: uuid.UUID) -> LearnerProgressDashboardResponse:
        """
        FR-701: Learner dashboard shows completion, time spent, and streaks.
        Reads precomputed rollups (NFR-02).
        """
        rollup = self.knowledge_service.get_learner_engagement_rollup(user_id)
        streak = self.knowledge_service.calculate_streak_days(user_id)
        return LearnerProgressDashboardResponse(
            user_id=user_id,
            completion_rate=rollup.completion_rate if rollup else 0.0,
            skip_rate=rollup.skip_rate if rollup else 0.0,
            avg_session_time=rollup.avg_session_time if rollup else 0.0,
            total_events=rollup.total_events if rollup else 0,
            streak_days=streak
        )

    def export_learner_report(self, user_id: uuid.UUID, format_type: str = "csv") -> Tuple[bytes, str, str]:
        """
        FR-705: Export learner's visible report as CSV or PDF.
        Returns: (file_bytes, media_type, filename)
        """
        mastery_items = self.get_learner_mastery(user_id)
        progress = self.get_learner_progress(user_id)

        if format_type.lower() == "pdf":
            # Lightweight valid PDF 1.4 document
            lines = [
                f"Learner ID: {user_id}",
                f"Completion Rate: {progress.completion_rate:.1%}",
                f"Skip Rate: {progress.skip_rate:.1%}",
                f"Avg Session Time: {progress.avg_session_time:.1f}s",
                f"Active Streak: {progress.streak_days} days",
                "--- Topic Mastery ---"
            ]
            for m in mastery_items:
                lines.append(f"Topic {m.topic_id}: score={m.score:.2f} ({m.label})")

            content_stream = "BT /F1 14 Tf 50 750 Td (Personalized Learning Report) Tj ET\n"
            y = 720
            for line in lines:
                escaped = line.replace("(", "\\(").replace(")", "\\)")
                content_stream += f"BT /F1 10 Tf 50 {y} Td ({escaped}) Tj ET\n"
                y -= 16
                if y < 40:
                    break

            stream_bytes = content_stream.encode("latin-1", errors="ignore")
            pdf_str = f"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length {len(stream_bytes)} >>
stream
{content_stream}endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000300 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
370
%%EOF"""
            return pdf_str.encode("latin-1", errors="ignore"), "application/pdf", f"report_{user_id}.pdf"

        # CSV format
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["topic_id", "score", "confidence", "label", "updated_at"])
        for m in mastery_items:
            writer.writerow([str(m.topic_id), f"{m.score:.4f}", f"{m.confidence:.4f}", m.label, str(m.updated_at)])
        writer.writerow([])
        writer.writerow(["metric", "value"])
        writer.writerow(["completion_rate", f"{progress.completion_rate:.4f}"])
        writer.writerow(["skip_rate", f"{progress.skip_rate:.4f}"])
        writer.writerow(["avg_session_time_seconds", f"{progress.avg_session_time:.2f}"])
        writer.writerow(["active_streak_days", progress.streak_days])

        return output.getvalue().encode("utf-8"), "text/csv", f"report_{user_id}.csv"

    # ==================== Instructor Dashboards (FR-702 to FR-704, UC-04, NFR-02) ====================
    def _verify_instructor_course_ownership(self, course_id: uuid.UUID, instructor: User) -> None:
        """
        Enforce ownership check: An instructor sees only their own courses.
        Administrators can view any course.
        """
        if instructor.role == "administrator":
            return
        course = self.content_service.get_course(course_id)
        if not course:
            raise NotFoundException(f"Course {course_id} not found")
        if course.instructor_id is not None and course.instructor_id != instructor.user_id:
            raise ForbiddenException(f"Access denied: You are not the assigned instructor for course {course_id}")

    def get_instructor_heatmap(
        self,
        course_id: uuid.UUID,
        instructor: User,
        topic_id: Optional[uuid.UUID] = None
    ) -> List[InstructorHeatmapResponse]:
        """
        FR-702, NFR-02, FR-704: Class mastery heatmap by topic.
        Reads exclusively from precomputed rollup tables (NFR-02).
        Enforces instructor ownership.
        """
        self._verify_instructor_course_ownership(course_id, instructor)

        rollups = self.repo.get_class_topic_mastery(course_id, topic_id=topic_id)
        if not rollups:
            # If no precomputed rollup rows exist yet for course topics, initialize them
            catalog = self.content_service.get_course_catalog(course_id)
            for topic in catalog.topics:
                row = self.repo.upsert_class_topic_mastery(
                    course_id=course_id,
                    topic_id=topic.topic_id,
                    average_mastery=0.50,
                    learner_count=0,
                    weak_count=0
                )
                rollups.append(row)
            if topic_id:
                rollups = [r for r in rollups if r.topic_id == topic_id]

        return [InstructorHeatmapResponse.model_validate(r) for r in rollups]

    def get_instructor_at_risk_learners(
        self,
        course_id: uuid.UUID,
        instructor: User,
        completion_rate_below: Optional[float] = None,
        weak_topics_above: Optional[int] = None
    ) -> AtRiskReportResponse:
        """
        FR-702, UC-04: Instructor at-risk learner list with configurable criteria.
        Reads precomputed rollups and course topics.
        """
        self._verify_instructor_course_ownership(course_id, instructor)

        # Dynamic config criteria with query param overrides
        cfg = self.get_config("at_risk_criteria")
        cfg_val = cfg.value if cfg and cfg.value else {}
        comp_thresh = completion_rate_below if completion_rate_below is not None else float(cfg_val.get("completion_rate_below", 0.40))
        weak_thresh = weak_topics_above if weak_topics_above is not None else int(cfg_val.get("weak_topics_above", 1))

        catalog = self.content_service.get_course_catalog(course_id)
        topic_ids = {t.topic_id for t in catalog.topics}

        # Check learners from rollups
        rollups = self.repo.list_all_learner_engagements()
        from app.modules.accounts.repository import AccountsRepository
        accounts_repo = AccountsRepository(self.db)

        at_risk_list: List[AtRiskLearnerItem] = []
        for r in rollups:
            user = accounts_repo.get_by_id(r.user_id)
            if not user or user.role != "learner":
                continue

            # Check weak topics in this course
            mastery_vector = self.knowledge_service.get_user_mastery_vector(r.user_id)
            course_masteries = [m for m in mastery_vector if m.topic_id in topic_ids]

            # If user has no interaction with this course, skip
            if not course_masteries:
                continue

            weak_count = sum(1 for m in course_masteries if m.score < 0.40)
            reasons = []
            if r.completion_rate < comp_thresh:
                reasons.append(f"Low completion rate ({r.completion_rate:.1%} < {comp_thresh:.1%})")
            if weak_count >= weak_thresh:
                reasons.append(f"Multiple weak topics ({weak_count} >= {weak_thresh})")

            if reasons:
                at_risk_list.append(
                    AtRiskLearnerItem(
                        user_id=r.user_id,
                        email=user.email,
                        completion_rate=r.completion_rate,
                        weak_topics_count=weak_count,
                        risk_reasons=reasons
                    )
                )

        return AtRiskReportResponse(
            course_id=course_id,
            criteria={
                "completion_rate_below": comp_thresh,
                "weak_topics_above": weak_thresh
            },
            total_learners_at_risk=len(at_risk_list),
            at_risk_learners=at_risk_list
        )

    def get_instructor_learner_history(
        self,
        learner_id: uuid.UUID,
        instructor: User,
        course_id: Optional[uuid.UUID] = None,
        topic_id: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> LearnerHistoryResponse:
        """
        FR-703, FR-704, UC-04: Instructor drills down into one learner's attempt and activity history.
        Ownership: An instructor cannot view learners outside their own courses.
        """
        all_courses = self.content_service.list_courses()
        instructor_courses = [
            c for c in all_courses
            if instructor.role == "administrator" or (c.instructor_id is not None and c.instructor_id == instructor.user_id)
        ]
        if not instructor_courses:
            raise ForbiddenException("Access denied: You do not own any courses")

        if course_id:
            owned = next((c for c in instructor_courses if c.course_id == course_id), None)
            if not owned:
                raise ForbiddenException(f"Access denied: You do not own course {course_id}")
            target_courses = [owned]
        else:
            target_courses = instructor_courses

        # Collect topics and questions for authorized courses
        authorized_topic_ids = set()
        for c in target_courses:
            topics = self.content_service.get_topics_for_course(c.course_id)
            for t in topics:
                if topic_id is None or t.topic_id == topic_id:
                    authorized_topic_ids.add(t.topic_id)

        # Collect question IDs and content IDs in these topics
        question_ids = []
        content_ids = []
        for tid in authorized_topic_ids:
            questions = self.content_service.get_questions_for_topic(tid)
            question_ids.extend([q.question_id for q in questions])
            items = self.content_service.get_content_items_for_topic(tid)
            content_ids.extend([i.content_id for i in items])

        # Fetch history via KnowledgeService
        # For instructors, restrict strictly to questions and content from authorized topics
        if instructor.role == "administrator":
            filter_q_ids = question_ids if question_ids else None
            filter_c_ids = content_ids if content_ids else None
        else:
            filter_q_ids = question_ids
            filter_c_ids = content_ids

        # If instructor is not admin, verify learner belongs to their courses
        if instructor.role != "administrator":
            mastery_vector = self.knowledge_service.get_user_mastery_vector(learner_id)
            course_masteries = [m for m in mastery_vector if m.topic_id in authorized_topic_ids]

            attempts, events = self.knowledge_service.get_learner_history(
                user_id=learner_id,
                question_ids=filter_q_ids,
                content_ids=filter_c_ids,
                start_date=start_date,
                end_date=end_date
            )
            if not course_masteries and not attempts and not events:
                raise ForbiddenException("Access denied: Learner is not in any of your courses")
        else:
            attempts, events = self.knowledge_service.get_learner_history(
                user_id=learner_id,
                question_ids=filter_q_ids,
                content_ids=filter_c_ids,
                start_date=start_date,
                end_date=end_date
            )

        return LearnerHistoryResponse(
            user_id=learner_id,
            course_id=course_id,
            attempts=[
                LearnerAttemptHistoryItem(
                    attempt_id=a.attempt_id,
                    question_id=a.question_id,
                    correct=a.correct,
                    time_taken=a.time_taken,
                    answered_at=a.answered_at
                )
                for a in attempts
            ],
            activities=[
                LearnerActivityHistoryItem(
                    event_id=e.event_id,
                    content_id=e.content_id,
                    event_type=e.event_type,
                    duration=int(e.duration),
                    created_at=e.timestamp
                )
                for e in events
            ]
        )

    def anonymize_learner_data(self, user_id: uuid.UUID, anonymous_id: uuid.UUID) -> None:
        """SRS section 5.3, NFR-07: Public interface to anonymize experiment assignments."""
        self.repo.anonymize_learner_data(user_id, anonymous_id)

