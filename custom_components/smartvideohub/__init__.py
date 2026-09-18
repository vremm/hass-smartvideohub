"""The Blackmagic Smart Video Hub integration."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .pyvideohub import SmartVideoHub
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Smart Video Hub from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    smartvideohub = SmartVideoHub(
        config_entry.data["host"],
        config_entry.data["port"],
        hass.loop,
    )
    smartvideohub.start()

    # Wait for initial status dump from the device
    try:
        await asyncio.wait_for(smartvideohub.initialised.wait(), timeout=15)
    except asyncio.TimeoutError:
        _LOGGER.warning("Timed out waiting for initial data from Videohub; continuing anyway")

    hass.data[DOMAIN][config_entry.entry_id] = {
        "client": smartvideohub,
    }

    # Start keepalive task
    keepalive_task = hass.loop.create_task(smartvideohub.keep_alive())
    hass.data[DOMAIN][config_entry.entry_id]["keepalive_task"] = keepalive_task

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Register custom services
    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        client: SmartVideoHub = data["client"]
        client.stop()

        # Cancel keepalive task
        keepalive_task = data.get("keepalive_task")
        if keepalive_task:
            keepalive_task.cancel()

        # Unload services if no more config entries
        if not hass.data.get(DOMAIN):
            await async_unload_services(hass)

    return unload_ok