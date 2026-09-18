"""Switch platform for the Smart Video Hub integration.

Provides a streaming on/off switch for Web Presenter devices.
"""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id

from .const import DOMAIN
from .pyvideohub import MODEL_STREAMING, SmartVideoHub

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = "switch.{}"


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Smart Video Hub switch platform."""
    dev: SmartVideoHub = hass.data[DOMAIN][config_entry.entry_id]["client"]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=dev.name,
        manufacturer="Blackmagic Design",
        model=dev.model,
    )

    if dev.model == MODEL_STREAMING:
        entity_prefix = dev.attrs.get("Unique ID", dev.name)
        async_add_entities(
            [
                StreamingSwitchDevice(
                    hass,
                    dev,
                    entity_prefix,
                    "streaming",
                    device_info,
                )
            ],
            True,
        )


class StreamingSwitchDevice(SwitchEntity):
    """Switch entity for streaming on/off."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:ip"
    _attr_translation_key = "streaming"

    def __init__(
        self,
        hass,
        dev: SmartVideoHub,
        entity_prefix: str,
        translation_key: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the streaming switch."""
        self.hass = hass
        self._dev = dev
        self._attr_unique_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{entity_prefix}/{translation_key}",
            hass=hass,
        )
        self._attr_device_info = device_info
        self._dev.add_update_callback(self.update_callback)

    @property
    def is_on(self) -> bool:
        """Return True if streaming is active."""
        return self._dev.stream_state.get("Status") != "Idle"

    @property
    def available(self) -> bool:
        """Return whether the device is connected."""
        return self._dev.connected

    async def async_turn_on(self) -> None:
        """Start streaming."""
        self._dev.set_stream_state(True)
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Stop streaming."""
        self._dev.set_stream_state(False)
        self.async_write_ha_state()

    @callback
    def update_callback(self, output_id: int | bool = 0) -> None:
        """Called when data is received."""
        self.async_write_ha_state()