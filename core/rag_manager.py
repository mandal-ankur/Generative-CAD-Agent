"""
core/rag_manager.py
===================
Retrieval-Augmented Generation over build123d documentation.

ChromaDB  : <project>/.DB/          (PersistentClient — portable)
Docs      : <project>/../github/build123d-docs/   (auto-discovered)
Embedding : all-MiniLM-L6-v2        (sentence-transformers, CPU-friendly)

All paths are resolved relative to THIS file so the project is
device-independent — no hard-coded absolute paths anywhere.
"""

import os

os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")

# ── Path anchors (portable) ────────────────────────────────────────────────────
_PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_CHROMA  = os.path.join(_PROJECT, ".DB")
_DOCS_DIRS = [
    os.path.join(_PROJECT, "build123d"),
    os.path.join(_PROJECT, "chroma"),
    os.path.join(_PROJECT, "langgraph"),
    os.path.join(_PROJECT, "ollama-python"),
]

COLLECTION_NAME = "build123d_docs"
EMBED_MODEL     = "all-MiniLM-L6-v2"

# ── Lazy singletons (avoid heavy imports at module load time) ──────────────────
_client = None
_model  = None


def _get_client():
    global _client
    if _client is None:
        import chromadb
        os.makedirs(_CHROMA, exist_ok=True)
        _client = chromadb.PersistentClient(path=_CHROMA)
    return _client


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


# ── Internal helpers ──────────────────────────────────────────────────────────

def _docs_dirs() -> list[str]:
    return [p for p in _DOCS_DIRS if os.path.isdir(p)]


def _iter_docs(root: str):
    for dirpath, _, files in os.walk(root):
        for fname in files:
            if fname.endswith((".rst", ".md")):
                yield os.path.join(dirpath, fname)


def _chunks(text: str, size: int = 500):
    words = text.split()
    for i in range(0, len(words), size):
        yield " ".join(words[i:i + size])


# ── Public API ────────────────────────────────────────────────────────────────

def build_vector_db() -> int:
    """
    Index all build123d docs into ChromaDB.
    Returns the number of text chunks indexed.
    Call once (or to rebuild) — idempotent.
    """
    docs_dirs = _docs_dirs()
    if not docs_dirs:
        raise FileNotFoundError(
            "None of the docs directories found inside project folder. Expected:\n" +
            "\n".join(f"  {p}" for p in _DOCS_DIRS)
        )

    client     = _get_client()
    model      = _get_model()
    collection = client.get_or_create_collection(COLLECTION_NAME)

    # Wipe and re-index
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.get_or_create_collection(COLLECTION_NAME)

    documents, metadatas, ids = [], [], []
    for docs in docs_dirs:
        for fpath in _iter_docs(docs):
            try:
                text = open(fpath, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for i, chunk in enumerate(_chunks(text)):
                documents.append(chunk)
                metadatas.append({"source": os.path.relpath(fpath, _PROJECT)})
                ids.append(f"d{len(ids)}")

    if not documents:
        return 0

    embeddings = model.encode(documents, show_progress_bar=True).tolist()
    collection.add(ids=ids, documents=documents,
                   metadatas=metadatas, embeddings=embeddings)
    return len(documents)


def retrieve_context(query: str, k: int = 3) -> list[str]:
    """Return up to k most relevant doc chunks for the query. Never raises."""
    try:
        client     = _get_client()
        model      = _get_model()
        collection = client.get_collection(COLLECTION_NAME)
        embedding  = model.encode([query], show_progress_bar=False).tolist()
        results    = collection.query(query_embeddings=embedding, n_results=k)
        docs       = results.get("documents", [[]])
        return docs[0] if docs else []
    except Exception:
        return []


def db_ready() -> bool:
    """True if the ChromaDB collection exists and has at least one document."""
    try:
        return _get_client().get_collection(COLLECTION_NAME).count() > 0
    except Exception:
        return False
