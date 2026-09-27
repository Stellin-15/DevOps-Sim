# kube-sim

A terminal-based game for learning real Kubernetes/kubectl commands by
typing them, not memorizing them. Runs entirely locally — no real cluster,
no network calls, no backend. Every command output you see is a pre-written
simulated string.

## Modes

- **Learn (tutorials)** — short, guided scenarios that teach one concept at
  a time: create a pod, expose a service, scale a deployment, etc. Each
  correct command gets a short explanation of *why* it was right.
- **Incidents** — longer, investigative scenarios simulating real
  production problems (CrashLoopBackOff, OOMKilled, a service that's
  unreachable, a pod stuck Pending...). You have to chain the right
  sequence of diagnostic commands to find the actual root cause. Ends with
  a debrief explaining what really happened.
- **YAML Labs** — real manifest-editing practice, not command matching.
  The game writes a real file to `workspace/`, tells you what to build or
  fix, and you edit it in your actual editor (vim, nano, VS Code —
  whatever you'd really use). Typing the apply command reads your real
  file and checks its structure field by field. This is the one skill a
  pure command-matcher can't fake, and it's the closest thing here to the
  actual CKA exam experience.
- **Sandbox** — no scoring, no steps. The game generates a random fake
  cluster: several services, each with a Deployment, a Service, and 1-3
  pods (some healthy, some randomly broken with `CrashLoopBackOff`/
  `OOMKilled`/`Pending`/`Error`), plus nodes, a ConfigMap, a Secret, and
  an event log — all consistent with each other. Explore it freely with
  `kubectl get/describe/logs/top` across any of those resource types. On
  exit you choose to keep that cluster state for next time or throw it
  away.

At every prompt — menu, a tutorial/incident step, a YAML lab step, or
inside sandbox — you can type `exit` or `quit` to back out.

## Running it

Requires Python 3 and PyYAML (`pip install -r requirements.txt`, or just
`pip install pyyaml` — PyYAML is only needed for YAML Labs, everything
else uses only the standard library).

```
python game.py
```

## Playing a tutorial or incident

You'll see a prompt describing a task ("Create a pod named 'my-first-pod'
using the nginx image"). Type the kubectl command you think does that.

- **Correct** → you see the simulated output, then an explanation (for
  tutorials) or you move straight to the next investigative step
  (incidents). Tutorials also show a "Why this way" note — not just what
  the command did, but why that command/flag was the right pick over
  other valid ways to do the same thing.
- **Wrong** → a short nudge. Miss twice and a hint appears. Miss four times
  and the game just shows you the expected command — this is a learning
  tool, not a test, so there's no penalty for getting stuck.

Command matching is fuzzy, not exact string comparison: `--image=nginx` and
`--image nginx` are equivalent, extra whitespace doesn't matter, case
doesn't matter, and any command in a step's list of acceptable phrasings
counts as correct.

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
game.py             entry point / main menu
engine.py           generic scenario runner + fuzzy command matching
                     (no kubectl-specific logic — reusable for any topic)
scenario_loader.py  loads scenario JSON from scenarios/
progress.py         reads/writes progress.json (completion + attempt counts)
sandbox.py          random cluster generator + free-form command handling
yaml_lab.py         YAML Labs: real file editing + structural validation
scenarios/
  tutorials/*.json  guided, single-concept scenarios
  incidents/*.json  investigative, multi-step production-incident scenarios
  yaml_labs/*.json  manifest-editing labs (starter/broken YAML + a
                     validate spec checked against your real saved file)
tests/               pytest suite (see Testing, below)
progress.json         local player progress (gitignored) — created on first play
sandbox_data/        local runtime state (gitignored) — active + saved
                      sandbox cluster sessions
workspace/            local YAML lab files you edit (gitignored) — reset
                      to each lab's starter content every time you enter it
SPEC.md              original design spec: data model, matching rules,
                      feedback rules, build order
COMMANDS.md          master reference of real kubectl/helm syntax, used as
                      the source list when writing new scenario JSON or
                      expanding sandbox's command support
GAPS.md              honest self-assessment: does this actually prepare
                      you for the CKA / real production incidents, and
                      what's still missing
CLAUDE.md            working notes for AI-assisted development on this repo
```

## Adding a new scenario

**Tutorial or incident**: drop a new JSON file into `scenarios/tutorials/`
or `scenarios/incidents/` following the schema in SPEC.md (id, type,
category, title, difficulty, steps with
`prompt`/`expected_commands`/`fake_output`, etc). Pull real command syntax
from COMMANDS.md so what the game teaches matches actual kubectl.

**YAML lab**: drop a new JSON file into `scenarios/yaml_labs/` with
`type: "yaml_lab"` and steps shaped like `{"file": "pod.yaml",
"starter_content": "...", "prompt": "...", "apply_commands": [...],
"validate": {"kind": "Pod", "fields": {"metadata.name": "db", ...}},
"hint": "...", "solution": "...", "fake_output": "..."}`. Field paths in
`validate.fields` use dotted notation with `[N]` for list indices (e.g.
`spec.containers[0].image`); use the string `"ANY"` as a value when a
field must exist but its exact value doesn't matter (like a random name).

Either way, it's picked up automatically — no code changes needed. Run
the test suite afterward; the parametrized content tests validate new
files against the schema automatically, and for YAML labs specifically,
confirm your `solution` actually passes your own `validate` spec (a
real typo-catcher — write this to prove your lab is actually solvable).

## Testing

```
python -m pytest
```

Covers the matching engine, scenario loading, sandbox command handling,
progress tracking, and the YAML Lab file-validation logic — and validates
every scenario/lab JSON file against its schema, including self-
consistency checks (every tutorial/incident's own listed commands match
under the real matcher; every YAML lab's own solution passes its own
validate spec). Run this after any change to the engine, loader, sandbox,
yaml_lab module, or scenario content.

## Is this enough to pass the CKA or handle production on your own?

Short answer: helpful, not sufficient, for either — see **GAPS.md** for
the full honest self-assessment. YAML Labs closed what used to be the
biggest structural gap (no real manifest-editing practice), but there's
still no exam timer, no real apiserver validating beyond each lab's
specific checks, and no substitute for actual time on a real cluster
(kind/minikube) before the exam.

## Status / roadmap

Built so far: hardcoded single scenario → JSON-driven scenarios with a
menu → hint escalation → sandbox mode → progress tracking → full tutorial
coverage of COMMANDS.md → CKA/production-readiness gap-filling → YAML
Labs (see GAPS.md for the reasoning behind each addition). 29 tutorials
(each step explaining both what a command does and why it's the right
pick over alternatives), 10 incidents, and 5 YAML labs included.

Tutorial topics: everything in COMMANDS.md (pods, deployments, services,
scaling/rollouts, configmaps/secrets, logs/exec, cluster/context/
namespaces, replicasets/statefulsets/daemonsets, jobs/cronjobs, ingress/
network policies, persistent storage, RBAC/service accounts, resource
quotas/autoscaling, labels/selectors/annotations, scheduling/node
draining, events/diagnostics, applying/diffing manifests, CRDs, Helm,
kubeconfig/multi-cluster — every category except "Tooling & Shortcuts",
since aliases/shell completion have no meaningful simulated output, though
their short resource names like `po`/`deploy`/`sts` are accepted
everywhere) — plus, beyond COMMANDS.md: probes, multi-container/init
containers, etcd backup & restore, static pods & control-plane
troubleshooting, kubeadm bootstrap & upgrades, certificate management,
cluster/pod security, and Operators & custom controllers.

Incident topics: CrashLoopBackOff, OOMKilled, service-unreachable,
pod-stuck-pending, stale ConfigMap, ImagePullBackOff, a readiness-probe
cascading failure, a CoreDNS outage, a silently-broken HPA, and a
NotReady node.

YAML lab topics: writing a Pod manifest from scratch (with resource
limits), fixing a broken Deployment (selector/template label mismatch —
a very common real mistake), a multi-container Pod with an init
container, a NetworkPolicy, and a PersistentVolumeClaim.

Sandbox covers pods, deployments, services, configmaps, secrets, nodes,
and events. Not yet built:
- A CLI scaffold for authoring new scenario JSON
- Dynamic storage/volume mount failure scenarios, RBAC-denial as an
  incident, PodDisruptionBudget-blocks-drain, admission controllers
- Further sandbox resources (jobs/cronjobs, PVCs, HPA, RBAC)
- More YAML labs (StatefulSet, Ingress, HPA, RBAC manifests)

See CLAUDE.md for the detailed status against the original build order and
notes for continuing development.
