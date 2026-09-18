# Smart Video Hub — Home Assistant Integration

A Home Assistant custom integration for Blackmagic Design Smart Videohub devices (including the 12x12, 20x20, 40x40, and other models), Web Presenter, and Teranex Mini devices.

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

### Custom Services

| Service | Description |
|---------|-------------|
| `smartvideohub.route_output` | Route a specific output to a specific input (by number or name) |
| `smartvideohub.route_all_outputs` | Route all outputs to the same input |
| `smartvideohub.swap_outputs` | Swap the inputs of two outputs |
| `smartvideohub.route_by_name` | Route by human-readable output and input label names |

### Automation Blueprint

A blueprint is included at `blueprints/select_input_for_display.yaml` — it automatically routes a Videohub output to a selected input when a display (TV/projector) turns on, and optionally routes back to a default when it turns off.

### Web Presenter (Streaming) Devices
- **Select entities** for streaming platform, video mode, and quality level
- **Switch entity** to start/stop streaming
- **Text entity** for the stream key
- **Reboot button**

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

The integration is configured via the UI (config flow). You'll need:

| Field | Description | Default |
|-------|-------------|---------|
| Host | IP address of your Videohub device | (required) |
| Port | TCP port (protocol default is 9990) | 9990 |
| Hide default inputs | Hide inputs that still have their default name (e.g. "Input 1") | false |

## How It Works

The integration connects to your Videohub over TCP port 9990 using the [Blackmagic Videohub Ethernet Protocol v2.3](https://documents.blackmagicdesign.com/DeveloperManuals/VideohubEthernetProtocol.pdf). Upon connection, the device sends a complete status dump. After that, the device pushes incremental updates whenever any route, label, or lock changes — whether from Home Assistant, the device's own front panel, or other clients.

This means the integration is **push-based** (`local_push` IoT class) — no polling is required. Changes made on the device front panel appear in Home Assistant instantly.

## Entity Overview for a 12x12 Videohub

For a Blackmagic Smart Videohub 12x12 (12 inputs, 12 outputs), you'll get:

| Platform | Count | What |
|----------|-------|------|
| media_player | 12 | One per output, each with a source dropdown to select any of 12 inputs |
| lock | 12 | One per output — lock/unlock/force-unlock |
| text | 24 | One per input label + one per output label (rename from HA) |
| sensor | 25+ | Connection status + 12 input hardware status + 12 output hardware status |
| button | 1 | Reboot |
| **Total** | **74+** | Entities created |

If your device has serial ports or monitoring outputs, additional entities are created for those as well.

## Usage Examples

### Route output 1 to input 3 (service call)
```yaml
service: smartvideohub.route_output
data:
  output: 1
  input: 3
```

### Route all outputs to input named "Camera 1"
```yaml
service: smartvideohub.route_all_outputs
data:
  input: "Camera 1"
```

### Swap outputs 1 and 2
```yaml
service: smartvideohub.swap_outputs
data:
  output_1: 1
  output_2: 2
```

### Route by name — "Projector" output to "PC" input
```yaml
service: smartvideohub.route_by_name
data:
  output_name: "Projector"
  input_name: "PC"
```

### Use with Universal Media Player
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

- Blackmagic Smart Videohub (12x12, 20x20, 40x40, etc.)
- Blackmagic Videohub 12G series
- Universal Videohub
- Blackmagic Web Presenter (streaming features)
- Blackmagic Teranex Mini (LUT selection)

## Protocol Details

The Blackmagic Videohub Ethernet Protocol is a text-based protocol on TCP port 9990. The integration supports:

- Device information and identity
- Input/output label reading and writing
- Video output routing (reading and writing)
- Monitoring output labels and routing
- Video output locks (lock, unlock, force-unlock)
- Serial port labels, routing, locks, and directions
- Video input/output hardware status (BNC/Optical/None)
- Streaming settings and state (Web Presenter)
- Teranex Mini device settings
- PING keepalive every 120 seconds
- Automatic reconnection with 30-second backoff
- Proper TCP buffer handling for partial messages

## Diagnostics

Go to Settings → Devices & Services → Smart Video Hub → ⋮ → Download diagnostics to get a full JSON dump of the device state for troubleshooting.

## Credits

Based on the original work by [jnimmo](https://github.com/jnimmo/hass-smartvideohub) with contributions from [magicbear](https://github.com/magicbear).

## License

MIT