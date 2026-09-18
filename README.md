# Smart Video Hub — Home Assistant Integration

A Home Assistant custom integration for Blackmagic Design Smart Videohub devices (including the 12x12, 20x20, 40x40, and other models), Blackmagic Web Presenter HD/4K, and Teranex Mini devices.

## Features

### Videohub Devices
- **Media Player entities** for each output port — select which input is routed to each output
- **Media Player entities** for each monitoring output (if your device has monitoring outputs)
- **Lock entities** for each output port — lock/unlock outputs, force-unlock ports locked by other clients
- **Text entities** for renaming input and output port labels directly from Home Assistant
- **Sensor entities** for connection status, video input/output hardware status (BNC/Optical/None), serial port direction, and serial port lock status
- **Select entities** for serial port direction (control/slave/auto) and serial port routing
- **Reboot button** to restart the device
- Push-based updates — the integration listens for real-time changes from the Videohub, so any changes made on the device itself or by other clients are instantly reflected in Home Assistant

### Web Presenter (Streaming) Devices
- **Select entities** for:
  - Streaming platform (YouTube, Facebook, Twitch, X, Instagram, Twitch, Vimeo, and more)
  - Stream server (Primary / Secondary — depends on selected platform)
  - Video mode (Auto, 1080p23.98–60, 720p25–60, etc.)
  - Quality level (Streaming High / Medium / Low, etc.)
  - Monitor output audio source (Auto / SDI In / Remote Source)
- **Switch entity** to start/stop streaming, with real-time attributes:
  - Stream status (Idle / Connecting / Streaming / Interrupted)
  - Current bitrate
  - Stream duration
  - Cache usage percentage
- **Text entities** for:
  - Stream key
  - Custom stream URL (when the platform supports customizable URLs)
  - SRT stream password (masked input for encrypted streams)
  - Device label (rename the Web Presenter from HA)
- **Reboot button**
- Push-based updates — stream status changes, bitrate, and state updates are pushed from the device in real time

### Custom Services

| Service | Description |
|---------|-------------|
| `smartvideohub.route_output` | Route a specific output to a specific input (by number or name) |
| `smartvideohub.route_all_outputs` | Route all outputs to the same input |
| `smartvideohub.swap_outputs` | Swap the inputs of two outputs |
| `smartvideohub.route_by_name` | Route by human-readable output and input label names |

### Automation Blueprint

A blueprint is included at `blueprints/select_input_for_display.yaml` — it automatically routes a Videohub output to a selected input when a display (TV/projector) turns on, and optionally routes back to a default when it turns off.

### Teranex Mini Devices
- **Select entity** for LUT selection
- **Reboot button**

## Installation

### Via HACS (recommended)

1. Add this repository as a custom repository in HACS:
   - Go to HACS → Integrations → ⋮ → Custom repositories
   - Paste `https://github.com/vremm/hass-smartvideohub`
   - Category: Integration
2. Click "Install" on the Smart Video Hub card
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration
5. Search for "Smart Video Hub" and follow the config flow

### Manual Installation

1. Copy the `custom_components/smartvideohub/` folder to your Home Assistant `custom_components/` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Smart Video Hub"

## Configuration

The integration is configured via the UI (config flow). You can add multiple devices — one for each Videohub or Web Presenter on your network.

| Field | Description | Default |
|-------|-------------|---------|
| Host | IP address of your device | (required) |
| Port | TCP port — **9990** for Videohub, **9977** for Web Presenter | 9990 |
| Hide default inputs | Hide inputs that still have their default name (e.g. "Input 1") | false |

### Adding a Web Presenter

The Web Presenter uses a **different TCP port (9977)** and a different protocol (v1.2) than the Videohub (port 9990, protocol v2.3). The integration auto-detects which device type it is from the `IDENTITY` block and creates the appropriate entities:

- **Videohub** → media_player, lock, text, sensor, select, button entities for routing
- **Web Presenter** → select, switch, text, button, sensor entities for streaming
- **Teranex Mini** → select, button entities for LUT control

Just add a new integration instance for each device with the correct port.

## How It Works

The integration connects to your device over TCP using the Blackmagic Ethernet Protocol. Upon connection, the device sends a complete status dump. After that, the device pushes incremental updates whenever any route, label, lock, or stream setting changes — whether from Home Assistant, the device's own front panel, or other clients.

This means the integration is **push-based** (`local_push` IoT class) — no polling is required. Changes made on the device front panel appear in Home Assistant instantly.

## Entity Overview

### Smart Videohub 12x12 (12 inputs, 12 outputs)

