"""
AegisBench v1 Benchmark Diversity, Duplicate Detection, and Domain Balance Audit.
Evaluates:
1. Pairwise similarity across task problem statements, tests, and oracle specifications.
2. Identifies identical mutation patterns or copied logic.
3. Computes domain, repository, difficulty, and bug type distributions.
4. Outputs results/benchmark_validation/v1/diversity_and_balance.json.
"""

import ast
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def tokenize_text(text: str) -> Set[str]:
    words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", text.lower())
    return set(words)


def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def run_diversity_audit():
    bench_dir = Path("benchmarks/v1")
    tasks = sorted([d for d in bench_dir.iterdir() if d.is_dir()])

    task_data: List[Dict[str, Any]] = []

    for td in tasks:
        task_id = td.name
        prob_file = td / "task" / "problem.md"
        sol_file = td / "task" / "buggy" / "solution.py"
        test_file = td / "task" / "tests" / "test_solution.py"
        meta_file = td / "task" / "metadata.json"
        oracle_test_file = td / "private" / "oracle_tests" / "test_oracle_behavior.py"
        mutations_file = td / "private" / "mutations.json"

        prob_text = prob_file.read_text(encoding="utf-8") if prob_file.exists() else ""
        sol_text = sol_file.read_text(encoding="utf-8") if sol_file.exists() else ""
        test_text = test_file.read_text(encoding="utf-8") if test_file.exists() else ""
        meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
        oracle_text = oracle_test_file.read_text(encoding="utf-8") if oracle_test_file.exists() else ""
        mutations = json.loads(mutations_file.read_text(encoding="utf-8")) if mutations_file.exists() else []

        task_data.append({
            "task_id": task_id,
            "category": meta.get("category", "unknown"),
            "repo": meta.get("repo", "unknown"),
            "difficulty": meta.get("difficulty_dimensions", {}).get("DIFFICULTY_BUCKET", meta.get("difficulty", "medium")),
            "difficulty_dimensions": meta.get("difficulty_dimensions", {}),
            "bug_type": meta.get("tags", ["logic_bug"])[0],
            "prob_tokens": tokenize_text(prob_text),
            "sol_tokens": tokenize_text(sol_text),
            "test_tokens": tokenize_text(test_text),
            "oracle_tokens": tokenize_text(oracle_text),
            "mutation_ids": [m.get("id") for m in mutations]
        })

    # 1. Pairwise Near-Duplicate Detection (Threshold 0.85)
    near_duplicates = []
    max_similarity = 0.0
    most_similar_pair = ("", "")

    for i in range(len(task_data)):
        for j in range(i + 1, len(task_data)):
            t1 = task_data[i]
            t2 = task_data[j]

            sim_prob = jaccard_similarity(t1["prob_tokens"], t2["prob_tokens"])
            sim_sol = jaccard_similarity(t1["sol_tokens"], t2["sol_tokens"])
            sim_test = jaccard_similarity(t1["test_tokens"], t2["test_tokens"])
            sim_orc = jaccard_similarity(t1["oracle_tokens"], t2["oracle_tokens"])

            composite_sim = (sim_prob * 0.3) + (sim_sol * 0.3) + (sim_test * 0.2) + (sim_orc * 0.2)
            if composite_sim > max_similarity:
                max_similarity = composite_sim
                most_similar_pair = (t1["task_id"], t2["task_id"])

            if composite_sim > 0.85:
                near_duplicates.append({
                    "task_a": t1["task_id"],
                    "task_b": t2["task_id"],
                    "similarity": round(composite_sim, 3)
                })

    # 2. Domain & Track Balance Analysis
    track_distribution = Counter()
    repo_distribution = Counter()
    difficulty_distribution = Counter()
    bug_type_distribution = Counter()

    domain_repo_breakdown = defaultdict(lambda: {
        "task_count": 0,
        "repositories": set(),
        "difficulties": Counter(),
        "bug_types": Counter()
    })

    for t in task_data:
        cat = t["category"]
        repo = t["repo"]
        diff = t["difficulty"]
        btype = t["bug_type"]

        track_distribution[cat] += 1
        repo_distribution[repo] += 1
        difficulty_distribution[diff] += 1
        bug_type_distribution[btype] += 1

        rec = domain_repo_breakdown[cat]
        rec["task_count"] += 1
        rec["repositories"].add(repo)
        rec["difficulties"][diff] += 1
        rec["bug_types"][btype] += 1

    domain_table = []
    for cat, rec in domain_repo_breakdown.items():
        domain_table.append({
            "domain": cat,
            "repositories": sorted(list(rec["repositories"])),
            "task_count": rec["task_count"],
            "difficulty_distribution": dict(rec["difficulties"]),
            "bug_type_distribution": dict(rec["bug_types"])
        })

    report = {
        "benchmark_name": "AegisBench-v1",
        "total_tasks": len(task_data),
        "near_duplicate_count": len(near_duplicates),
        "near_duplicates": near_duplicates,
        "max_pairwise_similarity": round(max_similarity, 3),
        "most_similar_pair": most_similar_pair,
        "duplicate_detection_passed": len(near_duplicates) == 0,
        "overall_difficulty_distribution": dict(difficulty_distribution),
        "track_distribution": dict(track_distribution),
        "repository_count": len(repo_distribution),
        "bug_type_count": len(bug_type_distribution),
        "domain_breakdown": domain_table
    }

    out_file = Path("results/benchmark_validation/v1/diversity_and_balance.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 80)
    print("AEGISBENCH v1 DIVERSITY & DOMAIN BALANCE AUDIT")
    print(f"Total Tasks: {len(task_data)}")
    print(f"Near-Duplicates Detected: {len(near_duplicates)}")
    print(f"Max Pairwise Similarity: {report['max_pairwise_similarity']} ({most_similar_pair[0]} vs {most_similar_pair[1]})")
    print(f"Difficulty Breakdown: {dict(difficulty_distribution)}")
    print(f"Track Breakdown: {len(track_distribution)} categories across {len(repo_distribution)} repositories")
    print("Audit Complete. Saved to results/benchmark_validation/v1/diversity_and_balance.json")
    print("=" * 80)


if __name__ == "__main__":
    run_diversity_audit()
