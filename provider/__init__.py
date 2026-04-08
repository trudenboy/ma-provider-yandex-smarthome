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

import logging
from typing import TYPE_CHECKING, cast

import aiohttp
from music_assistant_models.config_entries import ConfigEntry, ConfigValueOption
from music_assistant_models.enums import ConfigEntryType, ProviderFeature

from .cloud import get_cloud_otp, register_cloud_instance
from .constants import (
    CLOUD_SKILL_WEBHOOK_TEMPLATE,
    CONF_ACTION_GET_OTP,
    CONF_ACTION_REGISTER,
    CONF_CLOUD_CONNECTION_TOKEN,
    CONF_CLOUD_INSTANCE_ID,
    CONF_CLOUD_INSTANCE_PASSWORD,
    CONF_CONNECTION_TYPE,
    CONF_INSTANCE_NAME,
    CONF_SKILL_ID,
    CONF_SKILL_TOKEN,
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_CLOUD_PLUS,
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


def _build_status_label(
    otp_code: str | None, is_cloud_plus: bool, is_registered: bool
) -> str:
    """Build the status label text based on registration state."""
    if otp_code and is_cloud_plus:
        return (
            f"✅ Cloud instance registered! "
            f"OTP code: {otp_code} — "
            f"To link: Open Yandex app → Devices → Add device → Smart Home → "
            f"find your private skill → enter OTP code → "
            f"then click Save below to complete setup."
        )
    if otp_code:
        return (
            f"✅ Cloud instance registered! "
            f"OTP code: {otp_code} — "
            f"To link: Open Yandex app → Devices → Add device → Smart Home → "
            f"find 'Yaha Cloud' skill → enter OTP code → "
            f"then click Save below to complete setup."
        )
    if is_registered:
        return (
            "✅ Cloud instance is configured. "
            "Use 'Get OTP code' if you need to re-link with Yandex."
        )
    return (
        "Register a cloud instance to connect with Yandex Alice.\n"
        "This is free and uses the yaha-cloud.ru relay service (no public URL needed)."
    )


def _build_cloud_plus_label(
    is_cloud_plus: bool, is_registered: bool, cloud_instance_id: str
) -> str:
    """Build the Cloud Plus instruction label."""
    if not is_cloud_plus:
        return ""
    if is_registered:
        webhook_url = CLOUD_SKILL_WEBHOOK_TEMPLATE.format(instance_id=cloud_instance_id)
        return (
            f"Cloud Plus setup: "
            f"1) Create a private Smart Home skill at {YANDEX_DIALOGS_DEVELOPER_URL} "
            f"2) Set webhook URL to: {webhook_url} "
            f"3) Get OAuth token at: {YANDEX_OAUTH_URL} "
            f"4) Enter skill_id and token below, then Save."
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


async def get_config_entries(
    mass: MusicAssistant,
    instance_id: str | None = None,  # noqa: ARG001
    action: str | None = None,
    values: dict[str, ConfigValueType] | None = None,
) -> tuple[ConfigEntry, ...]:
    """Return Config entries to setup this provider.

    Supports two actions:
    - register_cloud: Auto-register a new instance on yaha-cloud.ru
    - get_otp: Get a fresh OTP code for linking in the Yandex app
    """
    if values is None:
        values = {}

    connection_type = str(values.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_CLOUD))
    is_cloud_plus = connection_type == CONNECTION_TYPE_CLOUD_PLUS

    # --- Handle register action ---
    if action == CONF_ACTION_REGISTER:
        try:
            async with aiohttp.ClientSession() as session:
                data = await register_cloud_instance(session)
            values[CONF_CLOUD_INSTANCE_ID] = data["id"]
            values[CONF_CLOUD_INSTANCE_PASSWORD] = data["password"]
            values[CONF_CLOUD_CONNECTION_TOKEN] = data["connection_token"]
            _LOGGER.info("Auto-registered cloud instance: %s", data["id"])
        except Exception:
            _LOGGER.exception("Failed to register cloud instance")

    # --- Handle get OTP action ---
    otp_code: str | None = None
    if action == CONF_ACTION_GET_OTP:
        cloud_id = str(values.get(CONF_CLOUD_INSTANCE_ID, ""))
        cloud_token = str(values.get(CONF_CLOUD_CONNECTION_TOKEN, ""))
        if cloud_id and cloud_token:
            try:
                async with aiohttp.ClientSession() as session:
                    otp_code = await get_cloud_otp(session, cloud_id, cloud_token)
            except Exception:
                _LOGGER.exception("Failed to get OTP code")

    # --- Auto-fetch OTP after registration ---
    if action == CONF_ACTION_REGISTER and not otp_code:
        cloud_id = str(values.get(CONF_CLOUD_INSTANCE_ID, ""))
        cloud_token = str(values.get(CONF_CLOUD_CONNECTION_TOKEN, ""))
        if cloud_id and cloud_token:
            try:
                async with aiohttp.ClientSession() as session:
                    otp_code = await get_cloud_otp(session, cloud_id, cloud_token)
            except Exception:
                _LOGGER.exception("Failed to get OTP after registration")

    # --- Determine state ---
    is_registered = bool(values.get(CONF_CLOUD_INSTANCE_ID)) and bool(
        values.get(CONF_CLOUD_CONNECTION_TOKEN)
    )
    cloud_instance_id = str(values.get(CONF_CLOUD_INSTANCE_ID, ""))

    label_text = _build_status_label(otp_code, is_cloud_plus, is_registered)
    cloud_plus_label = _build_cloud_plus_label(
        is_cloud_plus, is_registered, cloud_instance_id
    )

    return (
        # Instance name
        ConfigEntry(
            key=CONF_INSTANCE_NAME,
            type=ConfigEntryType.STRING,
            label="Instance Name",
            description=(
                "Name of this MA instance as it will appear in Yandex Smart Home. "
                'Alice will use this name for voice commands, e.g. '
                '"Алиса, включи музыку на [имя]".'
            ),
            required=True,
            default_value="Music Assistant",
        ),
        # Connection type selector
        ConfigEntry(
            key=CONF_CONNECTION_TYPE,
            type=ConfigEntryType.STRING,
            label="Connection Type",
            description=(
                '"cloud" — public Yaha Cloud skill (simple setup). '
                '"cloud_plus" — private skill (use if you already have Yaha Cloud '
                "linked to Home Assistant on the same Yandex account)."
            ),
            required=True,
            default_value=CONNECTION_TYPE_CLOUD,
            options=[
                ConfigValueOption(title="Cloud (public Yaha Cloud skill)", value="cloud"),
                ConfigValueOption(title="Cloud Plus (private skill)", value="cloud_plus"),
            ],
        ),
        # Status label
        ConfigEntry(
            key="label_status",
            type=ConfigEntryType.LABEL,
            label=label_text,
        ),
        # Cloud Plus instructions (shown only in cloud_plus mode)
        ConfigEntry(
            key="label_cloud_plus",
            type=ConfigEntryType.LABEL,
            label=cloud_plus_label,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
        ),
        # Register action (hidden after registration)
        ConfigEntry(
            key=CONF_ACTION_REGISTER,
            type=ConfigEntryType.ACTION,
            label="Register cloud instance",
            description="Register a new instance on yaha-cloud.ru relay service.",
            action=CONF_ACTION_REGISTER,
            action_label="Register with cloud",
            hidden=is_registered,
        ),
        # Get OTP action (shown after registration)
        ConfigEntry(
            key=CONF_ACTION_GET_OTP,
            type=ConfigEntryType.ACTION,
            label="Get OTP code",
            description="Get a fresh one-time password to link with Yandex Smart Home app.",
            action=CONF_ACTION_GET_OTP,
            action_label="Get OTP code",
            hidden=not is_registered,
        ),
        # --- Cloud Plus fields (visible only in cloud_plus mode) ---
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
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
        ),
        ConfigEntry(
            key=CONF_SKILL_TOKEN,
            type=ConfigEntryType.SECURE_STRING,
            label="Skill OAuth Token",
            description=(
                "OAuth token for sending state callbacks to Yandex. "
                "Get it by authorizing at the OAuth URL shown in the instructions above."
            ),
            required=False,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_CLOUD_PLUS,
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
            value=(
                cast("str", values.get(CONF_CLOUD_INSTANCE_PASSWORD)) if values else None
            ),
        ),
        ConfigEntry(
            key=CONF_CLOUD_CONNECTION_TOKEN,
            type=ConfigEntryType.SECURE_STRING,
            label="Cloud Connection Token",
            hidden=True,
            required=False,
            value=(
                cast("str", values.get(CONF_CLOUD_CONNECTION_TOKEN)) if values else None
            ),
        ),
    )
