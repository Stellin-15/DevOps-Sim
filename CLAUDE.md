# CLAUDE.md — working context for kube-sim

Read this before making changes. It's the project's memory across sessions:
what's built, why it's shaped this way, and what's next.

## What this is

`kube-sim` — a terminal game for learning real DevOps command-line skills
by typing them, not memorizing them. Originally Kubernetes-only; now a
multi-category simulator spanning **Kubernetes, Docker, Linux, Terraform,
Networking, CI/CD, Monitoring, and MLOps**, plus two modes that cut across
categories: **YAML Labs** (real manifest-editing practice) and **Career
Paths** (chaining scenarios across categories into one realistic
workflow, e.g. provision → containerize → deploy → automate → observe).
Everything runs locally, no real infrastructure, no network calls.
Tutorial/incident content is pre-written JSON matched via fuzzy command
comparison, category-agnostic; YAML Labs instead validates real files the
player edits in their own editor (see yaml_lab.py in Architecture).

The source-of-truth docs, all already in the repo, are:
- **SPEC.md** — the *original*, Kubernetes-only design spec (v1–v6). Kept
  for history; its matching/feedback rules and JSON schema are still
  accurate, but read this file (CLAUDE.md) for current architecture.
- **commands/*.md** — one master command reference per category
  (`commands/kubernetes.md`, `commands/docker.md`, etc). Pull from the
  matching file whenever writing new scenario JSON for that category, so
  the game always teaches syntax that matches the real tool.
- **GAPS.md** — an honest, periodically-updated self-assessment of what
  kube-sim does and doesn't prepare someone for. Part 1 is the deepest
  (Kubernetes / CKA); Parts 2-8 give each other category its own
  covered / still-missing / readiness-verdict section; Part 9 is the
  overall verdict on DevOps proficiency, with totals and a recommended
  path. Read the relevant part before adding content so new scenarios
  target real gaps. Update it in the same commit whenever content closes
  a gap it names — future sessions should be able to trust it's current.

Don't duplicate content from these files elsewhere — link to them.

## Architecture (do not blur this line)

- **engine.py** — the generic step runner + command matcher. Has **zero**
  kubectl-specific logic. It only knows: read a `steps` list, show a
  prompt, compare typed input against `expected_commands` with fuzzy
  matching, show `fake_output`/`explanation`/hints. This is what makes it
  possible to later add Docker/Terraform/CI content just by dropping in
  JSON with a different `category` — don't add any `if "kubectl"` type
  branching here.
- **scenario_loader.py** — category-aware. `list_categories()` dynamically
  discovers every subfolder of `scenarios/` that has a `tutorials/` or
  `incidents/` folder inside it (adding a category is a folder, zero code
  changes). `load_tutorials(category=None)` / `load_incidents(category=
  None)` return everything when no category is given, or just that
  category's scenarios. `load_yaml_labs()` and `load_career_paths()` read
  their own flat (non-category) folders. `load_all_scenarios_by_id()`
  returns every tutorial+incident across every category keyed by id —
  what `career_path.py` uses to resolve a path's step ids. No validation
  logic beyond "is it valid JSON" — schema correctness is enforced by
  `tests/test_scenario_content.py`, not by the loader.
- **scenarios/** — content, not code. Layout:
  `scenarios/<category>/tutorials/*.json`,
  `scenarios/<category>/incidents/*.json` for each of the 8 categories;
  `scenarios/yaml_labs/*.json` and `scenarios/career_paths/*.json` are
  flat, not nested by category. Scenario ids are globally unique across
  every category (category-prefixed except Kubernetes' original
  unprefixed `tutorial-NNN`/`incident-NNN`) — this is what lets
  `progress.json` stay flat instead of nested per category (see
  progress.py, below).
- **career_path.py** — `run_career_path(path, scenarios_by_id, progress)`
  resolves each id in `path["steps"]` via the lookup dict and runs it
  through the ordinary `engine.run_scenario`, in order, stopping at the
  first step the player quits. Records each sub-scenario's own
  attempt/completion into the shared `progress` dict as it goes (not just
  the path's own completion) — so finishing, say, the Docker tutorial via
  a career path also shows it as `[x]` when browsing Docker directly
  afterward. A missing/typo'd step id is logged and skipped, not fatal —
  but `test_career_path_content.py` catches that at test time instead of
  letting a player hit it live.
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
  everywhere. Originally built for Kubernetes manifests (GAPS.md's "no
  real YAML-editing practice" gap); now also validates GitHub Actions
  workflows, Prometheus alert rules, and Compose files. Validation
  features, all driven by lab JSON, not code:
  - `kind` is optional (required only for `category: kubernetes` labs,
    enforced by test_yaml_lab_content.py).
  - `[*]` wildcards: `jobs.test.steps[*].run` matches if ANY step has
    that value; with a list as the expected value, EVERY listed item
    must appear somewhere (e.g. `["npm ci", "npm test"]`).
  - `{"contains": [...]}` does substring checks — used for PromQL and
    `if:` expressions whose exact spacing shouldn't matter. Its failure
    message lists only the missing substrings.
  - Lenient comparison (`_equal`): strings ignore surrounding
    whitespace, numbers match their string form (`node-version: 20` vs
    `'20'`), a one-element list matches a scalar (`needs: [test]` vs
    `needs: test`). Rationale: a correct hand-written file shouldn't
    fail on formatting that the real tool accepts.
  - PyYAML follows YAML 1.1, so a workflow's unquoted `on:` key parses
    as boolean `True`; `_lookup_key` maps on/off/yes/no/true/false path
    tokens to those boolean keys so lab paths can still say `on.push`.
    (Related YAML 1.1 trap taught in yaml-011: unquoted `22:22` parses
    as the base-60 integer 1342.)
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
- **game.py** — entry point / main menu: Practice (category picker →
  Learn/Incidents within it), Career Paths, YAML Labs, Sandbox, Quit.
  `choose_category()` lists categories from `list_categories()` plus an
  "All categories" option (passes `category=None` through to the
  loaders). `exit`/`quit` work at every prompt — see `engine.read_input` /
  `engine.QUIT_COMMANDS`. `play()` takes a `runner` parameter (defaults to
  `engine.run_scenario`) so the same attempt-tracking/completion-marking
  wrapper works for `run_scenario`, `yaml_lab.run_yaml_lab`, and (via a
  lambda closing over `scenarios_by_id`/`progress`)
  `career_path.run_career_path`.
- **progress.py** — reads/writes `progress.json` (completed scenarios per
  type — tutorial/incident/yaml_lab/career_path — attempt counts per
  scenario id). Deliberately **flat, not nested per category** — every
  scenario id is already globally unique, so nesting would just be
  migration risk for no benefit. `game.py` loads it once at startup,
  passes it into `choose_from_list` to render `[x]`/attempt-count
  markers, and calls `record_attempt`/`mark_completed`/`save_progress`
  after every run via the `play()` helper.

## Known environment quirk

PowerShell prepends a UTF-8 BOM (`﻿`) when you pipe a string to a
Python process's stdin (e.g. testing with `$lines | python game.py`). Real
interactive typing never has this, but redirected/piped input on Windows
can. `engine.normalize()` and `engine.read_input()` both strip it — if you
add a new place that reads raw input, route it through `read_input`,
not bare `input()`.

## Matching-engine note

`engine.normalize()` rewrites `--flag value` to `--flag=value` so both
spellings match — but only when the next token is NOT itself a flag.
(An earlier version merged `--permanent --add-port=x` into
`--permanent=--add-port=x`, silently breaking reordered boolean flags;
`test_engine.py` has regression tests for this.) A boolean long flag
followed by a positional argument (`--rm alpine`) is still ambiguous and
is normalized consistently on both sides, so it matches as long as
argument order is the same as the expected command.

## Multi-category expansion (beyond SPEC.md entirely)

SPEC.md's v1-v6 order was written when this was Kubernetes-only. The repo
later grew a `kube-sim/` staging folder with starter content (1-2
tutorials + 1 incident each) for 7 more categories plus a redesigned
`kube-sim/SPEC.md` proposing the category-based architecture — that
folder's content has since been fully imported into `scenarios/<category>/`
and the folder itself deleted; its `commands/*.md` files live at
`commands/*.md` now, and its `SPEC.md` design became the current loader/
menu architecture described above (with one deliberate deviation: flat
progress tracking instead of nested-per-category, since ids are already
unique). The Kubernetes-only `kubernetes.md` command reference is
identical to (and replaces) the old root `COMMANDS.md`.

Current per-category content depth (tutorials / incidents):
- kubernetes: 29 / 10 (also has 9 YAML labs and Sandbox) — CKA-gap-filled
- docker: 10 / 5 (+1 YAML lab: Compose)
- linux: 12 / 6
- terraform: 10 / 6
- networking: 10 / 6
- cicd: 10 / 6 (+3 YAML labs: GitHub Actions)
- monitoring: 10 / 6 (+2 YAML labs: alert rules)
- mlops: 10 / 6
- **total: 101 tutorials, 51 incidents, 15 YAML labs**

Every category was expanded from its `commands/*.md` reference until
every command section there is covered by at least one tutorial, with
incidents modeled on the failures that actually hurt teams in that area
(each category's GAPS.md part lists them). Categories also carry a few
production-critical topics their commands file lacks (e.g. container
security in Docker, shell performance triage in Linux, OIDC and
deployment strategies in CI/CD) — noted per category in GAPS.md.

Every tutorial across every category has the `why` field (see below) —
that bar was held even for the newly-imported starter content, not just
Kubernetes.

## Career Paths

`scenarios/career_paths/*.json`: `{"id", "type": "career_path", "title",
"intro", "steps": [scenario_id, ...], "resolution"}`. `steps` just lists
existing tutorial/incident ids by id — no new scenario authoring, purely
composition of what already exists. `test_career_path_content.py` enforces
every step id resolves to a real scenario (self-consistency, same pattern
as the other content tests) and that a path spans at least 2 categories
(the whole point is combining categories, not padding one). Currently 6 paths: `path-001`
build→ship (terraform → docker → kubernetes → cicd → monitoring),
`path-002` incident chain (linux → networking → kubernetes → monitoring),
`path-003` ML model laptop→production (mlops + docker), `path-004`
security hardening layer by layer (linux → networking → docker →
kubernetes → cicd), `path-005` platform from zero (networking →
terraform → linux → kubernetes), and `path-006` "The Worst On-Call
Night" — seven incidents only, across seven categories. More paths need
no new scenario content — just new orderings of existing ids.

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
- [x] (beyond SPEC.md) — multi-category expansion to 8 categories, all
      at full depth, plus Career Paths chaining them together

**Kubernetes content specifically** (the other categories are summarized
under "Multi-category expansion" above and detailed in GAPS.md): 29
tutorials, 10 incidents, 5 YAML labs.
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

(`pytest.ini` points it at `tests/`.) Nine files:
- `test_engine.py` — matching/normalization logic, proven kubectl-agnostic
- `test_scenario_loader.py` — category-aware JSON loading (`list_categories`,
  category-filtered vs. aggregated `load_tutorials`/`load_incidents`,
  `load_all_scenarios_by_id`)
- `test_scenario_content.py` — every tutorial/incident file across every
  category validated against the schema, parametrized per scenario id;
  includes a self-consistency check that every listed `expected_commands`
  string actually matches itself under the real matcher (catches typos
  when hand-authoring JSON)
- `test_sandbox.py` — random cluster generation invariants + free-form
  command parsing (Kubernetes-only mode)
- `test_progress.py` — progress.json read/write, completion/attempt
  tracking across all four scenario types
- `test_yaml_lab.py` — dotted-path resolution (`get_value`), manifest
  validation (`validate_manifest`), file I/O (`load_and_parse`), and the
  full `run_yaml_lab` loop with a monkeypatched `read_input` that edits a
  real temp file mid-loop (simulating "player switches to their editor")
- `test_yaml_lab_content.py` — every yaml_lab file's schema, plus the
  critical self-consistency check that each hand-written `solution`
  actually parses and passes its own `validate` spec — and the converse:
  a pre-filled (broken) `starter_content` must NOT already pass, or the
  "fix this file" lab teaches nothing
- `test_career_path.py` — the run loop: completes all steps, records each
  sub-scenario into `progress` as it goes, stops cleanly on quit, skips
  (doesn't crash on) a missing scenario id
- `test_career_path_content.py` — every career_path file's schema, plus
  the self-consistency check that every step id resolves to a real
  scenario, and that a path spans 2+ categories

Run the suite after any change to `engine.py`, `scenario_loader.py`,
`sandbox.py`, `yaml_lab.py`, `career_path.py`, or any scenario JSON.
Adding a new tutorial/incident/yaml_lab/career_path file should require
zero new test code — the parametrized content tests pick it up
automatically; only add a dedicated test if the scenario needs to
exercise something the generic checks don't cover.

## Conventions / constraints to keep honoring

- No real kubectl/cluster connection anywhere — every "output" is a
  pre-written string, never a live command execution.
- Command validation is pattern/fuzzy-based, never exact string equality.
- `sandbox_data/`, `progress.json`, and `workspace/` are gitignored —
  they're local per-player state, not project content.
- Keep engine and content separate (see Architecture above) — this is the
  main thing to protect when extending the game.

## Likely next work

See GAPS.md Part 9 for the reasoning. In priority order:

1. **Non-YAML authoring labs** — Dockerfile, Terraform HCL, and bash.
   (YAML-based authoring — manifests, Actions workflows, alert rules,
   Compose — is done: 15 labs.) Each needs a small validator following
   yaml_lab.py's pattern: a Dockerfile instruction parser, HCL parsing
   (python-hcl2) or `terraform validate` if installed, and `bash -n` plus
   simple structural checks for scripts. Keep the lab JSON shape the same
   so the menu, progress, and content tests carry over.
2. Per-category exam gap passes (like Part 1 did for the CKA): e.g.
   Terraform Associate, CKAD, AWS certs.
3. Topics each GAPS.md part lists as missing: tracing/SLOs (monitoring),
   tcpdump/MTU (networking), feature stores and LLM serving (mlops),
   GitOps and supply-chain security (cicd), shell scripting (linux).
4. Sandbox modes for other categories (a fake Docker host, a fake Linux
   box) — bigger, separate efforts; sandbox.py is Kubernetes-only.
5. v6 scenario-scaffolding CLI — more valuable now that content volume
   is large.
6. Keep GAPS.md current: every content pass should update its part.
