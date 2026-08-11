# Setup Flow and Authentication Migration Design

## Goal

Align the standalone Yandex Smart Home provider with the current Music Assistant
setup-flow API, remove its dependency on the retired `AUTH_SESSION` browser-popup
mechanism, and incorporate the setup-flow translations previously isolated in
reverse-sync PR #114.

## Scope

This migration changes provider onboarding and authentication plumbing. It does
not change player discovery, Yandex device capabilities, cloud transport, direct
HTTP endpoints, or state reporting.

The work replaces reverse-sync PRs #115 and #114. Reverse-sync PR #116 is
redundant because the `dev` branch already targets Python 3.14. Automated config
sync PR #117 remains independent and can be merged before publishing this work.

## Architecture

The provider adopts the current upstream `SetupSession` architecture:

- `provider/setup_flow.py` owns initial onboarding for Cloud, Cloud Plus, and
  Direct modes.
- `provider/__init__.py` retains provider construction and runtime option entries,
  but no longer drives credential provisioning through action buttons.
- `provider/ma_authenticator.py` accepts an already acquired Yandex Passport
  `x_token` and exposes the authorized session expected by `ya-dialogs-api`.
- Native Device Flow runs directly in the setup flow with
  `SetupSession.progress_until`; it does not register callback routes or signal
  `EventType.AUTH_SESSION`.
- Existing configuration key names remain unchanged so stored provider instances
  continue to load without a data migration.

## Setup Flows

### Cloud

1. Collect the connection type, display name, and Yandex account source.
2. Register a public `yaha-cloud.ru` relay instance.
3. Fetch and display the one-time linking code.
4. Wait for user confirmation and persist the collected credentials.

### Cloud Plus

1. Collect common values.
2. Register a private relay instance.
3. Let the user choose automatic skill provisioning or a manually created skill.
4. For automatic provisioning, authenticate with Yandex and create the skill.
5. Collect the skill OAuth token.
6. Display the relay linking code and persist the completed configuration.

### Direct

1. Collect common values and validate the effective external URL as HTTPS.
2. Generate the per-install OAuth client secret if it does not exist.
3. Authenticate with Yandex and provision the private skill against the Music
   Assistant HTTP endpoints.
4. Collect the skill OAuth token and persist the configuration.

## Authentication

For the provider's own Yandex account, a valid cached `x_token` is attempted
first. If it is missing or rejected, the setup flow starts Yandex Passport Device
Flow, renders the user code and verification URL as an escaped SVG data URI, and
polls until confirmation. The resulting token is kept in the provider's secure
configuration for future provisioning attempts.

For a linked Yandex Music account, the provider reads its `x_token` through
`BorrowedCredentialSource`. The token remains owned by Yandex Music: Yandex Smart
Home neither persists nor rotates it. A missing, unloaded, or rejected borrowed
credential returns actionable re-authentication guidance and never falls back to
the provider's own account.

## Error Handling

- Direct mode rejects a non-HTTPS effective URL before provisioning begins.
- A denied Device Flow aborts with the localized `device_login_denied` reason.
- A timed-out flow expires through the setup-session deadline.
- A rejected own cached token is removed from collected session data and followed
  by one fresh Device Flow attempt.
- A rejected borrowed token fails with Yandex Music re-authentication guidance.
- Skill creation must reach `SkillCreationState.DONE` and return a skill ID;
  otherwise its last error is surfaced through `SetupFlowError`.
- Skill creation artifacts are updated during provisioning so successful partial
  work can be reused within the active setup session.
- Missing skill OAuth tokens re-render the token step with a localized error.
- Relay registration, OTP retrieval, and skill creation use explicit setup-step
  deadlines.

## Localization

`provider/strings.json` receives the setup-flow and error keys from upstream PR
#5024. The OTP confirmation wording must state that Music Assistant displays the
code and the user enters it in the Yandex app; it must not imply that the app
displays the code.

## Compatibility

Runtime components continue reading the existing configuration keys. No version
bump or stored-config rewrite belongs in the contributor PR. Initial setup moves
to the new wizard, while existing configured instances retain their credentials
and operational behavior.

## Testing

Implementation follows red/green/refactor TDD. Tests cover:

- Cloud, Cloud Plus, and Direct setup paths;
- automatic and manual skill selection;
- direct HTTPS validation;
- cached-token success and fallback to fresh Device Flow;
- denied and timed-out Device Flow behavior;
- borrowed-token read-only behavior and failure guidance;
- skill OAuth token validation and retry;
- skill-provisioning failure propagation and artifact tracking;
- SVG escaping for device and OTP codes;
- translation keys and corrected OTP wording;
- continued loading of configurations using existing key names.

The final gate is the full project test suite, Ruff formatting and linting, mypy,
and `pre-commit run --all-files`.

## Delivery Sequence

1. Merge independent automated config-sync PR #117 after confirming its current
   checks and maintainer authorization.
2. Close empty reverse-sync PR #116 as redundant.
3. Implement this design on an isolated branch and open a draft replacement PR
   targeting `dev`.
4. After the replacement PR is published, close #115 and #114 with links to it.
5. Leave the replacement draft unmerged until review, changelog completion, and
   explicit maintainer approval.
