# GAPS.md — will kube-sim actually make you proficient in DevOps?

Honest self-assessment, written from the perspective of a beginner using
this game as their main prep tool for (a) passing the CKA exam and (b)
eventually handling production Kubernetes incidents on their own. Short
answer: **helpful, not sufficient, for both** — and this file exists to be
specific about where it falls short, so nobody mistakes "completed every
scenario" for "ready."

**Structure:** the first half of this file is the original, deepest
assessment — **Kubernetes / CKA**. Each other category (Docker, Linux,
Terraform, Networking, CI/CD, Monitoring, MLOps) gets its own section
further down, written the same way: what's covered, what a real job
expects, what's still missing. The final section is a cross-category
summary: what "proficient in DevOps" actually requires beyond any single
tool, and how far this game gets you toward it.

---

# Part 1 — Kubernetes / CKA

## What kube-sim is actually good at

- **Command muscle memory.** By tutorial-020 you've typed real kubectl
  syntax — verbs, resources, flags, short aliases — for almost everything
  an application developer touches day to day.
- **The "why," not just the "what."** Every tutorial step explains why
  that command/flag beat the alternatives, which is closer to how an
  experienced engineer actually thinks than rote syntax memorization.
- **Investigative sequencing.** Incidents force chaining get → describe →
  logs → fix, which is the actual shape of real debugging — most
  beginners' instinct is to guess a fix immediately instead.
- **A safe place to be wrong.** Hint escalation and Sandbox mode mean you
  can flail without consequence, which real clusters (and real on-call
  shifts) do not offer.

## Where it falls short for the CKA specifically

The CKA is roughly 30% troubleshooting, but also has entire domains
kube-sim doesn't touch at all, because they require actions below the
kubectl layer that a pure command-matching game can't meaningfully verify:

| CKA domain (approx. weight) | kube-sim coverage | Gap |
|---|---|---|
| Troubleshooting (~30%) | Good for app-layer (pods, services, resources) | Weak on control-plane/node-layer troubleshooting until this update |
| Workloads & Scheduling (~15%) | Strong (deployments, jobs, scaling, scheduling) | Was missing probes and multi-container pods until this update |
| Services & Networking (~20%) | Decent (services, ingress, netpol, DNS objects) | Was missing DNS *failure* debugging (CoreDNS) until this update |
| Storage (~10%) | Basic (PV/PVC/StorageClass get/describe) | No dynamic provisioning failure scenarios, no volume mount troubleshooting |
| Cluster Architecture & Installation (~25%) | Was essentially absent | kubeadm bootstrap/upgrade, static pods, etcd backup/restore, certificate management — this is the single biggest gap, and this update addresses the highest-value pieces of it |

