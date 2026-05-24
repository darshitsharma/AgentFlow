"""SQLAlchemy ORM models for agents, workflows, messages, and logs."""

import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, JSON, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class Agent(Base):
    """AI agent with configurable model, tools, and memory."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="llama3.1:8b"
    )
    tools: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    channels: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    temperature: Mapped[float] = mapped_column(default=0.7)
    guardrails: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    skills: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    interaction_rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class Workflow(Base):
    """Multi-agent workflow defined as a directed graph."""

    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    graph: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    channels: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    executions: Mapped[list["WorkflowExecution"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )


class WorkflowExecution(Base):
    """Tracks a single run of a workflow with input/output data."""

    __tablename__ = "workflow_executions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, running, completed, failed
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workflow: Mapped["Workflow"] = relationship(back_populates="executions")


class Message(Base):
    """Chat message exchanged between a user and an agent."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    role: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # user, assistant, system, agent
    content: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(
        String(50), default="web"
    )  # web, telegram, inter-agent
    meta_info: Mapped[dict] = mapped_column(JSON, default=dict)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agent: Mapped["Agent"] = relationship(back_populates="messages")


class AgentLog(Base):
    """Audit log entry for agent actions and workflow events."""

    __tablename__ = "agent_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    workflow_execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    level: Mapped[str] = mapped_column(String(20), default="info")
    event: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
