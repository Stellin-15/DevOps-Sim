# kube-sim — Terminal-Based Kubernetes/DevOps Learning Game

> **Historical note:** this was the original, Kubernetes-only design spec
> (v1–v6). The project has since expanded into a multi-category DevOps
> simulator (Kubernetes, Docker, Linux, Terraform, Networking, CI/CD,
> Monitoring, MLOps) plus YAML Labs and Career Paths. This file is kept
> as-is for history — see **CLAUDE.md** for the current architecture and
> **README.md** for current usage. The matching rules, feedback rules, and
> JSON schema described below are still accurate; the "one category"
> framing and build order are not.

## Overview

A terminal-based CLI game for learning real DevOps/Kubernetes commands by doing, not memorizing. Two modes:

- **Tutorial mode** — short, guided, beginner-friendly scenarios that teach one command/concept at a time (create a pod, expose a service, scale a deployment, etc.)
- **Incident mode** — longer, investigative scenarios that simulate real production problems (CrashLoopBackOff, service unreachable, OOMKilled, etc.) where you have to figure out the right sequence of commands to diagnose and resolve the issue

Everything runs 100% locally. No real cluster connection, no hosting, no backend, no auth. All scenario content and simulated outputs are pre-written in JSON files. All progress is stored in a local JSON file.

The engine is fully generic — it just reads scenario JSON and validates typed commands against expected patterns. It has zero hardcoded knowledge of Kubernetes itself, so the same game can later be extended with Docker, Terraform, CI/CD, or any other command-line topic just by adding new JSON files with a different `category`.

---

## Tech Stack

- Python 3
- No external database — flat JSON files only
- Terminal UI: plain input/output for v1; consider the `rich` library later for colored output once the core loop works
- No network calls, no external services, no installation beyond local Python

---

## Data Model

### Scenario JSON schema

Every scenario, whether tutorial or incident, follows this shape. Stored one file per scenario under `/scenarios/`.

```json
{
  "id": "tutorial-001",
  "type": "tutorial",
  "category": "kubernetes",
  "title": "Your First Pod",
  "difficulty": "beginner",
  "tags": ["pods", "basics"],
  "intro": "Let's create your first pod. In real k8s, you'd use kubectl run for a quick one-off pod.",
  "steps": [
    {
      "prompt": "Create a pod named 'my-first-pod' using the nginx image.",
      "expected_commands": [
        "kubectl run my-first-pod --image=nginx",
        "kubectl run my-first-pod --image nginx"
      ],
      "fake_output": "pod/my-first-pod created",
      "explanation": "kubectl run creates a single pod directly — no Deployment, no self-healing. Good for quick tests, not production.",
      "hint": "Syntax: kubectl run <name> --image=<image>"
    },
    {
      "prompt": "Now check that it's running.",
      "expected_commands": [
        "kubectl get pods",
        "kubectl get pod my-first-pod"
      ],
      "fake_output": "my-first-pod   1/1   Running   0   5s",
      "explanation": "kubectl get pods lists everything in the current namespace."
    }
  ],
  "resolution": "Optional: a closing summary shown at the end, mainly used by incident scenarios.",
  "real_commands_used": ["kubectl run", "kubectl get pods"]
}
```

Field notes:
- `type`: `"tutorial"` or `"incident"` — determines tone/feedback style, not engine behavior
- `category`: e.g. `"kubernetes"` — lets the game filter/organize by topic and later support non-k8s content
- `expected_commands`: a list of acceptable exact-ish strings (see matching rules below) — not a single string, since multiple valid phrasings usually exist
- `hint`: optional, shown after N failed attempts on that step
- `explanation`: optional, shown after a correct answer to reinforce why it was right (tutorials should almost always have this; incidents can save it for the final debrief instead)

### Progress JSON schema

Stored in a single local `progress.json`:

```json
{
  "tutorials_completed": ["tutorial-001", "tutorial-002"],
  "incidents_completed": ["crashloop-001"],
  "attempts": {
    "tutorial-001": 1,
    "crashloop-001": 3
  }
}
```

---

## Core Game Loop

