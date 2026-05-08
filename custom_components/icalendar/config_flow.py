"""Config flow for iCalendar API."""

from __future__ import annotations

import re
import secrets
from collections.abc import Mapping

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_USER, FlowType
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    CONF_ALLOWLIST,
    CONF_BLOCKLIST,
    CONF_CALENDAR_ENTITY_ID,
    CONF_FUTURE_WEEKS,
    CONF_HISTORY_WEEKS,
    CONF_SECRET,
    DEFAULT_FUTURE_WEEKS,
    DEFAULT_HISTORY_WEEKS,
    DOMAIN,
    NAME,
    URL_PATH_PREFIX,
)


def _generate_secret() -> str:
    """Generate a URL-safe secret."""
    return secrets.token_urlsafe(24)


def _is_secret_valid(secret: str) -> bool:
    """Validate secret length/strength for URL auth."""
    return len(secret) >= 20


def _validate_regex(value: str | None) -> bool:
    """Validate optional regex value."""
    if not value:
        return True
    try:
        re.compile(value)
    except re.error:
        return False
    return True


def _build_feed_urls(
    hass: HomeAssistant, entry_id: str, secret: str
) -> tuple[str, str]:
    """Build local/internal and external URLs where available."""
    path = f"{URL_PATH_PREFIX}/{entry_id}/{secret}"

    local_base = hass.config.internal_url or ""
    external_base = hass.config.external_url or ""

    local_url = f"{local_base}{path}" if local_base else ""
    external_url = f"{external_base}{path}" if external_base else ""

    return local_url, external_url


def _build_urls_text(local_url: str, external_url: str) -> str:
    """Create URL description block with only available URLs."""
    lines: list[str] = []
    if local_url:
        lines.append(f"Current local URL:\n{local_url}")
    if external_url:
        lines.append(f"Current external URL:\n{external_url}")
    return "\n".join(lines)


def _title_for_entity(entity_id: str) -> str:
    """Build config entry title."""
    return f"{NAME} ({entity_id})"


class ICalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iCalendar API."""

    VERSION = 1

    async def async_on_create_entry(self, result):
        """Continue to options flow after setup to show the generated feed URL."""
        if self.source != SOURCE_USER:
            return result

        options_result = await self.hass.config_entries.options.async_init(
            result["result"].entry_id
        )
        result["next_flow"] = (FlowType.OPTIONS_FLOW, options_result["flow_id"])
        return result

    async def async_step_user(self, user_input: Mapping[str, str] | None = None):
        """Handle initial setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entity_id = user_input[CONF_CALENDAR_ENTITY_ID]
            allowlist = user_input.get(CONF_ALLOWLIST) or None
            blocklist = user_input.get(CONF_BLOCKLIST) or None

            if not _validate_regex(allowlist):
                errors[CONF_ALLOWLIST] = "invalid_allowlist"
            if not _validate_regex(blocklist):
                errors[CONF_BLOCKLIST] = "invalid_blocklist"
            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=_build_user_schema(user_input),
                    errors=errors,
                )

            if self.hass.states.get(entity_id) is None:
                return self.async_show_form(
                    step_id="user",
                    data_schema=_build_user_schema(user_input),
                    errors={CONF_CALENDAR_ENTITY_ID: "entity_not_found"},
                )

            # Prevent duplicate entries for the same calendar entity.
            for entry in self._async_current_entries():
                if entry.data.get(CONF_CALENDAR_ENTITY_ID) == entity_id:
                    return self.async_abort(reason="already_configured")

            secret = _generate_secret()
            data = {
                CONF_CALENDAR_ENTITY_ID: entity_id,
                CONF_SECRET: secret,
                CONF_ALLOWLIST: allowlist,
                CONF_BLOCKLIST: blocklist,
                CONF_HISTORY_WEEKS: user_input.get(
                    CONF_HISTORY_WEEKS, DEFAULT_HISTORY_WEEKS
                ),
                CONF_FUTURE_WEEKS: user_input.get(
                    CONF_FUTURE_WEEKS, DEFAULT_FUTURE_WEEKS
                ),
            }

            return self.async_create_entry(
                title=_title_for_entity(entity_id),
                data=data,
            )

        return self.async_show_form(
            step_id="user", data_schema=_build_user_schema(), errors=errors
        )

    async def async_step_reconfigure(self, user_input: Mapping[str, str] | None = None):
        """Handle reconfiguration from the UI."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        existing_secret = entry.data.get(CONF_SECRET, "")
        local_url, external_url = _build_feed_urls(
            self.hass, entry.entry_id, existing_secret
        )
        if user_input is not None:
            selected_entity = user_input[CONF_CALENDAR_ENTITY_ID]
            allowlist = user_input.get(CONF_ALLOWLIST) or None
            blocklist = user_input.get(CONF_BLOCKLIST) or None

            if not _validate_regex(allowlist):
                errors[CONF_ALLOWLIST] = "invalid_allowlist"

            if not _validate_regex(blocklist):
                errors[CONF_BLOCKLIST] = "invalid_blocklist"

            if self.hass.states.get(selected_entity) is None:
                errors[CONF_CALENDAR_ENTITY_ID] = "entity_not_found"

            if errors:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=_build_reconfigure_schema(entry),
                    errors=errors,
                    description_placeholders={
                        "url_block": _build_urls_text(local_url, external_url),
                    },
                )

            for existing_entry in self._async_current_entries():
                if (
                    existing_entry.entry_id != entry.entry_id
                    and existing_entry.data.get(CONF_CALENDAR_ENTITY_ID)
                    == selected_entity
                ):
                    return self.async_abort(reason="already_configured")

            updated_data = {
                **entry.data,
                CONF_CALENDAR_ENTITY_ID: selected_entity,
                CONF_ALLOWLIST: allowlist,
                CONF_BLOCKLIST: blocklist,
                CONF_HISTORY_WEEKS: user_input.get(
                    CONF_HISTORY_WEEKS, DEFAULT_HISTORY_WEEKS
                ),
                CONF_FUTURE_WEEKS: user_input.get(
                    CONF_FUTURE_WEEKS, DEFAULT_FUTURE_WEEKS
                ),
            }

            new_secret = user_input.get(CONF_SECRET)
            if new_secret:
                if not _is_secret_valid(new_secret):
                    errors[CONF_SECRET] = "invalid_secret"
                else:
                    updated_data[CONF_SECRET] = new_secret

            if errors:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=_build_reconfigure_schema(entry),
                    errors=errors,
                    description_placeholders={
                        "url_block": _build_urls_text(local_url, external_url),
                    },
                )

            self.hass.config_entries.async_update_entry(
                entry,
                title=_title_for_entity(updated_data[CONF_CALENDAR_ENTITY_ID]),
                data=updated_data,
            )
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_reconfigure_schema(entry),
            description_placeholders={
                "url_block": _build_urls_text(local_url, external_url),
            },
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get options flow."""
        return ICalendarOptionsFlow()


class ICalendarOptionsFlow(config_entries.OptionsFlow):
    """Handle options for iCalendar API."""

    async def async_step_init(self, user_input: Mapping[str, str] | None = None):
        """Manage options."""
        errors: dict[str, str] = {}
        existing_secret = self.config_entry.data.get(CONF_SECRET, "")
        local_url, external_url = _build_feed_urls(
            self.hass, self.config_entry.entry_id, existing_secret
        )
        if user_input is not None:
            new_secret = user_input.get(CONF_SECRET)
            allowlist = user_input.get(CONF_ALLOWLIST) or None
            blocklist = user_input.get(CONF_BLOCKLIST) or None

            if not _validate_regex(allowlist):
                errors[CONF_ALLOWLIST] = "invalid_allowlist"
            if not _validate_regex(blocklist):
                errors[CONF_BLOCKLIST] = "invalid_blocklist"

            if new_secret and not _is_secret_valid(new_secret):
                errors[CONF_SECRET] = "invalid_secret"
            if errors:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_build_options_schema(self.config_entry),
                    errors=errors,
                    description_placeholders={
                        "url_block": _build_urls_text(local_url, external_url),
                    },
                )

            updated_data = {
                **self.config_entry.data,
                CONF_ALLOWLIST: allowlist,
                CONF_BLOCKLIST: blocklist,
                CONF_HISTORY_WEEKS: user_input.get(
                    CONF_HISTORY_WEEKS, DEFAULT_HISTORY_WEEKS
                ),
                CONF_FUTURE_WEEKS: user_input.get(
                    CONF_FUTURE_WEEKS, DEFAULT_FUTURE_WEEKS
                ),
            }
            if new_secret:
                updated_data[CONF_SECRET] = new_secret

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=updated_data,
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_schema(self.config_entry),
            description_placeholders={
                "url_block": _build_urls_text(local_url, external_url),
            },
        )


