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
- `FAST`: Fast targeted verification. Evaluates Git diffs, AST syntax, security guardrails, and runs **only** the targeted tests affected by the patch (skips full regression and mutation testing).
- `STANDARD`: FAST checks + full repository regression test suite + empirical AST mutation sample on changed production modules.
- `DEEP`: STANDARD checks + exhaustive mutation testing + execution timing regression monitoring.
- `AUTO` (Default): Adaptively selects the verification budget based on the patch's computed risk score.

### 4. 100% Deterministic Mutation Testing
Measures whether the repository test suite is robust enough to catch regressions or if it is overfitting:
- Uses `DeterministicMutator` to mutate AST comparison and binary operators in consistent sequential order.
- Filters mutation candidates strictly to affected production source files (excluding test suites and configuration).
- Replaces modified files in the isolated snapshot, executes the test suite, and calculates the true empirical score:
  $$\text{Mutation Score} = \frac{\text{Killed Mutants}}{\text{Total Mutants}}$$

### 5. Hardened Sandbox Isolation
Untrusted AI code executes in a constrained Docker boundary:
- Network disabled: `--network none` (no data exfiltration).
- Resource limits: `--cpus 1.0`, `--memory 512m`, `--pids-limit 50`.
- Dropped capabilities: `--security-opt no-new-privileges`, `--cap-drop ALL`.
- Monotonic wall-clock timing measurement and guaranteed `finally:` container cleanup.

### 6. Environment Fingerprinting & Dependency Hashing
Ensures reproducibility across environments:
- Detects manifests (`requirements.txt`, `pyproject.toml`, `setup.py`, `poetry.lock`).
- Computes deterministic SHA-256 `dependency_lock_hash` and environment fingerprint.
- Guarantees third-party dependencies are frozen and accounted for prior to network isolation.

---

## 🛡️ Example Verification Output

Below is an example verification output produced by `aegis verify --base origin/main --head HEAD`:

```text
====================================================================
🛡️  AEGIS AI CHANGE VERIFICATION PLATFORM
====================================================================
Target:             Git Diff: origin/main..HEAD
Affected Files:     2 (auth/token_guardrail.py, models/user.py)
Verification Tier:  STANDARD (Risk: 0.30 MEDIUM)
--------------------------------------------------------------------
Correctness:        ✅ Passed (2 targeted test files passed)
Regression:         ✅ Passed (0 regressed)
Security:           ✅ Passed (AST imports + added lines scanned)
Mutation Score:     ✅ 100.0% (2/2 killed)
Performance:        ⚡ Skipped (STANDARD Tier)
Risk Score:         0.30 (MEDIUM RISK)
  - Risk factor: Sensitive authentication module modified
--------------------------------------------------------------------
Technical Verdict:  QUALIFIED ✅
Release Policy:     REVIEW ⚠️ (Medium risk change requires peer review before release)
Audit Artifact:     .aegis/runs/run_20260926_180000_a1b2c3/report.json (Schema v1.0)
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
# Verify changes between base and head (executes HEAD commit)
python -m aegis.cli verify --base origin/main --head HEAD

# Run in FAST tier for rapid targeted feedback
python -m aegis.cli verify --base HEAD~1 --tier fast

# Run in DEEP tier for full regression, mutation, and performance latency benchmarking
python -m aegis.cli verify --base HEAD~1 --head HEAD --tier deep

# Verify a standalone patch file directly onto an immutable base snapshot
python -m aegis.cli verify --diff proposed_change.patch --base HEAD~1

# Export machine-readable Schema 1.0 audit artifacts to a custom directory
python -m aegis.cli verify --base HEAD~1 --output-dir ./audit_artifacts
```

### 2. Launch Verification REST API Service
```bash
export AEGIS_API_KEY="your-secure-api-key"
uvicorn aegis.api.service:app --host 127.0.0.1 --port 8000
# Authenticate requests via header: -H "X-API-Key: your-secure-api-key"
# Endpoints: /v1/health, POST /v1/verifications, GET /v1/verifications/{run_id}/report
```

### 3. Validate Benchmark Suite
```bash
python -m aegis.cli benchmark --dir benchmarks/dev --validate
```

### 4. Autonomous Multi-Agent Program Repair
Aegis also provides autonomous multi-file repair driven by repository AST intelligence:
```bash
python -m aegis.cli repair --project-dir ./my_buggy_project
```

### 5. Run the Test Suite
All unit, integration, security, sandboxing, and benchmark validation suites run directly via pytest:
```bash
python -m pytest -v
```
[![CI Test Suite](https://img.shields.io/badge/test%20suite-100%25%20passing-brightgreen)](https://github.com/aryab/aegis-lite/actions)

---

## 📊 Benchmark Integrity (AegisBench Dev v0.1)

Aegis includes **AegisBench Dev v0.1**, a standardized diagnostic suite of 15 algorithmic and logical Python defect fixtures designed for unit testing, repair pipeline validation, and verifier regression testing.

In alignment with modern benchmark standards (such as SWE-Bench Pro Verified and SWE-Serve), Aegis enforces physical structural separation between public tasks and private evaluator data to eliminate data contamination:
- `task/`: Public task specification exposed to autonomous coding agents (`problem.md`, `metadata.json`, `buggy/`, and visible `tests/`).
- `private/`: Private evaluator harness untracked by public Git (`hidden_tests/`, `oracle_patch.diff`, `provenance.json`, and `constraints.yaml`), supportable via decoupled `--evaluator-dir`.

See [AegisBench Task Schema](benchmarks/SCHEMA.md) for full specification.

---

## 📄 License
Licensed under the [MIT License](LICENSE).
