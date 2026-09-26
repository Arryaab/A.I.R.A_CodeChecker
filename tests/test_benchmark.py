from __future__ import annotations

import json
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
    assert bench[0].bug_id == "bug_1" # Falls back to dir name

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
    buggy_dir = bug1 / "buggy"
    buggy_dir.mkdir()
    (buggy_dir / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    tests_dir = bug1 / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_calc.py").write_text("def test_add(): pass\n", encoding="utf-8")
    (bug1 / "hidden_tests").mkdir()
    (bug1 / "metadata.json").write_text(json.dumps({
        "bug_id": "bug_1",
        "category": "arithmetic",
        "description": "valid task"
    }), encoding="utf-8")
    
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

