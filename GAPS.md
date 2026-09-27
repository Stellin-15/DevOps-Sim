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

What YAML Labs still doesn't replicate: real exam **time pressure**
(there's no clock here), the breadth of an actual live cluster (no real
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

**Explicitly out of scope: Kubeflow.** It's an ML platform (pipelines,
notebooks, training jobs) that happens to run *on* Kubernetes, not a core
Kubernetes/CKA skill — closer to "an application you'd deploy" than "how
the cluster works." It's not on the CKA, and faking realistic Kubeflow
output here would teach a false sense of familiarity with a genuinely
large, separate ecosystem. If that's the actual goal, it needs its own
dedicated resource, not a few kube-sim tutorials.

**Incidents** (006–010): ImagePullBackOff, a readiness-probe cascading
failure, a CoreDNS outage, a silently-nonfunctional HPA (missing
metrics-server), and a NotReady node requiring node-filesystem-level
debugging — chosen specifically because they're either extremely common
in real production (ImagePullBackOff, probe misconfiguration) or teach a
failure mode beginners don't know to look for (silent failures, control
plane being the actual outage).

## What's still not covered (backlog, not addressed this pass)

- Dynamic storage provisioning failures, volume mount troubleshooting
- RBAC-denial as an *incident* (tutorial-012 teaches the commands, but
  there's no investigative incident built around "why can't this pod do X")
- PodDisruptionBudget blocking a drain
- Admission controllers / webhooks
- More YAML Labs — only 5 exist (pod-from-scratch, broken-deployment-fix,
  multi-container/init, NetworkPolicy, PVC); StatefulSet, Ingress, HPA,
  and RBAC (Role/RoleBinding) manifests would be natural next labs
- Kubeflow and other on-top-of-Kubernetes application platforms —
  deliberately out of scope, see above

---

*Written honestly, not to make the tool look complete. If you're using
this for CKA prep: also get time on a real cluster (kind/minikube) before
the exam, especially for YAML-writing speed. If you're using it to build
toward handling production on your own: pair it with actually being on an
on-call rotation, shadowed, before being the primary responder.*

---

# Part 2 — Docker

**Content:** 10 tutorials, 5 incidents.

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

- **Writing Dockerfiles** — same structural issue YAML Labs solved for
  Kubernetes manifests: tutorials teach you to *recognize* instructions
  and debug builds, but never have you write a Dockerfile yourself. A
  "Dockerfile Lab" (like YAML Labs, validating a real file you write) is
  the single highest-value Docker addition left.
- BuildKit specifics (cache mounts, secrets mounts `--secret`),
  multi-platform builds (`docker buildx`) — common in modern CI.
- Registry operations beyond push/login: image signing, digest pinning.
- `docker pause/unpause/rename/attach/diff` — rarely used in practice,
  deliberately skipped.
- Swarm mode — deliberately out of scope (largely displaced by Kubernetes).

## Readiness verdict

Solid for day-to-day development and debugging work with containers.
Missing the hands-on Dockerfile-writing practice that separates "can use
Docker" from "can containerize an app well."

---

# Part 3 — Linux

**Content:** 12 tutorials, 6 incidents.

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

- **Shell scripting** — the biggest gap. Real work means writing bash
  scripts (variables, conditionals, loops, exit codes, `set -euo
  pipefail`). This game teaches one-liners, not scripts. A "Script Lab"
  (validating a real .sh file you write, like YAML Labs) would close it.
- `strace`/`lsof` for deeper process debugging (lsof appears once).
- Package management (apt/dnf/yum) — trivial but universal.
- SELinux/AppArmor, firewalls (ufw/iptables/nftables).
- LVM and resizing a filesystem on a grown cloud volume.
- `tmux`/`screen` for surviving disconnects (mentioned, not practiced).

## Readiness verdict

Strong on operating and troubleshooting an existing Linux server — the
incident set here covers problems that genuinely trip up experienced
engineers. Not yet enough for automating Linux work, which requires
scripting practice this game doesn't offer.

---

# Part 4 — Terraform

**Content:** 10 tutorials, 6 incidents.

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

- **Writing HCL** — as with Dockerfiles, you learn to *operate* Terraform
  here, not to *author* it. A "Terraform Lab" validating a real .tf file
  (via `terraform validate` or HCL parsing) would close this.
- Writing reusable modules (inputs/outputs/versioning), `for_each` vs
  `count` trade-offs, `dynamic` blocks, data sources.
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

**Content:** 10 tutorials, 6 incidents.

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

- **Packet capture** (`tcpdump`, reading a pcap in Wireshark) — the tool
  of last resort for problems nothing else explains. Hard to simulate
  meaningfully as text, but its absence is a real gap.
- MTU/fragmentation problems (large requests hang, small ones work) —
  common with VPNs and overlay networks.
- Cloud networking specifics: security groups vs NACLs, NAT gateways,
  VPC peering/Transit Gateway, private endpoints.
- Load balancer internals (L4 vs L7, health checks, connection draining,
  sticky sessions) and service meshes.
- IPv6.

## Readiness verdict

Strong practical troubleshooting foundation — the refused/timeout
distinction and layer-by-layer method taught here resolve the majority of
real "can't connect" incidents. Cloud-provider networking and packet
capture are the next things to learn on real infrastructure.

---

# Part 6 — CI/CD

**Content:** 10 tutorials, 6 incidents.

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

- **Writing pipeline YAML** — the biggest gap, same as elsewhere. You
  recognize workflow structure here but never author one. A "Pipeline
  Lab" (write a real .github/workflows file, validated like YAML Labs:
  triggers, jobs, `needs`, caching, matrix builds) would close it — and
  the YAML Lab engine could validate it with no new code, only content.
- GitLab CI and Jenkins are recognized in commands/cicd.md but not
  practiced — GitHub Actions is used throughout as the representative.
- GitOps (Argo CD / Flux), artifact repositories, SBOMs and supply-chain
  security (signing images with cosign, SLSA provenance).
- Database migrations in a deploy pipeline (expand/contract pattern) —
  one of the hardest real-world CD problems.
- `git bisect` for finding which commit introduced a regression.

## Readiness verdict

Good grounding in the day-to-day operational side of CI/CD — git hygiene,
pipeline debugging, safe rollbacks, and secret handling. Authoring and
designing pipelines is the next skill to build, and needs hands-on YAML
writing that this game only partially supports today.

---

# Part 7 — Monitoring & Observability

**Content:** 10 tutorials, 6 incidents.

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

- **Distributed tracing** (OpenTelemetry, Jaeger/Tempo) — the third
  pillar of observability, absent entirely. Essential for microservices.
- **SLOs and error budgets** — defining SLIs, burn-rate alerting
  (multi-window, multi-burn-rate). Mentioned conceptually, not practiced.
- Writing alert rule YAML and dashboards (authoring, again — the YAML Lab
  engine could validate alert rule files with content only).
- Hosted/commercial tools (Datadog, New Relic, CloudWatch) — different
  syntax, same concepts.
- Incident-response process itself: declaring an incident, comms,
  writing a blameless post-mortem.

## Readiness verdict

Strong on the Prometheus/logging operator skills that most on-call
rotations rely on, and on the specific ways monitoring systems fail.
Tracing and SLO-based alerting are the major missing pieces for a
modern observability practice.
