# Yandex Smart Home — Music Assistant Plugin Provider


<!-- >>> ma-provider-tools sync (readme header) — DO NOT EDIT >>> -->
[![CI](https://github.com/trudenboy/ma-provider-yandex-smarthome/actions/workflows/test.yml/badge.svg)](https://github.com/trudenboy/ma-provider-yandex-smarthome/actions/workflows/test.yml)
[![Release](https://img.shields.io/github/v/release/trudenboy/ma-provider-yandex-smarthome?display_name=tag)](https://github.com/trudenboy/ma-provider-yandex-smarthome/releases/latest)
[![License](https://img.shields.io/github/license/trudenboy/ma-provider-yandex-smarthome)](LICENSE)
[![Music Assistant](https://img.shields.io/badge/Music%20Assistant-provider-9070B8?logo=python&logoColor=white)](https://www.music-assistant.io/)
[![Stars](https://img.shields.io/github/stars/trudenboy/ma-provider-yandex-smarthome?style=flat&logo=github)](https://github.com/trudenboy/ma-provider-yandex-smarthome/stargazers)

**📖 [Documentation / Документация](https://trudenboy.github.io/ma-provider-yandex-smarthome/)** · **🔄 [Changelog / Журнал](CHANGELOG.md)** · **🐛 [Issues / Проблемы](https://github.com/trudenboy/ma-provider-yandex-smarthome/issues)** · **💬 [Discussions / Обсуждения](https://github.com/trudenboy/ma-provider-yandex-smarthome/discussions)**

**Related providers:** [Yandex Alice](https://github.com/trudenboy/ma-provider-yandex-alice) · [Yandex Station](https://github.com/trudenboy/ma-provider-yandex-station)
<!-- <<< ma-provider-tools sync (readme header) <<< -->

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

### Setup flow per mode

Auto-create is the default path for `cloud_plus` and `direct`. The config form shows the single next step you need to complete; later steps only appear after you finish the current one.

> **Note:** Auto-create uses an undocumented Yandex Dialogs API — if it fails, the form automatically shows copy-paste fields so you can create the skill by hand in `dialogs.yandex.ru/developer` without leaving MA settings.

#### Cloud Plus (3 steps)

1. **Register cloud instance** — click **Register with cloud**. The provider creates a yaha-cloud.ru relay instance. (Step 2 becomes visible afterwards.)
2. **Create Smart Home skill** — click **Create skill automatically**. A popup opens showing your short Device Flow code; open `ya.ru/device` from the popup's link, log in to your Yandex account, and confirm the code. The provider creates the private skill, uploads the logo, wires up account linking, and publishes. On success **Skill ID** is filled in automatically; open the **OAuth URL** link and paste the resulting token into **Skill OAuth Token**. On failure, the form unfolds copy-paste fields for manual setup.
3. **Link skill to Yandex** — click **Get OTP code**. Open the Yandex app → Devices → Add device → Smart Home → find your private skill → enter the OTP. Save provider config.

#### Direct (1 step)

1. **Create Smart Home skill** — same as Step 2 above. Requires MA to be reachable from the public internet over **HTTPS** (reverse proxy with a real certificate — self-signed won't work). Linking happens via Yandex.Dialogs' own Account linking UI after the skill exists, so there's no Step 3.

#### Cloud (unchanged)

Public Yaha Cloud skill — just **Register** then **Get OTP** and enter it in the Yandex app.

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
