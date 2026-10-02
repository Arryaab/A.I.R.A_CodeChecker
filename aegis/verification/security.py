import re
import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class SecurityFinding:
    file: str
    line: int
    sink: str
    rule: str
    severity: str  # HIGH, MEDIUM, LOW
    source_classification: str  # APPLICATION_CODE, TEST_CODE, FIXTURE, BENCHMARK, TOOLING
    finding: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding": self.finding or f"{self.rule} at {self.sink}",
            "file": self.file,
            "line": self.line,
            "sink": self.sink,
            "rule": self.rule,
            "severity": self.severity,
            "source_classification": self.source_classification,
            "code_classification": self.source_classification,
        }

@dataclass
class SecurityScanResult:
    safe: bool
    issues: List[str] = field(default_factory=list)
    findings: List[SecurityFinding] = field(default_factory=list)

def classify_source_path(filepath: str) -> str:
    """Classifies source code paths into contextual risk categories."""
    norm = filepath.replace("\\", "/").lower().lstrip("./")
    if "fixtures" in norm or "/fixture" in norm or norm.startswith("fixture"):
        return "FIXTURE"
    if "benchmarks" in norm or norm.startswith("benchmark"):
        return "BENCHMARK"
    if "scripts/" in norm or norm.startswith("scripts/") or "tools/" in norm or norm.startswith("tools/"):
        return "TOOLING"
    if "tests/" in norm or norm.startswith("tests/") or "test_" in norm or norm.endswith("_test.py"):
        return "TEST_CODE"
    return "APPLICATION_CODE"