**Update — largely addressed.** This used to be a structural gap nothing
in kube-sim could fix: the CKA is a hands-on exam where you write and edit
YAML under time pressure, and a pure command-matching game can't simulate
that. It's now addressed by **YAML Labs**, a third mode alongside
Learn/Incidents: the game writes a real file to `workspace/`, tells you
what to build or fix, and you edit it in your *actual* editor (vim, nano,
VS Code — whatever you'd really use) — the same muscle the exam tests,
not a simulated one. Typing the apply command reads your real file off
disk, parses it, and gives field-by-field feedback (missing field, wrong
value, YAML syntax error), with the same nudge → hint → full-solution-
reveal escalation as everywhere else. See `yaml_lab.py` and
`scenarios/yaml_labs/`.

**Update — time pressure now addressed by Exam Mode:** a timed, scored
exam (one minute per question, 66% pass mark — the CKA's real one) that
draws random steps from a category with no hints and no feedback until
the end, then reviews every miss. It measures recall under pressure,
which is exactly what the forgiving tutorial loop can't. It's still
single commands, though — the real CKA's multi-step, 5-to-10-minute
tasks on a live cluster aren't simulated.

What YAML Labs still doesn't replicate: the breadth of an actual live cluster (no real
apiserver validating your YAML beyond what each lab's `validate` spec
checks), and the physical friction of working across multiple terminal
panes/contexts at once. Time on a real kind/minikube cluster remains
worthwhile before the actual exam — but "structurally impossible to
practice YAML editing here at all" is no longer true.

## Where it falls short for real production incidents

A few things that matter in practice and aren't really "exam topics" at
all, so they're easy to skip even after CKA-level prep:

- **Silent failure modes.** incident-009 (HPA stuck because metrics-server
  was never installed) is the shape of a huge share of real incidents:
  nothing is *broken*, something was just never wired up, and it looks
  fine until load reveals it. These don't show up in describe/get output
  as an obvious red error — you have to know to check.
- **Cascading/compounding failures.** incident-007 (readiness probe
  flapping under load makes the load worse) is closer to a real incident
  than a single root cause — most production fires have a feedback loop,
  not one clean cause.
- **When kubectl itself is the thing that's broken.** tutorial-024 covers
  this, but it's a mindset shift beginners often miss: sometimes the tool
  you'd normally debug with is unavailable, and you need a completely
  different toolset (journalctl, static pod manifests, node filesystem).
- **Judgment about risk**, not just correct syntax — e.g. incident-010's
  resolution deliberately flags that force-deleting a pod is only safe
  once you've independently confirmed the node is truly dead, not just
  unresponsive. A game can explain this in a resolution debrief; it can't
  fully substitute for the instinct that comes from having been burned by
  it once.
- **Scripted incidents lead you by the hand.** Every incident here is a
  sequence of prompts, and each prompt hints at what to check next. Real
  on-call starts with only a symptom and a blank terminal. Mystery
  Incidents (see Part 9) practice exactly that, but so far only on the
  Linux and Docker sandboxes. **A Kubernetes mystery doesn't exist
  yet**: the Kubernetes sandbox is read-only, so there's nothing to fix.
- **Escalation and communication** aren't practiced here at all — a huge
  part of real incident response is knowing when to page someone else,
  what to say in a status update, and how to hand off. Out of scope for
  this tool, but worth knowing it's out of scope.

## What this update adds to close the highest-value gaps

Given the assessment above, this pass adds:

**Tutorials** (021–029): liveness/readiness/startup probes, multi-container
& init containers, etcd backup & restore, static pods & control-plane
troubleshooting, kubeadm cluster upgrades, certificate management, cluster
& pod security (security contexts, Pod Security Standards), kubeadm
cluster bootstrap (init/join/token), and Operators & custom controllers
(the reconciliation-loop pattern, building on tutorial-018's CRDs) —
covering the Cluster Architecture domain that was previously almost
entirely absent, plus the probes/multi-container/security gaps in
Workloads and cluster security.

**Kubeflow — out of scope for the CKA, covered separately in MLOps.** It's
an ML platform that runs *on* Kubernetes, not a core Kubernetes/CKA skill,
so it isn't part of this Kubernetes assessment. The MLOps category (Part
8) now covers it at the level most engineers actually need — finding your
way around KServe InferenceServices and Kubeflow components as ordinary
Kubernetes workloads and CRDs, and running model canaries. Deep Kubeflow
Pipelines authoring still needs dedicated resources.

**Incidents** (006–010): ImagePullBackOff, a readiness-probe cascading
failure, a CoreDNS outage, a silently-nonfunctional HPA (missing
metrics-server), and a NotReady node requiring node-filesystem-level
debugging — chosen specifically because they're either extremely common
in real production (ImagePullBackOff, probe misconfiguration) or teach a
failure mode beginners don't know to look for (silent failures, control
plane being the actual outage).

## What's still not covered (backlog, not addressed this pass)

- ~~Dynamic storage provisioning failures~~: **done** in incident-013 (a
  PVC stuck Pending on a StorageClass that doesn't exist in this cluster,
  plus the "PVCs are immutable, StatefulSets never update them" trap).
  Volume *mount* failures (for example FailedAttachVolume, or a
  multi-attach error on a ReadWriteOnce volume) still aren't covered.
