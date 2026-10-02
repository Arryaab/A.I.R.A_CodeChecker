# A.I.R.A. System Architecture & Verification Lifecycle

**A.I.R.A. (AI Release Assurance)** is an enterprise-grade software verification and release-control platform. It sits between autonomous code generation systems (agents, LLMs, automated PR bots) and production software repositories.

---

## 1. High-Level Control Plane Architecture

```text
               +--------------------------------------------------+
               |             AI CODE GENERATION LAYER             |
               |  (Coding Agents, LLM IDEs, Automated PR Bots)   |
               +-------------------------+------------------------+
                                         |
                                         | Unified Git Diff / PR Ref
                                         v
               +--------------------------------------------------+
               |            A.I.R.A. INGESTION & REST API         |
               |   FastAPI Service (/api/verifications, Web UI)  |
               +-------------------------+------------------------+
                                         |
                 +-----------------------+-----------------------+
                 |                                               |
                 v                                               v
+----------------------------------+           +----------------------------------+
|      MLVERIFY (SHADOW MODE)      |           |     SECURE SANDBOX CONTAINER     |
| Pre-Verification Risk Prediction |           | Docker / Hardened Process Jail   |
|   * Defect Risk Probability      |           |   * Read-only root filesystem    |
|   * Feature Contract Validation  |           |   * Network disabled (--net none)|
|   * Zero Gate Bypass (Shadow)    |           |   * CPU/Memory/PID resource caps |
+----------------------------------+           +-----------------+----------------+
                                                                 |
                                                                 v
                                         +----------------------------------------+
                                         |      DETERMINISTIC 6-GATE PIPELINE     |
                                         +----------------------------------------+
                                         | [C1] Syntax & AST Integrity Gate       |
                                         | [C2] Visible Acceptance Tests Gate     |
                                         | [C3] Hidden Invariant & Edge Cases     |
                                         | [C4] Full Regression Test Suite        |
                                         | [C5] Deterministic Mutation Score Gate |
                                         | [C6] Security AST & Taint Analysis     |
                                         +-------------------+--------------------+
                                                             |
                                                             v
                                         +----------------------------------------+
                                         |        RELEASE POLICY ENGINE           |
                                         |  Evaluates Gate Results & Risk State   |
                                         +-------------------+--------------------+
                                                             |
                                           +-----------------+-----------------+
                                           |                 |                 |
                                           v                 v                 v
                                    [AUTO_APPROVE]       [REVIEW]           [BLOCK]
                                    Qualified Pass    Semantic Review     Hard Rejection
                                           |                 |                 |
                                           +-----------------+-----------------+
                                                             |
                                                             v
                                         +----------------------------------------+
                                         |        CRYPTOGRAPHIC AUDIT LOG         |
                                         |   SHA-256 Hashed Evidence Trail        |
                                         +----------------------------------------+
```

---

## 2. Verification Controls (When Applicable)

A.I.R.A. uses six verification controls when applicable. Each control reports a distinct capability and verification state: `AVAILABLE`, `RUNNING`, `PASSED`, `FAILED`, `ERROR`, `NOT_AVAILABLE`, or `NOT_SUPPORTED`.

Applicability depends strictly on:
- **Project Type**: Programming language, framework, and test discovery metadata.
- **Baseline Availability**: Whether a historical Git commit reference or baseline branch is supplied.
- **Independent Evaluator Availability**: Whether independent, decoupled test suites exist outside the generator context.
- **Execution Support**: Whether the execution runtime (e.g., container mutation harness) is implemented for the submission type.

Controls that cannot be executed are truthfully reported as limitations rather than fabricated passes.

---

### Control C1: STATIC AST INTEGRITY
- **State**: `AVAILABLE` where supported.
- **Objective**: Prevent unparseable or grammatically invalid code from entering the repository.
- **Mechanism**: Parses source files into complete Python Abstract Syntax Trees (AST). Validates grammar conformance, token integrity, and absence of syntax errors before test invocation.
- **Verdict Rule**: Any syntax error halts verification immediately with verdict `REJECTED`.

