"""Fallback strategy registry (FR-009, FR-010, FR-011, US3).

Maps each pipeline service to its degradation strategy when the circuit
breaker is open or a timeout occurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.fallback.bridge_audio import (
    BRIDGE_TEXT,
    BridgeAudioType,
    get_bridge_audio_b64,
)
from src.models.events import (
    PipelineStage,
    TTSAudioChunkEvent,
    TTSAudioChunkPayload,
    _new_correlation_id,
)
from src.telemetry.logger import logger


class FallbackAction(StrEnum):
    """What to do when a service is degraded."""

    BRIDGE_AUDIO = "bridge_audio"
    CACHED_CLIP = "cached_clip"
    RETRY_PROMPT = "retry_prompt"
    MODEL_SWITCH = "model_switch"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class FallbackStrategy:
    """Describes the fallback behaviour for a single service."""

    service: PipelineStage
    action: FallbackAction
    bridge_clip: BridgeAudioType | None = None
    description: str = ""


# ---------------------------------------------------------------------------
# Registry: one strategy per service
# ---------------------------------------------------------------------------

_REGISTRY: dict[PipelineStage, FallbackStrategy] = {
    PipelineStage.ASR: FallbackStrategy(
        service=PipelineStage.ASR,
        action=FallbackAction.RETRY_PROMPT,
        bridge_clip=BridgeAudioType.REPEAT,
        description="Play 'I didn't catch that, could you repeat?' prompt",
    ),
    PipelineStage.LLM: FallbackStrategy(
        service=PipelineStage.LLM,
        action=FallbackAction.BRIDGE_AUDIO,
        bridge_clip=BridgeAudioType.THINKING,
        description=(
            "Play 'Let me think about that...' bridge audio;"
            " on persistent failure switch model (FR-011)"
        ),
    ),
    PipelineStage.TTS: FallbackStrategy(
        service=PipelineStage.TTS,
        action=FallbackAction.CACHED_CLIP,
        bridge_clip=BridgeAudioType.ONE_MOMENT,
        description="Serve pre-generated fallback audio clip",
    ),
}


def get_strategy(service: PipelineStage) -> FallbackStrategy:
    """Return the fallback strategy for *service*."""
    return _REGISTRY.get(service, FallbackStrategy(service=service, action=FallbackAction.NONE))


def build_fallback_audio_event(
    service: PipelineStage,
    *,
    correlation_id: str | None = None,
) -> TTSAudioChunkEvent | None:
    """Build a TTS audio chunk event from the fallback strategy's bridge clip.

    Returns ``None`` if the strategy has no bridge audio.
    """
    strategy = get_strategy(service)
    if strategy.bridge_clip is None:
        return None

    cid = correlation_id or _new_correlation_id()
    audio_b64 = get_bridge_audio_b64(strategy.bridge_clip)

    logger.warning(
        f"Fallback activated for {service}: {strategy.description}",
        correlation_id=cid,
        pipeline_stage="fallback",
    )

    return TTSAudioChunkEvent(
        correlation_id=cid,
        payload=TTSAudioChunkPayload(
            audio_b64=audio_b64,
            chunk_index=0,
            is_last=True,
        ),
    )


def get_fallback_text(service: PipelineStage) -> str:
    """Return the human-readable fallback text for logging/context."""
    strategy = get_strategy(service)
    if strategy.bridge_clip:
        return BRIDGE_TEXT.get(strategy.bridge_clip, "")
    return ""
