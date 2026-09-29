"""Phase 6 entry points (thin by design; logic lives in modules)."""

from .completeness import validate_golden_chain
from .dataset_snapshot import build_dataset_snapshot, recompute_snapshot_id
from .export import BUNDLE_FILES, build_bundle, export_provenance_bundle, read_bundle
from .lineage import BuiltProvenance, build_provenance, roles_for_candidate, trace_golden_record
from .manifests import ReproductionManifest, build_reproduction_manifest
from .reproducibility import assess_reproducibility, compare_reproduction, worst_status
from .store import ProvenanceStore

__all__ = [
    "BUNDLE_FILES",
    "BuiltProvenance",
    "ProvenanceStore",
    "ReproductionManifest",
    "assess_reproducibility",
    "build_bundle",
    "build_dataset_snapshot",
    "build_provenance",
    "build_reproduction_manifest",
    "compare_reproduction",
    "export_provenance_bundle",
    "read_bundle",
    "recompute_snapshot_id",
    "roles_for_candidate",
    "trace_golden_record",
    "validate_golden_chain",
    "worst_status",
]
