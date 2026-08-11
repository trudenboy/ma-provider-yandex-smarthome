# Yandex Smart Home — Music Assistant Plugin Provider


<!-- >>> ma-provider-tools sync (readme header) — DO NOT EDIT >>> -->
[![CI](https://github.com/trudenboy/ma-provider-yandex-smarthome/actions/workflows/test.yml/badge.svg)](https://github.com/trudenboy/ma-provider-yandex-smarthome/actions/workflows/test.yml)
[![Release](https://img.shields.io/github/v/release/trudenboy/ma-provider-yandex-smarthome?display_name=tag)](https://github.com/trudenboy/ma-provider-yandex-smarthome/releases/latest)
[![License](https://img.shields.io/github/license/trudenboy/ma-provider-yandex-smarthome)](LICENSE)
[![Music Assistant](https://img.shields.io/badge/Music%20Assistant-9070B8?logo=python&logoColor=white)](https://www.music-assistant.io/)[![stable](https://img.shields.io/endpoint?url=https%3A%2F%2Ftrudenboy.github.io%2Fma-provider-tools%2Fbadges%2Fyandex_smarthome-stable.json)](https://github.com/music-assistant/server/releases/latest)[![beta](https://img.shields.io/endpoint?url=https%3A%2F%2Ftrudenboy.github.io%2Fma-provider-tools%2Fbadges%2Fyandex_smarthome-beta.json)](https://github.com/music-assistant/server/releases?q=prerelease)
[![Stars](https://img.shields.io/github/stars/trudenboy/ma-provider-yandex-smarthome?style=flat&logo=github)](https://github.com/trudenboy/ma-provider-yandex-smarthome/stargazers)

**📖 [Documentation / Документация](https://trudenboy.github.io/ma-provider-yandex-smarthome/)** · **🔄 [Changelog / Журнал](CHANGELOG.md)** · **🐛 [Issues / Проблемы](https://github.com/trudenboy/ma-provider-yandex-smarthome/issues)** · **💬 [Discussions / Обсуждения](https://github.com/trudenboy/ma-provider-yandex-smarthome/discussions)**

**Related providers:** [Yandex Alice](https://github.com/trudenboy/ma-provider-yandex-alice) · [Yandex Station](https://github.com/trudenboy/ma-provider-yandex-station) · [Yandex Music](https://github.com/trudenboy/ma-provider-yandex-music)
<!-- <<< ma-provider-tools sync (readme header) <<< -->

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
4. Follow the guided setup wizard and choose a connection mode:
   - **Cloud** — public Yaha Cloud skill; simplest setup
   - **Cloud Plus** — private skill through the relay; use this when the public skill is already linked to another installation
   - **Direct** — Yandex calls your MA server over a public HTTPS URL; no relay
5. Complete the steps shown by Music Assistant. Registration, Yandex sign-in, skill provisioning and account linking are presented in the required order.

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
| **Exposed Players** | Select which MA players to expose to Alice. Empty = all players. |
| **Exposed Playlists** | Select up to 10 library playlists to expose as input-source slots. |

Connection mode and credentials are collected by the setup wizard. Reconfigure the provider to run that wizard again; the regular settings page only contains playback options.

### Setup flow per mode

The wizard persists each provider's setup credentials separately from its normal playback options. For skill provisioning, you can use this provider's own Yandex account or borrow the authenticated account from a configured Yandex Music provider.

#### Cloud Plus (3 steps)

1. The wizard registers a private yaha-cloud.ru relay slot.
2. Choose automatic skill creation or enter the ID of an existing Yandex Dialogs skill. Automatic creation shows a Yandex Device Flow code inside the wizard and resumes when confirmation is detected.
3. Paste the skill OAuth token, then enter the one-time linking code shown by Music Assistant in the Yandex app.

#### Direct (1 step)

1. Enter or confirm the public **HTTPS** URL for Music Assistant. The wizard validates it before provisioning.
2. Confirm the Yandex Device Flow code; the provider creates and configures the private skill.
3. Paste the skill OAuth token. Linking then uses Yandex Dialogs account linking, so there is no relay OTP.

#### Cloud (unchanged)

The wizard registers the public relay slot, displays a one-time code, and waits while you enter it in the Yandex app.

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
