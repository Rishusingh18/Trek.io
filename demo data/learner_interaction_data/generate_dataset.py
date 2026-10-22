#!/usr/bin/env python3
"""
Synthetic learner-interaction dataset for the Personalized Learning Path Recommender.

Generates the SRS section 5 entities that describe what learners DID:
  users.csv, attempts.csv, interaction_events.csv
plus two helper files:
  ground_truth_skill.csv  hidden "true" skill per learner and topic (for validating the mastery model;
                          NOT part of the product schema)
  topics.csv, questions.csv, content_items.csv
                          a small stub catalog so the interaction rows have valid foreign keys.
                          Replace with the real catalog (dataset 1) when it exists.

How it works: every learner gets a hidden true skill per topic (correlated with prerequisite topics).
Answers are drawn from a logistic model of (skill - difficulty), content completion from persona
engagement x content-type affinity, and skill grows with practice / completed content and fades with
idle time. The adaptive quiz uses the SRS 7.1 / 7.3 rules, driven by the system's own mastery ESTIMATE
(not the hidden truth), so logs look like what the real system would produce.

Usage:  python generate_dataset.py --learners 500 --seed 42 --out data
Needs only the Python 3.10+ standard library.
"""
import argparse
import csv
import math
import random
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

REF_NOW = datetime(2026, 10, 22, 12, 0, 0)  # "today" for the dataset
BETA_GEN, GUESS, SLIP = 6.0, 0.15, 0.05    # how learners answer (generator side)
TRUE_DECAY = 0.004                          # true forgetting per idle day (differs from model's 0.01)
ETA, BETA, STRETCH = 0.10, 4.0, 0.10        # SRS 7.1 / 7.3 defaults (system side)
UP_AFTER, DOWN_AFTER = 3, 2

TOPICS = [  # topic_id, name, prerequisites (listed in a valid topological order)
    ("T01", "Variables and Types", []),
    ("T02", "Control Flow", ["T01"]),
    ("T03", "Functions", ["T02"]),
    ("T04", "Strings and Files", ["T01"]),
    ("T05", "Data Structures", ["T02"]),
    ("T06", "Error Handling", ["T03"]),
    ("T07", "Object-Oriented Programming", ["T03", "T05"]),
    ("T08", "Algorithms", ["T03", "T05"]),
]
CONTENT_TYPES = ["video", "reading", "exercise"]
EST_MIN = {"video": (10, 20), "reading": (8, 15), "exercise": (15, 30)}
PERSONAS = {  # share, ability mean, engagement, sessions mean, mean gap days, learning rate
    "fast": (0.20, 0.62, 0.90, 14, 1.5, 1.3),
    "steady": (0.40, 0.48, 0.80, 10, 2.5, 1.0),
    "struggling": (0.25, 0.30, 0.65, 8, 3.0, 0.8),
    "dropout": (0.15, 0.42, 0.55, 2, 5.0, 0.9),
}
HOURS = list(range(7, 24))
HOUR_W = [2, 3, 3, 2, 2, 2, 2, 2, 3, 3, 4, 5, 6, 6, 4, 2, 1]


def clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z))


def diff(level):          # difficulty level 1..5 -> 0..1 (0.1, 0.3, 0.5, 0.7, 0.9)
    return (level - 0.5) / 5


def level_of(d):          # 0..1 -> level 1..5
    return int(clip(round(d * 5 + 0.5), 1, 5))


def build_catalog(rng):
    topics, questions, content = [], [], []
    for t, name, pre in TOPICS:
        topics.append({"topic_id": t, "name": name, "prerequisites": "|".join(pre)})
        for lvl in range(1, 6):
            for k in range(3):
                questions.append({"question_id": f"Q-{t}-{lvl}{k + 1}", "topic_id": t,
                                  "difficulty_level": lvl, "correct_answer": rng.choice("ABCD")})
        for i, lvl in enumerate([1, 2, 3, 3, 4, 5]):
            typ = CONTENT_TYPES[i % 3]
            content.append({"content_id": f"C-{t}-{i + 1:02d}", "topic_id": t, "type": typ,
                            "difficulty_level": lvl,
                            "estimated_minutes": rng.randint(*EST_MIN[typ]),
                            "prerequisites": "|".join(pre)})
    return topics, questions, content


