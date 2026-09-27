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
- **Writing Labs** — real authoring practice, not command matching.
  The game writes a real file to `workspace/`, tells you what to build or
  fix, and you edit it in your actual editor (vim, nano, VS Code —
  whatever you'd really use). Typing the apply command reads your real
  file and checks it field by field. 21 labs across seven formats:
  Kubernetes manifests, GitHub Actions workflows, Prometheus alert rules,
  Docker Compose files, Dockerfiles, Terraform (HCL), and bash scripts.
  Half are "write from scratch", half are "fix this broken or dangerous
  file". This is the skill a command-matcher can't fake.
- **Exam Mode** — pick a category and a number of questions; they're drawn
  at random from that category's tutorials and incidents, one minute
  each, with **no hints and no feedback until the end** — like a real
  exam. You're scored against the CKA's real 66% pass mark, every miss is
  reviewed with the correct command, and your best score per category is
  remembered. The rest of the game is forgiving on purpose; this is the
  part that tells you whether it stuck.
- **Sandbox** — no scoring, no steps: a randomly generated broken
  environment to explore with real commands. Three to pick from:
  - **Kubernetes** — a cluster of Deployments, Services, and pods (some
    `CrashLoopBackOff`/`OOMKilled`/`Pending`/`Error`), plus nodes, a
    ConfigMap, a Secret, and an event log, all consistent with each other.
  - **Docker** — a host where one or two app containers were OOM-killed,
    crashed on startup, are stuck in a restart loop, or are failing their
    healthcheck, plus dangling images and volumes wasting disk.
  - **Linux** — a server with two hidden problems (a failed service, a
    full disk, a runaway process, a memory hog) that you must find **and
    fix**: `kill`, `systemctl restart`, `rm`, and `truncate` really change
    the state, so fixes only work if you've understood the cause.
  Pipes work everywhere (`ps aux | grep python`, `docker ps -a | grep
  Exited`). On exit you can keep the state for next time or throw it away.

At every prompt — menu, a tutorial/incident/career-path step, a YAML lab
step, or inside sandbox — you can type `exit` or `quit` to back out.

## Running it

Requires Python 3 and PyYAML (`pip install -r requirements.txt`, or just
`pip install pyyaml` — PyYAML is only needed for Writing Labs, everything
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

Type `help` inside any sandbox for its full command list. Every sandbox
supports pipes: `| grep [-i -v -c]`, `| head -N`, `| tail -N`, `| wc -l`,
`| sort`.

**Docker sandbox:** `docker ps [-a]`, `images`, `logs [--tail N]`,
`inspect <c> [--format '{{.State.ExitCode}}']` (also `.State.OOMKilled`,
`.State.Health.Status`, `.RestartCount`, and more), `stats`, `top`,
`exec <c> env`, `volume ls -f dangling=true`, `network ls/inspect`,
`system df`. Containers can be referenced by name or id prefix.

**Linux sandbox:** `uptime`, `nproc`, `free -h`, `df -h`, `du -sh <dir>/*`,
`ls -lh`, `ps aux --sort=-%cpu|-%mem`, `top`, `systemctl status|--failed|
restart <svc>`, `journalctl -u <svc> | -p err`, `dmesg -T`, `ss -tulnp`,
`lsof +L1`, and the fixes: `kill [-9] <pid>`, `rm <file>`,
`truncate -s 0 <file>`. Two things are wrong each time — you're done when
both are fixed and `systemctl --failed` and `df -h` look healthy.

**Kubernetes sandbox:**

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

## Playing Writing Labs

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
exam.py             Exam Mode: random timed questions, scoring, history
career_path.py       chains existing scenarios across categories into
                     one continuous playthrough
progress.py         reads/writes progress.json (completion + attempt
                     counts, flat across all categories — ids are
                     globally unique)
sandbox.py          Kubernetes sandbox (random cluster)
docker_sandbox.py   Docker sandbox (random broken host)
linux_sandbox.py    Linux sandbox (random broken server; reacts to fixes)
sandbox_common.py   shared sandbox loop, pipes, tables, save/discard
                     (Kubernetes-only)
yaml_lab.py         Writing Labs runner: real file editing + validation
lab_formats.py      parsers for YAML, Dockerfile, HCL, and bash lab files
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
GAPS.md              honest self-assessment per category (and overall):
                      what this prepares you for, what's still missing
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

**Writing lab**: drop a new JSON file into `scenarios/yaml_labs/` (the
folder keeps its original name) with
`type: "yaml_lab"` and steps shaped like `{"file": "pod.yaml",
"starter_content": "...", "prompt": "...", "apply_commands": [...],
"validate": {"kind": "Pod", "fields": {"metadata.name": "db", ...}},
"hint": "...", "solution": "...", "fake_output": "..."}`. Field paths in
`validate.fields` use dotted notation with `[N]` for list indices (e.g.
`spec.containers[0].image`); use the string `"ANY"` as a value when a
field must exist but its exact value doesn't matter (like a random name).
`[*]` matches any list element (`jobs.test.steps[*].run`), and with a
list as the expected value every item must appear. `{"contains": [...]}`
checks substrings (good for PromQL or `if:` expressions). `kind` is only
required for Kubernetes labs. Set `category` so the lab list labels it.
For non-YAML files add `"format": "dockerfile" | "hcl" | "bash"` to the
step; paths then refer to the parsed structure (e.g. `FROM[0]`,
`resource.aws_s3_bucket.logs.bucket`, `text`). Two more checks:
`"order": [...]` (substrings that must appear in that line order) and
`"absent": [...]` (text that must not appear, e.g. a hardcoded password).

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
command handling, progress tracking, the Writing Lab parsers and validation logic,
and the Career Path runner — and validates every scenario/lab/path JSON
file against its schema, including self-consistency checks (every
tutorial/incident's own listed commands match under the real matcher;
every YAML lab's own solution passes its own validate spec; every career
path's steps all resolve to real scenarios). Run this after any change to
the engine, loader, sandbox, yaml_lab, career_path, or scenario content.

## What's in it

| Category | Tutorials | Incidents | Topics |
|---|---|---|---|
| Kubernetes | 29 | 10 | pods → operators, full CKA coverage incl. etcd, kubeadm, certs, security; plus 9 Writing Labs and Sandbox |
| Docker | 10 | 5 | images/layers, volumes, networking, Compose, cleanup, Dockerfiles, runtime limits, container security; plus 3 Writing Labs (2 Dockerfile, Compose) |
| Linux | 12 | 6 | find, text pipelines, processes/signals, systemd, networking, users/permissions, SSH, cron, disks, performance; plus 2 bash-script Writing Labs |
| Terraform | 10 | 6 | safe CI workflow, variables/outputs, state inspection & refactoring, import, workspaces, remote state/locking, providers, debugging; plus 2 HCL Writing Labs |
| Networking | 10 | 6 | DNS, refused vs timeout, ports/nmap, routing/ARP, firewalls, TLS/openssl, HTTP/curl, in-cluster networking, CIDR |
| CI/CD | 10 | 6 | git workflows, revert vs reset, tags/releases, GitHub Actions CLI, secrets/OIDC, local CI repro, rolling/blue-green/canary; plus 3 workflow Writing Labs |
| Monitoring | 10 | 6 | PromQL, golden signals, Prometheus ops, alerting/Alertmanager, journald, Elasticsearch, Loki, Grafana API; plus 2 alert-rule Writing Labs |
| MLOps | 10 | 6 | environments, GPUs, MLflow, DVC, serving, KServe/Kubeflow, profiling, model monitoring, model canaries |
| **Total** | **101** | **51** | + 21 Writing Labs |

Plus **6 Career Paths** chaining scenarios across categories: ship a
feature end to end, a production incident chain, ML model from laptop to
production, security hardening layer by layer, building a platform from
zero, and "The Worst On-Call Night" (seven incidents, seven layers).

Every tutorial step explains not just what the command does but *why*
it beats the alternatives. Every incident ends with a debrief of the real
root cause and how to prevent it.

## Will this make me proficient in DevOps?

Honest answer — see **GAPS.md**, which assesses every category
individually (covered / still missing / readiness verdict) plus an
overall verdict in Part 9. In short: completing everything here makes
you a strong DevOps *operator* — you'll know the commands, the failure
modes, and the debugging method. To be fully proficient you also need to
practice *authoring* (Dockerfiles, Terraform, pipeline YAML, scripts),
time on real infrastructure where things break in unscripted ways, and
cloud-provider fundamentals. GAPS.md Part 9 lays out a concrete path.
For the CKA specifically, see GAPS.md Part 1.

## Status / roadmap

Built so far: hardcoded single scenario → JSON-driven scenarios with a
menu → hint escalation → sandbox → progress tracking → full Kubernetes
coverage → CKA gap-filling → Writing Labs → multi-category architecture →
Career Paths → all 8 categories expanded to full depth → Dockerfile,
Terraform, and bash Writing Labs → Exam Mode → Docker and Linux sandboxes.

Next, in priority order (details in CLAUDE.md and GAPS.md):
- **Mystery incidents** (next up) — free-form diagnosis: a symptom, any
  command in any order, scored on finding the root cause
- Exam-specific gap passes for other certifications (CKAD, Terraform
  Associate, AWS)
- Topics each GAPS.md part lists as missing (tracing/SLOs, tcpdump,
  feature stores, LLM serving, GitOps, shell scripting)
- More sandboxes (Kubernetes, Docker, and Linux exist; Terraform and
  networking would be next)
- A CLI scaffold for authoring new scenario JSON

See CLAUDE.md for architecture and notes for continuing development.
