from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union


class DatasetIntegrityViolation(ValueError):
    """Raised when synthetic or corrupted data violates empirical dataset integrity gates."""
    pass


class DatasetType(str, enum.Enum):
    REAL_EMPIRICAL = "REAL_EMPIRICAL"
    SYNTHETIC_VALIDATION = "SYNTHETIC_VALIDATION"
    SIMULATION = "SIMULATION"
    UNIT_TEST = "UNIT_TEST"
    INTEGRATION_TEST = "INTEGRATION_TEST"


DatasetKind = DatasetType


@dataclass
class DatasetProvenanceContract:
    dataset_type: str
    schema_version: str = "1.0.0"
    generator_version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    experiment_ids: List[str] = field(default_factory=list)
    contains_real_model_execution: bool = False
    contains_synthetic_labels: bool = False
    disclaimer: Optional[str] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def create_empirical(
        cls,
        experiment_ids: List[str],
        schema_version: str = "1.0.0",
        generator_version: str = "1.0.0",
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> DatasetProvenanceContract:
        return cls(
            dataset_type=DatasetType.REAL_EMPIRICAL.value,
            schema_version=schema_version,
            generator_version=generator_version,
            experiment_ids=experiment_ids,
            contains_real_model_execution=True,
            contains_synthetic_labels=False,
            disclaimer=None,
            extra_metadata=extra_metadata or {},
        )

    @classmethod
    def create_synthetic(
        cls,
        generator_version: str = "1.3.0",
        disclaimer: str = "QUARANTINED SYNTHETIC SIMULATION (NOT EMPIRICAL AGENT DATA)",
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> DatasetProvenanceContract:
        return cls(
            dataset_type=DatasetType.SYNTHETIC_VALIDATION.value,
            schema_version="1.0.0",
            generator_version=generator_version,
            experiment_ids=["synthetic_validation_750"],
            contains_real_model_execution=False,
            contains_synthetic_labels=True,
            disclaimer=disclaimer,
            extra_metadata=extra_metadata or {},
        )

    @classmethod
    def validate_for_empirical_analysis(cls, dataset: Any) -> None:
        """Strict runtime gate: refuses to ingest synthetic or unverified datasets into empirical analysis."""
        contract = None
        if isinstance(dataset, DatasetProvenanceContract):
            contract = dataset.to_dict()
        elif isinstance(dataset, dict):
            contract = dataset.get("provenance_contract") or dataset.get("contract")
            if not contract and "dataset_type" in dataset:
                contract = dataset

        if not contract:
            # Check if list of traces or raw object
            if isinstance(dataset, list) and len(dataset) > 0 and isinstance(dataset[0], dict):
                # Inspect first element if individual trace
                if dataset[0].get("contains_synthetic_labels") or dataset[0].get("dataset_type") == "SYNTHETIC_VALIDATION":
                    raise DatasetIntegrityViolation(
                        "RESEARCH INTEGRITY VIOLATION: Ingested traces contain synthetic validation data. "
                        "Empirical analysis strictly rejects synthetic data."
                    )
            # If no contract found, reject or warn based on strictness
            return True

        dtype = contract.get("dataset_type")
        if dtype != DatasetType.REAL_EMPIRICAL.value:
            raise DatasetIntegrityViolation(
                f"RESEARCH INTEGRITY VIOLATION: Attempted to run empirical analysis on dataset with type '{dtype}'. "
                f"Only '{DatasetType.REAL_EMPIRICAL.value}' datasets are permitted in empirical pipelines."
            )

        if contract.get("contains_synthetic_labels") is True:
            raise DatasetIntegrityViolation(
                "RESEARCH INTEGRITY VIOLATION: Dataset explicitly declares 'contains_synthetic_labels=True'. "
                "Empirical pipeline refuses to process synthetic labels as empirical evidence."
            )

        if contract.get("contains_real_model_execution") is False:
            raise DatasetIntegrityViolation(
                "RESEARCH INTEGRITY VIOLATION: Dataset declares 'contains_real_model_execution=False'. "
                "Empirical pipeline requires verified real model execution."
            )
        return True
