#!/bin/bash
# tools/_temp_run_jsm1_calib.sh - Dispatch single self-play run on
# joint_space_mission_v1. Mirrors ablation.sh's invocation pattern.
#
# Usage: bash tools/_temp_run_jsm1_calib.sh MODEL RUN_N
#   MODEL = gpt-5.4-mini | claude-sonnet-4-6 | ...
#   RUN_N = positive integer (file suffix)
#
# Output: tests/self_play/results/run15_calib_<modeltag>_jsm1_<n>.json
set -euo pipefail

MODEL="$1"
RUN_N="$2"

VENV_PYTHON="$(pwd)/.venv/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
  echo "ERROR: .venv/bin/python missing" >&2
  exit 2
fi

case "$MODEL" in
  gpt-*|o[1-4]*) PROVIDER="openai" ;;
  claude-*)      PROVIDER="anthropic" ;;
  gemini-*)      PROVIDER="google" ;;
  *) echo "ERROR: unknown provider for model '$MODEL'" >&2; exit 2 ;;
esac

TAG=$(echo "$MODEL" | tr -d '.-' | tr '[:upper:]' '[:lower:]')

SCENARIO_MD="scenarios/joint_space_mission.md"
ANALYSIS_JSON="scenarios/joint_space_mission_v1/scenario_analysis.json"
OUTPUT="tests/self_play/results/run15_calib_${TAG}_jsm1_${RUN_N}.json"

PROVIDERS_JSON=$(printf '{"alpha":{"provider":"%s","model":"%s"},"beta":{"provider":"%s","model":"%s"},"gamma":{"provider":"%s","model":"%s"}}' \
  "$PROVIDER" "$MODEL" "$PROVIDER" "$MODEL" "$PROVIDER" "$MODEL")

echo "[run15] model=$MODEL provider=$PROVIDER run=$RUN_N output=$OUTPUT"

"$VENV_PYTHON" -m tests.self_play.run_simulation \
  --scenario "$SCENARIO_MD" \
  --analysis-json "$ANALYSIS_JSON" \
  --scenario-title "Joint Space Mission" \
  --rounds 4 \
  --per-faction-providers "$PROVIDERS_JSON" \
  --output "$OUTPUT"

echo "[done] $OUTPUT"

"$VENV_PYTHON" -c "
import json
d = json.load(open('$OUTPUT'))
s = d.get('scores', {})
print(f'  deal_reached    = {s.get(\"deal_reached\")}')
print(f'  agreed_outcomes = {s.get(\"agreed_outcomes\")}')
print(f'  surplus_share   = {s.get(\"negotiated_surplus_share\")}')
print(f'  faction_deltas  = {s.get(\"faction_deltas\")}')
"
