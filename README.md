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
- **Sandbox** — no scoring, no steps. The game generates a random fake
  cluster: several services, each with a Deployment, a Service, and 1-3
  pods (some healthy, some randomly broken with `CrashLoopBackOff`/
  `OOMKilled`/`Pending`/`Error`), plus nodes, a ConfigMap, a Secret, and
  an event log — all consistent with each other. Explore it freely with
  `kubectl get/describe/logs/top` across any of those resource types. On
  exit you choose to keep that cluster state for next time or throw it
  away.

At every prompt — menu, a tutorial/incident step, or inside sandbox — you
can type `exit` or `quit` to back out.

## Running it

Requires Python 3.

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

## Project structure

```
game.py             entry point / main menu
engine.py           generic scenario runner + fuzzy command matching
                     (no kubectl-specific logic — reusable for any topic)
scenario_loader.py  loads scenario JSON from scenarios/
progress.py         reads/writes progress.json (completion + attempt counts)
sandbox.py          random cluster generator + free-form command handling
scenarios/
  tutorials/*.json  guided, single-concept scenarios
  incidents/*.json  investigative, multi-step production-incident scenarios
tests/               pytest suite (see Testing, below)
progress.json         local player progress (gitignored) — created on first play
sandbox_data/        local runtime state (gitignored) — active + saved
                      sandbox cluster sessions
SPEC.md              original design spec: data model, matching rules,
                      feedback rules, build order
COMMANDS.md          master reference of real kubectl/helm syntax, used as
                      the source list when writing new scenario JSON or
                      expanding sandbox's command support
CLAUDE.md            working notes for AI-assisted development on this repo
```

## Adding a new scenario

Drop a new JSON file into `scenarios/tutorials/` or `scenarios/incidents/`
following the schema in SPEC.md (id, type, category, title, difficulty,
steps with `prompt`/`expected_commands`/`fake_output`, etc). It's picked up
automatically — no code changes needed. Pull real command syntax from
COMMANDS.md so what the game teaches matches actual kubectl. Run the test
suite afterward; the scenario-content tests validate new files against the
schema automatically.

## Testing

```
python -m pytest
```

Covers the matching engine, scenario loading, sandbox command handling,
and validates every scenario JSON file against the schema (including a
self-consistency check that each scenario's own listed commands actually
match under the real matcher). Run this after any change to the engine,
loader, sandbox, or scenario content.

## Is this enough to pass the CKA or handle production on your own?

Short answer: helpful, not sufficient, for either — see **GAPS.md** for a
full honest self-assessment, including what was added specifically to
close gaps it identified, and what's still missing (mainly: real
YAML-writing practice, which a command-matching game structurally can't
simulate — get time on a real kind/minikube cluster before the exam).

## Status / roadmap

Built so far: hardcoded single scenario → JSON-driven scenarios with a
menu → hint escalation → sandbox mode → progress tracking → full tutorial
coverage of COMMANDS.md → CKA/production-readiness gap-filling (see
GAPS.md). 29 tutorials (each step explaining both what a command does and
why it's the right pick over alternatives) and 10 incidents included.

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

Sandbox covers pods, deployments, services, configmaps, secrets, nodes,
and events. Not yet built:
- A CLI scaffold for authoring new scenario JSON
- Dynamic storage/volume mount failure scenarios, RBAC-denial as an
  incident, PodDisruptionBudget-blocks-drain, admission controllers
- Further sandbox resources (jobs/cronjobs, PVCs, HPA, RBAC)

See CLAUDE.md for the detailed status against the original build order and
notes for continuing development.
