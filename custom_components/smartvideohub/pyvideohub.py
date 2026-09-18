"""Python library for interfacing with Blackmagic Smart Video Hub over TCP.

Implements the Blackmagic Videohub Ethernet Protocol v2.3.
Connects to TCP port 9990 on the Videohub device, parses status blocks,
and provides methods for sending commands (routing, labels, locks, etc.).
"""

from __future__ import annotations

import asyncio
import collections
import logging
import re

_LOGGER = logging.getLogger(__name__)

# Re-export model constants for backward compat
MODEL_VIDEOHUB = "VideoHub"
MODEL_STREAMING = "Streaming"
MODEL_TERANEX = "TERANEX"

SERVER_RECONNECT_DELAY = 30
KEEPALIVE_INTERVAL = 120


class SmartVideoHub(asyncio.Protocol):
    """Async TCP protocol client for Blackmagic Videohub devices."""

    def __init__(self, host: str, port: int, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Initialize the Videohub client."""
        self._cmdServer = host
        self._cmdServerPort = port
        self._transport: asyncio.Transport | None = None
        self._updateCallbacks: list = []
        self._errorMessage: str | None = None
        self._connected = False
        self._connecting = False
        self._stopped = False
        self.initialised = asyncio.Event()

        self.inputs: dict[int, str] = {}
        self.filtered_inputs: dict[int, str] = {}
        self.outputs: dict[int, dict] = collections.defaultdict(dict)
        self.output_locks: dict[int, str] = {}
        self.monitoring_outputs: dict[int, dict] = collections.defaultdict(dict)
        self.serial_ports: dict[int, str] = {}
        self.serial_port_routing: dict[int, int] = {}
        self.serial_port_locks: dict[int, str] = {}
        self.serial_port_directions: dict[int, str] = {}
        self.video_input_status: dict[int, str] = {}
        self.video_output_status: dict[int, str] = {}
        self.attrs: dict[str, str] = {}
        self.stream_set: dict[str, str] = {}
        self.stream_state: dict[str, str] = {}
        self.teranex_set: dict[str, str] = {}
        self.audio_settings: dict[str, str] = {}
        self.version_info: dict[str, str] = {}
        self.network_info: dict[str, str] = {}
        self.network_interfaces: dict[int, dict[str, str]] = {}
        self.stream_xml_files: str = ""
        self.model: str | None = None
        self.name: str = ""

        # Buffer for handling partial messages across TCP segments
        self._buffer = ""

        if loop:
            _LOGGER.debug("Latching onto an existing event loop")
            self._eventLoop = loop
        else:
            try:
                self._eventLoop = asyncio.get_event_loop()
            except RuntimeError:
                self._eventLoop = asyncio.new_event_loop()

    # ------------------------------------------------------------------
    # asyncio.Protocol callbacks
    # ------------------------------------------------------------------

    def connection_made(self, transport: asyncio.Transport) -> None:
        """asyncio callback for a successful connection."""
        _LOGGER.debug("Connected to Black Magic Smart Video Hub API")
        self._transport = transport
        self._connected = True
        self._connecting = False

    def data_received(self, data: bytes) -> None:
        """asyncio callback when data is received on the socket.

        Handles buffering of partial TCP segments and parses complete blocks.
        Blocks are terminated by a blank line (double newline).
        """
        if not data:
            return

        # Append to buffer and split on block boundaries
        self._buffer += data.decode("utf-8", errors="replace")

        # Split into complete blocks (terminated by \n\n or \r\n\r\n)
        # We keep the last partial block in the buffer
        while True:
            # Find the end of a block (blank line)
            # Protocol uses \n for line endings, blocks separated by blank lines
            block_end = self._find_block_end(self._buffer)
            if block_end is None:
                break

            block_str = self._buffer[:block_end]
            # Skip the blank line separator
            self._buffer = self._buffer[block_end:].lstrip("\n\r")

            if block_str.strip():
                self._parse_block(block_str)

    @staticmethod
    def _find_block_end(buffer: str) -> int | None:
        """Find the end index of the first complete block in the buffer.

        Blocks are terminated by a blank line (\n\n or \r\n\r\n).
        Returns the index past the block content (before the blank line),
        or None if no complete block is found.
        """
        # Look for double newline (the blank line terminator)
        for pattern in ["\n\n", "\r\n\r\n"]:
            idx = buffer.find(pattern)
            if idx != -1:
                return idx
        return None

    def _parse_block(self, block_str: str) -> None:
        """Parse a single complete protocol block."""
        lines = block_str.splitlines()
        if not lines:
            return

        first_line = lines[0]
        # Block headers end with a colon
        header_match = re.match(r"^([A-Z ]+):[\r]?$", first_line.strip())
        if not header_match:
            return

        current_block = header_match.group(1).strip()
        _LOGGER.debug("Parsing block: %s (%d lines)", current_block, len(lines) - 1)

        # Process each data line in the block
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            self._parse_block_line(current_block, line)

        # Handle post-block logic
        if current_block == "END PRELUDE":
            self.initialised.set()
            self._send_update_callback(output_id=0)
        elif current_block == "VIDEO OUTPUT ROUTING":
            if self.initialised.is_set():
                # Notify all outputs that routing may have changed
                self._send_update_callback(output_id=-1)
        elif current_block in (
            "OUTPUT LABELS",
            "INPUT LABELS",
            "VIDEO OUTPUT LOCKS",
            "STREAM SETTINGS",
            "STREAM STATE",
            "TERANEX MINI DEVICE",
            "VIDEO OUTPUT",
        ):
            if self.initialised.is_set():
                self._send_update_callback(output_id=0)

    def _parse_block_line(self, block: str, line: str) -> None:
        """Parse a single line within a protocol block."""
        if block == "INPUT LABELS":
            parts = line.split(" ", 1)
            if len(parts) == 2:
                input_number = int(parts[0]) + 1
                input_label = parts[1].strip()
                self.inputs.setdefault(input_number, input_label)
                if input_label != "Input " + str(input_number):
                    self.filtered_inputs.setdefault(input_number, input_label)
                _LOGGER.debug("Named input %i as %s", input_number, input_label)

        elif block == "OUTPUT LABELS":
            parts = line.split(" ", 1)
            if len(parts) == 2:
                output_number = int(parts[0]) + 1
                output_label = parts[1].strip()
                self.outputs[output_number]["name"] = output_label
                self.outputs[output_number]["output"] = output_number
                _LOGGER.debug("Named output %i as %s", output_number, output_label)

        elif block == "VIDEO OUTPUT ROUTING":
            parts = line.split(" ", 1)
            if len(parts) == 2:
                output_id = int(parts[0]) + 1
                input_id = int(parts[1]) + 1
                self.outputs[output_id]["input"] = input_id
                self.outputs[output_id]["input_name"] = self.get_input_name(input_id)
                _LOGGER.debug("Output %i is now displaying input %i", output_id, input_id)

        elif block == "MONITORING OUTPUT LABELS":
            parts = line.split(" ", 1)
            if len(parts) == 2:
                mon_number = int(parts[0]) + 1
                mon_label = parts[1].strip()
                self.monitoring_outputs[mon_number]["name"] = mon_label
                self.monitoring_outputs[mon_number]["output"] = mon_number

        elif block == "VIDEO MONITORING OUTPUT ROUTING":
            parts = line.split(" ", 1)
            if len(parts) == 2:
                mon_id = int(parts[0]) + 1
                input_id = int(parts[1]) + 1
                self.monitoring_outputs[mon_id]["input"] = input_id
                self.monitoring_outputs[mon_id]["input_name"] = self.get_input_name(input_id)

        elif block == "SERIAL PORT LABELS":
            parts = line.split(" ", 1)
            if len(parts) == 2:
                port_number = int(parts[0]) + 1
                self.serial_ports[port_number] = parts[1].strip()

        elif block == "SERIAL PORT ROUTING":
            parts = line.split(" ", 1)
            if len(parts) == 2:
                port_number = int(parts[0]) + 1
                self.serial_port_routing[port_number] = int(parts[1]) + 1

        elif block == "SERIAL PORT LOCKS":
            parts = line.split(" ", 1)
            if len(parts) == 2:
                port_number = int(parts[0]) + 1
                self.serial_port_locks[port_number] = parts[1].strip()

        elif block == "SERIAL PORT DIRECTIONS":
            parts = line.split(" ", 1)
            if len(parts) == 2:
                port_number = int(parts[0]) + 1
                self.serial_port_directions[port_number] = parts[1].strip()

        elif block == "VIDEO OUTPUT LOCKS":
            parts = line.split(" ", 1)
            if len(parts) == 2:
                output_number = int(parts[0]) + 1
                self.output_locks[output_number] = parts[1].strip()
                _LOGGER.debug("Output %i lock status: %s", output_number, parts[1].strip())

        elif block == "VIDEO INPUT STATUS":
            parts = line.split(" ", 1)
            if len(parts) == 2:
                input_number = int(parts[0]) + 1
                self.video_input_status[input_number] = parts[1].strip()

        elif block == "VIDEO OUTPUT STATUS":
            parts = line.split(" ", 1)
            if len(parts) == 2:
                output_number = int(parts[0]) + 1
                self.video_output_status[output_number] = parts[1].strip()

        elif block == "VIDEOHUB DEVICE":
            self.model = MODEL_VIDEOHUB
            line_conf = line.split(": ", 1)
            if len(line_conf) == 2 and line_conf[1].strip() != "":
                self.attrs[line_conf[0]] = line_conf[1].strip()
                if line_conf[0] == "Friendly Name":
                    self.name = line_conf[1].strip()

        elif block == "IDENTITY":
            line_conf = line.split(": ", 1)
            if len(line_conf) == 2 and line_conf[1].strip() != "":
                self.attrs[line_conf[0]] = line_conf[1].strip()
                if line_conf[0] == "Model":
                    if line_conf[1].startswith("Blackmagic Web Presenter"):
                        self.model = MODEL_STREAMING
                elif line_conf[0] == "Label":
                    self.name = line_conf[1].strip()

        elif block == "STREAM SETTINGS":
            line_conf = line.split(": ", 1)
            if len(line_conf) == 2 and line_conf[1].strip() != "":
                self.stream_set[line_conf[0]] = line_conf[1].strip()

        elif block == "STREAM STATE":
            line_conf = line.split(": ", 1)
            if len(line_conf) == 2 and line_conf[1].strip() != "":
                self.stream_state[line_conf[0]] = line_conf[1].strip()

        elif block == "AUDIO SETTINGS":
            line_conf = line.split(": ", 1)
            if len(line_conf) == 2 and line_conf[1].strip() != "":
                self.audio_settings[line_conf[0]] = line_conf[1].strip()

        elif block == "VERSION":
            line_conf = line.split(": ", 1)
            if len(line_conf) == 2 and line_conf[1].strip() != "":
                self.version_info[line_conf[0]] = line_conf[1].strip()

        elif block == "NETWORK":
            line_conf = line.split(": ", 1)
            if len(line_conf) == 2 and line_conf[1].strip() != "":
                self.network_info[line_conf[0]] = line_conf[1].strip()

        elif block.startswith("NETWORK INTERFACE"):
            # Network interface blocks have a number in the header
            try:
                iface_num = int(block.split()[-1])
            except (ValueError, IndexError):
                iface_num = 0
            line_conf = line.split(": ", 1)
            if len(line_conf) == 2 and line_conf[1].strip() != "":
                self.network_interfaces.setdefault(iface_num, {})[line_conf[0]] = line_conf[1].strip()

        elif block == "STREAM XML":
            line_conf = line.split(": ", 1)
            if len(line_conf) == 2:
                if line_conf[0] == "Files":
                    self.stream_xml_files = line_conf[1].strip()

        elif block == "TERANEX MINI DEVICE":
            self.model = MODEL_TERANEX
            line_conf = line.split(": ", 1)
            if len(line_conf) == 2 and line_conf[1].strip() != "":
                if line_conf[0] == "Unique ID":
                    self.attrs[line_conf[0]] = line_conf[1].strip()
                elif line_conf[0] == "Label":
                    self.name = line_conf[1].strip()
                self.teranex_set[line_conf[0]] = line_conf[1].strip()

        elif block == "VIDEO OUTPUT":
            line_conf = line.split(": ", 1)
            if len(line_conf) == 2 and line_conf[1].strip() != "":
                self.teranex_set[line_conf[0]] = line_conf[1].strip()

    def connection_lost(self, exc: Exception | None) -> None:
        """asyncio callback for a lost TCP connection."""
        self._connected = False
        self._buffer = ""
        self.initialised.set()  # Unblock anyone waiting
        self._send_update_callback()
        if exc:
            _LOGGER.error("Connection to the server lost: %s", exc)
        else:
            _LOGGER.error("Connection to the server lost")
        if not self._stopped:
            _LOGGER.info("Attempting reconnection in %i seconds", SERVER_RECONNECT_DELAY)
            self._eventLoop.call_later(SERVER_RECONNECT_DELAY, self._schedule_reconnect)

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if not self._stopped:
            self.connect()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> asyncio.Future:
        """Initiate a TCP connection to the Videohub."""
        _LOGGER.info(
            "Connecting to Smart Video Hub at %s:%s",
            self._cmdServer,
            self._cmdServerPort,
        )
        self._connecting = True
        coro = self._eventLoop.create_connection(
            lambda: self, self._cmdServer, self._cmdServerPort
        )
        return asyncio.ensure_future(coro)

    def start(self) -> None:
        """Public method for initiating connectivity with the Videohub."""
        self._stopped = False
        self.connect()
        _LOGGER.info("Started Videohub client")

    def stop(self) -> None:
        """Public method for shutting down connectivity with the Videohub."""
        self._connected = False
        self._stopped = True
        if self._transport:
            self._transport.close()

    # ------------------------------------------------------------------
    # Command methods — send commands to the Videohub
    # ------------------------------------------------------------------

    def _send_command(self, block_header: str, lines: list[str] | None = None) -> None:
        """Send a command block to the Videohub.

        All commands follow the same format:
        BLOCK HEADER:\\n
        data line 1\\n
        data line 2\\n
        \\n  (blank line terminator)
        """
        if not self._connected or not self._transport:
            _LOGGER.warning("Cannot send command: not connected")
            return

        command = block_header + ":\n"
        if lines:
            for line in lines:
                command += line + "\n"
        command += "\n"
        self._transport.write(command.encode("ascii"))

    def set_input(self, output_number: int, input_number: int) -> None:
        """Route an input to an output. Uses 1-based indexing internally."""
        if (
            output_number <= len(self.outputs)
            and input_number <= len(self.inputs)
            and self._connected
        ):
            _LOGGER.debug("Setting output %i to input %i", output_number, input_number)
            self._send_command(
                "VIDEO OUTPUT ROUTING",
                [f"{output_number - 1} {input_number - 1}"],
            )

    def set_input_by_name(self, output_number: int, input_name: str) -> bool:
        """Route an input (by name) to an output."""
        input_list = self.get_input_list()
        if input_name in input_list and self._connected:
            self.set_input(output_number, input_list.index(input_name) + 1)
            return True
        _LOGGER.debug(
            "Input %s was not found in the list of inputs or the server was disconnected",
            input_name,
        )
        return False

    def set_input_label(self, input_number: int, label: str) -> None:
        """Rename an input port label. Uses 1-based indexing internally."""
        self._send_command(
            "INPUT LABELS",
            [f"{input_number - 1} {label}"],
        )

    def set_output_label(self, output_number: int, label: str) -> None:
        """Rename an output port label. Uses 1-based indexing internally."""
        self._send_command(
            "OUTPUT LABELS",
            [f"{output_number - 1} {label}"],
        )

    def lock_output(self, output_number: int) -> None:
        """Lock an output port (owned by this client)."""
        self._send_command(
            "VIDEO OUTPUT LOCKS",
            [f"{output_number - 1} O"],
        )

    def unlock_output(self, output_number: int) -> None:
        """Unlock an output port."""
        self._send_command(
            "VIDEO OUTPUT LOCKS",
            [f"{output_number - 1} U"],
        )

    def force_unlock_output(self, output_number: int) -> None:
        """Force unlock an output port locked by another client."""
        self._send_command(
            "VIDEO OUTPUT LOCKS",
            [f"{output_number - 1} F"],
        )

    def set_serial_port_direction(self, port_number: int, direction: str) -> None:
        """Set serial port direction: 'control', 'slave', or 'auto'."""
        self._send_command(
            "SERIAL PORT DIRECTIONS",
            [f"{port_number - 1} {direction}"],
        )

    def set_serial_port_routing(self, port_number: int, input_number: int) -> None:
        """Route a serial port to an input."""
        self._send_command(
            "SERIAL PORT ROUTING",
            [f"{port_number - 1} {input_number - 1}"],
        )

    def request_status_dump(self, block_header: str) -> None:
        """Request the Videohub resend a complete status block."""
        self._send_command(block_header)

    def ping(self) -> None:
        """Send a PING command to check connection health."""
        self._send_command("PING")

    # ------------------------------------------------------------------
    # Streaming/Teranex commands (for Web Presenter / Teranex devices)
    # ------------------------------------------------------------------

    def set_video_mode(self, mode: str) -> None:
        """Set the video mode for streaming."""
        self._send_command("STREAM SETTINGS", [f"Video Mode: {mode}"])

    def set_stream_platform(self, platform: str) -> None:
        """Set the streaming platform."""
        self._send_command("STREAM SETTINGS", [f"Current Platform: {platform}"])

    def set_stream_key(self, key: str) -> None:
        """Set the stream key."""
        self._send_command("STREAM SETTINGS", [f"Stream Key: {key}"])

    def set_quality_level(self, level: str) -> None:
        """Set the quality level for streaming."""
        self._send_command("STREAM SETTINGS", [f"Current Quality Level: {level}"])

    def set_stream_server(self, server: str) -> None:
        """Set the streaming server (Web Presenter)."""
        self._send_command("STREAM SETTINGS", [f"Current Server: {server}"])

    def set_stream_url(self, url: str) -> None:
        """Set a custom streaming URL (Web Presenter, if Customizable URL is true)."""
        self._send_command("STREAM SETTINGS", [f"Current URL: {url}"])

    def set_stream_password(self, password: str) -> None:
        """Set the SRT stream password (Web Presenter)."""
        self._send_command("STREAM SETTINGS", [f"Password: {password}"])

    def set_audio_source(self, source: str) -> None:
        """Set the monitor output audio source (Web Presenter).

        Valid values: Auto, SDI In, Remote Source
        """
        self._send_command("AUDIO SETTINGS", [f"Current Monitor Out Audio Source: {source}"])

    def set_device_label(self, label: str) -> None:
        """Set the device label (Web Presenter / Teranex)."""
        self._send_command("IDENTITY", [f"Label: {label}"])

    def remove_stream_xml(self, filename: str) -> None:
        """Remove a custom stream XML file from the Web Presenter."""
        self._send_command("STREAM XML", [f"Action: Remove", f"Files: {filename}"])

    def remove_all_stream_xml(self) -> None:
        """Remove all custom stream XML files from the Web Presenter."""
        self._send_command("STREAM XML", ["Action: Remove All"])

    def set_lut(self, lut_id: int | str) -> None:
        """Set the LUT for Teranex devices."""
        if isinstance(lut_id, int):
            if lut_id == 1:
                lut = "Lut 0"
            elif lut_id == 2:
                lut = "Lut 1"
            else:
                lut = "none"
        else:
            lut = lut_id
        self._send_command("VIDEO OUTPUT", [f"Lut on loop: true", f"Lut selection: {lut}"])

    def set_stream_state(self, start: bool) -> None:
        """Start or stop streaming."""
        self._send_command("STREAM STATE", [f"Action: {'Start' if start else 'Stop'}"])

    def reboot(self) -> None:
        """Reboot the device."""
        self._send_command("SHUTDOWN", ["Action: Reboot"])

    # ------------------------------------------------------------------
    # Query methods — read state from the client's cached data
    # ------------------------------------------------------------------

    def get_input_list(self, filter_inputs: bool = False) -> list[str]:
        """Return a list of input names."""
        if filter_inputs:
            return list(self.filtered_inputs.values())
        return list(self.inputs.values())

    def get_inputs(self, filter_inputs: bool = False) -> dict[int, str]:
        """Return the inputs dict."""
        if filter_inputs:
            return self.filtered_inputs
        return self.inputs

    def get_input_name(self, input_number: int) -> str:
        """Return the name of an input by number."""
        if input_number in self.inputs:
            return self.inputs[input_number]
        return f"Input {input_number}"

    def get_selected_input(self, output_number: int) -> int | None:
        """Return the input number currently routed to an output."""
        if output_number in self.outputs:
            return self.outputs[output_number].get("input")
        return None

    def get_outputs(self) -> dict[int, dict]:
        """Return all outputs."""
        return self.outputs

    def get_output_lock(self, output_number: int) -> str:
        """Return the lock status of an output: 'U', 'O', or 'L'."""
        return self.output_locks.get(output_number, "U")

    def get_monitoring_outputs(self) -> dict[int, dict]:
        """Return all monitoring outputs."""
        return self.monitoring_outputs

    def get_serial_ports(self) -> dict[int, str]:
        """Return all serial ports."""
        return self.serial_ports

    def get_video_input_status(self) -> dict[int, str]:
        """Return hardware status of video inputs."""
        return self.video_input_status

    def get_video_output_status(self) -> dict[int, str]:
        """Return hardware status of video outputs."""
        return self.video_output_status

    def get_audio_settings(self) -> dict[str, str]:
        """Return audio settings (Web Presenter)."""
        return self.audio_settings

    def get_version_info(self) -> dict[str, str]:
        """Return hardware/software version info (Web Presenter)."""
        return self.version_info

    def get_network_info(self) -> dict[str, str]:
        """Return network configuration (Web Presenter)."""
        return self.network_info

    def get_network_interfaces(self) -> dict[int, dict[str, str]]:
        """Return network interface details (Web Presenter)."""
        return self.network_interfaces

    def get_stream_state(self) -> dict[str, str]:
        """Return the full stream state including bitrate, duration, etc."""
        return self.stream_state

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _send_update_callback(self, output_id: int | bool = False) -> None:
        """Internal method to notify all update callback subscribers."""
        if not self._updateCallbacks:
            _LOGGER.debug("Update callback has not been set by client")
        for callback in self._updateCallbacks:
            callback(output_id=output_id)

    def add_update_callback(self, method) -> None:
        """Public method to add a callback subscriber."""
        self._updateCallbacks.append(method)
        return lambda: self.remove_update_callback(method)

    def remove_update_callback(self, method) -> None:
        """Remove a previously registered update callback."""
        if method in self._updateCallbacks:
            self._updateCallbacks.remove(method)

    # ------------------------------------------------------------------
    # Keepalive
    # ------------------------------------------------------------------

    async def keep_alive(self) -> None:
        """Send a periodic PING to keep the connection alive."""
        while True:
            if self._connected:
                _LOGGER.debug("Sending keepalive PING to the server")
                self.ping()
            await asyncio.sleep(KEEPALIVE_INTERVAL)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def error_message(self) -> str | None:
        """Returns the last error message, or None if there were no errors."""
        return self._errorMessage

    @property
    def is_initialised(self) -> bool:
        """Return whether the client has received the initial status dump."""
        return self.initialised.is_set()

    @property
    def connected(self) -> bool:
        """Return whether the client is connected."""
        return self._connected