"""Media Player platform for the Smart Video Hub integration.

Each output port on the Videohub is represented as a media_player entity
with source selection (input routing) support.
"""

from __future__ import annotations

import logging

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id

from .const import CONF_HIDE_DEFAULT_INPUTS, DOMAIN
from .pyvideohub import MODEL_VIDEOHUB, SmartVideoHub

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = "media_player.{}"


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Smart Video Hub media player platform."""
    dev: SmartVideoHub = hass.data[DOMAIN][config_entry.entry_id]["client"]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=dev.name,
        manufacturer="Blackmagic Design",
        model=dev.model,
    )

    if dev.model == MODEL_VIDEOHUB:
        entity_prefix = dev.attrs.get("Unique ID", dev.name)

        # Main video outputs
        _LOGGER.info("Adding %i media_player outputs", len(dev.get_outputs()))
        async_add_entities(
            [
                SmartVideoHubOutput(
                    hass,
                    dev,
                    entity_prefix,
                    output_number,
                    output,
                    device_info,
                    is_monitoring=False,
                    hide_default_inputs=config_entry.data.get(
                        CONF_HIDE_DEFAULT_INPUTS, False
                    ),
                )
                for output_number, output in dev.get_outputs().items()
            ],
            True,
        )

        # Monitoring outputs (if any)
        mon_outputs = dev.get_monitoring_outputs()
        if mon_outputs:
            _LOGGER.info("Adding %i media_player monitoring outputs", len(mon_outputs))
            async_add_entities(
                [
                    SmartVideoHubOutput(
                        hass,
                        dev,
                        entity_prefix,
                        mon_number,
                        mon_output,
                        device_info,
                        is_monitoring=True,
                        hide_default_inputs=config_entry.data.get(
                            CONF_HIDE_DEFAULT_INPUTS, False
                        ),
                    )
                    for mon_number, mon_output in mon_outputs.items()
                ],
                True,
            )


class SmartVideoHubOutput(MediaPlayerEntity):
    """Representation of a Smart Video Hub output port."""

    _attr_supported_features = MediaPlayerEntityFeature.SELECT_SOURCE
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_should_poll = False

    def __init__(
        self,
        hass,
        smartvideohub: SmartVideoHub,
        entity_prefix: str,
        output_number: int,
        output: dict,
        device_info: DeviceInfo,
        is_monitoring: bool = False,
        hide_default_inputs: bool = False,
    ) -> None:
        """Initialize the output entity."""
        _LOGGER.info("Adding SmartVideoHub %soutput %i", "monitoring " if is_monitoring else "", output_number)
        self.hass = hass
        self._smartvideohub = smartvideohub
        self._output_id = output_number
        self._is_monitoring = is_monitoring
        self._output_name = output.get("name", f"{'Monitor' if is_monitoring else 'Output'} {output_number}")
        self._source_id = output.get("input")
        self._hide_default_inputs = hide_default_inputs

        port_label = "monitor" if is_monitoring else "output"
        self._attr_unique_id = f"{entity_prefix}_{port_label}_{self._output_id}"
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{entity_prefix} {port_label} {self._output_id}",
            hass=hass,
        )
        self._attr_device_info = device_info

        # Initialize source state
        self._attr_name = self._output_name
        if self._source_id:
            self._attr_source = smartvideohub.get_input_name(self._source_id)
        self._attr_source_list = smartvideohub.get_input_list(self._hide_default_inputs)

    async def async_added_to_hass(self) -> None:
        """Subscribe to VideoHub updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._smartvideohub.add_update_callback(self._handle_update)
        )

    def _update_state(self) -> None:
        """Retrieve latest state from the client."""
        if self._is_monitoring:
            outputs = self._smartvideohub.get_monitoring_outputs()
        else:
            outputs = self._smartvideohub.get_outputs()
        if self._output_id in outputs:
            output = outputs[self._output_id]
            self._output_name = output.get("name", f"{'Monitor' if self._is_monitoring else 'Output'} {self._output_id}")
            self._source_id = output.get("input")
            self._attr_name = self._output_name
            if self._source_id:
                self._attr_source = self._smartvideohub.get_input_name(self._source_id)
            self._attr_source_list = self._smartvideohub.get_input_list(
                self._hide_default_inputs
            )

    @property
    def available(self) -> bool:
        """Return whether the VideoHub connection is available."""
        return self._smartvideohub.connected

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the output."""
        if self._smartvideohub.connected:
            return MediaPlayerState.PLAYING
        return MediaPlayerState.OFF

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self._attr_source

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        self._smartvideohub.set_input_by_name(self._output_id, source)
        self._attr_source = source
        self.async_write_ha_state()

    @callback
    def _handle_update(self, output_id: int | bool = 0) -> None:
        """Called when data is received from the VideoHub."""
        # output_id=0 means general update, output_id=-1 means routing changed for all
        if output_id not in (0, -1, self._output_id):
            return
        _LOGGER.debug("Update for output %i (notified for %s)", self._output_id, output_id)
        self._update_state()
        self.async_write_ha_state()