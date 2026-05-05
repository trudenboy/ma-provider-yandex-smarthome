# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.7.6] — 2026-05-05

### Fixed
- **Dialog skill auto-create now uses the real Yandex API contract.** Captured a live `POST /apps` and `PATCH /draft/update` from the Yandex Dialogs developer console (DevTools Network) — both shapes were wrong in our previous guess. Concrete fixes:
  - `DIALOG_CHANNEL`: default changed from `"dialog"` to `"aliceSkill"` (was a placeholder pending a manual probe). Confirmed correct by Yandex's own dev console — `POST /apps {"channel":"aliceSkill", ...}` returns 200.
  - `build_dialog_draft_payload` rewritten to match the real PATCH shape: voice `"good_oksana"` (was `"shitova.us"` — Smart-Home value); flat `publishingSettings` fields (`description`, `email`, `category`, `developerName`, `brandVerificationWebsite`, `explicitContent`, `structuredExamples`) instead of the Smart-Home `multilingualSettings`/`secondaryTitle` blocks; required top-level fields added: `activationPhrases`, `yaCloudGrant`, `requiredInterfaces`, `exactSurfaces`, `surfaceWhitelist`, `surfaceBlacklist`, `appMetricaApiKey`, `useStateStorage`, `rsyPlatformId`. Removed: `enableAllAvailableRegions`, `selectedRegions` (those are Smart-Home-only).
  - **`activationPhrases` is globally unique across all Yandex skills.** If the user-set name (`CONF_DIALOG_SKILL_NAME`) is taken, Yandex returns `400 "Это активационное имя уже зарегистрировано"`. The plugin defaults to the user-set value, so users picking generic names like "Music Assistant" may need to choose something distinctive.

### Fixed
- **Better diagnostics for `create_app` HTTP 400** — Yandex sometimes rejects requests with an empty body, leaving users unable to tell what went wrong. The plugin now logs full response headers (Content-Type, etc.) at WARNING when a non-success response has an empty body, and the error string now reads `<empty>` instead of trailing whitespace.
- **Dialog skill `create_app` failure surfaces a channel hint** — when `create_app` returns HTTP 400 for the dialog pipeline (most common cause: the `DIALOG_CHANNEL` value is wrong — the «Навык» channel string is not publicly documented and our default `"dialog"` is a best guess), the FAILED artifact's `last_error` now contains a hint about overriding `MA_YANDEX_DIALOG_CHANNEL` at MA startup so users can self-diagnose without reading source code.



### Fixed
- **`UNKNOWN_USER` state-callback errors no longer flood the logs.** After auto-create completes the plugin starts pushing state callbacks to Yandex, but until the user opens *Дом с Алисой* and links the skill via the Account Linking flow, every callback returns `HTTP 400 UNKNOWN_USER` — that's the expected first-run state, not a code bug. Notifier now emits one clear `WARNING` with linking instructions on the first occurrence, then drops further `UNKNOWN_USER` responses to debug level. As soon as Yandex accepts a callback (linking complete) the warning latch resets and an INFO line confirms recovery.

### Fixed
- **`_resolve_base_url` strips whitespace before stripping trailing slash** — a copy-pasted External Base URL like `" https://ma.example.com/ "` would have failed the `https://` HTTPS check and produced malformed callback / webhook URIs. Both the override and `mass.webserver.base_url` fallback are now normalized via `.strip().rstrip('/')`.
- **Dialog-skill HTTPS warning text correctly identifies the source URL** — previously it said *"MA's Base URL is …"* even when the External Base URL plugin override was in effect; now reads *"Resolved Base URL is …"* and points users at the External Base URL field first (with the global setting as a fallback), matching the Smart Home warning above.

## [1.7.2] — 2026-05-05

### Fixed
- **Auto-create no longer fails on Yandex backend validation due to chicken-and-egg.** The plugin's direct-mode handler used to bail out at startup if `skill_id`/`skill_token` were missing, so HTTP routes were never registered until *after* a skill existed. But Yandex calls those routes *during* `request_deploy` to validate the backend — so the very first auto-create always failed with `400 BackendSettings uri ... is not valid`. Split the startup into two stages: routes register as soon as `direct_client_secret` is set (auto-generated when the form is opened); the state notifier (outgoing callbacks) starts only when `skill_id`/`skill_token` are populated. Now Yandex's validation hits live endpoints on the first attempt.

## [1.7.1] — 2026-05-05

### Fixed
- **Direct mode auto-create now passes Yandex's backend validation.** The Backend URI sent to Yandex (`derive_backend_uri` for `direct`) included `/v1.0`, but Yandex appends `/v1.0/...` itself when calling our endpoints. The result was duplicate `/v1.0/v1.0/user/devices` paths during validation → all 404, and `request_deploy` returned `HTTP 400 BackendSettings uri ... is not valid`. Introduced `DIRECT_BACKEND_URI_PATH = "/api/yandex_smarthome"` (without `/v1.0`) for Yandex; routes still register at `DIRECT_API_BASE_PATH = "/api/yandex_smarthome/v1.0"` so the actual paths Yandex calls (`<backend>/v1.0/user/devices` = `/api/yandex_smarthome/v1.0/user/devices`) match what the plugin listens on.

## [1.7.0] — 2026-05-05

