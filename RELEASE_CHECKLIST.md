# A.I.R.A. Public Release 1.0 — Verification & Quality Checklist

This checklist confirms that the repository, backend service, visual control plane, empirical research foundation, and security hardening satisfy all criteria for **A.I.R.A. (AI RELEASE ASSURANCE) PUBLIC RELEASE 1.0**.

---

## 1. Repository Sanitization & Hygiene

- [x] **No Internal Prompt Dumps**: All scratch directives and prompt files (`latest_user_prompt.txt`, `phase3_directive.txt`, `user_prompt_*.txt`) removed.
- [x] **Zero Secrets / API Keys**: Real API keys removed from `.env` and historical files. Only standard placeholders in `.env.example`.
- [x] **No Personal Identifier / Author Leakage**: Hardcoded personal usernames (`aryab`) replaced with `A.I.R.A. Core Team <maintainers@aira-verify.dev>` in `pyproject.toml` and documentation.
- [x] **No Local Windows Absolute Paths**: Absolute paths (`C:\Users\...`) replaced with clean relative or POSIX links.
- [x] **Zero Development-Time Claims**: Unsubstantiated claims of development duration ("built in 2 days", "completed in X hours") eliminated from all public materials.

---

## 2. Research State & Baseline Integrity

- [x] **Historical Baseline Frozen**: `empirical_100_local_v1` (100 real runs, 50 tasks, paired seeds 42 and 100) preserved completely intact.
- [x] **Phase 2 & 2.1 Preserved**: Audited empirical findings and research report preserved.
- [x] **Phase 3.1 Audit Honored**: Unverified Phase 3 multi-head claims quarantined; only the verified canary trace preserved in `empirical_mlverify_v2/`.
- [x] **MLVerify Operational Status**: Strictly designated as **`SHADOW_MODE_ONLY`**.
- [x] **No Autonomous Routing Claims**: Documentation explicitly rejects autonomous routing for production safety gating until large-scale multi-head expansion is collected.

---

## 3. Core Verification Pipeline (Gates C1 through C6)

- [x] **Gate C1 (Syntax & AST)**: Validates Python grammar and type annotations.
- [x] **Gate C2 (Visible Tests)**: Evaluates baseline functional prompt tests.
- [x] **Gate C3 (Hidden Invariants)**: Detects zero-division, boundary overflow, and AI overfitting.
- [x] **Gate C4 (Regression Suite)**: Catches breaking schema changes and signature regressions.
- [x] **Gate C5 (Mutation Score)**: Injects deterministic AST mutants; flags vacuous assertions.
- [x] **Gate C6 (Security AST & Taint)**: Blocks CWE-22 (path traversal), untrusted `eval`, and raw subprocess.

---

## 4. Curated Demo Scenarios (Zero-Dependency Safe Evaluation)

- [x] **Scenario 1**: Clean Correct Patch (`demo_01_clean_pass`) &rarr; `QUALIFIED` / `AUTO_APPROVE` (All C1..C6 pass).
- [x] **Scenario 2**: Hidden Invariant Failure (`demo_02_hidden_overfit`) &rarr; `REJECTED` / `BLOCK` (Passes C2, fails C3 zero-division).
- [x] **Scenario 3**: Security Boundary Violation (`demo_03_path_traversal`) &rarr; `REJECTED` / `BLOCK` (Passes tests, fails C6 CWE-22 path traversal).
- [x] **Scenario 4**: Backward Compatibility Regression (`demo_04_regression_break`) &rarr; `REJECTED` / `BLOCK` (Passes new tests, fails C4 legacy suite).
- [x] **Scenario 5**: Mutation-Resistant Semantic Defect (`demo_05_mutation_survivor`) &rarr; `REJECTED` / `REVIEW` (Passes tests, fails C5 mutation score < 0.50).

---

## 5. Web Console & Visual Control Plane

- [x] **Control Plane Dark Theme**: Ultra-dark canvas (`#09090B`) with subtle violet illumination and thin technical borders (`1px solid #1C1C24`).
- [x] **Interactive Change Graph**: Live 2D canvas network showing repo, changed files, modules, gates C1..C6, and evidence ledger with animated signal pulses and hover inspector.
- [x] **Live Pipeline Visualizer**: Sequential gate progression with animated status pills.
- [x] **Interactive Diff Editor**: Real-time unified diff input with file label and size counter.
- [x] **Streaming Terminal**: Formatted telemetry stream with millisecond timestamps and stage markers.
- [x] **Evidence & Audit Explorer**: Cryptographic SHA-256 evidence record inspection and JSON download.
- [x] **MLVerify Research View**: Full transparency displaying empirical metrics (PR-AUC 0.9367) and methodological boundaries.

---

## 6. Testing, CI/CD & Deployment

- [x] **Test Suite**: 343 passed, 0 failed, 4 skipped; 100% of executed tests passed (4 skipped tests are optional live cloud-model provider tests requiring external credentials).
- [x] **Public API Tests**: Complete coverage for `/health`, `/api/verifications`, `/api/demo/scenarios`, and web assets.
- [x] **GitHub Actions CI**: Automated lint, test, security, and build checks in `.github/workflows/ci.yml`.
- [x] **Docker Support**: Unified service `Dockerfile` and `docker-compose.yml` configured for deployment with `/var/run/docker.sock` volume mount for containerized sandbox orchestration.
