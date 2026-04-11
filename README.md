# Yandex Smart Home — Music Assistant Plugin Provider

[![Tests](https://github.com/trudenboy/ma-provider-yandex-smarthome/actions/workflows/test.yml/badge.svg)](https://github.com/trudenboy/ma-provider-yandex-smarthome/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Expose Music Assistant players to Yandex Alice via the [Yandex Smart Home API](https://yandex.ru/dev/dialogs/smart-home/).**

> «Алиса, включи музыку на Music Assistant»

## Overview

This plugin bridges [Music Assistant](https://github.com/music-assistant/server) and the Yandex Smart Home ecosystem. It registers MA players as smart home devices (type `media_device.receiver`), enabling voice control through Yandex Alice.

### Voice Commands

| Voice command | Action |
|---|---|
| «Алиса, включи музыку на \<имя\>» | Play / resume current queue |
| «Алиса, выключи \<имя\>» | Stop playback |
| «Алиса, сделай громче на \<имя\>» | Volume up (+10) |
| «Алиса, сделай тише на \<имя\>» | Volume down (-10) |
| «Алиса, поставь громкость 50 на \<имя\>» | Set volume to 50% |
| «Алиса, пауза на \<имя\>» | Pause |
| «Алиса, дальше на \<имя\>» | Next track |
| «Алиса, назад на \<имя\>» | Previous track |

## Architecture

```
Alice voice command
        │
        ▼
  Yandex Cloud
        │
        ▼ (Smart Home API callback)
┌───────────────────┐
│  This plugin      │──────► MA Player commands
│  (PluginProvider)  │       (play/pause/stop/vol/next/prev/source)
│                   │
│  Cloud relay      │◄────── MA Player state events
│  (yaha-cloud.ru)  │──────► Yandex state reports
└───────────────────┘
```

### Yandex Smart Home Capabilities

| Yandex Capability | MA Player Action | Notes |
|---|---|---|
| `on_off` | `play()` / `stop()` | "включи" resumes queue, "выключи" stops |
| `range(volume)` | `volume_set()` | Absolute and relative (±) |
| `toggle(mute)` | `volume_mute()` | Only if player supports VOLUME_MUTE |
| `toggle(pause)` | `play()` / `pause()` | |
| `range(channel)` | `next_track()` / `previous_track()` | Relative only: +1=next, -1=prev |
| `mode(input_source)` | `select_source()` | Maps source_list by index (max 10) |

> **Note:** Yandex Smart Home API does **not** support `play_media` for third-party devices.
> "Включи музыку" triggers play/resume on the current MA queue, not a specific track.

## Installation

> This provider is under active development.

### As a custom provider

1. Copy the `provider/` folder to your MA custom providers directory
2. Restart Music Assistant
3. Go to **Settings → Providers → Add → Yandex Smart Home**
4. Choose connection type:
   - **Cloud** — uses public Yaha Cloud skill (simplest setup)
   - **Cloud Plus** — uses a private skill (required if Yaha Cloud is already linked to Home Assistant on the same Yandex account)
   - **Direct** — Yandex calls your MA server directly via HTTPS (requires public URL, no relay needed)
5. **Cloud / Cloud Plus setup:**
   - Click **Register with cloud** — creates an instance on the yaha-cloud.ru relay
   - Copy the OTP code and enter it in the Yandex app: Devices → Add device → Smart Home → find the skill → enter OTP
   - (Cloud Plus only) Create a private skill in [Yandex.Dialogs](https://dialogs.yandex.ru/developer/smart-home) — the config flow provides all required values to copy
6. **Direct setup:**
   - Create a private skill in [Yandex.Dialogs](https://dialogs.yandex.ru/developer/smart-home), configure Backend URL / Account Linking from the config flow, publish, then link account in Yandex app

### Development

```bash
# Clone
git clone https://github.com/trudenboy/ma-provider-yandex-smarthome.git
cd ma-provider-yandex-smarthome

# Dev environment with Docker (recommended)
docker compose -f docker-compose.dev.yml up

# Or manual setup
pip install -e ".[test]"
pytest
```

## Configuration

| Parameter | Description |
|---|---|
| **Instance Name** | How this MA instance appears in Yandex Smart Home. Alice uses this name. |
| **Connection Type** | `cloud` (public skill), `cloud_plus` (private skill via relay), or `direct` (no relay, requires public URL). |
| **Exposed Players** | Select which MA players to expose to Alice. Empty = all players. |

Cloud Plus mode additionally requires **Skill ID** and **Skill OAuth Token** from Yandex.Dialogs.

Direct mode requires a publicly accessible HTTPS URL for your MA server. The config flow shows all URLs to paste into Yandex.Dialogs skill settings. Requires **Skill ID** and **Skill OAuth Token**.

## Limitations

- **No play_media** — Alice cannot start a specific song/playlist. "Включи музыку" only resumes the current MA queue.
- **Max 10 input sources** — Yandex mode capability supports up to 10 values.
- **No seek** — Yandex Smart Home API does not support seek for third-party media devices.
- **No track info** — Cannot push track name/artwork to Yandex (not supported by the API).

## Status

- [x] Project scaffold with CI/CD
- [x] Cloud relay connection (yaha-cloud.ru WebSocket)
- [x] Cloud Plus mode (private skill via Yandex.Dialogs)
- [x] Auto-registration config flow with OTP
- [x] Device registration & discovery
- [x] Capability: on_off, volume, mute, pause
- [x] Capability: next/previous track (channel)
- [x] Capability: input source selection (mode)
- [x] Player filter (expose selected players only)
- [x] State reporting to Yandex (debounced + heartbeat)
- [x] Direct connection mode (HTTP endpoints on MA webserver, no relay)
- [ ] Smart on_off (resume YaMusic playback when queue is empty)

## Related Projects

- [ma-provider-yandex-station](https://github.com/trudenboy/ma-provider-yandex-station) — Player provider for Yandex Station speakers (Glagol protocol)
- [dext0r/yandex_smart_home](https://github.com/dext0r/yandex_smart_home) — Home Assistant ↔ Yandex Smart Home integration (reference implementation)
- [Music Assistant](https://github.com/music-assistant/server) — The music server this plugin extends

## License

MIT — see [LICENSE](LICENSE).
