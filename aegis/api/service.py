from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Security, Depends, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from aegis.execution.sandbox import (
    is_docker_available,
    check_sandbox_health,
    build_sandbox_image_with_output,
    print_sandbox_startup_banner,
)
from aegis.api.demo_data import DEMO_SCENARIOS, build_scenario_report

import hashlib
import shutil
from fastapi import UploadFile, File
from aegis.uploads.archive import extract_archive, secure_cleanup, ExtractionResult
from aegis.uploads.detection import detect_framework, FrameworkDetection
from aegis.uploads.models import ProjectInfo, ProjectVerifyRequest, VerificationEvidence, StageStatus

logger = logging.getLogger(__name__)

# Web static assets directory
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(
    title="A.I.R.A. — AI Release Assurance Platform",
    version="1.0.0",
    description="A.I.R.A. (AI Release Assurance): Production REST API for autonomous AI code change verification, security scanning, and policy gating."
)

def create_app() -> FastAPI:
    return app

# Configure production-safe CORS without wildcard credentials
cors_origins_env = os.environ.get("AIRA_CORS_ORIGINS", "").strip()
if cors_origins_env:
    allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
else:
    allowed_origins = ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:3000"]

# Security: Never combine allow_credentials=True with unrestricted wildcard origin
allow_credentials = "*" not in allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup() -> None:
    print_sandbox_startup_banner()

class RollingRateLimiter:
    """In-process rolling window rate limiter to protect upload and verification endpoints."""
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = int(os.environ.get("AIRA_RATE_LIMIT", str(max_requests)))
        self.window_seconds = int(os.environ.get("AIRA_RATE_LIMIT_WINDOW", str(window_seconds)))
        self.history: Dict[str, List[float]] = {}
        self.lock = threading.Lock()

    def enforce(self, key: str) -> None:
        now = time.time()
        with self.lock:
            timestamps = self.history.get(key, [])
            cutoff = now - self.window_seconds
            valid = [t for t in timestamps if t > cutoff]
            if len(valid) >= self.max_requests:
                self.history[key] = valid
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Maximum verification and upload submissions per window reached."
                )
            valid.append(now)
            self.history[key] = valid

rate_limiter = RollingRateLimiter()

def is_demo_mode() -> bool:
    """Returns True if running in demo mode or if Docker is unavailable in local dev."""
    val = os.environ.get("DEMO_MODE", "true").strip().lower()
    return val in ("true", "1", "yes")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

LOCAL_DEV_KEY: Optional[str] = None
_LOCAL_DEV_PRINTED: bool = False

def is_local_dev_auth_enabled() -> bool:
    return os.environ.get("AIRA_LOCAL_DEV_AUTH", "").strip().lower() in ("true", "1", "yes")

def init_local_dev_auth() -> Optional[str]:
    global LOCAL_DEV_KEY, _LOCAL_DEV_PRINTED
    if not is_local_dev_auth_enabled():
        return None

    if not LOCAL_DEV_KEY:
        existing = os.environ.get("AIRA_API_KEY") or os.environ.get("AEGIS_API_KEY")
        if existing:
            LOCAL_DEV_KEY = existing
        else:
            LOCAL_DEV_KEY = f"aira_dev_{uuid.uuid4().hex[:16]}"
            os.environ["AIRA_API_KEY"] = LOCAL_DEV_KEY

        if not _LOCAL_DEV_PRINTED:
            print(f"A.I.R.A. LOCAL DEVELOPMENT API KEY\n{LOCAL_DEV_KEY}")
            _LOCAL_DEV_PRINTED = True

    return LOCAL_DEV_KEY

init_local_dev_auth()

def is_localhost_request(request: Request) -> bool:
    client_host = request.client.host if request.client else ""
    header_host = request.headers.get("host", "").split(":")[0].lower()
    local_ips = {"127.0.0.1", "::1", "localhost", "testclient"}
    return client_host in local_ips and (header_host in local_ips or header_host in ("testserver", "localhost", "127.0.0.1"))

