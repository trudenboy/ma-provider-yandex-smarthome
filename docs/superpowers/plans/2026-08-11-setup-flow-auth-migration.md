# Setup Flow Authentication Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the retired `AUTH_SESSION` onboarding path with Music Assistant's native setup-flow API while preserving existing provider configurations and all three connection modes.

**Architecture:** A new `provider/setup_flow.py` owns credential collection and provisioning. `provider/ma_authenticator.py` only converts a ready `x_token` into a Dialogs API session, while `provider/plugin.py` owns runtime playback options and reads credentials through `get_setup_value` for setup-data/legacy compatibility.

**Tech Stack:** Python 3.14, Music Assistant `SetupSession`, `music-assistant-models`, `ya-passport-auth[ma] 1.7.0`, `ya-dialogs-api 2.4.0`, aiohttp, pytest/pytest-asyncio, Ruff, mypy.

## Global Constraints

- Follow `docs/superpowers/specs/2026-08-11-setup-flow-auth-migration-design.md`.
- Preserve the existing configuration key strings; no stored-config rewrite is allowed.
- Do not change `VERSION`; it is maintainer-owned.
- Do not modify auto-synced Ruff/mypy/codespell configuration outside PR #117.
- Use Sphinx-style docstrings and asynchronous I/O.
- Use red/green/refactor TDD for every behavior change.
- Never persist or rotate a token borrowed from Yandex Music.
- Never fall back from a rejected borrowed token to the provider's own account.
- Target `dev`; do not write to `music-assistant/server` or `trudenboy/ma-server`.
- Preserve the user's unrelated local `uv.lock` modification.

---

### Task 1: Perform independent GitHub housekeeping

**Files:** None.

**Interfaces:**
- Consumes: PR #117 current head/check status; PR #116 diff and `dev` Python target.
- Produces: merged config-sync PR #117 and closed redundant PR #116.

- [ ] **Step 1: Re-read the current PR targets and checks**

Run:

```bash
gh pr view 117 --repo trudenboy/ma-provider-yandex-smarthome --json headRefOid,mergeable,mergeStateStatus,statusCheckRollup,url
gh pr diff 117 --repo trudenboy/ma-provider-yandex-smarthome
gh pr diff 116 --repo trudenboy/ma-provider-yandex-smarthome
```

Expected: #117 is clean and only adds `.github/pr-review/standards.md` to `codespell.skip`; #116 contains only WIP changelog/spec artifacts.

- [ ] **Step 2: Merge PR #117**

Run:

```bash
gh pr merge 117 --repo trudenboy/ma-provider-yandex-smarthome --squash --delete-branch
```

Expected: GitHub reports #117 merged into `dev`. This command is authorized by the user's approval and is the wrapper-sync auto-merge exception described in `CLAUDE.md`.

- [ ] **Step 3: Close PR #116 with the evidence-based reason**

Run:

```bash
gh pr close 116 --repo trudenboy/ma-provider-yandex-smarthome --comment "Closing as redundant: dev already targets Python 3.14 for runtime and mypy, and the provider-side PEP 758 formatting from upstream #4254 is already present. This reverse-sync contains only WIP placeholder artifacts and no remaining production change."
```

Expected: #116 is closed without merging.

---

### Task 2: Add the native setup-flow contract

**Files:**
- Create: `provider/setup_flow.py`
- Create: `tests/test_setup_flow.py`
- Modify: `conftest.py`

**Interfaces:**
- Consumes: `register_cloud_instance`, `get_cloud_otp`, `derive_smart_home_urls`, `resolve_base_url`, and existing config-key constants.
- Produces: `run_setup(session: SetupSession) -> None`, `_collect_user`, `_run_cloud`, `_show_linking_code`, `_user_entries`, `_device_image`, and `_code_image`.

- [ ] **Step 1: Write failing tests for the first form and Cloud path**

Add tests that import the wished-for API and assert the observable setup-session calls:

