"""
Yandex Smart Home Plugin Provider for Music Assistant.

Exposes Music Assistant players to Yandex Alice via the Yandex Smart Home API.
Allows voice control of MA players through Alice commands like
"Алиса, включи музыку на [имя плеера]".

Architecture:
  Alice voice command → Yandex Cloud → Smart Home API callback → this plugin → MA Player

The plugin registers MA players as media_device in Yandex Smart Home,
mapping capabilities (on_off, volume, pause) to MA player controls.

Reference: https://github.com/dext0r/yandex_smart_home
"""

from __future__ import annotations

import contextlib
import dataclasses
import logging
import uuid
from typing import TYPE_CHECKING, cast

import aiohttp
from music_assistant_models.config_entries import ConfigEntry, ConfigValueOption
from music_assistant_models.enums import ConfigEntryType, EventType, ProviderFeature

from ._compat import SecretStr
from .auto_skill import (
    auto_create_skill,
    load_default_logo_bytes,
)
from .auto_skill_state import (
    SkillCreationState,
    dump_artifacts,
    load_artifacts,
)
from .auto_skill_ui import auto_create_entries
from .cloud import get_cloud_otp, register_cloud_instance
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
    CONF_CLOUD_CONNECTION_TOKEN,
    CONF_CLOUD_INSTANCE_ID,
    CONF_CLOUD_INSTANCE_PASSWORD,
    CONF_CONNECTION_TYPE,
    CONF_DIRECT_ACCESS_TOKEN,
    CONF_DIRECT_CLIENT_SECRET,
    CONF_EXPERIMENTAL_AUTO_CREATE_SKILL,
    CONF_EXPOSED_PLAYERS,
    CONF_INSTANCE_NAME,
    CONF_SKILL_ID,
    CONF_SKILL_TOKEN,
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_CLOUD_PLUS,
    CONNECTION_TYPE_DIRECT,
    DIRECT_API_BASE_PATH,
    DIRECT_AUTH_BASE_PATH,
    DIRECT_OAUTH_CLIENT_ID,
    YANDEX_DIALOGS_DEVELOPER_URL,
    YANDEX_OAUTH_URL,
)
from .plugin import YandexSmartHomePlugin

if TYPE_CHECKING:
    from music_assistant_models.config_entries import ConfigValueType, ProviderConfig
    from music_assistant_models.provider import ProviderManifest

    from music_assistant.mass import MusicAssistant
    from music_assistant.models import ProviderInstanceType

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES: set[ProviderFeature] = set()


def _build_status_label(otp_code: str | None, is_cloud_plus: bool, is_registered: bool) -> str:
    """Build the status label text based on registration state."""
    if otp_code and is_cloud_plus:
        return (
            "✅ Cloud instance registered! "
            "Open Yandex app → Devices → Add device → Smart Home → "
            "find your private skill → enter OTP code below → "
            "then click Save to complete setup."
        )
    if otp_code:
        return (
            "✅ Cloud instance registered! "
            "Open Yandex app → Devices → Add device → Smart Home → "
            "find 'Yaha Cloud' skill → enter OTP code below → "
            "then click Save to complete setup."
        )
    if is_registered:
        return (
            "✅ Cloud instance is configured. "
            "Use 'Get OTP code' if you need to re-link with Yandex."
        )
    return (
        "Register a cloud instance to connect with Yandex Alice. "
        "This is free and uses the yaha-cloud.ru relay service (no public URL needed)."
    )


def _build_cloud_plus_label(is_cloud_plus: bool, is_registered: bool) -> str:
    """Build the Cloud Plus instruction label."""
    if not is_cloud_plus:
        return ""
    if is_registered:
        return (
            "Cloud Plus setup: "
            "1) Open Yandex.Dialogs console (link below) → Smart Home → Create skill. "
            "2) Fill 'Basic info': Backend URL = webhook URL below, Access = Private. "
            "3) Save, then fill 'Account linking' section with values below. "
            "4) Save & Publish. "
            "5) Get OAuth token → enter skill_id and token → Save."
        )
    return (
        "Cloud Plus mode requires a private skill in Yandex.Dialogs. "
        "First register a cloud instance, then follow the setup instructions."
    )


