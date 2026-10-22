# Learner interaction dataset (synthetic)

Regenerate: `python generate_dataset.py --learners 500 --seed 42 --out data` (Python 3.10+, no dependencies).

| File | Rows | Columns |
| --- | --- | --- |
| users.csv | 503 | user_id, email, role, consent_at (empty for staff) |
| attempts.csv | ~37k | attempt_id, user_id, session_id, quiz_type (diagnostic/adaptive), question_id, topic_id, difficulty_level (1-5), correct (0/1), time_taken_sec, answered_at |
| interaction_events.csv | ~51k | event_id, user_id, session_id, content_id, question_id, event_type (content_opened/completed/skipped, quiz_answered), duration_sec, timestamp |
| ground_truth_skill.csv | 4,000 | user_id, persona, topic_id, initial_true_skill, final_true_skill (validation only, not a product table) |
| topics / questions / content_items.csv | stub | Placeholder catalog (8 programming topics) so foreign keys resolve; replace with the real catalog |

Notes
- An "abandoned" content item is a `content_opened` with no completed/skipped event after it.
- `topic_id` and `difficulty_level` on attempts are denormalized for convenience.
- Difficulty level L maps to d = (L - 0.5) / 5 for the SRS 7.1 formulas.
- Four learner personas (fast, steady, struggling, dropout) differ in ability, engagement, session count and gaps between sessions.
