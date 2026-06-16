#!/usr/bin/env bash
# Run the pseudo-formalisation (PF) rewrite over every fatal-error proof using
# the user's Codex CLI (ChatGPT auth). Each proof's PF prompt is piped to
# `codex exec`; the structured rewrite is captured via --output-last-message.
#
# Usage:
#   ./pf_run.sh                # run all ids in pf_fatal_ids.txt, skip completed
#   ./pf_run.sh 01D 04A        # run only these ids
#   PARALLEL=3 ./pf_run.sh     # run 3 at a time
#   CODEX_MODEL=gpt-5.5 ./pf_run.sh   # force a model (default: codex config)
#   FORCE=1 ./pf_run.sh        # re-run even if output already exists
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_DIR="${PROMPT_DIR:-$HERE/pf_prompts}"
OUT_DIR="${OUT_DIR:-$HERE/pf_outputs}"
LOG_DIR="${LOG_DIR:-$HERE/pf_logs}"
WORK_DIR="$HERE/pf_work"     # empty scratch root so codex doesn't roam the repo
mkdir -p "$OUT_DIR" "$LOG_DIR" "$WORK_DIR"

PARALLEL="${PARALLEL:-1}"
FORCE="${FORCE:-0}"

# id list: args, else the prepared file
if [ "$#" -gt 0 ]; then
  IDS=("$@")
else
  mapfile -t IDS < "$HERE/pf_fatal_ids.txt"
fi

run_one() {
  id="$1"
  prompt="$PROMPT_DIR/$id.prompt.txt"
  out="$OUT_DIR/$id.pf.txt"
  log="$LOG_DIR/$id.log"
  if [ ! -f "$prompt" ]; then echo "[$id] MISSING prompt, skip"; return; fi
  if [ "$FORCE" != "1" ] && [ -s "$out" ]; then echo "[$id] already done, skip"; return; fi

  model_args=()
  [ -n "${CODEX_MODEL:-}" ] && model_args=(-m "$CODEX_MODEL")

  echo "[$id] running PF ..."
  start=$(date +%s)
  codex exec \
    --sandbox read-only \
    --skip-git-repo-check \
    --color never \
    -C "$WORK_DIR" \
    "${model_args[@]}" \
    -o "$out" \
    - < "$prompt" > "$log" 2>&1
  rc=$?
  dur=$(( $(date +%s) - start ))
  if [ "$rc" -eq 0 ] && [ -s "$out" ]; then
    lines=$(wc -l < "$out")
    blocks=$(grep -c "_STATEMENT id=" "$out" 2>/dev/null || echo 0)
    echo "[$id] OK in ${dur}s ($lines lines, $blocks statement blocks) -> $out"
  else
    echo "[$id] FAILED rc=$rc in ${dur}s (see $log)"
  fi
}
export -f run_one
export PROMPT_DIR OUT_DIR LOG_DIR WORK_DIR FORCE CODEX_MODEL

echo "PF over ${#IDS[@]} proof(s), parallelism=$PARALLEL"
if [ "$PARALLEL" -gt 1 ]; then
  printf '%s\n' "${IDS[@]}" | xargs -P "$PARALLEL" -I{} bash -c 'run_one "$@"' _ {}
else
  for id in "${IDS[@]}"; do run_one "$id"; done
fi
echo "Done. Outputs in $OUT_DIR ; logs in $LOG_DIR"