| Platform | Count | What |
|----------|-------|------|
| media_player | 12 | One per output, each with a source dropdown to select any of 12 inputs |
| lock | 12 | One per output — lock/unlock/force-unlock |
| text | 24 | One per input label + one per output label (rename from HA) |
| sensor | 25+ | Connection status + 12 input hardware status + 12 output hardware status |
| button | 1 | Reboot |
| **Total** | **74+** | (more if device has serial ports or monitoring outputs) |

### Blackmagic Web Presenter HD

| Platform | Count | What |
|----------|-------|------|
| select | 5 | Stream Platform, Stream Server, Video Mode, Quality Level, Monitor Audio Source |
| switch | 1 | Streaming on/off (with bitrate, duration, cache_used attributes) |
| text | 4 | Stream Key, Stream URL, Stream Password (SRT), Device Label |
| button | 1 | Reboot |
| sensor | 1 | Connection status |
| **Total** | **12** | Entities |

## Usage Examples

### Videohub — Route output 1 to input 3 (service call)
```yaml
service: smartvideohub.route_output
data:
  output: 1
  input: 3
```

### Videohub — Route all outputs to input named "Camera 1"
```yaml
service: smartvideohub.route_all_outputs
data:
  input: "Camera 1"
```

### Videohub — Swap outputs 1 and 2
```yaml
service: smartvideohub.swap_outputs
data:
  output_1: 1
  output_2: 2
```

### Videohub — Route by name ("Projector" output to "PC" input)
```yaml
service: smartvideohub.route_by_name
data:
  output_name: "Projector"
  input_name: "PC"
```

### Web Presenter — Start streaming (automation)
```yaml
alias: "Start streaming"
trigger:
  - platform: state
    entity_id: switch.my_web_presenter_streaming
    to: "on"
action:
  - service: switch.turn_on
    target:
      entity_id: switch.my_web_presenter_streaming
```

### Web Presenter — Notify when stream is interrupted
```yaml
alias: "Stream interrupted notification"
trigger:
  - platform: state
    entity_id: switch.my_web_presenter_streaming
    attribute:
      status: "Interrupted"
action:
  - service: notify.mobile_app
    data:
      message: "Web Presenter stream has been interrupted!"
```

### Videohub — Use with Universal Media Player
```yaml
media_player:
  - platform: universal
    name: Living Room TV
    children:
      - media_player.videohub_output_1
    commands:
      select_source:
        service: media_player.select_source
        target:
          entity_id: media_player.videohub_output_1
        data:
          source: "{{ source }}"
```

## Supported Devices

| Device | Protocol | Port | Features |
|--------|----------|------|----------|
| Blackmagic Smart Videohub 12x12 | v2.3 | 9990 | Routing, locks, labels, serial ports, hardware status |
| Blackmagic Smart Videohub 20x20 | v2.3 | 9990 | Same as above |
| Blackmagic Smart Videohub 40x40 | v2.3 | 9990 | Same as above |
| Blackmagic Videohub 12G series | v2.3 | 9990 | Same as above |
| Universal Videohub | v2.3 | 9990 | Same as above + processing units, frame buffers |
| Blackmagic Web Presenter HD | v1.2 | 9977 | Streaming platform/server/quality, audio source, stream key/URL/password |
| Blackmagic Web Presenter 4K | v1.2 | 9977 | Same as Web Presenter HD |
| Blackmagic Teranex Mini | v1.2 | 9990 | LUT selection, reboot |

## Protocol Details

The integration implements two Blackmagic protocols:

### Videohub Ethernet Protocol v2.3 (TCP port 9990)
- Device information and identity
- Input/output label reading and writing
- Video output routing (reading and writing)
- Monitoring output labels and routing
- Video output locks (lock, unlock, force-unlock)
- Serial port labels, routing, locks, and directions
- Video input/output hardware status (BNC/Optical/None)
- PING keepalive every 120 seconds
- Automatic reconnection with 30-second backoff
- Proper TCP buffer handling for partial messages

### Web Presenter Ethernet Protocol v1.2 (TCP port 9977)
- Identity block (model, label, unique ID — read/write)
- Version block (hardware/software version info)
- Network blocks (interface config, IP addresses, gateway, DNS)
- Stream settings (platform, server, quality level, video mode, stream key, URL, password)
- Stream state (status, bitrate, duration, cache used — read)
- Audio settings (monitor out audio source — read/write)
- Stream XML (custom platform XML file management)
- PING keepalive every 120 seconds
- Automatic reconnection with 30-second backoff

## Diagnostics

Go to Settings → Devices & Services → Smart Video Hub → ⋮ → Download diagnostics to get a full JSON dump of the device state for troubleshooting. The diagnostic dump includes all parsed protocol data — inputs, outputs, routing, locks, stream settings, audio settings, version info, and network configuration.

## Credits

Based on the original work by [jnimmo](https://github.com/jnimmo/hass-smartvideohub) with contributions from [magicbear](https://github.com/magicbear).

## License

MIT