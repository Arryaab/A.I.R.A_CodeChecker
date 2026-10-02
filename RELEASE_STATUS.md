# A.I.R.A. Release Status Report

**Release Candidate**: `v1.0.0-rc1`
**System**: A.I.R.A. (AI Release Assurance Platform)
**Evaluation Date**: 2026-10-02
**Security Posture**: Fail-Closed Hardened

---

## 1. Status Matrix

### `PRODUCT_STATUS`
- **Current State**: `RELEASE_CANDIDATE_READY`
- **Expansion**: AI Release Assurance (A.I.R.A.)
- **Core Purpose**: Verify AI-generated software modifications before production release and produce auditable, cryptographically signed evidence records.
- **Explicit Non-Claims**:
  - NOT a generic AI coding assistant (A.I.R.A. does not autocomplete or author software).
  - NOT an AI code generator.
  - NOT a simulated/fake QA dashboard (zero result fabrication; unexecutable runs fail closed).
  - NOT an absolute guarantee of bug-free software (strictly bounded by declared test scopes and invariant definitions).
  - NOT an unmonitored autonomous release router (assigns policy classes: `AUTO_APPROVE`, `REVIEW`, `BLOCK`).
- **MLVerify Status**: `SHADOW_MODE_ONLY` (Strict research/telemetry diagnostic; never bypasses deterministic release gates).

### `BACKEND_STATUS`
- **Current State**: `PRODUCTION_READY`
- **Service Engine**: FastAPI asynchronous control plane (`aegis.api.service:app`).
- **API Surface**:
  - `POST /api/projects/upload`: Validated archive upload & safe extraction.
  - `GET /api/projects/{project_id}`: Project inspection and test discovery inventory.
  - `POST /api/projects/{project_id}/tests`: Dedicated user custom test injection.
  - `POST /api/projects/{project_id}/verify`: Hardened sandbox verification job dispatcher.
  - `DELETE /api/projects/{project_id}`: Safe ephemeral cleanup.
  - `GET /api/verifications/{run_id}`: Verification state machine and verdict evaluation.
  - `GET /api/verifications/{run_id}/events`: SSE telemetry event stream.
  - `GET /api/verifications/{run_id}/evidence`: Cryptographic SHA-256 evidence package.
  - `GET /api/demo/scenarios`: Isolated pre-recorded benchmark traces.
- **Fail-Closed Execution**: If Docker is unavailable, verification requests immediately return HTTP 503 (`SANDBOX_UNAVAILABLE`). No results are fabricated.

### `FRONTEND_STATUS`
- **Current State**: `PRODUCTION_READY`
- **Visual Aesthetic**: Minimal cinematic developer control plane (deep neutral carbon palette, zero purple wash, zero blue wash, high typographic contrast).
- **Architecture**: Single Page Application (SPA) with native browser pushState routing (`/`, `/verify`, `/demo`).
- **Primary Navigation**:
  - Links: `PRODUCT`, `VERIFY`, `DEMO`, `EVIDENCE`, `RESEARCH`.
  - Primary Action: `VERIFY MY CODE →`.
  - Secondary Action: `EXPLORE DEMO`.
- **Workflow Isolation**: The user upload wizard and pre-recorded demo workbench are fully separated into dedicated components and routes.

### `USER_UPLOAD_STATUS`
- **Current State**: `PRODUCTION_READY`
- **Supported Formats**: `.zip`, `.tar.gz`, `.tgz`.
- **Decompression Safety Jail**:
  - Max archive upload size: 50 MB.
  - Max uncompressed size: 200 MB.
  - Max single file size: 25 MB.
  - Max file count: 5,000 files.
  - Max path length: 256 characters.
  - Rejection of path traversals (`../`), root escapes (`/`), symlinks, hardlinks, and device nodes.
  - Automatic blocking of sensitive files (`.env`, `*.pem`, `*.key`, `id_rsa`).
- **Test Framework Detection**:
  - Detects `pytest` via `pytest.ini`, `pyproject.toml`, `setup.cfg`, `tox.ini`, `requirements.txt`, or standard test files (`test_*.py`, `*_test.py`).
  - Detects `unittest` via `unittest.TestCase` and `import unittest`.
  - Unrecognized project structures return `UNSUPPORTED_PROJECT` with C2 marked `NOT_SUPPORTED`.

