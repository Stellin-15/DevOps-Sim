# CLAUDE.md — working context for kube-sim

Read this before making changes. It's the project's memory across sessions:
what's built, why it's shaped this way, and what's next.

## What this is

`kube-sim` — a terminal game for learning real DevOps command-line skills
by typing them, not memorizing them. Originally Kubernetes-only; now a
multi-category simulator spanning 24 categories (**Kubernetes, Docker,
Linux, Terraform, Networking, CI/CD, Monitoring, MLOps, AWS, Azure, GCP,
Security, Servers, SRE, Git, System Design, Databases, and Web Servers
& Proxies**), plus two modes that cut across
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
  (Kubernetes / CKA); every other category has its own part with a
  covered / still-missing / readiness-verdict section; the Backlog part is the
  tiered backlog of whole topics not in the game yet (commonly used,
  role-dependent, niche); the final part is the overall verdict on
  DevOps proficiency, with totals and a recommended path. Read the relevant part before adding content so new scenarios
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
  branching here. **Multiple-choice decision steps** need no engine
  support either: the prompt lists options a) to d) and ends "Type the
  letter.", and `expected_commands` is `["b"]`. System Design uses them
  for trade-off questions, with the reasoning in `why`. (This is why the
  reveal message says "The answer was:", not "The command was:".)
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
  `scenarios/yaml_labs/*.json`, `scenarios/career_paths/*.json`, and
  `scenarios/mysteries/*.json` are flat, not nested by category. Scenario ids are globally unique across
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
- **lab_formats.py** — the parsers behind Writing Labs (still called
  "yaml_lab" internally — `yaml_lab.py`, `scenarios/yaml_labs/`, type
  `yaml_lab` — renamed only in the menu, to avoid churning ids and
  progress keys). A lab step's `format` field picks the parser: `yaml`
  (default; also used for JSON such as IAM policies), `dockerfile`,
  `hcl`, `bash`, `ansible`, `markdown`, `nginx`, or `python`. Each returns a plain nested
  dict so the same dotted-path / `[*]` / `contains` checks work on every
  format: Dockerfile → `{"lines": [...], "FROM": [args...], "RUN": [...]}`,
  HCL → `{"resource": {"aws_s3_bucket": {"logs": {...}}}, "variable": ...}`,
  bash → `{"shebang", "lines", "text"}`, ansible → `{"plays": [...],
  "lines", "text"}` (a playbook is a YAML *list*, which the validator
  can't take directly), markdown → `{"title", "sections": {heading:
  body}, "headings", "lines", "text", "empty_section_count"}`, where
  sections are split on `## `. Two extra validate keys use
  them: `order` (substrings that must appear in `lines` in sequence —
  Dockerfile cache ordering, script structure) and `absent` (substrings
  that must NOT appear anywhere in the raw text — hardcoded secrets,
  unquoted `rm -rf`). Deliberately dependency-free: the HCL parser is a
  small hand-written recursive-descent parser (no python-hcl2), and the
  bash check is structural (balanced if/fi, do/done, case/esac, quotes)
  rather than shelling out to `bash -n` — because from native Windows
  Python, `bash` resolved to a launcher that hung indefinitely. The
  trade-off (documented in GAPS.md): checks confirm the right shape, not
  that `docker build`/`terraform validate`/shellcheck would pass.
- **sandbox_common.py** — shared by all six sandboxes: `render_table`,
  shell-style pipes (`split_pipes` respects quotes; `apply_pipe` supports
  grep [-i -v -c -A/-B/-C N], head/tail [-n N | -N], wc -l, sort [-r]),
  `parse_flags` (long flags, short aliases such as `-g`, boolean flags,
  and quoted values with spaces; used by the Azure and GCP sandboxes),
  `SandboxStore(kind)` for keep/discard persistence (Kubernetes keeps the
  original `sandbox_data/` root so previously saved sessions still load;
  others use `sandbox_data/<kind>/`), and `run_loop(kind, noun,
  generate_state, handle_command, describe_state)`. A sandbox module only
  supplies those three functions.
