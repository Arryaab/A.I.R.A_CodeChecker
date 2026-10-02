from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class VerificationMode(str, Enum):
    PROJECT = 'PROJECT'
    PATCH = 'PATCH'

class StageStatus(str, Enum):
    PASS = 'PASS'
    FAIL = 'FAIL'
    SKIPPED = 'SKIPPED'
    NOT_AVAILABLE = 'NOT_AVAILABLE'
    NOT_SUPPORTED = 'NOT_SUPPORTED'
    ERROR = 'ERROR'

class ProjectInfo(BaseModel):
    project_id: str
    project_hash: str
    source_type: str  # 'upload'
    framework: str
    framework_confidence: float
    test_files: List[str]
    discovered_tests: List[str] = Field(default_factory=list)
    discovered_test_nodeids: List[str] = Field(default_factory=list)
    discovered_count: int = 0
    total_files: int
    total_bytes: int
    created_at: str
    status: str  # 'ready', 'processing', 'error'

class ProjectVerifyRequest(BaseModel):
    mode: VerificationMode = Field(default=VerificationMode.PROJECT)
    tier: str = Field(default='standard')
    run_user_tests: bool = Field(default=True)
    run_project_tests: bool = Field(default=True)
    selected_tests: Optional[List[str]] = Field(default=None, description='Explicit test subset. If None, runs all discovered tests.')
    run_security: bool = Field(default=True)
    run_mutation: bool = Field(default=False)
    diff: Optional[str] = Field(default=None, description='Unified diff for PATCH mode')

class VerificationEvidence(BaseModel):
    project_id: str
    project_hash: str
    source_type: str
    verification_mode: str
    environment: dict
    framework: str
    test_inventory: dict
    user_test_inventory: Optional[dict] = None
    discovered_test_nodeids: List[str] = Field(default_factory=list)
    selected_test_nodeids: List[str] = Field(default_factory=list)
    executed_test_nodeids: List[str] = Field(default_factory=list)
    skipped_test_nodeids: List[str] = Field(default_factory=list)
    failed_test_nodeids: List[str] = Field(default_factory=list)
    error_test_nodeids: List[str] = Field(default_factory=list)
    discovery_command: Optional[str] = None
    execution_command: Optional[str] = None
    security_findings: List[dict] = Field(default_factory=list)
    limitations: List[str]
    stages: dict  # C1-C6 with StageStatus values