### `CUSTOM_TEST_STATUS`
- **Current State**: `PRODUCTION_READY`
- **Custom Suite Upload**: Users can provide supplementary or independent tests via `POST /api/projects/{project_id}/tests`.
- **Inventory Tracking**: Project tests (`project_tests`) and custom user tests (`user_tests`) are tracked as distinct inventories in the evidence model.
- **Verdict Impact**:
  - Any user test failure strictly forces `REJECTED` / `BLOCK`.
  - An error during custom test execution forces `INDETERMINATE` / `REVIEW`.
  - Under no circumstances can a run with failing custom tests receive `QUALIFIED` or `AUTO_APPROVE`.

### `SANDBOX_STATUS`
- **Current State**: `PRODUCTION_READY`
- **Execution Mechanism**: Ephemeral Docker containers launched with explicit parameters:
  - `use_docker=True`
  - `require_sandbox=True`
- **Hardened Jail Configuration**:
  - `--network none` (Zero inbound or outbound network connectivity).
  - `--read-only` (Immutable container root filesystem).
  - `--tmpfs /tmp:rw,noexec,nosuid,size=64m`
  - `--tmpfs /workspace/.pytest_cache:rw,noexec,nosuid,size=32m`
  - `--cap-drop ALL` (All Linux capabilities dropped).
  - `--security-opt no-new-privileges`
  - `--cpus 1.0`
  - `--memory 512m`
  - `--pids-limit 50`
  - `--ulimit nofile=1024:2048`
  - `--ulimit fsize=50000000` (Max 50MB output size).
- **Host Execution Elimination**: Untrusted user code is completely prohibited from running on the host machine.

### `SECURITY_STATUS`
- **Current State**: `PRODUCTION_READY`
- **Authentication**: Enforced on all upload, execution, and evidence routes via `X-API-Key` (configured via `AIRA_API_KEY` with fallback to `AEGIS_API_KEY`).
- **Rate Limiting**: Rolling window limiter guarding against upload/verification floods (`AIRA_RATE_LIMIT=30`, `AIRA_RATE_LIMIT_WINDOW=60`).
- **CORS Configuration**: Configured via `AIRA_CORS_ORIGINS`. Automatically sets `allow_credentials=False` if wildcard `*` is specified.
- **Static AST Security Scanner (C6)**: Scans Python AST for CWE-22 (path traversal), arbitrary command injection (`os.system`, `subprocess(shell=True)`), and exposed credentials.
- **Hygiene & Secrets Audit**: Clean. Zero hardcoded personal filesystem paths, usernames, or live API keys in the repository.

### `DEMO_SEPARATION_STATUS`
- **Current State**: `PRODUCTION_READY`
- **Strict Partitioning**: User verification (`/verify`) and curated demonstrations (`/demo`) share zero UI rendering components, state trees, or result containers.
- **Visual Demarcation**: Educational demo scenarios are labeled with explicit `[DEMO TRACE]` markers and separated by a high-contrast physical divider.

### `EVIDENCE_STATUS`
- **Current State**: `PRODUCTION_READY`
- **Audit Ledger**: Every verification run generates a downloadable, content-addressed JSON evidence package (`GET /api/verifications/{run_id}/evidence`).
- **Truthful Capability Reporting**:
  - C1 (Syntax AST): `AVAILABLE`
  - C2 (Visible / User Tests): `AVAILABLE` (if test suite is detected)
  - C3 (Hidden Invariants): `NOT_AVAILABLE` (Oracle invariant harness required)
  - C4 (Regression Diff): `NOT_AVAILABLE` (Git baseline history required)
  - C5 (Mutation Testing): `NOT_SUPPORTED` (Archive uploads)
  - C6 (AST Security): `AVAILABLE`
- **Sanitized Exposure**: Reports contain relative file paths, test inventory counts, and failure traces, with zero host filesystem paths or secret leaks.

### `DOCUMENTATION_STATUS`
- **Current State**: `PRODUCTION_READY`
- **`README.md`**: Complete overview including product definition, explicit non-claims, 6 verification controls, sandbox jail parameters, REST API documentation, and getting started steps.
- **`docs/ARCHITECTURE.md`**: Up-to-date system architecture detailing the capability model, verification stages, and truthful state transitions.
- **`docs/DEPLOYMENT.md`**: Production deployment guide covering Docker Compose, Nginx SSL reverse proxy, and operational configuration.
- **`.env.example`**: Complete template featuring all `AIRA_*` configuration variables.
- **Hygiene**: Developmental duration text ("2 days", "hours spent") removed.