```python
from provider.setup_flow import _collect_user, _run_cloud, _user_entries


def test_user_entries_offer_all_connection_modes() -> None:
    entries = _user_entries("cloud", "__own__", "", [])
    connection = {entry.key: entry for entry in entries}[CONF_CONNECTION_TYPE]
    assert [option.value for option in connection.options] == ["cloud", "cloud_plus", "direct"]


async def test_direct_reprompts_when_effective_url_is_not_https() -> None:
    session = _fake_session(base_url="http://ma.local:8095")
    session.form = _form_sequence(
        {CONF_CONNECTION_TYPE: "direct", CONF_EXTERNAL_BASE_URL: "http://public.example"},
        {CONF_CONNECTION_TYPE: "cloud", CONF_YM_INSTANCE: "__own__"},
    )
    result = await _collect_user(session, {})
    assert result[0] == "cloud"
    assert session.form.await_args_list[1].kwargs["errors"] == {
        "base": "direct_requires_https"
    }


async def test_cloud_registers_shows_otp_and_finishes() -> None:
    session = _fake_session()
    with (
        mock.patch(f"{_SETUP_FLOW}.register_cloud_instance", new_callable=mock.AsyncMock) as register,
        mock.patch(f"{_SETUP_FLOW}.get_cloud_otp", new_callable=mock.AsyncMock) as get_otp,
    ):
        register.return_value = {
            "id": "cloud-id",
            "password": "cloud-password",
            "connection_token": "connection-token",
        }
        get_otp.return_value = "1234"
        await _run_cloud(session, {})
    session.finish.assert_awaited_once()
```

- [ ] **Step 2: Verify the setup-flow tests fail for the missing module**

Run:

```bash
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run pytest tests/test_setup_flow.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'provider.setup_flow'`.

- [ ] **Step 3: Implement the setup-flow shell and Cloud flow**

Create `provider/setup_flow.py` with `run_setup`, `_collect_user`, `_run_cloud`,
and `_show_linking_code`. The top-level dispatcher must be:

```python
async def run_setup(session: SetupSession) -> None:
    collected: dict[str, ConfigValueType] = dict(session.context.setup_data)
    connection_type, instance_name, ym_instance = await _collect_user(
        session, collected
    )
    collected[CONF_CONNECTION_TYPE] = connection_type
    collected[CONF_YM_INSTANCE] = ym_instance
    if connection_type == CONNECTION_TYPE_CLOUD:
        await _run_cloud(session, collected)
    elif connection_type == CONNECTION_TYPE_CLOUD_PLUS:
        await _run_cloud_plus(session, collected, instance_name, ym_instance)
    else:
        await _run_direct(session, collected, instance_name, ym_instance)
```

Use `session.form` for `user` and `cloud_confirm`, `session.progress_until` for relay registration/OTP, `session.progress` for the OTP image, and `session.finish(collected)` for persistence. Define `_CLOUD_CALL_TIMEOUT = 60.0`, `_SKILL_CREATE_TIMEOUT = 180.0`, and render escaped SVG data URIs with `html.escape` plus base64 encoding.

Add minimal `AbortFlow` and `SetupFlowError` test doubles to `conftest.py` under
`music_assistant.models.setup_flow`. Both exceptions must retain a
`translation_key` attribute so tests assert the same public contract as Music
Assistant:

```python
class _SetupFlowError(Exception):
    def __init__(self, message: str = "", translation_key: str | None = None):
        super().__init__(message)
        self.translation_key = translation_key


class _AbortFlow(Exception):
    def __init__(self, translation_key: str):
        super().__init__(translation_key)
        self.translation_key = translation_key
```

Keep the legacy action-button constants during this task because the existing
`provider/__init__.py` still imports them. Task 5 removes them together with that
consumer.

- [ ] **Step 4: Verify the Cloud contract is green**

Run:

```bash
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run pytest tests/test_setup_flow.py -q
```

