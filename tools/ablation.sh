#!/bin/bash
# tools/ablation.sh — Dispatch a single bare-vs-full ablation run cell
#
# Designed to be run inside the claude-code incus container as user
# `claude`. The diplomat repo is bind-mounted at
# /home/claude/workspace/diplomat, so writing this script on the
# Windows side (P:/shared/diplomat/tools/ablation.sh) makes it
# immediately available in the container.
#
# Subcommands:
#   probe MODEL
#       Hit the provider once per faction with a trivial JSON request
#       (~$0.003 total). Catches API keys / model-name typos before
#       any live run.
#   run MODEL MODE RUN_N
#       Fire one ablation cell: a single 4-round Water Rights
#       beta-squeezed game with all three factions on the same MODEL,
#       in MODE = full|bare, output filename suffixed _RUN_N.
#       Examples:
#         tools/ablation.sh run gpt-5.4-mini full 1
#         tools/ablation.sh run gpt-5.4-mini bare 1
#         tools/ablation.sh run gpt-4.1-nano full 1
#         tools/ablation.sh run claude-sonnet-4-6 bare 1
#   summary
#       Print headline negotiated_surplus_share per existing
#       tests/self_play/results/run14*.json file.
#
# Usage (from the container, as user `claude`):
#   cd ~/workspace/diplomat
#   bash tools/ablation.sh probe gpt-5.4-mini
#   bash tools/ablation.sh run gpt-5.4-mini full 1
#   ...
#
# Usage from Windows via ssh (still one quoting layer but JSON stays in script):
#   ssh pirozhok "incus exec claude-code -- su - claude -c 'cd ~/workspace/diplomat && bash tools/ablation.sh probe gpt-5.4-mini'"

set -euo pipefail

# Use the project venv's python if it exists (it has toolkit + openai +
# anthropic SDKs installed editable). Fall back to system python3 only
# if the venv is missing (which would itself be a configuration error
# for this project).
VENV_PYTHON="$(pwd)/.venv/bin/python"
if [ -x "$VENV_PYTHON" ]; then
  PY="$VENV_PYTHON"
else
  echo "[warn] .venv/bin/python not found at $VENV_PYTHON — falling back to system python3" >&2
  echo "[warn] This will likely fail with 'openai package required' or similar import errors." >&2
  PY="python3"
fi

SCENARIO_MD="scenarios/water_rights.md"
ANALYSIS_JSON="scenarios/water_rights_beta_squeezed/scenario_analysis.json"
RESULTS_DIR="tests/self_play/results"

# Map model name → provider for --per-faction-providers.
provider_for_model() {
  case "$1" in
    gpt-*|o[1-4]*) echo "openai" ;;
    claude-*)      echo "anthropic" ;;
    gemini-*)      echo "google" ;;
    *)             echo "unknown" ;;
  esac
}

# Build the --per-faction-providers JSON (all three factions same model).
providers_json() {
  local model="$1"
  local provider
  provider=$(provider_for_model "$model")
  if [ "$provider" = "unknown" ]; then
    echo "ERROR: cannot infer provider for model '$model'" >&2
    exit 2
  fi
  printf '{"alpha":{"provider":"%s","model":"%s"},"beta":{"provider":"%s","model":"%s"},"gamma":{"provider":"%s","model":"%s"}}' \
    "$provider" "$model" "$provider" "$model" "$provider" "$model"
}

# Short tag for output filenames (gpt-5.4-mini → gpt54mini).
model_tag() {
  echo "$1" | tr -d '.-' | tr '[:upper:]' '[:lower:]'
}

cmd_probe() {
  local model="$1"
  echo "[probe] model=$model (python=$PY)"
  "$PY" -m tests.self_play.probe_providers \
    --providers "$(providers_json "$model")"
}

cmd_run() {
  local model="$1"
  local mode="$2"
  local run_n="$3"

  if [ "$mode" != "full" ] && [ "$mode" != "bare" ]; then
    echo "ERROR: mode must be 'full' or 'bare', got '$mode'" >&2
    exit 2
  fi

  local tag
  tag=$(model_tag "$model")
  local output="${RESULTS_DIR}/run14_${mode}_${tag}_beta_squeezed_${run_n}.json"

  local bare_flag=""
  if [ "$mode" = "bare" ]; then
    bare_flag="--bare-prompt"
  fi

  echo "[run] model=$model mode=$mode run=$run_n output=$output (python=$PY)"
  "$PY" -m tests.self_play.run_simulation \
    --scenario "$SCENARIO_MD" \
    --analysis-json "$ANALYSIS_JSON" \
    --rounds 4 \
    --per-faction-providers "$(providers_json "$model")" \
    $bare_flag \
    --output "$output"

  echo "[done] $output"
  # Quick eyeball of the headline metric.
  "$PY" -c "
import json
d = json.load(open('$output'))
scores = d.get('scores', {})
print(f'  negotiated_surplus_share = {scores.get(\"negotiated_surplus_share\", \"?\")}')
print(f'  pareto_efficiency        = {scores.get(\"pareto_efficiency\", \"?\")}')
print(f'  faction_deltas           = {scores.get(\"faction_deltas\", \"?\")}')
print(f'  bare_mode (metadata)     = {d.get(\"metadata\", {}).get(\"bare_mode\", d.get(\"bare_mode\", \"?\"))}')
"
}

cmd_summary() {
  echo "model            | mode | run | surplus_share | pareto_eff"
  echo "-----------------+------+-----+---------------+-----------"
  for f in ${RESULTS_DIR}/run14_*.json; do
    [ -f "$f" ] || continue
    "$PY" -c "
import json, os, re
f = '$f'
d = json.load(open(f))
s = d.get('scores', {})
name = os.path.basename(f).replace('.json', '')
m = re.match(r'run14_(full|bare)_(.+?)_beta_squeezed_(\d+)', name)
if not m:
    print(f'{name:<40} | ???')
else:
    mode, model_tag, run_n = m.groups()
    surplus = s.get('negotiated_surplus_share', '?')
    pareto = s.get('pareto_efficiency', '?')
    surplus_str = f'{surplus:.3f}' if isinstance(surplus, (int, float)) else str(surplus)
    pareto_str  = f'{pareto:.3f}'  if isinstance(pareto, (int, float))  else str(pareto)
    print(f'{model_tag:<16} | {mode:<4} | {run_n:<3} | {surplus_str:<13} | {pareto_str}')
"
  done
}

# --- dispatch ---

if [ $# -lt 1 ]; then
  echo "Usage: bash tools/ablation.sh probe MODEL"
  echo "       bash tools/ablation.sh run MODEL MODE RUN_N"
  echo "       bash tools/ablation.sh summary"
  exit 1
fi

case "$1" in
  probe)
    [ $# -eq 2 ] || { echo "Usage: probe MODEL"; exit 1; }
    cmd_probe "$2"
    ;;
  run)
    [ $# -eq 4 ] || { echo "Usage: run MODEL MODE RUN_N"; exit 1; }
    cmd_run "$2" "$3" "$4"
    ;;
  summary)
    cmd_summary
    ;;
  *)
    echo "Unknown subcommand: $1" >&2
    exit 1
    ;;
esac
