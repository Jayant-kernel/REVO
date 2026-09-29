"""Stable public API for Candidate Generation (Phase 2 consumers).

Phase 3 consumes ``CandidateSolution.candidate_sql`` + TaskInstance fixture
info; Phase 4 consumes ``CandidateSolution`` + ``TaskInstance``. Neither is
coupled to here: candidates carry no verdicts and no execution results.
"""

from .config import GenerationSettings, ProviderEndpoint, load_settings, settings_from_dict
from .errors import (
    GenerationError,
    PermanentProviderError,
    ProviderConfigurationError,
    ProviderError,
    ProviderTimeoutError,
    TransientProviderError,
)
from .export import (
    candidate_from_dict,
    candidate_from_json,
    candidate_to_dict,
    candidate_to_json,
    read_candidates_jsonl,
    write_candidates_jsonl,
)
from .fake import FakeProvider
from .generator import (
    build_candidate_id,
    generate_candidate,
    generate_candidates,
    generate_for_tasks,
)
from .models import (
    GENERATION_SCHEMA_VERSION,
    PROMPT_VERSION,
    SQL_DIALECT,
    CandidateSolution,
    GenerationConfig,
    GenerationResponse,
    GenerationResult,
    TokenUsage,
)
from .parser import ParsedSQL, extract_candidate_sql
from .prompt import SolverContext, build_solver_context, build_sql_prompt
from .provider import OpenAICompatibleProvider, Provider
from .providers import PROVIDERS, DevstralProvider, QwenProvider, create_provider

__all__ = [
    "GENERATION_SCHEMA_VERSION",
    "PROMPT_VERSION",
    "PROVIDERS",
    "SQL_DIALECT",
    "CandidateSolution",
    "DevstralProvider",
    "FakeProvider",
    "GenerationConfig",
    "GenerationError",
    "GenerationResponse",
    "GenerationResult",
    "GenerationSettings",
    "OpenAICompatibleProvider",
    "ParsedSQL",
    "PermanentProviderError",
    "Provider",
    "ProviderConfigurationError",
    "ProviderEndpoint",
    "ProviderError",
    "ProviderTimeoutError",
    "QwenProvider",
    "SolverContext",
    "TokenUsage",
    "TransientProviderError",
    "build_candidate_id",
    "build_solver_context",
    "build_sql_prompt",
    "candidate_from_dict",
    "candidate_from_json",
    "candidate_to_dict",
    "candidate_to_json",
    "create_provider",
    "extract_candidate_sql",
    "generate_candidate",
    "generate_candidates",
    "generate_for_tasks",
    "load_settings",
    "read_candidates_jsonl",
    "settings_from_dict",
    "write_candidates_jsonl",
]
