"""Session model (FR-004, Clarification Q2).

Represents a single user conversation session with rolling context window.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from src.config import config


class ConnectionState(StrEnum):
    """Possible session connection states."""

    ACTIVE = "active"
    IDLE = "idle"
    CLOSED = "closed"


class ConversationTurn(BaseModel):
    """A single user + assistant exchange."""

    model_config = ConfigDict(frozen=True)
    user_text: str
    assistant_text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Session(BaseModel):
    """Mutable session representing one voice conversation.

    Conversation history is capped at ``max_context_turns`` (default 10) on a
    rolling basis per FR-004 / Clarification Q2.
    """

    model_config = ConfigDict(validate_assignment=True)

    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    state: ConnectionState = ConnectionState.ACTIVE
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = Field(default_factory=lambda: datetime.now(UTC))
    idle_timeout_seconds: float = Field(default=config.session.idle_timeout_seconds)
    max_context_turns: int = Field(default=config.session.max_context_turns)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def add_turn(self, user_text: str, assistant_text: str) -> None:
        """Append a conversation turn, enforcing the rolling window cap."""
        self.conversation_history.append(
            ConversationTurn(user_text=user_text, assistant_text=assistant_text)
        )
        if len(self.conversation_history) > self.max_context_turns:
            self.conversation_history = self.conversation_history[-self.max_context_turns :]
        self.touch()

    def touch(self) -> None:
        """Update last_activity timestamp."""
        self.last_activity = datetime.now(UTC)

    def close(self) -> None:
        """Mark session closed and purge ephemeral data."""
        self.state = ConnectionState.CLOSED
        self.conversation_history = []

    @property
    def context_texts(self) -> list[dict[str, str]]:
        """Return conversation history as a list of role/content dicts for LLM context."""
        messages: list[dict[str, str]] = []
        for turn in self.conversation_history:
            messages.append({"role": "user", "content": turn.user_text})
            messages.append({"role": "assistant", "content": turn.assistant_text})
        return messages

    @property
    def is_active(self) -> bool:
        return self.state == ConnectionState.ACTIVE