Expected: all tests added in this task pass.

- [ ] **Step 5: Commit the setup-flow foundation**

```bash
git add provider/setup_flow.py conftest.py tests/test_setup_flow.py
git commit -m "refactor(setup): add native cloud setup flow"
```

---

### Task 3: Move Device Flow and skill provisioning into SetupSession

**Files:**
- Modify: `provider/setup_flow.py`
- Modify: `tests/test_setup_flow.py`
- Modify: `tests/test_borrow_source.py`

**Interfaces:**
- Consumes: Task 2 setup-session helpers and the existing cached-token path of
  `make_authenticator`, invoked with `allow_device_flow=False` so it cannot use
  `AUTH_SESSION` while the setup flow is active.
- Produces: `_run_cloud_plus`, `_run_direct`, `_provision_skill`, `_device_login`, `_collect_skill_token`, and `_borrowed_x_token`.

- [ ] **Step 1: Add failing own-account and Device Flow tests**

Add tests with these assertions:

```python
async def test_own_rejected_cache_runs_one_fresh_device_login() -> None:
    session = _fake_session(setup_data={CONF_AUTH_X_TOKEN: "expired"})
    collected = dict(session.context.setup_data)
    with (
        mock.patch(f"{_SETUP_FLOW}.make_authenticator") as make_auth,
        mock.patch(
            f"{_SETUP_FLOW}.auto_create_skill", new_callable=mock.AsyncMock
        ) as create,
        mock.patch(f"{_SETUP_FLOW}.load_default_logo_bytes", return_value=b"logo"),
        mock.patch(f"{_SETUP_FLOW}._device_login", new_callable=mock.AsyncMock) as login,
    ):
        create.side_effect = [
            InvalidCredentialsError("expired"),
            _done_artifacts("skill-id"),
        ]
        login.return_value = "fresh-token"
        result = await _provision_skill(
            session,
            collected,
            connection_type="cloud_plus",
            skill_name="Test",
            ym_instance=BORROW_SOURCE_OWN,
        )
    assert result == "skill-id"
    assert collected[CONF_AUTH_X_TOKEN] == "fresh-token"
    assert [
        call.kwargs["cached_x_token"] for call in make_auth.call_args_list
    ] == ["expired", "fresh-token"]


async def test_device_login_denial_aborts_with_translation_key() -> None:
    session = _fake_session()
    fake_client = _passport_client(
        poll_error=InvalidCredentialsError("denied"),
    )
    with mock.patch("ya_passport_auth.PassportClient.create", return_value=fake_client):
        with pytest.raises(AbortFlow) as err:
            await _device_login(session)
    assert err.value.translation_key == "device_login_denied"
```

Define `_done_artifacts(skill_id: str)` in the test module with
`dataclasses.replace(load_artifacts(None), state=SkillCreationState.DONE,
skill_id=skill_id)`; it constructs test data and does not duplicate production
logic.

- [ ] **Step 2: Add failing borrowed-account tests**

Adapt `tests/test_borrow_source.py` to call the new setup-flow functions and assert:

```python
skill_id = await _provision_skill(
    session,
    collected,
    connection_type="cloud_plus",
    skill_name="Test",
    ym_instance="ym-a",
)
assert skill_id == "skill-xyz"
kwargs = make_auth.call_args.kwargs
assert kwargs["cached_x_token"] == "test-x-ym"
assert kwargs["allow_device_flow"] is False
assert kwargs["on_token_obtained"] is None
assert CONF_AUTH_X_TOKEN not in collected
```

Add a missing-token case that raises `SetupFlowError` with translation key `no_borrowed_token`, and assert `_device_login` is not called.

- [ ] **Step 3: Verify the new tests fail because provisioning is absent**

Run:

```bash
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run pytest tests/test_setup_flow.py tests/test_borrow_source.py -q
```

Expected: failures reference missing `_provision_skill`, `_device_login`, `_run_cloud_plus`, or `_run_direct` behavior.

