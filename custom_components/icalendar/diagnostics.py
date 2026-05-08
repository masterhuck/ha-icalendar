"""Diagnostics support for iCalendar integration."""

from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_CALENDAR_ENTITY_ID, CONF_SECRET

TO_REDACT = {CONF_SECRET}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    registry = er.async_get(hass)
    entity_id = entry.data.get(CONF_CALENDAR_ENTITY_ID)
    registry_entry = registry.async_get(entity_id) if entity_id else None

    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "entity_exists": hass.states.get(entity_id) is not None if entity_id else False,
        "entity_registry": {
            "entity_id": registry_entry.entity_id if registry_entry else None,
            "disabled_by": registry_entry.disabled_by if registry_entry else None,
            "has_calendar_color": bool(
                registry_entry and registry_entry.options.get("calendar", {}).get("color")
            ),
        },
    }
