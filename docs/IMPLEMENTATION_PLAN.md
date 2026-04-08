# Implementation Plan: Yandex Smart Home API Bridge

## Problem Statement

Expose Music Assistant players to Yandex Alice via the Yandex Smart Home API, enabling
voice commands like «Алиса, включи музыку на Music Assistant». The plugin subscribes to
MA player events and presents them as `media_device` devices in Yandex Smart Home with
capabilities: `on_off`, `range(volume)`, `toggle(mute)`, `toggle(pause)`.

## Connection Architecture

Two connection modes, same as dext0r/yandex_smart_home:

### Mode A — Cloud Relay (via yaha-cloud.ru)
```
Yandex Cloud ──WS──▶ yaha-cloud.ru ──WS──▶ this plugin
                                    ◀──WS──  state reports
```
- No public URL needed (NAT-friendly)
- Register cloud instance → get `instance_id` + `connection_token`
- Plugin opens persistent WebSocket to `wss://yaha-cloud.ru/api/home_assistant/v1/connect`
- Receives JSON `{request_id, action, message}`, responds with JSON
- State reports POST to `https://yaha-cloud.ru/api/home_assistant/v2/callback/{platform}/state`

### Mode B — Direct (Yandex Dialogs Skill)
```
Yandex Cloud ──HTTP──▶ this plugin (public URL)
                      ◀──HTTP──  JSON response
             ◀──HTTP──  state callback
```
- Requires public URL (reverse proxy / port forwarding)
- Register a Yandex Dialogs skill → get `skill_id`
- Yandex calls `POST /api/yandex_smarthome/v1.0/user/devices`, `/query`, `/action`
- State reports POST to `https://dialogs.yandex.net/api/v1/skills/{skill_id}/callback/state`

**Priority: Cloud mode first** (easier setup, no public URL), direct mode later.

## Yandex Smart Home API Protocol

All interactions follow 4 handlers (same as dext0r):

| Action | Request | What it does |
|--------|---------|-------------|
| `/user/devices` | — | Return list of all MA players as Yandex devices |
| `/user/devices/query` | `{devices: [{id}]}` | Return current state of requested devices |
| `/user/devices/action` | `{payload: {devices: [{id, capabilities}]}}` | Execute capability actions |
| `/user/unlink` | — | User disconnected account |

### Device Description (per MA player)
```json
{
  "id": "<player_id>",
  "name": "<player display_name>",
  "type": "devices.types.media_device.receiver",
  "capabilities": [
    {"type": "devices.capabilities.on_off", "retrievable": true, "reportable": true},
    {"type": "devices.capabilities.range", "retrievable": true, "reportable": true,
     "parameters": {"instance": "volume", "range": {"min": 0, "max": 100, "precision": 1}, "unit": "unit.percent"}},
    {"type": "devices.capabilities.toggle", "retrievable": true, "reportable": true,
     "parameters": {"instance": "mute"}},
    {"type": "devices.capabilities.toggle", "retrievable": true, "reportable": true,
     "parameters": {"instance": "pause"}}
  ],
  "device_info": {"manufacturer": "Music Assistant", "model": "<provider type>"}
}
```

### Capability → MA Command Mapping
| Yandex Capability | Value | MA Player Action |
|-------------------|-------|------------------|
| `on_off` | `true` | `mass.players.cmd_play(player_id)` or resume queue |
| `on_off` | `false` | `mass.players.cmd_stop(player_id)` |
| `range(volume)` | `0–100` | `mass.players.cmd_volume_set(player_id, value)` |
| `range(volume)` | relative `+N/-N` | `mass.players.cmd_volume_set(player_id, current + delta)` |
| `toggle(mute)` | `true/false` | `mass.players.cmd_volume_mute(player_id, value)` |
| `toggle(pause)` | `true` | `mass.players.cmd_pause(player_id)` |
| `toggle(pause)` | `false` | `mass.players.cmd_play(player_id)` |

### State Reporting (Callback)
When MA player state changes, report to Yandex:
```json
{
  "ts": 1234567890.0,
  "payload": {
    "user_id": "<cloud_instance_id>",
    "devices": [{
      "id": "<player_id>",
      "capabilities": [
        {"type": "devices.capabilities.on_off", "state": {"instance": "on", "value": true}},
        {"type": "devices.capabilities.range", "state": {"instance": "volume", "value": 42}},
        {"type": "devices.capabilities.toggle", "state": {"instance": "mute", "value": false}},
        {"type": "devices.capabilities.toggle", "state": {"instance": "pause", "value": false}}
      ]
    }]
  }
}
```

## Module Plan

### Phase 1: Schema & Constants (foundation)

