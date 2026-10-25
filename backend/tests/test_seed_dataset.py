"""
Tests for the CSV learner-dataset loader (app/db/seed_dataset.py).
Pure transformation tests: no database, no Redis, no demo-data files needed (tiny fixture is written to tmp_path).
Traces to FR-104 (consent), FR-301/FR-302 (mastery), FR-307 (events), NFR-08 (idempotent ids), NFR-13 (config-driven params).
"""
import csv
import math
import uuid

import pytest

from app.db.seed_dataset import (
    CONF_STEP,
    build_rows,
    difficulty_from_level,
    ground_truth_report,
    guard_environment,
)


def _write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def make_dataset(d, attempt_time="2026-02-01T10:00:00"):
    _write(d / "users.csv", ["user_id", "email", "role", "consent_at"], [
        ["U0001", "learner0001@example.com", "learner", "2026-01-01T00:00:00"],
        ["I001", "instructor1@example.com", "instructor", ""],
        ["A001", "admin1@example.com", "administrator", ""],
    ])
    _write(d / "topics.csv", ["topic_id", "name", "prerequisites"], [
        ["T01", "Variables", ""], ["T02", "Control Flow", "T01"],
    ])
    _write(d / "content_items.csv",
           ["content_id", "topic_id", "type", "difficulty_level", "estimated_minutes", "prerequisites"], [
               ["C-T01-01", "T01", "reading", "2", "11", ""],
               ["C-T02-01", "T02", "video", "3", "20", "T01"],
           ])
    _write(d / "questions.csv", ["question_id", "topic_id", "difficulty_level", "correct_answer"], [
        ["Q-T01-11", "T01", "1", "A"], ["Q-T01-12", "T01", "3", "B"],
    ])
    _write(d / "attempts.csv",
           ["attempt_id", "user_id", "session_id", "quiz_type", "question_id", "topic_id",
            "difficulty_level", "correct", "time_taken_sec", "answered_at"], [
               ["A1", "U0001", "S-U0001-00", "diagnostic", "Q-T01-11", "T01", "1", "1", "10", attempt_time],
               ["A2", "U0001", "S-U0001-00", "diagnostic", "Q-T01-12", "T01", "3", "0", "20", "2026-02-01T10:01:00"],
           ])
    _write(d / "interaction_events.csv",
           ["event_id", "user_id", "session_id", "content_id", "question_id", "event_type", "duration_sec", "timestamp"], [
               ["E1", "U0001", "S-U0001-00", "", "Q-T01-11", "quiz_answered", "10", attempt_time],
               ["E2", "U0001", "S-U0001-01", "C-T01-01", "", "content_completed", "300", "2026-02-02T09:00:00"],
           ])
    return d


def test_ids_are_deterministic_uuid5_nfr08(tmp_path):
    make_dataset(tmp_path)
    a, b = build_rows(tmp_path, "h"), build_rows(tmp_path, "h")
    assert [u["user_id"] for u in a["users"]] == [u["user_id"] for u in b["users"]]
    assert all(isinstance(u["user_id"], uuid.UUID) for u in a["users"])
    assert {x["attempt_id"] for x in a["attempts"]} == {x["attempt_id"] for x in b["attempts"]}


def test_value_mappings_difficulty_duration_type(tmp_path):
    make_dataset(tmp_path)
    t = build_rows(tmp_path, "h")
    assert difficulty_from_level(1) == 0.1 and difficulty_from_level(5) == 0.9
    assert sorted(q["difficulty"] for q in t["questions"]) == [0.1, 0.5]
    reading = next(c for c in t["content_items"] if c["difficulty"] == 2)
    assert reading["type"] == "text" and reading["duration"] == 11 * 60
    assert {e["event_type"] for e in t["interaction_events"]} == {"quiz_answered", "completed"}


def test_prerequisites_become_topic_uuids(tmp_path):
    make_dataset(tmp_path)
    t = build_rows(tmp_path, "h")
    t01 = next(x for x in t["topics"] if x["name"] == "Variables")
    t02 = next(x for x in t["topics"] if x["name"] == "Control Flow")
    assert t02["prerequisite_topic_ids"] == [str(t01["topic_id"])]


def test_staff_email_override_keeps_documented_logins(tmp_path):
    make_dataset(tmp_path)
    emails = {u["email"] for u in build_rows(tmp_path, "h")["users"]}
    assert {"admin@techxtract.com", "instructor1@techxtract.com"} <= emails


def _expected_mastery(eta, beta):
    sig = lambda z: 1 / (1 + math.exp(-z))
    m = 0.5
    m = m + eta * (1 - sig(beta * (m - 0.1)))
    m = m + eta * (0 - sig(beta * (m - 0.5)))
    return m


def test_mastery_replay_matches_knowledge_service_formula_fr302(tmp_path):
    make_dataset(tmp_path)
    row = build_rows(tmp_path, "h")["mastery_scores"][0]
    assert row["score"] == pytest.approx(_expected_mastery(0.10, 4.0), abs=1e-4)
    assert row["confidence"] == pytest.approx(2 * CONF_STEP)


def test_mastery_parameters_are_injectable_nfr13(tmp_path):
    make_dataset(tmp_path)
    row = build_rows(tmp_path, "h", eta=0.2, beta=2.0)["mastery_scores"][0]
    assert row["score"] == pytest.approx(_expected_mastery(0.2, 2.0), abs=1e-4)


def test_session_columns_link_attempts_and_events_fr307(tmp_path):
    make_dataset(tmp_path)
    t = build_rows(tmp_path, "h")
    sessions = {a["session_id"] for a in t["attempts"]}
    assert len(sessions) == 1 and isinstance(next(iter(sessions)), uuid.UUID)
    assert {a["quiz_type"] for a in t["attempts"]} == {"diagnostic"}
    answered = next(e for e in t["interaction_events"] if e["event_type"] == "quiz_answered")
    assert answered["session_id"] in sessions and answered["question_id"] is not None


def test_activity_before_consent_is_rejected_fr104(tmp_path):
    make_dataset(tmp_path, attempt_time="2025-12-31T23:00:00")
    with pytest.raises(ValueError, match="before consent"):
        build_rows(tmp_path, "h")


def test_unknown_foreign_key_is_rejected(tmp_path):
    make_dataset(tmp_path)
    _write(tmp_path / "questions.csv", ["question_id", "topic_id", "difficulty_level", "correct_answer"],
           [["Q-T01-11", "T01", "1", "A"]])  # Q-T01-12 referenced by attempts is gone
    with pytest.raises(ValueError, match="unknown question"):
        build_rows(tmp_path, "h")


def test_production_guard_blocks_demo_load():
    with pytest.raises(ValueError, match="production"):
        guard_environment("production", allow_production=False)
    guard_environment("development", allow_production=False)
    guard_environment("production", allow_production=True)


def test_ground_truth_report_is_validation_only(tmp_path):
    make_dataset(tmp_path)
    _write(tmp_path / "ground_truth_skill.csv",
           ["user_id", "persona", "topic_id", "initial_true_skill", "final_true_skill"],
           [["U0001", "steady", "T01", "0.4", "0.5"]])
    t = build_rows(tmp_path, "h")
    assert ground_truth_report(tmp_path, t["mastery_scores"])["pairs"] == 1
    assert "ground_truth" not in " ".join(t)  # never loaded as a table
