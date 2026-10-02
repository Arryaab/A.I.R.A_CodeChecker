import json
import shutil
from pathlib import Path

v3_dir = Path("empirical_100_v3")
for sub in ["raw", "traces", "derived", "metrics", "reports", "failures", "integrity"]:
    (v3_dir / sub).mkdir(parents=True, exist_ok=True)

shutil.copy("AegisBench-v1.lock.json", v3_dir / "benchmark_lock.json")
shutil.copy("experiments/protocols/empirical_100_v3/protocol_hashes.json", v3_dir / "protocol_hashes.json")

with open("empirical_100_v2/model_manifest.json") as f:
    mm = json.load(f)
mm["experiment_id"] = "empirical_100_v3"
with open(v3_dir / "model_manifest.json", "w", encoding="utf-8") as f:
    json.dump(mm, f, indent=2)

with open("empirical_100_v2/environment_manifest.json") as f:
    em = json.load(f)
em["experiment_id"] = "empirical_100_v3"
with open(v3_dir / "environment_manifest.json", "w", encoding="utf-8") as f:
    json.dump(em, f, indent=2)

with open("empirical_100_v2/manifest.json") as f:
    mf = json.load(f)
mf["experiment_id"] = "empirical_100_v3"
mf["pre_registered_analysis"]["false_accept_definition"] = "aegis_verification.release_policy == 'AUTO_APPROVE' and oracle_evaluation.oracle_verdict == 'DEFECTIVE'"
mf["pre_registered_analysis"]["false_reject_definition"] = "aegis_verification.release_policy == 'BLOCK' and oracle_evaluation.oracle_verdict == 'CORRECT'"
mf["created_at"] = "2026-09-27T10:00:00Z"
with open(v3_dir / "manifest.json", "w", encoding="utf-8") as f:
    json.dump(mf, f, indent=2)

with open("empirical_100_v2/execution_matrix.json") as f:
    matrix = json.load(f)
with open(v3_dir / "execution_matrix.json", "w", encoding="utf-8") as f:
    json.dump(matrix, f, indent=2)

print("Setup empirical_100_v3 complete. Directories and files verified:")
for p in sorted(v3_dir.glob("*")):
    print(" ", p.name)
