"""
Semantic Memory Service for AI Agents.

Two-tier memory architecture:
- Short-term memory: Recent conversation window + semantic retrieval of relevant
  past messages within the current session. Stored in ChromaDB per-agent collection.
- Long-term memory: Persistent facts, preferences, and key information extracted
  from conversations. Survives across sessions. Stored in a separate ChromaDB
  collection with explicit "remember" markers.

Both tiers use sentence-transformers (all-MiniLM-L6-v2, ~80MB) for local
embeddings — no API calls, fully offline.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Singleton embedding model (~80MB, loads once)
_embed_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.ClientAPI] = None

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
SHORT_TERM_WINDOW = 20  # last N messages always included
SEMANTIC_TOP_K = 5  # top-K semantically similar past messages
LONG_TERM_TOP_K = 5  # top-K long-term facts to retrieve


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        logger.info("Loading embedding model: %s", EMBED_MODEL_NAME)
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


def _get_chroma() -> chromadb.ClientAPI:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.Client(
            ChromaSettings(
                anonymized_telemetry=False,
                is_persistent=True,
                persist_directory="./data/chromadb",
            )
        )
    return _chroma_client


def _embed(texts: list[str]) -> list[list[float]]:
    model = _get_embed_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()


# ---------------------------------------------------------------------------
# Short-Term Memory (conversation-scoped semantic recall)
# ---------------------------------------------------------------------------


def store_short_term(
    agent_id: str, role: str, content: str, message_id: str | None = None
):
    """Store a message in the agent's short-term semantic memory."""
    chroma = _get_chroma()
    collection = chroma.get_or_create_collection(
        name=f"stm_{agent_id}",
        metadata={"hnsw:space": "cosine"},
    )
    doc_id = message_id or str(uuid.uuid4())
    embedding = _embed([content])
    collection.add(
        ids=[doc_id],
        documents=[content],
        embeddings=embedding,
        metadatas=[
            {
                "role": role,
                "agent_id": agent_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )


def recall_short_term(
    agent_id: str, query: str, top_k: int = SEMANTIC_TOP_K
) -> list[dict]:
    """Retrieve semantically similar past messages for this agent."""
    chroma = _get_chroma()
    try:
        collection = chroma.get_collection(name=f"stm_{agent_id}")
    except Exception:
        return []

    if collection.count() == 0:
        return []

    embedding = _embed([query])
    results = collection.query(
        query_embeddings=embedding,
        n_results=min(top_k, collection.count()),
    )

    memories = []
    for i in range(len(results["ids"][0])):
        memories.append(
            {
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "role": results["metadatas"][0][i].get("role", "unknown"),
                "timestamp": results["metadatas"][0][i].get("timestamp", ""),
                "distance": (
                    results["distances"][0][i] if results.get("distances") else None
                ),
            }
        )
    return memories


# ---------------------------------------------------------------------------
# Long-Term Memory (persistent facts & knowledge)
# ---------------------------------------------------------------------------


def store_long_term(
    agent_id: str, fact: str, source: str = "conversation", fact_id: str | None = None
):
    """Store a long-term fact/knowledge for this agent."""
    chroma = _get_chroma()
    collection = chroma.get_or_create_collection(
        name=f"ltm_{agent_id}",
        metadata={"hnsw:space": "cosine"},
    )
    doc_id = fact_id or str(uuid.uuid4())
    embedding = _embed([fact])
    collection.add(
        ids=[doc_id],
        documents=[fact],
        embeddings=embedding,
        metadatas=[
            {
                "agent_id": agent_id,
                "source": source,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )


def recall_long_term(
    agent_id: str, query: str, top_k: int = LONG_TERM_TOP_K
) -> list[dict]:
    """Retrieve semantically relevant long-term facts for this agent."""
    chroma = _get_chroma()
    try:
        collection = chroma.get_collection(name=f"ltm_{agent_id}")
    except Exception:
        return []

    if collection.count() == 0:
        return []

    embedding = _embed([query])
    results = collection.query(
        query_embeddings=embedding,
        n_results=min(top_k, collection.count()),
    )

    facts = []
    for i in range(len(results["ids"][0])):
        facts.append(
            {
                "id": results["ids"][0][i],
                "fact": results["documents"][0][i],
                "source": results["metadatas"][0][i].get("source", ""),
                "timestamp": results["metadatas"][0][i].get("timestamp", ""),
                "distance": (
                    results["distances"][0][i] if results.get("distances") else None
                ),
            }
        )
    return facts


def get_long_term_facts(agent_id: str, limit: int = 50) -> list[dict]:
    """Get all long-term facts for an agent (for UI display)."""
    chroma = _get_chroma()
    try:
        collection = chroma.get_collection(name=f"ltm_{agent_id}")
    except Exception:
        return []

    if collection.count() == 0:
        return []

    results = collection.get(limit=limit, include=["documents", "metadatas"])
    facts = []
    for i in range(len(results["ids"])):
        facts.append(
            {
                "id": results["ids"][i],
                "fact": results["documents"][i],
                "source": results["metadatas"][i].get("source", ""),
                "timestamp": results["metadatas"][i].get("timestamp", ""),
            }
        )
    return facts


def delete_long_term_fact(agent_id: str, fact_id: str):
    """Delete a specific long-term fact."""
    chroma = _get_chroma()
    try:
        collection = chroma.get_collection(name=f"ltm_{agent_id}")
        collection.delete(ids=[fact_id])
    except Exception:
        pass


def clear_agent_memory(agent_id: str, memory_type: str = "all"):
    """Clear an agent's memory. memory_type: 'short', 'long', or 'all'."""
    chroma = _get_chroma()
    if memory_type in ("short", "all"):
        try:
            chroma.delete_collection(name=f"stm_{agent_id}")
        except Exception:
            pass
    if memory_type in ("long", "all"):
        try:
            chroma.delete_collection(name=f"ltm_{agent_id}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Combined recall: builds context for the LLM
# ---------------------------------------------------------------------------


def build_memory_context(
    agent_id: str,
    current_query: str,
    recent_messages: list[dict] | None = None,
) -> str:
    """
    Build a memory context string for injection into the agent's prompt.

    1. Recall relevant long-term facts
    2. Recall semantically similar past short-term messages
    3. Combine with recent conversation window

    Returns a formatted string to prepend to the system prompt.
    """
    parts = []

    # Long-term facts
    lt_facts = recall_long_term(agent_id, current_query)
    if lt_facts:
        facts_text = "\n".join(f"- {f['fact']}" for f in lt_facts)
        parts.append(f"[Long-Term Memory — relevant facts]\n{facts_text}")

    # Semantic short-term recall (beyond the recent window)
    st_memories = recall_short_term(agent_id, current_query)
    if st_memories:
        # Filter out messages already in the recent window
        recent_ids = {m.get("id") for m in (recent_messages or [])}
        unique = [m for m in st_memories if m["id"] not in recent_ids]
        if unique:
            mem_text = "\n".join(
                f"- [{m['role']}]: {m['content']}" for m in unique[:SEMANTIC_TOP_K]
            )
            parts.append(
                f"[Short-Term Memory — semantically relevant past messages]\n{mem_text}"
            )

    if not parts:
        return ""

    return "\n\n".join(parts)
