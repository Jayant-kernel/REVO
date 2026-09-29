"""Independent Verification Engine (Phase 4 public API).

Phase 5 consumes ``VerificationResult`` per candidate-task run. Deeper
imports (oracle implementations, stage runners) are available but only
``api`` is contractual.
"""

from .api import build_verification_id, compute_oracle, verify_candidate
from .backend import DerivedTaskBackend, ExecutionBackend, SandboxBackend
from .comparator import compare
from .config import config_from_dict, load_verification_config
from .errors import (
    BackendError,
    OracleError,
    OracleUnknownError,
    VerificationConfigError,
    VerificationError,
)
from .export import (
    read_verifications_jsonl,
    verification_from_dict,
    verification_from_json,
    verification_to_dict,
    verification_to_json,
    write_verifications_jsonl,
)
from .fake import FakeBackend
from .hidden import derive_hidden_seed, run_hidden_checks
from .metamorphic import (
    RELATION_REGISTRY,
    relations_for_family,
    run_metamorphic_checks,
)
from .models import (
    VERIFICATION_CONFIG_VERSION,
    ComparisonPolicy,
    ComparisonResult,
    ExpectedResult,
    HiddenTestResult,
    MetamorphicResult,
    MutationResult,
    OracleOutcome,
    OrderSpec,
    PerformanceOutcome,
    PropertyResult,
    Strength,
    Verdict,
    VerificationConfig,
    VerificationFailureCode,
    VerificationResult,
)
from .mutations import (
    OPERATORS,
    OPERATORS_BY_FAMILY,
    applicable_operators,
    run_mutation_checks,
)
from .oracle_registry import (
    ORACLES,
    RETIRED_VERSIONS,
    get_oracle,
    is_retired_version,
    known_templates,
)
from .performance import collect_performance
from .properties import (
    PROPERTY_REGISTRY,
    properties_for_family,
    run_property_checks,
)

__all__ = [
    "OPERATORS",
    "OPERATORS_BY_FAMILY",
    "ORACLES",
    "PROPERTY_REGISTRY",
    "RELATION_REGISTRY",
    "RETIRED_VERSIONS",
    "VERIFICATION_CONFIG_VERSION",
    "BackendError",
    "ComparisonPolicy",
    "ComparisonResult",
    "DerivedTaskBackend",
    "ExecutionBackend",
    "ExpectedResult",
    "FakeBackend",
    "HiddenTestResult",
    "MetamorphicResult",
    "MutationResult",
    "OracleError",
    "OracleOutcome",
    "OracleUnknownError",
    "OrderSpec",
    "PerformanceOutcome",
    "PropertyResult",
    "SandboxBackend",
    "Strength",
    "Verdict",
    "VerificationConfig",
    "VerificationConfigError",
    "VerificationError",
    "VerificationFailureCode",
    "VerificationResult",
    "applicable_operators",
    "build_verification_id",
    "collect_performance",
    "compare",
    "compute_oracle",
    "config_from_dict",
    "derive_hidden_seed",
    "get_oracle",
    "is_retired_version",
    "known_templates",
    "load_verification_config",
    "properties_for_family",
    "read_verifications_jsonl",
    "relations_for_family",
    "run_hidden_checks",
    "run_metamorphic_checks",
    "run_mutation_checks",
    "run_property_checks",
    "verification_from_dict",
    "verification_from_json",
    "verification_to_dict",
    "verification_to_json",
    "verify_candidate",
    "write_verifications_jsonl",
]
