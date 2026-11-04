"""FastAPI app: a JSON API plus a one-page UI.

Run locally:  uvicorn app.main:app --reload   then open http://127.0.0.1:8000
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.llm import LLMError
from app.rag import RAGPipeline

STATIC_DIR = Path(__file__).parent / "static"


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, examples=["How do I get a refund?"])


class AskResponse(BaseModel):
    question: str
    answer: str
    refused: bool
    blocked: bool
    block_reason: str | None
    sources: list[str]
    citations: list[str]
    model: str
    latency_ms: float
    trace_id: str


def create_app(pipeline: RAGPipeline | None = None) -> FastAPI:
    """App factory. Tests pass in their own pipeline; production builds one from env."""
    api = FastAPI(title="NimbusNotes Help Assistant", version="1.0.0")
    api.state.pipeline = pipeline or RAGPipeline.from_settings()

    @api.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @api.get("/health")
    def health() -> dict:
        return {"status": "ok", "model": api.state.pipeline.llm.name}

    @api.post("/ask", response_model=AskResponse)
    def ask(req: AskRequest) -> dict:
        try:
            return api.state.pipeline.ask(req.question).to_dict()
        except LLMError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return api


app = create_app()
