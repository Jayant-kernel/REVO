# Verified SQL Data Factory — Phase 3 sandbox execution image.
#
# Minimal by design: Python stdlib + pinned DuckDB + harness only.
# NO git, SSH, Docker CLI, cloud CLIs, compilers, or package managers
# beyond what is needed at BUILD time. Build needs network (pip);
# RUNTIME candidate execution must have none (`docker create --network none`).
#
# Base is pinned to a patch release; record the built digest with:
#   docker image inspect --format '{{.Id}}' verified-data-factory-sandbox:1.0
# and store it in ExecutionResult.sandbox_image_digest at runtime.
FROM python:3.12.10-slim-bookworm

# No interactive/debian frontend prompts; no bytecode noise.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Pinned DuckDB matches the project's development dependency.
RUN pip install --no-cache-dir "duckdb==1.5.5"

# Non-root execution user (uid/gid 10000). Doubly enforced with
# `docker create --user 10000:10000`; the harness probe asserts uid != 0.
RUN groupadd -r -g 10000 sandbox && useradd -r -u 10000 -g sandbox sandbox \
    && mkdir -p /work/input /work/output /work/tmp /harness \
    && chown -R sandbox:sandbox /work /harness

COPY harness/run.py /harness/run.py
RUN chmod 0555 /harness/run.py && chown sandbox:sandbox /harness/run.py

USER 10000:10000
WORKDIR /work

# No ENTRYPOINT network services; the executor runs `python /harness/run.py`.
CMD ["python", "/harness/run.py"]
