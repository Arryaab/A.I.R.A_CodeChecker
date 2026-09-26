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
        
    def predict_risk(self, original_files: Dict[str, str], patch: Dict[str, str], test_output: str) -> RiskPrediction:
        """Predict the P(patch is unsafe) using heuristic baseline features."""
        risk_score = 0.0
        factors = []
        
        # Heuristic 1: Lines changed
        total_lines_changed = sum(len(code.splitlines()) for code in patch.values())
        if total_lines_changed > 50:
            risk_score += 0.3
            factors.append("Large diff size (>50 lines)")
            
        # Heuristic 2: Semantic security operations
        dangerous_patterns = [
            ("eval(", "Dynamic code execution via eval()"),
            ("exec(", "Dynamic code execution via exec()"),
            ("shell=True", "Subprocess invocation with shell=True"),
            ("os.system(", "Direct shell execution via os.system()"),
            ("requests.get(", "Outbound HTTP request detected"),
        ]
        
        for filepath, code in patch.items():
            # Skip test files and system infrastructure files
            norm_path = filepath.replace("\\", "/")
            if any(norm_path.endswith(f) for f in {"git.py", "sandbox.py", "runner.py", "security.py"}):
                continue
            if "tests/" in norm_path or norm_path.startswith("tests"):
                continue

            for pattern, desc in dangerous_patterns:
                if pattern in code:
                    risk_score += 0.4
                    factors.append(f"{desc} in {filepath}")
                    
        # Heuristic 3: Number of files touched
        if len(patch) > 3:
            risk_score += 0.2
            factors.append(f"Multiple files modified ({len(patch)})")
            
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
