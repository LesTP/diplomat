#!/bin/bash
# tools/_run_jsm1_matrix.sh — Driver: probes + 12-run jsm1 ablation matrix.
#
# Cells (cheap-first ordering per RUN_PROTOCOL):
#   weak  (gpt-4.1-nano)       full × 3
#   weak  (gpt-4.1-nano)       bare × 3
#   mid   (gpt-5.4-mini)       bare × 3
#   strong (claude-sonnet-4-6) bare × 3
#
# Designed to run inside a detached tmux window on the Pi so SSH disconnects
# don't kill the run. All output tee'd to a logfile + stdout.
#
# Total: ~12 runs, ~$1.50, ~90-120 min wall clock.

set -uo pipefail   # no -e: keep going if one cell fails

LOG="/tmp/jsm1_matrix_$(date +%Y%m%d_%H%M%S).log"

log()  { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

cd "$HOME/workspace/diplomat"

log "=== JSM1 ABLATION MATRIX (Run 16) ==="
log "logfile: $LOG"
log "cwd: $(pwd)"
log ""

log "--- Probes (~\$0.01 total) ---"
for model in gpt-4.1-nano gpt-5.4-mini claude-sonnet-4-6; do
  log ">> probe $model"
  bash tools/ablation_jsm1.sh probe "$model" 2>&1 | tee -a "$LOG"
  log ""
done

log "--- Cells ---"

# Cheap-first ordering. Each entry: MODEL MODE COUNT
declare -a cells=(
  "gpt-4.1-nano        full  3"
  "gpt-4.1-nano        bare  3"
  "gpt-5.4-mini        bare  3"
  "claude-sonnet-4-6   bare  3"
)

for cell in "${cells[@]}"; do
  read -r model mode count <<< "$cell"
  log ""
  log "=== Cell: $model $mode × $count ==="
  for n in $(seq 1 "$count"); do
    log ""
    log ">> $model $mode run=$n"
    bash tools/ablation_jsm1.sh run "$model" "$mode" "$n" 2>&1 | tee -a "$LOG"
  done
done

log ""
log "=== SUMMARY ==="
bash tools/ablation_jsm1.sh summary 2>&1 | tee -a "$LOG"

log ""
log "=== DONE ==="
log "logfile: $LOG"