- ~~RBAC denial as an incident~~: **done** in incident-011 (a job that
  moved namespaces falls back to the 'default' service account;
  diagnosed from the 403 text and `auth can-i --as`).
- ~~PodDisruptionBudget blocking a drain~~: **done** in incident-012.
- Admission controllers / webhooks (still missing; also relevant to
  enforcing image signatures, see Part 6)
- ~~More YAML Labs~~ — **done**: StatefulSet, Ingress (with TLS), HPA,
  and RBAC (Role + RoleBinding) labs added, for 9 Kubernetes labs total
- Kubeflow at an operator level now lives in the MLOps category (Part 8);
  deep Kubeflow Pipelines authoring remains out of scope

---

*Written honestly, not to make the tool look complete. If you're using
this for CKA prep: also get time on a real cluster (kind/minikube) before
the exam, especially for YAML-writing speed. If you're using it to build
toward handling production on your own: pair it with actually being on an
on-call rotation, shadowed, before being the primary responder.*

---

# Part 2 — Docker

**Content:** 11 tutorials, 5 incidents, 3 Writing Labs, and a Sandbox (a random
host with OOM-killed, crashed, restart-looping, or unhealthy containers
and dangling images/volumes to find with real docker commands and pipes).
Two Mystery Incidents (an OOM kill, and a restart loop that the
dashboard reports as "running") run on it. The Docker sandbox is
read-only, so these are diagnosis-only: you can't fix anything in them.

## Covered

Every section of `commands/docker.md`: images (build, tag, push, history,
prune), containers (run flags, lifecycle, logs, exec, inspect, top,
stats, cp, events), volumes and bind mounts, networks, Compose (up/down,
logs, build, exec, config), system cleanup, Dockerfile essentials
(multi-stage builds, ARG vs ENV, HEALTHCHECK, --no-cache), runtime
options (restart policies, resource limits, --rm), and container
security (non-root users, image scanning, read-only filesystems,
privileged-mode auditing — the last group isn't in docker.md at all but
is expected in real work). Incidents cover the five most common real
Docker failures: immediate exit (missing dependency), cross-container
networking, disk exhaustion from never-pruned images, port conflicts,
and the ARG-vs-ENV secret mistake.

## Still missing

- ~~Writing Dockerfiles~~ — **closed**: Writing Labs yaml-016 (a
  cache-friendly, non-root, exec-form Dockerfile from scratch) and
  yaml-017 (convert a 1.1GB root image with a baked-in secret into a
  multi-stage build), plus yaml-011 for docker-compose.yml. Validation is
  structural (instruction order, stages, forbidden text) — it doesn't
  run a real `docker build`, so it can't catch e.g. a wrong COPY path.
- ~~BuildKit and multi-platform builds~~: **closed** by docker-tutorial-011
  (buildx builders, `--secret` mounts, registry cache with mode=max,
  amd64+arm64 manifest lists, `imagetools inspect`).
- ~~Image signing, digest pinning~~: **closed** by cicd-tutorial-012
  (cosign sign/verify by digest, `crane digest`), which lives in CI/CD
  because that's where it runs.
- `docker pause/unpause/rename/attach/diff` — rarely used in practice,
  deliberately skipped.
- Swarm mode — deliberately out of scope (largely displaced by Kubernetes).

## Readiness verdict

Solid for day-to-day development and debugging work with containers,
and, with the Dockerfile labs and BuildKit tutorial, for containerizing
an app well. The remaining gap is realism: the Dockerfile checker is
structural, so run a real `docker build` on your own projects.

---

# Part 3 — Linux

