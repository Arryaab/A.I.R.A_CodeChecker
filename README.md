# Aegis: AI Change Verification & Evaluation Platform

[![CI Verification Guardrail](https://github.com/aryab/aegis-lite/actions/workflows/aegis_verify.yml/badge.svg)](https://github.com/aryab/aegis-lite/actions)
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-success)

> **"Don't just ask if an AI agent can generate code. Ask: Can this AI-generated change be safely merged, and can we empirically prove that it is correct?"**

Aegis is an enterprise verification layer that sits between autonomous coding agents and production. It evaluates AI-generated software changes at the repository level by combining **commit-pure Git diff analysis**, **AST-level security guardrails**, **intelligent test selection**, **deterministic mutation testing**, **hardened Docker sandbox execution**, and **adaptive risk budgeting**.

---

## 🏛️ System Architecture

```text
                 AI CODING AGENT
                        │
                        ▼
             PROPOSED PULL REQUEST
                        │
                        ▼
         ┌───────────────────────────────┐
         │     AEGIS VERIFICATION        │
         └──────────────┬────────────────┘
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
   GIT DIFF        REPOSITORY       SECURITY GUARDRAIL
  PatchChange     INTELLIGENCE       AST & Secrets
  (Commit-Pure)   Dependency Graph  Prompt Injection
        │               │                │
        └───────┬───────┘                │
                ▼                        │
         TEST SELECTION                  │
                │                        │
        ┌───────┴────────┐               │
        ▼                ▼               ▼
   TARGETED TESTS   FULL REGRESSION  MUTATION SCORE
   (Fast Feedback)   (Sandboxed)    (Deterministic)
        │                │               │
        └───────┬────────┴───────────────┘
                ▼
      HEURISTIC RISK MODEL & BUDGETING
        │ (FAST / STANDARD / DEEP)
        ▼
   PRODUCTION MERGE DECISION
     /                     \
 APPROVE 🚀             REVIEW ⚠️ / REJECT ⛔
 (Auto-Merge)          (Human Approval Needed)
```

---

## ⚡ Core Capabilities

### 1. Commit-Pure Change Verification
Unlike naive tools that audit the local dirty working directory, Aegis inspects the Git object database directly via `git show {base}:{path}` and `git show {head}:{path}`. It constructs a structured `PatchChange` representation tracking:
- Added, modified, deleted, and renamed files (`A`, `M`, `D`, `R`).
- Isolated added hunks vs. reconstructed post-change Python ASTs.
- Protection against silent AST syntax failures on unified diff headers.

### 2. AST Security & Prompt Injection Guardrail
- **Secret & Key Leakage:** Regex scanning on newly added lines to detect exposed AWS keys, GitHub tokens, and hardcoded credentials.
- **Prompt Injection Defense:** Blocks AI comments trying to hijack the verifier (`"ignore previous instructions"`, `"return approved=true"`).
- **Dangerous AST Imports:** Forbids untrusted introduction of `socket`, `pty`, `subprocess`, `eval()`, or `exec()`.
- **Critical File Deletion Detection:** Immediately blocks unauthorized deletions of authentication, security, or guardrail modules.

### 3. Adaptive Verification Tiers (`FAST`, `STANDARD`, `DEEP`)
Aegis automatically balances developer velocity and verification depth:
- `FAST`: Sub-second feedback. Evaluates Git diffs, AST syntax, security guardrails, and runs **only** the targeted tests affected by the patch.
- `STANDARD`: FAST checks + full repository regression test suite + empirical AST mutation sample.
- `DEEP`: STANDARD checks + exhaustive mutation testing + execution timing regression monitoring.
- `AUTO` (Default): Adaptively selects the verification budget based on the patch's computed risk score.

### 4. 100% Deterministic Mutation Testing
Measures whether the repository test suite is robust enough to catch regressions or if it is overfitting:
- Uses `DeterministicMutator` to mutate AST comparison and binary operators in consistent sequential order.
- Replaces modified files, executes the test suite, and calculates the true empirical score:
  $$\text{Mutation Score} = \frac{\text{Killed Mutants}}{\text{Total Mutants}}$$

### 5. Hardened Sandbox Isolation
Untrusted AI code executes in a constrained Docker boundary:
- Network disabled: `--network none` (no data exfiltration).
- Resource limits: `--cpus 1.0`, `--memory 512m`, `--pids-limit 50`.
- Dropped capabilities: `--security-opt no-new-privileges`, `--cap-drop ALL`.
- Monotonic wall-clock timing measurement and guaranteed `finally:` container cleanup.

---

## 🚀 Live Verification Report Card

When running `aegis verify --base HEAD~1 --head HEAD`:

```text
====================================================================
🛡️  AEGIS AI CHANGE VERIFICATION PLATFORM
====================================================================
Target:             Git Diff: HEAD~1..HEAD
Affected Files:     4 (aegis/evals/risk_model.py, aegis/execution/sandbox.py...)
Verification Tier:  FAST (Risk: 0.50 MEDIUM)
--------------------------------------------------------------------
Correctness:        ✅ Passed (1 targeted test files passed in 0.825s)
Regression:         ⚡ Skipped (FAST Tier)
Security:           ✅ Passed (AST imports + added lines scanned)
Mutation Score:     ⚡ Skipped (FAST Tier)
Risk Score:         0.50 (MEDIUM RISK)
  - Risk factor: Large diff size (>50 lines)
  - Risk factor: Multiple files modified (4)
--------------------------------------------------------------------
VERDICT: APPROVE 🚀 (Change qualified for production merge)
```

---

## 🛠️ Quick Start

### Installation
```bash
git clone https://github.com/aryab/aegis-lite.git
cd aegis-lite
pip install -e .[all]
```

### 1. Verify a Pull Request or Git Commit
```bash
# Verify changes between base and head
python -m aegis.cli verify --base origin/main --head HEAD

# Run in FAST tier for immediate sub-second feedback
python -m aegis.cli verify --base HEAD~1 --tier fast

# Verify a standalone patch file directly
python -m aegis.cli verify --diff proposed_change.patch
```

### 2. Autonomous Multi-Agent Program Repair
Aegis also provides autonomous multi-file repair driven by repository AST intelligence:
```bash
python -m aegis.cli repair --project-dir ./my_buggy_project
```

### 3. Run the Test Suite
```bash
python -m pytest -q
```
All **57 tests** pass cleanly with 0 collection errors.

---

## 📊 Benchmark Integrity (AegisBench)
In alignment with 2026 benchmarks (such as SWE-Bench Pro Verified and SWE-Gate), Aegis rejects fake autogenerated benchmark placeholders. Every task follows the formal [AegisBench Schema](benchmarks/SCHEMA.md):
- `metadata.json` & `provenance.json` (source repository, commit SHA, verified issue ID).
- `problem.md` (natural language prompt).
- `constraints.yaml` (API stability, memory, latency).
- `oracle_patch.diff` (gold standard human fix).

---

## 📄 License
Licensed under the [MIT License](LICENSE).