async def setup(
    mass: MusicAssistant, manifest: ProviderManifest, config: ProviderConfig
) -> ProviderInstanceType:
    """Initialize provider(instance) with given configuration."""
    return YandexSmartHomePlugin(mass, manifest, config, SUPPORTED_FEATURES)


async def _handle_config_actions(
    mass: MusicAssistant,
    action: str | None,
    values: dict[str, ConfigValueType],
    instance_id: str | None,
    is_cloud_plus: bool,
    connection_type: str,
) -> str | None:
    """Execute config-flow actions and return OTP code if obtained."""
    saved_config = None
    if instance_id:
        prov = mass.get_provider(instance_id)
        if prov:
            saved_config = prov.config

    if action == CONF_ACTION_REGISTER:
        try:
            platform = "yandex" if is_cloud_plus else None
            async with aiohttp.ClientSession() as session:
                data = await register_cloud_instance(session, platform=platform)
            values[CONF_CLOUD_INSTANCE_ID] = data["id"]
            values[CONF_CLOUD_INSTANCE_PASSWORD] = data["password"]
            values[CONF_CLOUD_CONNECTION_TOKEN] = data["connection_token"]
            _LOGGER.info("Auto-registered cloud instance: %s", data["id"])
        except Exception:
            _LOGGER.exception("Failed to register cloud instance")

    otp_code: str | None = None
    if action == CONF_ACTION_GET_OTP:
        cloud_id = str(values.get(CONF_CLOUD_INSTANCE_ID, ""))
        cloud_token = ""
        if saved_config:
            cloud_token = str(saved_config.get_value(CONF_CLOUD_CONNECTION_TOKEN) or "")
        if not cloud_token:
            cloud_token = str(values.get(CONF_CLOUD_CONNECTION_TOKEN, ""))
        if cloud_id and cloud_token:
            try:
                async with aiohttp.ClientSession() as session:
                    otp_code = await get_cloud_otp(session, cloud_id, SecretStr(cloud_token))
            except Exception:
                _LOGGER.exception("Failed to get OTP code")

    if action == CONF_ACTION_REGISTER and not otp_code:
        cloud_id = str(values.get(CONF_CLOUD_INSTANCE_ID, ""))
        cloud_token = str(values.get(CONF_CLOUD_CONNECTION_TOKEN, ""))
        if cloud_id and cloud_token:
            try:
                async with aiohttp.ClientSession() as session:
                    otp_code = await get_cloud_otp(session, cloud_id, SecretStr(cloud_token))
            except Exception:
                _LOGGER.exception("Failed to get OTP after registration")

    if action == CONF_ACTION_AUTO_CREATE:
        await _run_auto_create_action(mass, values, connection_type)

    return otp_code


async def _run_auto_create_action(
    mass: MusicAssistant,
    values: dict[str, ConfigValueType],
    connection_type: str,
) -> None:
    """Execute the experimental auto-create-skill action.

    Never re-raises: all errors are persisted into the artifacts blob so
    the UI can show a FAILED state on the next render rather than
    crashing the config form.
    """
    session_id = str(values.get(CONF_AUTO_CREATE_SESSION_ID) or uuid.uuid4().hex)
    values[CONF_AUTO_CREATE_SESSION_ID] = session_id
    artifacts_raw = values.get(CONF_AUTO_CREATE_ARTIFACTS)
    artifacts = load_artifacts(str(artifacts_raw) if artifacts_raw else None)

    def _on_device_code(device_session: object) -> None:
        # ya-passport-auth's DeviceCodeSession exposes user_code and
        # verification_url; we push a URL with the code embedded so the
        # popup in the MA frontend pre-fills it for the user.
        user_code = getattr(device_session, "user_code", "")
        verification_url = getattr(
            device_session, "verification_url", "https://ya.ru/device"
        )
        full_url = (
            f"{verification_url}?user_code={user_code}"
            if user_code
            else verification_url
        )
        try:
            mass.signal_event(EventType.AUTH_SESSION, session_id, full_url)
        except Exception:
            _LOGGER.exception("signal_event for auto-create popup failed")

    try:
        new_artifacts = await auto_create_skill(
            mass=mass,
            connection_type=connection_type,
            skill_name=str(values.get(CONF_INSTANCE_NAME) or "Music Assistant"),
            artifacts=artifacts,
            cloud_instance_id=str(values.get(CONF_CLOUD_INSTANCE_ID, "")),
            direct_client_secret=str(values.get(CONF_DIRECT_CLIENT_SECRET, "")),
            logo_bytes=load_default_logo_bytes(),
            on_device_code=_on_device_code,
        )
    except ValueError as exc:
        # Precondition failures come back here — surface as FAILED.
        new_artifacts = dataclasses.replace(
            artifacts,
            state=SkillCreationState.FAILED,
            last_error=str(exc),
        )
        _LOGGER.warning("auto-create precondition failed: %s", exc)
    except Exception as exc:  # defensive — never crash the config form
        new_artifacts = dataclasses.replace(
            artifacts,
            state=SkillCreationState.FAILED,
            last_error=repr(exc),
        )
        _LOGGER.exception("auto-create hit unexpected error")

    values[CONF_AUTO_CREATE_ARTIFACTS] = dump_artifacts(new_artifacts)
    if new_artifacts.state == SkillCreationState.DONE and new_artifacts.skill_id:
        # Only set CONF_SKILL_ID on full success so the runtime doesn't
        # try to use a half-built skill mid-pipeline.
        values[CONF_SKILL_ID] = new_artifacts.skill_id


