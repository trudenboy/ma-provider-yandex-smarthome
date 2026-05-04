# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.6.0] — 2026-05-04

### Added
- **Experimental Yandex Dialogs «Навык» for free-form voice playback (direct mode only)** — a new optional skill type that lets users say *"Алиса, попроси Music Assistant включить Metallica на кухне"* and have MA search for the content and start playback on the named player.
  - New modules: `provider/dialogs_nlu.py` (command parser + player resolver), `provider/dialogs_player.py` (content resolver + play wrapper), `provider/dialogs.py` (aiohttp webhook handler).
  - **NLU parser** classifies Russian voice commands into kinds: `track`, `artist`, `album`, `playlist`, `my_wave`, `genre`, `search`. Extracts an optional `"на <player>"` suffix and fuzzy-matches player names with Russian inflection stripping (e.g. «на кухне» → player «Кухня»).
  - **Content resolver** dispatches to `mass.music.search` by kind, with special-case paths for *Моя волна* (yandex_music rotor `user:onyourwave`) and genre radio (yandex_music genre rotor with artist-search fallback).
  - **Webhook handler** authenticates via URL path-secret + `body.session.skill_id`, keeps a 200-entry in-memory LRU session cache so follow-up commands remember which player was chosen, powers the player on before playback if needed, and fires play in a background task to stay within Yandex's 4.5 s response budget.
  - **Auto-create pipeline extended** — `auto_skill.py` is now parameterised by `skill_type` (`"smart_home"` | `"dialog"`); the dialog path builds a separate draft payload and injects the generated webhook URL. New `auto_rename_dialog_skill` helper patches the skill name in Yandex Dialogs and re-deploys.
  - **Config UI (direct mode only)** — toggle `Enable Dialogs voice skill (experimental)`, skill activation name (`CONF_DIALOG_SKILL_NAME`), auto-create action, rename-drift detection, hidden storage for artifacts/secret.
  - **Plugin wiring** — `DialogsWebhookHandler` is instantiated and routes registered during `_start_direct_mode`; unregistered on `unload`. Ignored silently in cloud/cloud_plus mode.
  - Full test coverage: 30+ table-driven NLU parse cases (including "включай"/"включайте" verb forms), player resolver cases (exact/inflected/substring/disabled/exposed_ids), content resolver unit tests, and webhook handler end-to-end tests including session memory, auth rejection, and fire-and-forget playback.

### Fixed (follow-up review)
- **Webhook skill_id check rejects absent/empty skill_id** — previously a request with no `session.skill_id` field was accepted (only URL secret validated); now any payload with missing or mismatched `skill_id` returns 401. Comparison uses `secrets.compare_digest` for constant-time safety.
- **NLU verb regex covers "включай"/"включайте"** — prior regex matched "включи"/"включите" but not "включай"/"включайте", leaving those forms unparsed and passing the raw verb into the search query.
- **`DIALOG_CHANNEL` single source of truth** — removed the duplicate definition from `auto_skill.py`; now imported from `provider/constants.py`.
- **Dialog draft docstring aligned with payload** — `build_dialog_draft_payload` docstring previously stated `category="other"` while the actual payload used `"music_and_sounds"`; aligned to match reality.
- **Removed duplicate inflection suffixes** — `_INFLECTION_SUFFIXES` in `dialogs_nlu.py` contained "ыми", "ого", "ой" twice each; duplicates removed.

## [1.5.3] — 2026-05-04

### Fixed
- **Misleading "Exposed Playlists" config description** — the in-app help text claimed the user could *"open the device in the Yandex app and assign voice aliases (e.g. \"Rock\" for mode «one»)"*. That option does not exist: the Yandex Smart Home API for `mode(input_source)` accepts only the fixed catalogue values `one`..`ten`, `ModeValue` has no `display_name`/`synonym` field, and the *Home with Alice* app has no UI to rename mode values. Description now reflects the actual ordinal-only mechanism («Alice, switch \<player\> source to five») and tells users the slot index is determined by the order they picked the playlists.

## [1.5.2] — 2026-05-04

### Fixed
- **Playlist picker no longer silently truncated at 500** — `fetch_playlist_options` now pages through `iter_library_items` instead of a single `library_items(limit=500)` call, so users with very large libraries see every playlist in the multi-select.

