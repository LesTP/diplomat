#!/bin/bash
# tools/ablation_multi.sh — Generalized single-cell dispatcher.
# Accepts MODEL (any provider/model OpenRouter or native), SCENARIO
# (wrbeta | wrsym | wralpha | jsm1), MODE (full|bare), RUN_N.
#
# Mirrors tools/ablation.sh + tools/ablation_jsm1.sh, generalized
# across scenario + provider. Output naming:
#   run17_<mode>_<modeltag>_<scenariotag>_<n>.json
# (Run 17 = OpenRouter multi-provider probe, post-Run-16.)
#
# Subcommands:
#   probe MODEL
#       One trivial JSON call per faction (~$0.003 native, varies on
#       OpenRouter) to validate keys + model name.
#   run MODEL SCENARIO MODE RUN_N
#       Examples:
#         tools/ablation_multi.sh run deepseek/deepseek-chat jsm1 full 1
#         tools/ablation_multi.sh run meta-llama/llama-3.3-70b-instruct wrbeta full 1
#   summary
#       Print run17_*.json results.

set -uo pipefail

VENV_PYTHON="$(pwd)/.venv/bin/python"
if [ -x "$VENV_PYTHON" ]; then
  PY="$VENV_PYTHON"
else
  echo "[warn] .venv/bin/python missing, falling back to system python3" >&2
  PY="python3"
fi

RESULTS_DIR="tests/self_play/results"

provider_for_model() {
  local m="$1"
  if [[ "$m" == *"/"* ]]; then
    echo "openrouter"
    return
  fi
  case "$m" in
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

# Short tag from model name. For openrouter "vendor/model" forms, drop
# the vendor prefix so the filename stays readable.
model_tag() {
  local m="$1"
  if [[ "$m" == *"/"* ]]; then
    m="${m#*/}"
  fi
  echo "$m" | tr -d '.-' | tr '[:upper:]' '[:lower:]'
}

# Resolve scenario tag → (scenario.md, analysis.json, scenario-title).
scenario_paths() {
  case "$1" in
    wrbeta)
      echo "scenarios/water_rights.md|scenarios/water_rights_beta_squeezed/scenario_analysis.json|Water Rights"
      ;;
    wrsym)
      echo "scenarios/water_rights.md|scenarios/water_rights_symmetric_050/scenario_analysis.json|Water Rights"
      ;;
    wralpha)
      echo "scenarios/water_rights.md|scenarios/water_rights_alpha_squeezed/scenario_analysis.json|Water Rights"
      ;;
    jsm1)
      echo "scenarios/joint_space_mission.md|scenarios/joint_space_mission_v1/scenario_analysis.json|Joint Space Mission"
      ;;
    succ)
      echo "scenarios/succession_division.md|scenarios/succession_division_v1/scenario_analysis.json|The Verdanian Succession"
      ;;
    *)
      echo "ERROR: unknown scenario '$1' (expected: wrbeta | wrsym | wralpha | jsm1 | succ)" >&2
      exit 2
      ;;
  esac
}

cmd_probe() {
  local model="$1"
  echo "[probe] model=$model provider=$(provider_for_model "$model") (python=$PY)"
  "$PY" -m tests.self_play.probe_providers \
    --providers "$(providers_json "$model")"
}

cmd_run() {
  local model="$1"
  local scenario="$2"
  local mode="$3"
  local run_n="$4"

  if [ "$mode" != "full" ] && [ "$mode" != "bare" ]; then
    echo "ERROR: mode must be 'full' or 'bare', got '$mode'" >&2
    exit 2
  fi

  local paths
  paths=$(scenario_paths "$scenario")
  local scenario_md="${paths%%|*}"
  local rest="${paths#*|}"
  local analysis_json="${rest%%|*}"
  local title="${rest#*|}"

  local tag
  tag=$(model_tag "$model")
  local output="${RESULTS_DIR}/run17_${mode}_${tag}_${scenario}_${run_n}.json"

  local bare_flag=""
  if [ "$mode" = "bare" ]; then
    bare_flag="--bare-prompt"
  fi

  # Optional uniform temperature override via the TEMPERATURE env var, e.g.
  #   TEMPERATURE=1 bash tools/ablation_multi.sh run gpt-4.1-nano jsm1 bare 1
  # Lets a tier sweep hold temperature constant (the clean cross-provider
  # comparison). Unset => the generator uses the toolkit default (0.7).
  local temp_flag=""
  if [ -n "${TEMPERATURE:-}" ]; then
    temp_flag="--temperature ${TEMPERATURE}"
  fi

  echo "[run] model=$model scenario=$scenario mode=$mode run=$run_n output=$output"
  "$PY" -m tests.self_play.run_simulation \
    --scenario "$scenario_md" \
    --analysis-json "$analysis_json" \
    --scenario-title "$title" \
    --rounds 4 \
    --per-faction-providers "$(providers_json "$model")" \
    $bare_flag \
    $temp_flag \
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
"
}

cmd_summary() {
  echo "model                | scenario | mode | run | deal? | surplus_share | pareto_eff | deltas"
  echo "---------------------+----------+------+-----+-------+---------------+------------+--------"
  for f in ${RESULTS_DIR}/run17_*.json; do
    [ -f "$f" ] || continue
    "$PY" -c "
import json, os, re
f = '$f'
d = json.load(open(f))
s = d.get('scores', {})
name = os.path.basename(f).replace('.json', '')
m = re.match(r'run17_(full|bare)_(.+?)_(wrbeta|wrsym|wralpha|jsm1|succ)_(\d+)', name)
if not m:
    print(f'{name:<60} | ???')
else:
    mode, model_tag, scenario, run_n = m.groups()
    deal = s.get('deal_reached', '?')
    surplus = s.get('negotiated_surplus_share', '?')
    pareto = s.get('pareto_efficiency', '?')
    deltas = s.get('faction_deltas', '?')
    surplus_str = f'{surplus:.3f}' if isinstance(surplus, (int, float)) else str(surplus)
    pareto_str  = f'{pareto:.3f}'  if isinstance(pareto, (int, float))  else str(pareto)
    print(f'{model_tag:<20} | {scenario:<8} | {mode:<4} | {run_n:<3} | {str(deal):<5} | {surplus_str:<13} | {pareto_str:<10} | {deltas}')
"
  done
}

if [ $# -lt 1 ]; then
  echo "Usage: bash tools/ablation_multi.sh probe MODEL"
  echo "       bash tools/ablation_multi.sh run MODEL SCENARIO MODE RUN_N"
  echo "       bash tools/ablation_multi.sh summary"
  exit 1
fi

case "$1" in
  probe)
    [ $# -eq 2 ] || { echo "Usage: probe MODEL"; exit 1; }
    cmd_probe "$2"
    ;;
  run)
    [ $# -eq 5 ] || { echo "Usage: run MODEL SCENARIO MODE RUN_N"; exit 1; }
    cmd_run "$2" "$3" "$4" "$5"
    ;;
  summary)
    cmd_summary
    ;;
  *)
    echo "Unknown subcommand: $1" >&2
    exit 1
    ;;
esac