def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    Enforces authentication for authenticated API endpoints.
    Validates against the AIRA_API_KEY or AEGIS_API_KEY environment variable.
    """
    expected_key = os.environ.get("AIRA_API_KEY") or os.environ.get("AEGIS_API_KEY")
    if expected_key:
        if not api_key or api_key != expected_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing 'X-API-Key' header."
            )
    else:
        # Require non-empty key when AEGIS_API_KEY / AIRA_API_KEY is not configured
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Please provide a valid 'X-API-Key' header."
            )
    return api_key

def check_run_access_auth(run_id: str, api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """
    Allows public unauthenticated access only for curated demo runs.
    Enforces verify_api_key for all real verification runs.
    """
    if run_id in DEMO_SCENARIOS or run_id.startswith("demo_") or run_id.startswith("run_demo_"):
        return api_key
    if run_id in RUNS_STORE and RUNS_STORE[run_id].get("scenario_id") is not None:
        return api_key
    return verify_api_key(api_key)

def get_temp_upload_dir() -> Path:
    temp_dir = Path("/tmp/aegis_uploads") if not sys.platform.startswith("win") else Path(os.environ.get("TEMP", "C:/Temp")) / "aegis_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir

def sanitize_path_str(text: str, project_dir: Optional[str] = None) -> str:
    if not text:
        return ""
    clean = str(text)
    if project_dir:
        clean = clean.replace(str(project_dir), "<workspace>")
    import re
    clean = re.sub(r"[A-Za-z]:\\[Uu]sers\\[^\s,;\"']+", "<workspace>", clean)
    clean = re.sub(r"/home/[^\s,;\"']+", "<workspace>", clean)
    clean = re.sub(r"/tmp/aira_project_[^\s,;\"']+", "<workspace>", clean)
    clean = re.sub(r"[A-Za-z]:\\.*\\aira_project_[^\s,;\"']+", "<workspace>", clean)
    return clean

def validate_repository_source(repo_str: str) -> Path:
    """
    Validates repository paths to prevent path traversal and unauthorized filesystem access.
    """
    if ".." in repo_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repository path: Path traversal ('..') is strictly prohibited."
        )
    p = Path(repo_str).resolve()
    if not p.exists() or not p.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository path does not exist or is not a directory: {repo_str}"
        )

    # Reject critical OS system directories
    norm = str(p).lower().replace("\\", "/")
    forbidden_prefixes = ["/etc", "/sys", "/proc", "/root", "/var", "c:/windows", "c:/system32", "c:/program files"]
    if any(norm.startswith(fb) for fb in forbidden_prefixes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access to protected system directories is strictly prohibited."
        )
    return p

# Request & Response Models
class VerificationRequest(BaseModel):
    repository: str = Field(default=".", description="Path or identifier of repository to verify")
    base: str = Field(default="HEAD~1", description="Baseline commit or ref")
    head: str = Field(default="HEAD", description="Proposed commit or ref")
    diff: Optional[str] = Field(default=None, description="Optional unified diff patch content (max 1MB)")
    tier: str = Field(default="auto", description="Verification tier: fast, standard, deep, auto")

class DemoVerificationRequest(BaseModel):
    scenario_id: str = Field(default="demo_01_clean_pass", description="ID of curated scenario to execute")

class VerificationStatusResponse(BaseModel):
    run_id: str
    status: str  # queued, running, completed, failed
    tier: str
    technical_verdict: Optional[str] = None
    release_policy: Optional[str] = None
    created_at: str
    updated_at: str

# In-memory execution store for verified runs
RUNS_STORE: Dict[str, Dict[str, Any]] = {}
RUN_EVENTS: Dict[str, List[Dict[str, Any]]] = {}

# In-memory project store for uploaded projects
PROJECTS_STORE: Dict[str, Dict[str, Any]] = {}

def record_event(run_id: str, stage: str, message: str) -> None:
    if run_id not in RUN_EVENTS:
        RUN_EVENTS[run_id] = []
    RUN_EVENTS[run_id].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "message": message
    })

def seed_demo_runs():
    """Populates store with curated demo scenarios so dashboard has immediate data."""
    for s_id, s_data in DEMO_SCENARIOS.items():
        run_id = f"run_{s_id}"
        if run_id not in RUNS_STORE:
            report = build_scenario_report(s_data)
            RUNS_STORE[run_id] = {
                "run_id": run_id,
                "status": "completed",
                "tier": s_data["execution_tier"],
                "technical_verdict": s_data["technical_verdict"],
                "release_policy": s_data["release_policy"],
                "created_at": "2026-09-27T20:00:00Z",
                "updated_at": "2026-09-27T20:01:00Z",
                "scenario_id": s_id,
                "title": s_data["title"],
                "report": report
            }
            RUN_EVENTS[run_id] = [
                {
                    "timestamp": f"2026-09-27T20:00:{e['ms_offset']//1000:02d}.{e['ms_offset']%1000:03d}Z",
                    "stage": e["stage"],
                    "message": e["message"]
                }
                for e in s_data["events"]
            ]

seed_demo_runs()

def execute_verification_job(run_id: str, req: VerificationRequest) -> None:
    RUNS_STORE[run_id]["status"] = "running"
    RUNS_STORE[run_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    record_event(run_id, "INDEXING", f"Starting repository verification for {req.base}..{req.head}")

    try:
        repo_dir = validate_repository_source(req.repository)
        run_artifacts_dir = repo_dir / ".aegis" / "runs" / run_id
        run_artifacts_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable, "-m", "aegis.cli", "verify",
            "--project-dir", str(repo_dir),
            "--base", req.base,
            "--head", req.head,
            "--tier", req.tier,
            "-o", str(run_artifacts_dir)
        ]

        record_event(run_id, "SECURITY", "Scanning modified AST nodes and diff additions for vulnerabilities")
        record_event(run_id, "TESTING", f"Executing sandboxed test suite under tier '{req.tier.upper()}'")

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        record_event(run_id, "DECISION", "Evaluating risk model and release policy gate")

        report_file = run_artifacts_dir / "report.json"
        if report_file.exists():
            report_data = json.loads(report_file.read_text(encoding="utf-8"))
            RUNS_STORE[run_id]["status"] = "completed"
            RUNS_STORE[run_id]["report"] = report_data
            RUNS_STORE[run_id]["technical_verdict"] = report_data.get("decision", {}).get("technical_verdict")
            RUNS_STORE[run_id]["release_policy"] = report_data.get("decision", {}).get("release_policy")
        else:
            RUNS_STORE[run_id]["status"] = "failed"
            RUNS_STORE[run_id]["error"] = proc.stderr or proc.stdout

    except Exception as e:
        logger.exception("Verification task error")
        RUNS_STORE[run_id]["status"] = "failed"
        RUNS_STORE[run_id]["error"] = str(e)
        record_event(run_id, "ERROR", str(e))
    finally:
        RUNS_STORE[run_id]["updated_at"] = datetime.now(timezone.utc).isoformat()


# ============================================================================
# Authenticated Legacy v1 Routes (Preserved for compatibility & strict testing)
# ============================================================================

@app.get("/v1/health")
def health_check_v1() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "aegis-verifier",
        "version": "1.0.0",
        "docker_available": is_docker_available(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/v1/verifications", status_code=status.HTTP_202_ACCEPTED)
def create_verification_v1(
    req: VerificationRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
) -> Dict[str, Any]:
    """
    Enqueues a repository verification job.
    Mandatory Docker sandbox is enforced. Path traversal is rejected.
    """
    if not is_docker_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mandatory sandbox requirement failed: Docker daemon is unavailable. Remote execution refuses to run un-sandboxed."
        )

    validate_repository_source(req.repository)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{timestamp}_{uuid.uuid4().hex[:6]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    RUNS_STORE[run_id] = {
        "run_id": run_id,
        "status": "queued",
        "tier": req.tier.upper(),
        "technical_verdict": None,
        "release_policy": None,
        "created_at": now_iso,
        "updated_at": now_iso,
        "request": req.model_dump() if hasattr(req, "model_dump") else req.dict()
    }
    record_event(run_id, "QUEUED", f"Verification request received for ref {req.base}..{req.head}")

    background_tasks.add_task(execute_verification_job, run_id, req)

    return {
        "run_id": run_id,
        "status": "queued",
        "tier": req.tier.upper(),
        "created_at": now_iso
    }

@app.get("/v1/verifications/{run_id}")
def get_verification_status_v1(
    run_id: str,
    api_key: str = Depends(verify_api_key)
) -> Dict[str, Any]:
    if run_id not in RUNS_STORE:
        runs_dir = Path(".aegis/runs") / run_id
        report_file = runs_dir / "report.json"
        if report_file.exists():
            data = json.loads(report_file.read_text(encoding="utf-8"))
            return {
                "run_id": run_id,
                "status": "completed",
                "tier": data.get("verification", {}).get("tier", "STANDARD"),
                "technical_verdict": data.get("decision", {}).get("technical_verdict"),
                "release_policy": data.get("decision", {}).get("release_policy"),
                "created_at": data.get("timestamp"),
                "updated_at": data.get("timestamp"),
            }
        raise HTTPException(status_code=404, detail=f"Verification run '{run_id}' not found")

    run_info = RUNS_STORE[run_id]
    return {
        "run_id": run_id,
        "status": run_info["status"],
        "tier": run_info["tier"],
        "technical_verdict": run_info["technical_verdict"],
        "release_policy": run_info["release_policy"],
        "created_at": run_info["created_at"],
        "updated_at": run_info["updated_at"],
    }

@app.get("/v1/verifications/{run_id}/report")
def get_verification_report_v1(
    run_id: str,
    api_key: str = Depends(verify_api_key)
) -> Dict[str, Any]:
    if run_id in RUNS_STORE and "report" in RUNS_STORE[run_id]:
        return RUNS_STORE[run_id]["report"]

    runs_dir = Path(".aegis/runs") / run_id
    report_file = runs_dir / "report.json"
    if report_file.exists():
        return json.loads(report_file.read_text(encoding="utf-8"))

    raise HTTPException(status_code=404, detail=f"Report for run '{run_id}' not found or still running")

@app.get("/v1/verifications/{run_id}/events")
def get_verification_events_v1(
    run_id: str,
    api_key: str = Depends(verify_api_key)
) -> List[Dict[str, Any]]:
    if run_id not in RUN_EVENTS:
        raise HTTPException(status_code=404, detail=f"No events found for run '{run_id}'")
    return RUN_EVENTS[run_id]


# ============================================================================
# Public Release 1.0 Developer & Product API Routes (/api/ and /health)
# ============================================================================

@app.get("/health")
@app.get("/api/health")
def public_health() -> Dict[str, Any]:
    sandbox_diag = check_sandbox_health()
    return {
        "status": "healthy",
        "service": "aira-release-assurance",
        "product": "A.I.R.A.",
        "version": "1.0.0",
        "docker_available": is_docker_available(),
        "sandbox_available": sandbox_diag["available"],
        "sandbox_health": sandbox_diag["sandbox_health"],
        "demo_mode": is_demo_mode(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/system/sandbox")
def get_sandbox_system_health(response: Response) -> Dict[str, Any]:
    """
    Returns explicit container sandbox diagnostics, daemon connectivity, and image readiness.
    Publicly accessible to allow health probes, status badges, and pre-verification checks.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return check_sandbox_health()

