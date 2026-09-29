# Build from the repository root (build-time network required for pip).
# The build context is the sandbox package so the harness is included:
#
#   docker build -f src/verified_data_factory/sandbox/docker/Dockerfile \
#     -t verified-data-factory-sandbox:1.0 \
#     src/verified_data_factory/sandbox
#
# Record the resulting digest for provenance:
#
#   docker image inspect --format '{{.Id}}' verified-data-factory-sandbox:1.0