**`provider/schema.py`** — Pydantic models for all API request/response types.
Adapted from dext0r/yandex_smart_home/schema/* but simplified (only the types we need):
- `DeviceType` enum (only `MEDIA_DEVICE`, `MEDIA_DEVICE_RECEIVER`)
- `CapabilityType` enum (`ON_OFF`, `RANGE`, `TOGGLE`)
- `RangeCapabilityInstance` (`VOLUME`), `ToggleCapabilityInstance` (`MUTE`, `PAUSE`)
- `DeviceDescription`, `DeviceState`, `DeviceList`, `DeviceStates`
- `ActionRequest`, `ActionResult` (with capability-level results)
- `Response`, `ResponseCode`, `ResponsePayload`
- `CallbackStatesRequest`, `CallbackDiscoveryRequest`, `CallbackResponse`

**Update `provider/constants.py`** — add cloud URLs:
- `CLOUD_BASE_URL = "https://yaha-cloud.ru"`
- `CLOUD_API_URL = f"{CLOUD_BASE_URL}/api/home_assistant/v1"`
- `YANDEX_DIALOGS_API_URL = "https://dialogs.yandex.net/api/v1"`
- Config entry keys for connection_type, cloud_instance_id, cloud_connection_token, skill_id

### Phase 2: Device Mapper

**`provider/device.py`** — Maps MA Player ↔ Yandex Smart Home device.
- `MAPlayerDevice` class wrapping an MA `Player` object
- `get_description() -> DeviceDescription` — builds device desc with capabilities
- `get_state() -> DeviceState` — reads current player state, returns capability states
- `execute_action(action) -> ActionResult` — maps Yandex capability action → MA player command
- Helper: `player_to_device_id(player_id) -> str` and reverse
- Helper: `is_player_exposable(player) -> bool` — filter which players to expose

Key decisions:
- Device type: `devices.types.media_device.receiver` (best match for an AV receiver / amplifier)
- Device ID: use MA `player_id` directly (unique, stable)
- Device name: MA `player.display_name` (user-facing name)

### Phase 3: Request Handlers

**`provider/handlers.py`** — Pure async functions handling each Yandex API action.
Pattern matches dext0r's handler registry:
- `handle_device_list(mass, config) -> DeviceList`
- `handle_devices_query(mass, config, device_ids) -> DeviceStates`
- `handle_devices_action(mass, config, actions) -> ActionResult`
- `handle_user_unlink(config) -> None`
- Router: `async_handle_request(action, payload) -> Response`

Each handler:
1. Gets relevant MA players from `mass.players`
2. Uses `MAPlayerDevice` to build responses / execute actions
3. Returns proper Yandex API schema objects

### Phase 4: Cloud Connection Manager

**`provider/cloud.py`** — WebSocket connection to yaha-cloud.ru.
Adapted from dext0r's `cloud.py` but without HA dependencies:

- `CloudManager` class:
  - `__init__(session, connection_token, on_request_callback)`
  - `async connect()` — open WS to `{CLOUD_API_URL}/connect` with Bearer token
  - Message loop: parse `CloudRequest`, call `on_request_callback`, send response
  - `async disconnect()`
  - Auto-reconnect with exponential backoff (2s → 180s max)
  - Heartbeat: 45s

- Cloud instance management (free functions):
  - `register_instance(session) -> CloudInstanceData`
  - `get_instance_otp(session, instance_id, token) -> str`

### Phase 5: State Notifier

**`provider/notifier.py`** — Reports MA player state changes to Yandex.
Simplified from dext0r's notifier (no HA templates, no custom properties):

- `StateNotifier` class:
  - Subscribes to MA `EventType.PLAYER_UPDATED` events
  - On player state change: compare old/new states, queue changed capabilities
  - Batched reporting: collect changes within 1-second window, then POST
  - Periodic heartbeat: every 1 hour, report all states
  - Initial report: 15s after startup, report all current states
  - Discovery notification: after player added/removed, POST discovery request

- Two subclasses:
  - `CloudNotifier` — POSTs to `yaha-cloud.ru/api/home_assistant/v2/callback/{platform}/state`
  - `DirectNotifier` — POSTs to `dialogs.yandex.net/api/v1/skills/{skill_id}/callback/state`

### Phase 6: Plugin Integration (main orchestrator)

**Update `provider/plugin.py`** — Wire everything together in `YandexSmartHomePlugin`:

```python
async def handle_async_init(self):
    # Create aiohttp session
    # Validate config (connection_type, token)
    # Initialize CloudManager or prepare direct HTTP handler

async def loaded_in_mass(self):
    # Subscribe to PLAYER_ADDED, PLAYER_REMOVED, PLAYER_UPDATED events
    # Connect to cloud (or register HTTP routes for direct mode)
    # Start StateNotifier
    # Register all existing players

async def unload(self, is_removed):
    # Disconnect cloud / stop notifier
    # Close aiohttp session
```

Event handling:
- `PLAYER_ADDED` → add device to internal registry, send discovery notification
- `PLAYER_REMOVED` → remove from registry, send discovery notification
- `PLAYER_UPDATED` → feed to StateNotifier for debounced reporting

**Update `provider/__init__.py`** — add `CONF_CONNECTION_TYPE` config entry with cloud/direct options.

### Phase 7: Direct Mode HTTP Handler (deferred to v0.2)

**`provider/http.py`** — aiohttp web server for direct Yandex webhook.
Only needed for direct mode (Mode B):
- Register routes: `/api/yandex_smarthome/v1.0/user/devices`, `/query`, `/action`, `/unlink`
- OAuth token validation from Yandex request headers
- Call same handlers as cloud mode

**This phase can be deferred** — cloud mode is sufficient for initial release.

### Phase 8: Tests

Tests for each module (unit tests, no MA server needed):
- `tests/test_schema.py` — Pydantic model serialization/deserialization roundtrips
- `tests/test_device.py` — MA player → Yandex device mapping, capability state extraction
- `tests/test_handlers.py` — handler logic with mock MA players
- `tests/test_cloud.py` — WebSocket message parsing, reconnect logic
- `tests/test_notifier.py` — state change detection, batching, reporting

### Phase 9: Config Flow Improvements (deferred to v0.2)

- Add `CONF_CONNECTION_TYPE` choice (cloud / direct) to config entries
- Cloud mode: auto-register instance, show OTP for linking in Yandex app
- Direct mode: show webhook URL to copy into Yandex Dialogs skill config
- Player filter: option to choose which MA players to expose

## File Structure (final)

```
provider/
├── __init__.py          # setup(), get_config_entries()
├── plugin.py            # YandexSmartHomePlugin(PluginProvider) — orchestrator
├── constants.py         # API URLs, config keys, enums
├── schema.py            # Pydantic models for Yandex Smart Home API
├── device.py            # MAPlayerDevice — MA Player ↔ Yandex device mapper
├── handlers.py          # Request handler functions (device_list, query, action)
├── cloud.py             # CloudManager — WebSocket connection to yaha-cloud.ru
├── notifier.py          # StateNotifier — report state changes to Yandex
├── http.py              # (Phase 7) Direct mode HTTP webhook handler
├── manifest.json        # Provider metadata
└── icon.svg             # Provider icon
```

## Implementation Order

1. **Schema + Constants** — foundation, no dependencies
2. **Device mapper** — needs schema, testable in isolation
3. **Handlers** — needs schema + device, testable with mock players
4. **Cloud connection** — needs handlers, testable with mock WS
5. **Notifier** — needs schema + device, testable in isolation
6. **Plugin integration** — wires phases 1-5 together
7. **Tests** — throughout, but comprehensive suite at the end
8. **Direct HTTP** — deferred to v0.2
9. **Config flow** — deferred to v0.2

## Key Design Decisions

1. **Cloud mode first**: easier for users (no port forwarding), well-tested path via yaha-cloud.ru
2. **Device type `media_device.receiver`**: best semantic match for an AV receiver controlled by MA
3. **Player ID as device ID**: stable, unique, no mapping table needed
4. **No `play_media` capability**: Yandex Smart Home API doesn't support it for 3rd-party devices.
   `on_off: true` → resume current MA queue. Users can use MA UI/app to pick content.
5. **Pydantic models**: same approach as dext0r for JSON serialization, validation
6. **Batched state reporting**: 1-second window to avoid spamming Yandex with per-attribute changes
7. **Reuse yaha-cloud.ru**: don't reinvent cloud relay — use dext0r's existing infrastructure

## Open Questions

1. **yaha-cloud.ru compatibility**: The API paths contain `/home_assistant/` — will it accept
   non-HA clients? May need to talk to dext0r or create a compatible platform identifier.
2. **Player filtering**: Should we expose all MA players or let user select which ones?
   Start with all, add filter in v0.2.
3. **Playback content**: Alice can say "включи музыку" but Smart Home API can't specify _what_
   to play. `on_off: true` resumes the MA queue. Is this sufficient? Consider Ynison integration
   for content selection in a future version.
4. **Authentication**: Cloud mode uses yaha-cloud token. Direct mode needs Yandex OAuth skill.
   Both require user setup in Yandex ecosystem — document clearly.