- [ ] **Step 4: Implement provisioning and all mode branches**

Implement the approved upstream-compatible flow:

```python
async def _device_login(session: SetupSession) -> str:
    async with PassportClient.create(config=ClientConfig()) as client:
        device = await client.start_device_login(device_name="Music Assistant")
        try:
            credentials = await session.progress_until(
                client.poll_device_until_confirmed(
                    device, total_timeout=float(device.expires_in) + 60
                ),
                step_id="device_login",
                text="device_login",
                image=_device_image(device.user_code, device.verification_url),
                expires_in=float(device.expires_in),
            )
        except InvalidCredentialsError as err:
            raise AbortFlow("device_login_denied") from err
    return credentials.x_token.get_secret()
```

In `_provision_skill`, use `derive_smart_home_urls`, `auto_create_skill`,
`load_artifacts`, `dump_artifacts`, `load_default_logo_bytes`, and
`SMART_HOME_CHANNEL`. During this task, construct the existing authenticator as
shown below; Task 4 removes these compatibility-only parameters after its target
API tests fail:

```python
authenticator = make_authenticator(
    mass=session.mass,
    session_id=session.flow_id,
    cached_x_token=x_token,
    on_token_obtained=None,
    allow_device_flow=False,
)
```

Attempt borrowed credentials exactly once. For own credentials, try the cached
token once, remove it after `SetupFlowError` or `InvalidCredentialsError`, perform
Device Flow once, store the new token, and retry once.

Cloud Plus must support `_METHOD_AUTO = "auto"` and `_METHOD_MANUAL = "manual"`. Direct must create `CONF_DIRECT_CLIENT_SECRET` with `uuid4().hex` before deriving URLs. `_collect_skill_token` must retain an existing secure token when reconfiguration submits an empty value.

- [ ] **Step 5: Verify provisioning and borrow behavior are green**

Run:

```bash
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run pytest tests/test_setup_flow.py tests/test_borrow_source.py -q
```

Expected: all own, borrowed, Cloud Plus, Direct, denial, and token-validation tests pass.

- [ ] **Step 6: Commit setup provisioning**

```bash
git add provider/setup_flow.py tests/test_setup_flow.py tests/test_borrow_source.py
git commit -m "refactor(auth): move Yandex login into setup flow"
```

---

### Task 4: Reduce the authenticator to cached-token session creation

**Files:**
- Modify: `provider/ma_authenticator.py`
- Modify: `provider/setup_flow.py`
- Modify: `tests/test_ma_authenticator.py`
- Modify: `tests/test_borrow_source.py`
- Modify: `tests/test_setup_flow.py`

**Interfaces:**
- Consumes: an optional `cached_x_token: str | None` supplied by `provider.setup_flow`.
- Produces: `make_authenticator(*, cached_x_token: str | None = None) -> AuthenticatorCM` with no Music Assistant, session-id, callback, or Device Flow dependency.

- [ ] **Step 1: Replace session-id tests with failing token-session tests**

Test the new API before changing production code:

```python
async def test_valid_token_yields_authorized_session() -> None:
    authenticator = make_authenticator(cached_x_token="x-token")
    client = _fake_passport_client()
    with mock.patch("ya_passport_auth.PassportClient.create", return_value=_client_cm(client)):
        async with authenticator() as session:
            assert session is client._session
    client.refresh_passport_cookies.assert_awaited_once()


@pytest.mark.parametrize("token", [None, ""])
async def test_missing_token_requires_yandex_music_reauthentication(token: str | None) -> None:
    authenticator = make_authenticator(cached_x_token=token)
    with mock.patch("ya_passport_auth.PassportClient.create", return_value=_client_cm()):
        with pytest.raises(LoginFailed, match="Yandex Music"):
            async with authenticator():
                pass
```

