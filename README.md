# kube-sim

A terminal-based game for learning real DevOps command-line skills by
typing them, not memorizing them. Started as Kubernetes-only; now spans
**Kubernetes, Docker, Linux, Terraform, Networking, CI/CD, Monitoring, and
MLOps**. Runs entirely locally — no real infrastructure, no network calls,
no backend. Every command output you see is a pre-written simulated
string.

## Modes

- **Practice** — pick a category (or "All categories"), then Learn
  (tutorials) or Incidents within it.
  - **Learn (tutorials)** — short, guided scenarios that teach one concept
    at a time: create a pod, build a Docker image, run a Terraform apply,
    etc. Each correct command gets a "Why this way" note — not just what
    it did, but why that command/flag beat other valid ways to do the
    same thing.
  - **Incidents** — longer, investigative scenarios simulating real
    production problems (CrashLoopBackOff, a container that exits
    immediately, Terraform state drift, silent ML model drift...). You
    chain the right sequence of diagnostic commands to find the actual
    root cause. Ends with a debrief explaining what really happened.
- **Career Paths** — chains existing tutorials/incidents *across*
  categories into one continuous playthrough, the way these tools
  actually get used together on a job (e.g. provision infrastructure with
  Terraform → containerize with Docker → deploy to Kubernetes → automate
  with CI/CD → observe with Monitoring). Each stage is a normal scenario;
  the path just sequences them with one framing intro/outro around the
  whole thing.