def _build_user_schema(user_input: Mapping[str, str] | None = None) -> vol.Schema:
    """Build the setup schema."""
    entity_key: object
    if user_input and user_input.get(CONF_CALENDAR_ENTITY_ID):
        entity_key = vol.Required(
            CONF_CALENDAR_ENTITY_ID, default=user_input[CONF_CALENDAR_ENTITY_ID]
        )
    else:
        entity_key = vol.Required(CONF_CALENDAR_ENTITY_ID)

    return vol.Schema(
        {
            entity_key: selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["calendar"])
            ),
            vol.Optional(
                CONF_ALLOWLIST,
                default=(user_input.get(CONF_ALLOWLIST, "") if user_input else ""),
            ): str,
            vol.Optional(
                CONF_BLOCKLIST,
                default=(user_input.get(CONF_BLOCKLIST, "") if user_input else ""),
            ): str,
            vol.Optional(
                CONF_HISTORY_WEEKS,
                default=int(
                    user_input.get(CONF_HISTORY_WEEKS, DEFAULT_HISTORY_WEEKS)
                    if user_input
                    else DEFAULT_HISTORY_WEEKS
                ),
            ): int,
            vol.Optional(
                CONF_FUTURE_WEEKS,
                default=int(
                    user_input.get(CONF_FUTURE_WEEKS, DEFAULT_FUTURE_WEEKS)
                    if user_input
                    else DEFAULT_FUTURE_WEEKS
                ),
            ): int,
        }
    )


def _build_reconfigure_schema(entry: config_entries.ConfigEntry) -> vol.Schema:
    """Build reconfigure schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_CALENDAR_ENTITY_ID,
                default=entry.data.get(CONF_CALENDAR_ENTITY_ID),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["calendar"])
            ),
            vol.Optional(CONF_SECRET, default=entry.data.get(CONF_SECRET, "")): str,
            vol.Optional(
                CONF_ALLOWLIST, default=entry.data.get(CONF_ALLOWLIST, "") or ""
            ): str,
            vol.Optional(
                CONF_BLOCKLIST, default=entry.data.get(CONF_BLOCKLIST, "") or ""
            ): str,
            vol.Optional(
                CONF_HISTORY_WEEKS,
                default=int(entry.data.get(CONF_HISTORY_WEEKS, DEFAULT_HISTORY_WEEKS)),
            ): int,
            vol.Optional(
                CONF_FUTURE_WEEKS,
                default=int(entry.data.get(CONF_FUTURE_WEEKS, DEFAULT_FUTURE_WEEKS)),
            ): int,
        }
    )


def _build_options_schema(entry: config_entries.ConfigEntry) -> vol.Schema:
    """Build options schema."""
    return vol.Schema(
        {
            vol.Optional(CONF_SECRET, default=entry.data.get(CONF_SECRET, "")): str,
            vol.Optional(
                CONF_ALLOWLIST, default=entry.data.get(CONF_ALLOWLIST, "") or ""
            ): str,
            vol.Optional(
                CONF_BLOCKLIST, default=entry.data.get(CONF_BLOCKLIST, "") or ""
            ): str,
            vol.Optional(
                CONF_HISTORY_WEEKS,
                default=int(entry.data.get(CONF_HISTORY_WEEKS, DEFAULT_HISTORY_WEEKS)),
            ): int,
            vol.Optional(
                CONF_FUTURE_WEEKS,
                default=int(entry.data.get(CONF_FUTURE_WEEKS, DEFAULT_FUTURE_WEEKS)),
            ): int,
        }
    )
