"""ConfigEntry builder for the auto-create-skill section.

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
    CONF_ACTION_AUTO_CREATE,
    CONF_AUTO_CREATE_ARTIFACTS,
    CONF_AUTO_CREATE_SESSION_ID,
    CONF_CONNECTION_TYPE,
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_CLOUD_PLUS,
    CONNECTION_TYPE_DIRECT,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "AUTO_CREATE_CATEGORY",
    "auto_create_entries",
    "should_show_button",
]

AUTO_CREATE_CATEGORY = "Auto-create skill"


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
