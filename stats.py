"""
Stats screen — where you stand across every category and mode, and what to
do next. Read-only: it derives everything from progress.json plus the
loaded content, and never changes either.

build_stats() returns plain data (so it's testable); render_stats() turns
it into the text the menu prints.
"""

from exam import PASS_MARK

BAR_WIDTH = 20
MAX_SUGGESTIONS = 3
MAX_STRUGGLES = 5


def _done(items: list, completed: set) -> int:
    return sum(1 for i in items if i["id"] in completed)


def _best_exam(progress: dict, category: str):
    """Best exam ratio (0-1) for a category, or None if never taken."""
    scores = [e["score"] / e["total"] for e in progress.get("exam_history", [])
              if e["category"] == category and e["total"]]
    return max(scores) if scores else None


def build_stats(progress: dict, tutorials: list, incidents: list, labs: list,
                paths: list, mysteries: list) -> dict:
    done = {
        "tutorial": set(progress.get("tutorials_completed", [])),
        "incident": set(progress.get("incidents_completed", [])),
        "lab": set(progress.get("yaml_labs_completed", [])),
        "path": set(progress.get("career_paths_completed", [])),
        "mystery": set(progress.get("mysteries_completed", [])),
    }
    by_cat = {}

    def bucket(category):
        return by_cat.setdefault(category, {"tutorials": [], "incidents": [], "labs": [], "mysteries": []})

    for t in tutorials:
        bucket(t["category"])["tutorials"].append(t)
    for i in incidents:
        bucket(i["category"])["incidents"].append(i)
    for lab in labs:
        bucket(lab.get("category", "kubernetes"))["labs"].append(lab)
    for m in mysteries:
        bucket(m["category"])["mysteries"].append(m)

    categories = []
    for name in sorted(by_cat):
        c = by_cat[name]
        best = _best_exam(progress, name)
        row = {
            "category": name,
            "tutorials": (_done(c["tutorials"], done["tutorial"]), len(c["tutorials"])),
            "incidents": (_done(c["incidents"], done["incident"]), len(c["incidents"])),
            "labs": (_done(c["labs"], done["lab"]), len(c["labs"])),
            "mysteries": (_done(c["mysteries"], done["mystery"]), len(c["mysteries"])),
            "exam_best": None if best is None else round(best * 100),
            "exam_passed": best is not None and best >= PASS_MARK,
            "next_tutorial": next((t for t in c["tutorials"] if t["id"] not in done["tutorial"]), None),
            "next_incident": next((i for i in c["incidents"] if i["id"] not in done["incident"]), None),
            "next_mystery": next((m for m in c["mysteries"] if m["id"] not in done["mystery"]), None),
        }
        parts = [row["tutorials"], row["incidents"], row["labs"], row["mysteries"]]
        row["done"] = sum(p[0] for p in parts)
        row["total"] = sum(p[1] for p in parts)
        categories.append(row)

    titles = {s["id"]: s["title"] for s in tutorials + incidents + labs + paths + mysteries}
    struggles = sorted(((count, sid) for sid, count in progress.get("attempts", {}).items()
                        if count >= 2 and sid in titles), reverse=True)[:MAX_STRUGGLES]
    scores = progress.get("mystery_scores", {})
    exam_categories = [c for c in categories if c["tutorials"][1] or c["incidents"][1]]

    stats = {
        "categories": categories,
        "done": sum(c["done"] for c in categories) + _done(paths, done["path"]),
        "total": sum(c["total"] for c in categories) + len(paths),
        "paths": (_done(paths, done["path"]), len(paths)),
        "exams_taken": len(progress.get("exam_history", [])),
        "exams_passed": (sum(1 for c in exam_categories if c["exam_passed"]), len(exam_categories)),
        "mystery_average": round(sum(scores.values()) / len(scores)) if scores else None,
        "struggles": [{"id": sid, "title": titles[sid], "attempts": count} for count, sid in struggles],
    }
    stats["suggestions"] = suggest_next(stats)
    return stats


