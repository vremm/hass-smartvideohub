"""Select platform for the Smart Video Hub integration.

Provides select entities for:
  - Streaming platform (Web Presenter)
  - Video mode (Web Presenter)
  - Quality level (Web Presenter)
  - LUT selection (Teranex)
  - Serial port direction (control/slave/auto) — Videohub
  - Serial port routing — Videohub
"""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id

from .const import DOMAIN
from .pyvideohub import MODEL_STREAMING, MODEL_TERANEX, MODEL_VIDEOHUB, SmartVideoHub

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = "select.{}"


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Smart Video Hub select platform."""
    dev: SmartVideoHub = hass.data[DOMAIN][config_entry.entry_id]["client"]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=dev.name,
        manufacturer="Blackmagic Design",
        model=dev.model,
    )

    entities = []
    entity_prefix = dev.attrs.get("Unique ID", dev.name)

    if dev.model == MODEL_STREAMING:
        entities.extend(
            [
                StreamingSelectDevice(hass, dev, entity_prefix, "platform", device_info),
                StreamingSelectDevice(hass, dev, entity_prefix, "quality_level", device_info),
                StreamingSelectDevice(hass, dev, entity_prefix, "video_mode", device_info),
            ]
        )
    elif dev.model == MODEL_TERANEX:
        entities.append(
            StreamingSelectDevice(hass, dev, entity_prefix, "lut", device_info)
        )

    if dev.model == MODEL_VIDEOHUB:
        # Serial port direction selects
        for port_number, port_label in dev.serial_ports.items():
            entities.append(
                SerialPortDirectionSelect(hass, dev, entity_prefix, port_number, port_label, device_info)
            )
        # Serial port routing selects
        for port_number, port_label in dev.serial_ports.items():
            entities.append(
                SerialPortRoutingSelect(hass, dev, entity_prefix, port_number, port_label, device_info)
            )

    if entities:
        async_add_entities(entities, True)


class StreamingSelectDevice(SelectEntity):
    """Representation of a Smart Video Hub select entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass,
        dev: SmartVideoHub,
        entity_prefix: str,
        translation_key: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the select entity."""
        self.hass = hass
        self._dev = dev
        self._attr_translation_key = translation_key
        self._attr_unique_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{entity_prefix}/{translation_key}",
            hass=hass,
        )
        self._attr_device_info = device_info
        self._dev.add_update_callback(self.update_callback)

    def update(self) -> None:
        """Retrieve latest state."""
        if self._attr_translation_key == "platform":
            self._attr_current_option = self._dev.stream_set.get("Current Platform")
            platforms = []
            if default := self._dev.stream_set.get("Available Default Platforms"):
                platforms.extend(default.split(", "))
            if custom := self._dev.stream_set.get("Available Custom Platforms"):
                platforms.extend(custom.split(", "))
            self._attr_options = platforms
            self._attr_available = (
                self._dev.stream_state.get("Status") == "Idle"
                and self._dev.connected
            )
        elif self._attr_translation_key == "video_mode":
            self._attr_current_option = self._dev.stream_set.get("Video Mode")
            modes = self._dev.stream_set.get("Available Video Modes", "")
            self._attr_options = modes.split(", ") if modes else []
            self._attr_available = (
                self._dev.stream_state.get("Status") == "Idle"
                and self._dev.connected
            )
        elif self._attr_translation_key == "quality_level":
            self._attr_current_option = self._dev.stream_set.get("Current Quality Level")
            levels = self._dev.stream_set.get("Available Quality Levels", "")
            self._attr_options = levels.split(", ") if levels else []
            self._attr_available = (
                self._dev.stream_state.get("Status") == "Idle"
                and self._dev.connected
            )
        elif self._attr_translation_key == "lut":
            num_luts_str = self._dev.teranex_set.get("Number of LUTs", "0")
            try:
                num_luts = int(num_luts_str)
            except (ValueError, TypeError):
                num_luts = 0
            self._attr_options = ["none"] + [f"Lut {x}" for x in range(num_luts)]
            self._attr_current_option = self._dev.teranex_set.get("Lut selection", "none")
            self._attr_available = self._dev.connected

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        if self._attr_translation_key == "platform":
            self._dev.set_stream_platform(option)
        elif self._attr_translation_key == "video_mode":
            self._dev.set_video_mode(option)
        elif self._attr_translation_key == "quality_level":
            self._dev.set_quality_level(option)
        elif self._attr_translation_key == "lut":
            self._dev.set_lut(option)
        self.async_write_ha_state()

    @callback
    def update_callback(self, output_id: int | bool = 0) -> None:
        """Called when data is received."""
        self.update()
        self.async_write_ha_state()


class SerialPortDirectionSelect(SelectEntity):
    """Select entity for serial port direction (control/slave/auto)."""

    _attr_should_poll = False
    _attr_icon = "mdi:serial-port"

    def __init__(
        self,
        hass,
        dev: SmartVideoHub,
        entity_prefix: str,
        port_number: int,
        port_label: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the serial port direction select."""
        self.hass = hass
        self._dev = dev
        self._port_number = port_number
        self._attr_unique_id = f"{entity_prefix}_serial_dir_{port_number}"
        self._attr_name = f"{port_label} Direction"
        self._attr_options = ["control", "slave", "auto"]
        self._attr_current_option = dev.serial_port_directions.get(port_number, "auto")
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{entity_prefix} serial {port_number} direction", hass=hass
        )
        self._attr_device_info = device_info
        dev.add_update_callback(self._handle_update)

    @property
    def available(self) -> bool:
        """Return whether the device is connected."""
        return self._dev.connected

    async def async_select_option(self, option: str) -> None:
        """Select the serial port direction."""
        self._dev.set_serial_port_direction(self._port_number, option)
        self._attr_current_option = option
        self.async_write_ha_state()

    @callback
    def _handle_update(self, output_id: int | bool = 0) -> None:
        """Update when data received."""
        self._attr_current_option = self._dev.serial_port_directions.get(
            self._port_number, "auto"
        )
        self.async_write_ha_state()


