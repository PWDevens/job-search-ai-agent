#!/usr/bin/env bash
# Model bake-off FRAMEWORK — find which local model performs best on the eval.
# Holds everything constant (corpus, personas, variant, effort, temp) and varies ONLY --model.
# Per-model: pull -> preflight -> run eval (raw-persisted for $0 offline re-score) -> rm (disk-bounded).
# A model that fails to pull/preflight is skipped, not fatal. Resilient to session interruptions:
# raw banks each persona, so re-score whatever completed with scripts/rescore_raw.py.
#
# Usage:
#   OLLAMA_BASE_URL=https://<pod>.proxy.runpod.net bash scripts/model_bakeoff.sh \
#       phi4-mini-reasoning qwen3:4b deepseek-r1:8b phi4-reasoning:14b gpt-oss:20b magistral
#   env: CHROMA_DB (default data/chroma_atsfull), VARIANT (switching), KEEP_MODELS (don't rm these)
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=.
P="${OLLAMA_BASE_URL:?set OLLAMA_BASE_URL}"
CHROMA="${CHROMA_DB:-data/chroma_atsfull}"
VARIANT="${VARIANT:-switching}"
KEEP=" ${KEEP_MODELS:-} "
unset RUNPOD_ENDPOINT_ID RUNPOD_API_KEY
for m in "$@"; do
  tag="$(echo "$m" | tr ':/.' '___')"
  echo "=== $m ==="
  curl -s --max-time 1800 "$P/api/pull" -d "{\"name\":\"$m\"}" | tail -c 30; echo
  r=$(curl -s --max-time 180 "$P/api/chat" -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"ok\"}],\"stream\":false}")
  if ! echo "$r" | grep -q '"content"'; then echo "  SKIP $m (pull/preflight failed)"; continue; fi
  EFFORT=balanced EVAL_PERSIST_RAW=1 EVAL_OUT="reports/bakeoff_${tag}.csv" CHROMA_DB_PATH="$CHROMA" \
    OLLAMA_BASE_URL="$P" OLLAMA_NUM_CTX=8192 OLLAMA_TIMEOUT=600 \
    python scripts/eval_compare.py --repeats 1 --configs baseline --scenario 9 --temp 0 \
        --variant "$VARIANT" --model "$m" > "reports/bakeoff_${tag}.log" 2>&1
  echo "  done $m"
  case "$KEEP" in *" $m "*) ;; *) curl -s -X DELETE "$P/api/delete" -d "{\"name\":\"$m\"}" >/dev/null ;; esac
done
echo BAKEOFF_DONE
