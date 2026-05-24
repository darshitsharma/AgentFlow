"""
Telegram Bot integration.

Provides:
- Webhook endpoint for receiving Telegram messages
- Routes incoming messages to the assigned agent
- Sends agent responses back to the Telegram chat
- Setup endpoint to register the webhook with Telegram
"""

import logging
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx

from app.database import get_db, async_session
from app.config import settings
from app.models import Agent, Message, Workflow, WorkflowExecution
from app.runtime import run_agent
from app.workflow_engine import execute_workflow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram", tags=["telegram"])

# Track processed Telegram message IDs to prevent duplicate handling from webhook retries
_processed_messages: set[int] = set()
_processed_messages_max = 1000

TELEGRAM_API = "https://api.telegram.org/bot{token}"


async def send_telegram_message(chat_id: int, text: str) -> None:
    """Send a message back to a Telegram chat, splitting into chunks if needed."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping send")
        return
    url = f"{TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN)}/sendMessage"
    # Telegram limits messages to 4096 chars
    for i in range(0, len(text), 4000):
        chunk = text[i : i + 4000]
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(url, json={"chat_id": chat_id, "text": chunk})


async def send_chat_action(chat_id: int, action: str = "typing") -> None:
    """Send a chat action (e.g. 'typing') so the user sees a status indicator."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    url = f"{TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN)}/sendChatAction"
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(url, json={"chat_id": chat_id, "action": action})


async def _get_telegram_agent(db: AsyncSession) -> Agent | None:
    """Find the first active agent with 'telegram' in its channels."""
    result = await db.execute(select(Agent).where(Agent.is_active == True))
    agents = result.scalars().all()
    for agent in agents:
        channels = agent.channels or []
        if "telegram" in channels:
            return agent
    return None


async def _get_telegram_workflow(db: AsyncSession) -> Workflow | None:
    """Find the first active workflow with 'telegram' in its channels."""
    result = await db.execute(select(Workflow).where(Workflow.is_active == True))
    workflows = result.scalars().all()
    for wf in workflows:
        channels = wf.channels or []
        if "telegram" in channels:
            return wf
    return None


@router.post("/webhook")
async def telegram_webhook(request: Request) -> dict[str, bool]:
    """
    Receive updates from Telegram.
    Returns immediately and processes the message in a background task
    to avoid Telegram webhook retry duplicates.
    """
    try:
        data = await request.json()
    except Exception:
        return {"ok": True}

    # Extract message
    message = data.get("message")
    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    msg_id = message.get("message_id")

    if not text or not chat_id:
        return {"ok": True}

    # Deduplicate: skip if we already processed this Telegram message
    if msg_id and msg_id in _processed_messages:
        logger.info("Skipping duplicate Telegram message %s", msg_id)
        return {"ok": True}
    if msg_id:
        _processed_messages.add(msg_id)
        # Evict old entries to prevent memory leak
        if len(_processed_messages) > _processed_messages_max:
            _processed_messages.clear()

    sender = message.get("from", {})
    sender_name = sender.get("first_name", "User")

    # Handle /start command inline (fast)
    if text.startswith("/start"):
        await send_telegram_message(
            chat_id, "Hello! I'm an AI agent. Send me any message to chat."
        )
        return {"ok": True}

    # Process everything else in background so we return 200 fast
    asyncio.create_task(_handle_message(chat_id, text, sender_name, msg_id))

    return {"ok": True}


async def _handle_message(
    chat_id: int, text: str, sender_name: str, msg_id: int | None
) -> None:
    """Background handler — runs agent or workflow and sends result to Telegram."""
    try:
        async with async_session() as db:
            # Find workflow or agent assigned to Telegram (workflow takes priority)
            workflow = await _get_telegram_workflow(db)
            agent = await _get_telegram_agent(db)

            if not workflow and not agent:
                await send_telegram_message(
                    chat_id,
                    "No agent or workflow is assigned to Telegram. Please configure one in the web UI.",
                )
                return

            # Send "typing..." indicator so user knows we're working
            await send_chat_action(chat_id, "typing")

            if workflow:
                response_text = await _run_workflow(
                    db, workflow, text, sender_name, chat_id
                )
            else:
                response_text = await _run_single_agent(
                    db, agent, text, sender_name, msg_id, chat_id
                )

            # Send response back to Telegram
            await send_telegram_message(chat_id, response_text)
    except Exception as e:
        logger.error("Background telegram handler failed: %s", e, exc_info=True)
        await send_telegram_message(
            chat_id, "Sorry, something went wrong processing your message."
        )


