# kube-sim

**Learn DevOps by typing real commands, not by memorising them.**

A terminal game with guided tutorials, production incidents, real
file-writing labs, timed exams, and broken systems to investigate and fix.
It started as Kubernetes-only and now covers 26 areas of DevOps work.

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![Runs offline](https://img.shields.io/badge/runs-offline-green)
![Tests: pytest](https://img.shields.io/badge/tests-pytest-orange)

```bash
pip install -r requirements.txt   # just PyYAML
python game.py
```

> **Runs entirely locally.** There's no real infrastructure, no network
> calls, and no backend. Command output is pre-written and simulated. The
> two exceptions are local and contained: the database sandbox runs real
> SQL in memory, and the Git sandbox runs your installed `git` on a
> throwaway repository.

---

## Contents

- [What it covers](#what-it-covers)
- [Modes](#modes)
- [How playing works](#how-playing-works)
- [Sandboxes](#sandboxes)
- [What's in it](#whats-in-it)
- [Will this make me proficient in DevOps?](#will-this-make-me-proficient-in-devops)
- [Running it](#running-it)
- [Adding a new scenario](#adding-a-new-scenario)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Status / roadmap](#status--roadmap)

---

## What it covers

| Layer | Categories |
|---|---|
| **The core every role needs** | Linux · Networking · Git · Scripting · Docker · Kubernetes · Terraform · CI/CD · Monitoring |
| **Where it runs** | AWS · Azure · Google Cloud · Serverless · Databases · Web Servers & Proxies · Messaging |
| **Running it well** | Security · Identity & Secrets · SRE (how large companies run production) · Server Fleet Ops · Performance · FinOps · System Design |
| **Specialisms and recognition** | MLOps · Data Engineering · The Wider Landscape (less common tools) |

---

## Modes

| Mode | What you do | What it trains |
|---|---|---|
| 📘 **Practice: Learn** | Short guided tutorials, one concept at a time | Real syntax, and *why* one way beats another |
| 🚨 **Practice: Incidents** | Investigate a simulated production problem step by step | Finding the root cause instead of guessing |
| 🧭 **Career Paths** | Play scenarios from several categories as one job | Switching layers the way real work does |
| ✍️ **Writing Labs** | Write or fix a real file in your own editor | Authoring, which command matching can't fake |
| ⏱️ **Exam Mode** | Timed questions, no hints, scored at the end | Whether it actually stuck |
| 🔍 **Mystery Incidents** | A symptom and a live sandbox; no steps at all | Real on-call conditions |
| 🧪 **Sandbox** | Explore a randomly broken environment freely | Looking around without a script |
| 📊 **Stats** | See progress, exam bests, and next steps | Knowing what to do next |

> 💡 At every prompt (menus, tutorial steps, labs, sandboxes) you can type
> `exit` or `quit` to back out.

### 📘 Practice

Pick a category (or "All categories"), then Learn (tutorials) or
Incidents within it.

- **Learn (tutorials)**: short, guided scenarios that teach one concept
  at a time: create a pod, build a Docker image, run a Terraform apply,
  and so on. Each correct command gets a "Why this way" note: not just
  what it did, but why that command or flag beat other valid ways to do
  the same thing.
- **Incidents**: longer, investigative scenarios simulating real
  production problems (CrashLoopBackOff, a container that exits
  immediately, Terraform state drift, silent ML model drift...). You
  chain the right sequence of diagnostic commands to find the actual
  root cause. Each ends with a debrief explaining what really happened.

### 🧭 Career Paths

Chains existing tutorials and incidents *across* categories into one
continuous playthrough, the way these tools actually get used together
on a job. For example: provision infrastructure with Terraform →
containerize with Docker → deploy to Kubernetes → automate with CI/CD →
observe with Monitoring. Each stage is a normal scenario; the path just
sequences them, with one framing intro and outro around the whole thing.

### ✍️ Writing Labs

Real authoring practice, not command matching. The game writes a real
file to `workspace/`, tells you what to build or fix, and you edit it in
your actual editor (vim, nano, VS Code, whatever you'd really use).
Typing the apply command reads your real file and checks it field by
field.

51 labs across thirteen formats:
- Kubernetes manifests, GitHub Actions workflows, Prometheus alert rules,
  and Docker Compose files;
- Dockerfiles, and Terraform (AWS VPCs, security groups, GCP firewalls,
  a reusable module);
- AWS IAM policies, Ansible playbooks, and bash and Python scripts;
- nginx configuration, a blameless postmortem, and system design
  documents in Markdown.

Half are "write from scratch" and half are "fix this broken or dangerous
file". This is the skill a command-matcher can't fake.

### ⏱️ Exam Mode

Pick a category and a number of questions. They're drawn at random from
that category's tutorials and incidents, one minute each, with **no hints
and no feedback until the end**, like a real exam.

- You're scored against the CKA's real 66% pass mark.
- Every miss is reviewed with the correct command.
- Your best score per category is remembered.

The rest of the game is forgiving on purpose; this is the part that tells
you whether it stuck.

### 🔍 Mystery Incidents

Real on-call conditions. You get only a symptom ("postgres just dies,
nothing in its logs") and a live Linux, Docker, Kubernetes, AWS, Azure,
Google Cloud, Terraform, database, or Git sandbox. There are no steps and no hints,
and any command works in any order.

- **Solving it.** When you think you've fixed it, type `solve`. The game
  checks:
  1. that the system really is fixed;
  2. where there's nothing to fix (the Docker mysteries are diagnosis
     only), that you've actually *seen* the evidence, so you can't win
     by guessing;
  3. that you can name the root cause.
- **Scoring.** You're scored against an experienced engineer's command
  count. Careless fixes cost points: `kill -9` on sshd locks you out, and
  opening SSH to 0.0.0.0/0 on AWS gets flagged.
- **Debrief.** Afterwards you get a debrief, plus one efficient path
  through the problem. Type `giveup` at any time to see the answer.

### 🧪 Sandbox

No scoring and no steps: a randomly generated broken environment to
explore with real commands. There are ten to pick from (see
[Sandboxes](#sandboxes)). Pipes work everywhere (`ps aux | grep python`,
`docker ps -a | grep Exited`). On exit you can keep the state for next
time or throw it away.

### 📊 Stats

One screen showing where you stand:
- for every category: tutorials, incidents, labs, and mysteries done, and
  your best exam score against the 66% pass mark;
- career paths, your mystery average, and the scenarios that took you the
  most attempts;
- up to three concrete next steps.

---

## How playing works

### A tutorial or incident

You'll see a prompt describing a task ("Create a pod named 'my-first-pod'
using the nginx image"). Type the command you think does that.

| You type | What happens |
|---|---|
| ✅ The right command | You see the simulated output, then an explanation and a "Why this way" note (tutorials), or you move straight to the next investigative step (incidents) |
| ❌ A wrong command | A short nudge |
| ❌❌ Two misses | A hint appears |
| ❌❌❌❌ Four misses | The game shows the expected command. It's a learning tool, not a test, so there's no penalty for getting stuck |

> **Matching is forgiving.** It's fuzzy, not exact string comparison:
> `--image=nginx` and `--image nginx` are equivalent, extra whitespace and
> case don't matter, and any command in a step's list of accepted
> phrasings counts. The matcher is completely tool-agnostic: it works the
> same whether the expected command is `kubectl`, `docker`, `terraform`,
> `git`, or a plain Linux command like `grep`.

### A Career Path

The same as a tutorial or incident, just longer. You're dropped into
stage 1 (say, a Terraform tutorial), play it to completion, then move
automatically to stage 2 (say, Docker), and so on.

- Quitting mid-path stops the whole path (re-enter it to start again).
- Completing every stage marks the path itself complete, and also credits
  each stage's own tutorial or incident, so it shows as done when you
  browse that category directly afterwards.

### A Writing Lab

1. The lab writes a real file under `workspace/` in the project directory
   (blank, or with a deliberate bug) and prints its path.
2. Open that path in your own editor, write or fix the file, and save it.
3. Back in the terminal, type the apply command it told you (for example
   `kubectl apply -f pod.yaml`). The game reads the file you actually
   saved and checks it.

| Result | What happens |
|---|---|
| ✅ Passes | Simulated "created" output, an explanation, and a why-this-way note |
| ❌ Fails | A list of specific problems (a missing field, a wrong value, or a syntax error if it doesn't even parse), not just "wrong" |
| ❌❌ Two misses | A hint appears |
| ❌❌❌❌ Four misses | A full working version of the file to compare against or copy in |

This is real file I/O: no simulated typing, no pasting into the game's
own prompt. It's the closest thing here to actual exam conditions.

---

## Sandboxes

Type `help` inside any sandbox for its full command list. Every sandbox
supports pipes: `| grep [-i -v -c]`, `| head -N`, `| tail -N`, `| wc -l`,
`| sort`.

| Sandbox | What's broken | Can you fix it? |
|---|---|---|
| ☸️ **Kubernetes** | Deployments, Services, and pods, some `CrashLoopBackOff`/`OOMKilled`/`Pending`/`Error`, plus nodes, a ConfigMap, a Secret, and an event log, all consistent with each other | Read-only: for practising how to look around |
| ☸️ **Kubernetes, fixable** | Every failing pod has a cause: an image tag that doesn't exist, a missing ConfigMap key, a memory limit that's too low, a readiness probe on the wrong path, drained nodes, or a Service selector that matches nothing | Yes: `kubectl rollout undo`, `set image\|env\|resources\|selector`, `patch`, and `uncordon` really fix it, and deleting a broken pod really doesn't |
| 🐳 **Docker** | One or two app containers OOM-killed, crashed on startup, stuck in a restart loop, or failing their healthcheck, plus dangling images and volumes wasting disk | Read-only diagnosis |
| 🐧 **Linux** | Two hidden problems: a failed service, a full disk, a runaway process, a memory hog, a crypto-miner that keeps coming back, or an SSH backdoor | Yes: `kill`, `systemctl restart`, `rm`, and `truncate` really change the state, so fixes only work if you've understood the cause |
| ☁️ **AWS** | A VPC with two broken network layers, explored with real `aws ec2 describe-*` commands. Traffic is evaluated layer by layer: public IP, route table (IGW or NAT), stateless network ACLs, and security groups. Every failure just times out, as it would for real, so you have to read the configuration | Yes: create-route, security group rules, NACL entries, or Elastic IPs; then test with `curl`/`nc`/`ssh` from your laptop, or from inside an instance through `aws ssm start-session` |
| ☁️ **Azure** | NSG rules evaluated by priority, an NSG that may also sit on the VM's network card, and a route that sends traffic to a firewall that may not be there | Yes; `az network watcher test-ip-flow` names the rule that decided, as the real one does |
| ☁️ **Google Cloud** | Firewall rules that apply only to VMs with the right network tag, SSH through IAP, and Cloud NAT that exists per region | Yes |
| 🗄️ **Database** | Real SQL (SQLite in memory). Two of four data problems: a dropped index, a double-loaded day, orphaned rows, and deleted rows with a backup table that's older than the live data | Yes, with real SQL; `check` shows which reports are fixed |
| 🏗️ **Terraform** | A production working directory whose code, state, and real account are out of step. Two of five problems: drift from a console change, a stale state lock, a rename that would replace a server, a bucket that exists but isn't in state, and a database handed to another team | Yes: `plan` really diffs the three layers; `apply`, `state mv`/`rm`, `import`, and `force-unlock` really fix it, and the wrong move (applying the rename) really destroys the server |
| 🌿 **Git** | A real repository and your real `git`. One of five problems: commits on the wrong branch, a key in unpushed history, a merge stopped on a conflict, commits lost to `reset --hard`, or a pushed commit to undo | Yes, with real git; `check` shows whether it's fixed |

<details>
<summary><b>Command reference for each sandbox</b></summary>

**Docker:** `docker ps [-a]`, `images`, `logs [--tail N]`,
`inspect <c> [--format '{{.State.ExitCode}}']` (also `.State.OOMKilled`,
`.State.Health.Status`, `.RestartCount`, and more), `stats`, `top`,
`exec <c> env`, `volume ls -f dangling=true`, `network ls/inspect`,
`system df`. Containers can be referenced by name or id prefix.

**Linux:** `uptime`, `nproc`, `free -h`, `df -h`, `du -sh <dir>/*`,
`ls -lh`, `ps aux --sort=-%cpu|-%mem`, `top`, `systemctl status|--failed|
restart <svc>`, `journalctl -u <svc> | -p err`, `dmesg -T`, `ss -tulnp`,
`lsof +L1`, and the fixes: `kill [-9] <pid>`, `rm <file>`,
`truncate -s 0 <file>`. Two things are wrong each time; you're done when
both are fixed and `systemctl --failed` and `df -h` look healthy.

**Database:** a real SQL database (SQLite, in memory, from Python's
standard library), not pre-written output. Any SQL works, one statement
per line, with explicit `BEGIN`/`COMMIT`/`ROLLBACK` as in psql, plus
`EXPLAIN QUERY PLAN`, `.tables`, `.schema`, `.indexes`, and psql-style
`\dt`, `\d <table>`, `\di`.

**Git:** needs git installed. Any local git command works; commands that
reach a remote or run other programs (push, fetch, `bisect run`,
`rebase --exec`, aliases) are refused. Edit files in your own editor (the
repository's path is shown), or with `sed -i`; `ls`, `cat`, and `check`
also work. The repositories live in `workspace/git-sandbox/` and are
cleaned up after six hours.

**Terraform:** `terraform init|validate|plan [-refresh-only] [-lock=false]`,
`apply [-auto-approve] [-refresh-only]`, `state list|show|mv|rm|pull`,
`import <addr> <id>`, `force-unlock [-force] <id>`, and `cat main.tf`;
plus read-only views of what really exists: `aws s3 ls`,
`aws ec2 describe-instances`, `aws ec2 describe-security-groups`,
`aws rds describe-db-instances`, `aws cloudtrail lookup-events`, and
`gh run list`. Fully simulated: no real Terraform or cloud account.

**Kubernetes:**

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

Some pods will be broken (CrashLoopBackOff, OOMKilled, Pending, Error);
the point is figuring out which ones and why, the same way you would
against a real cluster. Everything is consistent: a broken pod shows up
in its Deployment's READY count, in `get events`, and in `describe pod`'s
events section.

</details>

---

## What's in it

> Every tutorial step explains not just what the command does but *why*
> it beats the alternatives. Every incident ends with a debrief of the
> real root cause and how to prevent it.

| Category | Tutorials | Incidents | Topics |
|---|---|---|---|
| Kubernetes | 44 | 18 | pods → operators, full CKA coverage incl. etcd, kubeadm, certs, security, RBAC/PDB/storage/admission-webhook/Multi-Attach incidents, and the ecosystem (Kustomize, Helm chart authoring, Gateway API, VPA/KEDA/Karpenter, Flux, Linkerd), Velero backups, Cluster API and ApplicationSets, multi-tenancy, CKAD speed (generated manifests, blue/green and canary, `kubectl debug`, API deprecations), and CKS hardening (audit logs, encryption at rest, AppArmor/seccomp, kubesec, ImagePolicyWebhook); plus 11 Writing Labs and 2 Sandboxes |
| Docker | 11 | 5 | images/layers, volumes, networking, Compose, cleanup, Dockerfiles, runtime limits, container security, BuildKit/buildx multi-platform; plus 3 Writing Labs (2 Dockerfile, Compose) |
| Linux | 15 | 6 | find, text pipelines, processes/signals, systemd, networking, users/permissions, SSH, cron, disks, performance, strace/lsof, packages/firewalls, SELinux; plus 4 bash-script Writing Labs |
| Terraform | 19 | 7 | safe CI workflow, modules/for_each/moved blocks, writing modules (validation, dynamic blocks, terraform test), variables/outputs, state inspection & refactoring, import, workspaces, remote state/locking, providers, debugging, OpenTofu/Terragrunt/Atlantis, policy as code (Checkov, Conftest), Packer, and the other IaC tools (CloudFormation, Bicep, Pulumi, Crossplane), and Terraform Associate topics (drift, lifecycle and conditions, functions, HCP Terraform); plus 5 HCL Writing Labs, a Sandbox, and 5 Mysteries |
| Networking | 17 | 8 | DNS, refused vs timeout, ports/nmap, routing/ARP, firewalls, TLS/openssl, HTTP/curl, in-cluster networking, CIDR, tcpdump, MTU black holes, IPv6, WireGuard, BGP, DNS delegation, HTTP/2 and gRPC, Cilium/Hubble |
| CI/CD | 20 | 8 | git workflows, revert vs reset, git bisect, tags/releases, GitHub Actions CLI, secrets/OIDC, local CI repro, rolling/blue-green/canary, GitOps (Argo CD), SBOMs/scanning/signing, SLSA provenance, zero-downtime database migrations, GitLab CI, Jenkins, artifact registries and promotion, release automation (semver, Renovate), flaky and contract tests; plus 4 pipeline Writing Labs |
| Monitoring | 17 | 8 | PromQL, golden signals, tracing (OTel/Jaeger), OpenTelemetry instrumentation, SLOs and burn-rate alerts, Prometheus ops, alerting/Alertmanager, journald, Elasticsearch, Loki, Grafana API, log pipelines (Fluent Bit, Vector), log volume and cardinality, Datadog and Sentry; plus 5 Writing Labs (alert rules, burn-rate alerts, a dashboard, manual spans) |
| MLOps | 18 | 8 | environments, GPUs, MLflow, DVC, serving, KServe/Kubeflow, profiling, model monitoring, model canaries, LLM serving (vLLM), feature stores (Feast), distributed training, Airflow pipelines, LLM evaluation, vector search (pgvector), token cost and guardrails, quantization |
| AWS | 17 | 7 | profiles/identity, EC2, SSM vs SSH, VPC anatomy, security groups vs NACLs, IAM, S3, CloudWatch/CloudTrail, ALB/ASG, EKS/ECR, cost, RDS, Route 53, peering/Transit Gateway/PrivateLink, and Solutions Architect design choices (storage classes and EFS, Multi-AZ vs replicas, Aurora, DynamoDB, caching, KMS, CloudFront, scaling policies); plus a VPC Sandbox |
| Azure | 13 | 6 | subscriptions, resource groups/locks, VMs (stop vs deallocate), Run Command/Bastion/az ssh, VNets/NSGs, UDRs/Network Watcher, RBAC/managed identity, Key Vault/storage, Monitor/KQL, AKS, and AZ-104 topics (Entra users and groups, Azure Policy, storage redundancy/SAS/AzCopy/lifecycle, scale sets, App Service slots, peering, Backup, action groups) |
| Google Cloud | 13 | 6 | configurations/projects/APIs, Compute Engine filters, IAP SSH/serial console, global VPCs, tag-based firewalls, Cloud NAT, IAM without keys/impersonation, Cloud Storage, logging/quotas, GKE/Workload Identity, and ACE topics (projects and billing, custom roles, budgets, instance templates and MIGs, Cloud Run, Cloud SQL, Pub/Sub, snapshots, choosing a database) |
| Security | 16 | 7 | nmap discovery/TLS checks, Trivy/kube-bench, Lynis/OpenSCAP CIS audits, SSH hardening, fail2ban, auditd, osquery/AIDE, secrets scanning, compromise triage, Kubernetes admission policy (Kyverno) and runtime detection (Falco), cloud posture scanning (Prowler), compliance evidence, threat modelling (STRIDE), Sigma detection rules, zero-trust access; plus 3 Writing Labs and 2 hacked-server mysteries |
| Server Fleet Ops | 13 | 7 | Ansible (inventories, safe playbook runs, rolling serial updates, Vault/lint), Debian and RHEL patching with rollback, kernels and reboots, SSM Patch Manager, chrony, LVM growth, backups with real restore tests, NFS, Ceph health |
| SRE | 14 | 6 | incident first ten minutes, Argo Rollouts canaries, Istio resilience, capacity planning, load testing (k6/vegeta), chaos engineering, feature flags/kill switches, postmortem timelines, graceful degradation, production readiness reviews, disaster recovery drills, service catalogs and golden paths, DORA metrics, LitmusChaos and game days |
| Git | 11 | 6 | objects/refs/HEAD, precise staging, branches, merge conflicts, rebase (autosquash, --onto), the undo matrix and reflog, searching history, remotes and forks, stash/worktrees, config/attributes/hooks, shallow and partial clones, submodules, LFS, signing; plus a real-git Sandbox and 5 Mysteries |
| System Design | 18 | 8 | estimation, load balancing, caching, indexes and query plans, replication, sharding, queues, consistency and quorums, rate limiting and idempotency, CDNs, distributed transactions (outbox, sagas), CQRS, multi-region, consensus and quorum, HyperLogLog and Bloom filters, real-time delivery, worked designs (URL shortener, chat); real commands plus multiple-choice trade-off questions; plus 4 design-document Writing Labs |
| Databases | 12 | 6 | psql, on-call SQL (joins, GROUP BY, window functions), transactions and isolation, roles and privileges, pg_stat_activity and lock chains, slow queries (pg_stat_statements, EXPLAIN), vacuum and wraparound, pg_dump/pg_restore, point-in-time recovery (pgBackRest), Patroni failover, MySQL, Redis operations; plus a real-SQL Sandbox and 4 Mysteries |
| Web Servers & Proxies | 11 | 6 | nginx (test and reload, server blocks and locations, reverse proxying, TLS with certbot, access-log analysis, reading 502/503/504, rate and body limits, caching and gzip, connection and file-descriptor capacity), HAProxy draining, and recognising Envoy, Caddy, Traefik, and Apache; plus 2 nginx Writing Labs |
| Identity & Secrets | 9 | 5 | reading JWTs, OAuth 2.0 and OIDC flows, Kubernetes workload identity, Vault (KV, policies, dynamic database credentials), External Secrets Operator, SOPS and Sealed Secrets, PKI and mutual TLS, cert-manager; plus 2 Writing Labs |
| Scripting | 8 | 4 | Python environments and pinned dependencies, running and debugging scripts, pytest/ruff/mypy, jq in depth, yq, regular expressions, Makefiles, building and testing Go tools; plus 2 Python Writing Labs |
| Messaging | 7 | 4 | Kafka (topics and replication, reading a topic by hand, consumer groups and lag, retention and compaction, broker operations), RabbitMQ alarms and queue limits, SQS visibility timeouts and dead-letter queues |
| Serverless | 7 | 4 | Lambda (invoke and logs, cold starts and concurrency, versions/aliases/canaries, event retries and failure destinations), API Gateway limits, ECS on Fargate, Cloud Run revisions and traffic, Azure Functions |
| Performance | 7 | 3 | perf CPU profiling, flame graphs, py-spy, JVM heap/GC/thread dumps, eBPF tools (execsnoop, biolatency, bpftrace), Go pprof, honest benchmarking and percentiles |
| FinOps | 6 | 3 | reading the bill by service and team, tags/budgets/anomaly alerts, rightsizing, Savings Plans and spot, Kubernetes cost (OpenCost), storage classes, log retention, and data transfer |
| Data Engineering | 5 | 2 | writing and testing Airflow DAGs, dbt (models, tests, state-based builds, freshness), warehouse cost and partitions (BigQuery, Snowflake), Spark on Kubernetes, change data capture with Debezium; plus 1 Writing Lab |
| The Wider Landscape | 13 | 0 | recognising the less common tools: Nomad and Consul, Puppet/Chef/Salt, Podman/Buildah/Skopeo, crictl and sandboxed runtimes, OpenShift/k3s/MetalLB, Bazel and Nix, Gerrit/Perforce/Mercurial, Windows and PowerShell, OpenStack/Proxmox/IPMI, Nagios/Zabbix/SNMP/StatsD, Slurm, SPF/DKIM/DMARC/DNSSEC, Fastlane |
| **Total** | **361** | **158** | + 51 Writing Labs |

> 🌐 The three clouds use different names for the same ideas (security
> group vs NSG vs firewall rule; CloudTrail vs Activity Log vs Audit
> Logs). The cross-cloud map at the end of GAPS.md Part 11 lines them up
> side by side.

<details>
<summary><b>Career Paths</b>: scenarios chained across categories</summary>

Plus **18 Career Paths** chaining scenarios across categories:

| Path | The journey |
|---|---|
| Ship a feature | end to end |
| A production incident chain | one problem crossing several layers |
| An ML model | from laptop to production |
| Security hardening | layer by layer |
| A platform | built from zero |
| "The Worst On-Call Night" | seven incidents, seven layers |
| A self-hosted LLM, shipped safely | build → sign → GitOps → serve → SLO |
| Multi-cloud | the same job on AWS, Google Cloud, and Azure |
| Security incident response | end to end |
| Patch Tuesday | for a fleet |
| SRE at scale | from readiness review to postmortem |
| Whiteboard to production | estimate → design → clean history → Terraform module → zero-downtime migration → provenance → admission policy |
| Own the database | live activity → slow queries → migrations and the lock queue → backups → a WAL-filled disk → recovering a deleted table |
| The front door | HTTP and TLS → nginx → load balancing → certificates → gateway errors → three proxy incidents |
| Secrets done right | a leaked key → Vault → dynamic credentials → workload identity → mTLS → two rotation outages |
| The event-driven backend | API Gateway → Lambda → queues and Kafka → three incidents in the joins → budgets |
| Faster and cheaper | measure → profile → rightsize → autoscale → Kubernetes cost |
| Database to dashboard | on-call SQL → change data capture → Airflow → dbt → the warehouse → two quiet data bugs |

</details>

<details>
<summary><b>Mystery Incidents</b>: symptom only</summary>

Plus **37 Mystery Incidents**, symptom only:

| Area | Mysteries |
|---|---|
| ☸️ Kubernetes | 503s while every pod is Running, a deploy that never finishes, workers that fail and then fail differently, the morning after node maintenance, and pods that are Running but not Ready |
| 🐧 Linux | an API down after a deploy, a disk alert that won't clear, a database that keeps dying, and a slow server with two unrelated problems |
| 🐳 Docker | a container that "disappears", and a worker the dashboard wrongly reports as "running" |
| ☁️ AWS | a new web server that times out, private workers that can't pull updates, SSH that works while the site doesn't, and a "network hardening" change that broke everything |
| ☁️ Azure | an allow rule that's "right there" but ignored, an app tier that lost the internet, and a subnet firewall that looks perfect |
| ☁️ Google Cloud | a rebuilt web VM nobody can reach, workers that can't install packages, and the morning after a firewall cleanup |
| 🛡️ Security | a pegged CPU and a doubled cloud bill (a crypto-miner that comes back until you find its cron job), and a 3am login (a brute-forced root password, a hidden UID-0 account, and a planted SSH key) |
| 🗄️ Databases, in real SQL | a 'My orders' page that got slow after a migration, a revenue day that doubled, saved addresses to restore from a backup that's older than the live data, and an export that can't find its orders |
| 🏗️ Terraform | port 22 open while the code says it isn't, every pipeline failing on a lock, a tidy-up that would replace production, an apply that fails on a brand-new bucket, and handing a database to another team without deleting it |
| 🌿 Git, with the real git | two commits on the wrong branch, a payment key in unpushed history, a merge stopped halfway, work lost to a reset, and a pushed release that broke every timeout |

</details>

---

## Will this make me proficient in DevOps?

**Honest answer: see [GAPS.md](GAPS.md)**, which assesses every category
individually (covered / still missing / readiness verdict) plus an
overall verdict in its final part.

- **GAPS.md's Backlog part** is the full list of topics this game doesn't
  teach yet, in three tiers (commonly used, role-dependent, and niche),
  so you can see what's left to learn.
- **In short:** completing everything here makes you a strong DevOps
  *operator*. You'll know the commands, the failure modes, and the
  debugging method.
- **To be fully proficient** you also need to practise *authoring*
  (Dockerfiles, Terraform, pipeline YAML, scripts), time on real
  infrastructure where things break in unscripted ways, and
  cloud-provider fundamentals. GAPS.md's final part lays out a concrete
  path.
- **For certifications:** GAPS.md maps the CKA, CKAD, and CKS (Part 1),
  the Terraform Associate (Terraform part), and the associate exams of
  all three clouds (AWS Solutions Architect Associate, AZ-104, and
  Google Cloud ACE, each in its cloud's part) onto the content.

---

## Running it

Requires **Python 3.12+** and PyYAML:

```bash
pip install -r requirements.txt   # or just: pip install pyyaml
python game.py
```

PyYAML is only needed for Writing Labs; everything else uses only the
standard library. The Git sandbox also needs `git` installed.

---

## Adding a new scenario

The quickest start is the scaffold. It picks the next free id, writes the
file in the right folder, and marks every field you still have to write
with `TODO(scaffold)` (the tests fail until none are left):

```bash
python game.py add-scenario          # asks what you're adding
python game.py add-scenario --type tutorial --category git --title "Sparse checkout" --steps 4
python game.py add-scenario --type mystery --sandbox db --title "..."
```

Anything you add is picked up automatically, with no code changes. Run the
test suite afterwards: the parametrized content tests validate new files
against the schema, and include self-consistency checks (a lab's
`solution` must pass its own `validate` spec; a career path's `steps` must
all resolve to real scenario ids).

<details>
<summary><b>Tutorial or incident</b></summary>

Drop a new JSON file into `scenarios/<category>/tutorials/` or
`scenarios/<category>/incidents/` (category = any folder under
`scenarios/`) following the schema in SPEC.md: id, type, category, title,
difficulty, and steps with `prompt`/`expected_commands`/`fake_output`,
plus `why` per step, which every tutorial in this repo carries.

Pull real command syntax from that category's `commands/<category>.md`
reference so what the game teaches matches the actual tool.

**A brand-new category** just needs a new
`scenarios/<newcategory>/tutorials/` (and/or `incidents/`) folder;
`list_categories()` discovers it automatically, with no code changes.

</details>

<details>
<summary><b>Writing Lab</b></summary>

Drop a new JSON file into `scenarios/yaml_labs/` (the folder keeps its
original name) with `type: "yaml_lab"` and steps shaped like:

```json
{"file": "pod.yaml", "starter_content": "...", "prompt": "...",
 "apply_commands": ["..."],
 "validate": {"kind": "Pod", "fields": {"metadata.name": "db"}},
 "hint": "...", "solution": "...", "fake_output": "..."}
```

| Validation feature | How it works |
|---|---|
| Dotted paths | `validate.fields` uses dotted notation with `[N]` for list indices, e.g. `spec.containers[0].image` |
| `"ANY"` | The field must exist, but its exact value doesn't matter (like a random name) |
| `[*]` | Matches any list element (`jobs.test.steps[*].run`); with a list as the expected value, every item must appear |
| `{"contains": [...]}` | Substring checks, good for PromQL or `if:` expressions |
| `"order": [...]` | Substrings that must appear in that line order |
| `"absent": [...]` | Text that must not appear, e.g. a hardcoded password |

- `kind` is only required for Kubernetes labs. Set `category` so the lab
  list labels it.
- For non-YAML files add `"format"` to the step (`dockerfile`, `hcl`,
  `bash`, `ansible`, `yamllist`, `markdown`, `nginx`, or `python`); paths
  then refer to the parsed structure (e.g. `FROM[0]`,
  `resource.aws_s3_bucket.logs.bucket`, `text`).

</details>

<details>
<summary><b>Career path</b></summary>

Drop a new JSON file into `scenarios/career_paths/` with
`type: "career_path"` and `{"id", "title", "intro", "steps": [existing
scenario ids in play order], "resolution"}`. No new scenario content is
needed, just a sensible ordering of ids that already exist, spanning at
least two categories.

</details>

<details>
<summary><b>Mystery incident</b></summary>

Drop a JSON file into `scenarios/mysteries/` with `type: "mystery"`, a
`sandbox` (`linux`, `docker`, `kube`, `aws`, `azure`, `gcp`, `db`,
`git`, or `terraform`), and `setup` (a `seed` plus forced `problems`, or `assignments`
for docker). It also needs:
- a `symptom`;
- `goals` (state checks such as `service_active`, `disk_below`, and
  `load_below_nproc`; leave empty for docker);
- `evidence` (`{"description", "seen_any": [...]}`, text that must
  appear in some command's output before `solve` is accepted);
- a multiple-choice `question`;
- `expert_commands`, `solution_commands`, and a `debrief`.

The tests run `solution_commands` against the seeded state to prove the
mystery is solvable and that the solution finds the evidence.

</details>

---

## Testing

```bash
python -m pytest
```

It covers:
- the matching engine, category-aware scenario loading, and sandbox
  command handling;
- progress tracking, the Writing Lab parsers and validation logic, and
  the Career Path runner;
- every scenario, lab, and path JSON file against its schema, including
  self-consistency checks: every tutorial's and incident's listed
  commands match under the real matcher, every lab's solution passes its
  own validate spec, and every career path's steps resolve to real
  scenarios.

Run it after any change to the engine, loader, sandboxes, yaml_lab,
career_path, mystery, or scenario content. Git sandbox tests are skipped
when git isn't installed.

---

## Project structure

<details>
<summary><b>Show the file layout</b></summary>

```
game.py             entry point / main menu (practice, career paths,
                     writing labs, exam, mysteries, sandboxes, stats)
                     and `add-scenario`
engine.py           generic scenario runner + fuzzy command matching
                     (zero tool-specific logic: works identically for
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
career_path.py      chains existing scenarios across categories into
                     one continuous playthrough
progress.py         reads/writes progress.json (completion + attempt
                     counts, flat across all categories; ids are
                     globally unique)
scaffold.py         `python game.py add-scenario`: skeletons for new content
sandbox.py          Kubernetes sandbox (random cluster, read-only)
kube_sandbox.py     Kubernetes sandbox (fixable: status derived from cause)
docker_sandbox.py   Docker sandbox (random broken host)
linux_sandbox.py    Linux sandbox (random broken server; reacts to fixes)
aws_sandbox.py      AWS sandbox (a VPC with real layer-by-layer reachability)
azure_sandbox.py    Azure sandbox (NSG priorities, NIC NSGs, routes to a firewall)
gcp_sandbox.py      Google Cloud sandbox (tag-based firewalls, IAP SSH, Cloud NAT)
db_sandbox.py       database sandbox (real SQL on an in-memory SQLite shop database)
git_sandbox.py      Git sandbox (the real git on a throwaway repository)
tf_sandbox.py       Terraform sandbox (code, state, and the real account, diffed by plan)
sandbox_common.py   shared sandbox loop, pipes, tables, save/discard
yaml_lab.py         Writing Labs runner: real file editing + validation
lab_formats.py      parsers for YAML/JSON, Dockerfile, HCL, bash, Ansible,
                     YAML lists, Markdown, nginx, and Python lab files
tools/
  sync_docs.py      rewrites the counts in GAPS.md, README.md, CLAUDE.md
  git_editor.py     the editor the Git sandbox hands to git
scenarios/
  <category>/tutorials/*.json, incidents/*.json   one folder per category
  yaml_labs/*.json   Writing Labs (not nested by category)
  career_paths/*.json  ordered lists of existing scenario ids spanning
                     2+ categories (not nested by category)
  mysteries/*.json   symptom + sandbox seed + goals + evidence + question
tests/              pytest suite (see Testing, above)
progress.json       local player progress (gitignored), created on first play
sandbox_data/       local runtime state (gitignored): active + saved
                     sandbox sessions
workspace/          local lab files you edit and Git sandbox repositories
                     (gitignored); a lab resets to its starter content
                     every time you enter it
commands/           one master command reference per category
                     (commands/kubernetes.md, commands/docker.md, ...);
                     pull from the matching file when writing new
                     scenario JSON for that category
SPEC.md             the *original*, Kubernetes-only design spec, kept
                     for history; see CLAUDE.md for current architecture
GAPS.md             honest self-assessment per category (and overall):
                     what this prepares you for, what's still missing
CLAUDE.md           working notes for AI-assisted development on this repo
```

</details>

---

## Status / roadmap

<details>
<summary><b>How it was built, step by step</b></summary>

1. Hardcoded single scenario → JSON-driven scenarios with a menu → hint
   escalation → sandbox → progress tracking.
2. Full Kubernetes coverage → CKA gap-filling → Writing Labs.
3. Multi-category architecture → Career Paths → all 8 original categories
   expanded to full depth → Dockerfile, Terraform, and bash Writing Labs.
4. Exam Mode → Docker and Linux sandboxes → Mystery Incidents.
5. New-topic content (tracing, SLOs, tcpdump/MTU, GitOps, supply chain,
   bisect, LLM serving, feature stores, strace, BuildKit, Terraform
   modules, and RBAC/PDB/storage incidents).
6. AWS category, VPC sandbox, and AWS mysteries → Azure and Google Cloud
   categories → Security category and hacked-server mysteries → Server
   Fleet Ops category → SRE category.
7. Cloud, Ansible, and postmortem Writing Labs, plus four more career
   paths → Stats screen → Azure and Google Cloud sandboxes with mysteries
   → a fixable Kubernetes sandbox with five Kubernetes mysteries.
8. Git category → System Design category (with multiple-choice decision
   steps and design-document labs).
9. A gap-closing batch (admission webhooks, Multi-Attach, SELinux, IPv6,
   database migrations, SLSA provenance, OpenTelemetry instrumentation,
   distributed training, Airflow, RDS, Route 53, Kyverno/Falco, Terraform
   modules, getopts).
10. Databases category (PostgreSQL operations, SQL, recovery, MySQL,
    Redis) → Web Servers & Proxies category (nginx, HAProxy, and an nginx
    lab format).
11. The rest of the backlog (identity and secrets, scripting, messaging,
    serverless, performance, FinOps, data engineering, and The Wider
    Landscape, plus depth in the existing categories) → career paths over
    the new categories.
12. A database sandbox running real SQL and a Git sandbox running real
    git, each with mysteries → the `add-scenario` scaffold → exam passes
    for the CKAD, Terraform Associate, and AWS Solutions Architect
    Associate → exam passes for the CKS, AZ-104, and Google Cloud ACE →
    a Terraform sandbox with five mysteries.

</details>

**Next**, in priority order (details in CLAUDE.md and GAPS.md):
- exam passes for the professional-level cloud exams;
- a networking sandbox.

See [CLAUDE.md](CLAUDE.md) for architecture and notes for continuing
development.
