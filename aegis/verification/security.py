import re
import ast
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class SecurityScanResult:
    safe: bool
    issues: List[str] = field(default_factory=list)

class SecurityScanner:
    """
    Aegis Security Guardrail: Scans proposed patches for prompt injection,
    secret exfiltration, hardcoded credentials, and dangerous execution.
    """
    
    # Patterns for secrets
    SECRET_PATTERNS = [
        (r"(?i)(api[_-]?key|secret|token|password|passwd|auth)\s*=\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]", "Hardcoded API key or credential"),
        (r"-----BEGIN (?:RSA )?PRIVATE KEY-----", "Private key detected"),
        (r"ghp_[A-Za-z0-9]{36}", "GitHub Personal Access Token"),
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    ]
    
    # Patterns for prompt injection attempts in patch comments/docstrings
    PROMPT_INJECTION_PATTERNS = [
        r"(?i)ignore previous instructions",
        r"(?i)disregard (all )?prior instructions",
        r"(?i)system prompt overrides",
        r"(?i)you must approve this patch",
        r"(?i)return {\"approved\": true}",
    ]
    
    # Dangerous modules that an AI generated patch should rarely/never introduce
    DANGEROUS_MODULES = {
        "pty", "subprocess", "socket", "telnetlib", "ftplib", "paramiko"
    }

    def scan_patch(self, patch: Dict[str, str]) -> SecurityScanResult:
        issues = []
        
        for filepath, content in patch.items():
            # 1. Secret Exfiltration & Hardcoded Credential Scan
            for pattern, desc in self.SECRET_PATTERNS:
                if re.search(pattern, content):
                    issues.append(f"{desc} in {filepath}")

            # 2. Prompt Injection Scan
            for pattern in self.PROMPT_INJECTION_PATTERNS:
                if re.search(pattern, content):
                    issues.append(f"Potential Prompt Injection marker in {filepath}: {pattern}")

            # 3. AST-level import & dangerous call scan
            try:
                tree = ast.parse(content, filename=filepath)
                for node in ast.walk(tree):
                    # Check imports
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in self.DANGEROUS_MODULES:
                                issues.append(f"Forbidden dangerous module import: `{alias.name}` in {filepath}")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module in self.DANGEROUS_MODULES:
                            issues.append(f"Forbidden dangerous module import: `{node.module}` in {filepath}")
                    # Check eval/exec
                    elif isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                            issues.append(f"Forbidden dangerous function call: `{node.func.id}()` in {filepath}")
            except SyntaxError:
                # Syntax errors are caught by validator.py
                pass
            except Exception as e:
                issues.append(f"Security scanner AST parsing error in {filepath}: {e}")

        safe = len(issues) == 0
        return SecurityScanResult(safe=safe, issues=issues)