### `DEPLOYMENT_STATUS`
- **Current State**: `DEPLOYMENT_READY`
- **Local Service**: Active and responsive at `http://127.0.0.1:8000`.
- **Containers**:
  - `docker-compose.yml` configured for service `aira-platform`, image `aira-platform:1.0.0`, container `aira_platform`.
  - Docker daemon socket mounted to allow sandbox container orchestration.
  - Hardened runner image builder (`Dockerfile.sandbox`).
- **Production Status Note**: Container deployment configurations are verified and ready for cloud deployment; live production cloud rollout has not been performed as external cloud credentials were not provided.

### `TEST_STATUS`
- **Current State**: `ALL_TESTS_PASSING`
- **Full Verification Suite**: **343 PASSED, 4 SKIPPED, 0 FAILED** (100% pass rate across 347 collected test cases in 45 files).
  - Skipped tests (4) correspond to remote live cloud API provider calls that skip gracefully when live credentials are not exported.
- **Sub-Suite Verification Highlights**:
  - Real Fixtures & Repository Test Accounting (`tests/test_real_fixtures_and_repo_accounting.py`): **19 PASSED**
  - Test Integrity & Regression Suite (`tests/test_test_integrity.py`): **15 PASSED**
  - Project Upload & Verification Suite (`tests/test_project_upload.py`): **26 PASSED**
  - Frontend Authentication & Security (`tests/test_frontend_auth.py`): **17 PASSED**
  - Frontend Separation & Isolation (`tests/test_frontend_separation.py`): **10 PASSED**
  - Git Integration & Snapshot Integrity (`tests/test_git.py`): **10 PASSED**
  - Public API & Demo Integrity (`tests/test_public_api_and_demo.py`): **9 PASSED**
  - Benchmark Immutability Gate (`tests/test_benchmark_immutability.py`): **1 PASSED** (Cryptographic lock verified)
  - Benchmark Anti-Leakage & Traversal (`tests/test_benchmark_anti_leakage.py`): **2 PASSED**
  - Environment Reproducibility & Provenance (`tests/test_evaluation.py`): **7 PASSED**
  - Sandbox Jail Security Suite (`tests/test_sandbox.py`): **4 PASSED**
  - Sandbox Availability & Doctor Diagnostics (`tests/test_sandbox_availability.py`): **17 PASSED**
  - AST Security Scanner Guardrails (`tests/test_security.py`): **4 PASSED**

### `ACCEPTANCE_TEST_EVIDENCE`
- **Calculator Project Acceptance (`aira_test_project.zip`)**:
  - Discovered tests: **3** (`test_add`, `test_divide`, `test_divide_by_zero`)
  - Selected tests: **3**
  - Executed tests: **3**
  - Passed tests: **2**
  - Failed tests: **1** (`test_divide_by_zero`)
  - Control C2: **FAIL**
  - Technical Verdict: **REJECTED**
  - Release Policy: **BLOCK**
- **Security Project Acceptance (`aira_security_test_project.zip`)**:
  - Discovered tests: **2** (`test_normal_filename`, `test_nested_filename`)
  - Selected tests: **2**
  - Executed tests: **2**
  - Passed tests: **2**
  - Failed tests: **0**
  - Control C2: **PASS**
  - Control C6 (AST Security Guardrails): **FAIL** (CWE-22 Path Traversal vulnerability detected in application code `archive_utils.py`)
  - Technical Verdict: **REJECTED**
  - Release Policy: **BLOCK**

---

## 2. Summary of Changes Implemented

1. **Hard Sandbox Guarantee**:
   - Enforced `use_docker=True` and `require_sandbox=True` on all project execution entry points.
   - Eliminated all host execution fallbacks for user-submitted code.
   - Implemented fail-closed behavior returning HTTP 503 (`SANDBOX_UNAVAILABLE`) when Docker daemon is not running.

2. **Custom Test Integration & Verdict Engine**:
   - Added `POST /api/projects/{project_id}/tests` for supplementary test upload.
   - Enforced rule: Any custom test failure immediately vetoes `QUALIFIED` status and yields `REJECTED` / `BLOCK`.
   - Distinctly inventoried project tests and user tests in the evidence model.

