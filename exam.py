"""
Exam mode — timed, no hints, no feedback until the end, randomly drawn
questions. Closes GAPS.md's "no exam timer" gap: the rest of the game is a
forgiving learning tool; this is the part that tells you whether you've
actually retained it under pressure.

Questions are individual steps drawn from a category's tutorials and
incidents. Matching reuses engine.matches, so an answer is accepted
exactly when it would be accepted in normal play.
"""

import random
import re
import time
from datetime import datetime

from engine import QUIT_COMMANDS, matches, normalize, read_input

PASS_MARK = 0.66  # the CKA's published passing score
SECONDS_PER_QUESTION = 60
MAX_CONTEXT_LINES = 6


# Generated-looking identifiers: hex ids (b4c5d6e7f8a9) and hyphenated
# names containing a digit (web-7d8f9c6b5-abcde, gpu-node-1, 9f2c-44e1-b7a0).
ID_LIKE = re.compile(
    r"\b[a-z]+(?:-[a-z0-9]+)*-[a-z0-9]*\d[a-z0-9]*\b"   # web-abc123, gpu-node-1, model-v12
    r"|\b[0-9a-f]{8,}\b"                                  # b4c5d6e7f8a9
    r"|\b[0-9a-f]{4}(?:-[0-9a-f]{4})+\b"                  # 9f2c-44e1-b7a0
)


def _needed_ids(step: dict) -> set:
    return set(ID_LIKE.findall(step["expected_commands"][0]))


def build_questions(scenarios: list, count: int, rng: random.Random) -> list:
    """Flatten scenarios into single-step questions and draw `count` at
    random. Each question carries the previous step's prompt and output
    as context, because many steps ('Now check its logs') assume them.

    Later steps often reference an id (a container id, a pod name) that
    only appeared in some earlier step's output. Any earlier output line
    containing an id the answer needs is added to the context; a question
    whose needed id appears nowhere visible is left out of the exam as
    unanswerable out of order."""
    pool = []
    for scenario in scenarios:
        steps = scenario["steps"]
        intro = scenario.get("intro", "")
        for i, step in enumerate(steps):
            previous = steps[i - 1] if i > 0 else None
            lines = previous.get("fake_output", "").splitlines()[:MAX_CONTEXT_LINES] if previous else []
            visible = " ".join([intro, step["prompt"], previous["prompt"] if previous else "", "\n".join(lines)])

            unanswerable = False
            for needed in sorted(_needed_ids(step)):
                if needed in visible:
                    continue
                earlier = [l for s in steps[:i]
                           for l in [s["prompt"]] + s.get("fake_output", "").splitlines()
                           if needed in l]
                if not earlier:
                    unanswerable = True
                    break
                lines.append(earlier[-1])
                visible += " " + earlier[-1]
            if unanswerable:
                continue

            pool.append({
                "scenario": scenario["title"],
                "category": scenario.get("category"),
                "context": previous["prompt"] if previous else None,
                "context_output": "\n".join(lines),
                "prompt": step["prompt"],
                "expected_commands": step["expected_commands"],
            })
    rng.shuffle(pool)
    return pool[:count]


def _fmt(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def run_exam(questions: list, time_limit: float, clock=time.monotonic, input_fn=None) -> dict:
    """Runs the exam. Returns {"score", "total", "passed", "seconds",
    "results"} where results holds one entry per question with status
    'correct', 'wrong', 'skipped', or 'unanswered'."""
    input_fn = input_fn or read_input
    print(f"\n=== EXAM: {len(questions)} questions, {_fmt(time_limit)} ===")
    print("No hints, no feedback until the end. Type 'skip' to move on, 'exit' to end early.")

    start = clock()
    results = []
    ended_early = False

    for n, q in enumerate(questions, start=1):
        remaining = time_limit - (clock() - start)
        if remaining <= 0 or ended_early:
            results.append({**q, "status": "unanswered", "answer": None})
            continue

        print(f"\n--- Question {n}/{len(questions)}   [time left {_fmt(remaining)}] ---")
        print(f"({q['scenario']})")
        if q["context"]:
            print(f"Earlier: {q['context']}")
        if q.get("context_output"):
            print("Earlier output:")
            for line in q["context_output"].splitlines():
                print(f"  | {line}")
        print(q["prompt"])

        answer = input_fn("\n$ ")
        if normalize(answer) in QUIT_COMMANDS:
            ended_early = True
            results.append({**q, "status": "unanswered", "answer": None})
            continue
        if clock() - start > time_limit:
            print("(time expired — answer not counted)")
            results.append({**q, "status": "unanswered", "answer": answer})
            continue
        if normalize(answer) in ("skip", ""):
            results.append({**q, "status": "skipped", "answer": None})
            continue
        status = "correct" if matches(answer, q["expected_commands"]) else "wrong"
        results.append({**q, "status": status, "answer": answer})
        print("Recorded.")

    elapsed = min(clock() - start, time_limit)
    score = sum(1 for r in results if r["status"] == "correct")
    total = len(questions)
    passed = total > 0 and score / total >= PASS_MARK

    print("\n=== EXAM RESULTS ===")
    print(f"Score: {score}/{total} ({(score / total * 100) if total else 0:.0f}%)   "
          f"Pass mark: {PASS_MARK * 100:.0f}%   Time used: {_fmt(elapsed)}")
    print("PASSED" if passed else "NOT PASSED")

    misses = [r for r in results if r["status"] != "correct"]
    if misses:
        print("\nReview:")
        for r in misses:
            given = f"you typed: {r['answer']}" if r["answer"] else r["status"]
            print(f"  - {r['prompt']}\n      {given}\n      expected: {r['expected_commands'][0]}")

    return {"score": score, "total": total, "passed": passed, "seconds": round(elapsed), "results": results}


def record_result(progress: dict, category, outcome: dict) -> None:
    progress.setdefault("exam_history", []).append({
        "category": category or "all",
        "score": outcome["score"],
        "total": outcome["total"],
        "passed": outcome["passed"],
        "seconds": outcome["seconds"],
        "date": datetime.now().isoformat(timespec="seconds"),
    })


def best_percent(progress: dict, category) -> int | None:
    key = category or "all"
    scores = [e["score"] / e["total"] for e in progress.get("exam_history", [])
              if e["category"] == key and e["total"]]
    return round(max(scores) * 100) if scores else None
