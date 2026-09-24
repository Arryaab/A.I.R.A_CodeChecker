from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Callable

from aegis.benchmark import Benchmark
from aegis.config import AegisConfig
from aegis.llm import LLMProvider
from aegis.repair import RepairResult, repair_bug
from aegis.taxonomy import FailureType

logger = logging.getLogger(__name__)

@dataclass
class EvaluationMetrics:
    total_bugs: int
    pass_at_1: float
    pass_at_3: float
    visible_pass_rate: float
    hidden_pass_rate: float
    invalid_python_rate: float
    avg_attempts: float
    avg_duration_seconds: float
    avg_tokens: int
    failure_distribution: dict[str, int] = field(default_factory=dict)

@dataclass
class EvaluationReport:
    metrics: EvaluationMetrics
    results: list[RepairResult]
    model_name: str
    config: dict
    timestamp: str
    benchmark_name: str

def evaluate_benchmark(
    benchmark: Benchmark,
    provider: LLMProvider,
    config: AegisConfig,
    progress_callback: Callable | None = None,
) -> EvaluationReport:
    """Run repair on every bug in the benchmark, collect results."""
    results = []
    
    total = len(benchmark)
    for i, bug in enumerate(benchmark):
        if progress_callback:
            progress_callback(bug.bug_id, i + 1, total)
            
        result = repair_bug(
            bug_dir=bug.buggy_dir,
            provider=provider,
            config=config,
            visible_tests_dir=bug.visible_tests_dir,
            hidden_tests_dir=bug.hidden_tests_dir,
            bug_id=bug.bug_id
        )
        results.append(result)
        
    metrics = calculate_metrics(results)
    
    return EvaluationReport(
        metrics=metrics,
        results=results,
        model_name=provider.name,
        config=asdict(config),
        timestamp=datetime.now().isoformat(),
        benchmark_name=benchmark.name
    )

def calculate_metrics(results: list[RepairResult]) -> EvaluationMetrics:
    """Compute aggregate metrics from results."""
    total = len(results)
    if total == 0:
        return EvaluationMetrics(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
        
    pass_at_1_count = 0
    pass_at_3_count = 0
    visible_pass_count = 0
    hidden_pass_count = 0
    bugs_with_hidden = 0
    invalid_python_count = 0
    total_attempts = 0
    total_duration = 0.0
    total_tokens = 0
    
    failure_distribution = {ft.value: 0 for ft in FailureType}
    
    for r in results:
        total_attempts += len(r.attempts)
        total_duration += r.total_duration_seconds
        total_tokens += r.total_tokens
        
        if r.visible_pass:
            visible_pass_count += 1
            
        if r.hidden_pass is not None:
            bugs_with_hidden += 1
            if r.hidden_pass:
                hidden_pass_count += 1
                
        if r.success:
            pass_at_3_count += 1 # Any success within max_retries (usually 3)
            # check if passed on first attempt
            if len(r.attempts) > 0 and r.attempts[0].test_result and r.attempts[0].test_result.passed:
                pass_at_1_count += 1
                
        if r.failure_record:
            ft = r.failure_record.failure_type.value
            failure_distribution[ft] = failure_distribution.get(ft, 0) + 1
            if r.failure_record.failure_type == FailureType.INVALID_PYTHON:
                invalid_python_count += 1

    return EvaluationMetrics(
        total_bugs=total,
        pass_at_1=(pass_at_1_count / total) * 100,
        pass_at_3=(pass_at_3_count / total) * 100,
        visible_pass_rate=(visible_pass_count / total) * 100,
        hidden_pass_rate=(hidden_pass_count / bugs_with_hidden * 100) if bugs_with_hidden > 0 else 0.0,
        invalid_python_rate=(invalid_python_count / total) * 100,
        avg_attempts=total_attempts / total,
        avg_duration_seconds=total_duration / total,
        avg_tokens=int(total_tokens / total),
        failure_distribution=failure_distribution
    )

def generate_json_report(report: EvaluationReport, output_dir: Path) -> Path:
    """Write JSON report to file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"report_{report.timestamp.replace(':', '')}.json"
    
    # Custom serializer for complex types
    def default_serializer(obj):
        if hasattr(obj, 'asdict'):
            return obj.asdict()
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        if isinstance(obj, Path):
            return str(obj)
        return str(obj)
        
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, default=default_serializer, indent=2)
        
    return report_path

def generate_markdown_report(report: EvaluationReport, output_dir: Path) -> Path:
    """Write human-readable markdown report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"report_{report.timestamp.replace(':', '')}.md"
    
    lines = [
        f"# Aegis Evaluation Report: {report.benchmark_name}",
        f"**Date**: {report.timestamp}",
        f"**Model**: {report.model_name}",
        "",
        "## Metrics",
        f"- Total Bugs: {report.metrics.total_bugs}",
        f"- Pass@1: {report.metrics.pass_at_1:.2f}%",
        f"- Pass@3 (Overall Success): {report.metrics.pass_at_3:.2f}%",
        f"- Visible Pass Rate: {report.metrics.visible_pass_rate:.2f}%",
        f"- Hidden Pass Rate: {report.metrics.hidden_pass_rate:.2f}%",
        f"- Invalid Python Rate: {report.metrics.invalid_python_rate:.2f}%",
        f"- Avg Attempts: {report.metrics.avg_attempts:.2f}",
        f"- Avg Duration: {report.metrics.avg_duration_seconds:.2f}s",
        f"- Avg Tokens: {report.metrics.avg_tokens}",
        "",
        "## Failure Distribution",
    ]
    
    for ft, count in report.metrics.failure_distribution.items():
        if count > 0:
            lines.append(f"- {ft}: {count}")
            
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    return report_path
