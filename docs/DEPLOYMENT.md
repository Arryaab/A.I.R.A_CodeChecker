# A.I.R.A. Deployment & Operations Guide

This guide covers deploying the **A.I.R.A. (AI Release Assurance)** service in production or staging environments.

---

## 1. Quick Local Execution

### Option A: Direct Python Installation
```bash
# Clone the repository
git clone https://github.com/aira-platform/aira.git
cd aira

# Inspect and checkout release tag
git show v1.0.0 --summary
git rev-parse v1.0.0
git checkout v1.0.0

# Install package and dependencies
pip install -e ".[all]"

# Build the sandbox runner image on host (required for real verification)
docker build -t aegis-sandbox:latest -f Dockerfile.sandbox .

# Launch API and visual control plane
uvicorn aegis.api.service:app --host 0.0.0.0 --port 8000
```
Open your browser at `http://localhost:8000`.

### Option B: Docker Compose (Unified Service)
```bash
# 1. Build the sandbox runner image on the host Docker daemon
docker build -t aegis-sandbox:latest -f Dockerfile.sandbox .

# 2. Launch unified service via Docker Compose (mounts /var/run/docker.sock)
docker compose up -d
```
The control plane dashboard and REST API will be accessible at `http://localhost:8000`.

---

## 2. Configuration & Environment Variables

| Variable | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `AIRA_API_KEY` | string | `""` (empty) | Primary API key required for authenticated verification, upload, and evidence endpoints. |
| `AEGIS_API_KEY` | string | `""` (empty) | Fallback backwards-compatibility alias for `AIRA_API_KEY`. |
| `AIRA_CORS_ORIGINS` | string | `"http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000"` | Comma-separated allowed origins. Note: When set to `*`, credentials are automatically disabled for security. |
| `AIRA_RATE_LIMIT` | integer | `30` | Rolling rate limit: maximum requests per window for project upload and verification endpoints. |
| `AIRA_RATE_LIMIT_WINDOW` | integer | `60` | Rolling rate limit window duration in seconds. |
| `DEMO_MODE` | boolean | `false` | When `true`, enables safe scenario exploration without requiring a live Docker daemon. In production, set to `false`. |
| `HOST` | string | `0.0.0.0` | Network binding address. |
| `PORT` | integer | `8000` | Port for the HTTP server. |
| `DOCKER_SANDBOX_IMAGE` | string | `aegis-sandbox:latest` | Docker image tag used for isolating sandboxed test runs. |
| `OLLAMA_BASE_URL`| string | `http://localhost:11434` | Endpoint for local model execution during benchmark generation (SHADOW_MODE_ONLY). |
| `OPENAI_API_KEY` | string | `""` | Optional key for cloud provider experiments. |
| `GEMINI_API_KEY` | string | `""` | Optional key for cloud provider experiments. |

---

## 3. Sandboxing & Docker Daemon Requirements

In production (`DEMO_MODE=false`), A.I.R.A. mandates a running Docker daemon to enforce zero-network container isolation during code execution.

### Fail-Closed Principle
Untrusted user projects and patches are **never** executed directly on the host machine. If Docker is unavailable:
- Verification requests (`POST /api/projects/{id}/verify`) immediately return `HTTP 503 Service Unavailable` (`SANDBOX_UNAVAILABLE`).
- Results are **never fabricated** or simulated when real execution fails or cannot be scheduled.

### Control-Plane Container Health vs. End-to-End Sandbox Execution
It is critical to distinguish between control-plane container health and full sandbox execution readiness:

- **Control-Plane Health**: Running `docker run -p 8000:8000 aira-platform:release` starts the FastAPI backend and serves the frontend dashboard. Probing `/api/health` returns HTTP 200 with `status: "healthy"`. However, if the container does not have access to the host's Docker socket, the health payload reports:
  ```json
  "docker_available": false,
  "sandbox_available": false,
  "sandbox_health": "DOCKER_CLI_MISSING"
  ```
  This indicates that while the control-plane container itself is functioning, it cannot spawn execution sandboxes. In this state, any request to verify untrusted code (`POST /api/projects/{id}/verify`) will safely **fail closed** with `HTTP 503 Service Unavailable`.
