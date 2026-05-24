"""
Chat router — handles user→agent conversations and inter-agent messaging.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Agent, Message
from app.schemas import MessageCreate, MessageResponse
from app.runtime import run_agent

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/{agent_id}", response_model=MessageResponse)
async def chat_with_agent(
    agent_id: str,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
) -> Message:
    """Send a message to an agent and get a response."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if not agent.is_active:
        raise HTTPException(status_code=400, detail="Agent is inactive")

    # Save user message
    user_msg = Message(
        agent_id=agent_id,
        role="user",
        content=data.content,
        channel=data.channel,
    )
    db.add(user_msg)
    await db.commit()

    # Fetch recent messages for context window
    result = await db.execute(
        select(Message)
        .where(Message.agent_id == agent_id)
        .order_by(Message.created_at.desc())
        .limit(20)
    )
    recent_db_msgs = list(reversed(result.scalars().all()))
    recent_messages = [
        {"id": m.id, "role": m.role, "content": m.content} for m in recent_db_msgs
    ]

    # Run agent
    agent_result = await run_agent(
        agent_id=agent_id,
        user_message=data.content,
        system_prompt=agent.system_prompt,
        model=agent.model,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        tool_names=agent.tools or [],
        memory_enabled=agent.memory_enabled,
        recent_messages=recent_messages,
    )

    # Save assistant response
    assistant_msg = Message(
        agent_id=agent_id,
        role="assistant",
        content=agent_result["response"],
        channel=data.channel,
        tokens_used=agent_result["tokens_used"],
        meta_info={
            "tool_calls": agent_result["tool_calls"],
            "memories_stored": agent_result["memories_stored"],
        },
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    return assistant_msg


@router.post("/{agent_id}/inter-agent")
async def inter_agent_message(
    agent_id: str,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send an inter-agent message — one agent talking to another."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Target agent not found")

    # Save the incoming agent message
    incoming_msg = Message(
        agent_id=agent_id,
        role="agent",
        content=data.content,
        channel="inter-agent",
    )
    db.add(incoming_msg)
    await db.commit()

    # Fetch recent messages
    result = await db.execute(
        select(Message)
        .where(Message.agent_id == agent_id)
        .order_by(Message.created_at.desc())
        .limit(20)
    )
    recent_db_msgs = list(reversed(result.scalars().all()))
    recent_messages = [
        {"id": m.id, "role": m.role, "content": m.content} for m in recent_db_msgs
    ]

    # Run agent with the inter-agent message
    agent_result = await run_agent(
        agent_id=agent_id,
        user_message=data.content,
        system_prompt=agent.system_prompt,
        model=agent.model,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        tool_names=agent.tools or [],
        memory_enabled=agent.memory_enabled,
        recent_messages=recent_messages,
    )

    # Save response
    response_msg = Message(
        agent_id=agent_id,
        role="assistant",
        content=agent_result["response"],
        channel="inter-agent",
        tokens_used=agent_result["tokens_used"],
        meta_info={
            "tool_calls": agent_result["tool_calls"],
            "memories_stored": agent_result["memories_stored"],
        },
    )
    db.add(response_msg)
    await db.commit()
    await db.refresh(response_msg)

    return {
        "response": agent_result["response"],
        "tokens_used": agent_result["tokens_used"],
        "tool_calls": agent_result["tool_calls"],
    }
