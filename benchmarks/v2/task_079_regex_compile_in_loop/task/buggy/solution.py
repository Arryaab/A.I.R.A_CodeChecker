import re
from typing import List

def extract_log_severities(lines: List[str]) -> List[str]:
    """Extracts severity tags [INFO], [WARN], [ERROR] from log stream."""
    severities = []
    # BUG: Compiles regex on every single line inside the loop
    for line in lines:
        pattern = re.compile(r"\[(INFO|WARN|ERROR)\]")
        match = pattern.search(line)
        if match:
            severities.append(match.group(1))
    return severities
