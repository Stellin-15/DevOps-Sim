# kube-sim

A terminal-based game for learning real DevOps command-line skills by
typing them, not memorizing them. Started as Kubernetes-only; now spans
**Kubernetes, Docker, Linux, Terraform, Networking, CI/CD, Monitoring,
MLOps, AWS, Azure, Google Cloud, Security, Server Fleet Ops, SRE**
(how large companies run production), **Git, System Design, Databases,
and Web Servers & Proxies**. Runs entirely locally — no real infrastructure, no network calls,
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
  file and checks it field by field. 44 labs across thirteen formats:
  Kubernetes manifests, GitHub Actions workflows, Prometheus alert rules,
  Docker Compose files, Dockerfiles, Terraform (AWS VPCs, security
  groups, GCP firewalls, a reusable module), AWS IAM policies, Ansible
  playbooks, bash and Python scripts, nginx configuration, a blameless postmortem,
  and system design documents in Markdown.
  Half are "write from scratch", half are "fix this broken or dangerous
  file". This is the skill a command-matcher can't fake.
- **Exam Mode** — pick a category and a number of questions; they're drawn
  at random from that category's tutorials and incidents, one minute
  each, with **no hints and no feedback until the end** — like a real
  exam. You're scored against the CKA's real 66% pass mark, every miss is
  reviewed with the correct command, and your best score per category is
  remembered. The rest of the game is forgiving on purpose; this is the
  part that tells you whether it stuck.
- **Mystery Incidents**: real on-call conditions. You get only a
  symptom ("postgres just dies, nothing in its logs") and a live Linux,
  Docker, AWS, Azure, or Google Cloud sandbox. There are no steps and no hints, and any command
  works in any order.
  - **Solving it.** When you think you've fixed it, type `solve`. The
    game checks three things:
    1. the system really is fixed;
    2. you can name the root cause.

    Where there's nothing to fix (the Docker mysteries are diagnosis
    only), you must also have actually *seen* the evidence, so you can't
    win by guessing.
  - **Scoring.** You're scored against an experienced engineer's command
    count. Careless fixes cost points: `kill -9` on sshd locks you out,
    and opening SSH to 0.0.0.0/0 on AWS gets flagged.
  - **Debrief.** Afterwards you get a debrief, plus one efficient path
    through the problem. Type `giveup` at any time to see the answer.
- **Stats**: one screen showing where you stand. For every category it
  lists tutorials, incidents, labs, and mysteries done, and your best
  exam score against the 66% pass mark. It also shows career paths, your
  mystery average, and the scenarios that took you the most attempts,
  and suggests up to three concrete next steps.
- **Sandbox** — no scoring, no steps: a randomly generated broken
  environment to explore with real commands. Seven to pick from:
  - **Kubernetes** — a cluster of Deployments, Services, and pods (some
    `CrashLoopBackOff`/`OOMKilled`/`Pending`/`Error`), plus nodes, a
    ConfigMap, a Secret, and an event log, all consistent with each other.
    Read-only: for practising how to look around.
  - **Kubernetes, fixable** — a cluster where every failing pod has a
    cause: an image tag that doesn't exist, a missing ConfigMap key, a
    memory limit that's too low, a readiness probe on the wrong path,
    drained nodes, or a Service selector that matches nothing. `kubectl
    rollout undo`, `set image|env|resources|selector`, `patch`, and
    `uncordon` really fix it, and deleting a broken pod really doesn't.
  - **Docker** — a host where one or two app containers were OOM-killed,
    crashed on startup, are stuck in a restart loop, or are failing their
    healthcheck, plus dangling images and volumes wasting disk.
  - **Linux** — a server with two hidden problems (a failed service, a
    full disk, a runaway process, a memory hog, a crypto-miner that keeps
    coming back, or an SSH backdoor) that you must find **and fix**: `kill`, `systemctl restart`, `rm`, and `truncate` really change
    the state, so fixes only work if you've understood the cause.
  - **AWS** — a VPC with two broken network layers. Explore it with real
    `aws ec2 describe-*` commands. Traffic is evaluated layer by layer:
    public IP, route table (IGW or NAT), stateless network ACLs, and
    security groups. Every failure just times out, as it would for real,
    so you have to read the configuration. Fix it with create-route,
    security group rules, NACL entries or Elastic IPs, then test with
    `curl`/`nc`/`ssh` from your laptop, or from inside an instance via
    `aws ssm start-session`.
  - **Azure** — NSG rules evaluated by priority, an NSG that may also sit
    on the VM's network card, and a route that sends traffic to a
    firewall that may not be there. `az network watcher test-ip-flow`
    names the rule that decided, as the real one does.
  - **Google Cloud** — firewall rules that only apply to VMs with the
    right network tag, SSH through IAP, and Cloud NAT that exists per
    region.
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
game.py             entry point / main menu (practice, career paths,
                     writing labs, exam, mysteries, sandboxes)