### Added
- **Plugin-local "External Base URL" override (direct mode)** — a new optional config field exposed only when *Connection Type = Direct*. Lets users keep MA's global `Base URL` pointing at the local address (so Home Assistant Ingress and local frontend access keep working) while exposing a public HTTPS URL only to Yandex via a reverse proxy. The override is used by:
  - the Smart Home callback URL (`derive_backend_uri`) and OAuth URLs (`derive_auth_urls`) sent to Yandex during auto-create,
  - the HTTPS precondition check (`check_preconditions`),
  - the Dialogs «Навык» webhook URL (`_build_dialog_backend_uri`),
  - the read-only base-URL display in cloud_plus / direct UI status panels.
  - The auto-create pipeline functions accept it via a new keyword-only `base_url_override: str | None = None` parameter (back-compatible default `None` falls back to `mass.webserver.base_url`).
- The HTTPS-warning label now points users at the new field first ("recommended — doesn't affect MA's local access / HA Ingress") and only mentions the global `Settings → Core → Webserver → Base URL` as a fallback.

## [1.6.6] — 2026-05-05

### Added
- **`MA_YANDEX_DIALOG_CHANNEL` env var override for `DIALOG_CHANNEL`** — the Yandex Dialogs app-store-api channel string for «Навык» is not publicly documented; we ship a best-guess default of `"dialog"`. If a future Yandex change or our guess is wrong and auto-create returns 4xx, users can override the value at MA startup (e.g. `MA_YANDEX_DIALOG_CHANNEL=general`) without editing source code.

### Fixed
- **Webhook test now exercises the production secret-from-path fallback** — `_handle_webhook` reads the URL secret from `request.match_info["secret"]` first, then falls back to parsing the last path segment. The route is registered as an exact path (no `{secret}` variable), so production always hits the fallback. Added `test_secret_parsed_from_path_when_no_match_info` which builds a request with empty `match_info` to cover that branch.

## [1.6.5] — 2026-05-05

### Fixed
- **`asyncio.CancelledError` propagation across all blanket exception handlers around `await` calls** — eight `try / except Exception` blocks (and one `contextlib.suppress(Exception)`) wrapped awaited I/O without re-raising `CancelledError`, which would have absorbed task cancellation during MA shutdown / config-flow abort and turned cancellations into silent no-ops or "not found" responses. Affected sites: `dialogs_player.py` (`mass.music.search` ×2, `get_rotor_station_tracks` ×2, `cmd_power`), `dialogs.py` (`request.json`), `playlists.py` (`iter_library_items`), `__init__.py` (`fetch_playlist_options`). Each now re-raises `asyncio.CancelledError` before the generic handler.

## [1.6.4] — 2026-05-05

### Fixed
- **Inline `# noqa: RUF001` survives the auto-fix workflow** — v1.6.2 added these comments alongside `per-file-ignores` in `ruff.toml`, but the auto-fix CI step (`ruff check --fix`) considered them redundant and stripped them, breaking upstream lint (which has no per-file-ignores). Removed `RUF001` from `per-file-ignores` so the inline noqa is "used" and preserved across syncs. `RUF002` (docstrings) stays in per-file-ignores — upstream doesn't enforce it.

## [1.6.3] — 2026-05-04

### Fixed
- **Webhook secret no longer logged in plain text** — `register_routes` now logs a redacted path (`…<last-4-chars>`) instead of the full secret-bearing URL. Full path is never written to logs.
- **Track URI format corrected for My Wave and genre rotor** — URIs were built as `yandex_music://{instance_id}/track/{id}` (double-nesting the provider name), yielding an unparsable path. Now built as `{instance_id}://track/{id}` matching MA's `create_uri` format (`{provider_instance_id}://{media_type}/{item_id}`).

## [1.6.2] — 2026-05-04

### Fixed
- **Upstream ruff compliance for v1.6.x dialog modules** — added `# noqa: RUF001` inline suppressions on lines with intentional Cyrillic characters flagged as visually ambiguous with Latin lookalikes (`с`, `Н`, `е`, `у`, `а`, `о`, `г`). The upstream server's ruff config has no `per-file-ignores` for these modules, so inline noqa is required.
- **`_build_request` test helper signature** — changed `dict[str, object]` to `dict[str, Any]`; `dict` is invariant so callers passing `dict[str, dict[str, str]]` fail mypy strict.

## [1.6.1] — 2026-05-04

### Fixed
- **Upstream mypy compliance for v1.6.0** — test files copied to `music-assistant/server` failed mypy strict: bare `list`/`dict` generic types in `_SearchResults` dataclass fields now annotated as `list[object]` / `dict[str, object]`; `resolve_player` calls with `MockMass` stub suppressed via `# type: ignore[arg-type]`.

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
- **Background play task uses `mass.create_task`** — replaced bare `asyncio.create_task` with `self._mass.create_task` so the playback task is tracked in the MA lifecycle (cancelled on shutdown/unload) and unhandled exceptions are logged by the framework's task handler. The manual `add_done_callback` / `_on_play_task_done` are no longer needed and have been removed.
- **`resolve_query` docstring corrected** — removed the redundant "caller should tell the caller" phrasing; now reads "the webhook handler should respond with a 'not found' message".

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
