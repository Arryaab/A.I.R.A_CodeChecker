# AegisBench Task Specification & Provenance Schema

To prevent benchmark leakage, reward hacking, and unverified task definitions (as observed in SWE-Bench Pro Verified and SWE-Gate), every benchmark task in AegisBench conforms to this rigorous schema.

## Directory Structure per Task
```text
task_id/
├── metadata.json         # Formal task definition & difficulty
├── provenance.json       # Source repository, commit SHA, issue link, license
├── problem.md            # Natural language problem statement given to the agent
├── constraints.yaml      # Non-functional review constraints (API stability, latency, etc.)
├── solution.py           # Buggy source file(s)
├── tests/                # Visible test suite provided to the agent
│   └── test_solution.py
├── hidden_tests/         # Hidden adversarial test suite for verification
│   └── test_hidden.py
└── oracle_patch.diff     # Gold standard human patch that resolves the issue
```

## Schemas

### `metadata.json`
```json
{
  "id": "ab_001_wrong_operator",
  "category": "core_logic",
  "difficulty": "easy",
  "description": "Fix arithmetic precedence in calculation engine",
  "failure_type": "WrongOperator",
  "expected_behavior": "Returns mathematically correct order of operations",
  "tags": ["logic", "arithmetic", "unit-test"]
}
```

### `provenance.json`
```json
{
  "source": "curated_open_source",
  "repository": "https://github.com/...",
  "base_commit": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "issue_id": "#104",
  "license": "MIT",
  "verified_by": "human_expert",
  "verification_date": "2026-09-26"
}
```

### `constraints.yaml`
```yaml
constraints:
  public_api_unchanged: true
  max_files_modified: 2
  forbidden_modules:
    - subprocess
    - socket
  max_latency_regression_pct: 10
```
