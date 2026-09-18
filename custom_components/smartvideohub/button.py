"""Button platform for the Smart Video Hub integration.

Provides a reboot button for all device types.
"""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id

from .const import DOMAIN
from .pyvideohub import SmartVideoHub

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = "button.{}"


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Smart Video Hub button platform."""
    dev: SmartVideoHub = hass.data[DOMAIN][config_entry.entry_id]["client"]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=dev.name,
        manufacturer="Blackmagic Design",
        model=dev.model,
    )

    entity_prefix = dev.attrs.get("Unique ID", dev.name)
    async_add_entities(
        [
            VideoHubRebootButton(
                hass,
                dev,
                entity_prefix,
                device_info,
            )
        ],
        True,
    )


class VideoHubRebootButton(ButtonEntity):
    """Button entity for rebooting the Videohub device."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "reboot"
    _attr_icon = "mdi:restart"

    def __init__(
        self,
        hass,
        dev: SmartVideoHub,
        entity_prefix: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the reboot button."""
        self.hass = hass
        self._dev = dev
        self._attr_unique_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{entity_prefix}/reboot",
            hass=hass,
        )
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        """Return whether the device is connected."""
        return self._dev.connected

    async def async_press(self) -> None:
        """Press the button — reboot the device."""
        self._dev.reboot()