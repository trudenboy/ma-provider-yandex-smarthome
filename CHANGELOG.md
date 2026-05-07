# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [2.1.1] — 2026-05-07

### Fixed

- State-callback error log no longer floods after a freshly auto-created
  skill. Yandex's CDN returns HTTP 5xx for ~1-2 minutes while propagating
  a new skill, then HTTP 400 + UNKNOWN_USER until the user links the
  skill in the Yandex app. Each error class now logs only once per
  "episode": UNKNOWN_USER and HTTP 5xx at WARNING (expected first-run
  states, no traceback), transport / unexpected errors at ERROR with
  traceback (real bugs worth diagnostic detail). Repeats with the same
  fingerprint drop to DEBUG until a different error class arrives or a
  successful callback resets the fingerprint. INFO line confirms
  recovery.

## [2.1.0] — 2026-05-06

### Added

- **Auto-create Smart Home skill** is back. Click *Auto-create Smart Home skill*
  in the cloud_plus or direct config form; after a one-time Yandex Passport
  Device Flow login, the skill is provisioned at `dialogs.yandex.ru`
  programmatically (POST `/apps` → upload logo → patch draft → register
  OAuth app → publish). The resulting `skill_id` populates automatically on
  success. The flow is **resumable** — transient failures checkpoint the
  partial state and the next click resumes from the last completed step.
- Cached Yandex Passport `x_token` (`CONF_AUTH_X_TOKEN`) is restored.
  Subsequent auto-create runs within the token's TTL skip the Device Code
  prompt entirely; only the first attempt asks the user to confirm at
  `ya.ru/device`.
- State-aware action button: label flips between *Create…* / *Retry* /
  *Continue* / *Re-create* based on the current artifacts state, with
  a status banner that surfaces `last_error` on failure.

### Changed

- **Adapted to `ya-dialogs-api 2.0.0`.** The lib's 2.0.0 release renamed
  `skill_type="smart_home"` → `channel="smartHome"` (Yandex API wire value)
  and made OAuth params optional. Smart-home call site now imports
  `SMART_HOME_CHANNEL` and passes `channel=`. Manifest dependency bumped
  to `ya-dialogs-api>=2.0.0`. No behavioural change for users.

### Internal

- New `provider/ma_authenticator.py` — adapter wrapping
  `ya-passport-auth.PassportClient` Device Flow + an MA-flavored activation
  HTML page hosted on `mass.webserver`. Conforms to the `AuthenticatorCM`
  Protocol expected by `ya-dialogs-api.auto_create_skill` (no-arg
  async-context-manager factory yielding an authorized
  `aiohttp.ClientSession`). The bulk of the file is the activation page
  HTML/CSS/JS template, ported verbatim from the deleted `auto_skill.py`.
- New `provider/_smarthome_auto_create.py` — URL derivation
  helpers (`derive_smart_home_urls` returns the five pre-computed values
  required by `auto_create_skill`). Replaces the `derive_*` functions
  previously vendored inside the now-extracted `auto_skill.py`.
- Restored config keys: `CONF_AUTO_CREATE_ARTIFACTS`,
  `CONF_AUTO_CREATE_SESSION_ID`, `CONF_AUTH_X_TOKEN`,
  `CONF_ACTION_AUTO_CREATE`. Existing 2.0.0 manual-setup configs are
  unaffected — these keys default to empty.

### Tests

196 → 224 (+28). New: 12 tests for URL derivations + 16 tests for
authenticator session-id validation and HTML escaping. The Device Flow
body is verified end-to-end against a real Yandex Passport account in V.4
of the rollout plan.

## [2.0.0] — 2026-05-06

### Removed (BREAKING)

