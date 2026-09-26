import json
import logging
import re
from dataclasses import dataclass
from typing import Dict, Any, List

from aegis.llm import LLMProvider, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

@dataclass
class Plan:
    strategy: str
    files_to_modify: List[str]

@dataclass
class CriticFeedback:
    approved: bool
    feedback: str

class PlannerAgent:
    """Aegis Planner: Determines the strategy and files to modify."""
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.system = "You are the Aegis Planner. Analyze the repository map and test failures, and create a repair plan. Return ONLY JSON wrapped in ```json fences."

    def plan(self, repo_map: str, test_output: str) -> Plan:
        prompt = (
            f"Repository Map:\n```\n{repo_map}\n```\n\n"
            f"Test Failures:\n```\n{test_output}\n```\n\n"
            "Return a JSON plan with 'strategy' (string) and 'files_to_modify' (list of strings)."
        )
        try:
            res = self.provider.ask(prompt, system=self.system)
            content = self._extract_json(res.content)
            data = json.loads(content)
            return Plan(
                strategy=data.get("strategy", "Unknown strategy"),
                files_to_modify=data.get("files_to_modify", [])
            )
        except Exception as e:
            logger.warning(f"Planner failed: {e}")
            return Plan(strategy="Fallback to default file", files_to_modify=[])

    def _extract_json(self, text: str) -> str:
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
        return match.group(1).strip() if match else text

class CriticAgent:
    """Aegis Critic: Attempts to disprove the patch."""
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.system = "You are the Aegis Critic. Review the proposed patch against the original code. Check for logic regressions, security issues, and correctness. Return ONLY JSON wrapped in ```json fences."

    def critique(self, original_files: Dict[str, str], patch: Dict[str, str], test_output: str) -> CriticFeedback:
        prompt = "Original Files:\n"
        for filepath, code in original_files.items():
            prompt += f"File: `{filepath}`\n```python\n{code}\n```\n\n"
        
        prompt += (
            f"Proposed Patch:\n```json\n{json.dumps(patch, indent=2)}\n```\n\n"
            f"Resulting Test Output:\n```\n{test_output}\n```\n\n"
            "If the patch successfully fixes the issue and introduces no new regressions, set 'approved': true.\n"
            "Otherwise, set 'approved': false and provide 'feedback'."
        )
        try:
            res = self.provider.ask(prompt, system=self.system)
            content = self._extract_json(res.content)
            data = json.loads(content)
            return CriticFeedback(
                approved=data.get("approved", False),
                feedback=data.get("feedback", "No feedback provided")
            )
        except Exception as e:
            logger.warning(f"Critic failed: {e}")
            return CriticFeedback(approved=False, feedback=f"Critic verification failed: {e}. Defaulting to REJECT.")

    def _extract_json(self, text: str) -> str:
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
        return match.group(1).strip() if match else text
