"""HTTP view for iCalendar feed exposure."""

from __future__ import annotations

import hmac
import re
from http import HTTPStatus
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import CONTENT_TYPE_ICAL, DOMAIN, URL_PATH_PREFIX
from .ical import build_icalendar
from .models import ICalendarRuntimeData


class ICalendarView(HomeAssistantView):
    """Serve iCalendar feeds."""

    name = DOMAIN
    url = f"{URL_PATH_PREFIX}/{{entry_id}}/{{secret}}"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(
        self, request: web.Request, entry_id: str, secret: str
    ) -> web.Response:
        """Handle iCalendar feed requests."""
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            return web.Response(body="404: Not Found", status=HTTPStatus.NOT_FOUND)

        runtime_data = getattr(entry, "runtime_data", None)
        if runtime_data is None or not isinstance(runtime_data, ICalendarRuntimeData):
            return web.Response(
                body="503: Service Unavailable", status=HTTPStatus.SERVICE_UNAVAILABLE
            )

        if not secret or not runtime_data.secret:
            return web.Response(body="403: Forbidden", status=HTTPStatus.FORBIDDEN)

        if not hmac.compare_digest(str(secret), str(runtime_data.secret)):
            return web.Response(
                body="401: Unauthorized", status=HTTPStatus.UNAUTHORIZED
            )

        entity_id = runtime_data.calendar_entity_id
        if not entity_id.startswith("calendar."):
            return web.Response(body="403: Forbidden", status=HTTPStatus.FORBIDDEN)

        state = self.hass.states.get(entity_id)
        if state is None:
            return web.Response(body="404: Not Found", status=HTTPStatus.NOT_FOUND)

        events = await self._fetch_events(
            entity_id,
            history_weeks=runtime_data.history_weeks,
            future_weeks=runtime_data.future_weeks,
        )
        if events is None:
            return web.Response(body="404: Not Found", status=HTTPStatus.NOT_FOUND)

        events = self._filter_events(
            events,
            allowlist=runtime_data.allowlist,
            blocklist=runtime_data.blocklist,
        )

        feed = build_icalendar(self.hass, entity_id, state.name, events)
        return web.Response(body=feed, content_type=CONTENT_TYPE_ICAL, charset="utf-8")

    async def _fetch_events(
        self,
        entity_id: str,
        history_weeks: int,
        future_weeks: int,
    ) -> list[dict[str, Any]] | None:
        """Fetch events from Home Assistant calendar service."""
        from datetime import datetime, timedelta, timezone

        start = datetime.now(timezone.utc) - timedelta(weeks=history_weeks)
        end = datetime.now(timezone.utc) + timedelta(weeks=future_weeks)

        events_response = await self.hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": entity_id,
                "start_date_time": start.isoformat(),
                "end_date_time": end.isoformat(),
            },
            blocking=True,
            return_response=True,
        )
        if not events_response or entity_id not in events_response:
            return None
        return events_response[entity_id].get("events", [])

    def _filter_events(
        self,
        events: list[dict[str, Any]],
        allowlist: str | None,
        blocklist: str | None,
    ) -> list[dict[str, Any]]:
        """Filter events using optional regex allowlist/blocklist rules."""
        allow_pattern = self._compile_regex(allowlist)
        block_pattern = self._compile_regex(blocklist)

        if allow_pattern:
            return [
                event
                for event in events
                if allow_pattern.search(str(event.get("summary") or ""))
            ]

        if block_pattern:
            return [
                event
                for event in events
                if not block_pattern.search(str(event.get("summary") or ""))
            ]

        return events

    @staticmethod
    def _compile_regex(pattern: str | None) -> re.Pattern[str] | None:
        """Compile regex pattern and ignore invalid values."""
        if not pattern:
            return None
        try:
            return re.compile(pattern)
        except re.error:
            return None
