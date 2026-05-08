# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Music Assistant (MA) Plugin Provider that exposes MA players to Yandex Alice via the Yandex Smart Home API. This is a **plugin provider** (not a player or music provider) — it doesn't create players or provide music, it bridges existing MA players to the Yandex ecosystem for voice control.

## Architecture

```
Alice → Yandex Cloud → Smart Home API callback → this plugin → MA Player commands
                                                              ← MA Player state → Yandex state reports
```

**Connection modes:**
- **Cloud / Cloud Plus**: Alice → Yandex Cloud → yaha-cloud.ru WebSocket relay → plugin
- **Direct**: Alice → Yandex Cloud → HTTPS → MA Webserver (dynamic routes) → plugin

**Provider** (`provider/`): MA Plugin Provider with Smart Home API bridge.
- `__init__.py` — `setup()`, `get_config_entries()` (instance_name, cloud_token)
- `plugin.py` — `YandexSmartHomePlugin(PluginProvider)`: main plugin class, event subscriptions, device lifecycle
- `direct.py` — `DirectConnectionHandler`: HTTP endpoints for direct connection mode (routes registered on MA webserver)
- `constants.py` — Yandex Smart Home API constants (device types, capabilities, API URLs)
- `manifest.json` — provider metadata (type: plugin, domain: yandex_smarthome)

### Key Flows

**Device Registration:**
1. Plugin loads → subscribes to MA player events
2. For each MA player → creates Yandex Smart Home device (type: media_device)
3. Registers capabilities: on_off, range(volume), toggle(mute), toggle(pause)
4. Reports device list to Yandex via Smart Home API

**Voice Command Handling:**
1. Alice sends command → Yandex Cloud → Smart Home API callback to plugin
2. Plugin receives capability action (e.g. on_off=true, volume=50)
3. Maps to MA player command (play, pause, stop, volume_set, etc.)
4. Executes command on MA player

**State Reporting:**
1. MA player state changes → plugin receives event
2. Maps MA state to Yandex Smart Home device state
3. Reports state to Yandex via callback_state API

## Development Setup

```bash
# Docker dev environment (recommended)
docker compose -f docker-compose.dev.yml up

# Or manual:
pip install -e ".[test]"
pytest
```

## Code Standards

- **Python**: PEP 8, type hints on all functions, `from __future__ import annotations`
- **Commits**: `type(scope): description` — types: feat, fix, docs, style, refactor, test, chore
- **Async**: All I/O uses async/await (aiohttp)
- **MA conventions**: Follow patterns from `_demo_plugin_provider` and `hass` plugin provider
- **DO NOT use subagents (Task tool) without explicit user instruction or confirmation!**

## Key References

| Source | Purpose |
|--------|---------|
| `music_assistant/providers/_demo_plugin_provider/` | Canonical plugin provider template |
| `music_assistant/providers/hass/` | Real plugin with PlayerControl registration |
| `music_assistant/models/plugin.py` | PluginProvider, PluginSource base classes |
| `dext0r/yandex_smart_home` | Yandex Smart Home protocol reference |

## Gotchas

- **No play_media from Alice**: Yandex Smart Home API does NOT support `play_media` for third-party devices. "Включи музыку" → `on_off: true` only. Plugin resumes current MA queue.
- **Cloud vs Direct mode**: Without a public URL, need a cloud relay (like dext0r's yaha-cloud.ru WebSocket relay). Direct mode needs port forwarding or reverse proxy.
- **Device types**: Use `devices.types.media_device` for MA players in Yandex.
- **Capabilities limited**: Only on_off, range(volume), toggle(mute/pause), mode(input_source). No seek, no track info push.
- **This is a plugin, not a player provider**: It does NOT create MA players. It controls existing ones.
- **Don't name files `http.py`**: Shadows Python's stdlib `http` module. The direct connection handler is in `direct.py`.
- **Direct mode uses `mass.webserver.register_dynamic_route()`**: MA's built-in mechanism for adding HTTP endpoints. Returns an unregister callback.
- **OAuth is minimal**: Single access token (UUID) stored in config. Pending authorization codes kept in memory with 5-min TTL.
