# Yandex Smart Home — Music Assistant Plugin Provider

[![Tests](https://github.com/trudenboy/ma-provider-yandex-smarthome/actions/workflows/test.yml/badge.svg)](https://github.com/trudenboy/ma-provider-yandex-smarthome/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Expose Music Assistant players to Yandex Alice via the [Yandex Smart Home API](https://yandex.ru/dev/dialogs/smart-home/).**

> «Алиса, включи музыку на Music Assistant»

## Overview

This plugin bridges Music Assistant and the Yandex Smart Home ecosystem. It registers MA players as smart home devices (type `media_device`), enabling voice control through Alice:

| Voice command | Action |
|---|---|
| «Алиса, включи музыку на \<имя\>» | Play / resume |
| «Алиса, выключи \<имя\>» | Stop / pause |
| «Алиса, сделай громче на \<имя\>» | Volume up |
| «Алиса, поставь громкость 50 на \<имя\>» | Set volume |
| «Алиса, пауза на \<имя\>» | Pause |
| «Алиса, дальше на \<имя\>» | Next track |

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
│  (PluginProvider)  │       (play/pause/stop/vol/next)
│                   │
│  HTTP webhook or  │◄────── MA Player state events
│  cloud relay      │──────► Yandex state reports
└───────────────────┘
```

### Yandex Smart Home Capabilities Mapped

| Yandex Capability | MA Player Action |
|---|---|
| `on_off` | `play()` / `stop()` |
| `range(volume)` | `volume_set()` |
| `toggle(mute)` | `volume_mute()` |
| `toggle(pause)` | `play()` / `pause()` |

> **Note:** Yandex Smart Home API does **not** support `play_media` for third-party devices.
> When Alice says "включи музыку", the plugin triggers play/resume on the current MA queue.

## Installation

> ⚠️ **Experimental** — This provider is under active development.

### As a custom provider

1. Copy the `provider/` folder to your MA custom providers directory
2. Restart Music Assistant
3. Go to Settings → Providers → Add → Yandex Smart Home
4. Configure instance name and cloud token

### Development

```bash
# Clone
git clone https://github.com/trudenboy/ma-provider-yandex-smarthome.git
cd ma-provider-yandex-smarthome

# Dev environment with Docker
docker compose -f docker-compose.dev.yml up

# Or manual setup
pip install -e ".[test]"
pytest
```

## Configuration

| Parameter | Description |
|---|---|
| **Instance Name** | How this MA instance appears in Yandex Smart Home. Alice uses this name for voice commands. |
| **Cloud Token** | OAuth token for Yandex Smart Home API authentication. |

## Status

🚧 **Work in progress.** Core scaffolding is complete. Implementation of the Smart Home API bridge is underway.

- [x] Project scaffold with CI/CD
- [ ] Yandex Smart Home API client
- [ ] Device registration & discovery
- [ ] Capability action handling (on_off, volume, pause)
- [ ] State reporting to Yandex
- [ ] Cloud relay mode (no public URL needed)
- [ ] Direct webhook mode

## Related Projects

- [ma-provider-yandex-station](https://github.com/trudenboy/ma-provider-yandex-station) — Player provider for Yandex Station speakers (Glagol protocol)
- [dext0r/yandex_smart_home](https://github.com/dext0r/yandex_smart_home) — Home Assistant ↔ Yandex Smart Home integration (reference implementation)
- [Music Assistant](https://github.com/music-assistant/server) — The music server this plugin extends

## License

MIT — see [LICENSE](LICENSE).
