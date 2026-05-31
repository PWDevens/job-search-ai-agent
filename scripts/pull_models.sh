#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# pull_models.sh — Download Ollama models for Job-Search AI
# Run this ONCE after starting the docker-compose stack.
#
# Usage:
#   bash scripts/pull_models.sh              # pulls default (phi4-mini + nomic-embed-text)
#   bash scripts/pull_models.sh llama3       # pulls Llama-3 8B instead
#   OLLAMA_URL=http://localhost:11434 bash scripts/pull_models.sh
# ══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
CHAT_MODEL="${1:-phi4-mini}"          # override with: bash pull_models.sh llama3
EMBED_MODEL="nomic-embed-text"

echo "═══════════════════════════════════════════════"
echo "  Job-Search AI — Ollama Model Downloader"
echo "  Ollama endpoint: $OLLAMA_URL"
echo "  Chat model:      $CHAT_MODEL"
echo "  Embed model:     $EMBED_MODEL"
echo "═══════════════════════════════════════════════"

# Wait for Ollama to be ready
echo ""
echo "⏳  Waiting for Ollama to be ready…"
until curl -sf "$OLLAMA_URL/api/version" > /dev/null; do
    sleep 3
done
echo "✅  Ollama is up."

# Pull chat model
echo ""
echo "⬇   Pulling chat model: $CHAT_MODEL"
echo "    (This may take several minutes on first run — model files are large)"
curl -X POST "$OLLAMA_URL/api/pull" \
     -H "Content-Type: application/json" \
     -d "{\"name\": \"$CHAT_MODEL\"}" | grep -E '"status"' || true

# Pull embedding model
echo ""
echo "⬇   Pulling embedding model: $EMBED_MODEL"
curl -X POST "$OLLAMA_URL/api/pull" \
     -H "Content-Type: application/json" \
     -d "{\"name\": \"$EMBED_MODEL\"}" | grep -E '"status"' || true

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  ✅  Models ready!                           ║"
echo "║  Chat:  $CHAT_MODEL"
echo "║  Embed: $EMBED_MODEL"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "Model sizes for reference:"
echo "  phi4-mini          ~2.5 GB  (best for low-RAM machines)"
echo "  phi3:mini          ~2.2 GB  (alternative)"
echo "  llama3             ~4.7 GB  (better quality, needs 8 GB RAM)"
echo "  llama3.2:1b        ~1.3 GB  (extreme resource constraint)"
echo "  mistral            ~4.1 GB  (fast, good quality)"
echo "  tinyllama          ~0.6 GB  (demo only, low quality)"
echo "  nomic-embed-text   ~0.3 GB  (required for local embeddings)"
echo ""
echo "To switch models after setup, edit LLM_BACKEND in your .env file"
echo "and restart the app container: docker compose restart app"