- **Yandex Dialogs custom skill (voice control)** moved to a new dedicated provider,
  [`ma-provider-yandex-alice`](https://github.com/trudenboy/ma-provider-yandex-alice).
  All `dialogs*.py` modules, voice config keys (`CONF_DIALOG_*`), the
  `auto_create_dialog_skill` and `rename_dialog_skill` actions, and the
  experimental dialog-skill section of the config form have been removed from
  this repository. This repository now focuses exclusively on the Yandex
  **Smart Home** device-bridge integration.
- **Auto-create Smart Home skill** action and its config UI entries (Device
  Flow OAuth + automated skill registration) are temporarily removed. The
  underlying `auto_skill.py` was extracted into the new `ya-dialogs-api` PyPI
  package to be shared between this provider and `ma-provider-yandex-alice`,
  but the new lib's API contract differs and re-wiring the config flow is
  scheduled for **2.1.0**. Manual skill setup (paste `skill_id` + OAuth
  token from the dev console) continues to work and is now the only option.

### Migration

If you previously used the **voice skill** (Dialogs custom skill — *«Алиса,
попроси Music Assistant включи джаз на кухне»* etc.):

1. Install [`ma-provider-yandex-alice`](https://github.com/trudenboy/ma-provider-yandex-alice).
2. Settings → Add Provider → *Yandex Alice*. Paste the same `skill_id`,
   skill OAuth token, and webhook secret you used here. Re-pick the players
   you want voice-controlled (uses the same MA Player Filter UI).
3. The next time the form for `ma-provider-yandex-smarthome` is opened in
   2.0.0, the now-removed voice fields silently disappear; saved values for
   `dialog_skill_*` keys are ignored on load.

If you only used the **Smart Home device bridge** (Alice voice commands like
*«Алиса, поставь на паузу Кухню»* via the standard Smart Home protocol —
no custom skill webhook), no action required: your existing config and
device set are unaffected.

If you used the previous **auto-create Smart Home skill** action: that
button is gone in 2.0.0. To set up a skill manually, follow the link in
the config form to `https://dialogs.yandex.ru/developer`, create a Smart
Home skill against your account, and paste the resulting `skill_id` + OAuth
token into this provider. Auto-create returns in 2.1.0.

### Changed

- New runtime dependency: [`ya-dialogs-api`](https://pypi.org/project/ya-dialogs-api/)
  re-exports `SecretStr` from `ya-passport-auth`. The provider's runtime
  imports `SecretStr` from there instead of the deleted `provider/_compat.py`.
  No user-visible behaviour change.

### Files removed

- `provider/dialogs.py` (1311 LOC), `dialogs_control.py` (468), `dialogs_nlu.py` (474),
  `dialogs_player.py` (313) — moved to `ma-provider-yandex-alice`.
- `provider/auto_skill.py` (1630 LOC), `auto_skill_state.py` (122),
  `auto_skill_logo.png`, `_compat.py` — extracted to the
  `ya-dialogs-api` PyPI package.
- `provider/auto_skill_ui.py` (1124 LOC) and `tests/test_auto_skill_ui.py`
  removed; the simplified config form lives directly in `provider/__init__.py`.
- `tests/test_dialogs*.py`, `tests/test_auto_skill*.py`, `tests/test_config_actions.py`,
  `tests/test_smarthome_config_ui.py` — removed alongside the source files
  they covered.
- `docs/VOICE_COMMANDS.md`, `docs/VOICE_UX_RESEARCH.md` — moved to alice repo.

### Test surface

`pytest -q` runs **196 tests** (down from 629 at v1.9.1). Coverage on the
remaining smart-home code (cloud / direct / handlers / device / notifier /
schema) is unaffected — every deleted test exercised a deleted module.

## [1.9.1] — 2026-05-06

Three Copilot review findings on the v1.9.0 voice-commands batch.

### Fixed
- **`enqueue_option` survives the disambiguation re-entry.** When the user said *«добавь Iron Maiden»* with an ambiguous player hint, the disambiguation prompt saved a `pending_command` without the enqueue intent — so after the user picked a player the replay hit `play_media()` with no option, defaulting to REPLACE instead of ADD. Now `pending_command` carries `enqueue_option`, and `_try_resume_pending` restores it on every `ParsedCommand` rebuild path (success replay + still-ambiguous re-prompt + ordinal-out-of-range re-prompt). New test `test_add_to_queue_preserved_through_disambiguation` walks the full two-turn round-trip.
- **Removed dead `hint = …` assignment in the `now_playing` branch.** Copilot caught a leftover from the early refactor — the variable was set but never read.

### Docs
- **`play_for_alice` docstring corrected.** It claimed *"add and next skip powering the player on"* but the implementation always powers the player on when it's off. Aligned the docstring with reality and added the rationale (voice intent is unambiguous — user just asked for music, so an off player needs to wake up).

## [1.9.0] — 2026-05-06

Six new voice commands in one PR — driven by the gap analysis between MA's APIs and what we covered. All backed by stable MA controllers; no architectural changes.

### Added
- **`now_playing` info query.** *"Что играет"* / *"что играет на кухне"* / *"что мы слушаем"* / *"что за песня"* / *"какой трек"* — Alice replies with `queue.current_item.name` (MA pre-formats as *"Artist - Title"*, or stream title for radio). Idle queue → *"На <player> сейчас ничего не играет."*
- **Shuffle on/off.** *"перемешай"* / *"включи перемешивание"* / *"случайный порядок"* → `mass.player_queues.set_shuffle(qid, True)`. *"выключи перемешивание"* / *"не перемешивай"* / *"по порядку"* → `set_shuffle(qid, False)`.
- **Repeat mode.** *"повтор песни"* / *"повтори трек"* / *"повтор эту"* → `RepeatMode.ONE`. *"повтор всё"* / *"повтор очередь"* / *"повторяй"* / *"включи повтор"* → `RepeatMode.ALL`. *"выключи повтор"* / *"не повторяй"* → `RepeatMode.OFF`. NB: `set_repeat` is a *sync* MA method, not async — dispatched without `await`.
- **Seek (relative + absolute).** *"перемотай вперёд на 30 секунд"* / *"вперёд на 1 минуту"* / *"назад на 5 секунд"* — relative skip via `mass.player_queues.skip(qid, ±N)`. Minutes auto-multiplied by 60. Bare-digit forms work too (*"вперёд 30"*). *"к началу"* / *"в начало"* / *"начни трек заново"* → absolute `seek(qid, position=0)`.
- **Transfer playback.** *"переведи на спальню"* / *"перенеси на спальню"* / *"продолжи в спальне"* — moves the queue from the saved default player to the named target via `mass.player_queues.transfer_queue(source_queue_id, target_queue_id)`. Updates `last_player_id` to the target across all three state tiers + cache. Edge cases: target = current → *"Уже играет на …"*; no saved default → *"Сначала включи музыку на колонке"*; ambiguous target → clarification prompt.
- **Add-to-queue.** *"добавь Metallica"* / *"добавьте альбом Black Album"* / *"добавить Iron Maiden на кухне"* — new `enqueue_option: Literal["replace","next","add"] | None` field on `ParsedCommand`; *"добавь"*-prefixed commands set it to `"add"`, which `play_for_alice` maps to `QueueOption.ADD` on `play_media`. Confirmation: *"Добавил <query> в очередь на <player>"*. `radio_mode` forced off — you add a track, not a station.

### Implementation notes
- `ControlAction` Literal extended with 10 new values: `now_playing`, `shuffle_on/off`, `repeat_off/one/all`, `seek_forward/back/start`, `transfer`. `now_playing` and `transfer` are special-cased in `_handle_control` (need handler-side logic — live data / cross-player); the rest dispatch through `execute_control`.
- `ParsedCommand.enqueue_option` is optional with default `None`, so existing callers and tests are unaffected.
- New seek-pattern parsers extract digit + optional Russian unit (*секунд / секунду / секунды* / *минут / минуту / минуты*); the `ParsedControl.value` carries seconds (negated at dispatch for `seek_back`).
- `transfer` captures the target name into `ParsedControl.player_hint`; SOURCE comes from the caller's saved default. Multi-match target → clarification prompt (the disambiguation flow is play-coupled and not yet wired to replay transfers).
- 83 new test cases (pattern coverage + execute_control units + 12 E2E in `test_dialogs.py`); 628 passing total. ruff + mypy clean.

## [1.8.10] — 2026-05-06

User feedback: после disambiguation последующие play-команды без явного hint всегда играют на выбранной колонке (это by design — `last_player_id` сохраняется во всех state-tier'ах для удобства). Добавлена голосовая команда чтобы явно сбросить выбор.

### Added
- **Voice command `forget_player`.** Phrasings recognised: *"забудь колонку"*, *"сбрось колонку"*, *"забудь плеер"*, *"забудь выбор"*, *"сбрось выбор"*, *"выбери колонку заново"*, *"поменяй колонку"*, *"сменить колонку"*. Clears `last_player_id` from `state.session`, `state.application`, AND the in-process cache, plus emits `user_state_update.preferred_player_id = None` (Yandex protocol: a `None` value tells the platform to delete the key from merged user-scoped state). Response: *"Хорошо, забыл колонку. В следующий раз спрошу."* The next play command without an explicit hint will then re-ask via the disambiguation flow. Note: the user can also override the saved default at any time by simply naming the player explicitly (*"включи джаз на спальне"*) — `forget_player` is the way to opt back into being asked.

## [1.8.9] — 2026-05-06

Three Copilot review findings on the upstream PR — all docs/comment fixes, no behaviour change.

### Docs
- **Module docstring of `provider/dialogs.py` describes the actual three-tier state strategy.** The previous text claimed *"the handler does not keep any in-process LRU"* — true before v1.8.8, contradictory after. Now describes session → application → in-process cache with the LRU/TTL details, so a maintainer or security reviewer reading the file gets the right picture.
- **`Exposed Playlists` config description corrected.** Previous text said playlists *"appear as input_source mode slots one..ten on every exposed player, in the order you select them"* — implied slot-stable across players. Reality: native sources fill slots first, playlists fill the remainder up to the 10-slot cap, so a player with ≥10 native sources gets no playlist slots and the playlist→slot mapping varies between players. Description now spells this out so users don't expect playlist slot N to mean the same thing on every player.
- **Removed forward-version reference in code comment.** A comment in `dialogs.py` near the in-process cache constants said *"…until v1.8.8 added this cache"* — Copilot rightly flagged forward/version-coupled comments as fragile during backports. Reworded without the version mention.

## [1.8.8] — 2026-05-06

User shared a dev-console transcript that conclusively diagnosed the disambiguation-loop bug on Yandex Stations. The actual webhook request body for **every** turn after the first arrived **without a `state` field at all** — Yandex didn't echo back `state.session` OR `state.application` despite both being set on the previous response. The v1.8.5 application-state mirror was no help because Yandex was dropping that bucket too. Adding a third-tier in-process state cache fixes it.

### Fixed
- **In-process state cache as third-tier fallback when Yandex drops `state.*`.** Read priority is now `state.session` → `state.application` → in-process LRU cache (keyed by `session.user.user_id` if present, else `session.application.application_id`, else `session_id`). The cache has a 5-minute TTL (matching Alice's session inactivity timeout) and a 200-entry LRU cap. Every state-bearing response (greeting, slot-elicit, disambig prompt, play, control) writes the merged state into the cache via `_yandex_response`. So when the next turn arrives with no `state` at all (Yandex Station behaviour reproduced from the dev-console transcript), the handler still recovers `pending_command` / `awaiting_query` / `awaiting_player_id` / `last_player_id` and the disambiguation flow resolves correctly.
- **DEBUG-recv log shows which tier provided the pending state.** New format: `pending=True (session=False app=False cache=True) …`. Lets users diagnose at a glance which fallback their device is hitting.

## [1.8.7] — 2026-05-06

One Copilot review finding from upstream PR #3834 addressed.

### Fixed
- **`execute_control` now has an explicit `list_players` branch.** The action exists in the `ControlAction` `Literal` for typing convenience, but it's an *informational* query that `DialogsWebhookHandler._handle_control` short-circuits before dispatch. Previously a stray call into `execute_control` with `action="list_players"` would silently no-op (no `if/elif` matched) — easy to miss if a future caller bug routed it there. Now the function emits a `WARNING` log and returns; new test `test_list_players_is_a_safe_noop_with_warning` pins the contract. Defensive fix only — no behaviour change on the happy path.

## [1.8.6] — 2026-05-05

Three Copilot review findings on the upstream PR addressed.

### Fixed
- **Player-suffix splitter no longer eats content titles starting with «На».** The trailing `\s+на\s+(.+?)\s*$` regex used to greedily strip *"на заре"* from *"включи песню На заре"*, leaving the parser with an unusable `query="песню"` and a fake `player_hint="заре"`. Now `parse_command` checks the residual after the split: if a `player_hint` was extracted but the surviving intent collapsed to a kind-marker word (`песню` / `альбом` / `плейлист` / `артиста` / etc. — all listed in the new `_KIND_MARKER_WORDS` frozenset), the function recurses with `_split_player_hint=False` and re-parses without the suffix split. So *"включи песню На заре"* now parses as `kind=track, query="на заре", hint=None` — and a subsequent search finds the track. Genuine `<query> на <player>` (e.g. *"включи песню Yesterday на кухне"*) keeps its hint because the residual *"песню Yesterday"* is not a marker-only string.
- **Slot elicitation triggers when the query slot is empty even if a player hint was given.** Saying *"включи на кухне"* used to fall through to *"Не нашёл такую музыку: ."* because the elicitation gate required `parsed.player_hint is None`. Now elicitation fires whenever `parsed.query == ""`; if the hint resolves unambiguously to a single exposed player, the player_id is saved as `awaiting_player_id` (mirrored to both `state.session` and `state.application`) and the next-turn `_handle_webhook` restores it as `default_id`. Result: *"Включи на кухне." → "Что включить?" → "Iron Maiden"* plays Iron Maiden on the kitchen player without the user re-stating *"на кухне"*.

### Removed
- **`DialogsSkillCreator.get_operations` dropped as dead code.** The polling helper that consumed it (`_unused_wait_for_deploy_completed_DEPRECATED`) was deleted in v1.7.18 (async-deploy is non-blocking — the user tracks status via the dev-console link surfaced in the UI). The `get_operations` method has been unreferenced since then; removing it cuts the maintenance surface (Yandex API drift, response-shape variants) for a feature that no longer exists.

## [1.8.5] — 2026-05-05

User report: на screenless Яндекс-Станциях disambiguation prompt получает голосовой ответ ("Проигрыватель"), но навык переспрашивает прежним промптом, и так в цикле, пока не падает в "Не понял команду". С прямой формой "включи джаз на проигрывателе" всё работает — то есть resolver и стеммер сами по себе нормальные.

### Fixed
- **`pending_command` дублируется в `state.application` как fallback к `state.session`.** Корневая причина зацикливания: некоторые Yandex-устройства (особенно screenless Stations) не возвращают `state.session` между SimpleUtterance-turn-ами в одной открытой сессии — мы получаем второй turn без `pending_command`, попадаем в "no-hint + no-default disambig" branch, который заново показывает тот же prompt. Теперь disambiguation-ответ сохраняет `pending_command` (и `awaiting_query`) одновременно в `state.session` И `state.application`. Application-tier per-device, переживает session-сброс, и Yandex эту секцию возвращает надёжно. `_handle_webhook` читает обе секции, отдаёт приоритет session, fallback на application. Успешный play / control сбрасывает pending в обоих tier-ах. Webhook-recv DEBUG-лог теперь показывает наличие `pending_command` отдельно для session и application — это поможет в будущей диагностике.

## [1.8.4] — 2026-05-05

User-reported issue: на screenless Яндекс-Станциях voice-first disambiguation prompt получает голосовой ответ, но навык переспрашивает вместо того чтобы запустить выбранную колонку. Три причины:

### Fixed
- **Accusative-case Russian endings now stripped by the player-name stemmer.** Added `ую` (feminine adjective accusative — *"большую"*, *"маленькую"*) and `ю` (feminine noun accusative — *"Кухню"*, *"Спальню"*) to `_INFLECTION_SUFFIXES`. Without these, an answer like *"большую"* couldn't match *"Кухня большая"* via free-text resolution: stem of *"большую"* stayed *"большую"* (no matching suffix) while stem of *"Кухня большая"* was *"кухн больш"* — neither `contains` nor `startswith` produced a hit, so the resolver returned `[]`. The user heard the prompt repeated.
- **Ordinal regex tolerates leading filler words.** *"выбираю первую"*, *"хочу вторую"*, *"давай первую"* now resolve to the right candidate. Previously the strict `^…\b` anchor required the ordinal word at position 0, missing every padded reply. The patterns now use word-prefix `\bперв\w*\b` (etc.) with `re.search` — catches every morphological form (нач. с *перв*, *втор*, *треть*, *четвёрт*, *пят*) without enumerating each, regardless of leading or trailing words. Cardinal numbers (*один*, *два*, …) and digits stay anchored whole-utterance to avoid false positives ("у меня один вариант" must NOT pick the first candidate).
- **Reordered `_try_resume_pending` resolution steps** so named answers always win over positional ones. New order: `ButtonPressed` → free-text (named distinguishers like *"Кухня большая"* / *"большая"*) → ordinal (*"первая"*, *"выбираю первую"*). The previous ordinal-first order would have mis-resolved a hypothetical *"Спальня первая"*-named player to whatever happened to be `candidate_ids[0]` instead of matching by name. Three new tests cover the regression: `test_voice_ordinal_with_filler`, `test_voice_accusative_adjective`, `test_voice_accusative_noun`.

## [1.8.3] — 2026-05-05

Upstream-sync lint fix. The upstream `music-assistant/server` CI ran with the v1.8.2 sync and surfaced 57 ruff errors + 3 mypy errors that this repo's local checks were silencing via `ruff.toml` rules that don't propagate when the sync workflow copies provider files into `music_assistant/providers/yandex_smarthome/`. All purely lint configuration — no behaviour change.

### Fixed
- **`# ruff: noqa: RUF001, RUF002, RUF003` directives moved into the source files.** Previously the per-file Cyrillic-string suppression lived in `ruff.toml`'s `[lint.per-file-ignores]` block. That config is local-only — upstream's lint pre-commit runs against its own ruff config which doesn't have those entries, so the sync surfaced ~50 RUF001/002/003 errors. Each Cyrillic-heavy module now carries the directive at the top of the file (`provider/dialogs.py`, `dialogs_control.py`, `dialogs_nlu.py`, `dialogs_player.py`, plus `tests/test_dialogs*.py`). `ruff.toml` correspondingly drops the per-file overrides.
- **`# noqa: PLR0915` re-added to three functions** — `provider/__init__.py:get_config_entries` (59 stmts), `provider/auto_skill.py:_execute_pipeline` (59 stmts), `provider/device.py:execute_capability_action` (55 stmts). All exceed the 50-statement default cap; ruff had stripped the markers earlier when this repo's local cap was bumped to 60. Local cap restored to 50 to match upstream.
- **`tests/test_dialogs.py:_response_body` mypy `no-any-return`** fixed by binding the `json.loads` result to an explicitly-typed local before returning.

## [1.8.2] — 2026-05-05

Voice-first disambiguation. Suggestion buttons aren't visible on screenless Yandex Stations, so the disambiguation prompt now leads with a voice channel. Two Copilot-review findings on the initial implementation also rolled in.

### Changed
- **Disambiguation prompt is voice-first.** Previous text was *"На какой колонке: A, B?"* — fine on a phone screen but unhelpful on smart speakers, where the user couldn't see (or tap) the buttons. New prompt enumerates candidates with Russian ordinals and explicitly asks for a voice answer:

  > На какой колонке? Первая — A, вторая — B. Скажи название или номер.

  Buttons stay on the response for screen surfaces but are no longer the primary channel.

### Added
- **Voice ordinal disambiguation.** A new `_parse_ordinal_choice(text)` helper recognises *первая / первый / первое / первую / один / 1*, …, *пятая* / *пять* / *5* (incl. `номер N`-prefix and `четвёртая` / `четвертая` spelling variants) as 0-based indices into the candidate list. The handler tries the ordinal **first** in `_try_resume_pending`, before button payload, before free-text — so on a screenless device the user can answer the disambiguation prompt by voice alone.
- **Disambiguation `pending_command` carries the candidate IDs.** New `candidate_ids: list[str]` field saved alongside `kind` / `query` / `radio_mode`. Used by `_try_resume_pending` for two purposes: (a) ordinal lookup `candidate_ids[index]`, (b) **narrowing free-text resolution** to just the saved candidate set so a one-word distinguisher like *"большая"* picks the right player even when other unrelated players elsewhere also match.

### Fixed
- **Out-of-range / unresolvable ordinal re-asks instead of falling through.** Previously, if the user said *"третья"* with only 2 candidates (or picked an ordinal whose target player had been removed since the buttons were sent), the handler skipped the ordinal block and the free-text fallback parsed *"третья"* as a play-search query — leading to playback of *"третья"* on a default player. Fix: a recognised ordinal that can't resolve to an exposed player now triggers a re-ask of the disambiguation prompt with whatever candidates remain exposed. If none remain, falls through to the regular "не нашёл колонку" path.

## [1.8.1] — 2026-05-05

Six Copilot-review findings on the v1.8.0 voice-UX refactor + observability + a "list speakers" voice query.

### Fixed
- **`_yandex_response.user_id` echo falls back to nested `session.user.user_id`.** Yandex envelopes carry both a deprecated root `session.user_id` and a nested `session.user.user_id` (set when the user is account-linked). Previously we only read the root, which would emit an empty echo if a future Yandex API revision drops the deprecated field. Now uses the root with a fallback to the nested form.
- **Disambiguation no longer leaks `awaiting_query` into the next turn.** `_build_disambiguation_response` previously copied `session_state_in` verbatim. If the multi-match was reached via slot elicitation (`Включи.` → `Что включить?` → `Metallica на кухне` → multiple "Кухня"), `awaiting_query=True` stayed in the response state. The user's answer to the disambiguation question (e.g. *"Кухня маленькая"*) would then get auto-prefixed with `включи `, breaking pending-command resolution. Fix: clear both `awaiting_query` and `pending_command` via `_without_pending(...)` before writing the new pending entry.
- **Control commands without a player hint now ask "на какой колонке?".** Saying *"пауза"* on a fresh multi-player install (no `default_id` in any state tier) used to respond with the misleading `Не нашёл колонку «(не указано)»`. The message now distinguishes "hint given but unknown" (kept the same) from "no hint, ambiguous" (new: *"Скажи, на какой колонке. Например: пауза на кухне."*).
- **Control phrases work during slot-elicitation.** Previously the `awaiting_query` synthesis ran *before* `parse_control`, so a user answering *"Что включить?"* with a control phrase like *"пауза на кухне"* got their utterance prepended with `включи ` and the resulting `включи пауза на кухне` no longer matched any control pattern. Now `parse_control` runs first; if it matches, the handler clears `awaiting_query` / `pending_command` and dispatches the control action.
- **Play branch: no hint + no default + multiple players → disambiguation prompt.** Same UX bug as the control branch one (above) but on the play side. Saying *"включи Metallica"* on a fresh multi-player install used to reply with `Не нашёл колонку «(не указано)»`. Now the handler detects this case, calls `list_exposed_players(...)` to get all candidates, and offers disambiguation buttons just like the explicit-hint multi-match flow.
- **`ButtonPressed.payload.player_id` validated against the exposed-player set.** `_try_resume_pending` previously called `mass.players.get_player(pid)` directly with whatever `payload.player_id` came back. Now the player_id is looked up against `list_exposed_players(...)` — guards against stale payloads (player disabled / un-exposed since the buttons were sent) and crafted payloads that target unavailable players. Defence-in-depth on top of the existing `body.session.skill_id` check.

### Added
- **Voice query "сколько колонок видишь" / "какие колонки".** New informational `list_players` control action — Alice answers with the count and names of the speakers exposed to the skill. Recognised phrasings (no `на <player>` suffix; not dispatched to MA): `сколько колонок (ты)? (видишь|знаешь)?`, `какие колонки (ты)? (видишь|знаешь|есть)?`, `какие у тебя колонки`, `перечисли колонки`, `список колонок`, `покажи колонки`, `назови колонки`. Response uses correct Russian quantitative agreement: *"Вижу одну колонку: Кухня."* / *"Вижу 3 колонки: Кухня, Спальня, Гостиная."* / *"Вижу 5 колонок: …"*.
- **DEBUG-level observability of the dialog pipeline.** Every webhook request now logs a one-line summary on entry (`Webhook recv: cmd=… req_type=… is_new=… pending=… awaiting=… default_player=… session_id=…`) and one log line per branch decision (awaiting-query synthesis, pending-command resume / fall-through, slot-elicit prompt, play-branch resolution outcome, control-branch outcome). The `resolve_player_candidates` resolver now emits a single summary line on **every** call (instead of only when a hint is given) describing the chosen tier (`exact` / `startswith` / `contains` / `generic-word` / `none`), the candidate count, and the names of the candidates returned — so a "не нашёл колонку" reply has a matching DEBUG line explaining *why*. Failures (no player resolved) are also logged at INFO.

### Docs
- **Wire-format snippet in `VOICE_COMMANDS.md` accurately describes the two `user_id` fields.** Root `session.user_id` clarified as deprecated-but-always-present (per-app-instance); nested `session.user.user_id` clarified as account-linked-only.

## [1.8.0] — 2026-05-05

Voice-UX overhaul of the experimental Dialogs skill, driven by the research write-up in [`docs/VOICE_UX_RESEARCH.md`](docs/VOICE_UX_RESEARCH.md). Seven P0 changes — together they turn the skill from "works most of the time" into "predictable" without any breaking config changes.

### Added
- **Playback control via the Dialogs skill (P0.6).** Pause / resume / stop / next / previous / volume up-down / volume set / mute / unmute now go through the same `Алиса, попроси <skill> …` path. New phrases recognised:
  - `пауза`, `на паузу`, `поставь на паузу`, `останови музыку`
  - `продолжи`, `включи снова`, `возобнови`
  - `стоп`, `останови`, `выключи`, `выключи музыку`
  - `следующая` / `следующий трек` / `дальше` / `переключи`
  - `предыдущая` / `предыдущий трек` / `назад` / `вернись`
  - `громче` / `сделай громче` / `прибавь` / `прибавь громкость`
  - `тише` / `сделай тише` / `убавь` / `убавь громкость`
  - `громкость 50` / `громкость на 30` / `сделай громкость 75` / `громкость на 30 процентов` (clamped to 0–100)
  - `приглуши` / `выключи звук` / `беззвучно` (mute) / `включи звук` / `сделай звук` (unmute)
  - All accept the trailing `на <player>` suffix; without it, the last-used player is reused.
- **Disambiguation prompt with suggestion buttons (P0.3).** When a player hint matches multiple candidates, the response is now `На какой колонке: A, B, C?` with `end_session=False` and one button per candidate (`hide=True` so they vanish after one tap). Pressing the button or naming the player on the next turn replays the saved play intent. Previously the resolver silently picked the first candidate alphabetically.
- **Slot elicitation for bare verbs (P0.4).** Saying just `Включи.` (no query, no player) now replies `Что включить? Можно сказать имя артиста, песни или плейлиста.` with `awaiting_query=true` in `state.session`. The next utterance is treated as the play query — including longer forms like `песню Yesterday` or `альбом Black Album`. Avoids the "Не нашёл такую музыку: " dead-end.
- **More play-verb synonyms (P0.5).** `найди` / `найти` / `открой` / `открыть` / `покажи` / `показать` are now stripped same as `включи` so `найди Metallica`, `открой плейлист утренний джаз` etc. work.
- **Search retries with stem-stripped query (P0.7).** Russian noun/adjective endings on the query (`включи металлику`, `включи песню утреннюю`) used to miss the music index because providers store nominative forms (`Металлика`, `утреннее`). After an empty result, the resolver now retries with the same suffix-stripping the player resolver uses (`металлику` → `металлик` → matches). ASCII-only queries skip the retry.
- **Stress-mark TTS dictionary (P0.2).** Response `tts` is now distinct from `text` and includes `+` accent marks for the most common Alice mispronunciations (`включ+аю`, `гр+омче`, `кол+онке`, etc.). Non-Russian band/track names are still passed verbatim — a phoneme dictionary for those is tracked as P2.
- **Two new Russian inflection endings recognised** by the player-name and search stemmer: `я` (feminine noun nominative — *"Кухня"*, *"Спальня"*) and `ая` (feminine adjective — *"большая"*, *"маленькая"*). Lets the multi-word player matching land *"на кухне маленькой"* → *"Кухня маленькая"* without an exact prefix.

### Changed
- **Session memory now persists via Yandex's state envelope (P0.1).** The dialog handler no longer keeps an in-memory `OrderedDict` LRU. Last-used player is round-tripped through `state.session.last_player_id`, `state.application.last_player_id`, and (when the user is account-linked) `state.user.preferred_player_id`. The `application` tier survives plugin reloads and MA restarts; the `user` tier survives across devices for the same Yandex account. Default-resolution priority: session > application > user.
- **`resolve_player(...)` returns `None` on tied matches.** Multi-candidate hints used to silently pick the first by name and log a warning; that behaviour was the source of the "wrong room played" bug. Use the new `resolve_player_candidates(...)` to surface the ambiguity (the dialog handler does — see P0.3 above).
- **The play-verb regex now matches end-of-string,** so a lone `включи` is fully stripped instead of leaving the verb in the query. Required to reach the slot-elicitation branch (P0.4).

### Removed
- **In-memory session-cache constants** — `DIALOG_SESSION_CACHE_MAX`, `DIALOG_SESSION_TTL_SEC` and the `OrderedDict` they backed are gone. State is now in Yandex.

## [1.7.21] — 2026-05-05

### Fixed
- **"включи Iron Maiden" no longer plays a random playlist.** Three issues compounded:
  1. **Verb regex missed infinitives.** Yandex's voice-to-text sometimes returns the infinitive (`включить`, `поставить`, `запустить`) even if the user spoke the imperative. The regex only matched imperatives, so the unparsed verb leaked into the search query (`query="включить iron maiden"`) which made `mass.music.search` return arbitrary matches. Now also accepts infinitives plus `сыграй(те)?`, `сыграть`, `играй(те)?`, `послушай(те)?`, `послушать`.
  2. **`kind=search` preferred playlists over artists.** The result picker order was `playlists > albums > artists > tracks` for unqualified queries, so a tangentially-matching playlist (e.g. *"Тяжелее, чем танк"*) won over the actual artist. Reordered to `artists > albums > tracks > playlists` — when users say a band name without the `плейлист` / `альбом` qualifier they almost always want the artist.
  3. **`kind=search` ran without `radio_mode`.** Even when the picker did pick the right artist or track, playback would stop after one item. Now `radio_mode=True` for `search` so artists and tracks both start a continuous radio (matches the typical "play X" intent).

### Added
- **`resolve_player` debug log** — when MA log level is DEBUG for the dialog provider, every voice-command resolution now logs the raw hint, the normalised needle, all candidate (raw_name, normalised_name) pairs, and how many matched at each tier (exact / startswith / contains). Lets users see exactly why a hint failed to resolve to a player.

### Added
- **Generic Russian "speaker" / "player" words resolve to the default / only exposed player.** If the user says *"на колонке"*, *"на проигрывателе"*, *"на плеере"*, *"на динамике"* etc. instead of a specific player name, `resolve_player` now treats it as "any speaker" and returns either the configured default player (last-used in this session, or `default_id`) or the only exposed candidate when there's just one. Previously these generic words failed fuzzy matching and Alice replied "не нашёл колонку". Stems covered: `колонк`, `плеер`, `пле`, `проигрыватель`, `проигрывател`, `динамик`, `акустик`, `устройств`.

### Note
- Voice-command player names match against MA's `player.name` (not the alias the user might have set in the Yandex Smart Home app — Yandex doesn't forward those into the dialog skill payload). Use the generic words above, the player's MA name, or rename the player in MA itself.

### Changed
- **Auto-create no longer blocks waiting for `deployCompleted`.** v1.7.17 added a polling loop after `request_deploy`; testing shows Yandex's moderation queue can take 5–10+ minutes for private aliceSkills under typical load, which is too long to block a config-flow action. Pipeline now returns as soon as `request_deploy` is accepted (200) and lets the user track on-air status via the dev-console link surfaced in the UI. The polling helper is kept in the codebase as a deprecated debugging aid.
- **UI link label calls out the async-deploy delay** and tells the user that the skill is unusable on Alice until the dev console shows «На воздухе».

### Added
- **Direct link to the skill in Yandex Dialogs dev console.** Once a dialog skill has been auto-created, the plugin's config UI now shows a clickable URL of the form `https://dialogs.yandex.ru/developer/skills/<skill_id>` so the user can jump to the draft view (and verify the on-air status indicator at the top of the page).
- **Poll deploy completion after `request_deploy`.** Yandex's `request_deploy` returns immediately, but the actual publish takes a few seconds (private skills) up to ~minute (under load). The pipeline now polls `/apps/<id>/operations` every 3 s with a 120 s ceiling, looking for a `deployCompleted` event for the just-deployed skill_id; logs an INFO line when seen, a WARNING on `deployFailed` or timeout (the request itself was accepted, Yandex finishes on its side either way).

### Fixed
- **`structuredExamples` shape captured correctly via DevTools.** The previous guess `{"phrase": "..."}` was completely wrong — the real shape is `{"marker": <activator>, "activationPhrase": <skill_name>, "request": <phrase>, "is_valid": true}`, captured from a successful `PATCH /draft/update` issued by the Yandex Dialogs dev console after the user filled the form. This wrong shape was the actual cause of all the previous silent HTTP 400 + empty-body rejections (not the category, not the email — those worked fine, but Yandex aborts validation of the whole publishingSettings block when *any* nested validator fails). Reverted v1.7.14's split-PATCH workaround now that we know the right shape: dialog draft is sent in a single PATCH again.

### Fixed
- **Dialogs webhook docstring matches actual routing.** The module docstring claimed the route was `POST /api/yandex_dialogs/webhook/{secret}` (templated `{secret}` variable), but `register_routes` registers the secret as a *literal* path segment baked into the URL string at registration time. In production `request.match_info` is empty and the secret is parsed from `request.path`. Updated the docstring so future contributors don't accidentally remove the production hot-path branch. (Thanks Copilot review.)
- **`device.execute_capability_action` lets `CancelledError` propagate.** The broad `except Exception` in the action dispatcher converted shutdown / config-flow cancellations into an `INTERNAL_ERROR` action result. Added an explicit `except asyncio.CancelledError: raise` before the generic handler so cooperative cancellation propagates untouched.

### Fixed
- **Dialog skill `update_draft` no longer rejected by Yandex.** Despite the v1.7.12 fix to use the correct `category="music_audio"` value, Yandex was still returning HTTP 400 with an empty body — additional fields in `publishingSettings` (almost certainly `email=""`, but the API does not say) silently fail validation. Splitting the draft update into two PATCH passes:
  1. Initial draft PATCH — only the fields we genuinely need to set (name, activation phrases, voice, backend URL, access flags). No `publishingSettings` at all, so Yandex keeps its server-side defaults (e.g. user's email pre-filled from Passport).
  2. Pre-deploy PATCH — sends the `publishingSettings` block (category, description, examples, developerName) right before `request_deploy`. If this second PATCH fails, the skill is still created and reachable in the Yandex Dialogs dev console; the user can finish the form there.
- **Dialog skill auto-create no longer crashes if `request_deploy` fails.** Yandex's `request_deploy` enforces strict validation rules on dialog skills that we don't fully understand yet — and the pre-deploy publishingSettings PATCH may itself fail. In both cases the auto-create now completes with `state=DONE` (skill_id saved, OAuth attached) and logs a WARNING with instructions; users can finish the publish step in the Yandex Dialogs dev console.

### Fixed
- **Empty-body 400 diagnostic no longer dumps full response headers.** v1.7.5 logged the entire `resp.headers` dict at WARNING when Yandex returned a 4xx with an empty body, which leaked `Set-Cookie` (and any other header Yandex sets in the response) into MA's log file. Now logs only a small safe subset: `Content-Type`, `Content-Length`, `X-Request-Id`, `X-RateLimit-Remaining`, `X-RateLimit-Limit`.

### Fixed
- **Dialog skill `category` value corrected to `"music_audio"`.** The previous best-guess `"music_and_sounds"` is not a recognised Yandex category — `PATCH /draft/update` was returning HTTP 400 with an empty body (no JSON `validationErrors` payload) which made the failure cause invisible. The correct API key for the *«Аудио и подкасты»* category was captured from `GET /snapshot` (which exposes the full catalogue: `[{"type":"music_audio","title":"Аудио и подкасты"}, ...]`). Other categories also have non-obvious mappings (e.g. *«Игры и развлечения»* → `games_trivia_accessories`, *«Видео»* → `movies_tv`).

### Fixed
- **DIALOG_CHANNEL hint comments / user-facing text reflect the actual default** — `_run_auto_create_dialog_action` previously claimed the default channel was `"dialog"` (it had been the placeholder before v1.7.6) and suggested fall-back values (`general`, `alice`, `skill`) for an override. The default is now `"aliceSkill"` (captured from a live `POST /apps` in the dev console) and the hint text and suggested overrides have been updated to match.
- **`StateNotifier._send_state_callback` logs all transport-level failures.** Previously only `RuntimeError` was caught/logged, so `aiohttp.ClientError`, DNS failures, connection resets, etc. bubbled up without the `"State callback error"` log path — making production failures harder to diagnose. Now catches `Exception` (lets `asyncio.CancelledError` propagate) and re-raises after logging so the caller's re-queue logic still runs.

### Fixed
- **`structuredExamples` populated for `request_deploy`** — Yandex enforces non-empty structured examples in `publishingSettings.structuredExamples` at deploy time, even for private skills (quality check), failing with `400 "Draft is not allowed to deploy"` / `validationErrors: [{"key":"publishingSettings/structuredExamples","type":"VALIDATION_ERROR"}]`. The payload now ships three sample phrases that actually match the patterns recognised by `parse_command` in `dialogs_nlu.py` (so the published catalogue text reflects what users can really say).

### Fixed
- **Pre-validate dialog skill name has ≥2 words.** Yandex Dialogs rejects single-word skill names with `400 Validation error: "Название должно содержать минимум два слова"`, but the validation runs at `update_draft` step — *after* `create_app` already produced a half-broken skill (and Device Flow already burned a fresh device code). The plugin now checks `len(skill_name.split()) >= 2` before kicking off the pipeline; if violated, surfaces an immediate `FAILED` artifact with a clear message and returns without creating anything on Yandex's side. UI description updated to spell out the constraint.

### Fixed
- **`x_token` cache passes `SecretStr` to ya_passport_auth correctly** — `client.refresh_passport_cookies` requires a `SecretStr` (not `str`), and `creds.x_token` is `SecretStr` (cannot be passed verbatim to a `str`-typed callback). v1.7.7 plumbing was correct functionally but failed mypy strict; now we wrap the cached string via `SecretStr(cached_x_token)` before refresh, and unwrap with `creds.x_token.get_secret()` before passing to the persistence callback.
- **English-only comments / docstrings** — translated remaining Russian fragments in code documentation (e.g. references to «Навык», «Дом с Алисой», «Моя волна») to English equivalents so future contributors don't need Russian to read the codebase. Functional Russian (regex patterns matching Russian voice commands, inflection suffixes, user-facing reply strings) intentionally stays as-is — translating would break the feature.



### Added
- **Cache Yandex Passport `x_token` between auto-create runs.** The first successful Device Flow now stores the long-lived `x_token` in plugin config (SECURE_STRING). Subsequent `auto_create_skill` / `auto_rename_dialog_skill` calls — including switching from the Smart Home pipeline to the Dialog pipeline — try `client.refresh_passport_cookies(cached_x_token)` first; if Yandex still accepts it, the device-code popup is skipped entirely. On any failure during refresh (token expired / revoked) the cache is silently dropped and the regular Device Flow runs as before. New private config key `CONF_AUTH_X_TOKEN`.



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
