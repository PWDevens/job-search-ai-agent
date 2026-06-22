# Retrieval store: why ChromaDB (and when to consider Pinecone)

**Decision: stay on ChromaDB (embedded).** Pinecone is a good product but the wrong fit
for this app today.

## Why ChromaDB fits this app

| Factor | ChromaDB (embedded) | Pinecone (hosted) |
|---|---|---|
| **Privacy** | Vectors + metadata live on-disk locally. Nothing leaves the machine. | Vectors + metadata sent to a third-party cloud. Breaks the app's core "nothing leaves your computer" promise. |
| **Setup / ops** | Zero. A folder (`data/chroma/`). No server, no account. | Needs an account, API key, network, index provisioning. |
| **Cost** | Free. | Paid beyond a small free tier. |
| **Scale** | Comfortable to ~100k+ vectors on a laptop. | Built for 10M–1B+ vectors, high QPS, many clients. |
| **Offline** | Works with no internet. | Requires connectivity. |

This is a **single-user, local-first, privacy-first** tool holding hundreds–thousands of
job/resume vectors. ChromaDB covers that with no moving parts. Pinecone's strengths
(massive scale, managed HA, high concurrency) are capabilities this app doesn't use —
they'd be pure cost and a privacy regression.

## When to revisit Pinecone (or another hosted store)

Switch only if the app's shape changes to:
- **Multi-user / hosted SaaS** — many concurrent users hitting one shared index.
- **>~1M vectors** — corpus too large to keep on one machine's disk/RAM.
- **Multiple app instances** sharing one vector store (horizontal scaling).
- A hard requirement for managed backups / HA on the vector layer.

If none of those are true, ChromaDB remains the right call.

## Swap path (if it ever comes to that)

The retrieval layer is already isolated behind one seam: **`app/retrieval/client.py`**.
A Pinecone (or Qdrant/pgvector) move touches only that file's five functions:

- `get_or_create_collection()`
- `upsert_documents()`
- `query_collection()`
- `delete_collection()`
- `health_check()`

All callers — `app/pipeline/matcher.py`, `app/pipeline/ingest.py`,
`app/agents/rag_knowledge.py` — call those functions and would **not** change. You'd:

1. Reimplement the five functions against the new backend.
2. Add `PINECONE_API_KEY` / index-name to `app/config.py` and `.env`.
3. Keep the local Sentence-Transformers embeddings (or switch — separate decision).

Because the seam is clean, this is a contained change, not a rewrite — which is exactly
why there's no need to do it pre-emptively.