engine.py           generic scenario runner + fuzzy command matching
                     (zero tool-specific logic — works identically for
                     kubectl, docker, terraform, git, plain shell...)
scenario_loader.py  category-aware loading: list_categories(),
                     load_tutorials(category=None), load_incidents(...),
                     load_yaml_labs(), load_career_paths(),
                     load_all_scenarios_by_id()
exam.py             Exam Mode: random timed questions, scoring, history
stats.py            Stats screen: progress per category, exam bests,
                     suggested next steps
mystery.py          Mystery Incidents: symptom-only, free-form diagnosis
                     on a seeded sandbox; goals + evidence + root cause
career_path.py       chains existing scenarios across categories into
                     one continuous playthrough
progress.py         reads/writes progress.json (completion + attempt
                     counts, flat across all categories — ids are
                     globally unique)
sandbox.py          Kubernetes sandbox (random cluster, read-only)
kube_sandbox.py     Kubernetes sandbox (fixable: status derived from cause)
docker_sandbox.py   Docker sandbox (random broken host)
linux_sandbox.py    Linux sandbox (random broken server; reacts to fixes)
aws_sandbox.py      AWS sandbox (a VPC with real layer-by-layer reachability)
azure_sandbox.py    Azure sandbox (NSG priorities, NIC NSGs, routes to a firewall)
gcp_sandbox.py      Google Cloud sandbox (tag-based firewalls, IAP SSH, Cloud NAT)
sandbox_common.py   shared sandbox loop, pipes, tables, save/discard
yaml_lab.py         Writing Labs runner: real file editing + validation
lab_formats.py      parsers for YAML/JSON, Dockerfile, HCL, bash, Ansible,
                     and Markdown lab files
