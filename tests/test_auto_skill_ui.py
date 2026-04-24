"""Tests for auto_skill_ui — ConfigEntry visibility and action label logic."""

from __future__ import annotations

from music_assistant.providers.yandex_smarthome.auto_skill_state import (
    SkillCreationArtifacts,
    SkillCreationState,
)
from music_assistant.providers.yandex_smarthome.auto_skill_ui import (
    auto_create_entries,
    should_show_button,
)
from music_assistant.providers.yandex_smarthome.constants import (
    CONF_ACTION_AUTO_CREATE,
    CONF_AUTO_CREATE_ARTIFACTS,
    CONF_EXPERIMENTAL_AUTO_CREATE_SKILL,
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_CLOUD_PLUS,
    CONNECTION_TYPE_DIRECT,
)


def _find(entries, key):  # type: ignore[no-untyped-def]
    for e in entries:
        if e.key == key:
            return e
    return None


# ---------------------------------------------------------------------------
# should_show_button
# ---------------------------------------------------------------------------


class TestShouldShowButton:
    """should_show_button captures the full visibility truth table."""

    def test_hidden_when_experimental_off(self) -> None:
        """Master flag off → button hidden regardless of everything else."""
        assert not should_show_button(
            experimental_enabled=False,
            connection_type=CONNECTION_TYPE_CLOUD_PLUS,
            state=SkillCreationState.NONE,
            cloud_instance_id="abc",
            base_url="https://x",
        )

    def test_hidden_in_cloud_mode(self) -> None:
        """Plain cloud has no custom skill — button hidden."""
        assert not should_show_button(
            experimental_enabled=True,
            connection_type=CONNECTION_TYPE_CLOUD,
            state=SkillCreationState.NONE,
            cloud_instance_id="abc",
            base_url="https://x",
        )

    def test_hidden_when_state_done(self) -> None:
        """DONE means skill already created — don't offer re-creation."""
        assert not should_show_button(
            experimental_enabled=True,
            connection_type=CONNECTION_TYPE_CLOUD_PLUS,
            state=SkillCreationState.DONE,
            cloud_instance_id="abc",
            base_url="https://x",
        )

    def test_hidden_cloud_plus_no_instance(self) -> None:
        """cloud_plus requires a registered cloud instance first."""
        assert not should_show_button(
            experimental_enabled=True,
            connection_type=CONNECTION_TYPE_CLOUD_PLUS,
            state=SkillCreationState.NONE,
            cloud_instance_id="",
            base_url="https://x",
        )

    def test_hidden_direct_non_https(self) -> None:
        """Direct needs an HTTPS base URL or Yandex will reject the skill."""
        assert not should_show_button(
            experimental_enabled=True,
            connection_type=CONNECTION_TYPE_DIRECT,
            state=SkillCreationState.NONE,
            cloud_instance_id="",
            base_url="http://localhost:8095",
        )

    def test_shown_cloud_plus_ready(self) -> None:
        """All gates satisfied for cloud_plus → button visible."""
        assert should_show_button(
            experimental_enabled=True,
            connection_type=CONNECTION_TYPE_CLOUD_PLUS,
            state=SkillCreationState.NONE,
            cloud_instance_id="abc",
            base_url="https://x",
        )

    def test_shown_direct_ready(self) -> None:
        """All gates satisfied for direct → button visible."""
        assert should_show_button(
            experimental_enabled=True,
            connection_type=CONNECTION_TYPE_DIRECT,
            state=SkillCreationState.NONE,
            cloud_instance_id="",
            base_url="https://ma.example.com",
        )

    def test_shown_after_failed(self) -> None:
        """FAILED state keeps the button visible for retry."""
        assert should_show_button(
            experimental_enabled=True,
            connection_type=CONNECTION_TYPE_CLOUD_PLUS,
            state=SkillCreationState.FAILED,
            cloud_instance_id="abc",
            base_url="https://x",
        )


# ---------------------------------------------------------------------------
# auto_create_entries
# ---------------------------------------------------------------------------


