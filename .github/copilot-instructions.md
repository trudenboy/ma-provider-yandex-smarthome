# Copilot Instructions

## Project Overview

Music Assistant (MA) Plugin Provider that bridges existing MA players to Yandex Alice via the Yandex Smart Home API. This is a **plugin provider** — it does NOT create players or provide music, it exposes existing MA players for voice control.

## Architecture

```
Alice → Yandex Cloud → Smart Home API → yaha-cloud.ru WebSocket relay → this plugin → MA Player commands
                                                                                     ← MA Player state → Yandex state reports
```

### Module Responsibilities

- `provider/__init__.py` — `setup()` entry point, `get_config_entries()` with auto-registration config flow (OTP, Cloud Plus setup)
- `provider/plugin.py` — `YandexSmartHomePlugin(PluginProvider)`: event subscriptions, cloud lifecycle, routes incoming requests to handlers
- `provider/handlers.py` — Pure async functions for the 4 Smart Home API endpoints: `/user/devices`, `/user/devices/query`, `/user/devices/action`, `/user/unlink`
- `provider/device.py` — Maps MA Player state ↔ Yandex Smart Home device descriptions, capabilities, and action execution
- `provider/schema.py` — Dataclass models for the Yandex Smart Home protocol (device descriptions, capabilities, actions, callbacks)
- `provider/cloud.py` — `CloudManager`: persistent WebSocket connection to yaha-cloud.ru relay with reconnect/heartbeat
- `provider/notifier.py` — `StateNotifier`: debounced state reporting to Yandex (1s debounce, hourly heartbeat)
- `provider/constants.py` — All config keys (`CONF_*`), connection types, API URLs, capability/device type constants, timing values

### Key Flows

**Device Registration:** Plugin loads → subscribes to MA player events → creates Yandex device per player (type `media_device.receiver`) → registers capabilities (on_off, volume, mute, pause, channel, input_source) → reports to Yandex.

**Voice Commands:** Alice → Yandex Cloud → WebSocket relay → `plugin._handle_cloud_request()` → routes by normalized action path → `handlers.py` functions → `device.py` maps to MA player commands.

**State Reporting:** MA player state changes → `StateNotifier` receives event → debounces → maps via `device.py` → POSTs to Yandex callback/state API.

### Connection Modes

- **Cloud** — public Yaha Cloud skill via yaha-cloud.ru WebSocket relay (no public URL needed)
- **Cloud Plus** — private skill in Yandex.Dialogs (same relay, own OAuth)
- **Direct** — HTTP webhook (not yet implemented)

## Build, Test, Lint

```bash
# Install dev dependencies (uses uv)
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_handlers.py

# Run a single test function
uv run pytest tests/test_handlers.py::test_handle_device_list -v

# Lint (ruff checks all rules, see ruff.toml for ignores)
uv run ruff check .
uv run ruff format --check .

# Type checking
uv run mypy --ignore-missing-imports provider

# Spell checking
uv run codespell

# Pre-commit (runs all of the above)
uv run pre-commit run --all-files

# Dev environment with Docker (runs a real MA server with provider mounted)
docker compose -f docker-compose.dev.yml up
# MA UI at http://localhost:8095
```

## Code Conventions

- All files start with `from __future__ import annotations`
- All I/O is async/await (aiohttp for HTTP/WS)
- Protocol models use `@dataclass` in `schema.py`, serialized with `dataclasses.asdict()`
- Config keys are `CONF_*` constants in `constants.py` — never use raw strings
- Capability/device type constants are full Yandex API strings (e.g., `devices.capabilities.on_off`)
- Ruff is configured with `select = ["ALL"]` and explicit ignores — line length is 100, target Python 3.12
- Commit messages follow `type(scope): description` — types: feat, fix, docs, style, refactor, test, chore
- Follow patterns from MA's `_demo_plugin_provider` and `hass` plugin provider

## Testing Approach

Tests mock the entire `music_assistant` and `music_assistant_models` package hierarchy. The root `conftest.py` creates stub modules with `_ensure_module()` and registers them in `sys.modules` before any provider imports. This allows `provider/` to be importable both as `provider.*` and `music_assistant.providers.yandex_smarthome.*`.

When writing tests: import from the `music_assistant.providers.yandex_smarthome` namespace path, not directly from `provider`.

## Gotchas

- Yandex Smart Home API does NOT support `play_media` for third-party devices — "Включи музыку" triggers `on_off: true` only, which resumes the current MA queue
- Capabilities are limited to: on_off, range(volume), toggle(mute/pause), range(channel for next/prev), mode(input_source). No seek, no track info push
- Max 10 input sources (Yandex mode capability limit)
- Cloud relay action paths may or may not include `/v1.0` prefix — `plugin.py` normalizes with `removeprefix("/v1.0")`
