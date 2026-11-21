"""
Seed script aligning backend database with Stitch Academic Portal frontend:
- Course: CS 301: Advanced Data Structures & Algorithms
- Units: Arrays & Strings, Linked Lists, Trees & BSTs, Graph Theory, Dynamic Programming, Greedy Algorithms
- Personas:
  * Asha Sharma (Learner, asha@campus.edu)
  * Prof. Rao (Instructor, profr@campus.edu)
  * Platform Admin (admin@campus.edu)
  * 342 cohort learners (with Marcus Vance, Priya Patel, etc.)
- A/B Experiment: Exp #04 Rule-Based (Arm A) vs. Embedding-Hybrid (Arm B)
- Calibrated ML Embeddings & Topic Mastery vectors
"""
import os
import uuid
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from app.core.config import settings
from app.core.auth import get_password_hash
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.core.logging import logger, setup_logging
from app.modules.accounts.repository import AccountsRepository
from app.modules.content.service import ContentService
from app.modules.content.schemas import CourseCreate, TopicCreate, ContentItemCreate, QuestionCreate
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

STITCH_TOPICS = [
    {
        "name": "Arrays & Strings",
        "unit": "Unit 1",
        "description": "Two-pointer techniques, sliding windows, prefix sums, and amortized memory layouts.",
        "prereq_indices": [],
        "tags": ["arrays", "strings", "two-pointer", "sliding-window", "prefix-sums"],
        "class_mastery": 0.84,
        "asha_mastery": 0.88,
    },
    {
        "name": "Linked Lists",
        "unit": "Unit 2",
        "description": "Singly & doubly linked lists, cycle detection (Floyd's algorithm), and pointer manipulation.",
        "prereq_indices": [0],
        "tags": ["linked-lists", "pointers", "fast-slow-pointers", "reversal"],
        "class_mastery": 0.78,
        "asha_mastery": 0.82,
    },
    {
        "name": "Trees & BSTs",
        "unit": "Unit 3",
        "description": "Binary search trees, AVL self-balancing, DFS traversals (in/pre/post), and tree serialization.",
        "prereq_indices": [1],
        "tags": ["trees", "bst", "avl", "dfs", "traversals", "recursion"],
        "class_mastery": 0.66,
        "asha_mastery": 0.72,
    },
    {
        "name": "Graph Theory",
        "unit": "Unit 4",
        "description": "Adjacency structures, BFS/DFS exploration, Dijkstra shortest path, and topological sorting.",
        "prereq_indices": [2],
        "tags": ["graphs", "bfs", "dfs", "dijkstra", "topological-sort"],
        "class_mastery": 0.61,
        "asha_mastery": 0.65,
    },
    {
        "name": "Dynamic Programming",
        "unit": "Unit 5",
        "description": "Recurrence relations, memoization tables, bottom-up tabulation, and knapsack variations.",
        "prereq_indices": [2, 3],
        "tags": ["dp", "dynamic-programming", "memoization", "tabulation", "knapsack", "recurrence"],
        "class_mastery": 0.48, # Critical Bottleneck
        "asha_mastery": 0.48,
    },
    {
        "name": "Greedy Algorithms",
        "unit": "Unit 6",
        "description": "Optimal substructure proofs, interval scheduling, Huffman prefix codes, and minimum spanning trees.",
        "prereq_indices": [4],
        "tags": ["greedy", "intervals", "huffman", "mst", "kruskal", "prim"],
        "class_mastery": 0.59,
        "asha_mastery": 0.58,
    },
]

FLAGGED_AT_RISK = [
    {"name": "Marcus Vance", "email": "mvance@campus.edu", "sec": "Section A1", "blocker": "DP Recurrence Relations", "mastery": 0.32, "drops": 2, "inactive": 5},
    {"name": "Priya Patel", "email": "ppatel@campus.edu", "sec": "Section B2", "blocker": "Base Case Memorization", "mastery": 0.384, "drops": 3, "inactive": 2},
    {"name": "Ethan Thorne", "email": "ethorne@campus.edu", "sec": "Section C1", "blocker": "Graph Traversal Traps", "mastery": 0.441, "drops": 1, "inactive": 6},
    {"name": "Samantha Diaz", "email": "sdiaz@campus.edu", "sec": "Section A1", "blocker": "BST Rebalancing", "mastery": 0.391, "drops": 2, "inactive": 4},
    {"name": "Kofi Mensah", "email": "kmensah@campus.edu", "sec": "Section B2", "blocker": "Recursion Tree Unrolling", "mastery": 0.465, "drops": 1, "inactive": 3},
]


