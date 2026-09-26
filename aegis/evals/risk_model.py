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

class PatchRiskModel:
    """
    Evaluates the probability that a patch introduces a regression or security flaw.
    Currently uses heuristic features, designed to be replaced by a PyTorch/xgboost model.
    """
    def __init__(self):
        self.model_loaded = False
        
    def predict_risk(self, original_files: Dict[str, str], patch: Dict[str, str], test_output: str) -> RiskPrediction:
        """Predict the P(patch is unsafe)"""
        risk_score = 0.0
        factors = []
        
        # Heuristic 1: Lines changed
        total_lines_changed = sum(len(code.splitlines()) for code in patch.values())
        if total_lines_changed > 50:
            risk_score += 0.3
            factors.append("Large diff size (>50 lines)")
            
        # Heuristic 2: Security sensitive operations
        security_keywords = ["eval", "exec", "subprocess", "os.system", "open(", "requests.get"]
        for filepath, code in patch.items():
            for kw in security_keywords:
                if kw in code:
                    risk_score += 0.4
                    factors.append(f"Security-sensitive keyword detected: {kw}")
                    
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
