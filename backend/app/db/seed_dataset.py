"""
Load the synthetic learner-interaction dataset (CSV files) into the backend database.

Place this file at  backend/app/db/seed_dataset.py  (next to seed.py) and run:

    python -m app.db.seed_dataset --data-dir "../demo data" --dry-run     # parse + validate only, no DB
    python -m app.db.seed_dataset --data-dir "../demo data" --clean       # wipe DB, then load dataset

What it does
------------
* Reads users / topics / questions / content_items / attempts / interaction_events CSVs.
  (ground_truth_skill.csv is validation-only and is NOT loaded.)
* Maps the dataset's readable string IDs (U0371, Q-T01-41, ...) to UUIDs with uuid5, so IDs are
  stable across runs and the load is idempotent (INSERT ... ON CONFLICT DO NOTHING).
* Builds the catalog the dataset was generated against: 1 course, 8 topics, 120 questions, 48 content items.
* Translates dataset values to the backend's conventions:
    - difficulty level L (1-5)  ->  question.difficulty d = (L - 0.5) / 5     (SRS 7.1)
    - estimated_minutes         ->  content duration in seconds
    - content_opened/completed/skipped -> opened/completed/skipped            (same as seed.py)
    - content type "reading"    ->  "text"                                     (same as seed.py)
* Replays the attempts through the SRS 7.1 mastery update to fill mastery_scores.
* Runs the rollup job at the end, exactly like seed.py does.

Optional columns: if you add session_id / quiz_type to Attempt and session_id / question_id to
InteractionEvent (see 0002 migration), they are filled automatically. Without them they are dropped.
"""
import argparse
import csv
import math
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:  # lazy / optional so --dry-run works without the app environment
    from app.core.logging import logger
except Exception:  # pragma: no cover
    import logging

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("seed_dataset")

# ----------------------------------------------------------------------------------------------
# Conventions
# ----------------------------------------------------------------------------------------------
NAMESPACE = uuid.UUID("6f1d2c3e-5a4b-4c8d-9e7f-0a1b2c3d4e5f")  # fixed -> deterministic UUIDs

COURSE_KEY = "programming-fundamentals"
COURSE_TITLE = "Programming Fundamentals"
COURSE_DESC = "Eight core programming topics with prerequisites (synthetic learner dataset)."
COURSE_INSTRUCTOR = "I001"

# Keep the logins documented for the backend's own seed.py.
STAFF_EMAIL_OVERRIDES = {
    "admin1@example.com": "admin@techxtract.com",
    "instructor1@example.com": "instructor1@techxtract.com",
    "instructor2@example.com": "instructor2@techxtract.com",
}

EVENT_TYPE_MAP = {
    "content_opened": "opened",
    "content_completed": "completed",
    "content_skipped": "skipped",
    "quiz_answered": "quiz_answered",
}
CONTENT_TYPE_MAP = {"reading": "text"}  # video/exercise pass through unchanged

# SRS 7.1 defaults (same values the dataset generator used on the "system" side)
ETA, BETA = 0.10, 4.0

REQUIRED_FILES = ["users", "topics", "questions", "content_items", "attempts", "interaction_events"]


