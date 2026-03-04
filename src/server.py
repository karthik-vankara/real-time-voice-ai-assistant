"""FastAPI WebSocket entry point (FR-001, FR-008, FR-019, Assumptions).

Accepts WSS WebSocket connections, enforces TLS, and delegates to the
pipeline orchestrator per session.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware

from src.config import config
from src.models.events import ErrorEvent, ErrorPayload, PipelineStage
from src.telemetry.logger import logger

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Voice assistant server starting", pipeline_stage="server")
    yield
    logger.info("Voice assistant server shutting down", pipeline_stage="server")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title="Real-Time Voice Assistant",
        version="0.1.0",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register telemetry dashboard router (T033)
    from src.telemetry.dashboard import router as telemetry_router
    app.include_router(telemetry_router)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # WebSocket endpoint  (detailed handler wired in Phase 3 / T016)
    # ------------------------------------------------------------------
    @app.websocket(config.server.ws_path)
    async def websocket_endpoint(ws: WebSocket) -> None:
        # TLS enforcement — reject plain WS (Assumptions, Security)
        if config.server.require_tls and ws.url.scheme not in ("wss", "https"):
            # During local dev / testing, require_tls may be False
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            logger.warning(
                "Rejected non-TLS WebSocket connection",
                pipeline_stage="server",
            )
            return

        await ws.accept()
        logger.info("WebSocket connection accepted", pipeline_stage="server")

        # Import here to avoid circular imports (orchestrator depends on server module)
        from src.pipeline.orchestrator import handle_session

        try:
            await handle_session(ws)
        except WebSocketDisconnect:
            logger.info("Client disconnected", pipeline_stage="server")
        except Exception as exc:
            logger.error(
                f"Unhandled error in session: {exc}",
                pipeline_stage="server",
            )
            try:
                error_event = ErrorEvent(
                    source_stage=PipelineStage.ORCHESTRATOR,
                    payload=ErrorPayload(
                        code="INTERNAL_ERROR",
                        message="An unexpected error occurred",
                    ),
                )
                await ws.send_json(error_event.model_dump(mode="json"))
            except Exception:
                pass  # connection may already be closed

    # ------------------------------------------------------------------
    # Replay endpoint (FR-015, T037)
    # ------------------------------------------------------------------
    @app.post("/replay")
    async def replay_session(
        file_path: str,
        delay_multiplier: float = 1.0,
    ) -> dict:
        """Replay a recorded session file through the pipeline."""
        from pathlib import Path

        from src.pipeline.replay import RecordedSession, ReplayEngine

        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        recorded = RecordedSession.from_json(path.read_text(encoding="utf-8"))
        engine = ReplayEngine(recorded, delay_multiplier=delay_multiplier)
        events = await engine.replay()
        return {
            "session_id": recorded.session_id,
            "events_produced": len(events),
            "events": events,
        }

    return app


app = create_app()
