"""Diagnostics support for the Smart Video Hub integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .pyvideohub import SmartVideoHub


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    client: SmartVideoHub = hass.data[DOMAIN][entry.entry_id]["client"]

    return {
        "entry": {
            "title": entry.title,
            "host": entry.data.get("host"),
            "port": entry.data.get("port"),
        },
        "device": {
            "name": client.name,
            "model": client.model,
            "connected": client.connected,
            "initialised": client.is_initialised,
            "attributes": dict(client.attrs),
        },
        "inputs": {
            str(k): v for k, v in client.inputs.items()
        },
        "outputs": {
            str(k): dict(v) for k, v in client.get_outputs().items()
        },
        "output_locks": {
            str(k): v for k, v in client.output_locks.items()
        },
        "monitoring_outputs": {
            str(k): dict(v) for k, v in client.monitoring_outputs.items()
        },
        "serial_ports": {
            str(k): v for k, v in client.serial_ports.items()
        },
        "video_input_status": {
            str(k): v for k, v in client.video_input_status.items()
        },
        "video_output_status": {
            str(k): v for k, v in client.video_output_status.items()
        },
    }