class Learner:
    def __init__(self, uid, persona, bank, items, rng, sink):
        self.uid, self.persona, self.bank, self.items = uid, persona, bank, items
        self.rng, self.sink = rng, sink
        _, a_mean, self.eng, self.s_mean, self.gap, self.lr = PERSONAS[persona]
        self.skill = {}
        for t, _, pre in TOPICS:
            own = rng.gauss(a_mean, 0.12)
            if pre:
                own = 0.5 * own + 0.5 * statistics.mean(self.skill[p] for p in pre)
            self.skill[t] = clip(own, 0.03, 0.97)
        self.initial = dict(self.skill)
        self.aff = {ty: rng.uniform(0.6, 1.0) for ty in CONTENT_TYPES}
        self.m = {t: 0.5 for t, _, _ in TOPICS}   # system-side mastery estimate (SRS 7.1)
        self.done, self.last_touch = set(), {}

    def event(self, etype, ts, sid, content_id="", question_id="", dur=0):
        self.sink["events"].append({"user_id": self.uid, "session_id": sid, "content_id": content_id,
                                    "question_id": question_id, "event_type": etype,
                                    "duration_sec": dur, "timestamp": ts})

    def attempt(self, t, qid, lvl, ts, sid, qtype):
        rng, d = self.rng, diff(lvl)
        p = GUESS + (1 - GUESS - SLIP) * sigmoid(BETA_GEN * (self.skill[t] - d))
        y = 1 if rng.random() < p else 0
        secs = (15 + 45 * d) * rng.lognormvariate(0, 0.35) * (1.3 - 0.6 * self.skill[t])
        secs = int(clip(secs, 3, 300))
        self.sink["attempts"].append({"user_id": self.uid, "session_id": sid, "quiz_type": qtype,
                                      "question_id": qid, "topic_id": t, "difficulty_level": lvl,
                                      "correct": y, "time_taken_sec": secs, "answered_at": ts})
        self.event("quiz_answered", ts, sid, question_id=qid, dur=secs)
        pt = sigmoid(BETA * (self.m[t] - d))                      # SRS 7.1
        self.m[t] = clip(self.m[t] + ETA * (y - pt))
        self.skill[t] = clip(self.skill[t] + self.lr * 0.004 * (1 - self.skill[t]))
        return y, secs

    def pick_question(self, t, lvl, used):
        for delta in (0, 1, -1, 2, -2, 3, -3, 4, -4):
            l = lvl + delta
            if 1 <= l <= 5:
                avail = [q for q in self.bank[(t, l)] if q not in used]
                if avail:
                    return self.rng.choice(avail), l
        raise RuntimeError("question bank exhausted")

    def run_quiz(self, t, n, now, sid):
        used, up, dn, offset = set(), 0, 0, 0
        for _ in range(n):
            lvl = int(clip(level_of(self.m[t] + STRETCH) + offset, 1, 5))   # SRS 7.3
            qid, lvl = self.pick_question(t, lvl, used)
            used.add(qid)
            y, secs = self.attempt(t, qid, lvl, now, sid, "adaptive")
            now += timedelta(seconds=secs + self.rng.randint(2, 6))
            up, dn = (up + 1, 0) if y else (0, dn + 1)
            if up >= UP_AFTER:
                offset, up = offset + 1, 0
            if dn >= DOWN_AFTER:
                offset, dn = offset - 1, 0
            offset = int(clip(offset, -4, 4))
        return now

    def study(self, t, now, sid):
        rng, items = self.rng, self.items[t]
        target = self.m[t] + STRETCH
        w = [(math.exp(-((diff(i["difficulty_level"]) - target) / 0.3) ** 2) + 0.05)
             * (0.15 if i["content_id"] in self.done else 1) for i in items]
        it = rng.choices(items, w)[0]
        cid, est = it["content_id"], it["estimated_minutes"] * 60
        self.event("content_opened", now, sid, content_id=cid)
        p = clip(self.eng * self.aff[it["type"]], 0.05, 0.97)
        r = rng.random()
        if r < p:
            dur = int(est * rng.lognormvariate(0, 0.25) * (1.15 - 0.3 * self.skill[t]))
            now += timedelta(seconds=dur)
            self.event("content_completed", now, sid, content_id=cid, dur=dur)
            self.done.add(cid)
            zpd = math.exp(-((diff(it["difficulty_level"]) - self.skill[t] - 0.1) / 0.3) ** 2)
            self.skill[t] = clip(self.skill[t] + self.lr * 0.06 * (1 - self.skill[t]) * (0.3 + 0.7 * zpd))
        elif r < p + (1 - p) * 0.6:
            dur = rng.randint(5, 40)
            now += timedelta(seconds=dur)
            self.event("content_skipped", now, sid, content_id=cid, dur=dur)
        else:                                            # abandoned: opened, never finished
            now += timedelta(seconds=int(est * rng.uniform(0.15, 0.6)))
        return now + timedelta(seconds=rng.randint(5, 30))

    def pick_topic(self):
        if self.rng.random() < 0.7:
            cands = [t for t, _, pre in TOPICS
                     if self.m[t] < 0.75 and all(self.m[p] >= 0.4 for p in pre)]
            if cands:
                return self.rng.choices(cands, [(1 - self.m[t]) ** 2 for t in cands])[0]
        return self.rng.choice([t for t, _, _ in TOPICS])

    def run(self):
        rng = self.rng
        join = REF_NOW - timedelta(days=rng.uniform(3, 120))
        join = join.replace(hour=rng.choices(HOURS, HOUR_W)[0], minute=rng.randint(0, 59), second=0)
        self.join = join
        now, sid = join, f"S-{self.uid}-00"
        for t, _, _ in TOPICS:                                        # diagnostic quiz
            for lvl in rng.sample([2, 3, 4], 3):
                qid = rng.choice(self.bank[(t, lvl)])
                _, secs = self.attempt(t, qid, lvl, now, sid, "diagnostic")
                now += timedelta(seconds=secs + rng.randint(2, 6))
        prev_end = now
        n_sessions = max(0, int(rng.gauss(self.s_mean, self.s_mean * 0.3)))
        for k in range(1, n_sessions + 1):
            start = prev_end + timedelta(days=rng.expovariate(1 / self.gap))
            start = start.replace(hour=rng.choices(HOURS, HOUR_W)[0], minute=rng.randint(0, 59),
                                  second=rng.randint(0, 59))
            if start <= prev_end:
                start += timedelta(days=1)
            if start > REF_NOW - timedelta(hours=4):
                break
            sid = f"S-{self.uid}-{k:02d}"
            for t in list(self.last_touch):                           # forgetting while idle
                days = (start - self.last_touch[t]).total_seconds() / 86400
                self.skill[t] *= math.exp(-TRUE_DECAY * days)
            topic, now = self.pick_topic(), start
            for _ in range(rng.randint(1, 3)):
                now = self.study(topic, now, sid)
            now = self.run_quiz(topic, rng.randint(5, 8), now, sid)
            self.last_touch[topic] = now
            prev_end = now