**Content:** 14 tutorials, 6 incidents, 3 Writing Labs, and an interactive
Sandbox: a server with two random real problems (failed service blocked by
a stray process, disk filled by a log held open by a process, runaway CPU,
memory hog that got postgres OOM-killed) that you must find AND fix with
kill / systemctl restart / rm / truncate. It models real consequences —
deleting a log a process still holds open frees nothing until you restart
that process — which unscripted practice needs and scripted steps can't give.
Four Mystery Incidents run on that sandbox. Each is a symptom only, which
you diagnose and fix any way you like, and each is scored against an
expert's command count.

## Covered

Every section of `commands/linux.md`: navigation and `find` (by name,
mtime, size), text pipelines (grep -v, awk, sort | uniq -c | sort -rn,
sed preview-before-`-i`, diff), permissions and ownership (octal modes,
chown -R, the `usermod -G` without `-a` trap), processes and signals
(SIGTERM vs SIGKILL, nohup, jobs, nice/renice), systemd (status vs
enabled, reload vs restart, daemon-reload, enable --now, journalctl),
host networking (ip addr/route, ss -tulnp and the localhost-binding trap,
traceroute), SSH keys and transfer (ed25519, ssh-copy-id, scp vs rsync
and the trailing-slash trap), archives/cron/environment (tar flags, cron's
minimal PATH, output redirection), disks (lsblk, mkfs, mount, UUID-based
fstab, mount -a before rebooting), and performance triage (load vs nproc,
vmstat's `wa` column, iostat %util/await, dmesg). Incidents cover the
classic senior-level Linux puzzles: deleted-but-open files (df/du
mismatch), silent OOM kills, ownership broken by `sudo cp`, cron failing
silently for weeks, and sshd StrictModes rejecting keys.

## Still missing

- **Shell scripting** — **partly closed**: Writing Labs yaml-020 (a
  defensive backup script: `set -euo pipefail`, argument checks, stderr,
  quoting) and yaml-021 (fix a cleanup script that deletes `/*` when
  called without an argument). The script checker is structural
  (balanced if/fi, do/done, case/esac and quotes, plus required and
  forbidden text) — not a real bash parser or shellcheck, so subtler bugs
  go unnoticed. yaml-022 now adds arrays, functions with `local`, loops,
  `trap ... EXIT` cleanup, and the `((n++))`-under-`set -e` trap. Still
  unpracticed: `getopts` argument parsing, `while read` loops over
  files, and a real shellcheck pass.
- ~~`strace`/`lsof`~~: **closed** by linux-tutorial-013 (attach to a hung
  process, map fds to sockets, `-c` summaries, `-f -e trace=network`).
- ~~Package management, firewalls~~: **closed** by linux-tutorial-014
  (apt/dnf, targeted upgrades, `dnf provides`, ufw with source
  restrictions, and the real `nft list ruleset`).
- SELinux/AppArmor (still missing).
- LVM and resizing a filesystem on a grown cloud volume.
- `tmux`/`screen` for surviving disconnects (mentioned, not practiced).

## Readiness verdict

Strong on operating and troubleshooting an existing Linux server — the
incident set here covers problems that genuinely trip up experienced
engineers. Automation is now practiced too (three bash labs of growing
difficulty), but a structural checker is not shellcheck. Write and lint
real scripts to finish the job.

---

# Part 4 — Terraform

**Content:** 11 tutorials, 6 incidents, 2 Writing Labs.

## Covered

Every section of `commands/terraform.md`: the core workflow plus the safe
CI variant (fmt -recursive, validate, plan -out, apply tfplan), variables
and tfvars (and why -var leaves no record), outputs (-json, -raw),
console, state inspection (list/show/pull), state refactoring (mv, rm,
import — plus the modern `moved {}`/`import {}` blocks), workspaces,
remote state migration and locking (-migrate-state vs -reconfigure,
force-unlock), modules/providers/lock files (init -upgrade, cross-
platform `providers lock`), targeted and forced-replacement operations
(-replace superseding the deprecated `taint`, -target's dangers,
-detailed-exitcode for drift detection), and debugging (TF_LOG, graph,
parallelism, plan JSON for policy checks). Incidents cover the failures
that actually hurt Terraform teams: manual-console drift, orphaned state
locks from cancelled pipelines, a refactor that would destroy a
production database, importing pre-existing resources, a floating
provider version breaking CI, and secrets leaked through a committed
state file.

## Still missing

- ~~Writing HCL~~ — **closed** for core authoring: Writing Labs yaml-018
  (pinned provider, variable, interpolated resource, output) and yaml-019
  (harden a production database: prevent_destroy, deletion_protection,
  AWS-managed password, encrypted remote state). A built-in HCL parser
  checks structure and values; it doesn't validate against provider
  schemas the way `terraform validate` does, so a misspelled argument
  name passes.
- ~~Modules, `for_each` vs `count`, data sources~~: **mostly closed** by
  terraform-tutorial-011 (the count-renumbering trap shown in a real
  plan, `state mv` vs `moved` blocks, moving resources into a module
  with a zero-destroy plan, and version pinning). Still unpracticed:
  *writing* a module's variables and outputs yourself (no HCL lab for
  it yet), and `dynamic` blocks.
