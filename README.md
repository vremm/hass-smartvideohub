# Smart Video Hub — Home Assistant Integration

A Home Assistant custom integration for Blackmagic Design Smart Videohub devices (including the 12x12, 20x20, 40x40, and other models), Web Presenter, and Teranex Mini devices.

## Features

### Videohub Devices
- **Media Player entities** for each output port — select which input is routed to each output
- **Lock entities** for each output port — lock/unlock outputs, force-unlock ports locked by other clients
- **Text entities** for renaming input and output port labels directly from Home Assistant
- **Reboot button** to restart the device
- Push-based updates — the integration listens for real-time changes from the Videohub, so any changes made on the device itself or by other clients are instantly reflected in Home Assistant

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
   - Paste the GitHub URL of this repo
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

## Usage with Universal Media Player

The output media_player entities work well with the [Universal Media Player](https://www.home-assistant.io/integrations/universal/) integration. You can:

1. Create a universal media player for a TV/projector
2. Point its `source` and `source_select` at a Videohub output entity
3. Use automations to power on the TV and select the input via the Videohub

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
- Monitoring output routing
- Video output locks (lock, unlock, force-unlock)
- Serial port labels, routing, locks, and directions
- Video input/output hardware status
- Streaming settings and state (Web Presenter)
- Teranex Mini device settings
- PING keepalive every 120 seconds
- Automatic reconnection with 30-second backoff

## Credits

Based on the original work by [jnimmo](https://github.com/jnimmo/hass-smartvideohub) with contributions from [magicbear](https://github.com/magicbear).

## License

MIT