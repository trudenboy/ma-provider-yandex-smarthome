# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.3.0] — 2026-04-20

### Changed
- **Bumped `ya-passport-auth` to 1.3.0** — pulls in OAuth Device Flow (RFC 8628) support in the library; no provider-side code changes (only `SecretStr` is consumed)

## [1.2.0] — 2026-04-11

### Changed
- **Stage → beta** in manifest
- **on/off reflects player power state** — `is_on` uses `player.powered` (fallback to `available`), not playback state
- **Pause toggle shows ▶ when not playing** — IDLE/STOPPED players report `pause=true` so Yandex shows the play button
- **Device type → `media_device`** instead of `receiver` for better Yandex UI phrasing
- **Player name normalization** — strips non-Russian/English characters, adds space between letters and digits

### Fixed
- **Group player support** — volume/mute display and control now uses `group_volume`/`group_volume_muted` and `cmd_group_volume`/`cmd_group_volume_mute` APIs
- **Mute toggle conditional** — only exposed when player supports `VOLUME_MUTE` feature or is a group
- **State reporting race condition** — notifier reads fresh player state at flush time (1s debounce), not at event time, preventing transient volume=0 reports
- **Child→group event propagation** — child player state changes mark parent group as dirty for state reporting
- **Player deduplication** — uses `all_players()` to filter out PROTOCOL sub-players and disabled players
- **Defensive parsing** — `parse_action_payload` and `_handle_query` validate all intermediate types before iteration
- **JSON parse errors → 400** — malformed request bodies in direct mode return HTTP 400 instead of 500
- **Pending OAuth codes DoS cap** — `MAX_PENDING_CODES=20` with HTTP 429 on overflow
- **Input source selection** — `select_source` passes `source.id` instead of `source.name`

### Security
- **`secrets.compare_digest`** for OAuth refresh_token and client_secret comparisons
- **Redirect URI restricted** to `https://social.yandex.net` only
- **Best-effort error response** in cloud.py with `isinstance(data, dict)` guard

## [1.1.0] — 2026-04-10

### Added
- **Direct connection mode** — Yandex calls MA server directly via HTTPS, no yaha-cloud.ru relay needed
- **HTTP endpoint registration** on MA webserver (`/api/yandex_smarthome/v1.0/*`, `/api/yandex_smarthome/auth/*`)
- **OAuth account linking** — authorize + token exchange endpoints for Yandex.Dialogs skill setup
- **Per-install OAuth client secret** — auto-generated random secret stored in config (replaces hardcoded value)

### Changed
- **Tokens wrapped in SecretStr** via `ya-passport-auth` — cloud_token, connection_token, skill_token no longer stored as plain strings in memory
- **README restructured** — installation steps clearly separated for Cloud vs Direct setup

### Security
- **XSS fix** in OAuth authorize page — `redirect_uri` is now HTML-escaped and validated against `*.yandex.net` domain
- **OAuth credential validation** — `client_id` and `client_secret` are strictly validated on both authorize and token endpoints
- **URL normalization** — `base_url.rstrip("/")` prevents double-slash issues in generated endpoint URLs
- **Config token preservation** — hidden access token and client secret values are properly preserved across config saves

## [1.0.0] — 2025-04-08

### Added
- **Cloud relay connection** via yaha-cloud.ru WebSocket
- **Cloud Plus mode** with private skill support via Yandex.Dialogs
- **Auto-registration** config flow with OTP code generation
- **Device registration & discovery** (media_device.receiver)
- **Capabilities:** on_off, range(volume), toggle(mute), toggle(pause), range(channel), mode(input_source)
- **Next/Previous track** — `range(channel)` capability with relative actions ("Алиса, дальше/назад")
- **Input source selection** — `mode(input_source)` maps MA source_list to Yandex modes (up to 10 sources)
- **Player filter** — config option to select which MA players are exposed to Yandex Smart Home
- **State reporting** to Yandex with 1s debounce and hourly heartbeat
- **Discovery notifications** on player add/remove
- Custom icon from yaha-cloud.ru

### Notes
- on_off: "включи" = play/resume, "выключи" = stop. Device always reports as "on" while player is available.
- Yandex Smart Home API does **not** support `play_media` for third-party devices.
