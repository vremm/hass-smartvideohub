"""Text platform for the Smart Video Hub integration.

Provides text entities for renaming input and output port labels,
and for setting the stream key on Web Presenter devices.
"""

from __future__ import annotations

import logging

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id

from .const import DOMAIN
from .pyvideohub import MODEL_STREAMING, MODEL_VIDEOHUB, SmartVideoHub

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = "text.{}"


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Smart Video Hub text platform."""
    dev: SmartVideoHub = hass.data[DOMAIN][config_entry.entry_id]["client"]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=dev.name,
        manufacturer="Blackmagic Design",
        model=dev.model,
    )

    entities = []
    entity_prefix = dev.attrs.get("Unique ID", dev.name)

    if dev.model == MODEL_VIDEOHUB:
        # Input label text entities
        for input_number, input_name in dev.get_inputs().items():
            entities.append(
                VideoHubLabelText(
                    hass,
                    dev,
                    entity_prefix,
                    "input",
                    input_number,
                    input_name,
                    device_info,
                )
            )
        # Output label text entities
        for output_number, output in dev.get_outputs().items():
            entities.append(
                VideoHubLabelText(
                    hass,
                    dev,
                    entity_prefix,
                    "output",
                    output_number,
                    output.get("name", f"Output {output_number}"),
                    device_info,
                )
            )

    if dev.model == MODEL_STREAMING:
        entities.append(
            StreamingInputDevice(
                hass,
                dev,
                entity_prefix,
                "stream_key",
                device_info,
            )
        )
        # Stream URL (if customizable)
        entities.append(
            StreamingInputDevice(
                hass,
                dev,
                entity_prefix,
                "stream_url",
                device_info,
            )
        )
        # Stream password (for SRT)
        entities.append(
            StreamingInputDevice(
                hass,
                dev,
                entity_prefix,
                "stream_password",
                device_info,
            )
        )
        # Device label
        entities.append(
            StreamingInputDevice(
                hass,
                dev,
                entity_prefix,
                "device_label",
                device_info,
            )
        )

    if entities:
        async_add_entities(entities, True)


class VideoHubLabelText(TextEntity):
    """Text entity for renaming a Videohub input or output label."""

    _attr_should_poll = False
    _attr_mode = TextMode.TEXT
    _attr_native_max = 40  # Videohub labels have a max length

    def __init__(
        self,
        hass,
        smartvideohub: SmartVideoHub,
        entity_prefix: str,
        port_type: str,  # "input" or "output"
        port_number: int,
        current_label: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the label text entity."""
        self.hass = hass
        self._smartvideohub = smartvideohub
        self._port_type = port_type
        self._port_number = port_number

        self._attr_unique_id = f"{entity_prefix}_{port_type}_label_{port_number}"
        self._attr_name = f"{current_label} Label"
        self._attr_native_value = current_label
        self._attr_icon = "mdi:label" if port_type == "input" else "mdi:label-outline"
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{entity_prefix} {port_type} {port_number} label",
            hass=hass,
        )
        self._attr_device_info = device_info

    async def async_added_to_hass(self) -> None:
        """Subscribe to VideoHub updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._smartvideohub.add_update_callback(self._handle_update)
        )

    @property
    def available(self) -> bool:
        """Return whether the VideoHub connection is available."""
        return self._smartvideohub.connected

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        return {
            "port_type": self._port_type,
            "port_number": self._port_number,
        }

    async def async_set_value(self, value: str) -> None:
        """Set the label value."""
        if self._port_type == "input":
            self._smartvideohub.set_input_label(self._port_number, value)
        else:
            self._smartvideohub.set_output_label(self._port_number, value)
        self._attr_native_value = value
        self.async_write_ha_state()

    @callback
    def _handle_update(self, output_id: int | bool = 0) -> None:
        """Called when data is received from the VideoHub."""
        if output_id not in (0, -1, self._port_number):
            return
        # Update the label from the client's cached state
        if self._port_type == "input":
            inputs = self._smartvideohub.get_inputs()
            if self._port_number in inputs:
                self._attr_native_value = inputs[self._port_number]
        else:
            outputs = self._smartvideohub.get_outputs()
            if self._port_number in outputs:
                self._attr_native_value = outputs[self._port_number].get(
                    "name", f"Output {self._port_number}"
                )
        self.async_write_ha_state()


class StreamingInputDevice(TextEntity):
    """Text entity for Web Presenter streaming settings and device label."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_mode = TextMode.TEXT

    def __init__(
        self,
        hass,
        dev: SmartVideoHub,
        entity_prefix: str,
        translation_key: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the streaming text entity."""
        self.hass = hass
        self._dev = dev
        self._attr_translation_key = translation_key
        self._attr_unique_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{entity_prefix}/{translation_key}",
            hass=hass,
        )
        self._attr_device_info = device_info
        self._attr_available = False
        self._attr_native_value = None

        # Set icon based on type
        if translation_key == "stream_key":
            self._attr_icon = "mdi:key"
        elif translation_key == "stream_url":
            self._attr_icon = "mdi:link"
        elif translation_key == "stream_password":
            self._attr_icon = "mdi:lock-outline"
            self._attr_mode = TextMode.PASSWORD
        elif translation_key == "device_label":
            self._attr_icon = "mdi:label"

        self._dev.add_update_callback(self.update_callback)

    def update_callback(self, output_id: int | bool = 0) -> None:
        """Called when data is received."""
        self.update()
        self.schedule_update_ha_state(False)

    def update(self) -> None:
        """Retrieve latest state."""
        key = self._attr_translation_key
        if key == "stream_key":
            self._attr_native_value = self._dev.stream_set.get("Stream Key")
            self._attr_available = (
                self._dev.stream_state.get("Status") == "Idle"
                and self._dev.connected
            )
        elif key == "stream_url":
            self._attr_native_value = self._dev.stream_set.get("Current URL")
            customizable = self._dev.stream_set.get("Customizable URL", "false")
            self._attr_available = customizable == "true" and self._dev.connected
        elif key == "stream_password":
            self._attr_native_value = self._dev.stream_set.get("Password", "")
            self._attr_available = self._dev.connected
        elif key == "device_label":
            self._attr_native_value = self._dev.name
            self._attr_available = self._dev.connected

    async def async_set_value(self, value: str) -> None:
        """Set the value."""
        key = self._attr_translation_key
        self._attr_native_value = value
        if key == "stream_key":
            self._dev.set_stream_key(value)
        elif key == "stream_url":
            self._dev.set_stream_url(value)
        elif key == "stream_password":
            self._dev.set_stream_password(value)
        elif key == "device_label":
            self._dev.set_device_label(value)
        self.async_write_ha_state()