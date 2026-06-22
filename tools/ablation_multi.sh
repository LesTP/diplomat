#!/bin/bash
# tools/ablation_multi.sh — Generalized single-cell dispatcher.
# Accepts MODEL (any provider/model OpenRouter or native), SCENARIO
# (wrbeta | wrsym | wralpha | jsm1 | succ), MODE (full|bare), RUN_N.
#
# Mirrors tools/ablation.sh + tools/ablation_jsm1.sh, generalized
# across scenario + provider. Output naming:
#   run17_<mode>_<modeltag>_<scenariotag>_<n>.json
# (Run 17 = OpenRouter multi-provider probe, post-Run-16.)
# Mixed-population runs tag as run17_<mode>_mix-<tagA>-<tagB>-<tagC>_<scen>_<n>.
#
# Subcommands:
#   probe MODEL
#       One trivial JSON call per faction (~$0.003 native, varies on
#       OpenRouter) to validate keys + model name.
#   probemix 'faction=MODEL,faction=MODEL,...'
#       Same probe for a heterogeneous (mixed-model) population.
#   run MODEL SCENARIO MODE RUN_N
#       Homogeneous population (same MODEL on every faction). Examples:
#         tools/ablation_multi.sh run deepseek/deepseek-chat jsm1 full 1
#         tools/ablation_multi.sh run meta-llama/llama-3.3-70b-instruct wrbeta full 1
#   runmix 'faction=MODEL,faction=MODEL,...' SCENARIO MODE RUN_N
#       Heterogeneous population — a different model per faction. Example:
#         tools/ablation_multi.sh runmix \
#           'alpha=claude-sonnet-4-6,beta=gpt-5.4-mini,gamma=deepseek/deepseek-chat' \
#           succ full 1
#       Per-faction models are recorded in the result JSON's faction_models
#       map, so tests/self_play/rank_aggregator.py can attribute rank->model.
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

# Build a per-faction providers JSON from a "faction=MODEL,faction=MODEL,..."
# spec (heterogeneous / mixed-model population). Provider is inferred per
# model, exactly like the homogeneous path. Exits non-zero on a bad pair or
# unknown provider.
providers_json_mixed() {
  local spec="$1"
  local json="{"
  local first=1
  local pair faction model provider
  local saved_ifs="$IFS"
  IFS=','
  set -f
  for pair in $spec; do
    faction="${pair%%=*}"
    model="${pair#*=}"
    if [ "$faction" = "$pair" ] || [ -z "$faction" ] || [ -z "$model" ]; then
      IFS="$saved_ifs"; set +f
      echo "ERROR: bad 'faction=model' pair: '$pair'" >&2
      exit 2
    fi
    provider=$(provider_for_model "$model")
    if [ "$provider" = "unknown" ]; then
      IFS="$saved_ifs"; set +f
      echo "ERROR: cannot infer provider for model '$model' (faction '$faction')" >&2
      exit 2
    fi
    [ "$first" -eq 0 ] && json="${json},"
    json="${json}\"${faction}\":{\"provider\":\"${provider}\",\"model\":\"${model}\"}"
    first=0
  done
  IFS="$saved_ifs"; set +f
  if [ "$first" -eq 1 ]; then
    echo "ERROR: empty mixed-model spec" >&2
    exit 2
  fi
  json="${json}}"
  printf '%s' "$json"
}

# Filename tag for a mixed population: "mix-<tagA>-<tagB>-<tagC>" in spec order.
model_tag_mixed() {
  local spec="$1"
  local tag="mix"
  local pair model
  local saved_ifs="$IFS"
  IFS=','
  set -f
  for pair in $spec; do
    model="${pair#*=}"
    tag="${tag}-$(model_tag "$model")"
  done
  IFS="$saved_ifs"; set +f
  printf '%s' "$tag"
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

cmd_probemix() {
  local spec="$1"
  echo "[probemix] spec=$spec (python=$PY)"
  local providers
  if ! providers=$(providers_json_mixed "$spec"); then
    exit 2
  fi
  "$PY" -m tests.self_play.probe_providers --providers "$providers"
}

cmd_runmix() {
  local spec="$1"
  local scenario="$2"
  local mode="$3"
  local run_n="$4"

  if [ "$mode" != "full" ] && [ "$mode" != "bare" ]; then
    echo "ERROR: mode must be 'full' or 'bare', got '$mode'" >&2
    exit 2
  fi

  local providers
  if ! providers=$(providers_json_mixed "$spec"); then
    exit 2
  fi

  local paths
  paths=$(scenario_paths "$scenario")
  local scenario_md="${paths%%|*}"
  local rest="${paths#*|}"
  local analysis_json="${rest%%|*}"
  local title="${rest#*|}"

  local tag
  tag=$(model_tag_mixed "$spec")
  local output="${RESULTS_DIR}/run17_${mode}_${tag}_${scenario}_${run_n}.json"

  local bare_flag=""
  [ "$mode" = "bare" ] && bare_flag="--bare-prompt"

  local temp_flag=""
  [ -n "${TEMPERATURE:-}" ] && temp_flag="--temperature ${TEMPERATURE}"

  echo "[runmix] spec=$spec scenario=$scenario mode=$mode run=$run_n output=$output"
  "$PY" -m tests.self_play.run_simulation \
    --scenario "$scenario_md" \
    --analysis-json "$analysis_json" \
    --scenario-title "$title" \
    --rounds 4 \
    --per-faction-providers "$providers" \
    $bare_flag \
    $temp_flag \
    --output "$output"

  echo "[done] $output"
  "$PY" -c "
import json
d = json.load(open('$output'))
s = d.get('scores', {})
print(f'  deal_reached   = {s.get(\"deal_reached\")}')
print(f'  faction_ranks  = {s.get(\"faction_ranks\", \"?\")}')
print(f'  faction_deltas = {s.get(\"faction_deltas\", \"?\")}')
print(f'  faction_models = {d.get(\"faction_models\", \"?\")}')
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

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [ $# -lt 1 ]; then
    echo "Usage: bash tools/ablation_multi.sh probe MODEL"
    echo "       bash tools/ablation_multi.sh probemix 'faction=MODEL,faction=MODEL,...'"
    echo "       bash tools/ablation_multi.sh run MODEL SCENARIO MODE RUN_N"
    echo "       bash tools/ablation_multi.sh runmix 'faction=MODEL,...' SCENARIO MODE RUN_N"
    echo "       bash tools/ablation_multi.sh summary"
    exit 1
  fi

  case "$1" in
    probe)
      [ $# -eq 2 ] || { echo "Usage: probe MODEL"; exit 1; }
      cmd_probe "$2"
      ;;
    probemix)
      [ $# -eq 2 ] || { echo "Usage: probemix 'faction=MODEL,...'"; exit 1; }
      cmd_probemix "$2"
      ;;
    run)
      [ $# -eq 5 ] || { echo "Usage: run MODEL SCENARIO MODE RUN_N"; exit 1; }
      cmd_run "$2" "$3" "$4" "$5"
      ;;
    runmix)
      [ $# -eq 5 ] || { echo "Usage: runmix 'faction=MODEL,...' SCENARIO MODE RUN_N"; exit 1; }
      cmd_runmix "$2" "$3" "$4" "$5"
      ;;
    summary)
      cmd_summary
      ;;
    *)
      echo "Unknown subcommand: $1" >&2
      exit 1
      ;;
  esac
fi
