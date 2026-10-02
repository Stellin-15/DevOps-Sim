# GAPS.md — will kube-sim actually make you proficient in DevOps?

Honest self-assessment, written from the perspective of a beginner using
this game as their main prep tool for (a) passing the CKA exam and (b)
eventually handling production Kubernetes incidents on their own. Short
answer: **helpful, not sufficient, for both** — and this file exists to be
specific about where it falls short, so nobody mistakes "completed every
scenario" for "ready."

**Structure:** the first half of this file is the original, deepest
assessment — **Kubernetes / CKA**. Each other category (Docker, Linux,
Terraform, Networking, CI/CD, Monitoring, MLOps, the three clouds,
Security, Server Fleet Ops, SRE, Git, System Design, Databases, and Web
Servers) gets its own section
further down, written the same way: what's covered, what a real job
expects, what's still missing. The Backlog part lists every topic that
isn't in the game yet, in tiers. The final section is a cross-category
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
  Incidents (see the final Overall part) practice exactly that, and five of
  them are Kubernetes: a Service whose selector matches nothing, an
  image tag that doesn't exist, a renamed ConfigMap key hiding an OOM
  kill, nodes left cordoned after maintenance, and a readiness probe
  on the wrong path. They run on a second, fixable Kubernetes sandbox
  where pod status is derived from its cause.
- **Escalation and communication**: now **partly covered** by the SRE
  category (Part 14): incident roles, mitigate-first, and the postmortem
  timeline. Actually running an incident with other people (paging,
  status updates, handoffs) still needs real drills.

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
  Volume *attach* failures are now **done** too: incident-015 (a
  Multi-Attach error when a rolling update starts the new pod on
  another node while the old pod still holds a ReadWriteOnce volume).
- ~~RBAC denial as an incident~~: **done** in incident-011 (a job that
  moved namespaces falls back to the 'default' service account;
  diagnosed from the 403 text and `auth can-i --as`).
- ~~PodDisruptionBudget blocking a drain~~: **done** in incident-012.
- ~~Admission controllers / webhooks~~: **done** in incident-014 (a
  validating webhook with `failurePolicy: Fail` whose own pods are
  down, so nothing can be created, including its replacement) and
  security-tutorial-011 (Kyverno policies, Enforce vs Audit).
- ~~More YAML Labs~~ — **done**: StatefulSet, Ingress (with TLS), HPA,
  and RBAC (Role + RoleBinding) labs added, for 9 Kubernetes labs total
- ~~The wider ecosystem~~: **done** in tutorial-030 to 035 (Kustomize,
  writing a Helm chart, Gateway API, VPA/KEDA/Karpenter, Flux, and
  Linkerd), incident-016 (a Helm release stuck in pending-upgrade) and
  incident-017 (a node autoscaler stopped by its own limit), plus
  Writing Labs yaml-037 (a Kustomize overlay) and yaml-038 (an
  HTTPRoute with a canary split). Not covered: external-dns, writing
  chart templates in depth (helpers, hooks, library charts), Cluster
  API, and CKAD/CKS-specific passes.
- ~~Backup, fleets, and tenancy~~: **done** in tutorial-036 (Velero and
  CSI snapshots, with a restore test), tutorial-037 (Cluster API and
  ApplicationSets), tutorial-038 (quotas, limit ranges, network and API
  isolation, virtual clusters), and incident-018 (a restore that came
  back with no data).
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

**Content:** 15 tutorials, 6 incidents, 4 Writing Labs, and an interactive
Sandbox: a server with two random real problems (failed service blocked by
a stray process, disk filled by a log held open by a process, runaway CPU,
memory hog that got postgres OOM-killed, and, since the security pass, a
crypto-miner with cron persistence or an SSH backdoor) that you must find
AND fix with kill / systemctl restart / rm / truncate / crontab -r /
userdel / sed. It models real consequences —
deleting a log a process still holds open frees nothing until you restart
that process — which unscripted practice needs and scripted steps can't give.
Six Mystery Incidents run on that sandbox (two of them are the hacked-server ones, listed under Security). Each is a symptom only, which
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
  `trap ... EXIT` cleanup, and the `((n++))`-under-`set -e` trap, and
  yaml-031 adds `getopts` option parsing and `while IFS= read -r`
  loops over a file. Still unpracticed: a real shellcheck pass.
- ~~`strace`/`lsof`~~: **closed** by linux-tutorial-013 (attach to a hung
  process, map fds to sockets, `-c` summaries, `-f -e trace=network`).
- ~~Package management, firewalls~~: **closed** by linux-tutorial-014
  (apt/dnf, targeted upgrades, `dnf provides`, ufw with source
  restrictions, and the real `nft list ruleset`).
- ~~SELinux~~: **closed** by linux-tutorial-015 (reading AVC denials
  with `ausearch`, file contexts with `ls -Z`, `semanage fcontext` plus
  `restorecon`, and booleans with `setsebool -P`). AppArmor, Ubuntu's
  equivalent, is still missing.
- ~~LVM and resizing a filesystem on a grown cloud volume~~: **closed** by
  servers-tutorial-010 (growpart, pvresize, `lvextend -r`, all online).
- `tmux`/`screen` for surviving disconnects (mentioned, not practiced).

## Readiness verdict

Strong on operating and troubleshooting an existing Linux server — the
incident set here covers problems that genuinely trip up experienced
engineers. Automation is now practiced too (three bash labs of growing
difficulty), but a structural checker is not shellcheck. Write and lint
real scripts to finish the job.

---

# Part 4 — Terraform

**Content:** 16 tutorials, 7 incidents, 5 Writing Labs (the VPC and
security-group labs are described under AWS, Part 9).

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
  with a zero-destroy plan, and version pinning). Writing a module is
  now **closed** too: terraform-tutorial-012 (validating a module in
  isolation, variable validation, `dynamic` blocks, `terraform test`)
  and Writing Lab yaml-032 (a module's variables.tf, a main.tf with a
  dynamic block, and outputs.tf).
- Cloud-provider knowledge itself (VPCs, IAM, subnets). Terraform is
  only as useful as your understanding of what it's creating.
  **Now partly covered** by the AWS category (Part 9) and its VPC
  sandbox.
- ~~Team workflows and neighbouring tools~~: **closed** by
  terraform-tutorial-013 (OpenTofu, Terragrunt, Atlantis, state
  splitting), terraform-tutorial-014 (Checkov, plan JSON, Conftest and
  Rego, where checks run), terraform-tutorial-015 (Packer images), and
  terraform-tutorial-016 (CloudFormation change sets, Bicep what-if,
  Pulumi preview, Crossplane), with terraform-incident-007 (a stack
  stuck in UPDATE_ROLLBACK_FAILED). Writing Rego, Pulumi programs,
  CloudFormation or Bicep templates, and Crossplane compositions isn't
  practised; nor are Terraform Cloud, Spacelift, or Infracost.

## Readiness verdict

Good preparation for safely operating Terraform in a team — the incident
set targets the mistakes that cause real outages and data loss. Pair it
with actual HCL authoring on a free-tier cloud account and cloud
fundamentals study (e.g. an AWS Solutions Architect Associate level) to
be genuinely productive.

---

# Part 5 — Networking

**Content:** 17 tutorials, 8 incidents.

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
- ~~Cloud networking specifics~~: **mostly closed** for AWS by Part 9.
  The AWS sandbox makes you debug security groups vs NACLs, IGW and NAT
  routes, and VPC endpoints hands-on. Peering, Transit Gateway, and
  PrivateLink are **closed** by aws-tutorial-014.
- ~~Load balancer internals and meshes~~: **closed** across categories:
  L4 vs L7 and gRPC balancing in networking-tutorial-016, proxies in Web
  Servers (Part 18), and meshes in tutorial-035 and the SRE part.
- ~~VPNs, BGP, DNS servers, HTTP/2 and gRPC, CNI~~: **closed** by
  networking-tutorial-013 (WireGuard and AllowedIPs), 014 (reading BGP
  sessions and advertisements), 015 (delegation, authoritative answers,
  SOA, CoreDNS), 016 (HTTP/2, HTTP/3, grpcurl and gRPC status codes),
  and 017 (Cilium and Hubble flow verdicts), with
  networking-incident-008 (overlapping AllowedIPs). Not covered: IPsec,
  designing BGP policy, DNSSEC, Calico, and running BIND.
- ~~IPv6~~: **closed** at the basics level by networking-tutorial-012
  (v6 addresses, AAAA records, `curl -6`, dual-stack listeners, and the
  v6 routing table). IPv6-only clusters and NAT64 aren't covered.

## Readiness verdict

Strong practical troubleshooting foundation — the refused/timeout
distinction and layer-by-layer method taught here resolve the majority of
real "can't connect" incidents, and packet capture and MTU problems are
now covered too. Cloud-provider networking (security groups, NAT, VPC
peering) is the next thing to learn, on real infrastructure.

---

# Part 6 — CI/CD

**Content:** 20 tutorials, 8 incidents, 3 Writing Labs.

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
- ~~GitLab CI and Jenkins~~: **closed** by cicd-tutorial-016 (GitLab
  pipelines, jobs, runners, rules) and cicd-tutorial-017 (Jenkins
  through its API: build results, console logs, Jenkinsfile linting,
  agents), incidents cicd-incident-007 (runners removed by a token
  clean-up) and cicd-incident-008 (agents offline with full disks), and
  Writing Lab yaml-039 (a .gitlab-ci.yml). Writing a Jenkinsfile isn't
  practiced (no checker for Groovy). Azure DevOps Pipelines, CircleCI,
  and Tekton aren't covered.
- ~~Artifact registries and release automation~~: **closed** by
  cicd-tutorial-018 (promote by copying, digests, immutable tags, OCI
  charts) and cicd-tutorial-019 (Conventional Commits, semantic
  versioning, semantic-release, Renovate).
