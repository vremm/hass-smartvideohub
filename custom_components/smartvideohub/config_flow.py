"""Config flow for the Blackmagic Smart Video Hub integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_HIDE_DEFAULT_INPUTS, DEFAULT_PORT, DOMAIN
from .pyvideohub import SmartVideoHub

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_HIDE_DEFAULT_INPUTS, default=False): bool,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    client = SmartVideoHub(
        data[CONF_HOST],
        data[CONF_PORT],
        loop=hass.loop,
    )
    client.start()

    try:
        await asyncio.wait_for(client.initialised.wait(), timeout=15)
        title = client.name or f"VideoHub {data[CONF_HOST]}"
        return {"title": title}
    except asyncio.TimeoutError:
        raise ValueError("communication_error")
    except Exception as err:
        _LOGGER.error("Communication Error: %s: %s", err.__class__.__name__, err)
        raise ValueError("communication_error") from err
    finally:
        client.stop()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Video Hub."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check for duplicate entries with the same host
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )
            except (ConnectionError, ConnectionRefusedError, OSError):
                errors["base"] = "cannot_connect"
            except ValueError as err:
                if str(err) == "communication_error":
                    errors["base"] = "communication_error"
                else:
                    errors["base"] = "unknown"
                    _LOGGER.error("Unexpected error: %s: %s", err.__class__.__name__, err)
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected error: %s: %s", err.__class__.__name__, err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )