# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.4.0] — 2026-04-24

### Added
- **Auto-create skill as default flow** — for `cloud_plus` and `direct` modes the provider now creates the private Yandex Dialogs skill automatically via device-flow login against Yandex Passport + undocumented `dialogs.yandex.ru/developer/app-store-api`. Partial failures are resumable: retry resumes from the last completed step without duplicating work.
- **Numbered step UX** — the config form shows the single next step you need (Register → Create → Link for `cloud_plus`, Create only for `direct`). Later steps are hidden until the previous one is done.
- **Manual fallback is automatic** — on auto-create failure, the form unfolds copy-paste fields (Backend URL / Client ID / Client Secret / Auth/Token URLs / Dialogs console link) so the user finishes in Yandex.Dialogs by hand without leaving MA settings.
- **Power-user Advanced view** — all manual-setup reference values (Backend URL, Client ID, Client Secret, Auth/Token URLs) are always available under Advanced, so users can verify or edit them even when auto-create succeeded.
- **Cloud mode single-account-link advisory** — when Cloud connection type is selected, a note warns that the public Yaha Cloud skill only allows one linked instance per Yandex account and suggests Cloud Plus for multi-install setups.
- **Configured-state collapse** — once Skill ID and Skill OAuth Token are both saved, the provider UI replaces the edit fields with a single "Open skill in Yandex.Dialogs" link pointing at `dialogs.yandex.ru/developer/skills/{skill_id}/`.

### Changed
- **Connection Type moved out of Advanced** — the mode selector is the first decision a user makes and now renders in the default view.
- **Skill logo during auto-create** uses the provider's own `icon.svg` (rasterised to 512×512 PNG) instead of a placeholder.

### Removed
- `experimental_auto_create_skill` master toggle — auto-create is now on by default.

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
