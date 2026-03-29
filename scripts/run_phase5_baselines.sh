#!/usr/bin/env bash
set -euo pipefail

OUT_ROOT="${1:-results/phase5-baselines}"
TESTS_ROOT="${2:-tests}"
WORKSPACE_ROOT="${3:-mock_outputs}"
shift 3 || true

if [ "$#" -eq 0 ]; then
  MODELS=("claude-opus-4-6" "claude-sonnet-4-5" "gpt-4o" "gemini-pro")
else
  MODELS=("$@")
fi

mkdir -p "${OUT_ROOT}"

for model in "${MODELS[@]}"; do
  echo "[baseline] model=${model}"
  python -m harness.cli run --suite all --model "${model}" --tests-root "${TESTS_ROOT}" --workspace-root "${WORKSPACE_ROOT}" --output "${OUT_ROOT}/${model}/without-skills"
  if [ -n "${BIO_SKILLS_PATH:-}" ]; then
    python -m harness.cli run --suite all --model "${model}" --skills-path "${BIO_SKILLS_PATH}" --tests-root "${TESTS_ROOT}" --workspace-root "${WORKSPACE_ROOT}" --output "${OUT_ROOT}/${model}/with-skills"
    a=$(ls -1 "${OUT_ROOT}/${model}/without-skills"/run-all-*/run.json | tail -n 1)
    b=$(ls -1 "${OUT_ROOT}/${model}/with-skills"/run-all-*/run.json | tail -n 1)
    python -m harness.cli compare "${a}" "${b}"
  fi
done