- **Full Sandbox Execution**: To enable sandboxed verification in container deployments:
  1. Mount the host Docker socket into the control-plane container: `-v /var/run/docker.sock:/var/run/docker.sock` (configured by default in `docker-compose.yml`).
  2. Pre-build the sandbox runner image on the host daemon: `docker build -t aegis-sandbox:latest -f Dockerfile.sandbox .`.
  3. Ensure the running user in the container has permissions to communicate with the Docker socket.

A control-plane container smoke test confirms that the application starts and serves requests; it does not substitute for configuring host sandbox socket access.

### Building the Sandbox Image
Before launching full verification in non-demo mode, build the hardened sandbox container:
```bash
docker build -t aegis-sandbox:latest -f Dockerfile.sandbox .
```

### Production Sandbox Security Jail
When evaluating untrusted AI code changes, A.I.R.A. automatically launches containers with:
- `--network none` (Zero internet access)
- `--read-only` (Immutable root filesystem)
- `--tmpfs /tmp:rw,noexec,nosuid,size=64m`
- `--tmpfs /workspace/.pytest_cache:rw,noexec,nosuid,size=32m`
- `--ulimit nofile=1024:2048`
- `--ulimit fsize=50000000` (Max output file size 50MB)
- `--security-opt no-new-privileges`
- `--cap-drop ALL`
- `--cpus 1.0`
- `--memory 512m`
- `--pids-limit 50`

### Archive Upload Safety Limits
User-submitted project and test archives (`.zip`, `.tar.gz`, `.tgz`) are strictly validated prior to extraction:
- Maximum upload archive size: **50 MB**
- Maximum total uncompressed size: **200 MB**
- Maximum single file uncompressed size: **25 MB**
- Maximum file count: **5,000 files**
- Maximum path length: **256 characters**
- Absolute paths (`/`) and directory traversals (`..`) are rejected.
- Symlinks, hardlinks, and device special files are rejected.
- Sensitive credential files (`.env`, `.pem`, `.key`, `id_rsa`) are rejected.

---

## 4. Production Reverse Proxy (Nginx)

For production deployments behind Nginx with SSL:

```nginx
server {
    listen 443 ssl http2;
    server_name assurance.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/assurance.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/assurance.yourdomain.com/privkey.pem;

    client_max_body_size 55M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 5. Health & Liveness Checks

Automated orchestrators (Kubernetes, AWS ECS, Nomad) can probe:
- **Liveness Probe**: `GET /health` (Returns HTTP 200 with service version and engine status).
- **Readiness Probe**: `GET /api/health` (Reports detailed system diagnostics):
  - `status`: `"healthy"` confirms the control-plane application is active.
  - `docker_available`: Boolean indicating whether Docker CLI tools are present.
  - `sandbox_available`: Boolean indicating whether the sandbox daemon is reachable.
  - `sandbox_health`: Detailed status string (`HEALTHY`, `DOCKER_CLI_MISSING`, `DAEMON_UNREACHABLE`, `IMAGE_MISSING`).

Operators should configure readiness gates based on operational requirements: a node serving only static demo walkthroughs requires only `status: "healthy"`, while a worker processing live code verifications requires `sandbox_available: true`.

---

## 6. Authentication & Credential Architecture

A.I.R.A. enforces strict client-server separation for credentials:

### Production Deployments
- **Zero Frontend Credentials**: The production frontend bundle never ships with the server API key.
- **Client-Provided Credential**: The browser supplies a user-provided API credential via the `API ACCESS` interface in the header.
- **Session-Only Storage**: The credential is held strictly in `sessionStorage` and is never written to `localStorage`, cookies, analytics, or disk. It is automatically purged when the user's browser session ends.
- **Server Configuration**: Configure `AIRA_API_KEY=<server-configured-key>` in the backend environment. All live verification and project upload endpoints reject unauthorized requests with `HTTP 401 Unauthorized`.
- **Public Demo Routes**: Pre-recorded educational demo walkthroughs (`/api/demo/*`) remain public and require no API key.

### Local Development Mode
- For local testing on `localhost` / `127.0.0.1`, set `AIRA_LOCAL_DEV_AUTH=true`.
- The backend automatically initializes a development token on startup and provides it to localhost clients via `GET /api/auth/local-dev-token`.
- Non-localhost and remote hosts are strictly forbidden (`HTTP 403 Forbidden`).
