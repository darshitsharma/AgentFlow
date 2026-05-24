"""
Workflow Execution Engine.

Executes workflow graphs: sequences of agents with conditions and feedback loops.
Each node is an agent; edges define message flow between agents.

Graph format (stored in Workflow.graph):
{
  "nodes": [
    {"id": "node_1", "agent_id": "...", "label": "Researcher", "position": {"x": 0, "y": 0}},
    ...
  ],
  "edges": [
    {"id": "edge_1", "source": "node_1", "target": "node_2", "condition": null},
    ...
  ]
}

Conditions on edges (optional):
- null / missing → always follow
- {"type": "contains", "value": "APPROVE"} → follow if output contains value
- {"type": "not_contains", "value": "REJECT"} → follow if output does NOT contain value
- {"type": "max_iterations", "value": 3} → follow only if loop count < value
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Agent, Message, WorkflowExecution, AgentLog
from app.runtime import run_agent

logger = logging.getLogger(__name__)

MAX_TOTAL_STEPS = 50  # safety limit


async def execute_workflow(
    workflow_id: str,
    graph: dict,
    input_data: dict,
    execution_id: str,
    db: AsyncSession,
) -> dict:
    """
    Execute a workflow graph end-to-end.

    Returns: {"status": "completed"|"failed", "output": {...}, "steps": [...]}
    """
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    if not nodes:
        return {
            "status": "failed",
            "output": {"error": "No nodes in workflow"},
            "steps": [],
        }

    # Build adjacency: source_id → list of (target_id, condition)
    adjacency: dict[str, list[tuple[str, dict | None]]] = {}
    for edge in edges:
        src = edge["source"]
        tgt = edge["target"]
        cond = edge.get("condition")
        adjacency.setdefault(src, []).append((tgt, cond))

    # Find start nodes (no incoming edges)
    targets = {e["target"] for e in edges}
    start_nodes = [n for n in nodes if n["id"] not in targets]
    if not start_nodes:
        start_nodes = [nodes[0]]

    node_map = {n["id"]: n for n in nodes}
    steps = []
    iteration_counts: dict[str, int] = {}  # edge_id → count for loop tracking
    step_count = 0

    # Build reverse adjacency for fan-in detection
    incoming: dict[str, list[str]] = {}  # target_id → [source_ids]
    for edge in edges:
        incoming.setdefault(edge["target"], []).append(edge["source"])

    # Track which nodes have been queued with their inputs (for fan-in merging)
    pending_inputs: dict[str, list[str]] = {}  # node_id → [input_texts]

    # BFS-style execution
    queue: list[tuple[str, str]] = []  # (node_id, input_text)
    initial_input = input_data.get(
        "message", input_data.get("input", "Start the workflow.")
    )

    for sn in start_nodes:
        queue.append((sn["id"], initial_input))

    node_outputs: dict[str, str] = {}

    requeue_count = 0
    max_requeues = MAX_TOTAL_STEPS * 3  # safety limit for re-queued fan-in waits

    while queue and step_count < MAX_TOTAL_STEPS and requeue_count < max_requeues:
        node_id, input_text = queue.pop(0)
        node = node_map.get(node_id)
        if not node:
            continue

        # Skip nodes that already produced output (prevents duplicate fan-in runs)
        if node_id in node_outputs:
            continue

        # Fan-in: if this node has multiple incoming sources, collect all inputs
        sources = incoming.get(node_id, [])
        if len(sources) > 1:
            pending_inputs.setdefault(node_id, []).append(input_text)
            completed_sources = [s for s in sources if s in node_outputs]
            # Not all sources have finished yet — re-queue and wait
            if len(completed_sources) < len(sources):
                queue.append((node_id, input_text))
                requeue_count += 1
                continue
            # All sources done but we haven't collected all queue entries yet — skip this one
            if len(pending_inputs[node_id]) < len(sources):
                continue
            # All sources done and all inputs collected — merge
            merged_parts = []
            for src_id in sources:
                src_node = node_map.get(src_id)
                src_label = src_node.get("label", src_id) if src_node else src_id
                if src_id in node_outputs:
                    merged_parts.append(
                        f"--- Output from {src_label} ---\n{node_outputs[src_id]}"
                    )
            input_text = "\n\n".join(merged_parts) if merged_parts else input_text

        agent_id = node.get("agent_id")
        if not agent_id:
            continue

        step_count += 1

        # Load agent from DB
        agent = await db.get(Agent, agent_id)
        if not agent:
            log = AgentLog(
                agent_id=agent_id,
                workflow_execution_id=execution_id,
                level="error",
                event="agent_not_found",
                details={"node_id": node_id},
            )
            db.add(log)
            steps.append(
                {
                    "node_id": node_id,
                    "agent_id": agent_id,
                    "status": "error",
                    "error": "Agent not found",
                }
            )
            continue

        # Log start
        log_start = AgentLog(
            agent_id=agent_id,
            workflow_execution_id=execution_id,
            level="info",
            event="node_started",
            details={"node_id": node_id, "input_preview": input_text[:200]},
        )
        db.add(log_start)

        # Fetch recent messages for this agent
        result = await db.execute(
            select(Message)
            .where(Message.agent_id == agent_id)
            .order_by(Message.created_at.desc())
            .limit(10)
        )
        recent_db = list(reversed(result.scalars().all()))
        recent_messages = [
            {"id": m.id, "role": m.role, "content": m.content} for m in recent_db
        ]

        # Execute agent
        try:
            agent_result = await run_agent(
                agent_id=agent_id,
                user_message=input_text,
                system_prompt=agent.system_prompt,
                model=agent.model,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
                tool_names=agent.tools or [],
                memory_enabled=agent.memory_enabled,
                recent_messages=recent_messages,
            )
            output_text = agent_result["response"]
            tokens = agent_result["tokens_used"]
        except Exception as e:
            logger.error("Workflow node %s failed: %s", node_id, e)
            output_text = f"Error: {str(e)}"
            tokens = 0

        node_outputs[node_id] = output_text

        # Save messages
        user_msg = Message(
            agent_id=agent_id,
            role="user",
            content=input_text,
            channel="inter-agent",
            tokens_used=0,
        )
        assistant_msg = Message(
            agent_id=agent_id,
            role="assistant",
            content=output_text,
            channel="inter-agent",
            tokens_used=tokens,
        )
        db.add(user_msg)
        db.add(assistant_msg)

        # Log completion
        log_done = AgentLog(
            agent_id=agent_id,
            workflow_execution_id=execution_id,
            level="info",
            event="node_completed",
            details={
                "node_id": node_id,
                "output_preview": output_text[:200],
                "tokens": tokens,
            },
        )
        db.add(log_done)

        steps.append(
            {
                "node_id": node_id,
                "agent_id": agent_id,
                "agent_name": agent.name,
                "input_preview": input_text[:200],
                "output_preview": output_text[:500],
                "tokens_used": tokens,
                "status": "completed",
            }
        )

        # Determine next nodes based on edge conditions
        for target_id, condition in adjacency.get(node_id, []):
            edge_key = f"{node_id}->{target_id}"

            if condition is None:
                queue.append((target_id, output_text))
                continue

            cond_type = condition.get("type", "")
            cond_value = condition.get("value", "")

            if cond_type == "contains":
                if str(cond_value).lower() in output_text.lower():
                    queue.append((target_id, output_text))
            elif cond_type == "not_contains":
                if str(cond_value).lower() not in output_text.lower():
                    queue.append((target_id, output_text))
            elif cond_type == "max_iterations":
                count = iteration_counts.get(edge_key, 0)
                if count < int(cond_value):
                    iteration_counts[edge_key] = count + 1
                    queue.append((target_id, output_text))
            else:
                # Unknown condition type, follow anyway
                queue.append((target_id, output_text))

        await db.commit()

    # Determine final output — prefer terminal nodes (no outgoing edges)
    source_ids = {e["source"] for e in edges}
    terminal_nodes = [
        n["id"] for n in nodes if n["id"] not in source_ids and n["id"] in node_outputs
    ]
    if terminal_nodes:
        if len(terminal_nodes) == 1:
            final_output = node_outputs[terminal_nodes[0]]
        else:
            parts = []
            for tid in terminal_nodes:
                label = node_map[tid].get("label", tid)
                parts.append(f"--- {label} ---\n{node_outputs[tid]}")
            final_output = "\n\n".join(parts)
    else:
        final_output = node_outputs.get(steps[-1]["node_id"], "") if steps else ""

    return {
        "status": "completed" if steps else "failed",
        "output": {"result": final_output, "total_steps": len(steps)},
        "steps": steps,
    }
