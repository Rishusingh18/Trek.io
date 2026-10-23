"""
Synthetic demo data seed script.
Generates a complete, realistic dataset for demonstration and evaluation:
- 1 Primary Course with 8 topics and prerequisite links (Python Programming)
- 1 Secondary Course for Instructor 2
- 80 Content items (types, difficulties 1-5, durations, tags)
- 200 Questions across difficulty tiers (0.1 to 0.95)
- 1 Admin, 2 Instructors
- 1,000 Learners with realistic cohorts (Strong, Developing, At-Risk)
- Realistic attempt histories, interaction events (completed, skipped, opened)
- Recommendations and dismissals for quiet-period testing
- Precomputed engagement and class topic mastery rollups

Deterministic with a random seed and re-runnable with --clean.
"""
import argparse
import math
import random
import sys
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from app.core.auth import get_password_hash
from app.db.session import SessionLocal
from app.core.logging import logger, setup_logging
from app.modules.accounts.repository import AccountsRepository
from app.modules.content.repository import ContentRepository
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.recommender.repository import RecommenderRepository
from app.worker.jobs import run_rollup_job
from app.db.models.accounts import User
from app.db.models.content import Course, Topic, ContentItem, Question
from app.db.models.knowledge import MasteryScore, Attempt, InteractionEvent
from app.db.models.recommender import Recommendation
from app.db.models.experiments import Experiment, Arm, ExperimentAssignment
from app.db.models.rollups import (
    ClassTopicMasteryRollup,
    LearnerEngagementRollup,
    ExperimentMetricsRollup,
)


TOPIC_DEFINITIONS = [
    {
        "name": "Python Basics & Syntax",
        "description": "Variables, primitive types, operators, and basic input/output.",
        "prereq_indices": [],
        "tags": ["python", "syntax", "basics", "variables"],
    },
    {
        "name": "Control Flow & Conditionals",
        "description": "If-else branching, for/while loops, and list comprehensions.",
        "prereq_indices": [0],
        "tags": ["python", "control-flow", "loops", "conditionals"],
    },
    {
        "name": "Functions & Scopes",
        "description": "Defining functions, parameters, return values, args/kwargs, and namespaces.",
        "prereq_indices": [1],
        "tags": ["python", "functions", "scope", "modular"],
    },
    {
        "name": "Collections & Data Structures",
        "description": "Lists, tuples, dictionaries, sets, and basic algorithmic manipulation.",
        "prereq_indices": [2],
        "tags": ["python", "data-structures", "dicts", "lists"],
    },
    {
        "name": "Object-Oriented Programming",
        "description": "Classes, objects, methods, inheritance, polymorphism, and dunder methods.",
        "prereq_indices": [3],
        "tags": ["python", "oop", "classes", "inheritance"],
    },
    {
        "name": "Exception Handling & File I/O",
        "description": "Try-except blocks, custom exceptions, context managers, and file reading/writing.",
        "prereq_indices": [4],
        "tags": ["python", "exceptions", "file-io", "streams"],
    },
    {
        "name": "Modules & Packaging",
        "description": "Import system, pip, virtual environments, and organizing modular code.",
        "prereq_indices": [4],
        "tags": ["python", "modules", "packages", "tooling"],
    },
    {
        "name": "Advanced Python: Decorators, Generators & Async",
        "description": "Higher-order functions, generator yields, and asyncio event loops.",
        "prereq_indices": [2, 4],
        "tags": ["python", "advanced", "async", "decorators", "generators"],
    },
]

CONTENT_TYPES = ["video", "text", "interactive", "exercise", "quiz"]


def clean_database(db: Session) -> None:
    """Safely truncate existing seeded tables to ensure clean, idempotent re-runs."""
    logger.info("Cleaning existing database data for clean re-seed...")
    db.execute(delete(ExperimentMetricsRollup))
    db.execute(delete(ClassTopicMasteryRollup))
    db.execute(delete(LearnerEngagementRollup))
    db.execute(delete(ExperimentAssignment))
    db.execute(delete(Arm))
    db.execute(delete(Experiment))
    db.execute(delete(Recommendation))
    db.execute(delete(Attempt))
    db.execute(delete(InteractionEvent))
    db.execute(delete(MasteryScore))
    db.execute(delete(Question))
    db.execute(delete(ContentItem))
    db.execute(delete(Topic))
    db.execute(delete(Course))
    db.execute(delete(User))
    db.commit()
    logger.info("Database cleaned successfully.")


