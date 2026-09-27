# CLAUDE.md — working context for kube-sim

Read this before making changes. It's the project's memory across sessions:
what's built, why it's shaped this way, and what's next.

## What this is

`kube-sim` — a terminal game for learning real kubectl syntax by typing it,
not memorizing it. Two structured modes (tutorials, incidents), a
free-form sandbox, and a YAML Labs mode for real manifest-editing
practice. Everything runs locally, no real cluster, no network calls.
Tutorial/incident content is pre-written JSON matched via fuzzy command
comparison; YAML Labs instead validates real files the player edits in
their own editor (see yaml_lab.py in Architecture, below).

The source-of-truth docs, all already in the repo, are:
- **SPEC.md** — full original spec: data model, matching rules, feedback
  rules, modes, build order (v1–v6), constraints.
- **COMMANDS.md** — master reference of real kubectl (and helm) syntax,
  organized by category. Pull from here whenever writing new scenario JSON
  or extending which commands Sandbox mode understands, so the game always
  teaches syntax that matches the real tool.
- **GAPS.md** — an honest, periodically-updated self-assessment of what
  kube-sim does and doesn't prepare someone for (CKA exam readiness,
  real production-incident readiness). Read it before adding content so
  new scenarios target actual gaps rather than duplicating well-covered
  ground. Update it, don't just add scenarios silently, whenever a pass
  like this one closes gaps it names — future sessions should be able to
  trust it's current.

Don't duplicate content from these files elsewhere — link to them.

## Architecture (do not blur this line)

- **engine.py** — the generic step runner + command matcher. Has **zero**
  kubectl-specific logic. It only knows: read a `steps` list, show a
  prompt, compare typed input against `expected_commands` with fuzzy
  matching, show `fake_output`/`explanation`/hints. This is what makes it
  possible to later add Docker/Terraform/CI content just by dropping in
  JSON with a different `category` — don't add any `if "kubectl"` type
  branching here.
- **scenario_loader.py** — reads `scenarios/tutorials/*.json` and
  `scenarios/incidents/*.json` into dicts. No validation logic beyond
  "is it valid JSON" — schema correctness is enforced by
  `tests/test_scenario_content.py`, not by the loader.
