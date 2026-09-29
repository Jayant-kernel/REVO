"""E2E session guard: no execution containers may leak across the suite."""

import subprocess

import pytest


def _leftover_vdf_containers():
    completed = subprocess.run(
        ["docker", "ps", "-a", "-q", "--filter", "name=vdf-"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return sorted(line for line in completed.stdout.splitlines() if line.strip())


@pytest.fixture(scope="session", autouse=True)
def no_container_leakage():
    from verified_data_factory.sandbox import docker_available

    if not docker_available():
        yield
        return
    before = _leftover_vdf_containers()
    yield
    after = _leftover_vdf_containers()
    leaked = [c for c in after if c not in before]
    assert not leaked, f"leaked containers: {leaked}"
