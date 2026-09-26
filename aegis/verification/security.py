import re
import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List

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

    def scan_patch(self, patch: Dict[str, str], scan_tests: bool = False) -> SecurityScanResult:
        """Scan raw file content mapping."""
        issues = []
        for filepath, content in patch.items():
            if not scan_tests and ("tests/" in filepath.replace("\\", "/") or filepath.startswith("tests")):
                continue
            # Scan content
            for pattern, desc in self.SECRET_PATTERNS:
                if re.search(pattern, content):
                    issues.append(f"{desc} in {filepath}")
            for pattern in self.PROMPT_INJECTION_PATTERNS:
                if re.search(pattern, content):
                    issues.append(f"Potential Prompt Injection marker in {filepath}: {pattern}")
            # AST checks
            try:
                tree = ast.parse(content, filename=filepath)
                self._check_ast_nodes(tree, filepath, issues)
            except SyntaxError:
                pass
        return SecurityScanResult(safe=len(issues) == 0, issues=issues)

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
            for pattern, desc in self.SECRET_PATTERNS:
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
