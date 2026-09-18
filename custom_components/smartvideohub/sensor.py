"""Sensor platform for the Smart Video Hub integration.

Provides sensor entities for:
  - Device connection status
  - Video input/output hardware status (BNC, Optical, None)
  - Serial port direction
  - Serial port lock status
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id

from .const import DOMAIN
from .pyvideohub import MODEL_VIDEOHUB, MODEL_STREAMING, SmartVideoHub

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = "sensor.{}"


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Smart Video Hub sensor platform."""
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
        # Connection status sensor
        entities.append(
            VideoHubConnectionSensor(hass, dev, entity_prefix, device_info)
        )

        # Video input status sensors
        for input_number in dev.get_inputs():
            entities.append(
                VideoHubPortStatusSensor(
                    hass, dev, entity_prefix, "input", input_number, device_info
                )
            )

        # Video output status sensors
        for output_number in dev.get_outputs():
            entities.append(
                VideoHubPortStatusSensor(
                    hass, dev, entity_prefix, "output", output_number, device_info
                )
            )

        # Serial port sensors (direction + lock)
        for port_number in dev.serial_ports:
            entities.append(
                SerialPortDirectionSensor(hass, dev, entity_prefix, port_number, device_info)
            )
            entities.append(
                SerialPortLockSensor(hass, dev, entity_prefix, port_number, device_info)
            )

    if entities:
        async_add_entities(entities, True)


class VideoHubConnectionSensor(SensorEntity):
    """Sensor for Videohub connection status."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "connection_status"
    _attr_icon = "mdi:lan-connect"

    def __init__(self, hass, dev: SmartVideoHub, entity_prefix: str, device_info: DeviceInfo) -> None:
        """Initialize the connection sensor."""
        self.hass = hass
        self._dev = dev
        self._attr_unique_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{entity_prefix}/connection", hass=hass
        )
        self._attr_device_info = device_info
        self._attr_native_value = "Connected" if dev.connected else "Disconnected"
        self._dev.add_update_callback(self._handle_update)

    @property
    def available(self) -> bool:
        """Always available — this sensor reports the connection itself."""
        return True

    @callback
    def _handle_update(self, output_id: int | bool = 0) -> None:
        """Update when data received."""
        self._attr_native_value = "Connected" if self._dev.connected else "Disconnected"
        self.async_write_ha_state()


class VideoHubPortStatusSensor(SensorEntity):
    """Sensor for video input/output hardware status (BNC, Optical, None)."""

    _attr_should_poll = False
    _attr_icon = "mdi:video-input-component"

    def __init__(
        self,
        hass,
        dev: SmartVideoHub,
        entity_prefix: str,
        port_type: str,
        port_number: int,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the port status sensor."""
        self.hass = hass
        self._dev = dev
        self._port_type = port_type
        self._port_number = port_number

        # Get the label for the port name
        if port_type == "input":
            label = dev.get_input_name(port_number)
        else:
            outputs = dev.get_outputs()
            label = outputs.get(port_number, {}).get("name", f"Output {port_number}")

        self._attr_unique_id = f"{entity_prefix}_{port_type}_status_{port_number}"
        self._attr_name = f"{label} Hardware Status"
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{entity_prefix} {port_type} {port_number} status", hass=hass
        )
        self._attr_device_info = device_info

        # Set initial value
        if port_type == "input":
            self._attr_native_value = dev.video_input_status.get(port_number, "Unknown")
        else:
            self._attr_native_value = dev.video_output_status.get(port_number, "Unknown")

        dev.add_update_callback(self._handle_update)

    @property
    def available(self) -> bool:
        """Return whether the device is connected."""
        return self._dev.connected

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        return {
            "port_type": self._port_type,
            "port_number": self._port_number,
        }

    @callback
    def _handle_update(self, output_id: int | bool = 0) -> None:
        """Update when data received."""
        if self._port_type == "input":
            self._attr_native_value = self._dev.video_input_status.get(
                self._port_number, "Unknown"
            )
        else:
            self._attr_native_value = self._dev.video_output_status.get(
                self._port_number, "Unknown"
            )
        self.async_write_ha_state()


class SerialPortDirectionSensor(SensorEntity):
    """Sensor for serial port direction (control, slave, auto)."""

    _attr_should_poll = False
    _attr_icon = "mdi:serial-port"

    def __init__(
        self,
        hass,
        dev: SmartVideoHub,
        entity_prefix: str,
        port_number: int,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the serial port direction sensor."""
        self.hass = hass
        self._dev = dev
        self._port_number = port_number
        label = dev.serial_ports.get(port_number, f"Serial {port_number}")

        self._attr_unique_id = f"{entity_prefix}_serial_dir_{port_number}"
        self._attr_name = f"{label} Direction"
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{entity_prefix} serial {port_number} direction", hass=hass
        )
        self._attr_device_info = device_info
        self._attr_native_value = dev.serial_port_directions.get(port_number, "auto")
        self._attr_options = ["control", "slave", "auto"]
        dev.add_update_callback(self._handle_update)

    @property
    def available(self) -> bool:
        """Return whether the device is connected."""
        return self._dev.connected

    @callback
    def _handle_update(self, output_id: int | bool = 0) -> None:
        """Update when data received."""
        self._attr_native_value = self._dev.serial_port_directions.get(
            self._port_number, "auto"
        )
        self.async_write_ha_state()


class SerialPortLockSensor(SensorEntity):
    """Sensor for serial port lock status."""

    _attr_should_poll = False
    _attr_icon = "mdi:lock"

    def __init__(
        self,
        hass,
        dev: SmartVideoHub,
        entity_prefix: str,
        port_number: int,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the serial port lock sensor."""
        self.hass = hass
        self._dev = dev
        self._port_number = port_number
        label = dev.serial_ports.get(port_number, f"Serial {port_number}")

        self._attr_unique_id = f"{entity_prefix}_serial_lock_{port_number}"
        self._attr_name = f"{label} Lock Status"
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{entity_prefix} serial {port_number} lock", hass=hass
        )
        self._attr_device_info = device_info
        self._attr_native_value = dev.serial_port_locks.get(port_number, "U")
        dev.add_update_callback(self._handle_update)

    @property
    def available(self) -> bool:
        """Return whether the device is connected."""
        return self._dev.connected

    @callback
    def _handle_update(self, output_id: int | bool = 0) -> None:
        """Update when data received."""
        self._attr_native_value = self._dev.serial_port_locks.get(
            self._port_number, "U"
        )
        self.async_write_ha_state()