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

from typing import TYPE_CHECKING

from music_assistant_models.config_entries import ConfigEntry
from music_assistant_models.enums import ConfigEntryType, ProviderFeature

from .constants import (
    CONF_CLOUD_CONNECTION_TOKEN,
    CONF_CLOUD_INSTANCE_ID,
    CONF_CLOUD_TOKEN,
    CONF_CONNECTION_TYPE,
    CONF_INSTANCE_NAME,
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_DIRECT,
)
from .plugin import YandexSmartHomePlugin

if TYPE_CHECKING:
    from music_assistant_models.config_entries import ConfigValueType, ProviderConfig
    from music_assistant_models.provider import ProviderManifest

    from music_assistant.mass import MusicAssistant
    from music_assistant.models import ProviderInstanceType

SUPPORTED_FEATURES: set[ProviderFeature] = set()


async def setup(
    mass: MusicAssistant, manifest: ProviderManifest, config: ProviderConfig
) -> ProviderInstanceType:
    """Initialize provider(instance) with given configuration."""
    return YandexSmartHomePlugin(mass, manifest, config, SUPPORTED_FEATURES)


async def get_config_entries(
    mass: MusicAssistant,  # noqa: ARG001
    instance_id: str | None = None,  # noqa: ARG001
    action: str | None = None,  # noqa: ARG001
    values: dict[str, ConfigValueType] | None = None,  # noqa: ARG001
) -> tuple[ConfigEntry, ...]:
    """
    Return Config entries to setup this provider.

    instance_id: id of an existing provider instance (None if new instance setup).
    action: [optional] action key called from config entries UI.
    values: the (intermediate) raw values for config entries sent with the action.
    """
    return (
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
        ConfigEntry(
            key=CONF_CONNECTION_TYPE,
            type=ConfigEntryType.STRING,
            label="Connection Type",
            description=(
                "How to connect to Yandex Smart Home API. "
                '"cloud" uses the yaha-cloud.ru relay (no public URL needed). '
                '"direct" requires a publicly accessible URL and a registered Yandex Dialogs skill.'
            ),
            required=True,
            default_value=CONNECTION_TYPE_CLOUD,
        ),
        ConfigEntry(
            key=CONF_CLOUD_TOKEN,
            type=ConfigEntryType.SECURE_STRING,
            label="Cloud Token",
            description=(
                "OAuth token for Yandex Smart Home API. "
                "Required for registering devices with Yandex."
            ),
            required=True,
        ),
        ConfigEntry(
            key=CONF_CLOUD_INSTANCE_ID,
            type=ConfigEntryType.STRING,
            label="Cloud Instance ID",
            description=(
                "Instance ID from yaha-cloud.ru registration. "
                "Leave empty for auto-registration (not yet implemented)."
            ),
            required=False,
            default_value="",
        ),
        ConfigEntry(
            key=CONF_CLOUD_CONNECTION_TOKEN,
            type=ConfigEntryType.SECURE_STRING,
            label="Cloud Connection Token",
            description=(
                "Connection token from yaha-cloud.ru registration. "
                "Required for cloud mode WebSocket connection."
            ),
            required=False,
        ),
    )
