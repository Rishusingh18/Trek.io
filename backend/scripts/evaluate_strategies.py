"""Offline comparison of recommender strategies on the synthetic learner dataset."""
import argparse
import csv
import random
import uuid
from collections import Counter, defaultdict
from pathlib import Path

from app.modules.content.schemas import ContentItemResponse
from app.modules.recommender.strategies.base import LearnerContext
from app.modules.recommender.strategies.rules import RuleBasedStrategy
from app.modules.recommender.strategies.collaborative import (
    CollaborativeStrategy,
    compute_item_similarity,
)
from app.modules.recommender.strategies.embeddings import EmbeddingsStrategy


MIN_HISTORY = 6
HOLDOUT = 2
TOP_K = 5
SUCCESS_SKILL = 0.40
WEIGHTS = {"w1": 0.4, "w2": 0.3, "w3": 0.2, "w4": 0.1}


def make_id(value):
    return uuid.uuid5(uuid.NAMESPACE_URL, f"trek-eval:{value}")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_dataset(data):
    topics_rows = read_csv(data / "topics.csv")
    content_rows = read_csv(data / "content_items.csv")
    skill_rows = read_csv(data / "ground_truth_skill.csv")
    event_rows = read_csv(data / "interaction_events.csv")

    topic_names = {r["topic_id"]: r["name"] for r in topics_rows}
    topic_ids = {t: make_id(t) for t in topic_names}

    topic_prereqs = {}
    for row in topics_rows:
        prereqs = [p for p in row["prerequisites"].split("|") if p]
        topic_prereqs[topic_ids[row["topic_id"]]] = [
            topic_ids[p] for p in prereqs
        ]

    catalog = {}
    for row in content_rows:
        cid = row["content_id"]
        topic = row["topic_id"]
        difficulty = int(row["difficulty_level"])
        content_type = row["type"]

        prereqs = [p for p in row["prerequisites"].split("|") if p]
        catalog[cid] = ContentItemResponse(
            content_id=make_id(cid),
            topic_id=topic_ids[topic],
            title=f"{topic_names[topic]} {content_type} lesson level {difficulty}",
            type=content_type,
            difficulty=difficulty,
            duration=int(row["estimated_minutes"]),
            prerequisite_topic_ids=[str(topic_ids[p]) for p in prereqs],
        )

    skills = defaultdict(dict)
    for row in skill_rows:
        skills[row["user_id"]][row["topic_id"]] = {
            "initial": float(row["initial_true_skill"]),
            "final": float(row["final_true_skill"]),
        }

    completed = defaultdict(list)
    for row in event_rows:
        if row["event_type"] == "content_completed":
            completed[row["user_id"]].append(
                (row["timestamp"], row["content_id"])
            )

    sequences = {}
    for user, rows in completed.items():
        seen = set()
        sequence = []
        for _, cid in sorted(rows):
            if cid in catalog and cid not in seen:
                seen.add(cid)
                sequence.append(cid)
        sequences[user] = sequence

    return catalog, topic_ids, topic_prereqs, skills, sequences


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        default="../demo data/learner_interaction_data_eval",
    )
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    data = Path(args.data)
    if not data.exists():
        data = Path("../demo data/learner_interaction_data_eval")

    catalog, topic_ids, topic_prereqs, skills, sequences = load_dataset(data)

    eligible = {
        user: seq for user, seq in sequences.items()
        if len(seq) >= MIN_HISTORY
    }

    train = {u: seq[:-HOLDOUT] for u, seq in eligible.items()}
    held = {u: seq[-HOLDOUT:] for u, seq in eligible.items()}

    successful_by_user = {}
    for user, seq in train.items():
        successful_by_user[user] = {
            make_id(cid)
            for cid in seq
            if skills[user].get(
                next(
                    row["topic_id"]
                    for row in read_csv(data / "content_items.csv")
                    if row["content_id"] == cid
                ),
                {},
            ).get("final", 0.0) >= SUCCESS_SKILL
        }

    # Build collaborative similarities from training interactions only.
    item_similarity = compute_item_similarity(successful_by_user)

    popularity = Counter(
        cid for seq in train.values() for cid in seq
    )

    strategies = {
        "rule_based": RuleBasedStrategy(),
        "collaborative": CollaborativeStrategy(),
        "embeddings": EmbeddingsStrategy(),
    }

    stats = {
        name: [0, 0.0]
        for name in ["random", "popularity", *strategies]
    }

    rng = random.Random(args.seed)
    all_ids = set(catalog)

    for user, history in train.items():
        hidden = set(held[user])
        seen = set(history)
        candidate_ids = sorted(all_ids - seen)
        candidates = [catalog[cid] for cid in candidate_ids]

        if not candidates:
            continue

        user_id = make_id(user)
        completed_ids = {make_id(cid) for cid in history}
        completed_items = [catalog[cid] for cid in history]

        mastery = {
            topic_ids[topic]: values["initial"]
            for topic, values in skills[user].items()
            if topic in topic_ids
        }

        ctx = LearnerContext(
            user_id=user_id,
            mastery_map=mastery,
            completed_item_ids=completed_ids,
            dismissed_item_ids=set(),
            weights=WEIGHTS,
            topic_prereqs_map=topic_prereqs,
            overall_completion_rate=0.5,
            item_similarity=item_similarity,
            successful_completed_item_ids=successful_by_user[user],
            catalog=list(catalog.values()),
            completed_items=completed_items,
        )

        rankings = {}

        random_ids = candidate_ids.copy()
        rng.shuffle(random_ids)
        rankings["random"] = random_ids[:TOP_K]

        rankings["popularity"] = sorted(
            candidate_ids,
            key=lambda cid: (-popularity[cid], cid),
        )[:TOP_K]

        for name, strategy in strategies.items():
            scored = strategy.score(ctx, candidates)
            ranked = sorted(
                scored,
                key=lambda item: (-item.score, str(item.item.content_id)),
            )
            rankings[name] = [
                next(
                    cid for cid in candidate_ids
                    if catalog[cid].content_id == item.item.content_id
                )
                for item in ranked[:TOP_K]
            ]

        for name, ranked in rankings.items():
            hits = len(set(ranked) & hidden)
            stats[name][0] += hits > 0
            stats[name][1] += hits / len(hidden)

    n = len(eligible)
    print(f"learners evaluated: {n} | items in catalog: {len(catalog)}")
    print(
        f"hidden per learner: {HOLDOUT}, top-{TOP_K} ranking, "
        f"success threshold = {SUCCESS_SKILL}\n"
    )
    print(f"{'method':<16}{'hit@5':>10}{'recall@5':>12}")
    print("-" * 38)

    for name, (hit, recall) in stats.items():
        print(f"{name:<16}{hit / n:>10.3f}{recall / n:>12.3f}")


if __name__ == "__main__":
    main()