- **YAML Labs** — real manifest-editing practice, not command matching.
  The game writes a real file to `workspace/`, tells you what to build or
  fix, and you edit it in your actual editor (vim, nano, VS Code —
  whatever you'd really use). Typing the apply command reads your real
  file and checks its structure field by field. This is the one skill a
  pure command-matcher can't fake, and it's the closest thing here to the
  actual CKA exam experience. (Kubernetes-only for now.)
- **Sandbox** — no scoring, no steps. The game generates a random fake
  Kubernetes cluster: several services, each with a Deployment, a
  Service, and 1-3 pods (some healthy, some randomly broken with
  `CrashLoopBackOff`/`OOMKilled`/`Pending`/`Error`), plus nodes, a
  ConfigMap, a Secret, and an event log — all consistent with each other.
  Explore it freely with `kubectl get/describe/logs/top`. On exit you
  choose to keep that cluster state for next time or throw it away.
  (Kubernetes-only for now.)

At every prompt — menu, a tutorial/incident/career-path step, a YAML lab
step, or inside sandbox — you can type `exit` or `quit` to back out.

## Running it

Requires Python 3 and PyYAML (`pip install -r requirements.txt`, or just
`pip install pyyaml` — PyYAML is only needed for YAML Labs, everything
else uses only the standard library).

```
python game.py
```

## Playing a tutorial or incident

You'll see a prompt describing a task ("Create a pod named 'my-first-pod'
using the nginx image"). Type the command you think does that.

- **Correct** → you see the simulated output, then an explanation (for
  tutorials) or you move straight to the next investigative step
  (incidents). Tutorials also show a "Why this way" note.
- **Wrong** → a short nudge. Miss twice and a hint appears. Miss four times
  and the game just shows you the expected command — this is a learning
  tool, not a test, so there's no penalty for getting stuck.

Command matching is fuzzy, not exact string comparison: `--image=nginx` and
`--image nginx` are equivalent, extra whitespace doesn't matter, case
doesn't matter, and any command in a step's list of acceptable phrasings
counts as correct. This matching is completely tool-agnostic — it works
identically whether the expected command is `kubectl`, `docker`,
`terraform`, `git`, or a plain Linux command like `grep`.

## Playing a Career Path

Same as a tutorial/incident, just longer: you're dropped into stage 1
(e.g. a Terraform tutorial), play it to completion, then automatically
move to stage 2 (e.g. Docker), and so on. Quitting mid-path stops the
whole path (re-enter it to try again from the start); completing every
stage marks the path itself complete, and — separately — credits each
individual stage's own tutorial/incident, so it also shows as done if you
browse that category directly afterward.

## Playing sandbox mode

```
kubectl get pods [-o wide]
kubectl get pod <name>
kubectl get deployments | deploy
kubectl get svc | services
kubectl get configmaps | cm
kubectl get secrets
kubectl get nodes
kubectl get events
kubectl get all
kubectl describe pod|deployment|svc|configmap|secret|node <name>
kubectl logs <name>
kubectl top pod [<name>]
kubectl top nodes
help
exit
```

Some pods will be broken (CrashLoopBackOff, OOMKilled, Pending, Error) —
the point is figuring out which ones and why, the same way you would
against a real cluster. Everything is consistent: a broken pod shows up
in its Deployment's READY count, in `get events`, and in `describe pod`'s
events section.

## Playing YAML Labs

A lab writes a real file — blank, or with a deliberate bug — under
`workspace/` in the project directory and prints its path. Open that path
in your own editor, write or fix the YAML, save it, then come back to the
terminal and type the apply command it told you (e.g.
`kubectl apply -f pod.yaml`). The game reads the file you actually saved
and checks it:

- **Passes** → simulated "created" output, explanation, why-this-way note.
- **Fails** → a list of specific problems (a missing field, a wrong value,
  or a YAML syntax error if it doesn't even parse) — not just "wrong."
  Miss twice and a hint appears; miss four times and it shows you a full
  working version of the file to compare against or copy in.

This is real file I/O — no simulated typing, no pasting into the game's
own prompt. It's the closest thing here to actual exam conditions.

## Project structure

```
game.py             entry point / main menu (category picker, career
                     paths, YAML labs, sandbox)
engine.py           generic scenario runner + fuzzy command matching
                     (zero tool-specific logic — works identically for
                     kubectl, docker, terraform, git, plain shell...)
scenario_loader.py  category-aware loading: list_categories(),
                     load_tutorials(category=None), load_incidents(...),
                     load_yaml_labs(), load_career_paths(),
                     load_all_scenarios_by_id()
career_path.py       chains existing scenarios across categories into
                     one continuous playthrough
progress.py         reads/writes progress.json (completion + attempt
                     counts, flat across all categories — ids are
                     globally unique)
sandbox.py          random cluster generator + free-form command handling
                     (Kubernetes-only)
yaml_lab.py         YAML Labs: real file editing + structural validation
                     (Kubernetes-only)
scenarios/
  kubernetes/tutorials/*.json, incidents/*.json
  docker/tutorials/*.json, incidents/*.json
  linux/, terraform/, networking/, cicd/, monitoring/, mlops/
                     — same tutorials/incidents layout per category
  yaml_labs/*.json   manifest-editing labs (not nested by category)
  career_paths/*.json  ordered lists of existing scenario ids spanning
                     2+ categories (not nested by category)
tests/               pytest suite (see Testing, below)
progress.json         local player progress (gitignored) — created on first play
sandbox_data/        local runtime state (gitignored) — active + saved
                      sandbox cluster sessions
workspace/            local YAML lab files you edit (gitignored) — reset
                      to each lab's starter content every time you enter it
commands/            one master command reference per category
                      (commands/kubernetes.md, commands/docker.md, ...)
                      — pull from the matching file when writing new
                      scenario JSON for that category
SPEC.md              the *original*, Kubernetes-only design spec — kept
                      for history; see CLAUDE.md for current architecture
GAPS.md              honest self-assessment: does this actually prepare
                      you for the CKA / real production incidents —
                      currently scoped to Kubernetes only
CLAUDE.md            working notes for AI-assisted development on this repo
```

## Adding a new scenario

**Tutorial or incident**: drop a new JSON file into
`scenarios/<category>/tutorials/` or `scenarios/<category>/incidents/`
(category = kubernetes, docker, linux, terraform, networking, cicd,
monitoring, or mlops) following the schema in SPEC.md (id, type,
category, title, difficulty, steps with
`prompt`/`expected_commands`/`fake_output`, etc — plus `why` per step,
which every tutorial in this repo carries). Pull real command syntax from
that category's `commands/<category>.md` reference so what the game
teaches matches the actual tool. **A brand-new category** just needs a
new `scenarios/<newcategory>/tutorials/` (and/or `incidents/`) folder —
`list_categories()` discovers it automatically, no code changes.

**YAML lab**: drop a new JSON file into `scenarios/yaml_labs/` with
`type: "yaml_lab"` and steps shaped like `{"file": "pod.yaml",
"starter_content": "...", "prompt": "...", "apply_commands": [...],
"validate": {"kind": "Pod", "fields": {"metadata.name": "db", ...}},
"hint": "...", "solution": "...", "fake_output": "..."}`. Field paths in
`validate.fields` use dotted notation with `[N]` for list indices (e.g.
`spec.containers[0].image`); use the string `"ANY"` as a value when a
field must exist but its exact value doesn't matter (like a random name).

**Career path**: drop a new JSON file into `scenarios/career_paths/` with
`type: "career_path"` and `{"id", "title", "intro", "steps": [existing
scenario ids in play order], "resolution"}`. No new scenario content
needed — just a sensible ordering of ids that already exist, spanning at
least two categories.

Any of the above is picked up automatically — no code changes needed. Run
the test suite afterward; the parametrized content tests validate new
files against the schema automatically, and include self-consistency
checks (a YAML lab's `solution` must pass its own `validate` spec; a
career path's `steps` must all resolve to real scenario ids).

## Testing

```
python -m pytest
```

Covers the matching engine, category-aware scenario loading, sandbox
command handling, progress tracking, the YAML Lab file-validation logic,
and the Career Path runner — and validates every scenario/lab/path JSON
file against its schema, including self-consistency checks (every
tutorial/incident's own listed commands match under the real matcher;
every YAML lab's own solution passes its own validate spec; every career
path's steps all resolve to real scenarios). Run this after any change to
the engine, loader, sandbox, yaml_lab, career_path, or scenario content.

## Is this enough to pass the CKA or handle production on your own?

Short answer, for the **Kubernetes** content specifically: helpful, not
sufficient — see **GAPS.md** for the full honest self-assessment (it
doesn't yet cover the other 7 categories, which are at an earlier content
depth — see Status below). YAML Labs closed what used to be the biggest
structural gap (no real manifest-editing practice), but there's still no
exam timer, no real apiserver validating beyond each lab's specific
checks, and no substitute for actual time on a real cluster (kind/
minikube) before the exam.

## Status / roadmap

Built so far: hardcoded single scenario → JSON-driven scenarios with a
menu → hint escalation → sandbox mode → progress tracking → full
Kubernetes tutorial coverage → CKA/production-readiness gap-filling →
YAML Labs → multi-category expansion (Docker, Linux, Terraform,
Networking, CI/CD, Monitoring, MLOps) → Career Paths chaining categories
together.

Content depth per category (tutorials / incidents):
- **Kubernetes**: 29 / 10, plus 5 YAML labs — expanded specifically to
  close CKA/production-readiness gaps (see GAPS.md)
- **Docker, Linux**: 2 / 1 each
- **Terraform, Networking, CI/CD, Monitoring, MLOps**: 1 / 1 each

The 7 non-Kubernetes categories are at "starter content" depth — every
tutorial still carries the `why` field and is fully tested, but there's
much more of each category's real command surface (see `commands/*.md`)
left to cover. Expanding them to Kubernetes-level depth is the next large
body of work.

2 Career Paths currently exist: a build-and-ship flow (Terraform → Docker
→ Kubernetes → CI/CD → Monitoring) and an incident-response chain (Linux
→ Networking → Kubernetes → Monitoring).

Not yet built:
- Deeper content for the 7 non-Kubernetes categories
- A CLI scaffold for authoring new scenario JSON
- Dynamic storage/volume mount failure scenarios, RBAC-denial as an
  incident, PodDisruptionBudget-blocks-drain, admission controllers
  (Kubernetes-specific, see GAPS.md)
- Further sandbox resources (jobs/cronjobs, PVCs, HPA, RBAC) — and a
  sandbox mode for other categories (a fake Docker host, a fake Linux
  box) is a bigger, separate idea
- More YAML labs (StatefulSet, Ingress, HPA, RBAC manifests)

See CLAUDE.md for the detailed status against the original build order and
notes for continuing development.