def suggest_next(stats: dict) -> list:
    """Up to three concrete next steps, most useful first: finish what
    you've started, prove it with an exam, then go free-form."""
    out = []
    cats = stats["categories"]
    if not any(c["tutorials"][0] for c in cats):  # no tutorial done anywhere yet
        first = next((c for c in cats if c["category"] == "kubernetes"), cats[0] if cats else None)
        if first and first["next_tutorial"]:
            out.append(f"Start here: Practice > {first['category']} > Learn > \"{first['next_tutorial']['title']}\"")
        return out

    # 1. The category you're furthest into but haven't finished learning.
    in_progress = [c for c in cats if c["next_tutorial"] and c["tutorials"][0] > 0]
    if in_progress:
        c = max(in_progress, key=lambda c: c["tutorials"][0] / c["tutorials"][1])
        left = c["tutorials"][1] - c["tutorials"][0]
        out.append(f"Finish {c['category']}'s tutorials ({left} left): next is \"{c['next_tutorial']['title']}\"")

    # 2. Tutorials done but not proven: take the exam.
    for c in cats:
        if c["tutorials"][1] and not c["next_tutorial"] and not c["exam_passed"]:
            best = f" (best so far: {c['exam_best']}%)" if c["exam_best"] is not None else ""
            out.append(f"Take the {c['category']} exam: all its tutorials are done but it isn't passed yet{best}")
            break

    # 3. Tutorials done, incidents or mysteries left.
    for c in cats:
        if c["tutorials"][1] and not c["next_tutorial"]:
            if c["next_incident"]:
                out.append(f"Work an incident in {c['category']}: \"{c['next_incident']['title']}\"")
                break
            if c["next_mystery"]:
                out.append(f"Try a mystery in {c['category']}: \"{c['next_mystery']['title']}\"")
                break

    if len(out) < MAX_SUGGESTIONS:
        untouched = next((c for c in cats if c["done"] == 0 and c["next_tutorial"]), None)
        if untouched:
            out.append(f"Start a new category: {untouched['category']} > \"{untouched['next_tutorial']['title']}\"")
    return out[:MAX_SUGGESTIONS]


def _bar(done: int, total: int) -> str:
    filled = round(BAR_WIDTH * done / total) if total else 0
    return "[" + "#" * filled + "-" * (BAR_WIDTH - filled) + "]"


def _frac(pair) -> str:
    return f"{pair[0]}/{pair[1]}" if pair[1] else "-"


def render_stats(stats: dict, labels: dict | None = None) -> str:
    labels = labels or {}
    pct = round(100 * stats["done"] / stats["total"]) if stats["total"] else 0
    lines = [
        "=== Your Progress ===",
        f"Overall  {_bar(stats['done'], stats['total'])}  {stats['done']}/{stats['total']} completed ({pct}%)",
        "",
        f"{'Category':<26}{'Learn':>8}{'Incidents':>11}{'Labs':>7}{'Mysteries':>11}   Exam (pass {round(PASS_MARK * 100)}%)",
    ]
    for c in stats["categories"]:
        if c["exam_best"] is None:
            exam = "not taken"
        else:
            exam = f"{c['exam_best']}% " + ("PASSED" if c["exam_passed"] else "not yet")
        name = labels.get(c["category"], c["category"])
        lines.append(f"{name:<26}{_frac(c['tutorials']):>8}{_frac(c['incidents']):>11}"
                     f"{_frac(c['labs']):>7}{_frac(c['mysteries']):>11}   {exam}")

    lines += ["", f"Career Paths: {_frac(stats['paths'])}    "
                  f"Exams passed: {_frac(stats['exams_passed'])} categories "
                  f"({stats['exams_taken']} taken)"]
    if stats["mystery_average"] is not None:
        lines.append(f"Mystery average (best score per solved mystery): {stats['mystery_average']}/100")

    if stats["struggles"]:
        lines += ["", "Took you the most attempts (worth a replay):"]
        lines += [f"  {s['attempts']}x  {s['title']}" for s in stats["struggles"]]

    if stats["suggestions"]:
        lines += ["", "Suggested next:"]
        lines += [f"  - {s}" for s in stats["suggestions"]]
    return "\n".join(lines)
