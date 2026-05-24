"""Pydantic request/response schemas for the REST API."""

from datetime import datetime
from pydantic import BaseModel, Field

# --- Agent Schemas ---


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=255)
    system_prompt: str = ""
    model: str = "llama3.1:8b"
    tools: list[str] = []
    channels: list[str] = []
    schedule: str | None = None
    memory_enabled: bool = True
    max_tokens: int = 4096
    temperature: float = 0.7
    guardrails: dict = {}
    skills: list[str] = []
    interaction_rules: dict = {}


class AgentUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    channels: list[str] | None = None
    schedule: str | None = None
    memory_enabled: bool | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    guardrails: dict | None = None
    skills: list[str] | None = None
    interaction_rules: dict | None = None
    is_active: bool | None = None


class AgentResponse(BaseModel):
    id: str
    name: str
    role: str
    system_prompt: str
    model: str
    tools: list[str]
    channels: list[str]
    schedule: str | None
    memory_enabled: bool
    max_tokens: int
    temperature: float
    guardrails: dict
    skills: list[str]
    interaction_rules: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Workflow Schemas ---


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    graph: dict = {}
    channels: list[str] = []
    is_template: bool = False


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph: dict | None = None
    channels: list[str] | None = None
    is_active: bool | None = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str
    graph: dict
    channels: list[str]
    is_template: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Message Schemas ---


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    channel: str = "web"


class MessageResponse(BaseModel):
    id: str
    agent_id: str
    role: str
    content: str
    channel: str
    meta_info: dict
    tokens_used: int
    cost: float
    created_at: datetime

    class Config:
        from_attributes = True


# --- Workflow Execution Schemas ---


class WorkflowExecutionCreate(BaseModel):
    input_data: dict = {}


class WorkflowExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    input_data: dict
    output_data: dict
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Log Schemas ---


class AgentLogResponse(BaseModel):
    id: str
    agent_id: str
    workflow_execution_id: str | None
    level: str
    event: str
    details: dict
    created_at: datetime

    class Config:
        from_attributes = True