### Control C2: PROJECT & USER TESTS
- **State**: `AVAILABLE` when repository or user test suites are discovered.
- **Objective**: Execute the codebase's existing acceptance tests and user-provided custom test archives in a zero-network sandbox.
- **Mechanism**: Automatically detects test runners (`pytest`, `unittest`). Executes discovered test files and supplemental user tests (`user_tests/`) inside isolated Docker containers.
- **Verdict Rule**: Any test failure triggers `REJECTED` / `BLOCK`. Test runner crashes produce `INDETERMINATE` / `REVIEW`. User test failures strictly veto `QUALIFIED`.

### Control C3: INDEPENDENT INVARIANTS
- **State**: `NOT_AVAILABLE` for arbitrary user project uploads unless independent invariant suites are explicitly supplied.
- **Objective**: Prevent AI overfitting to visible prompt assertions by evaluating boundary invariants (zero inputs, null values, empty collections).
- **Applicability**: Active in curated benchmarks and enterprise environments where decoupled evaluator suites exist. For standalone archive uploads without external checks, reported honestly as `NOT_AVAILABLE`.

### Control C4: REGRESSION
- **State**: `NOT_AVAILABLE` unless an actual Git baseline or repository history is provided.
- **Objective**: Guarantee backward compatibility and ensure preexisting callers and downstream APIs remain unbroken.
- **Applicability**: Requires Git history comparison (`base..head`). For standalone archive uploads where no baseline commit exists, reported honestly as `NOT_AVAILABLE`.

### Control C5: MUTATION RESILIENCE
- **State**: `NOT_SUPPORTED` for standalone archive uploads.
- **Objective**: Detect vacuous, hollow assertions that pass trivially without genuinely verifying behavior.
- **Applicability**: Uses AST mutation operators to invert relational conditions and calculate mutation kill scores. When not implemented for arbitrary archive uploads, reported honestly as `NOT_SUPPORTED`.

### Control C6: SECURITY ANALYSIS
- **State**: `AVAILABLE` when the security AST scanner runs.
- **Objective**: Block supply-chain vulnerabilities, path traversals, unsafe subprocess invocations, and hardcoded secrets.
- **Mechanism**: AST visitor traverses modified code to track taint flows from untrusted inputs into dangerous filesystem or OS sinks (CWE-22 path traversal, raw `os.system()`, `eval()`, unescaped subprocess commands, high-entropy credential tokens).
- **Verdict Rule**: Any security violation produces an immediate veto (`REJECTED` / `BLOCK`).

---

## 3. Sandboxing & Isolation Architecture

A.I.R.A. mandates containerized sandbox execution for untrusted AI-generated code:
- **Zero-Network Isolation**: Executed with `--network none` to prevent command-and-control exfiltration or credential leakage.
- **Resource Constraints**: Strict limits on CPU (`--cpus 1.0`), memory (`--memory 512m`), and thread/process forks (`--pids-limit 50`).
- **Privilege Dropping**: Hardened with `--security-opt no-new-privileges` and `--cap-drop ALL`.
- **Read-Only Root Filesystem**: Mounts the container rootfs as read-only, allocating temporary in-memory tmpfs partitions (`/tmp`, `/.pytest_cache`) for ephemeral test runs.

---

## 4. MLVerify Predictive Risk Modeling (Shadow Mode)

MLVerify is an empirical research component designed to predict defect likelihood before expensive testing begins:
- **Prediction Boundary**: Operates strictly at $t_{\text{prediction}}$ (the instant after agent code generation concludes, prior to running any test or oracle).
- **Current Operational Status**: Strictly **`SHADOW_MODE_ONLY`**.
- **Role**: Computes calibrated defect probabilities and logs counterfactual comparisons against actual gate verdicts. MLVerify does **not** bypass deterministic gates or autonomously decide release policies.

---

## 5. Tamper-Evident Release Audit Records

Every verification run produces a cryptographically referenced audit report:
- **Diff SHA-256**: Content-addressed hash of the exact unified diff evaluated.
- **Criteria Manifest**: Per-gate scores, statuses, and detailed failure diagnostics.
- **Telemetry**: Wall-clock execution durations and container isolation metadata.
- **Export Format**: Standardized JSON artifacts conformant with A.I.R.A. Release Schema v1.0.