Delete tests whose only subject is the retired `session_id` path.
Update the provisioning assertions in `tests/test_borrow_source.py` and
`tests/test_setup_flow.py` to require
`make_auth.call_args.kwargs == {"cached_x_token": expected_token}`; this makes
the production call-site change fail before implementation as well as the
authenticator signature change.

- [ ] **Step 2: Verify the target API fails against the legacy signature**

Run:

```bash
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run pytest tests/test_ma_authenticator.py tests/test_borrow_source.py -q
```

Expected: tests fail because `mass` and `session_id` are still required or because rejected tokens still attempt Device Flow.

- [ ] **Step 3: Implement the cached-token-only authenticator**

Remove `MusicAssistant`, `run_device_flow`, `DevicePageConfig`, session-id
validation, timeout, callback, and `allow_device_flow`. Preserve cancellation
propagation. A rejected token and a missing token must both raise `LoginFailed`
with Yandex Music re-authentication guidance; the setup flow owns fallback for
the provider's own cached token. Update `_provision_skill` to construct it only
with `make_authenticator(cached_x_token=x_token)`.

- [ ] **Step 4: Verify authenticator tests are green**

Run:

```bash
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run pytest tests/test_ma_authenticator.py tests/test_borrow_source.py tests/test_setup_flow.py -q
```

Expected: all authentication/setup-flow tests pass.

- [ ] **Step 5: Commit the authenticator cleanup**

```bash
git add provider/ma_authenticator.py tests/test_ma_authenticator.py tests/test_borrow_source.py tests/test_setup_flow.py
git commit -m "refactor(auth): retire AUTH_SESSION authenticator"
```

---

### Task 5: Separate setup credentials from runtime options

**Files:**
- Modify: `provider/__init__.py`
- Modify: `provider/plugin.py`
- Modify: `provider/constants.py`
- Modify: `conftest.py`
- Modify: `tests/test_basic.py`
- Modify: `tests/test_borrow_source.py`
- Modify: `tests/test_smarthome_auto_create.py`

**Interfaces:**
- Consumes: setup credentials persisted by `run_setup`.
- Produces: `YandexSmartHomePlugin.get_config_entries() -> tuple[ConfigEntry, ...]`, `_list_player_options()`, and runtime reads through `get_setup_value`.

- [ ] **Step 1: Add failing runtime compatibility tests**

Add assertions that options and credentials are separated:

```python
async def test_plugin_options_only_expose_runtime_choices(plugin: YandexSmartHomePlugin) -> None:
    entries = await plugin.get_config_entries()
    assert {entry.key for entry in entries} == {
        CONF_INSTANCE_NAME,
        CONF_EXPOSED_PLAYERS,
        CONF_EXPOSED_PLAYLISTS,
    }


async def test_plugin_reads_credentials_from_setup_data(plugin: YandexSmartHomePlugin) -> None:
    plugin.get_setup_value = mock.MagicMock(
        side_effect=lambda key: {
            CONF_CONNECTION_TYPE: "direct",
            CONF_DIRECT_CLIENT_SECRET: "secret",
        }.get(key)
    )
    await plugin.handle_async_init()
    assert plugin._connection_type == "direct"
    assert plugin._direct_client_secret == "secret"
```

Extend the local `_PluginProvider` stub in `conftest.py` with the real fallback
contract used by these tests:

```python
def get_setup_value(self, key: str):
    setup_data = getattr(self.config, "setup_data", None)
    if isinstance(setup_data, dict) and key in setup_data:
        return setup_data[key]
    return self.config.get_value(key)
```

Add one test with `config.setup_data = {}` and
`config.get_value.side_effect = {CONF_CONNECTION_TYPE: "direct",
CONF_DIRECT_CLIENT_SECRET: "legacy-secret"}.get`; do not patch
`get_setup_value`. After `handle_async_init`, assert the plugin selected Direct
mode and loaded `legacy-secret`.

- [ ] **Step 2: Verify tests fail while setup actions remain in `__init__.py`**

Run:

