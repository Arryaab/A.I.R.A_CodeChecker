# A.I.R.A. — AI Release Assurance

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/release-v1.0.0-brightgreen)](https://github.com/aira-platform/aira)
[![Execution Isolation](https://img.shields.io/badge/sandbox-Docker%20Jail-blue)](docs/DEPLOYMENT.md)
[![MLVerify](https://img.shields.io/badge/MLVerify-Shadow%20Mode%20Only-orange)](docs/ARCHITECTURE.md)

> **"Verify what AI changes. Know what ships."**

**A.I.R.A. (AI Release Assurance)** is an enterprise control plane engineered to verify AI-generated software changes before production release and generate auditable, evidence-backed release decisions.

---

## ⚠️ Product Definition & Explicit Non-Claims

To ensure complete engineering transparency, A.I.R.A. defines clear functional boundaries:

- **A.I.R.A. is:** A fail-closed, multi-stage verification control plane that executes and tests software modifications inside hardened, zero-network sandboxes to determine whether changes are safe to merge.
- **A.I.R.A. is NOT a generic AI coding assistant:** It does not chat, autocomplete code, or act as an IDE companion.
- **A.I.R.A. is NOT an AI code generator:** It does not write application code; it audits, tests, and evaluates untrusted proposed code.
- **A.I.R.A. is NOT a fake automated QA dashboard:** Every verification verdict reflects real sandboxed execution. When container sandboxes are unavailable, it fails closed rather than fabricating results.
- **A.I.R.A. is NOT a guarantee of bug-free software:** Verification is strictly bounded by the declared test suites, static analyzers, and invariant checks.
- **A.I.R.A. is NOT an autonomous release router:** A.I.R.A. categorizes risk into clear policy buckets (`AUTO_APPROVE`, `REVIEW`, `BLOCK`) with cryptographic evidence trails, leaving release policy governance in engineering hands.

---

## 🛡️ The Two Workflows: Hard System Separation

A.I.R.A. provides two strictly separated operating modes:

```
┌──────────────────────────────────────────────┐     ┌──────────────────────────────────────────────┐
│            1. VERIFY MY CODE                 │     │              2. EXPLORE DEMO                 │
│         (Real Untrusted Execution)           │     │            (Curated Scenarios)               │
├──────────────────────────────────────────────┤     ├──────────────────────────────────────────────┤
│ • Upload user project archive (.zip, .tar.gz)│     │ • Curated pre-recorded benchmark traces      │
│ • Detect test suite (pytest, unittest)       │     │ • Demonstrates 5 classic AI failure modes    │
│ • Upload optional user-provided tests        │     │ • Zero Docker / API prerequisites required   │
│ • Hardened Docker sandbox jail execution     │     │ • Labeled explicitly with [DEMO TRACE] tags  │
│ • Real pass/fail evidence & auditable limits │     │ • Never shares UI components or state with   │
│ • Fails closed (503) if Docker unavailable   │     │   user project verification                  │
└──────────────────────────────────────────────┘     └──────────────────────────────────────────────┘
```

---

## 🏛️ Verification Architecture: The 6 Controls

A.I.R.A. evaluates code changes using six verification controls when applicable:

| Control ID | Name | Method | Capability State in User Uploads | Policy Impact on Failure |
| :---: | :--- | :--- | :---: | :---: |
| **C1** | **Syntax & AST Integrity** | AST parsing across all project Python source files | `AVAILABLE` | `REJECTED` / `BLOCK` |
| **C2** | **Project Test Suite** | Sandboxed execution of detected project tests (`pytest` / `unittest`) | `AVAILABLE` (if tests exist) | `REJECTED` / `BLOCK` |
| **C3** | **Hidden Invariants** | Unseen property tests evaluated against edge cases | `NOT_AVAILABLE` (Oracle harness required) | `REJECTED` / `BLOCK` |
| **C4** | **Regression Suite** | Base commit comparison to detect caller breakage | `NOT_AVAILABLE` (Git history required) | `REJECTED` / `BLOCK` |
| **C5** | **Mutation Resistance** | Deterministic mutant injection to detect vacuous tests | `NOT_SUPPORTED` (Archive uploads) | `REJECTED` / `REVIEW` |
| **C6** | **Security AST Guardrails** | AST & token scan for CWE-22 (path traversal), command injection, and leaked secrets | `AVAILABLE` | `REJECTED` / `BLOCK` |

> [!NOTE]
> **Strict Capability Model**: Controls that cannot be evaluated for an uploaded archive (such as hidden invariants C3 or historical regression C4) are explicitly recorded as `NOT_AVAILABLE` with documented evidence limitations. They are **never collapsed into a false `PASS`**.

---

## 🔒 Hardened Sandbox Security Jail

Untrusted code submitted to A.I.R.A. is **never** executed directly on the host operating system. All execution takes place within an ephemeral, locked-down Docker container with defense-in-depth security policies:

- **Zero Network Access**: `--network none` prohibits all egress, ingress, and socket listening.
- **Immutable Root Filesystem**: `--read-only` enforces complete filesystem immutability.
- **Restricted Ephemeral Memory Mounts**:
  - `/tmp:rw,noexec,nosuid,size=64m`
  - `/workspace/.pytest_cache:rw,noexec,nosuid,size=32m`
- **Dropped Linux Capabilities**: `--cap-drop ALL` strips all root privileges.
- **Privilege Escalation Prevention**: `--security-opt no-new-privileges`.
- **Resource Constraints**:
  - CPU allocation: `--cpus 1.0`
  - Memory limit: `--memory 512m`
  - Process limit: `--pids-limit 50`
  - File descriptor limit: `--ulimit nofile=1024:2048`
  - Maximum output file size: `--ulimit fsize=50000000` (50 MB)
- **Archive Upload Guardrails**:
  - Maximum upload archive size: **50 MB**
  - Maximum uncompressed extraction size: **200 MB**
  - Maximum file count: **5,000 files**
  - Maximum individual file size: **25 MB**
  - Path traversal (`../`), absolute paths (`/`), symlinks, and sensitive files (`.env`, `*.pem`, `*.key`) are rejected immediately prior to extraction.

---

## 🔬 MLVerify: Pre-Verification Risk Modeling (`SHADOW_MODE_ONLY`)

MLVerify is an internal research component investigating whether machine learning models can predict code defect likelihood prior to expensive test suite execution.

- **Status**: `SHADOW_MODE_ONLY` (Evaluated for diagnostic analysis; never alters release decisions or bypasses deterministic verification gates).
- **Baseline Foundation**: Evaluated on 100 complete executions (`empirical_100_local_v1`) across 50 software tasks using local model instances ($0 cloud cost).
- **Performance**: Random Forest PR-AUC of 0.9367 ($[0.8814, 0.9782]$ 95% Bootstrap CI).
- **Scientific Boundary**: False accept events (passing visible tests while violating hidden invariants) were exceedingly rare (3 out of 100). Claiming automated gating based on this cohort is methodologically unsupported.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- Docker Engine (mandatory for real code verification; optional for exploring static demos)

### 2. Local Installation
```bash
git clone https://github.com/aira-platform/aira.git
cd aira

# Inspect and verify release tag
git show v1.0.0 --summary
git rev-parse v1.0.0
git checkout v1.0.0

pip install -e ".[all]"
```

### 3. Launching A.I.R.A. Locally
```bash
# Build sandbox runner image (required for real verification)
docker build -t aegis-sandbox:latest -f Dockerfile.sandbox .

# Start the A.I.R.A. control plane
uvicorn aegis.api.service:app --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000`** in your browser.

### 4. Running with Docker Compose
```bash
# 1. Build the sandbox runner image on host Docker daemon
docker build -t aegis-sandbox:latest -f Dockerfile.sandbox .

# 2. Launch platform with Docker socket mounted for sandbox orchestration
docker compose up -d
```

> [!IMPORTANT]
> **Control-Plane vs. Sandbox Health**:
> When running the control-plane container (e.g. via `docker run` or `docker compose`), `/api/health` returning HTTP 200 confirms that the control-plane API and web application are healthy.
> However, full end-to-end sandbox execution requires that the container can access the host Docker daemon (via the `/var/run/docker.sock` volume mount configured in `docker compose`) and that `aegis-sandbox:latest` is built. A plain standalone `docker run` without socket mounting confirms control-plane health only; verification requests will safely fail closed (HTTP 503 `SANDBOX_UNAVAILABLE`) until the sandbox daemon connection is configured.

---

## 🌐 Public REST API

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health, version, and sandbox mode. |
| `POST` | `/api/projects/upload` | Uploads a `.zip` or `.tar.gz` project archive for inspection. |
| `GET` | `/api/projects/{id}` | Inspects uploaded project metadata and detected test framework. |
| `POST` | `/api/projects/{id}/tests` | Uploads optional custom/additional test files for verification. |
| `POST` | `/api/projects/{id}/verify` | Triggers sandboxed project verification (returns `503` if Docker is offline). |
| `DELETE`| `/api/projects/{id}` | Purges extracted project files and memory entries. |
| `GET` | `/api/verifications/{id}` | Retrieves execution status, verdict, and release policy. |
| `GET` | `/api/verifications/{id}/events` | Streams real-time telemetry events. |
| `GET` | `/api/verifications/{id}/evidence`| Downloads verifiable SHA-256 evidence record. |
| `GET` | `/api/demo/scenarios` | Lists curated educational demonstration scenarios. |
| `GET` | `/api/demo/scenarios/{id}` | Retrieves scenario details and diff. |
| `POST` | `/api/demo/verify` | Runs or replays a curated demonstration scenario. |

---

## 🧪 Running the Verification Test Suite

Run the complete test suite:
```bash
python -m pytest tests/ -v
```

Authoritative test suite result: **343 passed, 0 failed, 4 skipped; 100% of executed tests passed.**
*(The 4 skipped tests are optional live cloud-model provider tests requiring external credentials.)*

---

## 📄 License & Contact

Released under the [MIT License](LICENSE). Maintained by the **A.I.R.A. Core Team** (`maintainers@aira-verify.dev`).