scenarios/
  kubernetes/tutorials/*.json, incidents/*.json
  docker/tutorials/*.json, incidents/*.json
  linux/, terraform/, networking/, cicd/, monitoring/, mlops/
                     — same tutorials/incidents layout per category
  yaml_labs/*.json   manifest-editing labs (not nested by category)
  career_paths/*.json  ordered lists of existing scenario ids spanning
                     2+ categories (not nested by category)
  mysteries/*.json   symptom + sandbox seed + goals + evidence + question
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

**Mystery incident**: drop a JSON file into `scenarios/mysteries/` with
`type: "mystery"`, a `sandbox` (`linux` or `docker`), and `setup` (a
`seed` plus forced `problems` for linux or `assignments` for docker). It
also needs:
- a `symptom`;
- `goals` (state checks such as `service_active`, `disk_below`, and
  `load_below_nproc`; leave empty for docker);
- `evidence` (`{"description", "seen_any": [...]}`, text that must
  appear in some command's output before `solve` is accepted);
- a multiple-choice `question`;
- `expert_commands`, `solution_commands`, and a `debrief`.

The tests run `solution_commands` against the seeded state to prove the
mystery is solvable and that the solution finds the evidence.

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
the engine, loader, sandboxes, yaml_lab, career_path, mystery, or scenario content.

## What's in it

| Category | Tutorials | Incidents | Topics |
|---|---|---|---|
| Kubernetes | 35 | 17 | pods → operators, full CKA coverage incl. etcd, kubeadm, certs, security, RBAC/PDB/storage/admission-webhook/Multi-Attach incidents, and the ecosystem (Kustomize, Helm chart authoring, Gateway API, VPA/KEDA/Karpenter, Flux, Linkerd); plus 11 Writing Labs and 2 Sandboxes |
| Docker | 11 | 5 | images/layers, volumes, networking, Compose, cleanup, Dockerfiles, runtime limits, container security, BuildKit/buildx multi-platform; plus 3 Writing Labs (2 Dockerfile, Compose) |
| Linux | 15 | 6 | find, text pipelines, processes/signals, systemd, networking, users/permissions, SSH, cron, disks, performance, strace/lsof, packages/firewalls, SELinux; plus 4 bash-script Writing Labs |
| Terraform | 16 | 7 | safe CI workflow, modules/for_each/moved blocks, writing modules (validation, dynamic blocks, terraform test), variables/outputs, state inspection & refactoring, import, workspaces, remote state/locking, providers, debugging, OpenTofu/Terragrunt/Atlantis, policy as code (Checkov, Conftest), Packer, and the other IaC tools (CloudFormation, Bicep, Pulumi, Crossplane); plus 5 HCL Writing Labs |
| Networking | 17 | 8 | DNS, refused vs timeout, ports/nmap, routing/ARP, firewalls, TLS/openssl, HTTP/curl, in-cluster networking, CIDR, tcpdump, MTU black holes, IPv6, WireGuard, BGP, DNS delegation, HTTP/2 and gRPC, Cilium/Hubble |
| CI/CD | 20 | 8 | git workflows, revert vs reset, git bisect, tags/releases, GitHub Actions CLI, secrets/OIDC, local CI repro, rolling/blue-green/canary, GitOps (Argo CD), SBOMs/scanning/signing, SLSA provenance, zero-downtime database migrations, GitLab CI, Jenkins, artifact registries and promotion, release automation (semver, Renovate), flaky and contract tests; plus 4 pipeline Writing Labs |
| Monitoring | 17 | 8 | PromQL, golden signals, tracing (OTel/Jaeger), OpenTelemetry instrumentation, SLOs and burn-rate alerts, Prometheus ops, alerting/Alertmanager, journald, Elasticsearch, Loki, Grafana API, log pipelines (Fluent Bit, Vector), log volume and cardinality, Datadog and Sentry; plus 5 Writing Labs (alert rules, burn-rate alerts, a dashboard, manual spans) |
| MLOps | 14 | 7 | environments, GPUs, MLflow, DVC, serving, KServe/Kubeflow, profiling, model monitoring, model canaries, LLM serving (vLLM), feature stores (Feast), distributed training, Airflow pipelines |
| AWS | 14 | 7 | profiles/identity, EC2, SSM vs SSH, VPC anatomy, security groups vs NACLs, IAM, S3, CloudWatch/CloudTrail, ALB/ASG, EKS/ECR, cost, RDS, Route 53, peering/Transit Gateway/PrivateLink; plus a VPC Sandbox |
| Azure | 10 | 6 | subscriptions, resource groups/locks, VMs (stop vs deallocate), Run Command/Bastion/az ssh, VNets/NSGs, UDRs/Network Watcher, RBAC/managed identity, Key Vault/storage, Monitor/KQL, AKS |
| Google Cloud | 10 | 6 | configurations/projects/APIs, Compute Engine filters, IAP SSH/serial console, global VPCs, tag-based firewalls, Cloud NAT, IAM without keys/impersonation, Cloud Storage, logging/quotas, GKE/Workload Identity |
| Security | 11 | 6 | nmap discovery/TLS checks, Trivy/kube-bench, Lynis/OpenSCAP CIS audits, SSH hardening, fail2ban, auditd, osquery/AIDE, secrets scanning, compromise triage, Kubernetes admission policy (Kyverno) and runtime detection (Falco); plus 2 hacked-server mysteries |
| Server Fleet Ops | 11 | 6 | Ansible (inventories, safe playbook runs, rolling serial updates, Vault/lint), Debian and RHEL patching with rollback, kernels and reboots, SSM Patch Manager, chrony, LVM growth, backups with real restore tests |
| SRE | 10 | 6 | incident first ten minutes, Argo Rollouts canaries, Istio resilience, capacity planning, load testing (k6/vegeta), chaos engineering, feature flags/kill switches, postmortem timelines, graceful degradation, production readiness reviews |
| Git | 11 | 6 | objects/refs/HEAD, precise staging, branches, merge conflicts, rebase (autosquash, --onto), the undo matrix and reflog, searching history, remotes and forks, stash/worktrees, config/attributes/hooks, shallow and partial clones, submodules, LFS, signing |
| System Design | 11 | 6 | estimation, load balancing, caching, indexes and query plans, replication, sharding, queues, consistency and quorums, rate limiting and idempotency, CDNs, a worked URL shortener; real commands plus multiple-choice trade-off questions; plus 2 design-document Writing Labs |
| Databases | 12 | 6 | psql, on-call SQL (joins, GROUP BY, window functions), transactions and isolation, roles and privileges, pg_stat_activity and lock chains, slow queries (pg_stat_statements, EXPLAIN), vacuum and wraparound, pg_dump/pg_restore, point-in-time recovery (pgBackRest), Patroni failover, MySQL, Redis operations |
| Web Servers & Proxies | 11 | 6 | nginx (test and reload, server blocks and locations, reverse proxying, TLS with certbot, access-log analysis, reading 502/503/504, rate and body limits, caching and gzip, connection and file-descriptor capacity), HAProxy draining, and recognising Envoy, Caddy, Traefik, and Apache; plus 2 nginx Writing Labs |
| Identity & Secrets | 9 | 5 | reading JWTs, OAuth 2.0 and OIDC flows, Kubernetes workload identity, Vault (KV, policies, dynamic database credentials), External Secrets Operator, SOPS and Sealed Secrets, PKI and mutual TLS, cert-manager; plus 2 Writing Labs |
| Scripting | 8 | 4 | Python environments and pinned dependencies, running and debugging scripts, pytest/ruff/mypy, jq in depth, yq, regular expressions, Makefiles, building and testing Go tools; plus 2 Python Writing Labs |
| Messaging | 7 | 4 | Kafka (topics and replication, reading a topic by hand, consumer groups and lag, retention and compaction, broker operations), RabbitMQ alarms and queue limits, SQS visibility timeouts and dead-letter queues |
| Serverless | 7 | 4 | Lambda (invoke and logs, cold starts and concurrency, versions/aliases/canaries, event retries and failure destinations), API Gateway limits, ECS on Fargate, Cloud Run revisions and traffic, Azure Functions |
| Performance | 7 | 3 | perf CPU profiling, flame graphs, py-spy, JVM heap/GC/thread dumps, eBPF tools (execsnoop, biolatency, bpftrace), Go pprof, honest benchmarking and percentiles |
| FinOps | 6 | 3 | reading the bill by service and team, tags/budgets/anomaly alerts, rightsizing, Savings Plans and spot, Kubernetes cost (OpenCost), storage classes, log retention, and data transfer |
| **Total** | **300** | **150** | + 44 Writing Labs |

The three clouds use different names for the same ideas (security group
vs NSG vs firewall rule; CloudTrail vs Activity Log vs Audit Logs). The
cross-cloud map at the end of GAPS.md Part 11 lines them up side by
side.

Plus **14 Career Paths** chaining scenarios across categories:
- ship a feature end to end;
- a production incident chain;
- an ML model from laptop to production;
- security hardening layer by layer;
- building a platform from zero;
- "The Worst On-Call Night" (seven incidents, seven layers);
- shipping a self-hosted LLM safely (build → sign → GitOps → serve → SLO);
- the same job on AWS, Google Cloud, and Azure;
- security incident response end to end;
- Patch Tuesday for a fleet;
- SRE at scale, from readiness review to postmortem;
- whiteboard to production (estimate → design → clean history → Terraform
  module → zero-downtime migration → provenance → admission policy);
- own the database (live activity → slow queries → migrations and the
  lock queue → backups → a WAL-filled disk → recovering a deleted table);
- the front door (HTTP and TLS → nginx → load balancing → certificates →
  gateway errors → three proxy incidents).

Plus **23 Mystery Incidents**, symptom only:
- Kubernetes: 503s while every pod is Running, a deploy that never
  finishes, workers that fail and then fail differently, the morning
  after node maintenance, and pods that are Running but not Ready.
- Linux: an API down after a deploy, a disk alert that won't clear, a
  database that keeps dying, and a slow server with two unrelated
  problems.
- Docker: a container that "disappears", and a worker the dashboard
  wrongly reports as "running".
- AWS: a new web server that times out, private workers that can't pull
  updates, SSH that works while the site doesn't, and a "network
  hardening" change that broke everything.
- Azure: an allow rule that's "right there" but ignored, an app tier that
  lost the internet, and a subnet firewall that looks perfect.
- Google Cloud: a rebuilt web VM nobody can reach, workers that can't
  install packages, and the morning after a firewall cleanup.
- Security: a pegged CPU and a doubled cloud bill (a crypto-miner that
  comes back until you find its cron job), and a 3am login (a
  brute-forced root password, a hidden UID-0 account, and a planted SSH
  key).

Every tutorial step explains not just what the command does but *why*
it beats the alternatives. Every incident ends with a debrief of the real
root cause and how to prevent it.

## Will this make me proficient in DevOps?

Honest answer — see **GAPS.md**, which assesses every category
individually (covered / still missing / readiness verdict) plus an
overall verdict in its final part. **GAPS.md's Backlog part is the full list of
topics this game doesn't teach yet**, in three tiers (commonly used,
role-dependent, and niche), so you can see what's left to learn. In short: completing everything here makes
you a strong DevOps *operator* — you'll know the commands, the failure
modes, and the debugging method. To be fully proficient you also need to
practice *authoring* (Dockerfiles, Terraform, pipeline YAML, scripts),
time on real infrastructure where things break in unscripted ways, and
cloud-provider fundamentals. GAPS.md's final part lays out a concrete path.
For the CKA specifically, see GAPS.md Part 1.

## Status / roadmap

Built so far: hardcoded single scenario → JSON-driven scenarios with a
menu → hint escalation → sandbox → progress tracking → full Kubernetes
coverage → CKA gap-filling → Writing Labs → multi-category architecture →
Career Paths → all 8 categories expanded to full depth → Dockerfile,
Terraform, and bash Writing Labs → Exam Mode → Docker and Linux sandboxes →
Mystery Incidents → new-topic content (tracing, SLOs, tcpdump/MTU, GitOps,
supply chain, bisect, LLM serving, feature stores, strace, BuildKit,
Terraform modules, and RBAC/PDB/storage incidents) → AWS category, VPC
sandbox, and AWS mysteries → Azure and Google Cloud categories → Security
category and hacked-server mysteries → Server Fleet Ops category → SRE
category → cloud, Ansible, and postmortem Writing Labs, plus four more
career paths → Stats screen → Azure and Google Cloud sandboxes with
mysteries → a fixable Kubernetes sandbox with five Kubernetes mysteries →
Git category → System Design category (with multiple-choice decision
steps and design-document labs) → a gap-closing batch (admission
webhooks, Multi-Attach, SELinux, IPv6, database migrations, SLSA
provenance, OpenTelemetry instrumentation, distributed training, Airflow,
RDS, Route 53, Kyverno/Falco, Terraform modules, getopts) → Databases
category (PostgreSQL operations, SQL, recovery, MySQL, Redis) → Web
Servers & Proxies category (nginx, HAProxy, and an nginx lab format).

Next, in priority order (details in CLAUDE.md and GAPS.md):
- The topic backlog in GAPS.md's Backlog part: identity and secrets next
  (Vault, OIDC, mTLS), then the Kubernetes ecosystem, then Jenkins and
  GitLab CI
- Exam-specific gap passes for other certifications (CKAD, Terraform
  Associate, AWS/Azure/GCP associate exams)
- More sandboxes (Kubernetes, Docker, Linux, and AWS exist; Terraform
  state would be next)
- A CLI scaffold for authoring new scenario JSON

See CLAUDE.md for architecture and notes for continuing development.
