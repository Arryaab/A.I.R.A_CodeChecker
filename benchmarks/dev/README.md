# AegisBench Dev v0.1: Curated Algorithmic Regression Suite (15 tasks)

A standardized diagnostic suite of 15 algorithmic and logical Python defect fixtures designed for unit testing, repair pipeline validation, and verifier regression testing.

## Task Inventory

| Bug ID | Category | Difficulty | Description |
|--------|----------|------------|-------------|
| bug_001_wrong_operator | operator_error | easy | Fix arithmetic operator precedence |
| bug_002_off_by_one | boundary_error | easy | Fix array slice boundary condition |
| bug_003_missing_return | missing_return | easy | Restore missing return statement |
| bug_004_wrong_comparison | comparison_error | easy | Correct equality operator logic |
| bug_005_wrong_variable | variable_error | easy | Fix variable reference shadowing |
| bug_006_mutable_default | mutable_default | medium | Remove mutable default argument side-effect |
| bug_007_wrong_index | index_error | medium | Correct collection index offset |
| bug_008_string_error | string_error | easy | Fix string formatting / interpolation |
| bug_009_loop_boundary | loop_error | medium | Correct iteration termination condition |
| bug_010_missing_edge_case | edge_case | easy | Handle empty input edge case |
| bug_011_type_error | type_error | medium | Handle type coercion and validation |
| bug_012_dict_error | dict_error | medium | Fix dictionary key traversal |
| bug_013_none_check | none_check | medium | Guard against NoneType attribute access |
| bug_014_logic_error | logic_error | medium | Resolve boolean branching inversion |
| bug_015_recursion_error | recursion_error | hard | Add proper base case to recursive traversal |

---

## Architectural Separation & Zero Contamination

To guarantee evaluation integrity and eliminate training/evaluator contamination, each task maintains strict structural separation:
- `task/`: Public task specification exposed to autonomous coding agents (problem statement, metadata, buggy codebase, and visible unit tests).
- `private/`: Private evaluator harness (hidden tests, ground-truth oracle patches, non-functional constraints, and provenance metadata). In public Git checkouts, private evaluator data is untracked (`.gitignore`) and can be mounted separately via `--evaluator-dir`.

## Benchmark Validation

Validate tasks against the canonical schema:
```bash
python -m aegis.cli benchmark --dir benchmarks/dev --validate
```
Or with a decoupled private evaluator repository:
```bash
python -m aegis.cli benchmark --dir benchmarks/dev --evaluator-dir /path/to/private-evaluator --validate
```
