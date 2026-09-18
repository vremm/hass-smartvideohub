"""Shared entity classes for the Smart Video Hub integration."""

from __future__ import annotations

import logging

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN
from .pyvideohub import SmartVideoHub

_LOGGER = logging.getLogger(__name__)


class VideoHubEntity(Entity):
    """Base class for Smart Video Hub entities."""

    _attr_should_poll = False

    def __init__(
        self,
        hass,
        smartvideohub: SmartVideoHub,
        device_info: DeviceInfo,
        unique_id_suffix: str,
        translation_key: str | None = None,
    ) -> None:
        """Initialize the base entity."""
        self.hass = hass
        self._smartvideohub = smartvideohub
        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"{smartvideohub.attrs.get('Unique ID', smartvideohub.name)}_{unique_id_suffix}"
        )
        if translation_key:
            self._attr_translation_key = translation_key
            self._attr_has_entity_name = True