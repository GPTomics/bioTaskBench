#!/usr/bin/env bash
set -euo pipefail

RUNS_DIR="${1:-results/phase4-calibration}"
REPLICAS="${2:-3}"
TESTS_ROOT="${3:-tests}"
WORKSPACE_ROOT="${4:-mock_outputs}"

mkdir -p "${RUNS_DIR}"

echo "Phase 4 calibration"
echo "runs_dir=${RUNS_DIR}"
echo "replicas=${REPLICAS}"

for i in $(seq 1 "${REPLICAS}"); do
  out="${RUNS_DIR}/replica-${i}"
  echo "[replica ${i}] suite=all -> ${out}"
  python -m harness.cli run --suite all --tests-root "${TESTS_ROOT}" --workspace-root "${WORKSPACE_ROOT}" --output "${out}"
done

latest_runs=$(ls -1 "${RUNS_DIR}"/replica-*/run-all-*/run.json | tail -n "${REPLICAS}" | tr '\n' ' ')
echo "flakiness audit on runs: ${latest_runs}"
python -m harness.cli audit-flaky ${latest_runs} --threshold 0.3

echo "data-size audit"
python -m harness.cli audit-data --tests-root "${TESTS_ROOT}"
