"""Data models for iCalendar integration runtime."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ICalendarRuntimeData:
    """Runtime data for one config entry."""

    calendar_entity_id: str
    secret: str
    allowlist: str | None
    blocklist: str | None