### Removed
- Dead helper `_build_source_modes` in `device.py` — superseded by `_build_combined_modes` since 1.5.0; was unreachable.

## [1.5.1] — 2026-05-04

### Fixed
- **Upstream lint/mypy compliance for v1.5.0** — `tests/test_device.py` `# type: ignore[arg-type]` was on the wrong physical line of a multi-line `get_device_state(...)` call (mypy strict reported the ignore as unused while still flagging the arg); collapsed the call to one line so the ignore lands on the offending arg. `tests/test_handlers.py` added `assert mode_caps[0].parameters is not None` before `.modes` access (mypy `union-attr`). One ruff-format whitespace fix in `provider/playlists.py`.

## [1.5.0] — 2026-05-04

### Added
- **MA library playlists as Yandex `mode(input_source)` modes** — pick up to 10 playlists from any music provider in MA and they appear as input-source slots on every exposed player. After saving, assign voice aliases (e.g. "Rock", "Jazz") to mode values `one`..`ten` in the Yandex app and Alice can start a playlist by name (`"Алиса, включи рок на [плеер]"`). Native player sources still take priority and fill slots first; playlists fill the remainder. Playlist-slot actions power the player on if needed and start playback via `mass.player_queues.play_media`. Workaround for Yandex Smart Home API not supporting `play_media` for third-party devices.

### Internal
- Quieter logging when native player sources already fill all 10 `mode(input_source)` slots — the "playlists ignored" diagnostic now logs at debug level instead of warning, since it documents a config decision and gets emitted on every `/user/devices` poll.
- Drop redundant `list(YANDEX_MODE_VALUES).index(...)` allocations on action/state hot paths — tuples already support `.index()`.

## [1.4.5] — 2026-04-24

### Fixed
- **Cloud Plus manual fallback no longer shows invalid Client ID before registration** — the cloud_plus Client ID embeds the yaha-cloud instance UUID; before the user registers, it was rendered as `yandex_smart_home:` (trailing colon, no UUID) and could mislead power users in Advanced view into creating a skill with broken account-linking. Manual fallback is now suppressed entirely for cloud_plus while `cloud_instance_id` is empty.

## [1.4.4] — 2026-04-24

### Fixed
- **`asyncio.CancelledError` now propagates through the auto-create pipeline and config-action handler** — both broad `except Exception` clauses (`auto_skill.py` orchestrator and `_run_auto_create_action` in `__init__.py`) re-raise `CancelledError` explicitly before the generic handler, so HA shutdown / config-flow abort no longer gets absorbed into a `FAILED` artifact.

## [1.4.3] — 2026-04-24

### Fixed
- **`_build_authenticator_cm` double-wrap crash** — when a caller injected an authenticator already decorated with `@asynccontextmanager`, the helper re-wrapped it unconditionally, which broke at runtime because the outer wrapper would call `__anext__` on the inner CM object. Now detect an async-CM result and pass it through, otherwise adapt the async iterator without calling the factory twice.
- **`SkillCreationState.DEPLOY_REQUESTED` is now actually set** — previously the value was defined and allow-listed in the resume branch but no code ever wrote it, making it dead state. The orchestrator now checkpoints to `DEPLOY_REQUESTED` before calling `request_deploy`, so a crash mid-publish resumes from publish-only instead of rerunning the whole pipeline.
- **`TestListExistingSkills` docstring corrected** — class docstring claimed malformed JSON returned an empty list, but the test asserts `DialogsApiError` is raised. Docstring updated to match behavior.

## [1.4.2] — 2026-04-24

### Fixed
- **Upstream mypy strict `in` on `str | None`** — the `"Retry" in action.action_label` assertion now narrows `action_label` with an explicit `is not None` first, matching the strict operator rules used by upstream mypy.

## [1.4.1] — 2026-04-24

### Fixed
- **Upstream lint compliance** — drop duplicate module-docstring candidate in `auto_skill.py` (caught by `check-docstring-first`), tighten type annotations in UI/state tests to satisfy upstream mypy strict mode (no more `# type: ignore[no-untyped-def]` fallbacks; StrEnum comparisons now use `.value`).

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