- Cloud-provider knowledge itself (VPCs, IAM, subnets) — Terraform is
  only as useful as your understanding of what it's creating. This is the
  largest real-world prerequisite and is out of scope for a CLI game.
- Terraform Cloud / Atlantis / OpenTofu workflows, Terragrunt.

## Readiness verdict

Good preparation for safely operating Terraform in a team — the incident
set targets the mistakes that cause real outages and data loss. Pair it
with actual HCL authoring on a free-tier cloud account and cloud
fundamentals study (e.g. an AWS Solutions Architect Associate level) to
be genuinely productive.

---

# Part 5 — Networking

**Content:** 11 tutorials, 7 incidents.

## Covered

Every section of `commands/networking.md`: layered diagnosis (DNS → port
→ application), the refused-vs-timeout branch point, DNS in depth
(resolv.conf search domains, /etc/hosts precedence, querying specific
resolvers, record types, reverse lookups, +trace to the authoritative
source), ports and scanning (lsof, nmap -sV against hosts you own),
routing and ARP (ip route get, `<incomplete>` ARP entries as a layer-2
signal), host firewalls across all three front-ends (ufw, iptables
counters, firewalld's --permanent/--reload trap), TLS (s_client with SNI,
expiry checks, SANs, CSR generation, why `curl -k` is dangerous), HTTP
debugging (auth headers, redirect chains, --resolve to test one backend,
per-phase timing), in-cluster Kubernetes networking, and CIDR/subnet
planning. Incidents cover the most common real network outages: expired
certificates, stale /etc/hosts pins (dig vs getent), localhost-bound
services, firewall-dropped ports, and HTTPS redirect loops behind TLS-
terminating load balancers.

## Still missing

- ~~Packet capture~~: **closed** for tcpdump by networking-tutorial-011
  (choosing the interface, `-nn`, BPF filters on TCP flags, capturing
  at both ends to split the path, `-w` to a pcap). Actually reading a
  pcap in Wireshark is a GUI skill and stays out of scope.
- ~~MTU/fragmentation~~: **closed** by networking-incident-007 (a VPN
  PMTUD black hole: `ping -M do -s`, `tracepath`, blocked ICMP, and MSS
  clamping as the real fix).
- Cloud networking specifics: security groups vs NACLs, NAT gateways,
  VPC peering/Transit Gateway, private endpoints.
- Load balancer internals (L4 vs L7, health checks, connection draining,
  sticky sessions) and service meshes.
- IPv6.

## Readiness verdict

Strong practical troubleshooting foundation — the refused/timeout
distinction and layer-by-layer method taught here resolve the majority of
real "can't connect" incidents, and packet capture and MTU problems are
now covered too. Cloud-provider networking (security groups, NAT, VPC
peering) is the next thing to learn, on real infrastructure.

---