class TestAutoCreateEntries:
    """auto_create_entries renders a list of ConfigEntries matching state."""

    def _entries(
        self,
        *,
        connection_type: str = CONNECTION_TYPE_CLOUD_PLUS,
        experimental_enabled: bool = True,
        state: SkillCreationState = SkillCreationState.NONE,
        cloud_instance_id: str = "abc",
        base_url: str = "https://ma.example.com",
    ):  # type: ignore[no-untyped-def]
        return auto_create_entries(
            connection_type=connection_type,
            experimental_enabled=experimental_enabled,
            artifacts=SkillCreationArtifacts(state=state),
            cloud_instance_id=cloud_instance_id,
            base_url=base_url,
            session_id=None,
            user_code=None,
            verification_url=None,
            existing_artifacts_raw=None,
        )

    def test_empty_for_cloud_mode(self) -> None:
        """Plain cloud returns no entries — the section is meaningless."""
        assert self._entries(connection_type=CONNECTION_TYPE_CLOUD) == ()

    def test_only_toggle_when_flag_off(self) -> None:
        """Master toggle is visible even when flag is off; rest is hidden."""
        entries = list(self._entries(experimental_enabled=False))
        keys = [e.key for e in entries]
        assert CONF_EXPERIMENTAL_AUTO_CREATE_SKILL in keys
        # Action and warning must NOT appear unless flag is on
        assert CONF_ACTION_AUTO_CREATE not in keys
        assert "label_auto_create_warning" not in keys

    def test_warning_present_when_flag_on(self) -> None:
        """Warning label is rendered once the master toggle is on."""
        entries = list(self._entries(experimental_enabled=True))
        warning = _find(entries, "label_auto_create_warning")
        assert warning is not None
        assert "EXPERIMENTAL" in warning.label

    def test_action_shown_and_enabled_when_ready(self) -> None:
        """In the ready-to-create state, action is present and not hidden."""
        entries = list(self._entries())
        action = _find(entries, CONF_ACTION_AUTO_CREATE)
        assert action is not None
        assert action.hidden is False

    def test_action_hidden_when_state_done(self) -> None:
        """state=DONE renders the action with hidden=True."""
        entries = list(self._entries(state=SkillCreationState.DONE))
        action = _find(entries, CONF_ACTION_AUTO_CREATE)
        assert action is not None
        assert action.hidden is True

    def test_action_label_changes_on_failed(self) -> None:
        """After a failure the button offers to retry from last step."""
        entries = list(self._entries(state=SkillCreationState.FAILED))
        action = _find(entries, CONF_ACTION_AUTO_CREATE)
        assert action is not None
        # On FAILED we start from scratch — "Create skill" label, not "Retry"
        assert "Create" in action.action_label

    def test_action_label_says_retry_on_partial(self) -> None:
        """Partial (non-FAILED) progress state uses the 'Retry from last step' label."""
        entries = list(self._entries(state=SkillCreationState.OAUTH_CREATED))
        action = _find(entries, CONF_ACTION_AUTO_CREATE)
        assert action is not None
        assert "Retry" in action.action_label

    def test_hidden_artifacts_always_round_tripped(self) -> None:
        """Artifacts blob is included even when the section is mostly empty."""
        entries = list(self._entries(experimental_enabled=False))
        # Even with flag off, the hidden artifacts entry must exist
        artifacts_entry = _find(entries, CONF_AUTO_CREATE_ARTIFACTS)
        assert artifacts_entry is not None
        assert artifacts_entry.hidden is True

    def test_status_label_reflects_failed_error(self) -> None:
        """The status LABEL carries the last_error text for user visibility."""
        entries = auto_create_entries(
            connection_type=CONNECTION_TYPE_CLOUD_PLUS,
            experimental_enabled=True,
            artifacts=SkillCreationArtifacts(
                state=SkillCreationState.FAILED,
                last_error="HTTP 401: session expired",
            ),
            cloud_instance_id="abc",
            base_url="https://x",
            session_id=None,
            user_code=None,
            verification_url=None,
            existing_artifacts_raw=None,
        )
        status = _find(list(entries), "label_auto_create_status")
        assert status is not None
        assert "401" in status.label