- **docker_sandbox.py** — a fake Docker host: 4-6 containers, 1-2 of the
  app containers (web/api/worker — never db/cache/proxy) with a random
  problem (oom, crash, restart_loop, unhealthy), plus dangling images and
  volumes. Read-only. Containers resolve by name or unique id prefix;
  `docker inspect --format` supports a fixed set of Go-template fields
  (INSPECT_FORMATS). `generate_state(seed)` is deterministic per seed.
- **linux_sandbox.py** — a fake server with exactly 2 of 6 random
  problems (failed_service, disk_full, runaway_cpu, memory_hog,
  cryptominer, ssh_backdoor).

  **Security state:** `state["text_files"]` holds `/etc/passwd`,
  `auth.log`, `sshd_config`, root's `authorized_keys`, and per-user
  crontabs under `/var/spool/cron/crontabs`. `cat`, `grep <pat> <file>`,
  `crontab -l/-r [-u]`, `sed -i '/pat/d'`, `userdel`,
  `awk -F: '$3 == 0'`, `last`, `ss -tnp` (established),
  `ls -l /proc/<pid>/exe`, `pkill -f`, and `iptables ... DROP` operate
  on it.

  **Respawn:** killing the miner while its cron line exists sets
  `respawn_pending`, and `_maybe_respawn` brings it back on the next
  command with a new pid. The `process_gone` goal runs that settle step
  first, so 'kill then solve' fails.

  **Other behaviour:** unlike the Docker and Kubernetes sandboxes it is
  **reactive**: `kill`, `systemctl restart|start`, `rm`,
  and `truncate` mutate state, and fixes only work in the right order
  (restarting app fails while the stray process still holds port 8080;
  postgres gets OOM-killed again while the java hog runs). Models the
  deleted-but-open-file trap: `rm` on a file a running service holds
  leaves `df` unchanged and shows up in `lsof +L1` until that service
  restarts. `df` is capped at the disk size (it once showed 102%).
- **sandbox.py** — the Kubernetes sandbox. `generate_state()` builds a
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
- **kube_sandbox.py** — the fixable Kubernetes sandbox (sandbox kind
  `kube`), separate from the random read-only `sandbox.py`. Pod status
  is **derived** on every read by `pods(state)` from the deployment
  template, ConfigMaps, nodes, and Services. The checks run in kubelet
  order: unschedulable → bad image tag → missing ConfigMap key →
  memory limit below `needs_mem` (CrashLoopBackOff, last state
  OOMKilled) → readiness path the app doesn't serve (Running 0/1).
  - Service endpoints are the Ready pods the selector matches.
  - Pod names hash the template, so a template change renames the pods
    like a new ReplicaSet. `delete pod` only bumps a generation counter.
  - Fixes: `rollout undo` (per-deployment `history`), `set
    image|env|resources|selector`, `patch configmap`, `uncordon`,
    and `scale`.
  - Input is parsed with `shlex`, case-sensitively, **not** through
    `engine.normalize`, because env keys and JSON patches are
    case-sensitive.
  - Goals: `deployment_available` and `service_has_endpoints`.
  - JSON in a mystery's `solution_commands` needs doubled braces,
    because the commands go through `str.format`.