# Part 6 — CI/CD

**Content:** 13 tutorials, 6 incidents, 3 Writing Labs.

## Covered

Every command section of `commands/cicd.md`: git essentials (status,
diff, log, fetch vs pull, stash), merge vs rebase vs cherry-pick (and the
never-rebase-shared-branches rule, --force-with-lease), undoing safely
(revert for pushed work, reset for local, reflog as the safety net),
tags/SemVer/releases (annotated tags, describe, immutable published
versions, gh release), driving GitHub Actions from the CLI (workflow run
with inputs, run watch, --log-failed, rerun --failed), pipeline secrets
(environment-scoped secrets, OIDC over static keys, gitleaks), reproducing
CI failures locally (--no-cache, running tests in the CI image, act),
deployment strategies as real commands (rolling, blue-green via Service
selector, canary via replica ratio with data-driven abort), and the PR
review loop. Incidents: reverting a bad merge instead of force-pushing,
diagnosing a flaky test, responding to a leaked cloud key (revoke →
investigate → clean up), mutable `:latest` tags deploying mixed versions,
and recovering commits lost to a bad rebase.

## Still missing

- ~~Writing pipeline YAML~~ — **largely closed**: three YAML Labs now
  have you write a GitHub Actions workflow from scratch (yaml-006), fix
  one that deploys untested PRs with `needs`/`if`/`environment`
  (yaml-007), and add a version matrix plus dependency caching
  (yaml-008). Still unpracticed: reusable workflows, composite actions,
  and OIDC-based cloud deploys written by hand.
- GitLab CI and Jenkins are recognized in commands/cicd.md but not
  practiced — GitHub Actions is used throughout as the representative.
- ~~GitOps~~: **closed** for Argo CD by cicd-tutorial-011 (sync vs
  health, diff before sync, `app wait --health`, and why a git revert
  beats `argocd app rollback`). Flux isn't covered; the concepts are
  the same.
- ~~SBOMs and supply-chain security~~: **mostly closed** by
  cicd-tutorial-012 (syft SBOMs, grype `--fail-on`, cosign sign/verify
  by digest, `crane digest`). Still missing: SLSA provenance
  attestations, and an admission policy that enforces signatures.
- Database migrations in a deploy pipeline (expand/contract pattern) —
  one of the hardest real-world CD problems.
- ~~`git bisect`~~: **closed** by cicd-tutorial-013 (including `bisect
  run` with an exit-code test script and exit 125 to skip).

## Readiness verdict

Good grounding in the day-to-day operational side of CI/CD — git hygiene,
pipeline debugging, safe rollbacks, and secret handling. Authoring and
designing pipelines is the next skill to build, and needs hands-on YAML
writing that this game only partially supports today.

---

# Part 7 — Monitoring & Observability

**Content:** 12 tutorials, 6 incidents, 2 Writing Labs.

## Covered

