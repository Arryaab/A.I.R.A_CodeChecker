from __future__ import annotations

import json
from aegis.benchmark import Benchmark

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