def write_csv(path, rows, cols):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c].isoformat(timespec="seconds") if isinstance(r[c], datetime) else r[c]
                        for c in cols])


def validate(users, attempts, events, truth, questions, content):
    uids = {u["user_id"] for u in users}
    assert all(a["user_id"] in uids for a in attempts + events), "unknown user_id"
    seen = set()
    for a in attempts:
        key = (a["session_id"], a["question_id"])
        assert key not in seen, f"question repeated in a session: {key}"
        seen.add(key)
    assert all(r["answered_at"] <= REF_NOW for r in attempts), "attempt in the future"
    assert all(e["timestamp"] <= REF_NOW for e in events), "event in the future"

    persona = {t["user_id"]: t["persona"] for t in truth}
    print(f"\nrows: users={len(users)} attempts={len(attempts)} events={len(events)}")
    print(f"overall accuracy: {statistics.mean(a['correct'] for a in attempts):.3f}")
    print("accuracy by difficulty level (should fall as level rises):")
    for lvl in range(1, 6):
        xs = [a["correct"] for a in attempts if a["difficulty_level"] == lvl]
        print(f"  level {lvl}: {statistics.mean(xs):.3f}  (n={len(xs)})")
    ctype = {c["content_id"]: c["type"] for c in content}
    opened, completed = defaultdict(int), defaultdict(int)
    for e in events:
        if e["event_type"] == "content_opened":
            opened[ctype[e["content_id"]]] += 1
        elif e["event_type"] == "content_completed":
            completed[ctype[e["content_id"]]] += 1
    print("completion rate by content type: " +
          ", ".join(f"{k}={completed[k] / opened[k]:.2f}" for k in sorted(opened)))
    per_user = defaultdict(int)
    for a in attempts:
        per_user[a["user_id"]] += 1
    for p in PERSONAS:
        xs = [per_user[u] for u in persona if persona[u] == p]
        print(f"  {p:<10} learners={len(xs):<4} mean attempts per learner={statistics.mean(xs):.0f}")

    # Replay the SRS 7.1 mastery update on the logged attempts and compare with the hidden truth.
    final_true = {(t["user_id"], t["topic_id"]): t["final_true_skill"] for t in truth}
    qlevel = {q["question_id"]: q["difficulty_level"] for q in questions}
    m = defaultdict(lambda: 0.5)
    for a in sorted(attempts, key=lambda r: r["answered_at"]):
        k, d = (a["user_id"], a["topic_id"]), diff(qlevel[a["question_id"]])
        m[k] = clip(m[k] + ETA * (a["correct"] - sigmoid(BETA * (m[k] - d))))
    keys = list(final_true)
    r = statistics.correlation([m[k] for k in keys], [final_true[k] for k in keys])
    print(f"\nreplayed mastery vs hidden true skill: Pearson r = {r:.2f} (over {len(keys)} learner-topic pairs)")
    print("all integrity checks passed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--learners", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    topics, questions, content = build_catalog(rng)
    bank = defaultdict(list)
    for q in questions:
        bank[(q["topic_id"], q["difficulty_level"])].append(q["question_id"])
    items = defaultdict(list)
    for c in content:
        items[c["topic_id"]].append(c)

    sink = {"attempts": [], "events": []}
    users, truth = [], []
    names = list(PERSONAS)
    for i in range(1, args.learners + 1):
        uid = f"U{i:04d}"
        persona = rng.choices(names, [PERSONAS[n][0] for n in names])[0]
        L = Learner(uid, persona, bank, items, rng, sink)
        L.run()
        users.append({"user_id": uid, "email": f"learner{i:04d}@example.com", "role": "learner",
                      "consent_at": L.join})
        for t, _, _ in TOPICS:
            truth.append({"user_id": uid, "persona": persona, "topic_id": t,
                          "initial_true_skill": round(L.initial[t], 4),
                          "final_true_skill": round(L.skill[t], 4)})
    users += [{"user_id": "I001", "email": "instructor1@example.com", "role": "instructor", "consent_at": ""},
              {"user_id": "I002", "email": "instructor2@example.com", "role": "instructor", "consent_at": ""},
              {"user_id": "A001", "email": "admin1@example.com", "role": "administrator", "consent_at": ""}]

    for rows, key, prefix in ((sink["attempts"], "answered_at", "A"), (sink["events"], "timestamp", "E")):
        rows.sort(key=lambda r: (r[key], r["user_id"]))
        for n, r in enumerate(rows, 1):
            r["attempt_id" if prefix == "A" else "event_id"] = f"{prefix}{n:07d}"

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "users.csv", users, ["user_id", "email", "role", "consent_at"])
    write_csv(out / "attempts.csv", sink["attempts"],
              ["attempt_id", "user_id", "session_id", "quiz_type", "question_id", "topic_id",
               "difficulty_level", "correct", "time_taken_sec", "answered_at"])
    write_csv(out / "interaction_events.csv", sink["events"],
              ["event_id", "user_id", "session_id", "content_id", "question_id", "event_type",
               "duration_sec", "timestamp"])
    write_csv(out / "ground_truth_skill.csv", truth,
              ["user_id", "persona", "topic_id", "initial_true_skill", "final_true_skill"])
    write_csv(out / "topics.csv", topics, ["topic_id", "name", "prerequisites"])
    write_csv(out / "questions.csv", questions,
              ["question_id", "topic_id", "difficulty_level", "correct_answer"])
    write_csv(out / "content_items.csv", content,
              ["content_id", "topic_id", "type", "difficulty_level", "estimated_minutes", "prerequisites"])
    print(f"wrote 7 CSV files to {out.resolve()}")
    validate(users, sink["attempts"], sink["events"], truth, questions, content)


if __name__ == "__main__":
    main()
