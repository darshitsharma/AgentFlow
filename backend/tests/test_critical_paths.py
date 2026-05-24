"""
Tests for critical paths: agent CRUD, workflow execution, message delivery.
Uses SQLite in-memory for fast testing.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# --- Test DB Setup ---

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Agent CRUD Tests ---


class TestAgentCRUD:
    async def test_create_agent(self, client: AsyncClient):
        resp = await client.post(
            "/api/agents/",
            json={
                "name": "Test Agent",
                "role": "tester",
                "system_prompt": "You are a test agent.",
                "model": "llama3.1:8b",
                "tools": ["calculator"],
                "channels": ["web"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Agent"
        assert data["role"] == "tester"
        assert data["tools"] == ["calculator"]
        assert data["is_active"] is True
        assert "id" in data

    async def test_list_agents(self, client: AsyncClient):
        # Create two agents
        await client.post("/api/agents/", json={"name": "Agent 1", "role": "r1"})
        await client.post("/api/agents/", json={"name": "Agent 2", "role": "r2"})

        resp = await client.get("/api/agents/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_get_agent(self, client: AsyncClient):
        create = await client.post(
            "/api/agents/", json={"name": "Get Me", "role": "getter"}
        )
        agent_id = create.json()["id"]

        resp = await client.get(f"/api/agents/{agent_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    async def test_get_agent_not_found(self, client: AsyncClient):
        resp = await client.get("/api/agents/nonexistent-id")
        assert resp.status_code == 404

    async def test_update_agent(self, client: AsyncClient):
        create = await client.post(
            "/api/agents/", json={"name": "Old Name", "role": "updater"}
        )
        agent_id = create.json()["id"]

        resp = await client.put(
            f"/api/agents/{agent_id}", json={"name": "New Name", "temperature": 0.5}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["temperature"] == 0.5

    async def test_delete_agent(self, client: AsyncClient):
        create = await client.post(
            "/api/agents/", json={"name": "Delete Me", "role": "deleter"}
        )
        agent_id = create.json()["id"]

        resp = await client.delete(f"/api/agents/{agent_id}")
        assert resp.status_code == 204

        resp2 = await client.get(f"/api/agents/{agent_id}")
        assert resp2.status_code == 404

    async def test_create_agent_validation(self, client: AsyncClient):
        resp = await client.post("/api/agents/", json={"name": "", "role": "bad"})
        assert resp.status_code == 422


# --- Workflow Tests ---


class TestWorkflows:
    async def test_create_workflow(self, client: AsyncClient):
        resp = await client.post(
            "/api/workflows/",
            json={
                "name": "Test Flow",
                "description": "A test workflow",
                "graph": {
                    "nodes": [{"id": "n1", "agent_id": "a1", "label": "Node 1"}],
                    "edges": [],
                },
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Flow"
        assert "nodes" in data["graph"]

    async def test_list_workflows(self, client: AsyncClient):
        await client.post("/api/workflows/", json={"name": "WF1", "graph": {}})
        await client.post("/api/workflows/", json={"name": "WF2", "graph": {}})

        resp = await client.get("/api/workflows/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_workflow_templates(self, client: AsyncClient):
        await client.post(
            "/api/workflows/",
            json={"name": "Template", "graph": {}, "is_template": True},
        )
        await client.post(
            "/api/workflows/",
            json={"name": "Regular", "graph": {}, "is_template": False},
        )

        resp = await client.get("/api/workflows/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Template"

    async def test_delete_workflow(self, client: AsyncClient):
        create = await client.post(
            "/api/workflows/", json={"name": "Del WF", "graph": {}}
        )
        wf_id = create.json()["id"]

        resp = await client.delete(f"/api/workflows/{wf_id}")
        assert resp.status_code == 204


# --- Message Delivery Tests ---


class TestMessages:
    async def test_chat_sends_and_receives(self, client: AsyncClient):
        # Create agent first
        create = await client.post(
            "/api/agents/",
            json={
                "name": "Chat Agent",
                "role": "chatter",
                "system_prompt": "You are helpful.",
                "tools": [],
                "channels": ["web"],
            },
        )
        agent_id = create.json()["id"]

        # Mock the runtime to avoid needing Ollama
        with patch("app.routers.chat.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "response": "Hello! How can I help?",
                "tokens_used": 42,
                "tool_calls": [],
                "memories_stored": [],
            }

            resp = await client.post(
                f"/api/chat/{agent_id}",
                json={
                    "content": "Hi there",
                    "channel": "web",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["role"] == "assistant"
            assert data["content"] == "Hello! How can I help?"
            assert data["tokens_used"] == 42

    async def test_chat_agent_not_found(self, client: AsyncClient):
        resp = await client.post("/api/chat/nonexistent", json={"content": "hello"})
        assert resp.status_code == 404

    async def test_message_history(self, client: AsyncClient):
        create = await client.post(
            "/api/agents/", json={"name": "Hist Agent", "role": "hist"}
        )
        agent_id = create.json()["id"]

        with patch("app.routers.chat.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "response": "Response 1",
                "tokens_used": 10,
                "tool_calls": [],
                "memories_stored": [],
            }
            await client.post(f"/api/chat/{agent_id}", json={"content": "Message 1"})

            mock_run.return_value["response"] = "Response 2"
            await client.post(f"/api/chat/{agent_id}", json={"content": "Message 2"})

        resp = await client.get(f"/api/messages/agent/{agent_id}")
        assert resp.status_code == 200
        msgs = resp.json()
        # Should have 4 messages: 2 user + 2 assistant
        assert len(msgs) == 4


# --- Stats/Monitoring Tests ---


class TestMonitoring:
    async def test_stats_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/logs/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_agents" in data
        assert "total_messages" in data
        assert "total_tokens" in data
        assert "agent_stats" in data

    async def test_health_check(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