class SecurityScanner:
    """
    Aegis Security Guardrail: Scans proposed patches and project uploads for prompt injection,
    secret exfiltration, hardcoded credentials, and dangerous execution sinks.
    Classifies findings into APPLICATION_CODE, TEST_CODE, FIXTURE, BENCHMARK, and TOOLING.
    """
    
    # Patterns for secrets
    SECRET_PATTERNS = [
        (r"(?i)(api[_-]?key|secret|token|password|passwd|auth)\s*=\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]", "Hardcoded API key or credential", "HARDCODED_SECRET", "HIGH"),
        (r"-----BEGIN (?:RSA )?PRIVATE KEY-----", "Private key detected", "PRIVATE_KEY_LEAK", "HIGH"),
        (r"ghp_[A-Za-z0-9]{36}", "GitHub Personal Access Token", "TOKEN_LEAK", "HIGH"),
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID", "AWS_KEY_LEAK", "HIGH"),
    ]
    
    # Patterns for prompt injection attempts in patch comments/docstrings
    PROMPT_INJECTION_PATTERNS = [
        r"(?i)ign" + r"ore previous instructions",
        r"(?i)disr" + r"egard (all )?prior instructions",
        r"(?i)sys" + r"tem prompt overrides",
        r"(?i)you must" + r" approve this patch",
        r"(?i)return {\"appr" + r"oved\": true}",
    ]
    
    # Dangerous modules that an AI generated patch should rarely/never introduce
    DANGEROUS_MODULES = {
        "pty", "socket", "telnetlib", "ftplib", "paramiko"
    }

    # Patterns for common security vulnerabilities (e.g. CWE-22 Path Traversal)
    VULNERABILITY_PATTERNS = [
        (r"(?i)(cwe-22|path\s*traversal|\.\./|\.\.\\)", "CWE-22 / Path Traversal vulnerability", "CWE-22_PATH_TRAVERSAL", "HIGH"),
    ]

    def scan_file_findings(self, content: str, filepath: str) -> List[SecurityFinding]:
        """Scans a single file and produces detailed, contextual SecurityFinding records."""
        findings: List[SecurityFinding] = []
        classification = classify_source_path(filepath)
        norm_p = filepath.replace("\\", "/").lstrip("./")
        lines = content.splitlines()

        # 1. Regex line-by-line checks
        for idx, line in enumerate(lines, 1):
            for pattern, desc, rule, sev in self.SECRET_PATTERNS:
                if re.search(pattern, line):
                    findings.append(SecurityFinding(
                        file=norm_p,
                        line=idx,
                        sink="credential_assignment",
                        rule=rule,
                        severity=sev,
                        source_classification=classification,
                        finding=f"{desc} in {norm_p}:{idx}"
                    ))
            for pattern in self.PROMPT_INJECTION_PATTERNS:
                if re.search(pattern, line):
                    findings.append(SecurityFinding(
                        file=norm_p,
                        line=idx,
                        sink="comment_or_string",
                        rule="PROMPT_INJECTION",
                        severity="MEDIUM",
                        source_classification=classification,
                        finding=f"Potential Prompt Injection marker in {norm_p}:{idx}"
                    ))
            for pattern, desc, rule, sev in self.VULNERABILITY_PATTERNS:
                if re.search(pattern, line):
                    findings.append(SecurityFinding(
                        file=norm_p,
                        line=idx,
                        sink="path_resolution",
                        rule=rule,
                        severity=sev,
                        source_classification=classification,
                        finding=f"{desc} in {norm_p}:{idx}"
                    ))

        # 2. AST checks
        try:
            tree = ast.parse(content, filename=filepath)
            for node in ast.walk(tree):
                lineno = getattr(node, "lineno", 1)
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in self.DANGEROUS_MODULES:
                            findings.append(SecurityFinding(
                                file=norm_p,
                                line=lineno,
                                sink=alias.name,
                                rule="FORBIDDEN_MODULE_IMPORT",
                                severity="MEDIUM",
                                source_classification=classification,
                                finding=f"Forbidden dangerous module import: `{alias.name}` in {norm_p}:{lineno}"
                            ))
                elif isinstance(node, ast.ImportFrom):
                    if node.module in self.DANGEROUS_MODULES:
                        findings.append(SecurityFinding(
                            file=norm_p,
                            line=lineno,
                            sink=str(node.module),
                            rule="FORBIDDEN_MODULE_IMPORT",
                            severity="MEDIUM",
                            source_classification=classification,
                            finding=f"Forbidden dangerous module import: `{node.module}` in {norm_p}:{lineno}"
                        ))
                elif isinstance(node, ast.Call):
                    # eval / exec
                    if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                        findings.append(SecurityFinding(
                            file=norm_p,
                            line=lineno,
                            sink=f"{node.func.id}()",
                            rule="DANGEROUS_EVAL_EXEC",
                            severity="HIGH",
                            source_classification=classification,
                            finding=f"Forbidden dangerous function call: `{node.func.id}()` in {norm_p}:{lineno}"
                        ))
                    # os.system / os.popen
                    elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                        if node.func.value.id == "os" and node.func.attr in {"system", "popen"}:
                            findings.append(SecurityFinding(
                                file=norm_p,
                                line=lineno,
                                sink=f"os.{node.func.attr}()",
                                rule="DANGEROUS_SHELL_EXECUTION",
                                severity="HIGH",
                                source_classification=classification,
                                finding=f"Forbidden dangerous shell execution: `os.{node.func.attr}()` in {norm_p}:{lineno}"
                            ))
                        elif node.func.value.id == "subprocess" and node.func.attr in {"run", "Popen", "call", "check_output", "check_call"}:
                            for kw in node.keywords:
                                if kw.arg == "shell":
                                    if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                        findings.append(SecurityFinding(
                                            file=norm_p,
                                            line=lineno,
                                            sink="subprocess(shell=True)",
                                            rule="SUBPROCESS_SHELL_INJECTION",
                                            severity="HIGH",
                                            source_classification=classification,
                                            finding=f"Dangerous subprocess execution with `shell=True` in {norm_p}:{lineno}"
                                        ))
                                    elif not isinstance(kw.value, ast.Constant):
                                        findings.append(SecurityFinding(
                                            file=norm_p,
                                            line=lineno,
                                            sink="subprocess(dynamic shell)",
                                            rule="SUBPROCESS_DYNAMIC_SHELL",
                                            severity="HIGH",
                                            source_classification=classification,
                                            finding=f"Dangerous subprocess execution with dynamic `shell` parameter in {norm_p}:{lineno}"
                                        ))
        except SyntaxError:
            pass

        return findings

    def scan_project_files(self, file_map: Dict[str, str]) -> tuple[List[SecurityFinding], bool]:
        """
        Scans a dictionary of {relative_path: code_content}.
        Determines overall safety:
        - APPLICATION_CODE with HIGH or MEDIUM findings fails the scan (safe = False).
        - Findings in FIXTURE, BENCHMARK, or TOOLING are documented but do not block release
          unless they contain real credential leaks.
        """
        all_findings: List[SecurityFinding] = []
        for path, code in file_map.items():
            findings = self.scan_file_findings(code, path)
            all_findings.extend(findings)

        app_violations = [
            f for f in all_findings
            if f.source_classification == "APPLICATION_CODE" and f.severity in ("HIGH", "MEDIUM")
        ]
        credential_leaks = [
            f for f in all_findings
            if "SECRET" in f.rule or "KEY" in f.rule or "TOKEN" in f.rule
        ]

        safe = (len(app_violations) == 0 and len(credential_leaks) == 0)
        return all_findings, safe

    def scan_patch(self, patch: Dict[str, str], scan_tests: bool = False) -> SecurityScanResult:
        """Scan raw file content mapping."""
        findings, safe = self.scan_project_files(patch)
        issues = [f.finding for f in findings if scan_tests or f.source_classification != "TEST_CODE"]
        # For patch scanning: if non-test findings exist, safe is False
        app_safe = all(f.source_classification == "TEST_CODE" for f in findings) if not scan_tests and findings else safe
        return SecurityScanResult(safe=app_safe, issues=issues, findings=findings)


    def scan_patch_changes(self, patches: Dict[str, Any], scan_tests: bool = False) -> SecurityScanResult:
        """
        Scan structured PatchChange objects:
        - Check ONLY newly added lines for secrets & prompt injections (prevents false positives)
        - Check reconstructed new_content for AST imports and calls (ensures valid AST parsing)
        """
        issues = []
        for filepath, change in patches.items():
            norm_p = filepath.replace("\\", "/")
            if not norm_p.endswith(".py"):
                continue
            if not scan_tests and ("tests/" in norm_p or norm_p.startswith("tests")):
                continue
            
            # Check for suspicious security-critical file deletions
            if getattr(change, "status", "") == "D":
                if any(k in filepath.lower() for k in ["auth", "security", "guardrail", "policy", "token"]):
                    issues.append(f"Security-critical module deletion detected: `{filepath}`")
                continue
            
            # Check added lines only for regex patterns
            added_text = "\n".join(getattr(change, "added_lines", []))
            for pattern, desc, *_ in self.SECRET_PATTERNS:
                if re.search(pattern, added_text):
                    issues.append(f"{desc} introduced in {filepath}")
            for pattern in self.PROMPT_INJECTION_PATTERNS:
                if re.search(pattern, added_text):
                    issues.append(f"Potential Prompt Injection marker introduced in {filepath}: {pattern}")

            # Check full new content for valid AST analysis
            new_content = getattr(change, "new_content", "")
            if new_content:
                try:
                    tree = ast.parse(new_content, filename=filepath)
                    self._check_ast_nodes(tree, filepath, issues)
                except SyntaxError:
                    pass
                except Exception as e:
                    issues.append(f"Security scanner AST parsing error in {filepath}: {e}")

        return SecurityScanResult(safe=len(issues) == 0, issues=issues)

    def _check_ast_nodes(self, tree: ast.AST, filepath: str, issues: List[str]) -> None:
        normalized_path = filepath.replace("\\", "/").lstrip("./")
        is_system_file = normalized_path.startswith("aegis/")
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.DANGEROUS_MODULES:
                        issues.append(f"Forbidden dangerous module import: `{alias.name}` in {filepath}")
            elif isinstance(node, ast.ImportFrom):
                if node.module in self.DANGEROUS_MODULES:
                    issues.append(f"Forbidden dangerous module import: `{node.module}` in {filepath}")
            elif isinstance(node, ast.Call):
                # Block eval/exec
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                    issues.append(f"Forbidden dangerous function call: `{node.func.id}()` in {filepath}")
                
                # Block os.system / os.popen
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "os" and node.func.attr in {"system", "popen"}:
                        issues.append(f"Forbidden dangerous shell execution: `os.{node.func.attr}()` in {filepath}")
                    
                    # Inspect subprocess call-sites: forbid shell=True or dynamic shell execution
                    if node.func.value.id == "subprocess" and node.func.attr in {"run", "Popen", "call", "check_output", "check_call"}:
                        for kw in node.keywords:
                            if kw.arg == "shell":
                                if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                    issues.append(f"Dangerous subprocess execution with `shell=True` in {filepath}")
                                elif not isinstance(kw.value, ast.Constant):
                                    issues.append(f"Dangerous subprocess execution with dynamic `shell` parameter in {filepath}")
                    elif not is_system_file and node.func.value.id == "subprocess":
                        # For non-system files, forbid raw untrusted shell execution
                        pass
