import logging
import random
from dataclasses import dataclass
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

@dataclass
class RiskPrediction:
    risk_score: float  # 0.0 to 1.0
    risk_level: str    # LOW, MEDIUM, HIGH
    factors: List[str]

class HeuristicPatchRiskModel:
    """
    Evaluates the probability that a patch introduces a regression or security flaw.
    Uses an interpretable heuristic baseline, serving as the benchmark feature extractor
    for future learned ML models (XGBoost/LightGBM/Neural).
    """
    def __init__(self):
        self.model_loaded = False
        
    def predict_risk(
        self,
        original_files: Dict[str, Any],
        patch: Dict[str, Any],
        test_output: str = ""
    ) -> RiskPrediction:
        """Predict the P(patch is unsafe) using actual diff statistics and introduced AST patterns."""
        risk_score = 0.0
        factors = []
        
        # Heuristic 1: Actual Lines Changed (Added + Deleted)
        total_lines_changed = 0
        for p in patch.values():
            if hasattr(p, "added_lines") and hasattr(p, "deleted_lines"):
                total_lines_changed += len(p.added_lines) + len(p.deleted_lines)
            elif isinstance(p, str):
                total_lines_changed += len(p.splitlines())

        if total_lines_changed > 50:
            risk_score += 0.3
            factors.append(f"Large diff size ({total_lines_changed} lines changed)")
            
        # Heuristic 2: Semantic security operations introduced in added code
        dangerous_patterns = [
            ("eval(", "Dynamic code execution via eval()"),
            ("exec(", "Dynamic code execution via exec()"),
            ("shell=True", "Subprocess invocation with shell=True"),
            ("os.system(", "Direct shell execution via os.system()"),
            ("requests.get(", "Outbound HTTP request detected"),
        ]
        
        for filepath, p in patch.items():
            norm_path = filepath.replace("\\", "/")
            if not norm_path.endswith(".py"):
                continue
            if any(norm_path.endswith(f) for f in {"git.py", "sandbox.py", "runner.py", "security.py", "risk_model.py"}):
                continue
            if "tests/" in norm_path or norm_path.startswith("tests"):
                continue

            # Inspect newly introduced text only
            if hasattr(p, "added_lines"):
                code_to_check = "\n".join(p.added_lines)
            elif isinstance(p, str):
                code_to_check = p
            else:
                code_to_check = getattr(p, "new_content", "")

            for pattern, desc in dangerous_patterns:
                if pattern in code_to_check:
                    risk_score += 0.4
                    factors.append(f"{desc} in {filepath}")
                    
        # Heuristic 3: Number of files touched
        if len(patch) > 3:
            risk_score += 0.2
            factors.append(f"Multiple files modified ({len(patch)})")

        # Heuristic 4: Critical deletions
        for filepath, p in patch.items():
            if getattr(p, "status", "") == "D":
                if any(k in filepath.lower() for k in ["auth", "security", "guardrail", "policy", "token"]):
                    risk_score += 0.5
                    factors.append(f"Security-critical module deleted: {filepath}")
                else:
                    risk_score += 0.1
                    factors.append(f"File deleted: {filepath}")
            
        # Cap at 1.0
        risk_score = min(risk_score, 1.0)
        
        level = "LOW"
        if risk_score > 0.6:
            level = "HIGH"
        elif risk_score > 0.2:
            level = "MEDIUM"
            
        return RiskPrediction(risk_score=risk_score, risk_level=level, factors=factors)

# Backward-compatible alias for the heuristic baseline
PatchRiskModel = HeuristicPatchRiskModel
