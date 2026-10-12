"""Shared row shapes for harvest planning without a database."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class HarvestRow(Protocol):
    id: int
    role: str
    content: str | None


@dataclass
class MessageRow:
    """Concrete chat row with a stable monotonic id."""

    id: int
    role: str
    content: str | None = None
    created_at: str | None = None