@app.post("/api/system/sandbox/build-image")
def trigger_build_sandbox_image(api_key: str = Depends(verify_api_key)) -> Dict[str, Any]:
    """
    Triggers building or preparing the hardened sandbox container image.
    Requires authentication. Fails closed with 503 if Docker daemon is unreachable.
    """
    rate_limiter.enforce(api_key or "anon")
    if not is_docker_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SANDBOX_UNAVAILABLE: Docker daemon is not reachable. Start Docker Desktop and retry."
        )
    success, message = build_sandbox_image_with_output()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image build failed: {message}"
        )
    return {
        "status": "success",
        "image": os.environ.get("DOCKER_SANDBOX_IMAGE", "aegis-sandbox:latest"),
        "message": message
    }

@app.get("/api/auth/check")
def check_auth(api_key: str = Security(verify_api_key)) -> Dict[str, Any]:
    """
    Lightweight validation endpoint to test API key validity.
    Returns 200 { 'authenticated': true } if valid, 401 if invalid or missing.
    """
    return {"authenticated": True}

@app.get("/api/auth/local-dev-token")
def get_local_dev_token(request: Request) -> Dict[str, Any]:
    """
    Zero-friction local development helper.
    Available ONLY when:
    1. AIRA_LOCAL_DEV_AUTH=true
    2. Request is physically originating from localhost (127.0.0.1 / ::1 / localhost)

    Returns 403 on non-localhost or when local dev mode is not explicitly enabled.
    """
    if not is_local_dev_auth_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local development authentication mode is not enabled."
        )
    if not is_localhost_request(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local development token is only accessible from localhost."
        )
    dev_key = init_local_dev_auth()
    return {
        "enabled": True,
        "token": dev_key
    }

@app.get("/api/demo/scenarios")
def list_demo_scenarios() -> List[Dict[str, Any]]:
    """Returns curated demo scenarios showing Aegis verification capabilities."""
    summaries = []
    for s_id, s_data in DEMO_SCENARIOS.items():
        summaries.append({
            "id": s_id,
            "title": s_data["title"],
            "category": s_data["category"],
            "badge": s_data["badge"],
            "description": s_data["description"],
            "file_path": s_data["file_path"],
            "diff": s_data["diff"],
            "technical_verdict": s_data["technical_verdict"],
            "release_policy": s_data["release_policy"],
            "risk_level": s_data["risk_level"],
            "duration_ms": s_data["duration_ms"]
        })
    return summaries

@app.get("/api/demo/scenarios/{scenario_id}")
def get_demo_scenario(scenario_id: str) -> Dict[str, Any]:
    """Returns detailed scenario data by ID."""
    if scenario_id not in DEMO_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    return DEMO_SCENARIOS[scenario_id]

@app.post("/api/demo/verify", status_code=status.HTTP_200_OK)
def trigger_demo_verification(req: DemoVerificationRequest) -> Dict[str, Any]:
    """
    Executes or replays a curated demo scenario with real-time verification stages.
    """
    if req.scenario_id not in DEMO_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{req.scenario_id}' not found")

    scenario = DEMO_SCENARIOS[req.scenario_id]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"demo_{req.scenario_id}_{timestamp}_{uuid.uuid4().hex[:4]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    report = build_scenario_report(scenario)
    RUNS_STORE[run_id] = {
        "run_id": run_id,
        "status": "completed",
        "tier": scenario["execution_tier"],
        "technical_verdict": scenario["technical_verdict"],
        "release_policy": scenario["release_policy"],
        "created_at": now_iso,
        "updated_at": now_iso,
        "scenario_id": req.scenario_id,
        "title": scenario["title"],
        "report": report
    }

    RUN_EVENTS[run_id] = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": e["stage"],
            "message": e["message"]
        }
        for e in scenario["events"]
    ]

    return {
        "run_id": run_id,
        "scenario_id": req.scenario_id,
        "title": scenario["title"],
        "status": "completed",
        "technical_verdict": scenario["technical_verdict"],
        "release_policy": scenario["release_policy"],
        "created_at": now_iso,
        "report": report
    }

@app.get("/api/verifications")
def list_verifications() -> List[Dict[str, Any]]:
    """Returns all recent verifications for the dashboard view."""
    results = []
    for run_id, data in RUNS_STORE.items():
        results.append({
            "run_id": run_id,
            "status": data.get("status"),
            "tier": data.get("tier"),
            "technical_verdict": data.get("technical_verdict"),
            "release_policy": data.get("release_policy"),
            "created_at": data.get("created_at"),
            "title": data.get("title", f"Run {run_id}")
        })
    # Sort newest first
    results.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return results

