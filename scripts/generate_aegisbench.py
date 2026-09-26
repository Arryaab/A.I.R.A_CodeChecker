import os
from pathlib import Path

CATEGORIES = [
    "01_core_logic",
    "02_api_endpoints",
    "03_database_transactions",
    "04_security_auth",
    "05_concurrency_async",
    "06_data_processing",
    "07_ml_training_leakage",
    "08_ml_inference_latency",
    "09_system_integration",
    "10_regression_overfitting"
]

def generate_benchmarks():
    base_dir = Path("benchmarks/aegisbench_v1")
    base_dir.mkdir(parents=True, exist_ok=True)
    
    count = 1
    for category in CATEGORIES:
        for i in range(1, 11):
            bug_id = f"ab_{count:03d}_{category}"
            bug_dir = base_dir / bug_id
            bug_dir.mkdir(exist_ok=True)
            
            # Create standard files
            (bug_dir / "solution.py").write_text("# TODO: Implement the broken logic here\n")
            
            tests_dir = bug_dir / "tests"
            tests_dir.mkdir(exist_ok=True)
            (tests_dir / "test_solution.py").write_text("def test_visible():\n    assert False, 'Not implemented'\n")
            
            hidden_tests_dir = bug_dir / "hidden_tests"
            hidden_tests_dir.mkdir(exist_ok=True)
            (hidden_tests_dir / "test_hidden.py").write_text("def test_hidden():\n    assert False, 'Not implemented'\n")
            
            metadata = f'{{\n  "id": "{bug_id}",\n  "category": "{category.split("_", 1)[1]}",\n  "difficulty": "medium",\n  "description": "TODO"\n}}'
            (bug_dir / "metadata.json").write_text(metadata)
            
            count += 1
            
    print(f"Generated 100 benchmark scaffolds in {base_dir}")

if __name__ == "__main__":
    generate_benchmarks()