- ~~Testing in delivery~~: **closed** by cicd-tutorial-020 (reproducing
  flaky tests, random ordering and seeds, quarantine, contract tests
  with Pact, and preview environments).
- ~~GitOps~~: **closed** for Argo CD by cicd-tutorial-011 (sync vs
  health, diff before sync, `app wait --health`, and why a git revert
  beats `argocd app rollback`). Flux isn't covered; the concepts are
  the same.
- ~~SBOMs and supply-chain security~~: **mostly closed** by
  cicd-tutorial-012 (syft SBOMs, grype `--fail-on`, cosign sign/verify
  by digest, `crane digest`). SLSA provenance is now **closed** by
  cicd-tutorial-015 (`cosign attest` and `verify-attestation`, reading
  the predicate, `gh attestation verify`), and admission enforcement
  by security-tutorial-011 (Kyverno).
- ~~Database migrations in a deploy pipeline~~: **closed** by
  cicd-tutorial-014 (expand, backfill, contract, with `lock_timeout` so
  a schema change can't queue behind a long query and block the
  table). Online schema-change tools (gh-ost,
  pt-online-schema-change) aren't covered.
- ~~`git bisect`~~: **closed** by cicd-tutorial-013 (including `bisect
  run` with an exit-code test script and exit 125 to skip).

## Readiness verdict

Good grounding in the day-to-day operational side of CI/CD — git hygiene,
pipeline debugging, safe rollbacks, and secret handling. Authoring and
designing pipelines is the next skill to build, and needs hands-on YAML
writing that this game only partially supports today.

---

# Part 7 — Monitoring & Observability

**Content:** 17 tutorials, 8 incidents, 2 Writing Labs.

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
  reading a span tree). Instrumenting is now covered by
  monitoring-tutorial-013 (auto-instrumentation, the `OTEL_*`
  variables, head vs tail sampling, `otelcol validate`). Manual spans
  are **closed** by Writing Lab yaml-044 (a span, attributes, and error
  status around a business step, in Python).
- ~~SLOs and error budgets~~: **closed** by monitoring-tutorial-012 (a
  good/total SLI, budget remaining, burn rate, multi-window 14.4x
  paging, and `promtool test rules`). Writing the rules is **closed**
  by Writing Lab yaml-043 (fast and slow multi-window burn alerts).
- ~~Writing alert rule YAML~~ — **closed**: YAML Labs yaml-009 (write a
  ratio-based, `for:`-guarded paging rule) and yaml-010 (fix the flapping
  rule from monitoring-incident-003, including its missing `by (le)`).
  Dashboards are **closed** by Writing Lab yaml-042 (a rate, errors,
  and duration dashboard as JSON, with a template variable).
