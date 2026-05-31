"""
Agent Runtime — LangGraph-based execution engine.

Each agent runs as a LangGraph StateGraph:
  user input → (memory recall) → LLM → (tool calls?) → response → (memory store)

Supports:
- Ollama LLM (local, free)
- Tool calling via LangGraph ToolNode
- Semantic short-term + long-term memory injection
- Inter-agent messaging via Redis pub/sub
- Token tracking
"""

import json
import logging
import re
import time
from typing import Annotated, TypedDict, Sequence

import httpx
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    BaseMessage,
)

from app.config import settings
from app.memory import (
    store_short_term,
    store_long_term,
    build_memory_context,
)
from app.tools import get_tools, TOOL_REGISTRY

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    messages: list[BaseMessage]
    agent_id: str
    tokens_used: int


async def call_ollama(
    messages: list[dict],
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    tools: list | None = None,
) -> dict:
    """Call Ollama's chat API."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


def _format_tools_for_ollama(tool_objects: list) -> list[dict]:
    """Convert LangChain tools to Ollama tool format."""
    ollama_tools = []
    for t in tool_objects:
        schema = t.args_schema.schema() if t.args_schema else {}
        properties = {}
        required = []
        for field_name, field_info in schema.get("properties", {}).items():
            properties[field_name] = {
                "type": field_info.get("type", "string"),
                "description": field_info.get(
                    "description", field_info.get("title", "")
                ),
            }
            if field_name in schema.get("required", []):
                required.append(field_name)

        ollama_tools.append(
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return ollama_tools


def _messages_to_dicts(messages: list[BaseMessage]) -> list[dict]:
    """Convert LangChain messages to Ollama-compatible dicts."""
    result = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, ToolMessage):
            result.append({"role": "tool", "content": msg.content})
    return result


async def run_agent(
    agent_id: str,
    user_message: str,
    system_prompt: str,
    model: str = "llama3.1:8b",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    tool_names: list[str] | None = None,
    memory_enabled: bool = True,
    recent_messages: list[dict] | None = None,
) -> dict:
    """
    Execute one turn of agent reasoning.

    Returns: {
        "response": str,
        "tokens_used": int,
        "tool_calls": list[dict],
        "memories_stored": list[str],
    }
    """
    tool_names = tool_names or []
    recent_messages = recent_messages or []
    tool_objects = get_tools(tool_names)

    # --- Build system prompt with memory context and tool instructions ---
    full_system = system_prompt

    # Inject available tool names so the model doesn't hallucinate tools
    # TODO: Move all prompts in entire codebase to a central location and make them more robust and reusable, e.g. with few-shot examples and better instructions around tool calling format.
    if tool_objects:
        tool_list = ", ".join(t.name for t in tool_objects)
        full_system += (
            f"\n\nYou have access to ONLY these tools: [{tool_list}]. "
            "Use them by calling them through the tool-calling mechanism — do NOT "
            "write tool calls as JSON text in your response. If a tool you want "
            "doesn't exist in that list, just say you don't have that capability."
        )

    if memory_enabled:
        memory_ctx = build_memory_context(agent_id, user_message, recent_messages)
        if memory_ctx:
            full_system = f"{full_system}\n\n{memory_ctx}"

    # --- Assemble messages ---
    messages: list[BaseMessage] = [SystemMessage(content=full_system)]

    # Add recent conversation history
    for msg in recent_messages[-20:]:  # last 20 messages as window
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=user_message))

    # --- Call LLM ---
    ollama_tools = _format_tools_for_ollama(tool_objects) if tool_objects else None
    msg_dicts = _messages_to_dicts(messages)

    total_tokens = 0
    tool_call_results = []
    memories_stored = []

    try:
        result = await call_ollama(
            msg_dicts, model, temperature, max_tokens, ollama_tools
        )
    except httpx.HTTPStatusError as e:
        logger.error("Ollama API error: %s", e)
        return {
            "response": "I'm having trouble connecting to the language model. Please ensure Ollama is running.",
            "tokens_used": 0,
            "tool_calls": [],
            "memories_stored": [],
        }
    except httpx.ConnectError:
        return {
            "response": "Cannot connect to Ollama. Please start it with: ollama serve",
            "tokens_used": 0,
            "tool_calls": [],
            "memories_stored": [],
        }

    total_tokens += result.get("eval_count", 0) + result.get("prompt_eval_count", 0)
    ai_message = result.get("message", {})
    response_text = ai_message.get("content", "")

    # --- Detect hallucinated tool calls in text ---
    tool_calls = ai_message.get("tool_calls", [])
    if not tool_calls and response_text and tool_objects:
        # Check if the model wrote a fake JSON tool call in its response
        fake_call = re.search(r'\{\s*"name"\s*:\s*"(\w+)"', response_text)
        if fake_call:
            fake_name = fake_call.group(1)
            # Map common hallucinated tool names to real ones
            name_map = {
                "google_search": "web_search",
                "search": "web_search",
                "search_web": "web_search",
            }
            real_name = name_map.get(fake_name, fake_name)
            if real_name in TOOL_REGISTRY and real_name in tool_names:
                try:
                    # Try to extract the full JSON blob (may span multiple lines)
                    args_json = {}
                    json_start = response_text.find('{"name"')
                    if json_start == -1:
                        json_start = response_text.find('{ "name"')
                    if json_start >= 0:
                        depth = 0
                        for i in range(json_start, len(response_text)):
                            if response_text[i] == "{":
                                depth += 1
                            elif response_text[i] == "}":
                                depth -= 1
                                if depth == 0:
                                    try:
                                        parsed = json.loads(
                                            response_text[json_start : i + 1]
                                        )
                                        args_json = parsed.get(
                                            "parameters", parsed.get("arguments", {})
                                        )
                                    except json.JSONDecodeError:
                                        pass
                                    break

                    # Fallback: extract known param patterns
                    if not args_json:
                        query_match = re.search(
                            r'"query"\s*:\s*"([^"]+)"', response_text
                        )
                        loc_match = re.search(
                            r'"location"\s*:\s*"([^"]+)"', response_text
                        )
                        if query_match:
                            args_json = {"query": query_match.group(1)}
                        elif loc_match:
                            args_json = {"location": loc_match.group(1)}

                    if args_json:
                        logger.info(
                            "Intercepted hallucinated tool call: %s -> %s with args %s",
                            fake_name,
                            real_name,
                            args_json,
                        )
                        # Handle array args: call tool once per item
                        all_results = []
                        first_key = next(iter(args_json), None)
                        if first_key and isinstance(args_json[first_key], list):
                            for item in args_json[first_key]:
                                single_args = {first_key: str(item)}
                                result_str = str(
                                    TOOL_REGISTRY[real_name].invoke(single_args)
                                )
                                all_results.append(result_str)
                                tool_call_results.append(
                                    {
                                        "tool": real_name,
                                        "args": single_args,
                                        "result": result_str[:2000],
                                    }
                                )
                            tool_result = "\n".join(all_results)
                        else:
                            tool_result = TOOL_REGISTRY[real_name].invoke(args_json)
                            tool_call_results.append(
                                {
                                    "tool": real_name,
                                    "args": args_json,
                                    "result": str(tool_result)[:2000],
                                }
                            )

                        # Re-call LLM with the real tool result
                        msg_dicts.append(
                            {"role": "assistant", "content": response_text}
                        )
                        msg_dicts.append({"role": "tool", "content": str(tool_result)})
                        try:
                            result = await call_ollama(
                                msg_dicts, model, temperature, max_tokens, ollama_tools
                            )
                            total_tokens += result.get("eval_count", 0) + result.get(
                                "prompt_eval_count", 0
                            )
                            ai_message = result.get("message", {})
                            response_text = ai_message.get("content", "")
                            tool_calls = ai_message.get("tool_calls", [])
                        except Exception as e:
                            logger.error(
                                "Ollama error after intercepted tool call: %s", e
                            )
                except Exception as e:
                    logger.warning("Failed to intercept hallucinated tool call: %s", e)

    max_tool_rounds = 5
    round_count = 0

    while tool_calls and round_count < max_tool_rounds:
        round_count += 1
        msg_dicts.append(
            {"role": "assistant", "content": response_text, "tool_calls": tool_calls}
        )

        for tc in tool_calls:
            func_name = tc.get("function", {}).get("name", "")
            func_args = tc.get("function", {}).get("arguments", {})

            if func_name in TOOL_REGISTRY:
                try:
                    tool_result = TOOL_REGISTRY[func_name].invoke(func_args)

                    # Intercept remember_fact tool
                    if isinstance(tool_result, str) and tool_result.startswith(
                        "__REMEMBER__:"
                    ):
                        fact = tool_result[len("__REMEMBER__:") :]
                        store_long_term(agent_id, fact, source="agent_tool")
                        memories_stored.append(fact)
                        tool_result = f"Remembered: {fact}"

                    tool_call_results.append(
                        {
                            "tool": func_name,
                            "args": func_args,
                            "result": str(tool_result)[:2000],
                        }
                    )
                except Exception as e:
                    tool_result = f"Tool error: {str(e)}"
                    tool_call_results.append(
                        {
                            "tool": func_name,
                            "args": func_args,
                            "result": tool_result,
                        }
                    )

                msg_dicts.append({"role": "tool", "content": str(tool_result)})

        # Call LLM again with tool results
        try:
            result = await call_ollama(
                msg_dicts, model, temperature, max_tokens, ollama_tools
            )
        except Exception as e:
            logger.error("Ollama error during tool round: %s", e)
            break

        total_tokens += result.get("eval_count", 0) + result.get("prompt_eval_count", 0)
        ai_message = result.get("message", {})
        response_text = ai_message.get("content", "")
        tool_calls = ai_message.get("tool_calls", [])

    # --- Store to memory ---
    if memory_enabled:
        store_short_term(agent_id, "user", user_message)
        store_short_term(agent_id, "assistant", response_text)

    return {
        "response": response_text,
        "tokens_used": total_tokens,
        "tool_calls": tool_call_results,
        "memories_stored": memories_stored,
    }