async def _run_workflow(
    db: AsyncSession, workflow: Workflow, text: str, sender_name: str, chat_id: int
) -> str:
    """Execute a workflow and return the response text."""
    execution = WorkflowExecution(
        workflow_id=workflow.id,
        status="running",
        input_data={"message": text, "sender": sender_name, "chat_id": chat_id},
        started_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    try:
        result = await execute_workflow(
            workflow_id=workflow.id,
            graph=workflow.graph,
            input_data={"message": text},
            execution_id=execution.id,
            db=db,
        )
        execution.status = result["status"]
        execution.output_data = result["output"]
        execution.completed_at = datetime.now(timezone.utc)
        response_text = result["output"].get(
            "result", "Workflow completed with no output."
        )
    except Exception as e:
        logger.error("Telegram workflow execution failed: %s", e)
        execution.status = "failed"
        execution.output_data = {"error": str(e)}
        execution.completed_at = datetime.now(timezone.utc)
        response_text = f"Workflow failed: {str(e)}"

    await db.commit()
    return response_text


async def _run_single_agent(
    db: AsyncSession,
    agent: Agent,
    text: str,
    sender_name: str,
    msg_id: int | None,
    chat_id: int,
) -> str:
    """Execute a single agent and return the response text."""
    # Save incoming message
    user_msg = Message(
        agent_id=agent.id,
        role="user",
        content=text,
        channel="telegram",
        meta_info={
            "chat_id": chat_id,
            "sender": sender_name,
            "telegram_msg_id": msg_id,
        },
    )
    db.add(user_msg)
    await db.commit()

    # Get recent context
    result = await db.execute(
        select(Message)
        .where(Message.agent_id == agent.id)
        .order_by(Message.created_at.desc())
        .limit(20)
    )
    recent_db = list(reversed(result.scalars().all()))
    recent_messages = [
        {"id": m.id, "role": m.role, "content": m.content} for m in recent_db
    ]

    # Run agent
    agent_result = await run_agent(
        agent_id=agent.id,
        user_message=text,
        system_prompt=agent.system_prompt,
        model=agent.model,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        tool_names=agent.tools or [],
        memory_enabled=agent.memory_enabled,
        recent_messages=recent_messages,
    )

    response_text = agent_result["response"]

    # Save agent response
    assistant_msg = Message(
        agent_id=agent.id,
        role="assistant",
        content=response_text,
        channel="telegram",
        tokens_used=agent_result["tokens_used"],
        meta_info={
            "chat_id": chat_id,
            "tool_calls": agent_result["tool_calls"],
        },
    )
    db.add(assistant_msg)
    await db.commit()

    return response_text


@router.post("/setup-webhook")
async def setup_webhook():
    """Register the webhook URL with Telegram."""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN not configured")
    if not settings.TELEGRAM_WEBHOOK_URL:
        raise HTTPException(
            status_code=400, detail="TELEGRAM_WEBHOOK_URL not configured"
        )

    url = f"{TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN)}/setWebhook"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json={"url": settings.TELEGRAM_WEBHOOK_URL})
        result = resp.json()

    if result.get("ok"):
        return {"status": "webhook registered", "url": settings.TELEGRAM_WEBHOOK_URL}
    else:
        raise HTTPException(
            status_code=400, detail=f"Telegram error: {result.get('description')}"
        )


@router.get("/webhook-info")
async def webhook_info():
    """Get current webhook status from Telegram."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return {"status": "not configured", "detail": "TELEGRAM_BOT_TOKEN not set"}

    url = f"{TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN)}/getWebhookInfo"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        return resp.json()
