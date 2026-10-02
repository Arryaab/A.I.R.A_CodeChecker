# MLVerify Empirical Research & Methodological Boundaries

This document provides a transparent, scientifically honest summary of the **MLVerify** research layer in A.I.R.A. (AI Release Assurance).

---

## 1. Research Objective

Modern verification pipelines (comprising AST parsing, test execution, regression suites, and mutation testing) consume substantial compute and wall-clock time. MLVerify investigates:

> *Can statistical models accurately predict code defect likelihood BEFORE verification begins, using only features observable at the moment code generation finishes?*

Target boundary:

```text
AI Agent Finishes Patch
          │
          ▼
   [t_prediction]  <─── Feature snapshot: AST delta, diff metrics, static complexity
          │
          ▼
    MLVerify Risk  <─── Predicts P(is_defective) in SHADOW MODE
          │
          ▼
   Deterministic   <─── C1 through C6 gates execute unconditionally
    Verification
```

---

## 2. Empirical Baseline Foundation

All reported metrics are evaluated on the frozen, reproducible **`empirical_100_local_v1`** dataset:
- **Sample Size**: 100 complete, admitted executions.
- **Task Diversity**: 50 algorithmic and software tasks from the benchmark suite.
- **Provider & Model**: Qwen 2.5 Coder 7B running locally via Ollama ($0 external cloud cost, zero quota dependency).
- **Execution Seeds**: Paired runs under Seed 42 and Seed 100 for every task.
- **Ground Truth Outcomes**:
  - Defective runs (`is_defective = 1`): 57 runs across 32 tasks.
  - Non-defective runs (`is_defective = 0`): 43 runs across 25 tasks.
- **Validation Protocol**: 5-Fold `GroupKFold` grouped strictly by `task_id` (40 train tasks / 80 runs, 10 test tasks / 20 runs per fold). Paired seeds are never split across folds.
- **Leakage Audit**: Verified under formal feature contract. Zero post-execution or oracle features enter the predictive matrix.

---

## 3. Defect-Risk Prediction Results

Out-of-fold performance on the primary target `is_defective`:

| Candidate Model | PR-AUC | ROC-AUC | Brier Score | ECE | Fold PR-AUC Std |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Majority Class Baseline** | 0.5198 | 0.3858 | 0.2527 | 0.1100 | 0.1166 |
| **Domain Heuristic Baseline** | 0.7708 | 0.7305 | 0.1625 | 0.0027 | 0.1056 |
| **Regularized Linear (L1)** | 0.9348 | 0.8792 | 0.1078 | 0.1275 | 0.0286 |
| **Gradient Boosting** | 0.9291 | 0.8927 | 0.1131 | 0.0903 | 0.0793 |
| **Logistic Regression (L2)** | 0.9333 | 0.8907 | 0.1112 | 0.0687 | 0.0328 |
| **Random Forest (Shallow)** | **0.9367** | **0.8870** | **0.1114** | **0.0737** | **0.0323** |

### Bootstrap Uncertainty Analysis ($B=1000$ Clusters)
- **PR-AUC**: Point estimate $0.9367$, 95% Bootstrap CI **$[0.8814, 0.9782]$**
- **ROC-AUC**: Point estimate $0.8870$, 95% Bootstrap CI **$[0.8122, 0.9514]$**
- **Brier Score**: Point estimate $0.1114$, 95% Bootstrap CI **$[0.0811, 0.1482]$**
- **Seed-Pair Agreement**: Across 50 paired task runs (seed 42 vs seed 100), predicted defect risk exhibits a Pearson correlation of $r = 0.8214$ ($p < 10^{-12}$) and an 84.0% binary decision agreement rate.

---

## 4. Methodological Boundaries & Rigor

A.I.R.A. enforces strict boundaries separating research findings from unsubstantiated claims:

### Correction 1: Post-Agent Diagnostic vs. Predictive Head
In early development, predicting `agent_failure` (e.g. `MAX_STEPS` or model execution crashes) was explored as a predictive target. However, because agent termination status is **already known at the moment the agent finishes**, claiming high classification scores as "forecasting" is methodologically circular.
- **Resolution**: `agent_failure` was formally reclassified as a **`POST_AGENT_DIAGNOSTIC`** (telemetry monitor). It is excluded from pre-verification predictive claims.

### Correction 2: False Accept Forecasting Data Scarcity
In the 100-run baseline, patches that passed visible tests but failed hidden invariants occurred only 3 times.
- **Resolution**: Statistical power is insufficient to claim a reliable machine learning classifier for rare-event false accept escape. Claiming production readiness for false-accept prediction is rejected until a dedicated rare-event dataset is collected.

### Correction 3: Rejection of Autonomous Routing
Simulating autonomous routing policies (e.g. automatically skipping deep mutation checks on "low-risk" patches) reveals potential risk of defect escape without extensive cross-validation.
- **Resolution**: Autonomous routing is **REJECTED** for production. MLVerify is restricted strictly to **`SHADOW_MODE_ONLY`**.

---

## 5. Current Research Disposition Summary

```text
STATUS:                  MLVERIFY_PARTIALLY_SUPPORTED
DEFECT_PREDICTION:       RESEARCH_SUPPORTED (PR-AUC 0.9367)
AGENT_FAILURE:           DIAGNOSTIC_ONLY (Telemetry Monitor)
FALSE_ACCEPT_PREDICTION: INSUFFICIENT_DATA (Rare-event limitation)
AUTONOMOUS_ROUTING:      REJECTED (Unsafe for production bypass)
OPERATING_MODE:          SHADOW_MODE_ONLY
```
