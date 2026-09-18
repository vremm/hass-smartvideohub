"""Services for the Smart Video Hub integration.

Provides custom services for batch routing operations:
  - smartvideohub.route_output — Route a single output to an input
  - smartvideohub.route_all_outputs — Route all outputs to the same input
  - smartvideohub.swap_outputs — Swap the inputs of two outputs
  - smartvideohub.route_by_name — Route by output and input names
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_ROUTE_OUTPUT,
    SERVICE_ROUTE_ALL_OUTPUTS,
    SERVICE_SWAP_OUTPUTS,
    SERVICE_ROUTE_BY_NAME,
)
from .pyvideohub import SmartVideoHub

_LOGGER = logging.getLogger(__name__)

# Service schemas
ROUTE_OUTPUT_SCHEMA = vol.Schema(
    {
        vol.Required("output"): vol.Any(int, str),  # output number or name
        vol.Required("input"): vol.Any(int, str),  # input number or name
    }
)

ROUTE_ALL_OUTPUTS_SCHEMA = vol.Schema(
    {
        vol.Required("input"): vol.Any(int, str),  # input number or name
    }
)

SWAP_OUTPUTS_SCHEMA = vol.Schema(
    {
        vol.Required("output_1"): vol.Any(int, str),
        vol.Required("output_2"): vol.Any(int, str),
    }
)

ROUTE_BY_NAME_SCHEMA = vol.Schema(
    {
        vol.Required("output_name"): str,
        vol.Required("input_name"): str,
    }
)


def _get_client(hass: HomeAssistant, call: ServiceCall) -> SmartVideoHub | None:
    """Get the Videohub client from the first available config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data:
        _LOGGER.warning("No Smart Video Hub integration found")
        return None
    # Use the first config entry's client
    for entry_data in domain_data.values():
        if "client" in entry_data:
            return entry_data["client"]
    _LOGGER.warning("No Smart Video Hub client found")
    return None


def _resolve_output_number(client: SmartVideoHub, output: int | str) -> int | None:
    """Resolve an output identifier (number or name) to a port number."""
    if isinstance(output, int):
        return output
    # Try to find by name
    for port_num, port_data in client.get_outputs().items():
        if port_data.get("name", "").lower() == output.lower():
            return port_num
    _LOGGER.warning("Output '%s' not found", output)
    return None


def _resolve_input_number(client: SmartVideoHub, inp: int | str) -> int | None:
    """Resolve an input identifier (number or name) to a port number."""
    if isinstance(inp, int):
        return inp
    # Try to find by name
    for port_num, port_name in client.get_inputs().items():
        if port_name.lower() == inp.lower():
            return port_num
    _LOGGER.warning("Input '%s' not found", inp)
    return None


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Smart Video Hub services."""

    @callback
    async def route_output(call: ServiceCall) -> None:
        """Route a single output to an input."""
        client = _get_client(hass, call)
        if not client:
            return
        output_num = _resolve_output_number(client, call.data["output"])
        input_num = _resolve_input_number(client, call.data["input"])
        if output_num and input_num:
            _LOGGER.info(
                "Service: routing output %i to input %i", output_num, input_num
            )
            client.set_input(output_num, input_num)

    @callback
    async def route_all_outputs(call: ServiceCall) -> None:
        """Route all outputs to the same input."""
        client = _get_client(hass, call)
        if not client:
            return
        input_num = _resolve_input_number(client, call.data["input"])
        if input_num:
            _LOGGER.info("Service: routing all outputs to input %i", input_num)
            for output_num in client.get_outputs():
                client.set_input(output_num, input_num)

    @callback
    async def swap_outputs(call: ServiceCall) -> None:
        """Swap the inputs of two outputs."""
        client = _get_client(hass, call)
        if not client:
            return
        out1 = _resolve_output_number(client, call.data["output_1"])
        out2 = _resolve_output_number(client, call.data["output_2"])
        if out1 and out2:
            # Get current routing
            src1 = client.get_selected_input(out1)
            src2 = client.get_selected_input(out2)
            if src1 and src2:
                _LOGGER.info(
                    "Service: swapping outputs %i<->%i (inputs %i<->%i)",
                    out1, out2, src1, src2,
                )
                client.set_input(out1, src2)
                client.set_input(out2, src1)

    @callback
    async def route_by_name(call: ServiceCall) -> None:
        """Route by human-readable output and input names."""
        client = _get_client(hass, call)
        if not client:
            return
        output_name = call.data["output_name"]
        input_name = call.data["input_name"]
        success = client.set_input_by_name(
            _resolve_output_number(client, output_name) or 0,
            input_name,
        )
        if not success:
            _LOGGER.warning(
                "Service route_by_name failed: output='%s' input='%s'",
                output_name, input_name,
            )

    # Register services
    hass.services.async_register(
        DOMAIN, SERVICE_ROUTE_OUTPUT, route_output, schema=ROUTE_OUTPUT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ROUTE_ALL_OUTPUTS, route_all_outputs, schema=ROUTE_ALL_OUTPUTS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SWAP_OUTPUTS, swap_outputs, schema=SWAP_OUTPUTS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ROUTE_BY_NAME, route_by_name, schema=ROUTE_BY_NAME_SCHEMA
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Smart Video Hub services."""
    for service in [
        SERVICE_ROUTE_OUTPUT,
        SERVICE_ROUTE_ALL_OUTPUTS,
        SERVICE_SWAP_OUTPUTS,
        SERVICE_ROUTE_BY_NAME,
    ]:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)