"""
Experiments & Analytics repository (FR-801 to FR-807, FR-702, NFR-13).
Only this file touches experiments, arms, assignments, configs, config_audits, and rollups.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models.experiments import Experiment, Arm, ExperimentAssignment
from app.db.models.config import Config, ConfigAudit
from app.db.models.rollups import (
    ClassTopicMasteryRollup,
    LearnerEngagementRollup,
    ExperimentMetricsRollup,
)


class ExperimentsRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_experiment(self, name: str, primary_metric: str, start_date: Optional[datetime], end_date: Optional[datetime]) -> Experiment:
        exp = Experiment(
            name=name,
            primary_metric=primary_metric,
            status="active",
            start_date=start_date,
            end_date=end_date
        )
        self.db.add(exp)
        self.db.commit()
        self.db.refresh(exp)
        return exp

    def create_arm(self, experiment_id: uuid.UUID, name: str, strategy: str, parameters: dict, allocation_share: float) -> Arm:
        arm = Arm(
            experiment_id=experiment_id,
            name=name,
            strategy=strategy,
            parameters=parameters,
            allocation_share=allocation_share
        )
        self.db.add(arm)
        self.db.commit()
        self.db.refresh(arm)
        return arm

    def get_experiment(self, experiment_id: uuid.UUID) -> Optional[Experiment]:
        return self.db.execute(select(Experiment).where(Experiment.experiment_id == experiment_id)).scalar_one_or_none()

    def get_arm(self, arm_id: uuid.UUID) -> Optional[Arm]:
        return self.db.execute(select(Arm).where(Arm.arm_id == arm_id)).scalar_one_or_none()

    def get_active_assignment(self, user_id: uuid.UUID) -> Optional[ExperimentAssignment]:
        """Check if user has an active experiment assignment."""
        stmt = (
            select(ExperimentAssignment)
            .join(Experiment, Experiment.experiment_id == ExperimentAssignment.experiment_id)
            .where(
                ExperimentAssignment.user_id == user_id,
                Experiment.status == "active"
            )
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_assignment(self, user_id: uuid.UUID, experiment_id: uuid.UUID) -> Optional[ExperimentAssignment]:
        """FR-802: Check persistent assignment."""
        return self.db.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.user_id == user_id,
                ExperimentAssignment.experiment_id == experiment_id
            )
        ).scalar_one_or_none()

    def create_assignment(self, user_id: uuid.UUID, experiment_id: uuid.UUID, arm_id: uuid.UUID) -> ExperimentAssignment:
        assignment = ExperimentAssignment(
            user_id=user_id,
            experiment_id=experiment_id,
            arm_id=arm_id,
            assigned_at=datetime.now(timezone.utc)
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def pause_experiment(self, experiment_id: uuid.UUID) -> Optional[Experiment]:
        """FR-806: Auto-pause experiment when guardrails are breached."""
        exp = self.get_experiment(experiment_id)
        if exp:
            exp.status = "paused"
            self.db.commit()
            self.db.refresh(exp)
        return exp

    def get_config(self, key: str) -> Optional[Config]:
        return self.db.execute(select(Config).where(Config.key == key)).scalar_one_or_none()

    def set_config(self, key: str, value: dict, description: Optional[str], changed_by: Optional[uuid.UUID]) -> Config:
        """NFR-13: Store config and write audit log."""
        existing = self.get_config(key)
        old_val = existing.value if existing else None
        if existing:
            existing.value = value
            if description:
                existing.description = description
            existing.updated_at = datetime.now(timezone.utc)
            cfg = existing
        else:
            cfg = Config(key=key, value=value, description=description, updated_at=datetime.now(timezone.utc))
            self.db.add(cfg)

        audit = ConfigAudit(
            id=uuid.uuid4(),
            key=key,
            old_value=old_val,
            new_value=value,
            changed_by_user_id=changed_by,
            changed_at=datetime.now(timezone.utc)
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(cfg)
        return cfg

    def list_config_audits(self, key: Optional[str] = None, limit: int = 50) -> List[ConfigAudit]:
        """NFR-13: Fetch config change history recording who changed what and when."""
        stmt = select(ConfigAudit).order_by(ConfigAudit.changed_at.desc()).limit(limit)
        if key:
            stmt = stmt.where(ConfigAudit.key == key)
        return list(self.db.execute(stmt).scalars().all())

    def get_class_topic_mastery(self, course_id: uuid.UUID, topic_id: Optional[uuid.UUID] = None) -> List[ClassTopicMasteryRollup]:
        """FR-702, NFR-02: Fast instructor dashboard reads from precomputed rollup table."""
        stmt = select(ClassTopicMasteryRollup).where(ClassTopicMasteryRollup.course_id == course_id)
        if topic_id:
            stmt = stmt.where(ClassTopicMasteryRollup.topic_id == topic_id)
        return list(self.db.execute(stmt).scalars().all())

    def upsert_class_topic_mastery(
        self,
        course_id: uuid.UUID,
        topic_id: uuid.UUID,
        average_mastery: float,
        learner_count: int,
        weak_count: int
    ) -> ClassTopicMasteryRollup:
        """FR-702, NFR-02: Populate precomputed class topic mastery rollup."""
        stmt = select(ClassTopicMasteryRollup).where(
            ClassTopicMasteryRollup.course_id == course_id,
            ClassTopicMasteryRollup.topic_id == topic_id
        )
        row = self.db.execute(stmt).scalar_one_or_none()
        if row:
            row.average_mastery = average_mastery
            row.learner_count = learner_count
            row.weak_count = weak_count
            row.updated_at = datetime.now(timezone.utc)
        else:
            row = ClassTopicMasteryRollup(
                course_id=course_id,
                topic_id=topic_id,
                average_mastery=average_mastery,
                learner_count=learner_count,
                weak_count=weak_count,
                updated_at=datetime.now(timezone.utc)
            )
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_all_learner_engagements(self) -> List[LearnerEngagementRollup]:
        """FR-702: Read precomputed learner engagement rollups."""
        stmt = select(LearnerEngagementRollup)
        return list(self.db.execute(stmt).scalars().all())


    def get_active_running_experiment(self) -> Optional[Experiment]:
        """FR-801, FR-802: Get currently active experiment running within dates."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(Experiment)
            .where(Experiment.status == "active")
            .order_by(Experiment.created_at.desc())
        )
        experiments = self.db.execute(stmt).scalars().all()
        for exp in experiments:
            s_date = exp.start_date if (exp.start_date is None or exp.start_date.tzinfo) else exp.start_date.replace(tzinfo=timezone.utc)
            e_date = exp.end_date if (exp.end_date is None or exp.end_date.tzinfo) else exp.end_date.replace(tzinfo=timezone.utc)
            if s_date and s_date > now:
                continue
            if e_date and e_date < now:
                continue
            return exp
        return None

    def list_active_experiments(self) -> List[Experiment]:
        stmt = select(Experiment).where(Experiment.status == "active")
        return list(self.db.execute(stmt).scalars().all())

    def get_experiment_metrics(self, experiment_id: uuid.UUID) -> List[ExperimentMetricsRollup]:
        stmt = select(ExperimentMetricsRollup).where(ExperimentMetricsRollup.experiment_id == experiment_id)
        return list(self.db.execute(stmt).scalars().all())

    def get_assignments_for_experiment(self, experiment_id: uuid.UUID) -> List[ExperimentAssignment]:
        stmt = select(ExperimentAssignment).where(ExperimentAssignment.experiment_id == experiment_id)
        return list(self.db.execute(stmt).scalars().all())

    def get_recommendations_for_arm(self, arm_id: uuid.UUID):
        from app.db.models.recommender import Recommendation
        stmt = select(Recommendation).where(Recommendation.arm_id == arm_id)
        return list(self.db.execute(stmt).scalars().all())

    def upsert_experiment_metrics_rollup(
        self,
        experiment_id: uuid.UUID,
        arm_id: uuid.UUID,
        acceptance_rate: float,
        completion_rate_8w: float,
        post_test_gain: float,
        sample_size: int,
        guardrail_dropout_rate: float,
        guardrail_abandonment_rate: float
    ) -> ExperimentMetricsRollup:
        """FR-804 to FR-806: Store precomputed per-arm experiment metrics."""
        stmt = select(ExperimentMetricsRollup).where(
            ExperimentMetricsRollup.experiment_id == experiment_id,
            ExperimentMetricsRollup.arm_id == arm_id
        )
        row = self.db.execute(stmt).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if row:
            row.acceptance_rate = acceptance_rate
            row.completion_rate_8w = completion_rate_8w
            row.post_test_gain = post_test_gain
            row.sample_size = sample_size
            row.guardrail_dropout_rate = guardrail_dropout_rate
            row.guardrail_abandonment_rate = guardrail_abandonment_rate
            row.updated_at = now
        else:
            row = ExperimentMetricsRollup(
                experiment_id=experiment_id,
                arm_id=arm_id,
                acceptance_rate=acceptance_rate,
                completion_rate_8w=completion_rate_8w,
                post_test_gain=post_test_gain,
                sample_size=sample_size,
                guardrail_dropout_rate=guardrail_dropout_rate,
                guardrail_abandonment_rate=guardrail_abandonment_rate,
                updated_at=now
            )
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def anonymize_learner_data(self, user_id: uuid.UUID, anonymous_id: uuid.UUID) -> None:
        """SRS section 5.3, NFR-07: Anonymize experiment assignments while preserving arm metrics."""
        from sqlalchemy import update
        self.db.execute(
            update(ExperimentAssignment).where(ExperimentAssignment.user_id == user_id).values(user_id=anonymous_id)
        )
        self.db.commit()
