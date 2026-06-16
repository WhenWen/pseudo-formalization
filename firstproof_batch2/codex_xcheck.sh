#!/usr/bin/env bash
# Run the Codex CLI cross-check over every mapped error. Each prompt in
# codex_xcheck/prompts/ is sent to `codex exec` with --output-schema so the final
# message is a JSON verdict, captured to codex_xcheck/out/<name>.json.
# Resumable (skips completed); PARALLEL controls concurrency.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_DIR="$HERE/codex_xcheck/prompts"
OUT_DIR="$HERE/codex_xcheck/out"
LOG_DIR="$HERE/codex_xcheck/logs"
WORK_DIR="$HERE/pf_work"
SCHEMA="$HERE/codex_xcheck_schema.json"
mkdir -p "$OUT_DIR" "$LOG_DIR" "$WORK_DIR"
PARALLEL="${PARALLEL:-3}"
FORCE="${FORCE:-0}"

run_one() {
  name="$(basename "$1" .txt)"
  prompt="$PROMPT_DIR/$name.txt"
  out="$OUT_DIR/$name.json"
  log="$LOG_DIR/$name.log"
  if [ "$FORCE" != "1" ] && [ -s "$out" ]; then echo "[$name] done, skip"; return; fi
  start=$(date +%s)
  codex exec --sandbox read-only --skip-git-repo-check --color never \
    -C "$WORK_DIR" --output-schema "$SCHEMA" -o "$out" - < "$prompt" > "$log" 2>&1
  rc=$?; dur=$(( $(date +%s) - start ))
  if [ "$rc" -eq 0 ] && [ -s "$out" ]; then
    echo "[$name] OK ${dur}s $(tr -d '\n' < "$out" | cut -c1-80)"
  else
    echo "[$name] FAILED rc=$rc ${dur}s (see $log)"
  fi
}
export -f run_one
export PROMPT_DIR OUT_DIR LOG_DIR WORK_DIR SCHEMA FORCE

mapfile -t PROMPTS < <(ls "$PROMPT_DIR"/*.txt | sort)
echo "Codex cross-check over ${#PROMPTS[@]} mapping(s), parallelism=$PARALLEL"
printf '%s\n' "${PROMPTS[@]}" | xargs -P "$PARALLEL" -I{} bash -c 'run_one "$@"' _ {}
echo "Done. Verdicts in $OUT_DIR"
