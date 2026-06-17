#!/bin/bash
# tools/ablation_jsm1.sh — Dispatch a single bare-vs-full ablation cell
# on the joint_space_mission_v1 scenario.
#
# Mirrors tools/ablation.sh exactly, except:
#   - scenario fixed to joint_space_mission (multi-Pareto, 3 distinct Pareto deals)
#   - output filenames suffixed run16_<mode>_<modeltag>_jsm1_<n>.json
#     (Run 15 was the calibration; Run 16 is the full bare-vs-full matrix)
#
# Subcommands:
#   probe MODEL
#       One trivial JSON call per faction (~$0.003) to validate keys + model.
#   run MODEL MODE RUN_N
#       Fire one cell: 4-round game, all factions on MODEL, MODE = full|bare.
#       Examples:
#         tools/ablation_jsm1.sh run gpt-4.1-nano full 1
#         tools/ablation_jsm1.sh run claude-sonnet-4-6 bare 1
#   summary
#       Print headline metrics for existing run16_*.json files.

set -euo pipefail

VENV_PYTHON="$(pwd)/.venv/bin/python"
if [ -x "$VENV_PYTHON" ]; then
  PY="$VENV_PYTHON"
else
  echo "[warn] .venv/bin/python not found at $VENV_PYTHON — falling back to system python3" >&2
  PY="python3"
fi

SCENARIO_MD="tests/self_play/scenarios/joint_space_mission.md"
ANALYSIS_JSON="tests/self_play/scenarios/joint_space_mission_v1/scenario_analysis.json"
RESULTS_DIR="tests/self_play/results"

provider_for_model() {
  case "$1" in
    gpt-*|o[1-4]*) echo "openai" ;;
    claude-*)      echo "anthropic" ;;
    gemini-*)      echo "google" ;;
    *)             echo "unknown" ;;
  esac
}

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
  local output="${RESULTS_DIR}/run16_${mode}_${tag}_jsm1_${run_n}.json"

  local bare_flag=""
  if [ "$mode" = "bare" ]; then
    bare_flag="--bare-prompt"
  fi

  echo "[run] model=$model mode=$mode run=$run_n output=$output (python=$PY)"
  "$PY" -m tests.self_play.run_simulation \
    --scenario "$SCENARIO_MD" \
    --analysis-json "$ANALYSIS_JSON" \
    --scenario-title "Joint Space Mission" \
    --rounds 4 \
    --per-faction-providers "$(providers_json "$model")" \
    $bare_flag \
    --output "$output"

  echo "[done] $output"
  "$PY" -c "
import json
d = json.load(open('$output'))
s = d.get('scores', {})
print(f'  deal_reached             = {s.get(\"deal_reached\")}')
print(f'  agreed_outcomes          = {s.get(\"agreed_outcomes\")}')
print(f'  negotiated_surplus_share = {s.get(\"negotiated_surplus_share\", \"?\")}')
print(f'  pareto_efficiency        = {s.get(\"pareto_efficiency\", \"?\")}')
print(f'  faction_deltas           = {s.get(\"faction_deltas\", \"?\")}')
print(f'  bare_mode (metadata)     = {d.get(\"metadata\", {}).get(\"bare_mode\", d.get(\"bare_mode\", \"?\"))}')
"
}

cmd_summary() {
  echo "model            | mode | run | deal? | surplus_share | pareto_eff | deltas"
  echo "-----------------+------+-----+-------+---------------+------------+--------"
  for f in ${RESULTS_DIR}/run16_*.json; do
    [ -f "$f" ] || continue
    "$PY" -c "
import json, os, re
f = '$f'
d = json.load(open(f))
s = d.get('scores', {})
name = os.path.basename(f).replace('.json', '')
m = re.match(r'run16_(full|bare)_(.+?)_jsm1_(\d+)', name)
if not m:
    print(f'{name:<40} | ???')
else:
    mode, model_tag, run_n = m.groups()
    deal = s.get('deal_reached', '?')
    surplus = s.get('negotiated_surplus_share', '?')
    pareto = s.get('pareto_efficiency', '?')
    deltas = s.get('faction_deltas', '?')
    surplus_str = f'{surplus:.3f}' if isinstance(surplus, (int, float)) else str(surplus)
    pareto_str  = f'{pareto:.3f}'  if isinstance(pareto, (int, float))  else str(pareto)
    print(f'{model_tag:<16} | {mode:<4} | {run_n:<3} | {str(deal):<5} | {surplus_str:<13} | {pareto_str:<10} | {deltas}')
"
  done
}

if [ $# -lt 1 ]; then
  echo "Usage: bash tools/ablation_jsm1.sh probe MODEL"
  echo "       bash tools/ablation_jsm1.sh run MODEL MODE RUN_N"
  echo "       bash tools/ablation_jsm1.sh summary"
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
