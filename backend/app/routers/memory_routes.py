"""Memory management routes — view, add, delete agent memories."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.memory import (
    get_long_term_facts,
    store_long_term,
    delete_long_term_fact,
    recall_short_term,
    recall_long_term,
    clear_agent_memory,
)

router = APIRouter(prefix="/memory", tags=["memory"])


class FactCreate(BaseModel):
    fact: str
    source: str = "manual"


class MemoryQuery(BaseModel):
    query: str
    top_k: int = 5


@router.get("/{agent_id}/long-term")
async def list_long_term_facts(agent_id: str, limit: int = 50) -> dict:
    """Return stored long-term memory facts for an agent."""
    facts = get_long_term_facts(agent_id, limit=limit)
    return {"agent_id": agent_id, "facts": facts}


@router.post("/{agent_id}/long-term")
async def add_long_term_fact(agent_id: str, data: FactCreate) -> dict:
    """Persist a new long-term fact for an agent."""
    store_long_term(agent_id, data.fact, source=data.source)
    return {"status": "stored", "fact": data.fact}


@router.delete("/{agent_id}/long-term/{fact_id}")
async def remove_long_term_fact(agent_id: str, fact_id: str) -> dict:
    """Delete a specific long-term fact by ID."""
    delete_long_term_fact(agent_id, fact_id)
    return {"status": "deleted"}


@router.post("/{agent_id}/recall")
async def recall_memories(agent_id: str, data: MemoryQuery) -> dict:
    """Semantic recall across short-term and long-term memory."""
    short = recall_short_term(agent_id, data.query, top_k=data.top_k)
    long = recall_long_term(agent_id, data.query, top_k=data.top_k)
    return {
        "agent_id": agent_id,
        "query": data.query,
        "short_term": short,
        "long_term": long,
    }


@router.delete("/{agent_id}/clear")
async def clear_memory(agent_id: str, memory_type: str = "all") -> dict:
    """Clear an agent's memory (short-term, long-term, or all)."""
    clear_agent_memory(agent_id, memory_type)
    return {"status": "cleared", "memory_type": memory_type}
