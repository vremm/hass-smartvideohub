"""Lock platform for the Smart Video Hub integration.

Each output port on the Videohub has a lock status:
  U = Unlocked
  O = Owned (locked by this client)
  L = Locked (by another client)

This platform exposes lock/unlock and force-unlock for each output.
"""

from __future__ import annotations

import logging

from homeassistant.components.lock import LockEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id

from .const import DOMAIN
from .pyvideohub import MODEL_VIDEOHUB, SmartVideoHub

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = "lock.{}"


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Smart Video Hub lock platform."""
    dev: SmartVideoHub = hass.data[DOMAIN][config_entry.entry_id]["client"]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=dev.name,
        manufacturer="Blackmagic Design",
        model=dev.model,
    )

    if dev.model == MODEL_VIDEOHUB:
        _LOGGER.info("Adding %i lock entities for outputs", len(dev.get_outputs()))
        async_add_entities(
            [
                SmartVideoHubOutputLock(
                    hass,
                    dev,
                    dev.attrs.get("Unique ID", dev.name),
                    output_number,
                    output,
                    device_info,
                )
                for output_number, output in dev.get_outputs().items()
            ],
            True,
        )


class SmartVideoHubOutputLock(LockEntity):
    """Representation of a Smart Video Hub output lock."""

    _attr_should_poll = False
    _attr_icon = "mdi:lock"

    def __init__(
        self,
        hass,
        smartvideohub: SmartVideoHub,
        entity_prefix: str,
        output_number: int,
        output: dict,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the lock entity."""
        self.hass = hass
        self._smartvideohub = smartvideohub
        self._output_id = output_number
        self._output_name = output.get("name", f"Output {output_number}")

        self._attr_unique_id = f"{entity_prefix}_lock_{self._output_id}"
        self._attr_name = f"{self._output_name} Lock"
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{entity_prefix} output {self._output_id} lock",
            hass=hass,
        )
        self._attr_device_info = device_info

    async def async_added_to_hass(self) -> None:
        """Subscribe to VideoHub updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._smartvideohub.add_update_callback(self._handle_update)
        )

    def _update_state(self) -> None:
        """Retrieve latest lock state from the client."""
        lock_status = self._smartvideohub.get_output_lock(self._output_id)
        # Locked = True if status is O (owned) or L (locked by other)
        self._attr_is_locked = lock_status in ("O", "L")
        self._lock_status = lock_status

    @property
    def available(self) -> bool:
        """Return whether the VideoHub connection is available."""
        return self._smartvideohub.connected

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        return {
            "lock_status": getattr(self, "_lock_status", "U"),
            "output_number": self._output_id,
            "output_name": self._output_name,
        }

    async def async_lock(self) -> None:
        """Lock the output port."""
        self._smartvideohub.lock_output(self._output_id)
        self._attr_is_locked = True
        self._lock_status = "O"
        self.async_write_ha_state()

    async def async_unlock(self) -> None:
        """Unlock the output port."""
        self._smartvideohub.unlock_output(self._output_id)
        self._attr_is_locked = False
        self._lock_status = "U"
        self.async_write_ha_state()

    async def async_open(self) -> None:
        """Force unlock the output port (open = force unlock)."""
        self._smartvideohub.force_unlock_output(self._output_id)
        self._attr_is_locked = False
        self._lock_status = "U"
        self.async_write_ha_state()

    @callback
    def _handle_update(self, output_id: int | bool = 0) -> None:
        """Called when data is received from the VideoHub."""
        if output_id not in (0, -1, self._output_id):
            return
        self._update_state()
        self.async_write_ha_state()