def run_seed(
    db: Session,
    seed: int = 42,
    num_learners: int = 1000,
    clean: bool = True
) -> Dict[str, Any]:
    """
    Main synthetic data seeding procedure.
    """
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)

    if clean:
        clean_database(db)

    accounts_repo = AccountsRepository(db)
    from app.modules.content.service import ContentService
    from app.modules.content.schemas import CourseCreate, TopicCreate, ContentItemCreate, QuestionCreate

    content_svc = ContentService(db)
    knowledge_repo = KnowledgeRepository(db)
    recommender_repo = RecommenderRepository(db)

    default_password_hash = get_password_hash("Password123!")

    # 1. Staff Accounts
    logger.info("Seeding Admin and Instructors...")
    admin = accounts_repo.create_user("admin@techxtract.com", default_password_hash, "administrator")
    instructor1 = accounts_repo.create_user("instructor1@techxtract.com", default_password_hash, "instructor")
    instructor2 = accounts_repo.create_user("instructor2@techxtract.com", default_password_hash, "instructor")

    # 2. Courses
    logger.info("Seeding Courses and Topics...")
    course_primary = content_svc.create_course(
        CourseCreate(
            title="Comprehensive Python Mastery",
            description="A complete, end-to-end curriculum mastering modern Python programming.",
            instructor_id=instructor1.user_id
        )
    )

    course_secondary = content_svc.create_course(
        CourseCreate(
            title="Applied Python for Data Structures",
            description="Intermediate computer science and algorithmic structures in Python.",
            instructor_id=instructor2.user_id
        )
    )

    # 3. Topics with Prerequisite Links
    created_topics = []
    for t_def in TOPIC_DEFINITIONS:
        # Resolve prerequisite topic IDs
        prereq_ids = [str(created_topics[p_idx].topic_id) for p_idx in t_def["prereq_indices"]]
        topic = content_svc.create_topic(
            TopicCreate(
                course_id=course_primary.course_id,
                name=t_def["name"],
                prerequisite_topic_ids=prereq_ids
            )
        )
        created_topics.append(topic)

    # Secondary course sample topic
    content_svc.create_topic(
        TopicCreate(
            course_id=course_secondary.course_id,
            name="Graph Algorithms & Complexity",
            prerequisite_topic_ids=[]
        )
    )

    # 4. Content Items (~80 total, 10 per primary topic)
    logger.info("Seeding 80 Content Items across difficulty tiers and formats...")
    created_content_items = []
    for topic_idx, topic in enumerate(created_topics):
        t_def = TOPIC_DEFINITIONS[topic_idx]
        for item_idx in range(1, 11):
            difficulty = ((item_idx - 1) % 5) + 1  # 1 to 5
            c_type = CONTENT_TYPES[(item_idx - 1) % len(CONTENT_TYPES)]
            duration = rng.randint(3, 25) * 60  # 180s to 1500s
            tags = list(set(t_def["tags"] + [f"level-{difficulty}", c_type]))

            prereqs = [str(created_topics[p].topic_id) for p in t_def["prereq_indices"]]

            item = content_svc.create_content_item(
                ContentItemCreate(
                    topic_id=topic.topic_id,
                    title=f"{topic.name}: Part {item_idx} ({c_type.title()})",
                    type=c_type,
                    difficulty=difficulty,
                    duration=duration,
                    tags=tags,
                    prerequisite_topic_ids=prereqs
                )
            )
            created_content_items.append(item)

    # 5. Questions (~200 total, ~25 per topic)
    logger.info("Seeding 200 Questions with graded answers...")
    created_questions = []
    for topic in created_topics:
        for q_idx in range(1, 26):
            difficulty_float = round(0.1 + (q_idx - 1) * 0.035, 2)  # 0.10 to 0.94
            q = content_svc.create_question(
                QuestionCreate(
                    topic_id=topic.topic_id,
                    prompt=f"Question {q_idx} on {topic.name}: Which statement best demonstrates correct usage?",
                    difficulty=min(1.0, max(0.0, difficulty_float)),
                    correct_answer="Option A",
                    options=["Option A", "Option B", "Option C", "Option D"]
                )
            )
            created_questions.append(q)

    # 6. Learners (1,000 learners with realistic cohorts)
    logger.info(f"Seeding {num_learners} Learners with realistic cohorts and activity profiles...")
    # Cohort breakdown: 30% Strong, 50% Developing, 20% At-risk
    cohorts = ["strong"] * int(num_learners * 0.3) + \
              ["developing"] * int(num_learners * 0.5) + \
              ["at_risk"] * (num_learners - int(num_learners * 0.3) - int(num_learners * 0.5))
    rng.shuffle(cohorts)

    # Pre-select content preferences for variation
    preferred_types = ["video", "interactive", "exercise", "text"]

    for idx, cohort in enumerate(cohorts, start=1):
        email = f"learner_{idx:04d}@techxtract.com"
        learner = accounts_repo.create_user(email, default_password_hash, "learner")
        accounts_repo.record_consent(learner.user_id)

        pref_type = preferred_types[idx % len(preferred_types)]

        # Determine cohort parameters
        if cohort == "strong":
            base_ability = rng.uniform(0.75, 0.95)
            completion_prob = rng.uniform(0.80, 0.95)
            num_attempts = rng.randint(8, 20)
            num_events = rng.randint(10, 25)
        elif cohort == "developing":
            base_ability = rng.uniform(0.50, 0.74)
            completion_prob = rng.uniform(0.55, 0.75)
            num_attempts = rng.randint(5, 14)
            num_events = rng.randint(6, 18)
        else:  # at_risk
            base_ability = rng.uniform(0.20, 0.38)
            completion_prob = rng.uniform(0.15, 0.38)
            num_attempts = rng.randint(2, 8)
            num_events = rng.randint(3, 10)

        # 6a. Graded Question Attempts
        sampled_questions = rng.sample(created_questions, min(num_attempts, len(created_questions)))
        for q in sampled_questions:
            # Logistic model for correctness probability: p = 1 / (1 + exp(-beta * (ability - difficulty)))
            z = 4.0 * (base_ability - q.difficulty)
            p_correct = 1.0 / (1.0 + math.exp(-max(-10.0, min(10.0, z))))
            is_correct = rng.random() < p_correct
            time_taken = rng.uniform(15.0, 95.0)

            attempt = Attempt(
                attempt_id=uuid.uuid4(),
                user_id=learner.user_id,
                question_id=q.question_id,
                correct=is_correct,
                time_taken=round(time_taken, 1),
                answered_at=now - timedelta(days=rng.randint(0, 14), minutes=rng.randint(0, 1400))
            )
            db.add(attempt)

        # 6b. Interaction Events (completed, skipped, opened)
        sampled_items = rng.sample(created_content_items, min(num_events, len(created_content_items)))
        for item in sampled_items:
            # Boost completion prob if item matches preferred type
            type_boost = 0.15 if item.type == pref_type else 0.0
            eff_prob = min(0.98, completion_prob + type_boost)

            rand_val = rng.random()
            if rand_val < eff_prob:
                event_type = "completed"
                duration = int(item.duration * rng.uniform(0.8, 1.2))
            elif rand_val < eff_prob + 0.20:
                event_type = "skipped"
                duration = int(rng.uniform(10, 45))
            else:
                event_type = "opened"
                duration = int(item.duration * rng.uniform(0.3, 0.7))

            event = InteractionEvent(
                event_id=uuid.uuid4(),
                user_id=learner.user_id,
                content_id=item.content_id,
                event_type=event_type,
                duration=duration,
                timestamp=now - timedelta(days=rng.randint(0, 20), minutes=rng.randint(0, 1400))
            )
            db.add(event)

        # 6c. Initial Topic Mastery Vector
        for t_idx, topic in enumerate(created_topics):
            # Prerequisite decay effect: higher topics have slightly lower initial mastery
            topic_decay = t_idx * 0.04
            mastery_score = max(0.05, min(0.98, base_ability - topic_decay + rng.uniform(-0.08, 0.08)))
            confidence = min(0.95, 0.3 + (num_attempts * 0.04))

            db.add(
                MasteryScore(
                    user_id=learner.user_id,
                    topic_id=topic.topic_id,
                    score=round(mastery_score, 4),
                    confidence=round(confidence, 4),
                    updated_at=now - timedelta(days=rng.randint(0, 5))
                )
            )

        # 6d. Recommendations & Dismissals (for quiet-period and recommendation history testing)
        if rng.random() < 0.25:
            rec_item = rng.choice(created_content_items)
            rec = recommender_repo.save_recommendation(
                user_id=learner.user_id,
                content_id=rec_item.content_id,
                arm_id=None,
                rank=1,
                reason="Matches your current skill progression"
            )
            if rng.random() < 0.50:
                recommender_repo.dismiss_recommendation(rec.rec_id)

    db.commit()
    logger.info("Learners and activities committed.")

    # 7. Compute Rollups for Precomputed Dashboard Views (NFR-02)
    logger.info("Computing precomputed dashboard rollups (NFR-02)...")
    rollup_counts = run_rollup_job(db)

    logger.info("Synthetic demo data seeding complete!")
    return {
        "admin": admin.email,
        "instructors": [instructor1.email, instructor2.email],
        "course_id": str(course_primary.course_id),
        "topics_count": len(created_topics),
        "content_count": len(created_content_items),
        "questions_count": len(created_questions),
        "learners_count": num_learners,
        "rollups": rollup_counts,
    }


def main():
    parser = argparse.ArgumentParser(description="Seed synthetic demo data for Personalized Learning Recommender.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation (default: 42)")
    parser.add_argument("--learners", type=int, default=1000, help="Number of learners to generate (default: 1000)")
    parser.add_argument("--clean", action="store_true", default=True, help="Clean existing records before seeding")
    parser.add_argument("--no-clean", dest="clean", action="store_false", help="Append without clearing tables")

    args = parser.parse_args()
    setup_logging()

    db = SessionLocal()
    try:
        summary = run_seed(db, seed=args.seed, num_learners=args.learners, clean=args.clean)
        logger.info(f"Seed Summary: {summary}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
