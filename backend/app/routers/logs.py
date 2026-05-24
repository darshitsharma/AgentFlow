"""Monitoring and logs router — agent logs, execution traces, and platform stats."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import AgentLog, Message, Agent
from app.schemas import AgentLogResponse

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/agent/{agent_id}", response_model=list[AgentLogResponse])
async def get_agent_logs(
    agent_id: str, limit: int = 100, db: AsyncSession = Depends(get_db)
) -> list[AgentLog]:
    """Return logs for a specific agent, ordered chronologically."""
    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.agent_id == agent_id)
        .order_by(AgentLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return list(reversed(logs))


@router.get("/execution/{execution_id}", response_model=list[AgentLogResponse])
async def get_execution_logs(
    execution_id: str, limit: int = 100, db: AsyncSession = Depends(get_db)
) -> list[AgentLog]:
    """Return logs for a specific workflow execution."""
    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.workflow_execution_id == execution_id)
        .order_by(AgentLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return list(reversed(logs))


@router.get("/recent", response_model=list[AgentLogResponse])
async def get_recent_logs(
    limit: int = 50, db: AsyncSession = Depends(get_db)
) -> list[AgentLog]:
    """Return the most recent logs across all agents."""
    result = await db.execute(
        select(AgentLog).order_by(AgentLog.created_at.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return list(reversed(logs))


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)) -> dict:
    """Get platform-wide statistics for the monitoring dashboard."""
    # Total agents
    agent_count = await db.scalar(select(func.count()).select_from(Agent))

    # Active agents
    active_count = await db.scalar(
        select(func.count()).select_from(Agent).where(Agent.is_active == True)
    )

    # Total messages
    msg_count = await db.scalar(select(func.count()).select_from(Message))

    # Total tokens
    total_tokens = await db.scalar(
        select(func.coalesce(func.sum(Message.tokens_used), 0)).select_from(Message)
    )

    # Messages by channel
    channel_result = await db.execute(
        select(Message.channel, func.count()).group_by(Message.channel)
    )
    by_channel = {row[0]: row[1] for row in channel_result.all()}

    # Messages by role
    role_result = await db.execute(
        select(Message.role, func.count()).group_by(Message.role)
    )
    by_role = {row[0]: row[1] for row in role_result.all()}

    # Per-agent token usage
    agent_tokens_result = await db.execute(
        select(
            Agent.id,
            Agent.name,
            func.coalesce(func.sum(Message.tokens_used), 0).label("tokens"),
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Agent.id == Message.agent_id)
        .group_by(Agent.id, Agent.name)
    )
    agent_stats = [
        {"id": row[0], "name": row[1], "tokens_used": row[2], "message_count": row[3]}
        for row in agent_tokens_result.all()
    ]

    # Recent inter-agent messages
    inter_result = await db.execute(
        select(Message)
        .where(Message.channel == "inter-agent")
        .order_by(Message.created_at.desc())
        .limit(20)
    )
    inter_msgs = [
        {
            "id": m.id,
            "agent_id": m.agent_id,
            "role": m.role,
            "content": m.content[:200],
            "tokens_used": m.tokens_used,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in inter_result.scalars().all()
    ]

    return {
        "total_agents": agent_count,
        "active_agents": active_count,
        "total_messages": msg_count,
        "total_tokens": total_tokens,
        "messages_by_channel": by_channel,
        "messages_by_role": by_role,
        "agent_stats": agent_stats,
        "recent_inter_agent": list(reversed(inter_msgs)),
    }
