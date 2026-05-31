"""
app/chroma/__init__.py — ChromaDB Sub-Package Marker
=====================================================

WHY THIS FILE EXISTS:
---------------------
Marks `chroma/` as a Python package so imports like this work:

    from app.chroma.client import query_collection
    from app.chroma.embeddings import embed_texts

WHAT'S IN THIS PACKAGE:
  client.py     → Thin wrapper around the ChromaDB HTTP client.
                  Manages the connection to the running ChromaDB server
                  (started by docker-compose) and exposes helper functions
                  for upserting and querying collections.

  embeddings.py → Unified embedding interface. Converts text → vectors
                  using either:
                    - Ollama nomic-embed-text (preferred, local LLM server)
                    - Sentence Transformers all-MiniLM-L6-v2 (CPU fallback)
                  ChromaDB needs embeddings to do similarity search.

JUPYTER ANALOGY:
  In a notebook you'd call the ChromaDB library directly in a cell.
  Here, we wrap it so the rest of the app never has to know whether
  we're using Ollama embeddings or Sentence Transformers — it just
  calls `embed_texts(...)` and gets vectors back.

WHAT IS A VECTOR / EMBEDDING?
  A list of ~768 floating-point numbers that represent the "meaning"
  of a piece of text. Two texts that mean similar things produce
  vectors that are close together in this 768-dimensional space.
  ChromaDB stores these vectors and finds the closest ones on demand.
"""
