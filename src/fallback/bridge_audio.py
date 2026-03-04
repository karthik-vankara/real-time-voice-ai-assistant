"""Bridge audio assets and loader utility (FR-010, US3).

Pre-generated audio clips used when services degrade.  In production these
would be real audio files; here we generate simple placeholder PCM buffers
and encode them as base64 for transport over the event schema.
"""

from __future__ import annotations

import base64
import math
import struct
from enum import StrEnum


class BridgeAudioType(StrEnum):
    """Available bridge audio clips."""

    THINKING = "thinking"
    REPEAT = "repeat"
    ONE_MOMENT = "one_moment"


# ---------------------------------------------------------------------------
# Tiny beep/tone generator (placeholder for real audio assets)
# ---------------------------------------------------------------------------

def _generate_tone(
    frequency_hz: float = 440.0,
    duration_seconds: float = 1.0,
    sample_rate: int = 16_000,
    amplitude: int = 8_000,
) -> bytes:
    """Generate a simple sine-wave tone as 16-bit PCM."""
    num_samples = int(sample_rate * duration_seconds)
    samples = []
    for i in range(num_samples):
        value = int(amplitude * math.sin(2 * math.pi * frequency_hz * i / sample_rate))
        samples.append(struct.pack("<h", max(-32768, min(32767, value))))
    return b"".join(samples)


# Pre-generated PCM buffers — each represents a distinct "message"
# In production, these would be pre-recorded TTS clips.
_AUDIO_ASSETS: dict[BridgeAudioType, bytes] = {
    BridgeAudioType.THINKING: _generate_tone(frequency_hz=440.0, duration_seconds=1.5),
    BridgeAudioType.REPEAT: _generate_tone(frequency_hz=520.0, duration_seconds=1.2),
    BridgeAudioType.ONE_MOMENT: _generate_tone(frequency_hz=380.0, duration_seconds=1.0),
}

# Human-readable text for each clip (used in logging / transcription substitution)
BRIDGE_TEXT: dict[BridgeAudioType, str] = {
    BridgeAudioType.THINKING: "Let me think about that...",
    BridgeAudioType.REPEAT: "I didn't catch that, could you repeat?",
    BridgeAudioType.ONE_MOMENT: "One moment please...",
}


def get_bridge_audio_b64(clip: BridgeAudioType) -> str:
    """Return the base64-encoded PCM audio for *clip*."""
    return base64.b64encode(_AUDIO_ASSETS[clip]).decode("ascii")


def get_bridge_audio_raw(clip: BridgeAudioType) -> bytes:
    """Return raw PCM bytes for *clip*."""
    return _AUDIO_ASSETS[clip]