- **scenarios/** — content, not code. One JSON file per scenario. Schema is
  documented in SPEC.md and enforced by tests.
- **yaml_lab.py** — third mode alongside tutorials/incidents, fundamentally
  different from both: instead of matching typed command strings, it
  writes a real file to `workspace/` (gitignored — genuinely per-player,
  never committed), tells the player what to build/fix, and waits while
  they edit it in their own actual editor. Typing the step's apply
  command reads the real file off disk, parses it with `yaml.safe_load`,
  and validates it against a `validate` spec (`{"kind": ..., "fields":
  {"dotted.path[0].to.field": expected_value}}`) via `get_value()`'s
  dotted-path resolver — giving per-field feedback, not just pass/fail.
  Reuses `engine.QuitScenario`/`read_input` so `exit` works the same way
  everywhere. This exists specifically because GAPS.md named "no real
  YAML-editing practice" as a structural gap nothing else in this repo
  could fix — see GAPS.md's update note on that entry.
- **sandbox.py** — separate free-form mode. `generate_state()` builds a
  random fake cluster: for each of 4-6 randomly chosen services, a
  Deployment (1-3 replica pods), a ClusterIP Service, plus 3 nodes, an
  `app-config` ConfigMap, an `app-secrets` Secret, and an event log
  derived from each pod's status. `handle_command()` does token-based
  dispatch (`verb`/`resource`/`rest`) across pods, deployments, services,
  configmaps, secrets, nodes, and events — `get`/`describe`/`logs`/`top`
  as appropriate per resource type. This is the one place it's fine to
  have kubectl-shaped parsing, since sandbox is explicitly about exploring
  live-looking cluster state rather than validating scripted steps.
  Table output goes through `render_table()`, which sizes each column to
  its widest cell (header or row) instead of a fixed width — required
  because service/pod names vary a lot in length and a fixed width let
  long names collide with the next column.
- **game.py** — entry point / main menu (Learn, Incidents, YAML Labs,
  Sandbox, Quit). `exit`/`quit` work at every prompt (menu choice,
  scenario step, YAML lab step, sandbox command) — see
  `engine.read_input` / `engine.QUIT_COMMANDS`. `play()` takes a `runner`
  parameter (defaults to `engine.run_scenario`) so the same
  attempt-tracking/completion-marking wrapper works for both
  `run_scenario` and `yaml_lab.run_yaml_lab`.
- **progress.py** — reads/writes `progress.json` (completed scenarios per
  type — tutorial/incident/yaml_lab — attempt counts per scenario id).
  `game.py` loads it once at startup, passes it into `choose_from_list` to
  render `[x]`/attempt-count markers, and calls
  `record_attempt`/`mark_completed`/`save_progress` after every run via
  the `play()` helper.

## Known environment quirk

PowerShell prepends a UTF-8 BOM (`﻿`) when you pipe a string to a
Python process's stdin (e.g. testing with `$lines | python game.py`). Real
interactive typing never has this, but redirected/piped input on Windows
can. `engine.normalize()` and `engine.read_input()` both strip it — if you
add a new place that reads raw input, route it through `read_input`,
not bare `input()`.

## Build status vs. SPEC.md's v1–v6 order

- [x] v1 — single hardcoded scenario, playable end to end
- [x] v2 — JSON loading from `/scenarios/`, menu, tutorial/incident split
- [x] v3 — `progress.json` tracking (completed scenarios, attempt counts),
      shown in the menu (`progress.py` + `game.py`'s `play()`/
      `choose_from_list()`)
- [x] v4 — hint escalation (nudge → hint after 2 wrong → reveal after 4)
- [x] v5 — sandbox/freeform mode (built ahead of order, at the user's
      request — includes random cluster generation and a keep/discard
      choice on exit, saved sessions live in `sandbox_data/saved/`)
- [ ] v6 (optional) — `python game.py add-scenario` CLI scaffold
- [x] (beyond SPEC.md) — YAML Labs mode: real file editing + structural
      validation (`yaml_lab.py`, `scenarios/yaml_labs/`), added to close
      the "no real YAML editing" gap GAPS.md named

Content: 29 tutorials, 10 incidents, 5 YAML labs, all in `scenarios/`.
Tutorials/incidents are schema-valid per `tests/test_scenario_content.py`;
YAML labs per `tests/test_yaml_lab_content.py` (which also proves every
hand-written `solution` field actually passes its own `validate` spec —
same self-consistency idea as the command-matching check, applied to
manifest content instead of command strings). Tutorials cover every COMMANDS.md
category except "Tooling & Shortcuts" (see below), plus — per GAPS.md's
gap analysis — Cluster Architecture/CKA topics COMMANDS.md never listed
at all: probes, multi-container/init pods, etcd backup/restore, static
pods, kubeadm bootstrap/upgrade, certificates, and cluster/pod security.

- tutorial-001–006: the original set (pods, deployments, services,
  scaling/rollouts, configmaps/secrets, logs/exec)
- tutorial-007–020: cluster/context/namespaces, replicasets/
  statefulsets/daemonsets, jobs/cronjobs, ingress/netpol, storage
  (pv/pvc/storageclass), RBAC/service accounts, resource quotas/HPA,
  labels/selectors/annotations, scheduling (taints/cordon/drain),
  events/diagnostics (explain/jsonpath/api-resources), apply/diff/
  manifests, CRDs, Helm, kubeconfig/multi-cluster
- tutorial-021–029: probes, multi-container/init containers, etcd
  backup/restore, static pods & control-plane troubleshooting, kubeadm
  upgrades, certificates, cluster/pod security (SecurityContext, Pod
  Security Admission), kubeadm bootstrap (init/join), Operators &
  custom controllers (builds on tutorial-018's CRDs)
- incident-006–010: ImagePullBackOff, a readiness-probe cascading
  failure, a CoreDNS outage, a silently-broken HPA (missing
  metrics-server), a NotReady node — chosen to cover common real
  incidents and "silent failure" patterns GAPS.md flagged as under-taught

Several steps deliberately combine multiple flags in one command
(set-based label selectors, `--sort-by` + events, `autoscale` with three
flags at once, `auth can-i --as=`) rather than teaching one flag at a
time. Note tutorial-023/024/025/026/028 use non-kubectl commands
(`etcdctl`, `kubeadm`, `journalctl`, `cat`, `ls`) — the engine doesn't
care, since it has zero kubectl-specific logic (see Architecture above);
this is a live proof of that design working as intended.

"Tooling & Shortcuts" (aliases, `kubectl completion`, `export KUBECONFIG`)
has no dedicated tutorial — those are shell configuration, not commands
with meaningful simulated kubectl output. Their actual content (short
resource names: po, deploy, svc, ns, cm, rs, sts, ds, cj, pv, pvc, sc, sa,
ep, ing, netpol, hpa, crd) is still taught implicitly — every tutorial
that uses a resource type accepts both its full name and short alias in
`expected_commands`.

**Extension beyond the original SPEC.md schema**: every tutorial step also
carries an optional `why` field, shown after `explanation` on a correct
answer (prefixed "Why this way:"). Where `explanation` covers what the
command did, `why` specifically compares it against other valid ways to do
the same thing (e.g. `kubectl run` vs `kubectl apply -f`, `describe` vs
`-o yaml`) — added at the user's request so tutorials teach judgment, not
just syntax. Enforced for all tutorials by
`test_scenario_content.py::test_tutorial_steps_have_why_field`. Incidents
don't require it (SPEC.md already lets incidents save reasoning for the
final `resolution` debrief instead).

## Testing

```
python -m pytest
```

(`pytest.ini` points it at `tests/`.) Seven files:
- `test_engine.py` — matching/normalization logic, proven kubectl-agnostic
- `test_scenario_loader.py` — JSON loading from disk
- `test_scenario_content.py` — every tutorial/incident file validated
  against the schema, parametrized per scenario id; includes a
  self-consistency check that every listed `expected_commands` string
  actually matches itself under the real matcher (catches typos when
  hand-authoring JSON)
- `test_sandbox.py` — random cluster generation invariants + free-form
  command parsing
- `test_progress.py` — progress.json read/write, completion/attempt
  tracking across all three scenario types
- `test_yaml_lab.py` — dotted-path resolution (`get_value`), manifest
  validation (`validate_manifest`), file I/O (`load_and_parse`), and the
  full `run_yaml_lab` loop with a monkeypatched `read_input` that edits a
  real temp file mid-loop (simulating "player switches to their editor")
- `test_yaml_lab_content.py` — every yaml_lab file's schema, plus the
  critical self-consistency check that each hand-written `solution`
  actually parses and passes its own `validate` spec

Run the suite after any change to `engine.py`, `scenario_loader.py`,
`sandbox.py`, `yaml_lab.py`, or any scenario JSON. Adding a new
tutorial/incident/yaml_lab file should require zero new test code — the
parametrized content tests pick it up automatically; only add a dedicated
test if the scenario needs to exercise something the generic checks don't
cover.

## Conventions / constraints to keep honoring

- No real kubectl/cluster connection anywhere — every "output" is a
  pre-written string, never a live command execution.
- Command validation is pattern/fuzzy-based, never exact string equality.
- `sandbox_data/`, `progress.json`, and `workspace/` are gitignored —
  they're local per-player state, not project content.
- Keep engine and content separate (see Architecture above) — this is the
  main thing to protect when extending the game.

## Likely next work

See GAPS.md's "still not covered" backlog for the authoritative list.
As of this pass: dynamic storage/volume mount failures, RBAC-denial as
an incident (not just a tutorial), PodDisruptionBudget-blocks-drain,
admission controllers/webhooks. Also:

1. Further Sandbox vocabulary: jobs/cronjobs, PVCs, HPA, RBAC objects are
   the next natural resources beyond pods/deployments/services/configmaps/
   secrets/nodes/events (already covered).
2. v6 scenario-scaffolding CLI, once hand-authoring JSON gets tedious.
3. Re-read GAPS.md periodically and update it — it's a living assessment,
   not a one-time writeup, and it goes stale the moment new content lands
   without a matching update.