async def get_config_entries(
    mass: MusicAssistant,
    instance_id: str | None = None,
    action: str | None = None,
    values: dict[str, ConfigValueType] | None = None,
) -> tuple[ConfigEntry, ...]:
    """Return Config entries to setup this provider."""
    if values is None:
        values = {}

    connection_type = str(values.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_CLOUD))
    is_cloud_plus = connection_type == CONNECTION_TYPE_CLOUD_PLUS
    is_direct = connection_type == CONNECTION_TYPE_DIRECT

    otp_code = await _handle_config_actions(
        mass, action, values, instance_id, is_cloud_plus, connection_type
    )

    # Experimental auto-create-skill section — built separately and
    # appended at the end of the returned tuple.
    experimental_enabled = bool(values.get(CONF_EXPERIMENTAL_AUTO_CREATE_SKILL))
    artifacts_raw = values.get(CONF_AUTO_CREATE_ARTIFACTS)
    artifacts_str = str(artifacts_raw) if artifacts_raw else None
    artifacts = load_artifacts(artifacts_str)
    session_id = values.get(CONF_AUTO_CREATE_SESSION_ID)
    ma_base_url_for_ui = ""
    with contextlib.suppress(Exception):
        ma_base_url_for_ui = str(mass.webserver.base_url)
    auto_create_section = auto_create_entries(
        connection_type=connection_type,
        experimental_enabled=experimental_enabled,
        artifacts=artifacts,
        cloud_instance_id=str(values.get(CONF_CLOUD_INSTANCE_ID, "")),
        base_url=ma_base_url_for_ui,
        session_id=str(session_id) if session_id else None,
        user_code=None,  # not shown in form — popup URL carries the code
        verification_url=None,
        existing_artifacts_raw=artifacts_str,
    )

    is_registered = bool(values.get(CONF_CLOUD_INSTANCE_ID)) and bool(
        values.get(CONF_CLOUD_CONNECTION_TOKEN)
    )
    cloud_instance_id = str(values.get(CONF_CLOUD_INSTANCE_ID, ""))

    label_text = _build_status_label(otp_code, is_cloud_plus, is_registered)
    cloud_plus_label = _build_cloud_plus_label(is_cloud_plus, is_registered)

    # Compute copyable values for Cloud Plus mode
    webhook_url = ""
    client_id = ""
    if is_cloud_plus and is_registered:
        webhook_url = CLOUD_SKILL_WEBHOOK_TEMPLATE
        client_id = CLOUD_SKILL_CLIENT_ID_TEMPLATE.format(instance_id=cloud_instance_id)

    # Compute direct mode endpoint URLs
    direct_base_url = ""
    direct_auth_url = ""
    direct_token_url = ""
    if is_direct:
        try:
            ma_base_url = mass.webserver.base_url.rstrip("/")
        except Exception:
            ma_base_url = "https://<YOUR_MA_HOST>"
        direct_base_url = f"{ma_base_url}{DIRECT_API_BASE_PATH}"
        direct_auth_url = f"{ma_base_url}{DIRECT_AUTH_BASE_PATH}/authorize"
        direct_token_url = f"{ma_base_url}{DIRECT_AUTH_BASE_PATH}/token"

    # Build player options for exposed players filter
    player_options: list[ConfigValueOption] = []
    try:
        for player in mass.players.all_players():
            state = player.state
            player_options.append(
                ConfigValueOption(title=state.name or state.player_id, value=state.player_id)
            )
    except Exception:  # noqa: S110
        pass

    return (
        # Instance name
        ConfigEntry(
            key=CONF_INSTANCE_NAME,
            type=ConfigEntryType.STRING,
            label="Instance Name",
            description=(
                "Name of this MA instance as it will appear in Yandex Smart Home. "
                "Alice will use this name for voice commands, e.g. "
                '"Алиса, включи музыку на [имя]".'
            ),
            required=False,
            default_value="Music Assistant",
        ),
        # Connection type selector
        ConfigEntry(
            key=CONF_CONNECTION_TYPE,
            type=ConfigEntryType.STRING,
            label="Connection Type",
            description=(
                '"cloud" — public Yaha Cloud skill (simple setup). '
                '"cloud_plus" — private skill via cloud relay (for multi-platform setups). '
                '"direct" — Yandex calls your MA server directly (requires public HTTPS URL).'
            ),
            required=False,
            default_value=CONNECTION_TYPE_CLOUD,
            options=[
                ConfigValueOption(title="Cloud (public Yaha Cloud skill)", value="cloud"),
                ConfigValueOption(title="Cloud Plus (private skill)", value="cloud_plus"),
                ConfigValueOption(title="Direct (no relay, requires public URL)", value="direct"),
            ],
            advanced=True,
        ),
        # Status label (cloud modes only)
        ConfigEntry(
            key="label_status",
            type=ConfigEntryType.LABEL,
            label=label_text,
            hidden=is_direct,
        ),
        # OTP code — copyable text field (shown only when OTP is available)
        ConfigEntry(
            key="otp_code",
            type=ConfigEntryType.STRING,
            label="OTP Code",
            description="Copy this code and enter it in the Yandex app.",
            required=False,
            value=otp_code,
            hidden=not otp_code or is_direct,
        ),
        # Register action (hidden after registration or in direct mode)
        ConfigEntry(
            key=CONF_ACTION_REGISTER,
            type=ConfigEntryType.ACTION,
            label="Register cloud instance",
            description="Register a new instance on yaha-cloud.ru relay service.",
            action=CONF_ACTION_REGISTER,
            action_label="Register with cloud",
            hidden=is_registered or is_direct,
        ),
        # Get OTP action (shown after registration, hidden in direct mode)
        ConfigEntry(
            key=CONF_ACTION_GET_OTP,
            type=ConfigEntryType.ACTION,
            label="Get OTP code",
            description="Get a fresh one-time password to link with Yandex Smart Home app.",
            action=CONF_ACTION_GET_OTP,
            action_label="Get OTP code",
            hidden=not is_registered or is_direct,
        ),
        # --- Direct connection section ---
        ConfigEntry(
            key="label_direct",
            type=ConfigEntryType.LABEL,
            label=(
                "Direct connection setup: "
                "1) Create a private skill in Yandex.Dialogs (Smart Home type). "
                "2) Set Backend URL, Authorization URL, Token URL from values below. "
                "3) Set Client ID and Client Secret from values below. "
                "4) Publish skill, then link account in Yandex app. "
                "5) Fill Skill ID and Skill Token below and Save."
            ),
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_DIRECT,
            category="Direct Connection Setup",
        ),
        # Yandex Dialogs developer console link (direct)
        ConfigEntry(
            key="direct_dialogs_url",
            type=ConfigEntryType.STRING,
            label="Yandex.Dialogs Console (create skill here)",
            required=False,
            default_value=YANDEX_DIALOGS_DEVELOPER_URL,
            help_link=YANDEX_DIALOGS_DEVELOPER_URL,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_DIRECT,
            category="Direct Connection Setup",
        ),
        # Backend URL (for Yandex.Dialogs skill config)
        ConfigEntry(
            key="direct_backend_url",
            type=ConfigEntryType.STRING,
            label="Backend URL (→ Basic info)",
            description="Copy to your skill's Backend URL field in Yandex.Dialogs.",
            required=False,
            value=direct_base_url or None,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_DIRECT,
            category="Copy to Yandex.Dialogs skill",
        ),
        # Authorization URL (direct)
        ConfigEntry(
            key="direct_auth_url",
            type=ConfigEntryType.STRING,
            label="Authorization URL (→ Account linking)",
            description="Copy to 'Account linking' → 'Authorization URL' field.",
            required=False,
            value=direct_auth_url or None,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_DIRECT,
            category="Copy to Yandex.Dialogs skill",
        ),
        # Token URL (direct)
        ConfigEntry(
            key="direct_token_url",
            type=ConfigEntryType.STRING,
            label="Token URL (→ Account linking, both fields)",
            description=("Copy to both 'Token endpoint' and 'Refresh token URL' fields."),
            required=False,
            value=direct_token_url or None,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_DIRECT,
            category="Copy to Yandex.Dialogs skill",
        ),
        # Client ID (direct — always the same)
        ConfigEntry(
            key="direct_client_id",
            type=ConfigEntryType.STRING,
            label="Client ID (→ Account linking)",
            description="Copy to 'Account linking' → 'Client identifier' field.",
            required=False,
            default_value=DIRECT_OAUTH_CLIENT_ID,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_DIRECT,
            category="Copy to Yandex.Dialogs skill",
        ),
        # Client Secret (direct — auto-generated per install)
        ConfigEntry(
            key=CONF_DIRECT_CLIENT_SECRET,
            type=ConfigEntryType.SECURE_STRING,
            label="Client Secret (→ Account linking)",
            description=(
                "Copy to 'Account linking' → 'Client secret' field. Auto-generated on first setup."
            ),
            required=False,
            default_value=(
                cast("str", values.get(CONF_DIRECT_CLIENT_SECRET))
                if values and values.get(CONF_DIRECT_CLIENT_SECRET)
                else uuid.uuid4().hex
            ),
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_DIRECT,
            category="Copy to Yandex.Dialogs skill",
        ),
        # OAuth URL for getting skill token (direct)
        ConfigEntry(
            key="direct_oauth_url",
            type=ConfigEntryType.STRING,
            label="OAuth URL (open to get skill token)",
            required=False,
            default_value=YANDEX_OAUTH_URL,
            help_link=YANDEX_OAUTH_URL,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_DIRECT,
            category="Fill in from Yandex.Dialogs",
        ),
        # Skill ID (cloud_plus and direct)
        ConfigEntry(
            key=CONF_SKILL_ID,
            type=ConfigEntryType.STRING,
            label="Skill ID",
            description=(
                "UUID of your private Smart Home skill from Yandex.Dialogs. "
                "Find it in the skill URL: /developer/skills/{skill_id}/"
            ),
            required=False,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value_not=CONNECTION_TYPE_CLOUD,
            category="Fill in from Yandex.Dialogs",
        ),
        # Skill OAuth Token (cloud_plus and direct)
        ConfigEntry(
            key=CONF_SKILL_TOKEN,
            type=ConfigEntryType.SECURE_STRING,
            label="Skill OAuth Token",
            description="Paste the OAuth token obtained from the URL above.",
            required=False,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value_not=CONNECTION_TYPE_CLOUD,
            category="Fill in from Yandex.Dialogs",
        ),
        # --- Cloud Plus section (advanced) ---
        # Cloud Plus instructions
        ConfigEntry(
            key="label_cloud_plus",
            type=ConfigEntryType.LABEL,
            label=cloud_plus_label,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            advanced=True,
            category="Cloud Plus Setup",
        ),
        # Yandex Dialogs developer console link
        ConfigEntry(
            key="dialogs_url",
            type=ConfigEntryType.STRING,
            label="Yandex.Dialogs Console (create skill here)",
            required=False,
            default_value=YANDEX_DIALOGS_DEVELOPER_URL,
            help_link=YANDEX_DIALOGS_DEVELOPER_URL,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            advanced=True,
            category="Cloud Plus Setup",
        ),
        # --- Copy to Yandex.Dialogs ---
        # Webhook URL
        ConfigEntry(
            key="webhook_url",
            type=ConfigEntryType.STRING,
            label="Backend URL (→ Basic info)",
            description="Copy and paste into your private skill's Backend URL field.",
            required=False,
            value=webhook_url or None,
            hidden=not webhook_url,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            advanced=True,
            category="Copy to Yandex.Dialogs skill",
        ),
        # Client ID
        ConfigEntry(
            key="skill_client_id",
            type=ConfigEntryType.STRING,
            label="Client ID (→ Account linking)",
            description="Copy to 'Account linking' → 'Client identifier' field.",
            required=False,
            value=client_id or None,
            hidden=not client_id,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            advanced=True,
            category="Copy to Yandex.Dialogs skill",
        ),
        # Client Secret
        ConfigEntry(
            key="skill_client_secret",
            type=ConfigEntryType.STRING,
            label="Client Secret (→ Account linking)",
            description="Copy to 'Account linking' → 'Client secret' field.",
            required=False,
            default_value=CLOUD_SKILL_CLIENT_SECRET,
            hidden=not is_registered,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            advanced=True,
            category="Copy to Yandex.Dialogs skill",
        ),
        # Authorization URL
        ConfigEntry(
            key="skill_auth_url",
            type=ConfigEntryType.STRING,
            label="Authorization URL (→ Account linking)",
            description="Copy to 'Account linking' → 'Authorization URL' field.",
            required=False,
            default_value=CLOUD_OAUTH_AUTHORIZE_URL,
            hidden=not is_registered,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            advanced=True,
            category="Copy to Yandex.Dialogs skill",
        ),
        # Token URL
        ConfigEntry(
            key="skill_token_url",
            type=ConfigEntryType.STRING,
            label="Token URL (→ Account linking, both fields)",
            description=(
                "Copy to both 'Token endpoint' and 'Refresh token URL' fields "
                "in the 'Account linking' section."
            ),
            required=False,
            default_value=CLOUD_OAUTH_TOKEN_URL,
            hidden=not is_registered,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            advanced=True,
            category="Copy to Yandex.Dialogs skill",
        ),
        # OAuth URL — link to get skill token (Cloud Plus)
        ConfigEntry(
            key="oauth_url",
            type=ConfigEntryType.STRING,
            label="OAuth URL (open to get token)",
            required=False,
            default_value=YANDEX_OAUTH_URL,
            help_link=YANDEX_OAUTH_URL,
            hidden=not is_registered,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
            advanced=True,
            category="Fill in from Yandex.Dialogs",
        ),
        # --- Player filter ---
        ConfigEntry(
            key=CONF_EXPOSED_PLAYERS,
            type=ConfigEntryType.STRING,
            label="Exposed Players",
            description=(
                "Select which MA players to expose to Yandex Smart Home. "
                "Leave empty to expose all players."
            ),
            required=False,
            multi_value=True,
            default_value=[],
            options=list(player_options) if player_options else [],
        ),
        # --- Auto-managed fields (hidden, populated by actions) ---
        ConfigEntry(
            key=CONF_CLOUD_INSTANCE_ID,
            type=ConfigEntryType.STRING,
            label="Cloud Instance ID",
            hidden=True,
            required=False,
            value=cast("str", values.get(CONF_CLOUD_INSTANCE_ID)) if values else None,
        ),
        ConfigEntry(
            key=CONF_CLOUD_INSTANCE_PASSWORD,
            type=ConfigEntryType.SECURE_STRING,
            label="Cloud Instance Password",
            hidden=True,
            required=False,
            value=(cast("str", values.get(CONF_CLOUD_INSTANCE_PASSWORD)) if values else None),
        ),
        ConfigEntry(
            key=CONF_CLOUD_CONNECTION_TOKEN,
            type=ConfigEntryType.SECURE_STRING,
            label="Cloud Connection Token",
            hidden=True,
            required=False,
            value=(cast("str", values.get(CONF_CLOUD_CONNECTION_TOKEN)) if values else None),
        ),
        ConfigEntry(
            key=CONF_DIRECT_ACCESS_TOKEN,
            type=ConfigEntryType.SECURE_STRING,
            label="Direct Access Token",
            hidden=True,
            required=False,
            value=(cast("str", values.get(CONF_DIRECT_ACCESS_TOKEN)) if values else None),
        ),
        # --- Experimental auto-create-skill section (hidden for 'cloud' mode) ---
        *auto_create_section,
    )