```bash
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run pytest tests/test_basic.py tests/test_borrow_source.py tests/test_smarthome_auto_create.py -q
```

Expected: the plugin lacks `get_config_entries`, and setup action tests still target the legacy module API.

- [ ] **Step 3: Move runtime options to the plugin and simplify module setup**

Move player/playlist option enumeration into `YandexSmartHomePlugin.get_config_entries`. Keep only `setup`, `SUPPORTED_FEATURES`, and imports required to construct the plugin in `provider/__init__.py`.

In `handle_async_init`, read credentials with:

```python
self._connection_type = str(
    self.get_setup_value(CONF_CONNECTION_TYPE) or CONNECTION_TYPE_CLOUD
)
cloud_token_raw = str(self.get_setup_value(CONF_CLOUD_INSTANCE_PASSWORD) or "")
self._cloud_instance_id = str(self.get_setup_value(CONF_CLOUD_INSTANCE_ID) or "")
self._skill_id = str(self.get_setup_value(CONF_SKILL_ID) or "")
self._direct_client_secret = str(
    self.get_setup_value(CONF_DIRECT_CLIENT_SECRET) or ""
)
```

Continue reading `CONF_INSTANCE_NAME`, `CONF_EXPOSED_PLAYERS`, and
`CONF_EXPOSED_PLAYLISTS` with `config.get_value`. Persist a newly minted Direct
access token with
`self._update_setup_data(CONF_DIRECT_ACCESS_TOKEN, token, immediate=True)`.

Delete legacy action-button tests; retain URL derivation and pure skill-state tests that still exercise production behavior.

After simplifying `provider/__init__.py`, verify the legacy names have no
remaining production consumer and remove them from `provider/constants.py`:

```bash
rg -n 'CONF_ACTION_|CONF_AUTO_CREATE_SESSION_ID' provider tests
```

The only matches before removal may be legacy tests being deleted in this task;
the command must return no matches after the cleanup.

- [ ] **Step 4: Verify runtime compatibility tests are green**

Run:

```bash
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run pytest tests/test_basic.py tests/test_borrow_source.py tests/test_smarthome_auto_create.py -q
```

Expected: runtime options contain exactly three entries, setup credentials initialize the plugin, and retained pure tests pass.

- [ ] **Step 5: Commit the runtime/setup separation**

```bash
git add provider/__init__.py provider/plugin.py provider/constants.py conftest.py tests/test_basic.py tests/test_borrow_source.py tests/test_smarthome_auto_create.py
git commit -m "refactor(config): separate setup data from runtime options"
```

---

### Task 6: Add setup-flow localization and release documentation

**Files:**
- Modify: `provider/strings.json`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Test: `tests/test_setup_flow.py`

**Interfaces:**
- Consumes: every `step_id`, `text`, translation key, and error key emitted by `provider/setup_flow.py`.
- Produces: complete English strings for the wizard and user-facing migration notes.

- [ ] **Step 1: Add a failing translation coverage test**

```python
def test_setup_flow_translations_include_required_steps() -> None:
    strings = json.loads(Path("provider/strings.json").read_text())
    assert set(strings["setup_flow"]) >= {
        "user",
        "registering",
        "skill_method",
        "skill_id",
        "creating_skill",
        "device_login",
        "skill_token",
        "fetching_otp",
        "cloud_otp",
        "cloud_confirm",
        "abort",
    }
    assert "shown in the Yandex app" not in strings["setup_flow"]["cloud_confirm"]["description"]
    assert set(strings["errors"]) >= {
        "direct_requires_https",
        "skill_token_required",
        "no_borrowed_token",
    }
```

- [ ] **Step 2: Verify the translation test fails**

Run:

```bash
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run pytest tests/test_setup_flow.py::test_setup_flow_translations_include_required_steps -q
```

Expected: failure because `setup_flow` and `errors` are absent.

- [ ] **Step 3: Add corrected strings and update docs**

