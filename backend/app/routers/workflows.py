"""Workflow CRUD and execution router — manage and run multi-agent workflows."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Workflow, WorkflowExecution
from app.schemas import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowExecutionCreate,
    WorkflowExecutionResponse,
)
from app.workflow_engine import execute_workflow

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/", response_model=list[WorkflowResponse])
async def list_workflows(db: AsyncSession = Depends(get_db)) -> list[Workflow]:
    """Return all workflows ordered by creation date (newest first)."""
    result = await db.execute(select(Workflow).order_by(Workflow.created_at.desc()))
    return result.scalars().all()


@router.get("/templates", response_model=list[WorkflowResponse])
async def list_templates(db: AsyncSession = Depends(get_db)) -> list[Workflow]:
    """Return only workflow templates."""
    result = await db.execute(
        select(Workflow)
        .where(Workflow.is_template == True)
        .order_by(Workflow.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str, db: AsyncSession = Depends(get_db)
) -> Workflow:
    """Return a single workflow by ID, or 404 if not found."""
    workflow = await db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.post("/", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    data: WorkflowCreate, db: AsyncSession = Depends(get_db)
) -> Workflow:
    """Create a new workflow with the given graph definition."""
    workflow = Workflow(**data.model_dump())
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str, data: WorkflowUpdate, db: AsyncSession = Depends(get_db)
) -> Workflow:
    """Update an existing workflow. Only provided fields are changed."""
    workflow = await db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(workflow, key, value)
    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a workflow and all its execution history."""
    workflow = await db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.delete(workflow)
    await db.commit()


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def run_workflow(
    workflow_id: str,
    data: WorkflowExecutionCreate,
    db: AsyncSession = Depends(get_db),
) -> WorkflowExecution:
    """Execute a workflow — runs all agents in the graph sequentially."""
    workflow = await db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    execution = WorkflowExecution(
        workflow_id=workflow_id,
        status="running",
        input_data=data.input_data,
        started_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    try:
        result = await execute_workflow(
            workflow_id=workflow_id,
            graph=workflow.graph,
            input_data=data.input_data,
            execution_id=execution.id,
            db=db,
        )
        execution.status = result["status"]
        execution.output_data = result["output"]
        execution.completed_at = datetime.now(timezone.utc)
    except Exception as e:
        execution.status = "failed"
        execution.output_data = {"error": str(e)}
        execution.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(execution)
    return execution


@router.get("/{workflow_id}/executions", response_model=list[WorkflowExecutionResponse])
async def list_executions(
    workflow_id: str, db: AsyncSession = Depends(get_db)
) -> list[WorkflowExecution]:
    """Return recent executions for a workflow."""
    result = await db.execute(
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id)
        .order_by(WorkflowExecution.created_at.desc())
        .limit(20)
    )
    return result.scalars().all()
