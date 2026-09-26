from __future__ import annotations

import json
from pathlib import Path
from aegis.evals.benchmark import Benchmark

def test_benchmark_loading(tmp_path):
    bench_dir = tmp_path / "my_bench"
    bench_dir.mkdir()
    
    bug1 = bench_dir / "bug_1"
    bug1.mkdir()
    (bug1 / "buggy").mkdir()
    (bug1 / "tests").mkdir()
    (bug1 / "hidden_tests").mkdir()
    (bug1 / "metadata.json").write_text(json.dumps({"bug_id": "bug_1", "description": "desc 1"}))
    
    bug2 = bench_dir / "bug_2"
    bug2.mkdir()
    (bug2 / "buggy").mkdir()
    (bug2 / "tests").mkdir()
    
    bench = Benchmark.load(bench_dir)
    assert len(bench) == 2
    assert bench.name == "my_bench"
    
    bugs = list(bench)
    assert bugs[0].bug_id == "bug_1"
    assert bugs[0].description == "desc 1"
    assert bugs[0].hidden_tests_dir is not None
    
    assert bugs[1].bug_id == "bug_2"
    assert bugs[1].hidden_tests_dir is None

def test_benchmark_missing_metadata(tmp_path, caplog):
    bench_dir = tmp_path / "bench"
    bench_dir.mkdir()
    bug1 = bench_dir / "bug_1"
    bug1.mkdir()
    (bug1 / "buggy").mkdir()
    (bug1 / "tests").mkdir()
    
    bench = Benchmark.load(bench_dir)
    assert len(bench) == 1
    assert bench[0].bug_id == "bug_1"

def test_benchmark_summary(tmp_path):
    bench_dir = tmp_path / "bench"
    bench_dir.mkdir()
    bug1 = bench_dir / "bug_1"
    bug1.mkdir()
    (bug1 / "buggy").mkdir()
    (bug1 / "tests").mkdir()
    
    bench = Benchmark.load(bench_dir)
    summary = bench.summary()
    assert "1 bugs total" in summary
    assert "0 with hidden tests" in summary

def test_benchmark_validation(tmp_path):
    bench_dir = tmp_path / "valid_bench"
    bench_dir.mkdir()
    bug1 = bench_dir / "bug_1"
    bug1.mkdir()

    # Public task
    task_dir = bug1 / "task"
    (task_dir / "buggy").mkdir(parents=True)
    (task_dir / "buggy" / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test_calc.py").write_text("def test_add(): pass\n", encoding="utf-8")
    (task_dir / "problem.md").write_text("# Add two numbers\nDescription here\n", encoding="utf-8")
    (task_dir / "metadata.json").write_text(json.dumps({
        "bug_id": "bug_1",
        "category": "arithmetic",
        "difficulty": "easy",
        "description": "valid task"
    }), encoding="utf-8")

    # Private evaluator
    priv_dir = bug1 / "private"
    (priv_dir / "hidden_tests").mkdir(parents=True)
    (priv_dir / "hidden_tests" / "test_calc.py").write_text("def test_hidden(): pass\n", encoding="utf-8")
    (priv_dir / "provenance.json").write_text(json.dumps({
        "repository": "https://github.com/aegis-verifier/aegis-benchmarks",
        "base_commit": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "verified_by": "test_suite"
    }), encoding="utf-8")
    (priv_dir / "constraints.yaml").write_text("constraints:\n  max_files_modified: 1\n", encoding="utf-8")
    (priv_dir / "oracle_patch.diff").write_text("--- a/calc.py\n+++ b/calc.py\n@@ -1 +1 @@\n", encoding="utf-8")
    
    bench = Benchmark.load(bench_dir)
    issues = bench.validate()
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) == 0

def test_benchmark_validation_failure(tmp_path):
    bench_dir = tmp_path / "broken_bench"
    bench_dir.mkdir()
    bug1 = bench_dir / "bug_broken"
    bug1.mkdir()
    buggy_dir = bug1 / "buggy"
    buggy_dir.mkdir()
    # Write invalid Python syntax in buggy code
    (buggy_dir / "syntax_err.py").write_text("def broken(: pass\n", encoding="utf-8")
    (bug1 / "tests").mkdir()
    
    bench = Benchmark.load(bench_dir)
    issues = bench.validate()
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) > 0
    assert any("Syntax error" in e.issue for e in errors)

