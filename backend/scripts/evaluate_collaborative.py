"""
Offline evaluation of the item-based collaborative strategy on the synthetic learner dataset.

For every learner with at least MIN_HISTORY completions, the last HOLDOUT completions are hidden.
The similarity table is built from everyone's remaining completions, then each learner's unseen items
are ranked and we check whether the hidden ones show up in the top K. Compared with a popularity
baseline and random ranking. A completion counts as successful when the learner's final true skill
for the item's topic is at least SUCCESS_SKILL (the offline stand-in for "mastery is not weak").

Run from backend/:
    python -m scripts.evaluate_collaborative
    python -m scripts.evaluate_collaborative --data "../demo data/learner_interaction_data"

Caveat: the data is synthetic, so this shows the pipeline works, not real-world gains.
"""
import argparse
import csv
from pathlib import Path
import random
import re
import sys
from collections import Counter, defaultdict

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.modules.recommender.strategies.collaborative import compute_item_similarity

MIN_HISTORY, HOLDOUT, TOP_K, SUCCESS_SKILL = 6, 2, 5, 0.40


def load(data: Path):
    skill = {}
    with open(data / "ground_truth_skill.csv", newline="") as f:
        for r in csv.DictReader(f):
            skill[(r["user_id"], r["topic_id"])] = float(r["final_true_skill"])
    done = defaultdict(list)  # user -> [(timestamp, content_id)]
    with open(data / "interaction_events.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["event_type"] == "content_completed":
                done[r["user_id"]].append((r["timestamp"], r["content_id"]))
    seqs = {}
    for u, rows in done.items():
        seen, seq = set(), []
        for _, cid in sorted(rows):
            if cid not in seen:
                seen.add(cid)
                seq.append(cid)
        seqs[u] = seq
    return skill, seqs


def topic_of(content_id: str) -> str:
    return re.match(r"C-(T\d+)-", content_id).group(1)   # synthetic ids look like C-T03-02


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../demo data/learner_interaction_data")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    data_path = Path(args.data)
    if not data_path.exists():
        fallback = backend_dir.parent / "demo data" / "learner_interaction_data"
        if fallback.exists():
            data_path = fallback
    skill, seqs = load(data_path)
    catalog = sorted({c for s in seqs.values() for c in s})

    train, held = {}, {}
    for u, seq in seqs.items():
        if len(seq) >= MIN_HISTORY:
            train[u], held[u] = seq[:-HOLDOUT], seq[-HOLDOUT:]
        else:
            train[u] = seq
    ok = {u: {c for c in s if skill.get((u, topic_of(c)), 0.0) >= SUCCESS_SKILL} for u, s in train.items()}
    sim = compute_item_similarity(ok)
    popularity = Counter(c for s in train.values() for c in s)

    def rank_cf(u, cands):
        mine = set(train[u])
        score = {c: sum(sim.get(c, {}).get(j, 0.0) for j in mine) for c in cands}
        return sorted(cands, key=lambda c: (-score[c], -popularity[c], c))   # ties -> popularity

    def rank_pop(u, cands):
        return sorted(cands, key=lambda c: (-popularity[c], c))

    def rank_random(u, cands):
        c = list(cands)
        rng.shuffle(c)
        return c

    methods = {"random": rank_random, "popularity": rank_pop, "collaborative": rank_cf}
    stats = {m: [0, 0.0] for m in methods}
    for u, hidden in held.items():
        cands = [c for c in catalog if c not in set(train[u])]
        for name, fn in methods.items():
            top = set(fn(u, cands)[:TOP_K])
            hits = len(top & set(hidden))
            stats[name][0] += hits > 0
            stats[name][1] += hits / len(hidden)

    n = len(held)
    print(f"learners evaluated: {n}  |  items in catalog: {len(catalog)}  |  similarity rows: {len(sim)}")
    print(f"hidden per learner: {HOLDOUT}, top-{TOP_K} ranking, success = final skill >= {SUCCESS_SKILL}\n")
    print(f"{'method':<15}{'hit@'+str(TOP_K):>10}{'recall@'+str(TOP_K):>12}")
    for name, (hit, rec) in stats.items():
        print(f"{name:<15}{hit / n:>10.3f}{rec / n:>12.3f}")


if __name__ == "__main__":
    main()
