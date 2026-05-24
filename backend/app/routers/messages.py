"""Message history router — query persisted messages by agent or channel."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Message
from app.schemas import MessageResponse

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/agent/{agent_id}", response_model=list[MessageResponse])
async def get_agent_messages(
    agent_id: str, limit: int = 50, db: AsyncSession = Depends(get_db)
) -> list[Message]:
    """Return messages for a specific agent, ordered chronologically."""
    result = await db.execute(
        select(Message)
        .where(Message.agent_id == agent_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    return list(reversed(messages))


@router.get("/channel/{channel}", response_model=list[MessageResponse])
async def get_channel_messages(
    channel: str, limit: int = 50, db: AsyncSession = Depends(get_db)
) -> list[Message]:
    """Return messages for a specific channel (web, telegram, inter-agent)."""
    result = await db.execute(
        select(Message)
        .where(Message.channel == channel)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    return list(reversed(messages))
