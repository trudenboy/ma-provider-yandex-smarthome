# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
