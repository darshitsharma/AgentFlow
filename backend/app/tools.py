"""
Tool registry — real, executable tools that agents can use.
Each tool is a plain function wrapped with @tool for LangChain compatibility.
"""

import json
import math
import subprocess
import tempfile
import os
from datetime import datetime, timezone

from langchain_core.tools import tool


@tool
def web_search(query: str) -> str:
    """Search the web using DuckDuckGo and return top results."""
    try:
        from ddgs import DDGS

        results = DDGS().text(query, max_results=5)
        if not results:
            return "No results found."
        output = []
        for r in results:
            output.append(f"**{r['title']}**\n{r['body']}\nURL: {r['href']}")
        return "\n\n".join(output)
    except Exception as e:
        return f"Search error: {str(e)}"


# TODO: Replace this with a called external API for calculations if possible, to avoid security risks of eval. If eval must be used, consider using a restricted Python environment or a math expression parser library instead.
@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression. Supports basic math and functions like sqrt, sin, cos, log."""
    allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
    allowed_names.update({"abs": abs, "round": round, "min": min, "max": max})
    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)  # noqa: S307
        return str(result)
    except Exception as e:
        return f"Calculation error: {str(e)}"


# TODO: Use a more secure sandboxing approach for code execution, such as a containerized environment or a restricted Python interpreter, to prevent potential security risks.
@tool
def code_executor(code: str) -> str:
    """Execute a Python code snippet in an isolated subprocess and return stdout/stderr.
    The code runs in a temporary file with a 10-second timeout."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        tmp_path = f.name
    try:
        result = subprocess.run(
            ["python3", tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Code execution timed out (10s limit)"
    except Exception as e:
        return f"Execution error: {str(e)}"
    finally:
        os.unlink(tmp_path)


# TODO: Add extension to file extensions this file reader can access, and add a file size limit. Also consider adding a file writing tool with similar safeguards.
@tool
def file_reader(filepath: str) -> str:
    """Read the contents of a file. Only allows reading from the current working directory."""
    safe_path = os.path.abspath(filepath)
    cwd = os.path.abspath(".")
    if not safe_path.startswith(cwd):
        return "Error: Cannot read files outside the working directory."
    try:
        with open(safe_path, "r") as f:
            content = f.read(10000)  # limit to 10KB
        return content
    except Exception as e:
        return f"File read error: {str(e)}"


@tool
def weather(location: str) -> str:
    """Get current weather for a location using wttr.in (free, no API key)."""
    import httpx

    try:
        resp = httpx.get(f"https://wttr.in/{location}?format=j1", timeout=10)
        data = resp.json()
        current = data["current_condition"][0]
        return (
            f"Weather in {location}: {current['weatherDesc'][0]['value']}, "
            f"Temperature: {current['temp_C']}°C / {current['temp_F']}°F, "
            f"Humidity: {current['humidity']}%, "
            f"Wind: {current['windspeedKmph']} km/h {current['winddir16Point']}"
        )
    except Exception as e:
        return f"Weather error: {str(e)}"


# TODO: Fix the summarizer to use a real LLM-based approach instead of a naive extractive method
@tool
def summarizer(text: str) -> str:
    """Summarize a long text into key bullet points. Returns a condensed version."""
    sentences = text.replace("\n", " ").split(". ")
    if len(sentences) <= 3:
        return text
    # Simple extractive summary: take first, middle, and last sentences
    picks = [
        sentences[0],
        sentences[len(sentences) // 2],
        sentences[-1],
    ]
    return "Summary:\n" + "\n".join(f"• {s.strip()}" for s in picks if s.strip())


@tool
def current_datetime() -> str:
    """Get the current date and time in UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


@tool
def remember_fact(fact: str) -> str:
    """Save an important fact to long-term memory. Use this when the user asks you to remember something."""
    # This is a marker — the runtime intercepts this and stores via memory service
    return f"__REMEMBER__:{fact}"


# Tool lookup by name
TOOL_REGISTRY: dict = {
    "web_search": web_search,
    "calculator": calculator,
    "code_executor": code_executor,
    "file_reader": file_reader,
    "weather": weather,
    "summarizer": summarizer,
    "current_datetime": current_datetime,
    "remember_fact": remember_fact,
}


def get_tools(tool_names: list[str]):
    """Return tool objects for the given names."""
    tools = []
    for name in tool_names:
        if name in TOOL_REGISTRY:
            tools.append(TOOL_REGISTRY[name])
    return tools
