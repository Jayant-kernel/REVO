"""Docker integration tests for the Phase 3 sandbox (require a daemon).

Gate: every test in this directory is skipped with an explicit reason when
``docker info`` fails. Skips are REPORTED, never silent — see
``docker-availability`` in the final summary. Run with::

    python -m pytest tests/integration/sandbox -v

These tests prove actual boundary properties (file/network/extension
isolation, non-root, secrets, timeouts, cleanup), not just policy strings.
"""

import pytest

from verified_data_factory.sandbox import docker_available

pytestmark = pytest.mark.integration

HAS_DOCKER = docker_available()

requires_docker = pytest.mark.skipif(
    not HAS_DOCKER,
    reason="Docker daemon unavailable (docker info failed); boundary unproven here",
)


def test_docker_availability_reported():
    """Always runs: states honestly whether the boundary tests executed."""
    print(f"\nDocker daemon available: {HAS_DOCKER}")