class SerialPortRoutingSelect(SelectEntity):
    """Select entity for routing a serial port to a video input."""

    _attr_should_poll = False
    _attr_icon = "mdi:connection"

    def __init__(
        self,
        hass,
        dev: SmartVideoHub,
        entity_prefix: str,
        port_number: int,
        port_label: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the serial port routing select."""
        self.hass = hass
        self._dev = dev
        self._port_number = port_number
        self._attr_unique_id = f"{entity_prefix}_serial_route_{port_number}"
        self._attr_name = f"{port_label} Source"
        self._attr_options = list(dev.get_inputs().values())
        routed_input = dev.serial_port_routing.get(port_number)
        if routed_input:
            self._attr_current_option = dev.get_input_name(routed_input)
        else:
            self._attr_current_option = None
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{entity_prefix} serial {port_number} route", hass=hass
        )
        self._attr_device_info = device_info
        dev.add_update_callback(self._handle_update)

    @property
    def available(self) -> bool:
        """Return whether the device is connected."""
        return self._dev.connected

    async def async_select_option(self, option: str) -> None:
        """Route the serial port to the selected input."""
        input_list = self._dev.get_input_list()
        if option in input_list:
            input_number = list(self._dev.get_inputs().keys())[
                list(self._dev.get_inputs().values()).index(option)
            ]
            self._dev.set_serial_port_routing(self._port_number, input_number)
            self._attr_current_option = option
            self.async_write_ha_state()

    @callback
    def _handle_update(self, output_id: int | bool = 0) -> None:
        """Update when data received."""
        self._attr_options = list(self._dev.get_inputs().values())
        routed_input = self._dev.serial_port_routing.get(self._port_number)
        if routed_input:
            self._attr_current_option = self._dev.get_input_name(routed_input)
        self.async_write_ha_state()