Port the setup-flow/error keys from upstream PR #5024, but use this confirmation copy:

```json
"cloud_confirm": {
  "title": "Confirm in the Yandex app",
  "description": "Enter the one-time code shown by Music Assistant in the Yandex app, then continue once your account is linked."
}
```

Update README setup instructions from action buttons to the wizard sequence. Add one `### Changed` bullet under `## [Unreleased]` describing the setup wizard and removal of the retired auth popup; do not add a version block or internal symbol/file names.

- [ ] **Step 4: Verify translation and setup tests are green**

Run:

```bash
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run pytest tests/test_setup_flow.py -q
```

Expected: translation coverage and all setup-flow behavior pass.

- [ ] **Step 5: Commit localization and documentation**

```bash
git add provider/strings.json README.md CHANGELOG.md tests/test_setup_flow.py
git commit -m "docs: describe native setup wizard"
```

---

### Task 7: Verify, self-review, and publish the replacement PR

**Files:** All files changed by Tasks 2–6 plus the design and plan documents.

**Interfaces:**
- Consumes: complete implementation and test suite.
- Produces: reviewed draft PR targeting `dev`, replacing #115 and #114.

- [ ] **Step 1: Run focused tests**

```bash
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run pytest tests/test_setup_flow.py tests/test_ma_authenticator.py tests/test_borrow_source.py tests/test_basic.py -q
```

Expected: all focused tests pass with zero warnings attributable to the provider.

- [ ] **Step 2: Run the full verification gate**

```bash
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run pytest -q
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run ruff format --check .
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run ruff check .
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run mypy provider tests
UV_CACHE_DIR=/tmp/ma-yandex-smarthome-uv-cache uv run pre-commit run --all-files
```

Expected: every command exits 0.

- [ ] **Step 3: Perform a self-review against the design**

Run:

```bash
git diff --check dev...HEAD
git diff --stat dev...HEAD
git diff dev...HEAD
rg -n 'AUTH_SESSION|AuthenticationHelper|CONF_ACTION_|CONF_AUTO_CREATE_SESSION_ID|TODO|WIP' provider tests README.md CHANGELOG.md
```

Expected: no whitespace errors, no retired auth/action symbols, no placeholders, and only intended onboarding/auth/docs changes.

- [ ] **Step 4: Create the draft replacement PR**

Push the isolated branch and create a draft PR targeting `dev`. Use a `refactor(auth):` title, link upstream PR #5030 and local PRs #115/#114, describe legacy config compatibility, and include the verification commands/results. Do not modify `VERSION`.

- [ ] **Step 5: Re-read published checks and review feedback**

```bash
replacement_pr_number="$(gh pr view --json number --jq .number)"
gh pr checks --repo trudenboy/ma-provider-yandex-smarthome "$replacement_pr_number"
gh pr view --repo trudenboy/ma-provider-yandex-smarthome "$replacement_pr_number" --json comments,reviews,statusCheckRollup,mergeStateStatus
```

Expected: required checks finish successfully. Address AI review comments under the repository policy; leave replies to human upstream reviewers for the human maintainer.

- [ ] **Step 6: Close superseded reverse-sync PRs**

```bash
replacement_pr_number="$(gh pr view --json number --jq .number)"
gh pr close 115 --repo trudenboy/ma-provider-yandex-smarthome --comment "Superseded by #${replacement_pr_number}, which ports the native setup flow and removes the retired AUTH_SESSION dependency with regression coverage."
gh pr close 114 --repo trudenboy/ma-provider-yandex-smarthome --comment "Superseded by #${replacement_pr_number}, which includes the setup-flow translations with corrected OTP guidance alongside the implementation that consumes them."
```

Expected: #115 and #114 are closed without merging and link to the replacement draft.

- [ ] **Step 7: Leave the replacement as draft**

Do not merge or enable auto-merge. Per `CLAUDE.md`, changelog finalization, reviewer triage, and explicit maintainer approval precede merge.