def test_benchmark_contamination_detection(tmp_path):
    bench_dir = tmp_path / "contaminated_bench"
    bench_dir.mkdir()
    bug1 = bench_dir / "bug_leaked"
    bug1.mkdir()

    task_dir = bug1 / "task"
    (task_dir / "buggy").mkdir(parents=True)
    (task_dir / "buggy" / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test_calc.py").write_text("def test_add(): pass\n", encoding="utf-8")
    (task_dir / "problem.md").write_text("description", encoding="utf-8")
    (task_dir / "metadata.json").write_text(json.dumps({
        "bug_id": "bug_leaked", "category": "arithmetic", "difficulty": "easy", "description": "desc"
    }), encoding="utf-8")

    # Contamination: hidden_tests leaked into public task directory
    (task_dir / "hidden_tests").mkdir(parents=True)

    priv_dir = bug1 / "private"
    (priv_dir / "hidden_tests").mkdir(parents=True)
    (priv_dir / "hidden_tests" / "test_calc.py").write_text("def test_hidden(): pass\n", encoding="utf-8")
    (priv_dir / "provenance.json").write_text(json.dumps({
        "repository": "repo", "base_commit": "abc", "verified_by": "test"
    }), encoding="utf-8")
    (priv_dir / "constraints.yaml").write_text("constraints: none\n", encoding="utf-8")
    (priv_dir / "oracle_patch.diff").write_text("diff\n", encoding="utf-8")

    bench = Benchmark.load(bench_dir)
    issues = bench.validate()
    errors = [i for i in issues if i.severity == "ERROR"]
    assert any("Benchmark contamination error" in e.issue for e in errors)

def test_benchmark_public_only_validation_without_private_dir(tmp_path):
    bench_dir = tmp_path / "public_only_bench"
    bench_dir.mkdir()
    bug1 = bench_dir / "bug_pub"
    bug1.mkdir()

    task_dir = bug1 / "task"
    (task_dir / "buggy").mkdir(parents=True)
    (task_dir / "buggy" / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test_calc.py").write_text("def test_add(): pass\n", encoding="utf-8")
    (task_dir / "problem.md").write_text("# Add\nDescription\n", encoding="utf-8")
    (task_dir / "metadata.json").write_text(json.dumps({
        "bug_id": "bug_pub", "category": "arithmetic", "difficulty": "easy"
    }), encoding="utf-8")

    bench = Benchmark.load(bench_dir)
    assert len(bench) == 1
    assert bench[0].hidden_tests_dir is None
    issues = bench.validate()
    assert len([i for i in issues if i.severity == "ERROR"]) == 0

def test_benchmark_decoupled_evaluator_dir(tmp_path):
    public_bench = tmp_path / "public_suite"
    public_bench.mkdir()
    bug1 = public_bench / "bug_split"
    bug1.mkdir()

    task_dir = bug1 / "task"
    (task_dir / "buggy").mkdir(parents=True)
    (task_dir / "buggy" / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test_calc.py").write_text("def test_add(): pass\n", encoding="utf-8")
    (task_dir / "problem.md").write_text("# Add\n", encoding="utf-8")
    (task_dir / "metadata.json").write_text(json.dumps({
        "bug_id": "bug_split", "category": "arithmetic", "difficulty": "easy"
    }), encoding="utf-8")

    # Decoupled external private store
    eval_store = tmp_path / "private_store"
    eval_store.mkdir()
    priv_dir = eval_store / "bug_split" / "private"
    (priv_dir / "hidden_tests").mkdir(parents=True)
    (priv_dir / "hidden_tests" / "test_calc.py").write_text("def test_hidden(): pass\n", encoding="utf-8")
    (priv_dir / "provenance.json").write_text(json.dumps({
        "repository": "repo", "base_commit": "sha123"
    }), encoding="utf-8")
    (priv_dir / "constraints.yaml").write_text("constraints: ok\n", encoding="utf-8")
    (priv_dir / "oracle_patch.diff").write_text("diff\n", encoding="utf-8")

    bench = Benchmark.load(public_bench, evaluator_dir=eval_store)
    assert len(bench) == 1
    assert bench[0].hidden_tests_dir is not None
    issues = bench.validate()
    assert len([i for i in issues if i.severity == "ERROR"]) == 0