3. **Truthful Verification Capability Model**:
   - Distinguished stage statuses: `AVAILABLE`, `RUNNING`, `PASS`, `FAIL`, `ERROR`, `SKIPPED`, `NOT_AVAILABLE`, `NOT_SUPPORTED`.
   - Properly marked C3 (Hidden Invariants) and C4 (Regression) as `NOT_AVAILABLE` for user archive uploads lacking oracle harnesses or git history.
   - Properly marked C5 (Mutation) as `NOT_SUPPORTED` for raw user archives.
   - Prohibited treating `NOT_AVAILABLE` or `NOT_SUPPORTED` as fake passes.

4. **Complete Frontend & UI Separation**:
   - Separated the real user verification workflow (`/verify`) from the educational pre-recorded demo workbench (`/demo`).
   - Cleaned the hero section of simulated demo stats, replacing it with an authentic 6-control architecture framework.
   - Updated primary navigation (`Product`, `Verify`, `Demo`, `Evidence`, `Research`) and dual CTAs (`VERIFY MY CODE`, `EXPLORE DEMO`).
   - Added physical visual partition between real verification and pre-recorded demo areas.

5. **API Security, Rate Limiting & CORS**:
   - Guarded all upload, verification, and evidence routes with `X-API-Key` authentication.
   - Added in-process rolling rate limiting (`AIRA_RATE_LIMIT`, `AIRA_RATE_LIMIT_WINDOW`).
   - Configured CORS origins with safe wildcard handling (`allow_credentials=False` on `*`).

6. **Repository Hygiene & Brand Consistency**:
   - Updated product naming to **A.I.R.A.** across frontend, backend metadata, documentation, and configuration.
   - Sanitized personal paths, usernames, and development duration strings.
   - Synchronized `pyproject.toml` author metadata and regenerated evidence inventory checksums.

7. **Deployment & Operations**:
   - Configured `docker-compose.yml` with `aira-platform:1.0.0` and container `aira_platform`.
   - Updated `.env.example` with comprehensive `AIRA_*` variables.
   - Documented production deployment and Nginx reverse proxy in `docs/DEPLOYMENT.md`.

8. **Python Packaging & Container Verification**:
   - `pyproject.toml` configured with console entrypoints `aira` and `aegis` mapped to `aegis.cli:main`.
   - Optional dependency extras `[web]`, `[sandbox]`, `[dev]`, and `[all]` hardened with `pydantic>=2.0.0` and `python-multipart>=0.0.6`.
   - Verified clean sdist and wheel generation (`aegis_lite-1.0.0.tar.gz` and `aegis_lite-1.0.0-py3-none-any.whl`) via `python -m build`.
   - Built production container image `aira-platform:latest` from scratch running as non-root user `aira`, verified passing container health probe at `/api/health`.

---

## 3. Verification & Evidence

- **Unit & Security Tests**: Verified archive decompression defense against relative traversal (`../`), absolute paths (`/`), symlinks, and zip bombs.
- **Provider & Preflight Tests**: Verified Ollama local digest mismatch fails closed deterministically.
- **Evidence Audit**: Re-audited empirical dataset hashes, verifying mathematical fidelity and claim gate integrity.
- **HTTP Smoke Tests**: Verified that `/`, `/verify`, `/demo`, and `/health` respond with HTTP 200.

---

## 4. Remaining Blockers

- **None**: All release gates for Release Candidate 1 are satisfied.
- **Operational Requirement**: A running Docker daemon is required on the host system to verify user code in non-demo mode. If Docker is offline, the system behaves safely and truthfully by failing closed.

---

## 5. Startup & Deployment Commands

### Local Development Startup
```bash
# 1. Install dependencies with web & testing extras
pip install -e ".[all]"

# 2. Build sandbox runner image (requires Docker)
docker build -t aegis-sandbox:latest -f Dockerfile.sandbox .

# 3. Launch A.I.R.A. service and visual control plane
uvicorn aegis.api.service:app --host 0.0.0.0 --port 8000
```
Access the application at `http://localhost:8000`.

### Production Deployment (Docker Compose)
```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your AIRA_API_KEY and configuration

# 2. Build and launch platform
docker compose up -d

# 3. Check service health
curl -f http://localhost:8000/api/health
```
