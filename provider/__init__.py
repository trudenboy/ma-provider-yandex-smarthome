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
from music_assistant_models.config_entries import ConfigEntry
from music_assistant_models.enums import ConfigEntryType, ProviderFeature

from .cloud import get_cloud_otp, register_cloud_instance
from .constants import (
    CONF_ACTION_GET_OTP,
    CONF_ACTION_REGISTER,
    CONF_CLOUD_CONNECTION_TOKEN,
    CONF_CLOUD_INSTANCE_ID,
    CONF_CLOUD_INSTANCE_PASSWORD,
    CONF_CONNECTION_TYPE,
    CONF_INSTANCE_NAME,
    CONNECTION_TYPE_CLOUD,
)
from .plugin import YandexSmartHomePlugin

if TYPE_CHECKING:
    from music_assistant_models.config_entries import ConfigValueType, ProviderConfig
    from music_assistant_models.provider import ProviderManifest

    from music_assistant.mass import MusicAssistant
    from music_assistant.models import ProviderInstanceType

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES: set[ProviderFeature] = set()


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

    # --- Build label text ---
    if otp_code:
        label_text = (
            f"✅ Cloud instance registered!\n\n"
            f"**OTP code: {otp_code}**\n\n"
            f"To link with Yandex Alice:\n"
            f"1. Open the Yandex app → Devices → Add device → Smart Home\n"
            f"2. Find 'Yaha Cloud' skill and add it\n"
            f"3. Enter the OTP code shown above\n"
            f"4. Click **Save** below to complete setup"
        )
    elif is_registered:
        label_text = (
            "✅ Cloud instance is configured. "
            "Use 'Get OTP code' if you need to re-link with Yandex."
        )
    else:
        label_text = (
            "Register a cloud instance to connect with Yandex Alice.\n"
            "This is free and uses the yaha-cloud.ru relay service (no public URL needed)."
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
        # Status label
        ConfigEntry(
            key="label_status",
            type=ConfigEntryType.LABEL,
            label=label_text,
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
        # --- Advanced fallback: manual entry ---
        ConfigEntry(
            key=CONF_CONNECTION_TYPE,
            type=ConfigEntryType.STRING,
            label="Connection Type",
            description=(
                '"cloud" uses the yaha-cloud.ru relay (no public URL needed). '
                '"direct" requires a publicly accessible URL (not yet supported).'
            ),
            required=True,
            default_value=CONNECTION_TYPE_CLOUD,
            advanced=True,
        ),
    )
