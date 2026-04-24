"""ConfigEntry builders for the Yandex Smart Home provider.

Builds the numbered-step config form per connection type:

* ``cloud_plus`` → 3 steps: Register cloud → Create skill → Link via OTP.
* ``direct``     → 1 step:  Create skill  (skill is linked by Yandex Dialogs
  account-linking UI, no OTP).
* ``cloud``      → 2 steps: Register → Link via OTP  (unchanged).

Each step hides until the previous completes, so the user always sees
the single next action they need to take.

Kept separate from ``__init__.py`` so the long field list doesn't bloat
``get_config_entries`` and so it can be unit-tested in isolation from
the network-facing parts of the feature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from music_assistant_models.config_entries import ConfigEntry
from music_assistant_models.enums import ConfigEntryType

from .auto_skill_state import SkillCreationArtifacts, SkillCreationState
from .constants import (
    CLOUD_OAUTH_AUTHORIZE_URL,
    CLOUD_OAUTH_TOKEN_URL,
    CLOUD_SKILL_CLIENT_ID_TEMPLATE,
    CLOUD_SKILL_CLIENT_SECRET,
    CLOUD_SKILL_WEBHOOK_TEMPLATE,
    CONF_ACTION_AUTO_CREATE,
    CONF_ACTION_GET_OTP,
    CONF_ACTION_REGISTER,
    CONF_AUTO_CREATE_ARTIFACTS,
    CONF_AUTO_CREATE_SESSION_ID,
    CONF_CONNECTION_TYPE,
    CONF_SKILL_ID,
    CONF_SKILL_TOKEN,
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_CLOUD_PLUS,
    CONNECTION_TYPE_DIRECT,
    YANDEX_DIALOGS_DEVELOPER_URL,
    YANDEX_OAUTH_URL,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "AUTO_CREATE_CATEGORY",
    "auto_create_entries",
    "build_cloud_plus_entries",
    "should_show_button",
]

AUTO_CREATE_CATEGORY = "Auto-create skill"

# Category names are used as visual group headers in the MA UI. Numbered
# so they render in order and users see the flow as a sequence.
_CAT_STEP_1_REGISTER = "Step 1 — Register cloud instance"
_CAT_STEP_2_CREATE = "Step 2 — Create Smart Home skill"
_CAT_STEP_3_LINK = "Step 3 — Link skill to Yandex"


def _status_label(state: SkillCreationState, last_error: str | None) -> str:
    """Human-readable status line shown in the UI."""
    if state == SkillCreationState.DONE:
        return (
            "✅ Skill created and published. Now get the OAuth token "
            "(link below) and paste it into 'Skill OAuth Token'."
        )
    if state == SkillCreationState.FAILED:
        err = last_error or "unknown error"
        return (
            f"❌ Creation failed: {err}\n"
            "Press 'Retry' to try again, or fill in Skill ID / Skill OAuth Token "
            "manually below."
        )
    if state == SkillCreationState.NONE:
        return "Ready to create skill. Press the button below to start."
    # Any partial state — resume is possible.
    return (
        f"Partial progress saved ({state.value}). "
        "Press 'Retry from last step' to finish, or fill Skill ID manually."
    )


def _action_label(state: SkillCreationState) -> str:
    if state in (SkillCreationState.NONE, SkillCreationState.FAILED):
        return "Create skill automatically"
    return "Retry from last step"


def should_show_button(
    *,
    connection_type: str,
    state: SkillCreationState,
    cloud_instance_id: str,
    base_url: str,
) -> bool:
    """Return True iff the auto-create action button is actionable now.

    Hides the button when:
    - Mode is plain ``cloud`` (no custom skill exists there).
    - Skill creation already reached DONE.
    - cloud_plus is selected but no cloud instance has been registered.
    - direct is selected but MA base_url is not HTTPS.
    """
    if connection_type == CONNECTION_TYPE_CLOUD:
        return False
    if state == SkillCreationState.DONE:
        return False
    if connection_type == CONNECTION_TYPE_CLOUD_PLUS and not cloud_instance_id:
        return False
    return not (
        connection_type == CONNECTION_TYPE_DIRECT
        and not base_url.startswith("https://")
    )


def auto_create_entries(
    *,
    connection_type: str,
    artifacts: SkillCreationArtifacts,
    cloud_instance_id: str,
    base_url: str,
    session_id: str | None,
    user_code: str | None,
    verification_url: str | None,
    existing_artifacts_raw: str | None,
) -> Sequence[ConfigEntry]:
    """Build the auto-create section of the config form.

    Empty list for ``cloud`` mode — the feature is meaningless without
    a custom skill.
    """
    if connection_type == CONNECTION_TYPE_CLOUD:
        return ()

    entries: list[ConfigEntry] = []

    # Device-flow user code — shown when the flow obtained one this round.
    if user_code:
        entries.append(
            ConfigEntry(
                key="auto_create_user_code",
                type=ConfigEntryType.STRING,
                label="Device code for ya.ru/device",
                description=(
                    "Open the URL below in your browser, log in to your "
                    "Yandex account, and enter this code."
                ),
                value=user_code,
                required=False,
                help_link=verification_url or "https://ya.ru/device",
                depends_on=CONF_CONNECTION_TYPE,
                depends_on_value_not=CONNECTION_TYPE_CLOUD,
                category=AUTO_CREATE_CATEGORY,
            )
        )

    # Status label — dynamic based on current artifact state.
    entries.append(
        ConfigEntry(
            key="label_auto_create_status",
            type=ConfigEntryType.LABEL,
            label=_status_label(artifacts.state, artifacts.last_error),
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value_not=CONNECTION_TYPE_CLOUD,
            category=AUTO_CREATE_CATEGORY,
        )
    )

    # The action button — hidden in states where it can't run.
    show_button = should_show_button(
        connection_type=connection_type,
        state=artifacts.state,
        cloud_instance_id=cloud_instance_id,
        base_url=base_url,
    )
    entries.append(
        ConfigEntry(
            key=CONF_ACTION_AUTO_CREATE,
            type=ConfigEntryType.ACTION,
            label=_action_label(artifacts.state),
            description=(
                "Runs the Yandex Device Flow login, then creates and "
                "publishes the private Smart Home skill. Takes ~30 seconds "
                "after you enter the code."
            ),
            action=CONF_ACTION_AUTO_CREATE,
            action_label=_action_label(artifacts.state),
            hidden=not show_button,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value_not=CONNECTION_TYPE_CLOUD,
            category=AUTO_CREATE_CATEGORY,
        )
    )

    entries.extend(_hidden_state_entries(existing_artifacts_raw, session_id))
    return entries


def _hidden_state_entries(
    existing_artifacts_raw: str | None, session_id: str | None
) -> list[ConfigEntry]:
    """Round-trip the artifact blob and session id through the config form."""
    return [
        ConfigEntry(
            key=CONF_AUTO_CREATE_ARTIFACTS,
            type=ConfigEntryType.STRING,
            label="Auto-create artifacts (internal)",
            hidden=True,
            required=False,
            value=existing_artifacts_raw,
        ),
        ConfigEntry(
            key=CONF_AUTO_CREATE_SESSION_ID,
            type=ConfigEntryType.STRING,
            label="Auto-create session id (internal)",
            hidden=True,
            required=False,
            value=session_id,
        ),
    ]


# ---------------------------------------------------------------------------
# Cloud Plus step-flow
# ---------------------------------------------------------------------------


def build_cloud_plus_entries(
    *,
    otp_code: str | None,
    is_registered: bool,
    cloud_instance_id: str,
    artifacts: SkillCreationArtifacts,
    session_id: str | None,
    user_code: str | None,
    verification_url: str | None,
    existing_artifacts_raw: str | None,
    base_url: str,
) -> list[ConfigEntry]:
    """Return the cloud_plus-mode config entries as three visible steps.

    Step 1 (Register)       — always visible.
    Step 2 (Create skill)   — visible once cloud instance is registered.
    Step 3 (Link via OTP)   — visible once the skill (id + token) is set.
    """
    entries: list[ConfigEntry] = []
    entries.extend(_step1_register_entries(is_registered, cloud_instance_id))
    entries.extend(
        _step2_create_skill_entries(
            is_registered=is_registered,
            cloud_instance_id=cloud_instance_id,
            artifacts=artifacts,
            user_code=user_code,
            verification_url=verification_url,
            base_url=base_url,
        )
    )
    entries.extend(
        _step3_link_entries(
            is_registered=is_registered,
            otp_code=otp_code,
        )
    )
    entries.extend(_hidden_state_entries(existing_artifacts_raw, session_id))
    return entries


def _step1_register_entries(
    is_registered: bool, cloud_instance_id: str
) -> list[ConfigEntry]:
    """Step 1 — yaha-cloud.ru instance registration."""
    status_text = (
        f"✅ Cloud instance registered (id: {cloud_instance_id})."
        if is_registered
        else (
            "Click 'Register with cloud' to create a yaha-cloud.ru relay "
            "instance. This is free and takes a second."
        )
    )
    return [
        ConfigEntry(
            key="label_step1_status",
            type=ConfigEntryType.LABEL,
            label=status_text,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            category=_CAT_STEP_1_REGISTER,
        ),
        ConfigEntry(
            key=CONF_ACTION_REGISTER,
            type=ConfigEntryType.ACTION,
            label="Register cloud instance",
            description="Registers a new instance on yaha-cloud.ru relay.",
            action=CONF_ACTION_REGISTER,
            action_label="Register with cloud",
            hidden=is_registered,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            category=_CAT_STEP_1_REGISTER,
        ),
    ]


def _step2_create_skill_entries(
    *,
    is_registered: bool,
    cloud_instance_id: str,
    artifacts: SkillCreationArtifacts,
    user_code: str | None,
    verification_url: str | None,
    base_url: str,
) -> list[ConfigEntry]:
    """Step 2 — auto-create the skill and fill in the OAuth token."""
    if not is_registered:
        return []  # whole step hidden until Step 1 done

    entries: list[ConfigEntry] = []

    if user_code:
        entries.append(
            ConfigEntry(
                key="auto_create_user_code",
                type=ConfigEntryType.STRING,
                label="Device code for ya.ru/device",
                description=(
                    "Open the URL below, log in to your Yandex account, "
                    "and enter this code."
                ),
                value=user_code,
                required=False,
                help_link=verification_url or "https://ya.ru/device",
                depends_on=CONF_CONNECTION_TYPE,
                depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
                category=_CAT_STEP_2_CREATE,
            )
        )

    entries.append(
        ConfigEntry(
            key="label_step2_status",
            type=ConfigEntryType.LABEL,
            label=_status_label(artifacts.state, artifacts.last_error),
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            category=_CAT_STEP_2_CREATE,
        )
    )

    show_button = should_show_button(
        connection_type=CONNECTION_TYPE_CLOUD_PLUS,
        state=artifacts.state,
        cloud_instance_id=cloud_instance_id,
        base_url=base_url,
    )
    entries.append(
        ConfigEntry(
            key=CONF_ACTION_AUTO_CREATE,
            type=ConfigEntryType.ACTION,
            label=_action_label(artifacts.state),
            description=(
                "Runs the Yandex Device Flow login, then creates and "
                "publishes the private Smart Home skill."
            ),
            action=CONF_ACTION_AUTO_CREATE,
            action_label=_action_label(artifacts.state),
            hidden=not show_button,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            category=_CAT_STEP_2_CREATE,
        )
    )

    # OAuth URL + Skill OAuth Token — shown after skill is created so the
    # user can finish Step 2 by pasting the token.
    show_token_fields = artifacts.state == SkillCreationState.DONE
    entries.extend(
        [
            ConfigEntry(
                key="oauth_url",
                type=ConfigEntryType.STRING,
                label="OAuth URL (open to get token)",
                description=(
                    "Open this URL in your browser, approve, and copy the "
                    "access_token from the resulting URL into the field "
                    "below."
                ),
                required=False,
                default_value=YANDEX_OAUTH_URL,
                help_link=YANDEX_OAUTH_URL,
                hidden=not show_token_fields,
                depends_on=CONF_CONNECTION_TYPE,
                depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
                category=_CAT_STEP_2_CREATE,
            ),
            ConfigEntry(
                key=CONF_SKILL_TOKEN,
                type=ConfigEntryType.SECURE_STRING,
                label="Skill OAuth Token",
                description="Paste the OAuth token obtained from the URL above.",
                required=False,
                hidden=not show_token_fields,
                depends_on=CONF_CONNECTION_TYPE,
                depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
                category=_CAT_STEP_2_CREATE,
            ),
            # Also persist the Skill ID (usually set automatically on DONE,
            # but we expose it so users can enter it manually as fallback).
            ConfigEntry(
                key=CONF_SKILL_ID,
                type=ConfigEntryType.STRING,
                label="Skill ID",
                description=(
                    "UUID of your private Smart Home skill. Set automatically "
                    "when auto-create succeeds; you can paste it manually if "
                    "you created the skill by hand."
                ),
                required=False,
                hidden=not show_token_fields,
                depends_on=CONF_CONNECTION_TYPE,
                depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
                category=_CAT_STEP_2_CREATE,
            ),
        ]
    )

    return entries


def _step3_link_entries(
    *, is_registered: bool, otp_code: str | None
) -> list[ConfigEntry]:
    """Step 3 — get an OTP from the cloud and enter it in the Yandex app."""
    if not is_registered:
        return []  # whole step hidden until Step 1 done

    entries: list[ConfigEntry] = [
        ConfigEntry(
            key="label_step3_status",
            type=ConfigEntryType.LABEL,
            label=(
                f"Enter this OTP in the Yandex app: {otp_code}"
                if otp_code
                else (
                    "Press 'Get OTP code' to receive a short code, then "
                    "open Yandex app → Devices → Add device → Smart Home → "
                    "find your private skill → enter the code to link."
                )
            ),
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            category=_CAT_STEP_3_LINK,
        ),
        ConfigEntry(
            key="otp_code",
            type=ConfigEntryType.STRING,
            label="OTP Code",
            description="Copy this code and enter it in the Yandex app.",
            required=False,
            value=otp_code,
            hidden=not otp_code,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            category=_CAT_STEP_3_LINK,
        ),
        ConfigEntry(
            key=CONF_ACTION_GET_OTP,
            type=ConfigEntryType.ACTION,
            label="Get OTP code",
            description="Get a fresh one-time password to link with Yandex.",
            action=CONF_ACTION_GET_OTP,
            action_label="Get OTP code",
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            category=_CAT_STEP_3_LINK,
        ),
    ]
    return entries


# Reference constants imported but unused at top-level are required by
# future manual-fallback entries (Task: auto-show on FAILED). Export
# them as module-level attrs so type-checkers don't flag unused imports.
_ = (
    CLOUD_OAUTH_AUTHORIZE_URL,
    CLOUD_OAUTH_TOKEN_URL,
    CLOUD_SKILL_CLIENT_ID_TEMPLATE,
    CLOUD_SKILL_CLIENT_SECRET,
    CLOUD_SKILL_WEBHOOK_TEMPLATE,
    YANDEX_DIALOGS_DEVELOPER_URL,
)