1. Main menu: choose **Learn** (tutorials) or **Incidents**, or **Sandbox** (see below)
2. Show scenario list filtered by mode, with completion status and difficulty shown
3. Load chosen scenario JSON
4. Show `intro`
5. For each step:
   - Show `prompt`
   - Read player's typed command
   - Validate against `expected_commands` (see matching rules)
   - If correct: show `fake_output`, then `explanation` if present, advance to next step
   - If incorrect: give feedback (see feedback rules), allow retry
   - Track attempt count per scenario in `progress.json`
6. After all steps: show `resolution` if present, mark scenario complete, return to menu

---

## Command Matching Rules

This is the trickiest part of the engine — be deliberate about it.

- Real kubectl commands include variable names (pod names, namespaces) that can't be matched exactly, so matching must be pattern-based, not literal string equality
- Normalize input before comparing: trim whitespace, collapse multiple spaces, lowercase the command verb/resource (but not necessarily flag values)
- Accept minor variations automatically:
  - Singular/plural resource names (`pod` vs `pods`)
  - `--flag=value` vs `--flag value`
  - Reordered flags
- Give **partial credit / near-miss feedback** rather than a flat wrong/right:
  - Right verb + resource, wrong/missing flag → "Close — check your flags"
  - Right general idea, wrong command entirely → generic nudge, not the answer
  - Nothing close → prompt to try again or ask for a hint
- `expected_commands` in the JSON should be treated as a list of acceptable patterns (can include simple wildcards or regex if needed for pod-name suffixes like `checkout-service-7f9d...`)

---

## Feedback & Hint System

- Wrong answer: short generic nudge first (not the answer)
- After 2 wrong attempts on the same step: show the `hint` field if present
- After 4 wrong attempts: offer to reveal the expected command outright, no penalty (this is a learning tool, not a test)
- Correct answer: confirmation + `fake_output` + `explanation` (if present)

---

## Modes

### Learn (tutorials)
- Short (1–3 steps), sequential within a topic, gentle
- Suggested initial topic order: pods → deployments → services → scaling → configmaps/secrets → logs & debugging basics
- Optional: gate topics so e.g. "deployments" tutorial unlocks after "pods" tutorial is completed — make this a toggle/config option, not hardcoded, since sometimes jumping around is fine

### Incidents
- Longer (3+ steps), investigative, simulate a real production problem
- Should require chaining multiple commands correctly (get → describe/logs → fix) to reach resolution
- End with a `resolution` debrief explaining what actually happened and why, plus `real_commands_used` as a recap

### Sandbox (optional, build after v1–v4 work)
- No scoring, no steps — just a single fake cluster-state JSON file the player can poke at with any command and get plausible simulated output
- Good for free-form practice once they know rough syntax and just want it to feel automatic

---

## Build Order (tell Claude Code to build in this order, not all at once)

- **v1** — Single hardcoded tutorial scenario, playable start to finish in terminal. No JSON loading yet, no menu. Just prove the core loop works.
- **v2** — Load scenarios from `/scenarios/*.json`, add a menu to pick one, separate tutorial vs incident scenario folders/lists
- **v3** — Add `progress.json` tracking (completed scenarios, attempt counts), show completion status in the menu
- **v4** — Add the full hint escalation system (nudge → hint → reveal)
- **v5** — Sandbox/freeform mode
- **v6** (optional, later) — A simple CLI helper to scaffold a new scenario JSON file (`python game.py add-scenario`) so adding content doesn't mean hand-writing JSON from scratch every time

---

## Explicit Constraints to Give Claude Code

- No real kubectl/cluster connection anywhere — every "output" is a pre-written string from JSON, never a live command execution
- Keep the engine and content strictly separate: the engine only knows how to read scenario JSON and validate commands against patterns — it must have zero kubectl-specific logic hardcoded, so the same engine could run Docker or Terraform scenarios later just by adding new JSON with a different `category`
- Command validation must be pattern/fuzzy-based, not exact string match, per the matching rules above
- Keep v1 as small as possible — a single working scenario end to end — before adding JSON loading, menus, or progress tracking

---

## Nice-to-Haves (mention as future ideas, not for v1)

- Colored terminal output for correct/wrong/hint feedback (`rich` library)
- `--difficulty` or `--category` CLI flags to filter scenario lists
- Random scenario picker vs. sequential campaign mode
- Attempt-count/speed stats per scenario shown in a summary screen