def seed_stitch_data(db: Session, seed: int = 42) -> Dict[str, Any]:
    Base.metadata.create_all(bind=engine)
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)

    # 1. Clean existing records
    logger.info("Purging old records for fresh seed...")
    for model in [
        ExperimentMetricsRollup, ClassTopicMasteryRollup, LearnerEngagementRollup,
        ExperimentAssignment, Arm, Experiment, Recommendation, Attempt, InteractionEvent,
        MasteryScore, Question, ContentItem, Topic, Course, User
    ]:
        db.execute(delete(model))
    db.commit()

    accounts_repo = AccountsRepository(db)
    content_svc = ContentService(db)
    recommender_repo = RecommenderRepository(db)

    default_hash = get_password_hash("password123")

    # 2. Key Personas
    logger.info("Creating primary personas (Asha, Prof. Rao, Admin)...")
    asha = accounts_repo.create_user("asha@campus.edu", default_hash, "learner")
    accounts_repo.record_consent(asha.user_id) # Consent recorded for ML tracking

    prof_rao = accounts_repo.create_user("profr@campus.edu", default_hash, "instructor")

    # Administrator credential governance: require private password or gate demo behind explicit local-only mode
    admin_password = os.getenv("ADMIN_PASSWORD")
    is_local_demo = (
        settings.ENVIRONMENT in ("development", "local", "test")
        and os.getenv("ALLOW_LOCAL_DEMO_ADMIN", "false").lower() in ("true", "1")
    )

    if admin_password and admin_password.strip():
        admin_hash = get_password_hash(admin_password.strip())
        admin = accounts_repo.create_user("admin@campus.edu", admin_hash, "administrator")
    elif is_local_demo:
        logger.info("Local-only demo mode: creating local development administrator.")
        admin = accounts_repo.create_user("admin@campus.edu", default_hash, "administrator")
    else:
        logger.warning(
            "Automatic admin seeding skipped: configure ADMIN_PASSWORD in environment to provision an administrator account."
        )
        admin = None

    # 3. Primary Course (CS 301)
    logger.info("Creating Course: CS 301: Advanced Data Structures & Algorithms...")
    cs301 = content_svc.create_course(
        CourseCreate(
            title="CS 301: Advanced Data Structures & Algorithms",
            description="Real-time learner progress, dynamic difficulty calibration, and personalized intervention pathways.",
            instructor_id=prof_rao.user_id
        )
    )

    # 4. Topics & Prerequisite Hierarchy
    created_topics = []
    for t_idx, t_def in enumerate(STITCH_TOPICS):
        prereqs = [str(created_topics[p].topic_id) for p in t_def["prereq_indices"]]
        topic = content_svc.create_topic(
            TopicCreate(
                course_id=cs301.course_id,
                name=t_def["name"],
                prerequisite_topic_ids=prereqs
            )
        )
        created_topics.append(topic)

    # 5. Content Items & Questions
    created_items = []
    created_questions = []

    content_types = ["interactive", "video", "exercise", "text"]
    for t_idx, topic in enumerate(created_topics):
        t_def = STITCH_TOPICS[t_idx]
        for item_idx in range(1, 9):
            diff = ((item_idx - 1) % 5) + 1
            c_type = content_types[(item_idx - 1) % len(content_types)]
            duration = rng.randint(5, 20) * 60
            tags = list(set(t_def["tags"] + [f"difficulty-{diff}", c_type]))
            prereqs = [str(created_topics[p].topic_id) for p in t_def["prereq_indices"]]

            item = content_svc.create_content_item(
                ContentItemCreate(
                    topic_id=topic.topic_id,
                    title=f"{topic.name}: {c_type.title()} Drill {item_idx}",
                    type=c_type,
                    difficulty=diff,
                    duration=duration,
                    tags=tags,
                    prerequisite_topic_ids=prereqs
                )
            )
            created_items.append(item)

        # Questions for adaptive quiz
        for q_idx in range(1, 16):
            diff_float = round(0.15 + (q_idx - 1) * 0.05, 2)
            q = content_svc.create_question(
                QuestionCreate(
                    topic_id=topic.topic_id,
                    prompt=f"[{topic.name}] Concept Drill #{q_idx}: Which algorithmic approach minimizes runtime?",
                    difficulty=min(0.95, diff_float),
                    correct_answer="Option A: Optimized Two-Pointer / Recurrence with memoization",
                    options=[
                        "Option A: Optimized Two-Pointer / Recurrence with memoization",
                        "Option B: Brute-force nested loops O(N^2)",
                        "Option C: Random heuristic search without guarantees",
                        "Option D: Greedy step with unverified choice property"
                    ]
                )
            )
            created_questions.append(q)

    # 6. Flagged At-Risk Students & 342 Total Students
    cohort_learners = [asha]
    for stu in FLAGGED_AT_RISK:
        u = accounts_repo.create_user(stu["email"], default_hash, "learner")
        accounts_repo.record_consent(u.user_id)
        cohort_learners.append(u)

    # Fill remainder of 342 students
    needed = 342 - len(cohort_learners)
    for i in range(1, needed + 1):
        u = accounts_repo.create_user(f"student_{i:03d}@campus.edu", default_hash, "learner")
        cohort_learners.append(u)

    logger.info(f"Seeded {len(cohort_learners)} students into CS 301 cohort.")

    # 7. Mastery Scores & Attempts
    # Set Asha's mastery
    for t_idx, topic in enumerate(created_topics):
        t_def = STITCH_TOPICS[t_idx]
        db.add(
            MasteryScore(
                user_id=asha.user_id,
                topic_id=topic.topic_id,
                score=t_def["asha_mastery"],
                confidence=0.88,
                updated_at=now - timedelta(hours=2)
            )
        )
        # Log completed interaction event
        db.add(
            InteractionEvent(
                event_id=uuid.uuid4(),
                user_id=asha.user_id,
                content_id=created_items[t_idx * 8].content_id,
                event_type="completed",
                duration=720,
                timestamp=now - timedelta(days=1)
            )
        )

    # Set Cohort Mastery
    for learner in cohort_learners[1:]:
        is_at_risk = any(learner.email == stu["email"] for stu in FLAGGED_AT_RISK)
        for t_idx, topic in enumerate(created_topics):
            t_def = STITCH_TOPICS[t_idx]
            if is_at_risk:
                score = round(max(0.15, min(0.50, t_def["class_mastery"] - 0.25 + rng.uniform(-0.05, 0.05))), 4)
            else:
                score = round(max(0.35, min(0.95, t_def["class_mastery"] + rng.uniform(-0.10, 0.10))), 4)
            
            db.add(
                MasteryScore(
                    user_id=learner.user_id,
                    topic_id=topic.topic_id,
                    score=score,
                    confidence=0.75,
                    updated_at=now - timedelta(days=rng.randint(0, 4))
                )
            )

    # 8. Set up A/B Experiment #04 (Rule vs Hybrid)
    logger.info("Setting up A/B Experiment #04 (Rule vs Hybrid)...")
    exp = Experiment(
        experiment_id=uuid.uuid4(),
        name="Exp #04: Rule-Based (Arm A) vs. Embedding-Hybrid Vector Engine (Arm B)",
        status="active",
        created_at=now - timedelta(days=14)
    )
    db.add(exp)
    db.flush()

    arm_a = Arm(
        arm_id=uuid.uuid4(),
        experiment_id=exp.experiment_id,
        name="Arm A (Rule-Based)",
        strategy="rules",
        parameters={"w1": 0.4, "w2": 0.3, "w3": 0.2, "w4": 0.1}
    )
    arm_b = Arm(
        arm_id=uuid.uuid4(),
        experiment_id=exp.experiment_id,
        name="Arm B (Embedding-Hybrid Vector)",
        strategy="embeddings",
        parameters={"alpha": 0.5, "w1": 0.4, "w2": 0.3, "w3": 0.2, "w4": 0.1}
    )
    db.add(arm_a)
    db.add(arm_b)
    db.flush()

    # Assign Asha to Arm B (Hybrid)
    db.add(
        ExperimentAssignment(
            user_id=asha.user_id,
            experiment_id=exp.experiment_id,
            arm_id=arm_b.arm_id,
            assigned_at=now - timedelta(days=7)
        )
    )

    db.commit()

    # 9. Precompute Rollups for Instant Query Speed
    logger.info("Running precomputed rollup jobs...")
    rollup_counts = run_rollup_job(db)

    # 10. Generate Initial ML Recommendations for Asha
    from app.modules.recommender.service import RecommenderService
    rec_service = RecommenderService(db)
    recs = rec_service.get_recommendations(user_id=asha.user_id, course_id=cs301.course_id, limit=4)
    logger.info(f"Generated {len(recs.items)} initial ML recommendations for Asha.")

    return {
        "status": "success",
        "course_id": str(cs301.course_id),
        "asha_id": str(asha.user_id),
        "profr_id": str(prof_rao.user_id),
        "admin_id": str(admin.user_id) if admin else None,
        "experiment_id": str(exp.experiment_id),
        "arm_a_id": str(arm_a.arm_id),
        "arm_b_id": str(arm_b.arm_id),
        "topics": len(created_topics),
        "students": len(cohort_learners),
        "rollups": rollup_counts,
        "recommendations": [r.title for r in recs.items]
    }


if __name__ == "__main__":
    setup_logging()
    db = SessionLocal()
    try:
        res = seed_stitch_data(db)
        print("SEED RESULTS:", res)
    finally:
        db.close()
