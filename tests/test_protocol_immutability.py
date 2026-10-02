"""
Protocol Immutability CI Gate for empirical_100_v1.
Verifies that all protocol artifacts match their cryptographic SHA-256 digests.
"""

import hashlib
import json
from pathlib import Path
import pytest


@pytest.mark.parametrize("protocol_name", ["empirical_100_v1", "empirical_100_v2", "empirical_100_v3"])
def test_protocol_immutability_hashes(protocol_name: str):
    proto_dir = Path(f"experiments/protocols/{protocol_name}")
    assert proto_dir.exists(), f"Protocol directory missing: {proto_dir}"

    hash_file = proto_dir / "protocol_hashes.json"
    assert hash_file.exists(), f"protocol_hashes.json missing in {proto_dir}!"

    expected_hashes = json.loads(hash_file.read_text(encoding="utf-8"))
    assert len(expected_hashes) >= 7

    for fname, expected_h in expected_hashes.items():
        target_f = proto_dir / fname
        assert target_f.exists(), f"Protocol file missing: {fname}"
        actual_h = "sha256:" + hashlib.sha256(target_f.read_bytes()).hexdigest()
        assert actual_h == expected_h, (
            f"Protocol artifact '{fname}' was mutated! Expected {expected_h}, got {actual_h}. "
            "Experiment protocols are immutable."
        )
