# CLAUDE.md — working context for kube-sim

Read this before making changes. It's the project's memory across sessions:
what's built, why it's shaped this way, and what's next.

## What this is

`kube-sim` — a terminal game for learning real kubectl syntax by typing it,
not memorizing it. Two structured modes (tutorials, incidents) plus a
free-form sandbox. Everything runs locally, no real cluster, no network
calls. All content is pre-written JSON; the game engine only knows how to
read scenario JSON and fuzzy-match typed commands against it.

The two source-of-truth design docs, both already in the repo, are:
- **SPEC.md** — full original spec: data model, matching rules, feedback
  rules, modes, build order (v1–v6), constraints.
- **COMMANDS.md** — master reference of real kubectl (and helm) syntax,
  organized by category. Pull from here whenever writing new scenario JSON
  or extending which commands Sandbox mode understands, so the game always
  teaches syntax that matches the real tool.

Don't duplicate content from those two files elsewhere — link to them.

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
- **sandbox.py** — separate free-form mode. Generates a random fake
  cluster state (pods with random names/statuses/resource usage) and
  handles a small set of read-style kubectl commands
  (`get`/`describe`/`logs`/`top`) against it via token-based dispatch
  (see `handle_command`). This is the one place it's fine to have
  kubectl-shaped parsing, since sandbox is explicitly about exploring
  live-looking cluster state rather than validating scripted steps.
- **game.py** — entry point / main menu (Learn, Incidents, Sandbox, Quit).
  `exit`/`quit` work at every prompt (menu choice, scenario step, sandbox
  command) — see `engine.read_input` / `engine.QUIT_COMMANDS`.
- **progress.py** — reads/writes `progress.json` (completed scenarios per
  type, attempt counts per scenario id). `game.py` loads it once at
  startup, passes it into `choose_from_list` to render `[x]`/attempt-count
  markers, and calls `record_attempt`/`mark_completed`/`save_progress`
  after every `run_scenario` call via the `play()` helper.

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

Content: 20 tutorials, 5 incidents, all in `scenarios/`, all schema-valid
per `tests/test_scenario_content.py`. Tutorials now cover every COMMANDS.md
category except "Tooling & Shortcuts" (aliases/shell completion/
`export KUBECONFIG` — deliberately skipped, see below) — tutorial-001
through 006 were the original set (pods, deployments, services, scaling/
rollouts, configmaps/secrets, logs/exec); 007–020 cover cluster/context/
namespaces, replicasets/statefulsets/daemonsets, jobs/cronjobs, ingress/
netpol, storage (pv/pvc/storageclass), RBAC/service accounts, resource
quotas/HPA, labels/selectors/annotations, scheduling (taints/cordon/
drain), events/diagnostics (explain, jsonpath, api-resources), apply/diff/
manifests, CRDs, Helm, and kubeconfig/multi-cluster. Several steps
deliberately combine multiple flags in one command (set-based label
selectors, `--sort-by` + events, `autoscale` with three flags at once,
`auth can-i --as=`) rather than teaching one flag at a time.

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

(`pytest.ini` points it at `tests/`.) Four files:
- `test_engine.py` — matching/normalization logic, proven kubectl-agnostic
- `test_scenario_loader.py` — JSON loading from disk
- `test_scenario_content.py` — every scenario file validated against the
  schema, parametrized per scenario id; includes a self-consistency check
  that every listed `expected_commands` string actually matches itself
  under the real matcher (catches typos when hand-authoring JSON)
- `test_sandbox.py` — random cluster generation invariants + free-form
  command parsing

Run the suite after any change to `engine.py`, `scenario_loader.py`,
`sandbox.py`, or any scenario JSON. Adding a new scenario file should
require zero new test code — the parametrized content tests pick it up
automatically; only add a dedicated test if the scenario needs to exercise
something the generic checks don't cover.

## Conventions / constraints to keep honoring

- No real kubectl/cluster connection anywhere — every "output" is a
  pre-written string, never a live command execution.
- Command validation is pattern/fuzzy-based, never exact string equality.
- `sandbox_data/` and `progress.json` are gitignored — they're local
  per-player state, not project content.
- Keep engine and content separate (see Architecture above) — this is the
  main thing to protect when extending the game.

## Likely next work

1. Expand Sandbox's command vocabulary using COMMANDS.md as the source
   list (deployments, services, configmaps/secrets, nodes, events are the
   natural next additions beyond pods) — this is next up.
2. More incident content — only 5 exist vs. 20 tutorials now; incidents
   for the newer topics (RBAC denial, PVC stuck Pending, HPA not scaling,
   Ingress misrouting) would pair naturally with the tutorials just added.
3. v6 scenario-scaffolding CLI, once hand-authoring JSON gets tedious.
