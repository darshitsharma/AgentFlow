from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import agents, workflows, messages, logs
from app.routers.chat import router as chat_router
from app.routers.memory_routes import router as memory_router
from app.routers.telegram import router as telegram_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="AI Agent Orchestration Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router, prefix="/api")
app.include_router(workflows.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(telegram_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