def _id(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{kind}:{key}")


def read_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def parse_ts(s: str) -> datetime:
    """Dataset timestamps are naive ISO strings; treat them as UTC."""
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def difficulty_from_level(level: int) -> float:
    return round((level - 0.5) / 5, 4)


def sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


# ----------------------------------------------------------------------------------------------
# Pure transformation (no DB access)  ->  dict of table name -> list of row dicts
# ----------------------------------------------------------------------------------------------
def build_rows(data_dir: Path, password_hash: str) -> Dict[str, List[Dict[str, Any]]]:
    missing = [n for n in REQUIRED_FILES if not (data_dir / f"{n}.csv").exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing {', '.join(m + '.csv' for m in missing)} in {data_dir}. "
            "Run: python generate_dataset.py --learners 500 --seed 42 --out <dir>"
        )
    raw = {n: read_csv(data_dir / f"{n}.csv") for n in REQUIRED_FILES}
    now = datetime.now(timezone.utc)

    # ---- users -------------------------------------------------------------------------------
    user_uuid = {r["user_id"]: _id("user", r["user_id"]) for r in raw["users"]}
    users = []
    for r in raw["users"]:
        consent = parse_ts(r["consent_at"]) if r["consent_at"] else None
        users.append({
            "user_id": user_uuid[r["user_id"]],
            "email": STAFF_EMAIL_OVERRIDES.get(r["email"], r["email"]),
            "password_hash": password_hash,
            "role": r["role"],
            "consent_at": consent,
            "is_active": True,
            "created_at": consent or now,
            "updated_at": now,
        })
    if COURSE_INSTRUCTOR not in user_uuid:
        raise ValueError(f"Instructor {COURSE_INSTRUCTOR} not found in users.csv")

    # ---- course / topics ---------------------------------------------------------------------
    course_uuid = _id("course", COURSE_KEY)
    courses = [{
        "course_id": course_uuid, "title": COURSE_TITLE, "description": COURSE_DESC,
        "is_retired": False, "instructor_id": user_uuid[COURSE_INSTRUCTOR],
        "created_at": now, "updated_at": now,
    }]
    topic_uuid = {r["topic_id"]: _id("topic", r["topic_id"]) for r in raw["topics"]}
    topic_name = {r["topic_id"]: r["name"] for r in raw["topics"]}

    def prereq_ids(cell: str) -> List[str]:
        out = []
        for p in filter(None, cell.split("|")):
            if p not in topic_uuid:
                raise ValueError(f"Unknown prerequisite topic {p}")
            out.append(str(topic_uuid[p]))
        return out

    topics = [{
        "topic_id": topic_uuid[r["topic_id"]], "course_id": course_uuid, "name": r["name"],
        "prerequisite_topic_ids": prereq_ids(r["prerequisites"]), "is_retired": False,
        "created_at": now, "updated_at": now,
    } for r in raw["topics"]]

    # ---- content items -----------------------------------------------------------------------
    content_uuid = {r["content_id"]: _id("content", r["content_id"]) for r in raw["content_items"]}
    counter: Dict[str, int] = {}
    content_items = []
    for r in raw["content_items"]:
        ctype = CONTENT_TYPE_MAP.get(r["type"], r["type"])
        counter[r["topic_id"]] = counter.get(r["topic_id"], 0) + 1
        content_items.append({
            "content_id": content_uuid[r["content_id"]],
            "topic_id": topic_uuid[r["topic_id"]],
            "title": f"{topic_name[r['topic_id']]}: {ctype.title()} {counter[r['topic_id']]}",
            "type": ctype,
            "difficulty": int(r["difficulty_level"]),
            "duration": int(r["estimated_minutes"]) * 60,
            "prerequisite_topic_ids": prereq_ids(r["prerequisites"]),
            "is_retired": False,
            "created_at": now, "updated_at": now,
        })

    # ---- questions ---------------------------------------------------------------------------
    question_uuid = {r["question_id"]: _id("question", r["question_id"]) for r in raw["questions"]}
    q_level = {r["question_id"]: int(r["difficulty_level"]) for r in raw["questions"]}
    q_topic = {r["question_id"]: r["topic_id"] for r in raw["questions"]}
    questions = [{
        "question_id": question_uuid[r["question_id"]],
        "topic_id": topic_uuid[r["topic_id"]],
        "prompt": f"{topic_name[r['topic_id']]} (level {r['difficulty_level']}): "
                  f"which statement best demonstrates correct usage?",
        "difficulty": difficulty_from_level(int(r["difficulty_level"])),
        "correct_answer": f"Option {r['correct_answer']}",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "is_retired": False,
        "created_at": now, "updated_at": now,
    } for r in raw["questions"]]

    # ---- attempts (+ mastery replay) ---------------------------------------------------------
    attempts, mastery_state = [], {}
    for r in sorted(raw["attempts"], key=lambda x: (x["answered_at"], x["attempt_id"])):
        if r["user_id"] not in user_uuid:
            raise ValueError(f"Attempt {r['attempt_id']}: unknown user {r['user_id']}")
        if r["question_id"] not in question_uuid:
            raise ValueError(f"Attempt {r['attempt_id']}: unknown question {r['question_id']}")
        if q_topic[r["question_id"]] != r["topic_id"] or q_level[r["question_id"]] != int(r["difficulty_level"]):
            raise ValueError(f"Attempt {r['attempt_id']}: topic/difficulty disagree with questions.csv")
        ts, y = parse_ts(r["answered_at"]), int(r["correct"])
        attempts.append({
            "attempt_id": _id("attempt", r["attempt_id"]),
            "user_id": user_uuid[r["user_id"]],
            "question_id": question_uuid[r["question_id"]],
            "correct": bool(y),
            "time_taken": float(r["time_taken_sec"]),
            "answered_at": ts,
            # optional columns (dropped automatically if the model does not have them)
            "session_id": r["session_id"],
            "quiz_type": r["quiz_type"],
        })
        key = (r["user_id"], r["topic_id"])
        m, n, _ = mastery_state.get(key, (0.5, 0, ts))
        d = difficulty_from_level(q_level[r["question_id"]])
        m = max(0.0, min(1.0, m + ETA * (y - sigmoid(BETA * (m - d)))))   # SRS 7.1
        mastery_state[key] = (m, n + 1, ts)

    mastery = [{
        "user_id": user_uuid[u], "topic_id": topic_uuid[t],
        "score": round(m, 4),
        "confidence": round(min(0.95, 0.3 + 0.04 * n), 4),  # same convention as seed.py
        "updated_at": ts,
    } for (u, t), (m, n, ts) in mastery_state.items()]

    # ---- interaction events ------------------------------------------------------------------
    events = []
    for r in raw["interaction_events"]:
        if r["event_type"] not in EVENT_TYPE_MAP:
            raise ValueError(f"Event {r['event_id']}: unknown event_type {r['event_type']}")
        if r["user_id"] not in user_uuid:
            raise ValueError(f"Event {r['event_id']}: unknown user {r['user_id']}")
        if r["content_id"] and r["content_id"] not in content_uuid:
            raise ValueError(f"Event {r['event_id']}: unknown content {r['content_id']}")
        events.append({
            "event_id": _id("event", r["event_id"]),
            "timestamp": parse_ts(r["timestamp"]),
            "user_id": user_uuid[r["user_id"]],
            "content_id": content_uuid[r["content_id"]] if r["content_id"] else None,
            "event_type": EVENT_TYPE_MAP[r["event_type"]],
            "duration": float(r["duration_sec"]),
            # optional columns
            "session_id": r["session_id"],
            "question_id": question_uuid[r["question_id"]] if r["question_id"] else None,
        })

    return {
        "users": users, "courses": courses, "topics": topics, "content_items": content_items,
        "questions": questions, "attempts": attempts, "interaction_events": events,
        "mastery_scores": mastery,
    }


# ----------------------------------------------------------------------------------------------
# Database load
# ----------------------------------------------------------------------------------------------
def load_into_db(tables: Dict[str, List[Dict[str, Any]]], clean: bool, batch_size: int,
                 skip_mastery: bool, skip_rollups: bool) -> None:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.db.session import SessionLocal
    from app.db.models.accounts import User
    from app.db.models.content import Course, Topic, ContentItem, Question
    from app.db.models.knowledge import Attempt, MasteryScore, InteractionEvent

    plan = [  # FK-safe order
        ("users", User), ("courses", Course), ("topics", Topic), ("content_items", ContentItem),
        ("questions", Question), ("attempts", Attempt), ("interaction_events", InteractionEvent),
    ]
    if not skip_mastery:
        plan.append(("mastery_scores", MasteryScore))

    db = SessionLocal()
    try:
        if clean:
            from app.db.seed import clean_database
            clean_database(db)

        for name, model in plan:
            table = model.__table__
            cols = {c.key for c in table.columns}
            rows = tables[name]
            dropped = sorted(set(rows[0]) - cols) if rows else []
            if dropped:
                logger.info(f"{name}: columns not in model, skipped: {', '.join(dropped)}")
            stmt = pg_insert(table).on_conflict_do_nothing()
            for i in range(0, len(rows), batch_size):
                chunk = [{k: v for k, v in row.items() if k in cols} for row in rows[i:i + batch_size]]
                db.execute(stmt, chunk)
            db.commit()
            logger.info(f"{name}: {len(rows):,} rows loaded")

        if not skip_rollups:
            from app.worker.jobs import run_rollup_job
            logger.info(f"Rollups: {run_rollup_job(db)}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    import os
    ap = argparse.ArgumentParser(description="Load the CSV learner dataset into the backend database.")
    ap.add_argument("--data-dir", default=os.environ.get("DATASET_DIR", "../demo data"))
    ap.add_argument("--clean", action="store_true", help="wipe all tables first (uses app.db.seed.clean_database)")
    ap.add_argument("--dry-run", action="store_true", help="parse and validate only; no DB connection")
    ap.add_argument("--password", default="Password123!", help="password for every loaded account")
    ap.add_argument("--batch-size", type=int, default=5000)
    ap.add_argument("--skip-mastery", action="store_true", help="do not replay attempts into mastery_scores")
    ap.add_argument("--skip-rollups", action="store_true", help="do not run the rollup job afterwards")
    args = ap.parse_args()

    if args.dry_run:
        pw_hash = "DRY-RUN"
    else:
        try:
            from app.core.logging import setup_logging
            setup_logging()
        except Exception:
            pass
        from app.core.auth import get_password_hash
        pw_hash = get_password_hash(args.password)   # hash once, reuse for every account (bcrypt is slow)

    tables = build_rows(Path(args.data_dir), pw_hash)
    for name, rows in tables.items():
        logger.info(f"{name:<20}{len(rows):>9,} rows prepared")

    if args.dry_run:
        logger.info("Dry run OK: all foreign keys and value mappings validated. Nothing written.")
        return
    load_into_db(tables, args.clean, args.batch_size, args.skip_mastery, args.skip_rollups)
    logger.info("Dataset load complete.")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
