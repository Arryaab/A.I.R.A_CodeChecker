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

from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field

from aegis.execution.sandbox import is_docker_available

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Aegis AI Change Verification Service API",
    version="1.0.0",
    description="Production REST API for autonomous AI code change verification, security scanning, and policy gating."
)

class VerificationRequest(BaseModel):
    repository: str = Field(default=".", description="Path or identifier of repository to verify")
    base: str = Field(default="HEAD~1", description="Baseline commit or ref")
    head: str = Field(default="HEAD", description="Proposed commit or ref")
    diff: Optional[str] = Field(default=None, description="Optional unified diff patch content")
    tier: str = Field(default="auto", description="Verification tier: fast, standard, deep, auto")
    unsafe_local: bool = Field(default=False, description="Explicitly allow local non-sandboxed execution")

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

def record_event(run_id: str, stage: str, message: str) -> None:
    if run_id not in RUN_EVENTS:
        RUN_EVENTS[run_id] = []
    RUN_EVENTS[run_id].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "message": message
    })

def execute_verification_job(run_id: str, req: VerificationRequest) -> None:
    RUNS_STORE[run_id]["status"] = "running"
    RUNS_STORE[run_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    record_event(run_id, "INDEXING", f"Starting repository verification for {req.base}..{req.head}")

    try:
        repo_dir = Path(req.repository).resolve()
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
        if req.unsafe_local:
            cmd.append("--unsafe-local")

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


@app.get("/v1/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "aegis-verifier",
        "version": "1.0.0",
        "docker_available": is_docker_available(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/v1/verifications", status_code=status.HTTP_202_ACCEPTED)
def create_verification(
    req: VerificationRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
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
def get_verification_status(run_id: str) -> Dict[str, Any]:
    if run_id not in RUNS_STORE:
        # Check if exists on filesystem
        runs_dir = Path(".aegis/runs") / run_id
        report_file = runs_dir / "report.json"
        if report_file.exists():
            data = json.loads(report_file.read_text(encoding="utf-8"))
            return {
                "run_id": run_id,
                "status": "completed",
                "tier": data.get("verification", {}).get("tier"),
                "technical_verdict": data.get("decision", {}).get("technical_verdict"),
                "release_policy": data.get("decision", {}).get("release_policy"),
                "created_at": data.get("timestamp"),
                "updated_at": data.get("timestamp"),
            }
        raise HTTPException(status_code=404, detail=f"Verification run '{run_id}' not found")

    item = RUNS_STORE[run_id]
    return {
        "run_id": item["run_id"],
        "status": item["status"],
        "tier": item["tier"],
        "technical_verdict": item.get("technical_verdict"),
        "release_policy": item.get("release_policy"),
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
        "error": item.get("error")
    }

@app.get("/v1/verifications/{run_id}/report")
def get_verification_report(run_id: str) -> Dict[str, Any]:
    if run_id in RUNS_STORE and "report" in RUNS_STORE[run_id]:
        return RUNS_STORE[run_id]["report"]

    runs_dir = Path(".aegis/runs") / run_id
    report_file = runs_dir / "report.json"
    if report_file.exists():
        return json.loads(report_file.read_text(encoding="utf-8"))

    raise HTTPException(status_code=404, detail=f"Report for run '{run_id}' not found or still processing")

@app.get("/v1/verifications/{run_id}/events")
def get_verification_events(run_id: str) -> Dict[str, Any]:
    events = RUN_EVENTS.get(run_id, [])
    return {
        "run_id": run_id,
        "events": events
    }

def create_app() -> FastAPI:
    return app