Every section of `commands/monitoring.md`: PromQL fundamentals (up, rate
before sum, increase vs rate, ratios, *_over_time and the gauge/counter
distinction), the four golden signals as real queries (error ratio not
count, histogram_quantile's `by (le)`, saturation as the leading
indicator), operating Prometheus (promtool check config, lifecycle
reload, the targets API's lastError), alert rules and Alertmanager
(promtool check/test rules, amtool silences that expire), journald
(priority filters, time windows, previous-boot kernel logs, vacuum),
Elasticsearch operations (health colors, daily indices, disk
watermarks), Loki/LogQL (label selectors first, `| json`, log-derived
metrics), Grafana dashboards via API, and Kubernetes-native monitoring
(top --containers, all-container logs, events, API server metrics).
Incidents cover the failures that blind or exhaust monitoring itself:
silent scrape failures, alert fatigue from a flapping rule, Elasticsearch
flood-stage read-only, a Prometheus cardinality explosion, and runaway
journald volume.

## Still missing

- ~~Distributed tracing~~: **closed** at the operator level by
  monitoring-tutorial-011 (collector health and its span-loss metrics,
  finding services missing from Jaeger, filtering traces by duration,
  reading a span tree). *Instrumenting* code with OpenTelemetry SDKs
  isn't practiced.
- ~~SLOs and error budgets~~: **closed** by monitoring-tutorial-012 (a
  good/total SLI, budget remaining, burn rate, multi-window 14.4x
  paging, and `promtool test rules`). Writing the burn-rate rule file
  yourself would make a good future Writing Lab.
- ~~Writing alert rule YAML~~ — **closed**: YAML Labs yaml-009 (write a
  ratio-based, `for:`-guarded paging rule) and yaml-010 (fix the flapping
  rule from monitoring-incident-003, including its missing `by (le)`).
  Writing Grafana dashboards by hand is still not practiced.
- Hosted/commercial tools (Datadog, New Relic, CloudWatch) — different
  syntax, same concepts.
- Incident-response process itself: declaring an incident, comms,
  writing a blameless post-mortem.

## Readiness verdict

Strong on the Prometheus/logging operator skills that most on-call
rotations rely on, and on the specific ways monitoring systems fail.
Tracing and SLO burn-rate alerting are now covered at the operator
level. What's left is authoring: instrumenting services and writing
dashboards.

---

# Part 8 — MLOps

**Content:** 12 tutorials, 7 incidents.

## Covered

Every section of `commands/mlops.md`: reproducible environments (venv,
exact pins and why they matter more for pickled models, pip freeze,
poetry lock, conda export), GPUs (nvidia-smi and reading the sawtooth
data-loader bottleneck, CSV queries, GPU capacity and allocation on
Kubernetes nodes), MLflow (UI, runs, MLproject reproduction, serving a
logged artifact), DVC (remotes, pointer files, push, status, dag/repro),
model serving (TF Serving, versioned model directories, readiness for
slow-loading models, exposing on Kubernetes), KServe/Kubeflow at an
operator level, profiling training code (pandas memory/dtypes, cProfile,
memory_profiler, notebook-to-script), monitoring models in production
(prediction-score distributions as label-free drift signals, unseen
categories), and model canary rollouts on KServe. Incidents cover the
failures specific to ML systems: silent data drift, training/serving
skew (a units mismatch), GPU hoarding by idle notebooks, pickle/library
version mismatch between notebook and serving, batch-size-driven OOM,
and an unreproducible model trained on unversioned data.

## Still missing

- ~~Feature stores~~: **closed** by mlops-tutorial-012 (Feast plan/apply,
  offline vs online stores, materialization lag as a new form of skew,
  and handling missing or stale feature values when serving).
- ~~LLM serving~~: **mostly closed** by mlops-tutorial-011 (vLLM:
  context length vs concurrency, tensor parallelism, the
  OpenAI-compatible API, and scaling on queue depth and KV cache rather
  than GPU utilization) and mlops-incident-007 (a crash loop caused by
  a model swap's 128k default context). Quantization and speculative
  decoding aren't covered.
- Distributed training (multi-GPU/multi-node, NCCL issues) (still
  missing).
- Model registries' promotion workflows (staging → production approval).
- Writing pipeline definitions (Kubeflow Pipelines / Airflow / Argo
  Workflows DAGs).
- Evaluation and data-validation tooling (Great Expectations, Evidently).

## Readiness verdict

Covers the operational side of MLOps well — the parts where ML meets
DevOps infrastructure, and the distinctive "nothing errors but the model
is wrong" failure mode. LLM serving and feature stores are now covered;
distributed training and writing pipeline DAGs are the biggest gaps
remaining relative to what current MLOps roles ask for.

---

# Part 9 — Overall: will this make you proficient in DevOps?

## By the numbers

| Category | Tutorials | Incidents | Extra |
|---|---|---|---|
| Kubernetes | 29 | 13 | 9 Writing Labs, Sandbox |
| Docker | 11 | 5 | 3 Writing Labs (Dockerfile, Compose), Sandbox, 2 Mysteries |
| Linux | 14 | 6 | 3 Writing Labs (bash), interactive Sandbox, 4 Mysteries |
| Terraform | 11 | 6 | 2 Writing Labs (HCL) |
| Networking | 11 | 7 | |
| CI/CD | 13 | 6 | 3 Writing Labs (Actions) |
| Monitoring | 12 | 6 | 2 Writing Labs (alert rules) |
| MLOps | 12 | 7 | |
| **Total** | **113** | **56** | 22 Writing Labs, 7 career paths, 3 sandboxes, 6 Mystery Incidents, Exam Mode |

Every command section of every `commands/*.md` reference is now covered
by at least one tutorial, and every tutorial step explains *why* that
command beats the alternatives — not just what it does.

## Honest verdict

**Completing everything here will make you a strong DevOps operator: you
will know the commands, the failure modes, and — most importantly — the
debugging method** (check the layer before guessing the fix; refused vs
timeout; verify after every change; revoke before cleaning up; revert
don't force-push). The 56 incidents are modeled on the kinds of problems
that genuinely trip up working engineers, and working through them
builds judgment that command references alone never will.

**It will not, on its own, make you fully proficient**, for four reasons
that no amount of additional scenario content can fully close:

1. **Authoring vs. operating.** Largely addressed: 22 Writing Labs now
   have you write real Kubernetes manifests, GitHub Actions workflows,
   Prometheus alert rules, Compose files, Dockerfiles, Terraform, and
   bash scripts in your own editor. What remains is **depth and
   realism**: the checkers are structural, not the real tools
   (`docker build`, `terraform validate`, shellcheck), so they confirm
   you wrote the right shape, not that it would actually run. Building
   the same files for a real project is still the final test.
2. **Real systems misbehave in unscripted ways.** Every simulated output
   here was written in advance. A real cluster, a real cloud account, and
   real traffic produce errors nobody predicted. **Partly addressed**:
   Mystery Incidents give you only a symptom and a live sandbox. There is
   no prompt telling you what to check next, you can take any path, your
   fixes change the state, and careless fixes cost points (killing sshd
   or init counts as collateral damage). You can't win by guessing: you
   must have actually seen the evidence before you're allowed to answer.
   The outputs are still simulated, though, and there are only 6
   mysteries, none of them Kubernetes. Pair this game with a homelab
   (kind/minikube, a free-tier cloud account) where things break for real.
3. **Cloud-provider fundamentals** (IAM, VPCs, managed services) are a
   prerequisite for Terraform, networking, and CI/CD work, and are out of
   scope for a CLI game.
4. **The human side of operations** — incident command, communication
   during an outage, blameless post-mortems, and knowing when to escalate
   — isn't practiced here at all.

## Recommended path to real proficiency

1. Play every tutorial in each category in order (the `why` notes are
   the point, not the syntax).
2. Play every incident without hints first; read every resolution even
   when you solved it.
3. Take an Exam for each category until you pass (66%) consistently —
   then retake it a week later. Spaced recall is what makes commands
   stick; a single pass right after the tutorials proves little.
4. Complete the Writing Labs for each category.
5. Play all seven Career Paths to practice switching layers mid-problem —
   especially "The Worst On-Call Night".
6. Play every Mystery Incident, then replay it to aim for 100. Scoring
   near the expert's command count means you went straight to the right
   layer instead of wandering.
7. Rebuild each incident for real on a local cluster/VM — break it on
   purpose, then fix it with the same commands.
8. Write the artifacts yourself for one small real project, end to end:
   a Dockerfile, a Terraform module, a GitHub Actions workflow, alert
   rules, and a bash deploy script — the Writing Labs are practice for
   this, not a replacement.
9. For certification goals, see Part 1 (CKA); similar exam-specific gap
   passes haven't been done for other certs (e.g. Terraform Associate,
   AWS) yet.