@app.post("/api/verifications", status_code=status.HTTP_202_ACCEPTED)
def create_public_verification(
    req: VerificationRequest,
    background_tasks: BackgroundTasks,
    api_key: Optional[str] = Security(api_key_header)
) -> Dict[str, Any]:
    """
    Public submission endpoint for patch diff verification.
    Enforces diff size limits (1MB maximum) and safe execution guards.
    Mandatory Docker sandbox is enforced — never fabricates verification results.
    """
    rate_limiter.enforce(api_key or "anon")
    if req.diff and len(req.diff.encode("utf-8")) > 1_048_576:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload too large: unified diff exceeds maximum allowed size of 1MB."
        )

    # Hard sandbox requirement: NEVER fabricate results for real verifications
    if not is_docker_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A.I.R.A. real verification requires an isolated execution sandbox."
        )

    verify_api_key(api_key)

    validate_repository_source(req.repository)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{timestamp}_{uuid.uuid4().hex[:6]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    RUNS_STORE[run_id] = {
        "run_id": run_id,
        "status": "queued",
        "tier": req.tier.upper(),
        "technical_verdict": None,
        "release_policy": None,
        "created_at": now_iso,
        "updated_at": now_iso,
        "request": req.model_dump() if hasattr(req, "model_dump") else req.dict()
    }
    record_event(run_id, "QUEUED", f"Verification request received for ref {req.base}..{req.head}")

    background_tasks.add_task(execute_verification_job, run_id, req)

    return {
        "run_id": run_id,
        "status": "queued",
        "tier": req.tier.upper(),
        "created_at": now_iso
    }

@app.get("/api/verifications/{run_id}")
def get_public_verification_status(
    run_id: str,
    api_key: Optional[str] = Depends(check_run_access_auth)
) -> Dict[str, Any]:
    if run_id not in RUNS_STORE:
        raise HTTPException(status_code=404, detail=f"Verification run '{run_id}' not found")
    return RUNS_STORE[run_id]

@app.get("/api/verifications/{run_id}/events")
def get_public_verification_events(
    run_id: str,
    api_key: Optional[str] = Depends(check_run_access_auth)
) -> List[Dict[str, Any]]:
    if run_id not in RUN_EVENTS:
        raise HTTPException(status_code=404, detail=f"No events found for run '{run_id}'")
    return RUN_EVENTS[run_id]

@app.get("/api/verifications/{run_id}/evidence")
def get_public_verification_evidence(
    run_id: str,
    api_key: Optional[str] = Depends(check_run_access_auth)
) -> Dict[str, Any]:
    if run_id in RUNS_STORE and "report" in RUNS_STORE[run_id]:
        return RUNS_STORE[run_id]["report"]
    raise HTTPException(status_code=404, detail=f"Evidence report for run '{run_id}' not found")

@app.get("/api/research/mlverify")
def get_mlverify_research_metrics() -> Dict[str, Any]:
    """
    Returns authentic, audited research metrics from the Phase 2.1 evaluation.
    Honest reporting: Defect prediction is research-supported in SHADOW MODE ONLY.
    Autonomous routing is rejected.
    """
    return {
        "framework": "MLVerify Predictive Risk & Verification Routing",
        "status": "SHADOW_MODE_ONLY",
        "research_foundation": {
            "dataset": "empirical_100_local_v1",
            "sample_size": 100,
            "tasks": 50,
            "provider": "Qwen 2.5 Coder (Local, 0 cloud cost)",
            "evaluation_protocol": "5-Fold Grouped Cross-Validation (by task_id)",
            "leakage_audit": "PASSED_UNDER_DECLARED_FEATURE_CONTRACT"
        },
        "defect_prediction": {
            "status": "RESEARCH_SUPPORTED",
            "best_model": "Random Forest (Shallow)",
            "metrics": {
                "pr_auc": 0.9367,
                "roc_auc": 0.8870,
                "brier_score": 0.1114,
                "ece": 0.0737,
                "bootstrap_ci_pr_auc_95": [0.8814, 0.9782],
                "bootstrap_ci_roc_auc_95": [0.8122, 0.9514]
            },
            "comparison_to_baselines": {
                "majority_baseline_pr_auc": 0.5198,
                "heuristic_baseline_pr_auc": 0.7708,
                "regularized_linear_pr_auc": 0.9348
            }
        },
        "methodological_boundaries": {
            "agent_failure_prediction": "DIAGNOSTIC_ONLY (Telemetry monitor, excluded from pre-verification claims)",
            "false_accept_prediction": "INSUFFICIENT_DATA (Rare-event target in empirical data)",
            "autonomous_routing": "REJECTED (Routing cannot be claimed as production-certified without larger empirical campaign)"
        }
    }

# ============================================================================
# Project Upload and Verification Endpoints
# ============================================================================

# ============================================================================
# Project Upload and Verification Endpoints
# ============================================================================

@app.post("/api/projects/upload", status_code=201)
async def upload_project(
    archive: UploadFile = File(...),
    api_key: str = Depends(verify_api_key)
):
    rate_limiter.enforce(api_key or "anon")
    if not archive.filename.endswith((".zip", ".tar.gz", ".tgz")):
        raise HTTPException(status_code=400, detail="Invalid archive format. Must be .zip, .tar.gz, or .tgz")

    archive_bytes = await archive.read()
    if len(archive_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archive size exceeds 50MB limit")

    project_hash = hashlib.sha256(archive_bytes).hexdigest()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    uuid_hex = uuid.uuid4().hex[:6]
    project_id = f"proj_{timestamp}_{uuid_hex}"

    temp_dir = get_temp_upload_dir()
    # Security: Use internal filename derived from project_id and UUID, not the raw user filename
    ext = ".zip" if archive.filename.endswith(".zip") else (".tar.gz" if archive.filename.endswith(".tar.gz") else ".tgz")
    internal_name = f"{project_id}_{uuid.uuid4().hex[:8]}{ext}"
    archive_path = temp_dir / internal_name
    with open(archive_path, "wb") as f:
        f.write(archive_bytes)

    result = extract_archive(archive_path)
    try:
        archive_path.unlink(missing_ok=True)
    except Exception:
        pass

    if not result.success:
        raise HTTPException(status_code=400, detail=f"Extraction failed: {result.errors}")

    framework_info = detect_framework(result.root_dir)

    project_data = {
        "project_id": project_id,
        "project_hash": project_hash,
        "extract_dir": str(result.extract_dir),
        "root_dir": str(result.root_dir),
        "framework": framework_info.framework,
        "framework_confidence": framework_info.confidence,
        "test_files": framework_info.test_files,
        "discovered_tests": framework_info.discovered_tests,
        "discovered_test_nodeids": framework_info.discovered_tests,
        "discovered_count": framework_info.discovered_count,
        "user_test_files": [],
        "total_files": result.file_count,
        "total_bytes": result.total_bytes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready"
    }

    PROJECTS_STORE[project_id] = project_data
    return project_data

@app.post("/api/projects/{project_id}/tests")
async def upload_project_tests(
    project_id: str,
    tests_archive: UploadFile = File(...),
    api_key: str = Depends(verify_api_key)
):
    rate_limiter.enforce(api_key or "anon")
    if project_id not in PROJECTS_STORE:
        raise HTTPException(status_code=404, detail="Project not found")

    if not tests_archive.filename.endswith((".zip", ".tar.gz", ".tgz")):
        raise HTTPException(status_code=400, detail="Invalid archive format. Must be .zip, .tar.gz, or .tgz")

    archive_bytes = await tests_archive.read()
    if len(archive_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Custom test archive size exceeds 50MB limit")

    project = PROJECTS_STORE[project_id]
    project_root = Path(project["root_dir"])
    user_tests_dir = project_root / "user_tests"
    user_tests_dir.mkdir(exist_ok=True)

    temp_dir = get_temp_upload_dir()
    # Security: Use internal filename derived from project_id and UUID, not the raw user filename
    ext = ".zip" if tests_archive.filename.endswith(".zip") else (".tar.gz" if tests_archive.filename.endswith(".tar.gz") else ".tgz")
    internal_name = f"tests_{project_id}_{uuid.uuid4().hex[:8]}{ext}"
    archive_path = temp_dir / internal_name
    with open(archive_path, "wb") as f:
        f.write(archive_bytes)

    result = extract_archive(archive_path)
    try:
        archive_path.unlink(missing_ok=True)
    except Exception:
        pass

    if not result.success:
        raise HTTPException(status_code=400, detail=f"Custom test extraction failed: {result.errors}")

    # Copy extracted test files into the project's user_tests directory
    src_root = result.root_dir or result.extract_dir
    test_files_found = list(Path(src_root).rglob("test_*.py")) + list(Path(src_root).rglob("*_test.py"))
    str_test_files = []
    for tf in test_files_found:
        rel = tf.relative_to(src_root)
        dest = user_tests_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tf, dest)
        str_test_files.append(str(Path("user_tests") / rel))

    # Clean up the temporary extraction directory
    if result.extract_dir and result.extract_dir != project_root:
        secure_cleanup(result.extract_dir)

    project["user_test_files"] = str_test_files

    return {
        "message": "Tests uploaded",
        "user_test_files_detected": len(str_test_files),
        "test_files": str_test_files
    }

def execute_project_verification_job(run_id: str, project_id: str, req: ProjectVerifyRequest) -> None:
    """
    Background job that executes real verification on an uploaded project.
    HARD SANDBOX GUARANTEE: Never allows host execution. Runs strictly inside Docker container.
    """
    project = PROJECTS_STORE.get(project_id)
    if not project:
        RUNS_STORE[run_id]['status'] = 'failed'
        RUNS_STORE[run_id]['error'] = 'Project not found'
        return

    project_dir = Path(project['root_dir'])
    RUNS_STORE[run_id]['status'] = 'running'
    record_event(run_id, 'INITIALIZE', f'Starting verification of project {project_id}')

    from aegis.execution.sandbox import run_tests_sandboxed, SandboxUnavailableError
    from aegis.execution.environment import build_sandbox_environment_image

    # HARD SANDBOX CHECK: Docker must be available
    if not is_docker_available():
        diag = check_sandbox_health()
        reason = diag.get("failure_reason") or "Docker daemon is required but unavailable."
        RUNS_STORE[run_id]['status'] = 'failed'
        RUNS_STORE[run_id]['error'] = f'SANDBOX_UNAVAILABLE: {reason}'
        record_event(run_id, 'ERROR', f'SANDBOX_UNAVAILABLE: Execution refused without container sandbox. {reason}')
        return

    # BUILD / RESOLVE REPRODUCIBLE ENVIRONMENT IMAGE
    try:
        record_event(run_id, 'ENVIRONMENT', 'Resolving reproducible container image for project dependencies')
        docker_image = build_sandbox_environment_image(project_dir)
    except Exception as e:
        RUNS_STORE[run_id]['status'] = 'failed'
        RUNS_STORE[run_id]['error'] = f'SANDBOX_BUILD_ERROR: Failed to build environment image: {e}'
        record_event(run_id, 'ERROR', f'SANDBOX_BUILD_ERROR: {e}')
        return

    stages = {}
    limitations = []

    try:
        # C1: Syntax validation via AST
        from aegis.verification.validator import validate_python
        record_event(run_id, 'C1_SYNTAX', 'Validating Python syntax via AST parsing')
        py_files = list(project_dir.rglob('*.py'))
        syntax_ok = True
        syntax_errors = []
        for pf in py_files:
            if any(skip in str(pf) for skip in ['__pycache__', '.git', 'venv', '.venv']):
                continue
            try:
                code = pf.read_text(encoding='utf-8', errors='ignore')
                result = validate_python(code, str(pf.name))
                if not result.valid:
                    syntax_ok = False
                    syntax_errors.extend(result.errors)
            except Exception:
                pass
        stages['C1_syntax'] = {
            'name': 'C1: Syntax & AST Integrity',
            'status': StageStatus.PASS.value if syntax_ok else StageStatus.FAIL.value,
            'detail': 'All files pass AST validation' if syntax_ok else f'Syntax errors: {syntax_errors[:3]}'
        }

        # Test Discovery & Selection
        discovery_cmd_str = "python -m pytest -o addopts= --collect-only -q -p no:cacheprovider --ignore=user_tests"

        # Authoritative sandbox test collection inside container if Docker is armed
        # Pytest collection is the SINGLE source of truth for discovered tests.
        from aegis.execution.sandbox import collect_tests_sandboxed
        collection_error_nodeids = []
        try:
            sandbox_discovered = collect_tests_sandboxed(project_dir, docker_image=docker_image)
            discovered_tests = list(sandbox_discovered)
            collection_error_nodeids = list(getattr(sandbox_discovered, 'collection_error_nodeids', []))
            if not discovered_tests and not collection_error_nodeids:
                if project.get('discovered_tests'):
                    discovered_tests = list(project.get('discovered_tests'))
                elif project.get('test_files'):
                    from aegis.uploads.detection import discover_project_tests
                    discovered_tests = discover_project_tests(project_dir, project.get('test_files'))
        except Exception as e:
            logger.warning(f"Container test collection warning: {e}")
            discovered_tests = list(project.get('discovered_tests') or [])
            if not discovered_tests and project.get('test_files'):
                from aegis.uploads.detection import discover_project_tests
                discovered_tests = discover_project_tests(project_dir, project.get('test_files'))

        collected_nodeids = list(discovered_tests)
        collected_count = len(collected_nodeids)
        collection_error_count = len(collection_error_nodeids)
        discovered_count = collected_count
        print(f"PYTEST COLLECTION COUNT: {collected_count}")
        print(f"PYTEST COLLECTION ERRORS COUNT: {collection_error_count}")

        if req.selected_tests is not None:
            selected_nodeids = list(req.selected_tests)
            selected_tests = selected_nodeids
            excluded_tests = [t for t in collected_nodeids if t not in selected_nodeids]
            exclusion_reasons = {t: "User explicitly selected a subset" for t in excluded_tests}
            is_partial_suite = len(selected_nodeids) < collected_count
        else:
            selected_nodeids = list(collected_nodeids)
            selected_tests = selected_nodeids
            excluded_tests = []
            exclusion_reasons = {}
            is_partial_suite = False

        selected_count = len(selected_nodeids)
        if is_partial_suite:
            limitations.append(f"C2 partial test suite: user explicitly selected {selected_count} of {collected_count} discovered tests")

        # Instrument and print exact diagnostics (Directive Section 2)
        print(f"TEST DISCOVERY: discovered_tests = {discovered_tests}")
        print(f"TEST SELECTION: selected_tests = {selected_tests}")
        print(f"EXCLUDED: excluded_tests = {excluded_tests}")
        print(f"EXCLUSION REASONS: {exclusion_reasons}")

        project_test_discovery = {
            "framework": project.get('framework', 'pytest'),
            "collected": collected_count,
            "collection_errors": collection_error_count,
            "collected_nodeids": collected_nodeids,
            "collection_error_nodeids": collection_error_nodeids,
            "discovered": collected_count,
            "discovered_tests": discovered_tests,
            "selected": selected_count,
            "selected_tests": selected_tests,
            "excluded": len(excluded_tests),
            "excluded_tests": excluded_tests,
            "exclusion_reasons": exclusion_reasons
        }
        test_command_info = {
            "command": "python -m pytest -v --tb=short --color=no -p no:cacheprovider",
            "discovery_command": discovery_cmd_str,
            "execution_command": "python -m pytest -v --tb=short --color=no -p no:cacheprovider",
            "working_directory": "/workspace",
            "test_framework": project.get('framework', 'pytest'),
            "collected_count": collected_count,
            "collection_error_count": collection_error_count,
            "discovered_count": collected_count,
            "selected_count": selected_count,
            "executed_count": 0
        }
        project_test_execution = {
            "executed": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "collection_errors": collection_error_count,
            "collection_error_nodeids": collection_error_nodeids,
            "failed_tests": [],
            "failed_test_details": {},
            "executed_test_nodeids": [],
            "skipped_test_nodeids": [],
            "failed_test_nodeids": [],
            "error_test_nodeids": []
        }

        # C2: Project visible tests (HARD SANDBOX: use_docker=True, require_sandbox=True)
        count_mismatch = False
        executed_count = 0
        passed_count = 0
        failed_count = 0
        error_count = 0
        skipped_count = 0
        total_accounted = 0
        if project.get('framework') == 'UNSUPPORTED_PROJECT':
            stages['C2_visible_tests'] = {
                'name': 'C2: Project Acceptance Tests',
                'status': StageStatus.NOT_SUPPORTED.value,
                'detail': 'UNSUPPORTED_PROJECT: No supported test runner (pytest/unittest) discovered.'
            }
            limitations.append('C2 tests: unsupported project or unrecognized test runner')
        elif req.run_project_tests and (collected_count > 0 or collection_error_count > 0 or project.get('test_files')):
            record_event(run_id, 'C2_TESTS', 'Executing project test suite inside hardened Docker sandbox')
            try:
                # Default: Run full suite (test_files=None) unless user explicitly selected a subset
                files_to_run = selected_tests if is_partial_suite else None
                sandbox_res = run_tests_sandboxed(
                    project_dir=project_dir,
                    test_files=files_to_run,
                    timeout=120,
                    use_docker=True,
                    require_sandbox=True,
                    docker_image=docker_image,
                )
                if not sandbox_res.used_sandbox:
                    raise SandboxUnavailableError("Host execution prohibited: Sandbox failed to engage.")
                test_result = sandbox_res.test_result

                # Merge any collection error nodeids from execution run
                for ce in getattr(test_result, 'collection_error_nodeids', []):
                    if ce not in collection_error_nodeids:
                        collection_error_nodeids.append(ce)
                collection_error_count = len(collection_error_nodeids)
                project_test_discovery["collection_errors"] = collection_error_count
                project_test_discovery["collection_error_nodeids"] = collection_error_nodeids
                test_command_info["collection_error_count"] = collection_error_count

                executed_nodeids = getattr(test_result, 'executed_nodeids', None) or [node for node, status in test_result.test_outcomes.items() if status in ('PASSED', 'FAILED', 'ERROR', 'XPASS', 'XFAIL')]
                skipped_nodeids = getattr(test_result, 'skipped_nodeids', None) or [node for node, status in test_result.test_outcomes.items() if status == 'SKIPPED']
                failed_nodeids = getattr(test_result, 'failed_nodeids', None) or [node for node, status in test_result.test_outcomes.items() if status == 'FAILED']
                error_nodeids = getattr(test_result, 'error_nodeids', None) or [node for node, status in test_result.test_outcomes.items() if status == 'ERROR']
                passed_nodeids = getattr(test_result, 'passed_nodeids', None) or [node for node, status in test_result.test_outcomes.items() if status == 'PASSED']

                passed_count = test_result.tests_passed
                failed_count = test_result.tests_failed
                error_count = test_result.tests_error
                skipped_count = test_result.tests_skipped
                executed_count = test_result.total_executed or len(executed_nodeids) or (passed_count + failed_count + error_count)
                total_accounted = executed_count + skipped_count

                cmd_str = " ".join(sandbox_res.command) if sandbox_res.command else "python -m pytest -v --tb=short --color=no -p no:cacheprovider"
                test_command_info["command"] = cmd_str
                test_command_info["discovery_command"] = discovery_cmd_str
                test_command_info["execution_command"] = cmd_str
                test_command_info["executed_count"] = executed_count

                # Print EXACT required debug output (Directive 9)
                print(f"EXACT EXECUTION COMMAND: {cmd_str}")
                print(f"PYTEST EXECUTION COUNT: {executed_count}")
                print(f"PYTEST PASSED: {passed_count}")
                print(f"PYTEST FAILED: {failed_count}")
                print(f"PYTEST ERRORS: {error_count}")
                print(f"PYTEST SKIPPED: {skipped_count}")

                failed_tests = failed_nodeids or [k for k, v in test_result.test_outcomes.items() if v in ('FAILED', 'ERROR')]
                failed_details = dict(test_result.failed_test_details)
                executed_tests = executed_nodeids or [k for k, v in test_result.test_outcomes.items() if v in ('PASSED', 'FAILED', 'ERROR', 'XPASS', 'XFAIL')]
                print(f"TEST EXECUTION: executed_tests = {executed_tests}")

                project_test_execution = {
                    "executed": executed_count,
                    "passed": passed_count,
                    "failed": failed_count,
                    "errors": error_count,
                    "skipped": skipped_count,
                    "collection_errors": collection_error_count,
                    "collection_error_nodeids": collection_error_nodeids,
                    "failed_tests": failed_tests,
                    "failed_test_details": failed_details,
                    "executed_test_nodeids": executed_nodeids,
                    "skipped_test_nodeids": skipped_nodeids,
                    "failed_test_nodeids": failed_nodeids,
                    "error_test_nodeids": error_nodeids,
                }

                # Hard Integrity Invariant Checks (Directive 4, 7):
                # Semantic invariants:
                #   passed + failed + errors = executed (skipped tests are NOT executed)
                #   executed + skipped = selected
                reconciled = (passed_count + failed_count + error_count == executed_count)

                if not reconciled:
                    count_mismatch = True
                    c2_status = StageStatus.ERROR.value
                    c2_detail = f"COUNT_INVARIANT_VIOLATION: passed ({passed_count}) + failed ({failed_count}) + errors ({error_count}) != executed ({executed_count})."
                elif collection_error_count > 0:
                    c2_status = StageStatus.ERROR.value
                    c2_detail = f"TEST_COLLECTION_ERROR: {collection_error_count} collection error(s) detected during test discovery/execution ({collected_count} collected, {executed_count} executed)."
                elif not is_partial_suite and collected_count < executed_count:
                    count_mismatch = True
                    c2_status = StageStatus.ERROR.value
                    c2_detail = f"COUNT_INVARIANT_VIOLATION: collected ({collected_count}) < executed ({executed_count}). Invalid test accounting."
                elif req.selected_tests is None and selected_count < collected_count:
                    count_mismatch = True
                    c2_status = StageStatus.ERROR.value
                    c2_detail = f"SILENT_RESTRICTION_ERROR: selected ({selected_count}) < collected ({collected_count}) without user selection."
                elif not is_partial_suite and collected_count > 0 and total_accounted != collected_count:
                    count_mismatch = True
                    c2_status = StageStatus.ERROR.value
                    c2_detail = f"DISCOVERY_EXECUTION_MISMATCH: {collected_count} discovered, but {executed_count} executed ({skipped_count} skipped). Partial suite execution without user selection."
                elif is_partial_suite and total_accounted != selected_count:
                    count_mismatch = True
                    c2_status = StageStatus.ERROR.value
                    c2_detail = f"DISCOVERY_EXECUTION_MISMATCH: {selected_count} selected, but {executed_count} executed ({skipped_count} skipped)."
                elif executed_count > 0 and (passed_count + failed_count + error_count == 0) and (skipped_count < executed_count):
                    count_mismatch = True
                    c2_status = StageStatus.ERROR.value
                    c2_detail = f"INVALID_ZERO_ACCOUNTING: {executed_count} executed but 0 passed/failed reported."
                elif failed_count > 0:
                    c2_status = StageStatus.FAIL.value
                    fail_summary = f"{failed_count} failed"
                    if failed_tests:
                        first_f = failed_tests[0].split("::")[-1]
                        first_d = failed_details.get(failed_tests[0], "")
                        fail_summary += f" ({first_f}: {first_d[:80]})" if first_d else f" ({first_f})"
                    c2_detail = f"{collected_count} discovered, {executed_count} executed ({passed_count} passed, {fail_summary}, {error_count} errors, {skipped_count} skipped)"
                elif error_count > 0:
                    c2_status = StageStatus.ERROR.value
                    c2_detail = f"{collected_count} discovered, {executed_count} executed ({error_count} errors, {passed_count} passed, {skipped_count} skipped)"
                elif test_result.passed and reconciled and not count_mismatch:
                    c2_status = StageStatus.PASS.value
                    c2_detail = f"{collected_count} discovered, {executed_count} executed ({passed_count} passed, 0 failed, 0 errors, {skipped_count} skipped)"
                else:
                    c2_status = StageStatus.FAIL.value if not test_result.passed else StageStatus.ERROR.value
                    c2_detail = f"{passed_count} passed, {failed_count} failed, {error_count} errors, {skipped_count} skipped"

                stages['C2_visible_tests'] = {
                    'name': 'C2: Project Acceptance Tests',
                    'status': c2_status,
                    'detail': c2_detail,
                    'collected_count': collected_count,
                    'collection_error_count': collection_error_count,
                    'discovered_count': collected_count,
                    'selected_count': selected_count,
                    'tests_executed': executed_count,
                    'tests_passed': test_result.tests_passed,
                    'tests_failed': test_result.tests_failed,
                    'tests_error': test_result.tests_error,
                    'tests_skipped': skipped_count,
                    'collected_nodeids': collected_nodeids,
                    'collection_error_nodeids': collection_error_nodeids,
                    'selected_nodeids': selected_nodeids,
                    'failed_tests': failed_tests,
                    'failed_test_details': failed_details,
                    'executed_test_nodeids': executed_nodeids,
                    'skipped_test_nodeids': skipped_nodeids,
                    'failed_test_nodeids': failed_nodeids,
                    'error_test_nodeids': error_nodeids,
                    'duration_seconds': test_result.duration_seconds
                }
            except SandboxUnavailableError as e:
                stages['C2_visible_tests'] = {
                    'name': 'C2: Project Acceptance Tests',
                    'status': StageStatus.ERROR.value,
                    'detail': f'SANDBOX_UNAVAILABLE: {e}'
                }
                project_test_execution['errors'] = 1
            except Exception as e:
                stages['C2_visible_tests'] = {
                    'name': 'C2: Project Acceptance Tests',
                    'status': StageStatus.ERROR.value,
                    'detail': sanitize_path_str(str(e), str(project_dir))
                }
                project_test_execution['errors'] = 1
        else:
            stages['C2_visible_tests'] = {
                'name': 'C2: Project Acceptance Tests',
                'status': StageStatus.SKIPPED.value,
                'detail': 'No project tests found or test execution disabled'
            }

        # C2_user_tests: Custom user-uploaded tests (HARD SANDBOX: use_docker=True, require_sandbox=True)
        user_test_inventory = {'executed': 0, 'passed': 0, 'failed': 0, 'error': 0, 'status': StageStatus.NOT_AVAILABLE.value}
        if req.run_user_tests and project.get('user_test_files'):
            record_event(run_id, 'USER_TESTS', 'Executing custom user tests inside hardened Docker sandbox')
            try:
                user_sandbox_res = run_tests_sandboxed(
                    project_dir=project_dir,
                    test_files=project.get('user_test_files', []),
                    timeout=120,
                    use_docker=True,
                    require_sandbox=True,
                    docker_image=docker_image,
                )
                if not user_sandbox_res.used_sandbox:
                    raise SandboxUnavailableError("Host execution prohibited: Sandbox failed to engage for user tests.")
                user_res = user_sandbox_res.test_result
                user_total = user_res.tests_passed + user_res.tests_failed + user_res.tests_error
                user_status = StageStatus.PASS.value if user_res.passed else StageStatus.FAIL.value
                stages['C2_user_tests'] = {
                    'name': 'C2: User Custom Tests',
                    'status': user_status,
                    'detail': f'{user_res.tests_passed} passed, {user_res.tests_failed} failed, {user_res.tests_error} errors',
                    'tests_executed': user_total,
                    'tests_passed': user_res.tests_passed,
                    'tests_failed': user_res.tests_failed,
                    'tests_error': user_res.tests_error,
                    'duration_seconds': user_res.duration_seconds
                }
                user_test_inventory = {
                    'executed': user_total,
                    'passed': user_res.tests_passed,
                    'failed': user_res.tests_failed,
                    'error': user_res.tests_error,
                    'duration_seconds': user_res.duration_seconds,
                    'status': user_status
                }
            except SandboxUnavailableError as e:
                stages['C2_user_tests'] = {
                    'name': 'C2: User Custom Tests',
                    'status': StageStatus.ERROR.value,
                    'detail': f'SANDBOX_UNAVAILABLE: {e}'
                }
                user_test_inventory = {'executed': 0, 'passed': 0, 'failed': 0, 'error': 1, 'status': StageStatus.ERROR.value}
            except Exception as e:
                stages['C2_user_tests'] = {
                    'name': 'C2: User Custom Tests',
                    'status': StageStatus.ERROR.value,
                    'detail': sanitize_path_str(str(e), str(project_dir))
                }
                user_test_inventory = {'executed': 0, 'passed': 0, 'failed': 0, 'error': 1, 'status': StageStatus.ERROR.value}
        else:
            stages['C2_user_tests'] = {
                'name': 'C2: User Custom Tests',
                'status': StageStatus.NOT_AVAILABLE.value,
                'detail': 'No custom tests uploaded'
            }

        # C3: Hidden invariants — NOT_AVAILABLE for uploaded projects
        stages['C3_hidden_invariants'] = {
            'name': 'C3: Hidden Invariants',
            'status': StageStatus.NOT_AVAILABLE.value,
            'detail': 'Hidden invariant oracle tests are not available for user-uploaded projects'
        }
        limitations.append('C3 hidden invariants: not available for user-uploaded projects')

        # C4: Regression — NOT_AVAILABLE without repository history
        stages['C4_regression'] = {
            'name': 'C4: Regression Suite',
            'status': StageStatus.NOT_AVAILABLE.value,
            'detail': 'Regression testing requires a baseline commit reference (not available for standalone uploads)'
        }
        limitations.append('C4 regression: requires repository git history or baseline not present in archive upload')

        # C5: Mutation testing — NOT_SUPPORTED for standalone archive uploads
        stages['C5_mutation'] = {
            'name': 'C5: Mutation Resistance',
            'status': StageStatus.NOT_SUPPORTED.value,
            'detail': 'Mutation testing is not supported for standalone archive uploads'
        }
        limitations.append('C5 mutation: not supported for archive uploads')

        # C6: Security scan
        sec_findings = []
        if req.run_security:
            record_event(run_id, 'C6_SECURITY', 'Running security AST and secret scan')
            from aegis.verification.security import SecurityScanner
            scanner = SecurityScanner()
            sec_file_map = {}
            for pf in py_files:
                if any(skip in str(pf) for skip in ['__pycache__', '.git', 'venv', '.venv']):
                    continue
                try:
                    rel_p = str(pf.relative_to(project_dir)).replace('\\', '/')
                    sec_file_map[rel_p] = pf.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    pass
            sec_findings, is_safe = scanner.scan_project_files(sec_file_map)
            app_violations = [f for f in sec_findings if f.source_classification == "APPLICATION_CODE" and f.severity in ("HIGH", "MEDIUM")]
            sec_status = StageStatus.PASS.value if is_safe else StageStatus.FAIL.value
            sec_detail = 'Clean security scan' if is_safe else f'{len(app_violations)} security issues found in application code'
            stages['C6_security'] = {
                'name': 'C6: Security AST & Taint Scan',
                'status': sec_status,
                'detail': sec_detail,
                'findings': [f.finding for f in sec_findings[:15]],
                'security_table': [f.to_dict() for f in sec_findings]
            }
        else:
            stages['C6_security'] = {
                'name': 'C6: Security AST & Taint Scan',
                'status': StageStatus.SKIPPED.value,
                'detail': 'Security scanning not requested'
            }

        # STRICT VERDICT LOGIC & VERDICT GUARDS
        # Every required/executed stage participates: C1_syntax, C2_visible_tests, C2_user_tests, C6_security
        required_stages = []
        if 'C1_syntax' in stages:
            required_stages.append(stages['C1_syntax'])
        if req.run_project_tests and (collected_count > 0 or collection_error_count > 0 or project.get('test_files')) and 'C2_visible_tests' in stages:
            required_stages.append(stages['C2_visible_tests'])
        if req.run_user_tests and project.get('user_test_files') and 'C2_user_tests' in stages:
            required_stages.append(stages['C2_user_tests'])
        if req.run_security and 'C6_security' in stages:
            required_stages.append(stages['C6_security'])

        has_fail = any(s.get('status') == StageStatus.FAIL.value for s in required_stages)
        has_error = any(s.get('status') == StageStatus.ERROR.value for s in required_stages)
        all_passed = len(required_stages) > 0 and all(s.get('status') == StageStatus.PASS.value for s in required_stages)

        c2_proj_failed = stages.get('C2_visible_tests', {}).get('tests_failed', 0)
        c2_user_failed = stages.get('C2_user_tests', {}).get('failed', 0)
        total_test_failures = c2_proj_failed + c2_user_failed

        mismatch_unaccounted = False
        if not is_partial_suite and collected_count > 0:
            if total_accounted != collected_count and collection_error_count == 0:
                mismatch_unaccounted = True

        if count_mismatch or (collected_count < executed_count):
            verdict = 'INDETERMINATE'
            policy = 'REVIEW'
        elif total_test_failures > 0 or has_fail:
            verdict = 'REJECTED'
            policy = 'BLOCK'
        elif collection_error_count > 0 or mismatch_unaccounted or has_error:
            verdict = 'INDETERMINATE'
            policy = 'REVIEW'
        elif all_passed:
            if is_partial_suite:
                verdict = 'QUALIFIED_WITHIN_SCOPE'
                policy = 'REVIEW'
            else:
                verdict = 'QUALIFIED'
                policy = 'AUTO_APPROVE'
        else:
            verdict = 'INDETERMINATE'
            policy = 'REVIEW'

        # FINAL SAFETY INVARIANTS:
        if total_test_failures > 0 or (stages.get('C6_security', {}).get('status') == StageStatus.FAIL.value):
            verdict = 'REJECTED'
            policy = 'BLOCK'
        if collection_error_count > 0 or count_mismatch or (collected_count < executed_count) or (not is_partial_suite and collected_count > 0 and total_accounted != collected_count):
            if verdict in ('QUALIFIED', 'QUALIFIED_WITHIN_SCOPE'):
                verdict = 'INDETERMINATE'
                policy = 'REVIEW'

        record_event(run_id, 'DECISION', f'Verdict: {verdict} | Policy: {policy}')

        # Section 12 Required Diagnostic Output
        c2_report_status = stages.get('C2_visible_tests', {}).get('status', 'SKIPPED')
        print(f"COLLECTED: {collected_count}")
        print(f"COLLECTION_ERRORS: {collection_error_count}")
        print(f"SELECTED: {selected_count}")
        print(f"EXECUTED: {executed_count}")
        print(f"PASSED: {passed_count}")
        print(f"FAILED: {failed_count}")
        print(f"ERRORS: {error_count}")
        print(f"SKIPPED: {skipped_count}")
        print(f"C2: {c2_report_status}")
        print(f"FINAL_VERDICT: {verdict}")
        raw_junit_tc_count = getattr(test_result, 'raw_junit_testcase_count', executed_count + collection_error_count) if 'test_result' in locals() else (executed_count + collection_error_count)
        uniq_junit_tc_count = getattr(test_result, 'unique_junit_testcase_count', executed_count + collection_error_count) if 'test_result' in locals() else (executed_count + collection_error_count)
        print(f"raw_junit_testcase_count: {raw_junit_tc_count}")
        print(f"unique_junit_testcase_count: {uniq_junit_tc_count}")
        print(f"pytest_collection_count: {collected_count}")
        print(f"pytest_collection_error_count: {collection_error_count}")

        evidence = {
            'run_id': run_id,
            'project_id': project_id,
            'project_hash': project.get('project_hash', ''),
            'source_type': 'upload',
            'verification_mode': req.mode.value if hasattr(req.mode, 'value') else str(req.mode),
            'framework': project.get('framework', 'unknown'),
            'test_framework': project.get('framework', 'unknown'),
            'collected_count': collected_count,
            'collection_error_count': collection_error_count,
            'discovered_count': collected_count,
            'selected_count': selected_count,
            'executed_count': executed_count if 'executed_count' in locals() else 0,
            'passed_count': passed_count if 'passed_count' in locals() else 0,
            'failed_count': failed_count if 'failed_count' in locals() else 0,
            'error_count': error_count if 'error_count' in locals() else 0,
            'skipped_count': skipped_count if 'skipped_count' in locals() else 0,
            'collected_nodeids': collected_nodeids,
            'collection_error_nodeids': collection_error_nodeids,
            'discovered_test_nodeids': collected_nodeids,
            'selected_nodeids': selected_nodeids,
            'selected_test_nodeids': selected_nodeids,
            'executed_nodeids': executed_nodeids if 'executed_nodeids' in locals() else [],
            'executed_test_nodeids': executed_nodeids if 'executed_nodeids' in locals() else [],
            'skipped_nodeids': skipped_nodeids if 'skipped_nodeids' in locals() else [],
            'skipped_test_nodeids': skipped_nodeids if 'skipped_nodeids' in locals() else [],
            'failed_nodeids': failed_nodeids if 'failed_nodeids' in locals() else [],
            'failed_test_nodeids': failed_nodeids if 'failed_nodeids' in locals() else [],
            'error_nodeids': error_nodeids if 'error_nodeids' in locals() else [],
            'error_test_nodeids': error_nodeids if 'error_nodeids' in locals() else [],
            'discovery_command': discovery_cmd_str,
            'execution_command': cmd_str if 'cmd_str' in locals() else "",
            'security_findings': [f.to_dict() if hasattr(f, 'to_dict') else f for f in sec_findings],
            'security_table': [f.to_dict() if hasattr(f, 'to_dict') else f for f in sec_findings],
            'test_inventory': {
                'collected_count': collected_count,
                'collection_error_count': collection_error_count,
                'discovered_count': collected_count,
                'selected_count': selected_count,
                'executed_count': executed_count if 'executed_count' in locals() else 0,
                'passed_count': passed_count if 'passed_count' in locals() else 0,
                'failed_count': failed_count if 'failed_count' in locals() else 0,
                'error_count': error_count if 'error_count' in locals() else 0,
                'skipped_count': skipped_count if 'skipped_count' in locals() else 0,
                'project_tests': len(project.get('test_files', [])),
                'user_tests': len(project.get('user_test_files', []))
            },
            'project_test_discovery': project_test_discovery,
            'project_test_execution': project_test_execution,
            'project_test_inventory': project_test_execution,
            'custom_test_inventory': user_test_inventory,
            'test_command': test_command_info,
            'sandbox_used': True,
            'sandbox_image': docker_image,
            'sandbox_security_policy': {
                'network': 'NONE (--network none)',
                'filesystem': 'READ_ONLY_ROOTFS',
                'volume': '/workspace (ephemeral)',
                'tmpfs': ['/tmp:rw,noexec,nosuid,size=64m'],
                'caps': 'DROP ALL',
                'security_opt': 'no-new-privileges',
                'cpu_quota': '1.0',
                'memory_cap': '512m',
                'pids_limit': 50,
                'ulimits': ['nofile=1024:2048', 'fsize=50000000']
            },
            'stages': stages,
            'limitations': limitations,
            'verdict': verdict,
            'policy': policy,
            'mlverify': {
                'status': 'UNAVAILABLE',
                'explanation': 'MLVerify shadow-mode defect prediction is not run for standalone user project uploads.'
            }
        }

        report = {
            'report_id': f'rep_{run_id}',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'decision': {
                'technical_verdict': verdict,
                'release_policy': policy,
                'criteria_summary': {k: v['status'] for k, v in stages.items()}
            },
            'criteria': stages,
            'evidence': evidence
        }

        RUNS_STORE[run_id]['status'] = 'completed'
        RUNS_STORE[run_id]['technical_verdict'] = verdict
        RUNS_STORE[run_id]['release_policy'] = policy
        RUNS_STORE[run_id]['report'] = report

    except Exception as e:
        logger.exception('Project verification task error')
        RUNS_STORE[run_id]['status'] = 'failed'
        RUNS_STORE[run_id]['error'] = sanitize_path_str(str(e), str(project_dir))
        record_event(run_id, 'ERROR', sanitize_path_str(str(e), str(project_dir)))
    finally:
        RUNS_STORE[run_id]['updated_at'] = datetime.now(timezone.utc).isoformat()

@app.post("/api/projects/{project_id}/verify", status_code=202)
async def verify_project(
    project_id: str,
    req: ProjectVerifyRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    rate_limiter.enforce(api_key or "anon")
    if project_id not in PROJECTS_STORE:
        raise HTTPException(status_code=404, detail="Project not found")

    if not is_docker_available():
        diag = check_sandbox_health()
        reason = diag.get("failure_reason") or "Docker daemon is unavailable."
        raise HTTPException(
            status_code=503,
            detail=f"Sandbox unavailable. {reason} A.I.R.A. cannot execute real project verification without an isolated container runtime. This is not a demo — your code requires real execution."
        )

    run_id = f"run_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    RUNS_STORE[run_id] = {
        "run_id": run_id,
        "status": "queued",
        "tier": req.tier,
        "project_id": project_id,
        "created_at": now_iso,
        "updated_at": now_iso
    }

    background_tasks.add_task(execute_project_verification_job, run_id, project_id, req)

    return {"run_id": run_id, "status": "queued"}

@app.get("/api/projects/{project_id}")
async def get_project(
    project_id: str,
    api_key: str = Depends(verify_api_key)
):
    if project_id not in PROJECTS_STORE:
        raise HTTPException(status_code=404, detail="Project not found")
    return PROJECTS_STORE[project_id]

@app.delete("/api/projects/{project_id}")
async def delete_project(
    project_id: str,
    api_key: str = Depends(verify_api_key)
):
    if project_id not in PROJECTS_STORE:
        raise HTTPException(status_code=404, detail="Project not found")

    project = PROJECTS_STORE[project_id]
    extract_dir = project.get("extract_dir", project.get("root_dir"))
    if extract_dir:
        secure_cleanup(Path(extract_dir))
    del PROJECTS_STORE[project_id]

    return {"message": f"Project {project_id} deleted"}

# ============================================================================
# Static Files & Frontend SPA Mount
# ============================================================================

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    @app.get("/verify", include_in_schema=False)
    @app.get("/demo", include_in_schema=False)
    def serve_frontend():
        index_file = WEB_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return JSONResponse({"message": "A.I.R.A. API Service is running. Frontend assets not yet compiled."})