- **exam.py** — Exam Mode. `build_questions()` flattens a category's
  tutorials+incidents into single-step questions and draws N at random;
  each carries the previous step's prompt and (truncated) output as
  context, plus any earlier output/prompt line containing an id the
  answer needs (`ID_LIKE` regex: web-abc123, gpu-node-1, hex ids, lock
  ids). A step whose needed id is never visible is dropped from the pool
  — and `test_every_real_step_is_answerable_out_of_context` fails if
  that ever happens, so content stays fair (it caught 6 real prompts
  that never named what the answer required). `run_exam()` takes an
  injectable `clock` and `input_fn` (resolved at call time, not as a
  default argument — a default captured `read_input` at import and
  couldn't be patched), gives no feedback until the end, scores against
  the CKA's 66% pass mark, and reviews every miss. Results go to
  `progress["exam_history"]`; `best_percent()` shows the best score per
  category.
- **aws_sandbox.py** — a fake AWS account with one VPC, driven by real
  `aws ec2 ...` commands:
  - public-a holds web-1 and the NAT gateway;
  - private-a holds api-1 and worker-1.

  `reachability(state, source, target, port)` walks the real layers:
  public IP → route table (IGW or NAT) → NACLs → security groups. NACLs
  are stateless (both directions, ephemeral ports) and only apply when
  traffic crosses a subnet; security groups are stateful.

  - **Problems:** 6 random ones, 2 per account (see `PROBLEMS`). Every
    failure shows the player a timeout, never the reason.
  - **Reactive commands:** create/replace-route, SG authorize/revoke,
    NACL entries, associate-address, create-nat-gateway, and terminate.
  - **Sessions:** `aws ssm start-session` opens a nested shell by setting
    `state["session"]`. `sandbox_common.run_loop` and `mystery.run_mystery`
    let `exit` end the session instead of the sandbox.
  - **Output:** `normalize()` lowercases input, so ids and args are parsed
    lowercase. Output is always a table (`--query`/`--output` are
    ignored).
- **azure_sandbox.py** — a fake subscription: vm-web-01 (public) and
  vm-app-01 (private) in vnet-web-prod, with a hub firewall.
  - Inbound traffic must pass the subnet NSG and then the NIC NSG. Rules
    are evaluated by priority with Azure's `DEFAULT_RULES` appended.
  - Outbound follows the subnet's route table; a `VirtualAppliance` next
    hop that isn't the firewall's IP black-holes traffic.
  - `test-ip-flow` and `show-next-hop` answer from the real state.
  - 5 problems, 2 per subscription. Reactive commands: nsg rule
    create/update/delete, nic update, route update, vm start/deallocate.
  - Commands inside a VM go through `az vm run-command invoke --scripts`.
- **gcp_sandbox.py** — a fake project: web-1 (external IP), db-1, and
  worker-1 on the global prod-vpc.
  - A firewall rule applies only to VMs carrying one of its target tags
    (or to all VMs if it has none). The lowest priority wins, deny beats
    allow at equal priority, and an implied rule denies other ingress.
  - Source tags make tags act as identity: web-1 without the `web` tag
    also loses its database access.
  - Private VMs need a Cloud Router plus NAT in their own region.
  - `gcloud compute ssh --tunnel-through-iap` needs tcp:22 from
    35.235.240.0/20; it opens a session like AWS SSM, or runs one
    command with `--command`.
  - 6 problems, 2 per project.
- **mystery.py** — Mystery Incidents: a symptom and a seeded sandbox
  state (`scenarios/mysteries/*.json`). `sandbox` picks linux, docker,
  aws, azure, gcp or kube, and `mystery.build_state` calls that module's
  `generate_state(**setup)`.

  Mysteries are **sandbox-agnostic**: each sandbox module supplies three
  hooks.
  - `GOAL_CHECKS`: `{name: fn(state, goal)}`, for example linux's
    `service_active`/`disk_below`/`load_below_nproc`, or aws's
    `reachable`/`not_reachable`.
  - `placeholders(state)`: seeded pids and ids for `solution_commands`.
  - `collateral_issues(state)`: dangerous conditions. Any that weren't
    present at the start count as collateral. Linux flags killed
    init/sshd/nginx (`PROTECTED`); AWS flags opening non-web ports to
    0.0.0.0/0, terminating instances, and allowing all inbound traffic
    on the public NACL.

  A new sandbox needs only these hooks to host mysteries. There is no
  step list: the player runs anything and then types `solve`. `solve`
  checks three things in order:
  1. **goals**: the sandbox's `GOAL_CHECKS`. Docker mysteries have none,
     because that sandbox is read-only.
  2. **evidence**: substrings that must have appeared in some command's
     *output*. Typed commands don't count, so `echo batch.jar` can't
     fake it. It **gates only mysteries with no goals** (the read-only
     Docker ones), which were winnable with zero commands by guessing.
     Where there are goals it is reported in the debrief instead ("You
     fixed it without looking at..."). Gating there trapped players who
     fixed the cause first, because a timeout can't be observed once the
     route exists.
  3. **a root-cause question**: two tries allowed.

  Score is 100, minus 20 per wrong answer, minus 15 per collateral
  issue, minus up to 30 for using more than twice `expert_commands`.
  `solution_commands` may use `{stray_pid}` or `{web_sg}` style
  placeholders, because pids and ids come from the seed. Evidence
  strings must not appear in the symptom text; a test enforces this.
  `test_mystery.py` runs every mystery's stored solution against its
  seeded state, proving it's solvable, that it meets the goals, and that
  it finds the evidence.
- **game.py** — entry point / main menu: Practice (category picker →
  Learn/Incidents within it), Career Paths, Writing Labs, Exam Mode,
  Mystery Incidents, Sandbox, Stats, Quit. Mystery best scores are kept
  in `progress["mystery_scores"]`.
  `choose_category()` lists categories from `list_categories()` plus an
  "All categories" option (passes `category=None` through to the
  loaders). `exit`/`quit` work at every prompt — see `engine.read_input` /
  `engine.QUIT_COMMANDS`. `play()` takes a `runner` parameter (defaults to
  `engine.run_scenario`) so the same attempt-tracking/completion-marking
  wrapper works for `run_scenario`, `yaml_lab.run_yaml_lab`, and (via a
  lambda closing over `scenarios_by_id`/`progress`)
  `career_path.run_career_path`.
- **stats.py** — the Stats screen (menu 7). Read-only.
  `build_stats(progress, tutorials, incidents, labs, paths, mysteries)`
  returns plain data:
  - per-category done/total for Learn, Incidents, Labs, and Mysteries;
  - the best exam score per category, against `exam.PASS_MARK`;
  - career paths, the mystery average, and the most-attempted scenarios.

  `suggest_next()` gives up to three next steps: finish the category
  you're furthest into, take the exam for a category whose tutorials are
  done, then incidents and mysteries. `render_stats()` turns the data
  into text. Completed ids that no longer exist in content are ignored.
- **progress.py** — reads/writes `progress.json` (completed scenarios per
  type — tutorial/incident/yaml_lab/career_path — attempt counts per
  scenario id). Deliberately **flat, not nested per category** — every
  scenario id is already globally unique, so nesting would just be
  migration risk for no benefit. `game.py` loads it once at startup,
  passes it into `choose_from_list` to render `[x]`/attempt-count
  markers, and calls `record_attempt`/`mark_completed`/`save_progress`
  after every run via the `play()` helper.

## Known environment quirks

**Antivirus deletes malware signatures in content:** Windows Defender
silently deleted `security-incident-004` because its fake output
contained a real one-line PHP web shell. The file vanished moments
after being written, and tests then failed with PermissionError. Never
put working malicious code in scenario content, such as web shells,
reverse-shell one-liners, or real exploit payloads. Describe it instead
("one line of PHP that base64-decodes a POST parameter and passes it to
eval"). The lesson survives, and the repo stays safe to clone on
machines with endpoint protection.

**Editing files via bash heredoc scripts:** in this environment, a
`python - <<'EOF'` script that writes Python or JSON source containing
`\n` escapes inside string literals has repeatedly produced REAL
newlines in the output file (breaking string literals — it once put a
syntax error into game.py). Use the Edit/Write tools for any change
containing `\n`, and run `python -m pytest` (which now imports game.py
via test_game.py) after every edit.

**Native Windows `bash`:** from native Windows Python, `bash` can resolve
to a launcher that hangs forever, so the game never shells out to bash
(see lab_formats.py).

**PowerShell stdin BOM:** PowerShell prepends a UTF-8 BOM (`﻿`) when you pipe a string to a
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
- kubernetes: 38 / 18 (also has 11 Writing Labs, 2 sandboxes, 5 mysteries) — CKA-gap-filled
- docker: 11 / 5 (+3 Writing Labs: 2 Dockerfile, 1 Compose)
- linux: 15 / 6 (+4 Writing Labs: bash)
- terraform: 16 / 7 (+5 Writing Labs: HCL, including a three-file module)
- networking: 17 / 8
- cicd: 20 / 8 (+4 Writing Labs: GitHub Actions, GitLab CI)
- monitoring: 17 / 8 (+5 Writing Labs: alert rules, burn-rate alerts, a Grafana dashboard, manual OTel spans)
- mlops: 14 / 7
- aws: 14 / 7 (+1 Writing Lab, AWS VPC sandbox, 4 mysteries)
- azure: 10 / 6 (+ Azure sandbox, 3 mysteries)
- gcp: 10 / 6 (+ Google Cloud sandbox, 3 mysteries)
- security: 11 / 6 (+ 2 hacked-server mysteries on the Linux sandbox)
- servers: 13 / 7 (fleet ops: Ansible, patching, time, LVM, backups)
- sre: 11 / 6 (big-tech practices, via public tools)
- git: 11 / 6 (Git in its own right; everyday workflow, revert vs
  reset, and bisect stay in cicd)
- systemdesign: 11 / 6 (+2 design-document Writing Labs; mixes real
  commands with multiple-choice decision steps)
- databases: 12 / 6 (operator's side: psql, on-call SQL, roles,
  activity and locks, slow queries, vacuum, backup and point-in-time
  recovery, Patroni, MySQL, Redis). SQL steps are matched like any
  command (exact token set), so each prompt names the exact columns
  and the expected list carries with- and without-semicolon variants.
  Design topics stay in systemdesign and migrations in cicd.
- webservers: 11 / 6 (+2 Writing Labs in the `nginx` format): nginx
  operations, TLS with certbot, access-log analysis, gateway errors,
  limits, caching, capacity, HAProxy, and recognising Envoy, Caddy,
  Traefik, and Apache. `parse_nginx` maps a directive to its arguments
  as one string and a block to a dict keyed by its arguments
  (`location./api/.proxy_pass`); anything repeated becomes a list, so
  labs with two `server` blocks use `server[*]...` paths. It reports a
  missing `;` with the line number. Under a `[*]` path, a failed
  `contains` check now names only the substrings the closest candidate
  lacks.
- identity: 9 / 5 (+2 Writing Labs): JWTs, OAuth/OIDC, workload identity, Vault, External Secrets, SOPS, mTLS, cert-manager
- scripting: 8 / 4 (+2 Writing Labs in the `python` format, parsed with `ast`, never executed): Python tooling, jq, yq, regex, make, Go
- messaging: 7 / 4 (Kafka operations, RabbitMQ, SQS; `$BS` is the bootstrap-server variable used throughout)
- serverless: 7 / 4 (Lambda, API Gateway, ECS on Fargate, Cloud Run, Azure Functions)
- performance: 7 / 3 (profilers, flame graphs, eBPF tools, JVM and Go runtime inspection, measurement)
- finops: 6 / 3 (cost allocation, rightsizing, commitments and spot, Kubernetes cost, quiet costs)
- **total: 306 tutorials, 152 incidents, 44 Writing Labs, 14 career paths, 23 Mystery Incidents (5 kubernetes, 4 linux, 2 docker, 4 aws, 3 azure, 3 gcp, 2 security)**

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
(the whole point is combining categories, not padding one). Currently 14 paths: `path-001`
build→ship (terraform → docker → kubernetes → cicd → monitoring),
`path-002` incident chain (linux → networking → kubernetes → monitoring),
`path-003` ML model laptop→production (mlops + docker), `path-004`
security hardening layer by layer (linux → networking → docker →
kubernetes → cicd), `path-005` platform from zero (networking →
terraform → linux → kubernetes), and `path-006` "The Worst On-Call
Night" (seven incidents only, across seven categories), and `path-007`
"Ship an LLM Service Safely" (buildx → supply chain → GitOps → vLLM →
LLM incident → SLOs, built from the step-5 new-topic content). Then
`path-008` multi-cloud (aws → gcp → azure), `path-009` security incident
response (security → aws → sre), `path-010` Patch Tuesday (security →
servers → sre), `path-011` SRE at scale (sre → monitoring →
kubernetes), `path-012` whiteboard to production (systemdesign →
git → terraform → cicd → security), `path-013` own the database
(databases → systemdesign → cicd → aws), and `path-014` the front door
(networking → webservers → systemdesign). More paths need
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
under "Multi-category expansion" above and detailed in GAPS.md; counts
are in the depth list there).
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
- tutorial-030–035: the ecosystem around the core (Kustomize, writing
  a Helm chart, Gateway API, VPA/KEDA/Karpenter, Flux, Linkerd)
- incident-006–010: ImagePullBackOff, a readiness-probe cascading
  failure, a CoreDNS outage, a silently-broken HPA (missing
  metrics-server), a NotReady node — chosen to cover common real
  incidents and "silent failure" patterns GAPS.md flagged as under-taught
- incident-011–013: an RBAC denial after a namespace move, a PDB that
  blocks a drain forever, and a PVC stuck Pending on a StorageClass that
  doesn't exist (all three from GAPS.md Part 1's backlog)
- incident-014–015: an admission webhook with `failurePolicy: Fail`
  whose own pods are down (nothing can be created, including its
  replacement), and a Multi-Attach error on a ReadWriteOnce volume
  during a rolling update
- incident-016–017: a Helm release stuck in pending-upgrade after a
  cancelled pipeline, and Pending pods behind a Karpenter NodePool
  limit

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

(`pytest.ini` points it at `tests/`.) The files:
- `test_docs_sync.py` — the counts quoted in GAPS.md, README.md, and
  CLAUDE.md match the content. **After adding or removing scenarios,
  run `python tools/sync_docs.py`**: it rewrites the per-category
  counts, totals, lab and path counts, and renumbers GAPS.md's
  'Part N' headings in file order. A new category needs its rows
  written by hand first (GAPS.md table, README table, the depth list
  below, a GAPS part inserted before the Backlog part, and a label in
  `tools/sync_docs.py` if it isn't a plain capitalised key); the tool
  reports what's missing.
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
- `test_lab_formats.py` — the Dockerfile, HCL, bash, markdown,
  ansible, nginx, and python parsers (line
  continuations, labels, nested maps, repeated blocks, comments, syntax
  errors, unbalanced blocks/quotes) and the `order`/`absent` checks
- `test_exam.py` — question drawing (context, truncation, seeding),
  scoring, the pass mark, time-limit edge cases with a fake clock, early
  exit, no-feedback-until-the-end, history — plus the content-wide
  answerability guard described under exam.py
- `test_stats.py` — counts, exam pass marks, suggestions, and rendering
  on synthetic content, plus fresh and fully-complete progress over the
  real content
- `test_game.py` — smoke tests that import game.py and drive the real
  main menu with scripted input. Added after a syntax error in game.py
  slipped past a fully green suite because nothing imported it.
- `test_sandbox_common.py` — pipes (quoted `|`, every supported filter),
  table rendering, and SandboxStore save/keep/discard in a temp dir
- `test_docker_sandbox.py` — invariants over 200 seeds (1-2 problems,
  only app containers break, every problem type occurs) and the
  evidence each problem leaves in real commands
- `test_kube_sandbox.py` — each cause shows its status, each real fix
  clears it, layered failures appear one at a time, deleting a pod
  fixes nothing, and case is preserved
- `test_azure_sandbox.py` and `test_gcp_sandbox.py` — the same shape as
  the AWS tests, plus each cloud's own rules: NSG priority order and
  NIC-level NSGs; target tags, deny-beats-allow, regional NAT, and IAP
  SSH sessions
- `test_aws_sandbox.py` — each problem breaks exactly its paths; each
  real fix restores them; NACL statelessness; SSM session enter and exit;
  describe filters; AWS-style errors; collateral detection
- `test_linux_sandbox.py` — invariants over 200 seeds (exactly 2
  problems, df never above 100%) and each problem's full diagnose-and-
  fix workflow, including the rm-on-an-open-file trap
- `test_mystery.py` — every mystery's schema; its goals start unmet;
  its stored solution solves it and finds all the evidence; the evidence
  isn't visible in the symptom. Also scoring maths and the full run loop:
  wrong answers, collateral from killing sshd, `giveup`, and refusing a
  guess made without investigating
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

See GAPS.md's final 'Overall' part for the reasoning. In priority order:

0. ✓ **Done: the cloud, security, fleet ops, and SRE expansion.** It added
   six categories (aws, azure, gcp, security, servers, sre), each
   written from its `commands/*.md`, plus:
   - the AWS VPC sandbox and sandbox-agnostic mysteries;
   - hacked-server problems in linux_sandbox;
   - Writing Labs yaml-023 to 028, with the `ansible` and `markdown`
     formats;
   - career paths 008 to 011.

   Natural follow-ups: Azure and GCP sandboxes (the aws_sandbox pattern
   of layered reachability plus hooks), more mysteries on the AWS
   sandbox, and per-cloud exam gap passes.
1. ✓ **Stats screen** (stats.py, menu 7). The spaced-repetition review
   mode that was planned with it is **not wanted**: the user asked to
   continue with everything except spaced repetition. Don't build it
   unless they ask.
1b. ✓ **Azure and GCP sandboxes**, each with 3 mysteries.
2. Per-category exam gap passes (like Part 1 did for the CKA): e.g.
   Terraform Associate, CKAD, AWS certs.
3. ✓ Kubernetes mysteries (5), on the new fixable `kube_sandbox.py`.
   More mysteries on any sandbox need only JSON: a seed, problems,
   goals, evidence, a question, and a stored solution.
4. More sandboxes (Terraform state explorer, networking) — Kubernetes,
   Docker, and Linux exist; new ones only need generate_state() and
   handle_command() plus a SANDBOXES entry in game.py.
5. v6 scenario-scaffolding CLI — more valuable now that content volume
   is large.
6. ✓ **Named topic gaps closed** (the batch after Git and System
   Design): admission webhooks and Multi-Attach (incident-014/015),
   SELinux, IPv6, DB migrations in CD, SLSA provenance, OpenTelemetry
   instrumentation, distributed training, Airflow operations, RDS,
   Route 53, Kyverno and Falco, writing Terraform modules and dynamic
   blocks, plus Writing Labs yaml-031 (getopts, `while read`) and
   yaml-032 (a Terraform module).
6b. **The topic backlog is GAPS.md's Backlog part**, in three tiers, with a
   suggested build order. ✓ Its first two items are done: the
   `databases` category (12 tutorials, 6 incidents, path-013) and the
   `webservers` category (11 tutorials, 6 incidents, 2 nginx Writing
   Labs, path-014). Next up from it: identity and secrets (Vault,
   OIDC, JWTs, mTLS, cert-manager), then the Kubernetes ecosystem
   (Kustomize, Helm authoring, Gateway API), then Jenkins and GitLab
   CI. A **database sandbox** driving an
   in-memory SQLite database (standard library, no install) would let
   players run real SQL instead of matching pre-written statements.
   Authoring gaps that would each be one Writing Lab: a Kyverno
   policy, an Airflow DAG, a burn-rate alert rule file.
6c. A **Git sandbox** (a real temp repository the game inspects) is the
   most valuable follow-up for the git category: outputs are
   pre-written today, so rebase todo lists and conflicts are never
   edited for real.
7. Keep GAPS.md current: every content pass should update its part.