- ~~Log pipelines~~: **closed** by monitoring-tutorial-014 (Fluent Bit:
  DaemonSet health, dropped and retried records, multiline, buffering),
  monitoring-tutorial-015 (Vector: validation, transform tests, dropping
  at the source), and monitoring-tutorial-016 (volume by source, label
  cardinality, retention tiers), with incidents monitoring-incident-007
  (collectors OOM-killed during an outage) and monitoring-incident-008
  (a per-request label hitting Loki's stream limit). Logstash and
  OpenSearch-specific operations aren't covered.
- ~~Hosted tools~~: **partly closed** by monitoring-tutorial-017 (the
  Datadog agent's status and checks, tag cardinality as cost, Sentry
  releases and commits). New Relic, CloudWatch in depth, and building
  monitors and dashboards inside those products aren't covered.
- Incident-response process: **partly covered** by SRE (Part 14). It
  covers severity from user impact, mitigate-first, rebuilding the
  timeline, and the postmortem structure. Live comms practice is still
  missing.

## Readiness verdict

Strong on the Prometheus/logging operator skills that most on-call
rotations rely on, and on the specific ways monitoring systems fail.
Tracing and SLO burn-rate alerting are now covered at the operator
level, and so is auto-instrumenting a service. Authoring is now
practised too: a manual span, a dashboard, and burn-rate rules each have
a Writing Lab. What's left is the vendor products themselves.

---

# Part 8 — MLOps

**Content:** 18 tutorials, 8 incidents.

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
- ~~Distributed training~~: **closed** at the operator level by
  mlops-tutorial-013 (GPU topology, `torchrun`, learning-rate scaling,
  NCCL choosing the wrong interface, PyTorchJob). Batch schedulers
  (Slurm, Volcano gang scheduling) are only mentioned.
- Model registries' promotion workflows (staging → production approval).
- ~~Pipeline DAGs~~: **partly closed** by mlops-tutorial-014, which
  covers *operating* Airflow (import errors, `tasks test`, backfill and
  idempotency, manual triggers). Writing one is **closed** by
  dataeng-tutorial-001 and Writing Lab yaml-049.
- ~~LLM operations~~: **closed** by mlops-tutorial-015 (evaluation suites
  and model upgrades), 016 (vector search with pgvector: indexes, recall,
  freshness), 017 (tokens, caching, prompt injection, request logging),
  and 018 (quantization and GPU cost), with mlops-incident-008 (query and
  document embeddings from different models). Fine-tuning, agents and
  tool orchestration, and speculative decoding aren't covered.
- Data-validation tooling (Great Expectations, Evidently).

## Readiness verdict

Covers the operational side of MLOps well — the parts where ML meets
DevOps infrastructure, and the distinctive "nothing errors but the model
is wrong" failure mode. LLM serving, feature stores, distributed
training, and operating pipelines are now covered; writing pipeline DAGs
and evaluation tooling are the biggest gaps remaining relative to what
current MLOps roles ask for.

---

# Part 9 — AWS

**Content:** 14 tutorials, 7 incidents, an interactive AWS Sandbox, and
4 Mystery Incidents on it.

The sandbox is a fake account with one production VPC:
- a public and a private subnet;
- an internet gateway (IGW) and a NAT gateway;
- security groups and network ACLs;
- three instances.

Traffic is evaluated for real, layer by layer: public IP → route table →
NACL (stateless, in both directions) → security group. Every failure
looks the same from outside (a timeout), so you have to read the
configuration to find the broken layer. Fixes change the state:
- create-route and replace-route;
- authorize and revoke security group rules;
- network ACL entries;
- Elastic IPs;
- NAT gateways.

Careless fixes count as collateral damage: opening SSH to 0.0.0.0/0,
or terminating an instance.

## Covered

**Tutorials** (every section of `commands/aws.md`):
- identity and profiles (`sts get-caller-identity`, `AWS_PROFILE`, regions);
- EC2 navigation with `--filters`/`--query`, status checks, and console output;
- SSM Session Manager vs SSH vs EC2 Instance Connect, plus Run Command across a fleet;
- VPC anatomy (subnets, route tables, IGW, NAT per AZ);
- security groups vs NACLs (auditing 0.0.0.0/0, source-group references, NACL deny rules);
- IAM roles, policies, the policy simulator, assume-role, and decoding authorization messages;
- S3 (Block Public Access, versioning, presigned URLs);
- CloudWatch Logs and Insights, alarms, metrics, and CloudTrail;
- ALB target health and health-check design, ASG instance refresh;
- ECR login and scanning, EKS kubeconfig and the IAM-to-RBAC mapping;
- cost and governance (Cost Explorer, orphaned volumes and EIPs, the tagging API, Security Hub).

**Incidents:**
- an SCP explicit deny that no IAM change can fix;
- a public S3 bucket (contain first, then read access logs to see what was taken);
- ALB 502s from a moved health-check path;
- a leaked access key with attacker persistence and crypto-mining in an unused region;
- an instance stuck in emergency mode after NVMe device renaming;
- an EKS node role missing ECR read access;
- an $18k NAT gateway bill fixed with an S3 gateway endpoint.

**Mysteries:** a missing IGW route, a private route table with no NAT
route, a security group missing 443, and a stateless NACL dropping replies.

## Still missing

- ~~Writing IAM policies and VPC Terraform yourself~~: **closed** by Writing
  Labs yaml-023 (rewrite an over-broad policy to least privilege, including
  the object-vs-bucket ARN split), yaml-024 (a full two-tier VPC with IGW,
  NAT, and route tables), and yaml-025 (remove SSH from a security group
  in favour of SSM).
- ~~RDS operations~~: **closed** by aws-tutorial-012 (Multi-AZ, backup
  retention, manual snapshots, point-in-time restore, pending
  modifications). Aurora, parameter groups, DynamoDB capacity, and
  Lambda/serverless debugging are still missing.
- ~~Route 53~~: **closed** by aws-tutorial-013 (public vs private zones,
  alias records, lowering the TTL before a migration, `get-change`, and
  querying the authoritative servers). Health-check failover routing is
  described, not practiced.
- ~~Multi-account networking~~: **closed** by aws-tutorial-014 (peering
  and its non-transitivity, Transit Gateway routes and black holes,
  PrivateLink).
- CloudFormation/CDK (Terraform is used as the infrastructure-as-code representative).
- KMS key policies, and Secrets Manager rotation.
- The AWS Certified Solutions Architect / SysOps exam breadth: this is an
  operator's toolkit, not an exam pass.

## Readiness verdict

Enough to be useful on day one in an AWS shop:
- you can find things;
- you can tell which network layer is dropping traffic;
- you can read and test IAM;
- you respond to the most common AWS security incidents in the right order
  (contain, then investigate).

Pair it with a real free-tier account. Build the sandbox's VPC yourself with
Terraform, then break it on purpose.

---

# Part 10 — Azure

**Content:** 10 tutorials, 6 incidents, an interactive Azure Sandbox, and
3 Mystery Incidents on it.

## Covered

**Tutorials** (every section of `commands/azure.md`):
- login, subscriptions, and CLI defaults;
- resource groups, tags, and delete locks;
- VMs, including the stopped vs *deallocated* billing trap, and resizing;
- Run Command, `az ssh vm` with Entra ID, Bastion, and boot diagnostics;
- VNets and NSGs (priorities, service tags, NIC- vs subnet-level NSGs,
  effective rules, IP flow verify);
- UDRs and hub-and-spoke firewall routing, with effective routes and next hop;
- RBAC scopes and managed identities, with control plane vs data plane;
- Key Vault and storage network rules;
- Activity Log, metrics, and KQL;
- AKS credentials, node pools, and upgrades.

**Incidents:**
- a Deny rule with source '*' shadowing an allow;
- a UDR pointing at a non-existent firewall IP;
- a managed identity holding Contributor but no data-plane role;
- a deallocated VM that lost its dynamic IP;
- a merged kubeconfig that sent a staging script to prod;
- a storage firewall flipped to Deny before the app subnet was allowed.

## Still missing

- ~~An Azure sandbox~~: **closed**. The Azure sandbox evaluates NSG
  priorities (with Azure's default rules), subnet plus NIC-level NSGs,
  and user-defined routes to a firewall, and `test-ip-flow` and
  `show-next-hop` answer from the real state. Three mysteries run on it.
- Bicep and ARM templates (Terraform is the IaC representative).
- App Service, Functions, Azure SQL, Cosmos DB, and Front Door/Application
  Gateway operations.
- Entra ID administration (conditional access, PIM), and Azure Policy authoring.
- AZ-104 / AZ-400 exam breadth.

## Readiness verdict

A solid operator's foundation for an Azure shop: you can find resources,
debug network paths with Network Watcher, and avoid the classic cost and
identity traps. The sandbox makes NSG and route debugging hands-on; a free
account is still where you learn the parts the sandbox doesn't model
(Application Gateway, private endpoints, real latency and propagation
delays).

---

# Part 11 — Google Cloud

**Content:** 10 tutorials, 6 incidents, an interactive Google Cloud Sandbox,
and 3 Mystery Incidents on it.

## Covered

**Tutorials** (every section of `commands/gcp.md`):
- gcloud configurations, projects, APIs, and Application Default Credentials;
- Compute Engine `--filter`/`--format`, TERMINATED meaning *stopped*, and the
  default service account risk;
- SSH through IAP with `--troubleshoot`, the serial console, and IAP TCP tunnels;
- global VPCs with regional subnets, and Private Google Access;
- firewall rules by network tag or service account, LB health-check ranges,
  and audit logs;
- Cloud Router and Cloud NAT, including NAT port exhaustion;
- IAM bindings, service accounts without keys, impersonation, and the
  Policy Troubleshooter;
- Cloud Storage public access prevention;
- Logging queries and quotas;
- GKE credentials, Spot pools, Workload Identity, and release channels.

**Incidents:**
- a firewall rule targeting a tag the VM doesn't have;
- private VMs in a region with no Cloud NAT;
- a disabled API mistaken for a permissions problem;
- a firewall cleanup that deleted the IAP rule;
- a leaked service-account key with attacker persistence;
- an autoscaler blocked by a machine-family quota.

## Still missing

- ~~A GCP sandbox~~: **closed**. The Google Cloud sandbox evaluates
  tag-targeted firewall rules (priority, deny beats allow, implied deny),
  IAP SSH, and regional Cloud NAT. Three mysteries run on it.
- Cloud Run, Cloud SQL, BigQuery, Pub/Sub, and Cloud Load Balancing internals.
- Shared VPC and VPC Service Controls, and organisation policy authoring.
- Professional Cloud Architect / DevOps Engineer exam breadth.

## Readiness verdict

Enough to operate GCP projects confidently. You'll understand what makes
GCP networking different (a global VPC, tag-based firewalls, and regional
NAT) and follow its keyless IAM best practices.

## Cross-cloud map

The three clouds use different names for the same ideas:

| Concept | AWS | Azure | Google Cloud |
|---|---|---|---|
| Account boundary | Account (in an Organization) | Subscription (in a tenant) | Project (in an Organization) |
| VM | EC2 instance | Virtual Machine | Compute Engine instance |
| Private network | VPC (regional) | VNet (regional) | VPC network (**global**) |
| Subnet | Per availability zone | Per region (zone chosen per resource) | Per region |
| Instance firewall | Security group (stateful, allow-only) | NSG (stateful, priorities, allow + deny) | Firewall rule (stateful, network-wide, by tag or SA) |
| Subnet firewall | NACL (**stateless**) | NSG on the subnet | (none; hierarchical policies at the org level) |
| Outbound for private VMs | NAT gateway + route | NAT gateway or firewall + UDR | Cloud Router + Cloud NAT (regional) |
| Workload identity | Instance profile / IRSA | Managed identity | Attached service account / Workload Identity |
| "Who changed what" | CloudTrail | Activity Log | Cloud Audit Logs |
| Shell without SSH | SSM Session Manager | Run Command / Bastion | IAP tunnel / serial console |
| Console of a dead VM | get-console-output | Boot diagnostics | Serial port output |
| Block public buckets | S3 Block Public Access | Storage network rules / private endpoint | Public access prevention |

---

# Part 12 — Security (defensive)

**Content:** 16 tutorials, 7 incidents, and 2 hacked-server Mystery Incidents
on the Linux sandbox.

The Linux sandbox gained two compromise scenarios, and both are playable
there at random too.

**Crypto-miner:**
- a disguised miner running as www-data from `/tmp/.x`;
- a connection to a mining pool on port 3333;
- a www-data cron job that re-downloads it every five minutes.

Killing it without removing the cron job brings it back with a new pid.

**SSH backdoor:**
- a brute-forced root password;
- a second UID-0 account;
- an attacker key in root's `authorized_keys`.

Everything is evidenced in `auth.log`, `last`, and `/etc/passwd`. Careless
cleanup counts as collateral damage:
- deleting every SSH key, which locks out the ops team;
- `crontab -r` without `-u`, which deletes root's backup job;
- removing real accounts.

## Covered

**Tutorials** (every section of `commands/security.md`):
- nmap discovery and full-range scans;
- service versions and TLS checks (ssl-enum-ciphers, testssl.sh, certificate expiry);
- Trivy for images, repos, IaC, and clusters, plus kube-bench;
- Lynis and OpenSCAP CIS audits;
- SSH hardening in a lock-out-safe order (`sshd -T`, `sshd -t`, reload, test from outside);
- brute-force analysis and fail2ban;
- auditd (watches, ausearch by auid, aureport, persistent rules);
- osquery and AIDE file integrity;
- secrets scanning with gitleaks and trufflehog, rotating before rewriting history;
- a first-15-minutes compromise triage checklist.

**Incidents:**
- an SSH brute force (did anyone get in?);
- a secret in git history before open-sourcing;
- an internet-exposed Redis used to plant an SSH key;
- a PHP web shell through an unsafe upload plus nginx config;
- beaconing from a typosquatted Python package's systemd timer;
- fleet-wide response to a critical CVE (xz-utils, CVE-2024-3094).

## Still missing

- **Offensive testing**, deliberately. Penetration testing and exploitation are
  out of scope for a DevOps game; the category is defensive: find your own
  exposure, harden, detect, and respond.
- ~~Detection rules~~: **closed** by security-tutorial-015 (Sigma:
  linting, conversion, tuning, testing, ATT&CK coverage) and Writing Lab
  yaml-046. Working inside a specific SIEM product and commercial EDR
  consoles are still missing.
- ~~Posture, compliance, threat modelling, zero trust~~: **closed** by
  security-tutorial-012 (Prowler and CIS), 013 (frameworks and producing
  evidence), 014 (STRIDE, as decision steps), and 016 (short-lived
  certificates and just-in-time access), with security-incident-007 (a
  former employee's key still in use).
- ~~SELinux troubleshooting~~: **closed** by linux-tutorial-015 (Part 3).
  AppArmor is still missing.
- ~~Kubernetes admission policy and runtime detection~~: **closed** at the
  operator level by security-tutorial-011 (Kyverno Enforce vs Audit, a
  blocked privileged pod, `kyverno apply` in CI, policy reports, and reading
  Falco alerts) and incident-014 (a webhook that deadlocks the cluster).
  Writing them is **closed** by Writing Labs yaml-047 (a Kyverno policy)
  and yaml-048 (a Falco rule). OPA Gatekeeper and network policy
  auditing are still missing.
- Incident-response process: evidence handling, legal and breach-notification
  duties. Only mentioned in debriefs.

## Readiness verdict

Strong practical grounding for the security side of a DevOps or SRE role:
- scanning your own attack surface;
- hardening the commonly audited controls;
- recognising the most frequent real compromises (miners, backdoors,
  exposed datastores, leaked secrets, supply-chain packages);
- responding in the right order (look, preserve, find persistence, contain,
  rebuild).

It is not a security-engineer or penetration-testing curriculum.

---

# Part 13 — Server Fleet Operations

**Content:** 13 tutorials, 7 incidents.

## Covered

**Tutorials** (every section of `commands/servers.md`):
- Ansible inventories and ad-hoc commands;
- running playbooks safely (syntax check, list-hosts, check plus diff,
  canary with --limit, tags);
- rolling changes with `serial` and `max_fail_percentage`;
- Ansible Vault, ansible-lint, and pinned Galaxy roles;
- Debian/Ubuntu patching (security origins, holds, needrestart, reboot-required);
- RHEL-family patching (advisories, security-only upgrades, `dnf history undo`,
  versionlock, needs-restarting);
- kernels and /boot, live patching, and planned reboots;
- AWS SSM Patch Manager with concurrency and error limits;
- time sync with chrony;
- growing a disk online (growpart, pvresize, `lvextend -r`), which closes
  the Linux LVM gap;
- backups with restic, database-consistent dumps, and restore tests.

**Incidents:**
- automatic patching jumping a major version (undo, then re-apply security
  fixes under a lock);
- the whole fleet rebooting at the same minute;
- clock drift from a dead NTP source breaking JWTs;
- a full /boot breaking dpkg mid-kernel-install;
- a playbook run against production through a default inventory (with a
  table-level restore);
- backups of a live data directory that never restored.

## Still missing

- Writing Ansible: **partly closed** by Writing Lab yaml-026 (a rolling patch
  playbook with serial, a failure limit, a conditional reboot, and a health
  check). Writing reusable roles, and running them against real VMs, is
  still hands-on work.
- Other configuration-management tools (Puppet, Chef, Salt), and image
  pipelines (Packer golden images; immutable infrastructure as the
  alternative to patching in place, mentioned in debriefs).
- Windows Server fleets (WSUS, Group Policy), and hardware (RAID, IPMI/BMC,
  firmware).
- Point-in-time database recovery (pgBackRest, WAL-G) beyond logical dumps.

## Readiness verdict

This is the day-to-day work of an ops or infrastructure team:
- patching safely and reversibly;
- rebooting without correlated outages;
- keeping clocks, disks, and kernels healthy;
- having backups that are proven by restores.

The biggest remaining step is writing your own Ansible roles against a few
real VMs.

---

# Part 14 — SRE: How Large Companies Run Production

**Content:** 13 tutorials, 6 incidents.

**What's taught, honestly:** Google's and Meta's internal tools (Borg,
Borgmon, Tupperware, and the internal deploy and config systems) aren't
public, so nobody outside can practise them. This category teaches the
*practices* those companies made standard, using the open-source tools
that descend from or implement them:
- Kubernetes (from Borg);
- Prometheus (inspired by Borgmon);
- Argo Rollouts and Istio (progressive delivery and service mesh);
- the SLO, error-budget, and postmortem discipline of the Google SRE books.

## Covered

**Tutorials** (every section of `commands/sre.md`):
- the first ten minutes of an incident (quantify, what changed, mitigate first,
  verify, annotate);
- Argo Rollouts canaries with automated analysis, promote, and abort;
- Istio sync, analysis, weighted routing, outlier detection, and bounded
  retries and timeouts;
- capacity planning (predict_linear, peak subqueries, requested vs used CPU,
  N+1, growth and lead time);
- load testing (k6 thresholds, vegeta open-model constant rate, finding the
  bottleneck, histograms);
- chaos engineering (tc netem, Chaos Mesh, hypothesis, abort, and cleanup);
- feature flags and kill switches;
- rebuilding a postmortem timeline from git, ReplicaSets, metrics, and alerts;
- graceful degradation and load shedding;
- a production readiness review.

**Incidents** (the textbook large-scale failure modes):
- a retry storm (27x amplification);
- a slow dependency with no timeout or circuit breaker;
- a bad global config push to every region at once;
- a cache stampede;
- a noisy-neighbour batch job;
- a non-essential dependency wired into readiness probes.

## Still missing

- **The human side, practised live.** Incident command roles, stakeholder
  comms, and escalation are explained in the tutorials, and the Writing Labs
  include a postmortem, but running an incident with other people can only
  be practised in real game days or drills.
- Multi-region architecture work (active-active data, failover drills, DNS
  and global load balancing) and disaster-recovery exercises.
- Distributed systems theory behind it all: consensus (Raft/Paxos),
  consistency models, queues and backpressure.
- The SRE hiring-interview style of 'design a system for N users' (NALSD).

## Readiness verdict

This is the practices layer that distinguishes a senior SRE or DevOps
engineer: you'll recognise and prevent the failure patterns that cause
most large outages, and know the standard defences:
- mitigate first;
- canaries;
- bounded retries;
- timeouts and circuit breakers;
- shedding;
- isolation;
- staged config rollouts;
- blameless postmortems.

Read the free Google SRE books alongside it; this category is their
hands-on companion.

---

# Part 15 — Git

**Content:** 11 tutorials, 6 incidents.

Git already appeared inside CI/CD (Part 6): everyday workflow, revert vs
reset, tags, and `git bisect`. This category is Git as a tool in its own
right: how it stores things, and how to get out of trouble.

## Covered

Every section of `commands/git.md`:
- **How Git stores things:** objects, refs, and HEAD, which is what makes
  every later command predictable.
- **Staging precisely:** partial staging and small, reviewable commits.
- **Branches:** tracking, upstreams, and cleaning up merged branches.
- **Merging and conflicts:** reading conflict markers, taking one side,
  aborting, `rerere`, and reverting a merge with `revert -m`.
- **Rebasing:** autosquash and fixup commits, `--onto`, staying current
  with main, and pushing the result with `--force-with-lease`.
- **Undoing:** the full matrix of restore, reset, revert, amend, and the
  reflog, by what each one touches.
- **Searching history:** blame, the pickaxe (`log -S`), and following a
  line or a file through renames.
- **Remotes:** forks, upstream sync, and pruning.
- **Interruptions:** stash and worktrees.
- **Configuration:** .gitignore, .gitattributes (line endings), and hooks.
- **Large and unusual repositories:** shallow and partial clones, sparse
  checkout, submodules, and LFS.
- **Signing:** signed commits and tags, and verifying them.

Incidents, each one a real "I've lost my work" moment:
- three commits made on main that belonged on a branch;
- commits made on a detached HEAD that seem to have vanished;
- a push rejected for a 300MB file buried five commits back;
- `reset --hard` over a day of uncommitted work, and what is and isn't
  recoverable;
- every file showing as modified (line endings), and a script that won't
  run in a container;
- a re-merged branch that "succeeds" and brings none of its code,
  because the earlier merge was reverted.

## Still missing

- **A real repository.** Outputs are pre-written, so you never edit a
  rebase todo list or resolve a conflict in your own editor. A Git
  sandbox (a real temp repo the game inspects) would close this, and it's
  the most valuable next step for this category.
- Code-review practice: pull-request etiquette, stacked changes, Gerrit.
- Branching strategies compared in depth (trunk-based vs GitFlow vs
  release branches). CI/CD touches this; neither part drills it.
- Platform settings that matter as much as commands: branch protection,
  required checks, CODEOWNERS, merge queues.
- Less common commands: `range-diff`, `subtree`, `bundle`, `notes`,
  `maintenance`, and repository internals (packfiles, commit-graph).
- Monorepo tooling at scale (sparse index, Sapling, build-system
  integration).

## Readiness verdict

Enough to stop being afraid of Git. You'll know which undo command
touches what, that almost anything committed is recoverable through the
reflog, and that uncommitted work is not. The incidents cover the
situations that make people re-clone the repository. Practise the same
recoveries in a throwaway real repo, because conflict resolution is a
hands-on skill.

---

# Part 16 — System Design

**Content:** 11 tutorials, 6 incidents, 2 Writing Labs (design documents).

System design is mostly judgment, which a command matcher can't check
directly. So this category mixes three kinds of step:
- **real commands** against the pieces designs are built from (nginx,
  Redis, PostgreSQL, Kafka, etcd, HTTP headers with curl);
- **decision steps**, multiple-choice questions where you type a letter,
  each with a `why` that explains the trade-off and why the other
  options lose;
- **design documents**, written in Markdown in your own editor and
  checked for the sections a real design review expects.

## Covered

Every section of `commands/systemdesign.md`:
- **Estimation:** requests per second, storage, and bandwidth from daily
  users, and what the numbers rule in or out.
- **Scaling out:** load balancers, health checks, and stateless servers.
- **Caching:** cache-aside vs write-through, expiry, eviction, and
  stampedes.
- **Databases:** indexes and query plans, and choosing a store.
- **Replication:** read replicas, lag, and failover.
- **Partitioning:** shard keys, hot partitions, and consistent hashing.
- **Queues:** asynchronous work, consumer lag, retries, dead-letter
  queues, and backpressure.
- **Consistency:** availability trade-offs and quorums.
- **API robustness:** rate limiting, idempotency keys, and timeouts.
- **The edge:** CDNs, HTTP caching headers, and DNS.
- **A worked design:** a URL shortener, end to end.

Incidents are the failures those designs produce:
- one partition doing all the work (a bad key);
- "I saved it and it changed back" (reading from a lagging replica);
- customers charged twice (a retry without an idempotency key);
- scaling the app tier took the database down (connection exhaustion);
- stale prices after a sale ended (cache and CDN expiry);
- a queue that grew without limit and took its neighbours with it.

Writing Labs yaml-029 and yaml-030 have you write design documents for
a URL shortener and a rate limiter.

## Still missing

- **Feedback on quality.** The design-document labs check that the
  required sections and key terms are present. They can't tell a good
  design from a bad one that uses the right words. Have a person review
  your documents.
- Distributed transactions: sagas, the outbox pattern, two-phase commit.
- CQRS and event sourcing.
- Multi-region designs: active-active, data residency, failover.
- Consensus internals (Raft) beyond quorum arithmetic.
- Probabilistic structures (Bloom filters, HyperLogLog), search systems,
  and real-time delivery (WebSockets, long polling).
- More worked designs. Only two exist; interviews and real work draw on
  many (chat, a news feed, payments, notifications, a job scheduler).
- Speaking a design aloud under time pressure, which is its own skill.

## Readiness verdict

A solid base: you can estimate, name the standard building blocks, and
say what each one costs. You'll also recognise the classic failures from
their symptoms, which is where most real design knowledge comes from.
It is not yet interview-complete or architect-level: the missing topics
above are where senior design discussions spend their time.

---

# Part 17 — Databases

**Content:** 12 tutorials, 6 incidents.

This is the operator's side of databases: what a DevOps or SRE engineer
needs when there is no database administrator, which is most teams.
PostgreSQL is the main example, with one tutorial each for MySQL and
Redis. Design-level topics (indexes as a choice, read replicas,
sharding, pooling) are in System Design (Part 16), and schema migrations
in a pipeline are in CI/CD (Part 6); this part doesn't repeat them.

## Covered

Every section of `commands/databases.md`:
- **psql:** connecting, the backslash commands, expanded output, and
  running statements from scripts.
- **SQL for incidents:** filtering and sorting, GROUP BY and HAVING,
  bucketing by time with `date_trunc`, joins, and a window function.
- **Transactions:** BEGIN and checking the row count before COMMIT,
  isolation levels, lost updates and `FOR UPDATE`, and `lock_timeout`.
- **Roles and privileges:** group roles, the three grants a reader
  needs, default privileges for future tables, per-role settings, and
  reading `pg_hba.conf` rules.
- **Live activity:** `pg_stat_activity`, idle-in-transaction sessions,
  lock chains with `pg_blocking_pids`, cancel vs terminate, and
  reloading configuration.
- **Slow queries:** `pg_stat_statements` by total time,
  `EXPLAIN (ANALYZE, BUFFERS)`, expression indexes built concurrently,
  unused indexes, table sizes, and the slow-query log.
- **Vacuum:** dead rows and bloat, VACUUM vs VACUUM FULL vs pg_repack,
  per-table autovacuum settings, and transaction id wraparound.
- **Logical backups:** `pg_dump` formats, globals, parallel restore, a
  restore test with a data check, and restoring one table.
- **Point-in-time recovery:** WAL archiving health, pgBackRest backups,
  a restore to a target time, and RPO vs RTO.
- **Replication and failover:** Patroni, sync vs async replicas,
  replication slots, a planned switchover, and split brain.
- **MySQL:** the process list, metadata locks, deadlocks in the InnoDB
  status, EXPLAIN, replica status, and a consistent `mysqldump`.
- **Redis:** memory and eviction policy, big keys, SCAN instead of
  KEYS, the slow log, and persistence.

Incidents:
- a disk filling with WAL because of a forgotten replication slot;
- a millisecond migration that froze the site behind one idle
  transaction (the lock queue);
- a DELETE without a WHERE, recovered by point-in-time restore to a
  side host and copying one table back;
- a query 4,000 times slower after a bulk load (stale statistics);
- vacuum that runs constantly and removes nothing (an orphaned prepared
  transaction);
- Redis refusing every write at its memory limit (keys without a TTL
  under `volatile-lru`).

Career path 13 chains these with the System Design, CI/CD, and AWS
database content.

## Still missing

- **A real database.** Outputs are pre-written. Typing a query against
  canned output isn't the same as exploring real data, and SQL steps
  must match the expected statement closely. A database sandbox (the
  game could drive an in-memory SQLite database, which needs no
  install) is the most valuable follow-up.
- **SQL depth:** subqueries and CTEs, set operations, NULL semantics,
  upserts, schema design and normalization, constraints, JSON columns.
- **PostgreSQL depth:** partitioning, logical replication, major-version
  upgrades (`pg_upgrade`), configuration tuning (`shared_buffers`,
  `work_mem`, checkpoints), PgBouncer administration, extensions, and
  streaming replication set up by hand.
- **MySQL depth:** binary logs and point-in-time recovery, GTID
  replication, online schema-change tools, InnoDB tuning.
- **Redis depth:** Sentinel and Cluster operations, replication
  failover, and memory analysis beyond big keys.
- **Other stores:** MongoDB, Elasticsearch/OpenSearch cluster
  operations, Cassandra, DynamoDB, ClickHouse, and time-series
  databases.
- **Managed services beyond RDS basics:** Aurora, Cloud SQL, Azure
  Database, parameter groups, and blue/green upgrades.
- Kubernetes database operators (CloudNativePG, Zalando, Percona).

## Readiness verdict

Enough to be the person on the team who isn't afraid of the database.
You can read what it's doing, tell waiting from working, find the
expensive queries, keep vacuum healthy, and run a point-in-time
recovery, which is the skill that matters most on the worst day. It
doesn't make you a database administrator or a SQL developer. Install
PostgreSQL locally, load a sample dataset, and repeat the backup and
restore tutorials for real: a restore you've only read about doesn't
count.

---

# Part 18 — Web Servers and Proxies

**Content:** 11 tutorials, 6 incidents, 2 Writing Labs (nginx
configuration).

Almost every request to a production system passes through a reverse
proxy, and "the site is down" is a fault there more often than people
expect. nginx is the main example, HAProxy the second, with one tutorial
for recognising Envoy, Caddy, Traefik, and Apache. Load-balancing
algorithms as a design choice are in System Design (Part 16); TLS and
HTTP themselves (openssl, curl) are in Networking (Part 5).

## Covered

Every section of `commands/webservers.md`:
- **Running nginx:** `nginx -t` before every reload, `nginx -T` for the
  effective configuration, reload vs restart, and the master and worker
  processes.
- **Server blocks and locations:** testing a virtual host with a Host
  header, the default server, the location matching order, `try_files`,
  and `root` vs `alias`.
- **Reverse proxying:** upstreams, the four standard forwarded headers,
  the `proxy_pass` trailing slash, passive health checks, keepalive, and
  timeouts.
- **TLS:** certbot certificates, renewal rehearsals with `--dry-run`,
  the served certificate vs the one on disk, and HTTP-to-HTTPS
  redirects.
- **Access logs:** status counts, failing paths, busiest clients, and
  slowest requests with awk, sort, and uniq.
- **Gateway errors:** reading the error log to tell 502, 503, 504, and
  499 apart, and bypassing the proxy to split the problem.
- **Limits:** `limit_req` and `limit_conn`, 429 vs 503, body size and
  413, and allow/deny order.
- **Caching and compression:** `X-Cache-Status`, serving stale on
  errors, cache locking, what must never be cached, and `gzip_types`.
- **Capacity:** worker connections, `stub_status`, and file-descriptor
  limits read from `/proc/<pid>/limits`.
- **HAProxy:** config checks, the runtime socket, draining a server, and
  seamless reloads.
- **Other proxies:** Envoy's admin interface, Caddy, Traefik's router
  API, and Apache's virtual-host listing.

Incidents:
- 502 on every page after a deploy changed the app's port;
- an expired certificate that certbot had renewed a month earlier
  (nginx was never reloaded);
- exports failing at exactly 60 seconds while abandoned requests used up
  the app's workers;
- a new site showing the admin login (a file never enabled, and no
  explicit default server);
- dropped connections at 20% CPU (file-descriptor limit set by systemd);
- a per-client rate limit blocking everyone (the load balancer's address
  counted as the client).

Writing Labs yaml-033 (a reverse proxy with HTTPS from scratch) and
yaml-034 (harden a config: TLS versions, rate limit, admin allow-list,
directory listing) use a new `nginx` lab format. Career path 14 walks
the chain from curl and openssl through the proxy to these incidents.

## Still missing

- **A real nginx.** The lab checker confirms structure (balanced braces,
  semicolons, the right directives in the right blocks). It doesn't know
  which directives exist, so a misspelled one passes. Run `nginx -t` on
  real files; a container makes that a one-line command.
- nginx depth: `map` and variables, rewrites, the `stream` module for
  TCP and UDP, WebSocket and gRPC proxying, HTTP/3, njs and Lua
  (OpenResty), and nginx as a Kubernetes ingress controller's engine.
- HAProxy depth: ACLs and routing rules, stick tables, TCP mode for
  databases, and the Data Plane API.
- Writing Envoy, Traefik, or Caddy configuration: only inspection is
  covered.
- Cloud load balancers as a product (target groups, listener rules,
  connection draining settings), beyond the health checks in the cloud
  parts.
- Web application firewalls (ModSecurity, cloud WAF rules), bot
  management, and DDoS protection services.
- DNS-01 challenges and wildcard certificates, OCSP stapling, and mTLS
  between the proxy and the application.

## Readiness verdict

Enough to run and debug the proxy in front of a typical service: you can
test and reload safely, read its logs, tell which layer a gateway error
points at, keep certificates renewing, and avoid the classic
misconfigurations. That covers most of what on-call asks of this layer.
It isn't a specialist's knowledge of any one proxy. Put nginx in front
of a small app yourself, with a real certificate, and break each thing
on purpose.

---

# Part 19 — Identity and Secrets

**Content:** 9 tutorials, 5 incidents, 2 Writing Labs (a Vault policy;
a cert-manager issuer and certificate).

Two questions: who is this caller, and where do credentials live? Cloud
IAM stays in the cloud parts, Kubernetes RBAC in Part 1, and finding
leaked secrets in Security (Part 12).

## Covered

Every section of `commands/identity.md`:
- **JWTs:** decoding claims and headers, expiry, audience, signing
  algorithms, and the issuer's published keys (JWKS).
- **OAuth 2.0 and OIDC:** discovery, the client credentials grant,
  bearer tokens, 401 vs 403, authorization code with PKCE, and userinfo.
- **Workload identity:** `kubectl auth whoami`, projected service
  account tokens, the cluster as an OIDC issuer, and short-lived tokens
  instead of stored cloud keys.
- **Vault:** seal status, OIDC login, the key-value engine and its
  versions, capabilities, and policies.
- **Dynamic secrets:** database credentials created on request, leases,
  and revoking by lease or by prefix.
- **Secrets into Kubernetes:** External Secrets Operator stores and
  sync errors, what a Secret does and doesn't protect, and restarts.
- **Secrets in Git:** SOPS (encrypt, decrypt, update recipients) and
  Sealed Secrets, with what each needs backed up.
- **PKI and mTLS:** keys, signing requests, signing with a private CA,
  verifying a chain, client certificates with curl, and SANs.
- **cert-manager:** issuers, the Certificate to Challenge chain,
  `cmctl status`, and forced renewal.

Incidents:
- 401s everywhere after the identity provider rotated its signing key
  (a verifier that cached the key list for ever);
- Vault sealed on every node after fleet patching;
- a rotated password that the application never picked up;
- a CA rotation that broke mTLS for clients with the old trust bundle;
- Let's Encrypt rate-limiting a pipeline that deleted its certificate
  on every deploy.

## Still missing

- **A real identity provider or Vault.** Outputs are pre-written. Run
  Vault in dev mode (`vault server -dev`) and Keycloak or Dex locally to
  practise for real; both start in one command.
- SAML, SCIM provisioning, and configuring SSO in a provider's console
  (Okta, Entra ID, Google Workspace).
- Running Vault: Raft snapshots and restore, upgrades, namespaces,
  performance replication, and the PKI, transit, and SSH engines.
- Vault Agent and the Secrets Store CSI driver in practice (mentioned).
- SPIFFE/SPIRE, and mesh mTLS policy (the SRE part touches Istio).
- Authorization models and policy engines: RBAC vs ABAC, OPA/Rego,
  OpenFGA.
- Privileged access management, just-in-time access, and break-glass
  procedures.
- Cloud secret managers' own rotation features (AWS Secrets Manager
  rotation Lambdas, Key Vault rotation policies).

## Readiness verdict

Enough to debug the authentication failures that reach on-call: read a
token and say why it was rejected, follow a secret from its source to
the process that uses it, and find where a certificate chain or a
rotation broke. You'll also know the modern defaults: short-lived
credentials, workload identity over stored keys, and rotation with two
valid credentials. Designing an organisation's identity architecture is
a specialism beyond this.

---

# Part 20 — Scripting

**Content:** 8 tutorials, 4 incidents, 2 Writing Labs (Python).

Bash is in Linux (Part 3) and its labs. This part is the next layer:
Python as the automation language, the data tools pipelines lean on,
Makefiles, and enough Go to build and test the tools you run.

## Covered

Every section of `commands/scripting.md`:
- **Python environments:** venv, `python -m pip`, pinned requirements,
  freezing, and outdated packages.
- **Running and debugging:** `--help`, reading a traceback, exit codes,
  `pdb` post-mortem, and log levels from the environment.
- **Tests and linters:** pytest selection and coverage, ruff, and mypy.
- **jq:** length, select, group_by, tab-separated output, `-e`, and
  `--arg`.
- **yq:** reading paths, in-place edits that keep comments,
  multi-document files, and conversion to JSON.
- **Regular expressions:** alternation, extraction with `grep -o`,
  capture groups in sed, negated classes, and greedy matching.
- **Makefiles:** dry runs, the tab rule, `.PHONY`, variable overrides,
  and one definition shared with CI.
- **Go:** `go test`, `go vet`, `go mod tidy`, building, and
  cross-compiling.

Incidents:
- a nightly job broken by an unpinned indirect dependency;
- a script that works by hand and has never worked from cron (PATH);
- a deploy of an image tagged `null` after an API changed shape;
- a script killed by the kernel for reading a whole file into memory.

Writing Labs yaml-040 (a CLI with argparse, streaming, and exit codes)
and yaml-041 (fix command injection, a missing timeout, a bare except,
and a false success) use a new `python` lab format, which parses the
file with the standard library's `ast` module and never runs it.

## Still missing

- **Running the code.** The Python checker confirms structure (imports,
  functions, calls, a main guard) and required or forbidden text. It
  can't tell whether the logic is right. Run your scripts and write
  tests for them.
- Cloud SDKs in practice: boto3 pagination and waiters, the Azure and
  Google client libraries, and stubbing them in tests.
- HTTP APIs from code: sessions, retries with backoff, pagination, and
  rate limits.
- Concurrency (threads, asyncio) for fan-out tasks.
- Packaging a tool: pyproject.toml, entry points, and publishing.
- Writing Go, beyond building and testing it.
- PowerShell (listed under the Backlog's tier C with Windows).
- Makefile and Taskfile authoring as a lab.

## Readiness verdict

Enough to maintain the automation a team accumulates: run it in a
reproducible environment, debug it from a traceback and an exit code,
query and edit JSON and YAML safely, and recognise the failures that
come from environments and unchecked values instead of from logic. To
write good automation, write some: pick a manual task you do weekly and
script it, with tests.

---

# Part 21 — Messaging

**Content:** 7 tutorials, 4 incidents.

System Design (Part 16) explains why a queue sits between two services.
This part is about operating one: Kafka first, then RabbitMQ and the
cloud queues.

## Covered

Every section of `commands/messaging.md`:
- **Kafka anatomy:** topics, partitions, leaders, in-sync replicas, the
  replication factor / `min.insync.replicas` / `acks` trio, and what
  adding partitions does to key ordering.
- **Reading a topic by hand:** the console consumer and producer, and
  kcat for the last messages, their coordinates, or one exact offset.
- **Consumer groups:** lag per partition, group state, the partition
  count as the limit on parallelism, offset resets, and idempotency.
- **Retention:** time and size limits, per-topic overrides, disk use,
  log compaction, and what an offline consumer loses.
- **Brokers:** the KRaft quorum, under-replicated partitions as the gate
  for a rolling restart, preferred leaders, and reassignment.
- **RabbitMQ:** watermarks and alarms, queue depth with consumer counts,
  bounding queues with policies, and acknowledgements.
- **Cloud queues:** SQS attributes, the visibility timeout, dead-letter
  queues, and redrive.

Incidents:
- writes refused during a one-broker restart (replication factor 2 with
  a minimum of 2 in sync);
- a consumer group that never stops rebalancing after processing got
  slower;
- a poison message freezing one partition;
- RabbitMQ blocking every publisher because one abandoned queue filled
  its memory.

## Still missing

- **A real broker.** Outputs are pre-written; a single-node Kafka or
  RabbitMQ in a container is the practice ground.
- Kafka security (TLS, SASL, ACLs), quotas, and multi-tenancy.
- Schema registry and compatibility rules, Kafka Connect, Kafka Streams
  and ksqlDB, MirrorMaker and cross-cluster replication.
- Strimzi and other Kubernetes operators for Kafka; managed services
  (MSK, Confluent Cloud, Event Hubs).
- RabbitMQ clustering, quorum queues in depth, exchanges and routing
  topologies, and streams.
- NATS, Pulsar, and Redis Streams.
- Google Pub/Sub and Azure Service Bus hands-on (named, not practised).
- Exactly-once semantics and transactions, beyond idempotent consumers.

## Readiness verdict

Enough to answer the on-call questions for an event-driven system: is
the message in the topic, who's behind and on which partition, is the
group working or reshuffling, and what a broker restart will do to each
topic. The incidents cover the failures that produce the strangest
symptoms. Running a large Kafka estate (capacity, security, upgrades,
tenancy) is a job in itself.

---

# Part 22 — Serverless

**Content:** 7 tutorials, 4 incidents.

Compute you don't patch or scale yourself: functions (AWS Lambda is the
main example) and managed containers (ECS on Fargate, Cloud Run). The
limits you hit are different from a server's: concurrency, timeouts,
cold starts, and how each event source retries.

## Covered

Every section of `commands/serverless.md`:
- **Lambda basics:** configuration, invoking with a payload, the
  `FunctionError` trap, the REPORT log line, memory and timeout.
- **Scaling:** the shared account concurrency pool, cold starts and
  init time, provisioned and reserved concurrency, and how throttling
  looks to each kind of caller.
- **Releases:** versions, aliases, a weighted canary, instant rollback,
  and images by digest.
- **Events:** event source mappings, whole-batch retries and partial
  batch responses, silent loss of failed asynchronous events, failure
  destinations, and S3 trigger filters.
- **API Gateway:** routes, the 30-second integration limit, the
  asynchronous job pattern, and stage throttling.
- **ECS on Fargate:** service events, stopped-task reasons, ECS Exec,
  and forcing a deployment.
- **Other clouds:** Cloud Run revisions, traffic splits, and logs; an
  Azure function app's state and plans.

Incidents:
- checkout throttled because a bulk job used the account's whole
  concurrency pool;
- a function attached to a VPC that lost its route to the internet;
- a function triggering itself through its own S3 output, 40 million
  times;
- an ECS deployment looping because slow-starting tasks were killed by
  health checks.

## Still missing

- **A real account.** Everything is pre-written output. The free tiers
  of Lambda and Cloud Run cover real practice.
- Writing function code and its tests, layers, and packaging.
- Infrastructure code for serverless: SAM, the Serverless Framework,
  CDK, and Terraform modules.
- Step Functions and other workflow engines; EventBridge rules and
  schemas.
- DynamoDB as the usual serverless datastore (capacity modes, hot
  partitions, single-table design).
- Observability specific to functions: X-Ray, structured logs,
  Lambda Insights, and cost per invocation.
- Cloud Functions and Azure Functions in depth; Azure Container Apps;
  App Service.
- Knative and OpenFaaS on Kubernetes.

## Readiness verdict

Enough to operate serverless workloads someone else built: read a
function's logs and limits, recognise throttling, cold starts, and
timeouts for what they are, release and roll back safely, and spot the
event-driven failure modes that produce silence instead of errors.
Designing a serverless system well, especially its data model and its
cost profile, takes building one.

---

# Part 23 — Performance

**Content:** 7 tutorials, 3 incidents.

Linux (Part 3) covers the first look at a slow host. This part is about
finding which code, or which wait, the time goes to.

## Covered

Every section of `commands/performance.md`:
- **perf:** live and recorded CPU sampling, self vs children time,
  `perf stat`, and what a CPU profile can't show.
- **Flame graphs:** generating one, what width and order mean, where to
  look, and differential graphs.
- **Python:** py-spy top, record, and dump on a live process, the GIL,
  sampling vs instrumenting, and import-time cost.
- **The JVM:** jcmd, heap use, `jstat -gcutil`, class histograms, and
  thread dumps showing lock contention.
- **eBPF tools:** execsnoop, opensnoop, biolatency, runqlat, and a
  bpftrace one-liner.
- **Go:** pprof CPU and heap profiles, goroutine leaks, exposing the
  endpoint safely, and benchmarks.
- **Measuring:** hyperfine and noise, percentiles vs averages,
  coordinated omission, load-test validity, and continuous profiling.

Incidents:
- a Java pod OOMKilled while its heap had room (non-heap memory against
  a container limit);
- a server throttled every afternoon by CPU credits, visible only as
  steal time;
- database stalls caused by a backup job saturating the disk.

## Still missing

- **Real profiles.** Reading a real flame graph of your own service is
  the skill; outputs here are pre-written and the flame-graph steps are
  questions about a described picture.
- Memory profiling in depth: heap dump analysis, tracemalloc and memray,
  native leaks, and fragmentation.
- Off-CPU and wall-clock profiling in practice; lock profiling.
- Network performance: TCP tuning, retransmits, connection reuse, and
  kernel bypass.
- Database query tuning beyond Databases (Part 17).
- Kernel and NUMA tuning, huge pages, CPU pinning, and cgroup v2
  pressure (PSI) metrics.
- Node.js, .NET, and Rust profilers.
- Capacity modelling and queueing theory beyond SRE's capacity planning.

## Readiness verdict

Enough to go from 'it's slow' to a named function or a named wait on the
common runtimes, and to distrust a measurement that hasn't earned trust.
The incidents cover three causes that dashboards routinely hide. Real
skill here comes from profiling real services, repeatedly: profile
something healthy first, so you know what normal looks like.

---

# Part 24 — FinOps

**Content:** 6 tutorials, 3 incidents.

Making cloud cost visible to the engineers who cause it. AWS (Part 9)
has one tutorial on finding waste; this part covers the practice around
it. AWS is the example; the ideas hold on every cloud.

## Covered

Every section of `commands/finops.md`:
- **Reading the bill:** cost by service and by team tag, the untagged
  share, forecasts, unit cost, and unblended vs amortized.
- **Ownership:** finding untagged resources, enforcing tags at creation,
  budgets per team, and anomaly detection.
- **Rightsizing:** Compute Optimizer and its blind spot for memory, old
  snapshots, forgotten instances, and the order to work in.
- **Discounts:** Savings Plans coverage and utilisation, what to commit
  to, spot prices, and what spot suits.
- **Kubernetes:** cost and efficiency per namespace and deployment,
  requests against usage, and why savings need nodes to go away.
- **Quiet costs:** lifecycle rules, abandoned multipart uploads, log
  groups that never expire, and what data transfer charges for.

Incidents:
- GPU instances left running in an unused region, and telling a
  forgotten experiment from a stolen key;
- a logging bill tripled by a debug level left on;
- 74 TB of volumes orphaned by deleting clusters before emptying them.

## Still missing

- **A real bill.** Numbers here are invented and tidy. Real cost data is
  messy: credits, taxes, shared costs, and delayed line items.
- Azure Cost Management and Google Cloud billing exports in practice.
- Cost in infrastructure code review (Infracost) and policies that
  block expensive changes.
- Chargeback models, forecasting methods, and negotiating enterprise
  agreements and private pricing.
- The Cost and Usage Report queried with SQL (Athena, BigQuery).
- SaaS and licence cost, which is often larger than the cloud bill.
- Carbon and sustainability reporting.

## Readiness verdict

Enough to be the engineer who can explain the bill and cut it without
breaking anything: find what's unowned, remove what's unused, size what
remains, and commit to the baseline, in that order. FinOps as a
discipline is mostly organisational, getting teams to own a number, and
that part is learned by doing it with real people and a real budget.

---

# Part 25 — Data Engineering

**Content:** 5 tutorials, 2 incidents, 1 Writing Lab (an Airflow DAG).

Data pipelines are production systems that platform engineers end up
running. MLOps (Part 8) operates Airflow for model training; Databases
and Messaging cover PostgreSQL and Kafka themselves. This part is the
data platform's own tools, at an operator's depth.

## Covered

Every section of `commands/dataeng.md`:
- **Airflow authoring:** import checks, the task tree, `dags test`,
  catchup, the logical date, and idempotent tasks.
- **dbt:** targets and schemas, selecting models and their dependants,
  the four built-in tests, building only what changed, and source
  freshness.
- **Warehouses:** dry runs, partitions and clustering, requiring a
  partition filter, and idle Snowflake warehouses.
- **Spark on Kubernetes:** drivers and executors, reading a failing
  job's log, data skew, and the Spark UI.
- **Change data capture:** Kafka Connect's REST API, failed tasks behind
  a 'running' connector, replication slots, and schema changes.

Incidents:
- revenue doubled by re-running an appending pipeline;
- a dashboard scanning 4 TB an hour.

Writing Lab yaml-049 has you write an Airflow DAG.

## Still missing

- **Real data.** Everything here is pre-written output.
- Writing dbt models, macros, and incremental models; data modelling
  (star schemas, slowly changing dimensions).
- Spark tuning beyond skew: shuffle, partitions, caching, and Structured
  Streaming. Flink.
- Lakehouse formats (Iceberg, Delta, Hudi) and query engines (Trino,
  Athena).
- Data quality frameworks (Great Expectations, Soda), lineage
  (OpenLineage), and catalogs.
- Other orchestrators: Dagster, Prefect, Argo Workflows.
- Data governance: PII handling, retention, and access control on data.

## Readiness verdict

Enough to keep a data platform's machinery healthy and to recognise the
failures that produce wrong numbers instead of errors, which is what
makes data work different from service work. It isn't a data engineer's
training: modelling data and writing transformations are the craft, and
they're learned by building pipelines on real data.

---

# Part 26 — The backlog: everything that isn't in the game yet

The parts above each list what's missing *inside* a category. This part
lists whole topics with no category at all, in three tiers. Nobody needs
all of it. Tier A is worth learning for almost any DevOps, platform, or
SRE role; tier B depends on the job; tier C is for when a specific
employer uses it.

## Tier A: commonly used, expected in most roles

1. ~~**Databases as an operator**~~: **now a category** (Part 17):
   PostgreSQL operations, on-call SQL, roles, vacuum, backup and
   point-in-time recovery, Patroni failover, MySQL, and Redis. What
   remains is listed under Part 17's "Still missing": a real database
   to query, SQL and tuning depth, MongoDB, and
   Elasticsearch/OpenSearch.
2. ~~**Messaging systems**~~: **now a category** (Messaging): Kafka
   operations, RabbitMQ, and SQS. Security, schema registry, Connect,
   and the other brokers are under that part's "Still missing".
3. ~~**Web servers and proxies**~~: **now a category** (Part 18): nginx
   operations, TLS with certbot, log analysis, gateway errors, limits,
   caching, capacity, and HAProxy. Depth topics (rewrites, the stream
   module, HAProxy ACLs, WAFs) are under Part 18's "Still missing".
4. ~~**A scripting language**~~: **now a category** (Scripting): Python
   environments, debugging, tests and linters, `jq`, `yq`, regular
   expressions, Makefiles, and building Go tools, with two Python
   Writing Labs. Cloud SDK use (boto3) and writing Go are under that
   part's "Still missing".
5. ~~**Identity and secrets**~~: **now a category** (Identity and
   Secrets): JWTs, OAuth 2.0 and OIDC, workload identity, Vault,
   External Secrets, SOPS and Sealed Secrets, mTLS, and cert-manager.
   SAML, SPIFFE, and operating Vault itself are under that part's
   "Still missing".
6. ~~**Other CI systems and release tooling**~~: **done** inside CI/CD
   (cicd-tutorial-016 to 020, two incidents, one lab): GitLab CI,
   Jenkins, artifact registries, release automation, and Renovate.
   Still open: Azure DevOps Pipelines, CircleCI, Tekton, and writing a
   Jenkinsfile.
7. ~~**The Kubernetes ecosystem**~~: **done** inside the Kubernetes
   category (tutorial-030 to 035, two incidents, two labs): Kustomize,
   Helm chart authoring, Gateway API, VPA/KEDA/Karpenter, Flux, and
   Linkerd; cert-manager is in Identity and Secrets. Still open:
   external-dns, and CKAD and CKS exam passes.
8. ~~**Serverless and managed compute**~~: **now a category**
   (Serverless): Lambda, API Gateway, ECS on Fargate, Cloud Run, and
   Azure Functions. Step Functions, DynamoDB, and serverless
   infrastructure code are under that part's "Still missing".
9. ~~**Logging pipelines**~~: **done** inside Monitoring
   (monitoring-tutorial-014 to 016, two incidents). Logstash and
   OpenSearch operations are still open.
10. ~~**Performance engineering**~~: **now a category** (Performance):
    perf, flame graphs, py-spy, the JVM, eBPF tools, Go pprof, and
    measurement. Memory profiling and network tuning are under that
    part's "Still missing".
11. ~~**FinOps**~~: **now a category** (FinOps): allocation, budgets and
    anomalies, rightsizing, commitments and spot, Kubernetes cost, and
    storage, log, and transfer costs. Azure and Google Cloud billing
    and cost in code review are under that part's "Still missing".
12. ~~**Hosted observability**~~: **mostly done** inside Monitoring
    (monitoring-tutorial-017 for Datadog and Sentry; Writing Lab
    yaml-042 for Grafana dashboards). New Relic and CloudWatch in depth
    are still open.

## Tier B: valuable, depends on the role

- ~~**Other infrastructure-as-code tools**~~: **done** inside Terraform
  (terraform-tutorial-013 to 016, one incident), at the level of
  operating and recognising them. Authoring in each tool is still open.
- ~~**Advanced networking**~~: **done** in networking-tutorial-013 to
  017, networking-incident-008, and aws-tutorial-014. Still open:
  IPsec, DNSSEC, Calico, and BGP design.
- ~~**Storage and disaster recovery**~~: **done** in servers-tutorial-012
  (NFS), servers-tutorial-013 (Ceph health), tutorial-036 (Velero and
  CSI snapshots), sre-tutorial-011 (a DR drill against RPO and RTO),
  with servers-incident-007 and incident-018. Operating Rook, and
  object storage design, are still open.
- ~~**Multi-cluster and multi-tenancy**~~: **done** in tutorial-037 and
  tutorial-038. Karmada and cluster mesh aren't covered.
- ~~**Platform engineering**~~: **done** in sre-tutorial-012 (the service
  catalog, ownership, golden paths, measuring a platform),
  sre-tutorial-013 (the four DORA metrics from real data), and Writing
  Lab yaml-045 (a catalog-info.yaml). Building Backstage plugins and
  software templates isn't covered.
- ~~**Compliance and governance**~~: **done** in security-tutorial-012
  to 016, security-incident-007, and Writing Labs yaml-046 to 048.
- ~~**Data engineering**~~: **now a category** (Data Engineering), with
  five tutorials, two incidents, and an Airflow DAG lab.
- ~~**LLM operations**~~: **done** in mlops-tutorial-015 to 018 and
  mlops-incident-008.
- **System design depth:** the list under Part 16.
- ~~**Testing in delivery**~~: **done** in cicd-tutorial-020.
- ~~**Authoring gaps named in earlier parts**~~: **all done** as Writing
  Labs: a Grafana dashboard, burn-rate alerts, and manual spans
  (yaml-042 to 044), a Kyverno policy and a Falco rule (yaml-047, 048),
  and an Airflow DAG (yaml-049).

## Tier C: less popular, legacy, or niche

- **Other orchestrators:** Nomad, Docker Swarm, Consul for service
  discovery.
- **Other configuration management:** Puppet, Chef, SaltStack.
- **Other container tooling:** Podman, Buildah, Skopeo, containerd with
  nerdctl and crictl, Kaniko, ko, Buildpacks; sandboxed runtimes
  (gVisor, Kata, Firecracker); WebAssembly workloads.
- **Kubernetes distributions:** OpenShift (`oc`, Routes, SCCs), Rancher
  and RKE2, k3s, Talos; bare-metal load balancing (MetalLB, kube-vip).
- **Build systems:** Bazel, Nix and NixOS, Pants, Earthly, Dagger.
- **Other version control:** Gerrit, Perforce, Mercurial, monorepo
  tooling.
- **Windows administration:** PowerShell, Active Directory, Group
  Policy, IIS, WinRM, Windows containers.
- **Other clouds and on-premises:** Oracle Cloud, IBM Cloud,
  DigitalOcean, Hetzner, OpenStack, VMware vSphere, Proxmox; bare-metal
  provisioning (PXE, MAAS, Tinkerbell, IPMI and Redfish).
- **Older monitoring:** Nagios, Zabbix, Icinga, Graphite and StatsD,
  SNMP.
- **High-performance computing:** Slurm, MPI, parallel filesystems.
- **Edge:** k3s at the edge, KubeEdge.
- **Mail and DNS hygiene:** SPF, DKIM, DMARC, DNSSEC.
- **Mobile delivery:** Fastlane, app signing, store releases.
- **More chaos tooling:** Litmus, Gremlin, and designing game days.

## Suggested build order

If content is added in the order that helps most people soonest:
1. ~~a Databases category~~ (done, Part 17);
2. ~~web servers and proxies~~ (done, Part 18);
3. ~~identity and secrets~~ (done);
4. ~~Kubernetes ecosystem~~ (done);
5. ~~Jenkins and GitLab CI~~ (done);
6. ~~Python for automation, as Writing Labs~~ (done);
7. ~~Kafka operations~~ (done);
8. ~~serverless~~ (done);
9. then tier B by demand.

---

# Part 27 — Overall: will this make you proficient in DevOps?

## By the numbers

| Category | Tutorials | Incidents | Extra |
|---|---|---|---|
| Kubernetes | 38 | 18 | 11 Writing Labs, 2 Sandboxes (explore, and fixable), 5 Mysteries |
| Docker | 11 | 5 | 3 Writing Labs (Dockerfile, Compose), Sandbox, 2 Mysteries |
| Linux | 15 | 6 | 4 Writing Labs (bash), interactive Sandbox, 4 Mysteries |
| Terraform | 16 | 7 | 5 Writing Labs (HCL, including a module) |
| Networking | 17 | 8 | |
| CI/CD | 20 | 8 | 4 Writing Labs (Actions, GitLab CI) |
| Monitoring | 17 | 8 | 5 Writing Labs (alert rules, SLO burn alerts, a dashboard, manual spans) |
| MLOps | 18 | 8 | |
| AWS | 14 | 7 | 1 Writing Lab (IAM policy), Sandbox (VPC), 4 Mysteries |
| Azure | 10 | 6 | Sandbox, 3 Mysteries |
| Google Cloud | 10 | 6 | 1 Writing Lab (firewall), Sandbox, 3 Mysteries |
| Security | 16 | 7 | 3 Writing Labs (Sigma, Kyverno, Falco), 2 hacked-server Mysteries (Linux sandbox) |
| Server Fleet Ops | 13 | 7 | 1 Writing Lab (Ansible) |
| SRE | 13 | 6 | 2 Writing Labs (postmortem, catalog entry) |
| Git | 11 | 6 | |
| System Design | 11 | 6 | 2 Writing Labs (design documents) |
| Databases | 12 | 6 | |
| Web Servers & Proxies | 11 | 6 | 2 Writing Labs (nginx configuration) |
| Identity & Secrets | 9 | 5 | 2 Writing Labs (Vault policy, cert-manager) |
| Scripting | 8 | 4 | 2 Writing Labs (Python) |
| Messaging | 7 | 4 | |
| Serverless | 7 | 4 | |
| Performance | 7 | 3 | |
| FinOps | 6 | 3 | |
| Data Engineering | 5 | 2 | 1 Writing Lab (Airflow DAG) |
| **Total** | **322** | **156** | 49 Writing Labs, 14 career paths, 7 sandboxes, 23 Mystery Incidents, Exam Mode, Stats |

Every command section of every `commands/*.md` reference is now covered
by at least one tutorial, and every tutorial step explains *why* that
command beats the alternatives — not just what it does.

## Honest verdict

**Completing everything here will make you a strong DevOps operator: you
will know the commands, the failure modes, and — most importantly — the
debugging method** (check the layer before guessing the fix; refused vs
timeout; verify after every change; revoke before cleaning up; revert
don't force-push). The 156 incidents are modeled on the kinds of problems
that genuinely trip up working engineers, and working through them
builds judgment that command references alone never will.

**It will not, on its own, make you fully proficient**, for four reasons
that no amount of additional scenario content can fully close:

1. **Authoring vs. operating.** Largely addressed: 49 Writing Labs now
   have you write real Kubernetes manifests, GitHub Actions workflows,
   Prometheus alert rules, Compose files, Dockerfiles, Terraform (AWS
   VPCs and security groups, GCP firewalls), IAM policies, Ansible
   playbooks, bash scripts, a Terraform module, a blameless postmortem,
   two system design documents, and nginx configuration, in your own editor. What remains is **depth and
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
   or init counts as collateral damage). You have to fix it for real and
   then name the root cause; where there's nothing to fix, you must have
   seen the evidence, so you can't win by guessing. The outputs are still
   simulated, though: 23 mysteries (Kubernetes, Linux, Docker, AWS, Azure,
   Google Cloud, and hacked servers) are a start, not real on-call. Pair this game with a homelab
   (kind/minikube, a free-tier cloud account) where things break for real.
3. **Cloud-provider fundamentals** (IAM, VPCs, managed services).
   **Partly addressed.** The AWS category (Part 9) and its VPC sandbox
   teach networking layers, IAM, and incident response. Azure (Part 10)
   and Google Cloud (Part 11) cover the same ground on each platform,
   with a cross-cloud map. Serverless, multi-account networking, and
   managed databases beyond the RDS basics still need a real account.
4. **The human side of operations.** Incident command, communication
   during an outage, blameless postmortems, and knowing when to escalate.
   **Partly addressed** by the SRE category (Part 14), which covers
   incident roles, mitigate-first, timelines, and postmortem structure.
   Doing it with real people under pressure still needs game days and
   on-call shadowing.

## Recommended path to real proficiency

1. Play every tutorial in each category in order (the `why` notes are
   the point, not the syntax).
2. Play every incident without hints first; read every resolution even
   when you solved it.
3. Take an Exam for each category until you pass (66%) consistently —
   then retake it a week later. Spaced recall is what makes commands
   stick; a single pass right after the tutorials proves little. The
   Stats screen shows which categories you've passed, your best score
   in each, and what to do next.
4. Complete the Writing Labs for each category.
5. Play all 14 Career Paths to practice switching layers mid-problem —
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
10. Then widen. The Backlog part lists everything this game doesn't teach yet,
    in three tiers. Start with tier A (identity and secrets, a
    scripting language, messaging): those come up in almost every
    role.
