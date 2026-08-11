"""Setup flow for the Yandex Smart Home provider."""

from __future__ import annotations

import base64
from html import escape
from typing import TYPE_CHECKING

from music_assistant_models.config_entries import ConfigEntry, ConfigValueOption
from music_assistant_models.enums import ConfigEntryType
from ya_dialogs_api import SecretStr
from ya_passport_auth.ma import (
    BORROW_SOURCE_OWN,
    list_yandex_music_instances,
)

from music_assistant.models.setup_flow import SetupFlowError

from ._smarthome_auto_create import derive_smart_home_urls, resolve_base_url
from .cloud import get_cloud_otp, register_cloud_instance
from .constants import (
    CONF_CLOUD_CONNECTION_TOKEN,
    CONF_CLOUD_INSTANCE_ID,
    CONF_CLOUD_INSTANCE_PASSWORD,
    CONF_CONNECTION_TYPE,
    CONF_EXTERNAL_BASE_URL,
    CONF_INSTANCE_NAME,
    CONF_YM_INSTANCE,
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_CLOUD_PLUS,
    CONNECTION_TYPE_DIRECT,
)

if TYPE_CHECKING:
    from music_assistant_models.config_entries import ConfigValueType

    from music_assistant.models.setup_flow import SetupSession

_SKILL_CREATE_TIMEOUT = 180.0
_CLOUD_CALL_TIMEOUT = 60.0


async def run_setup(session: SetupSession) -> None:
    """Run the connection-mode-specific provider setup flow."""
    collected: dict[str, ConfigValueType] = dict(session.context.setup_data)
    connection_type, instance_name, ym_instance = await _collect_user(session, collected)
    collected[CONF_CONNECTION_TYPE] = connection_type
    collected[CONF_YM_INSTANCE] = ym_instance
    if connection_type == CONNECTION_TYPE_CLOUD:
        await _run_cloud(session, collected)
    elif connection_type == CONNECTION_TYPE_CLOUD_PLUS:
        await _run_cloud_plus(session, collected, instance_name, ym_instance)
    else:
        await _run_direct(session, collected, instance_name, ym_instance)


async def _collect_user(
    session: SetupSession, collected: dict[str, ConfigValueType]
) -> tuple[str, str, str]:
    """Show the initial setup form and validate Direct mode's external URL."""
    ym_instances = list_yandex_music_instances(session.mass)
    valid_sources = {instance_id for instance_id, _ in ym_instances}
    ym_default = str(collected.get(CONF_YM_INSTANCE) or BORROW_SOURCE_OWN)
    if ym_default != BORROW_SOURCE_OWN and ym_default not in valid_sources:
        ym_default = BORROW_SOURCE_OWN
    connection_default = str(collected.get(CONF_CONNECTION_TYPE) or CONNECTION_TYPE_CLOUD)
    base_url_default = str(collected.get(CONF_EXTERNAL_BASE_URL) or "")

    errors: dict[str, str] | None = None
    while True:
        values = await session.form(
            _user_entries(connection_default, ym_default, base_url_default, ym_instances),
            step_id="user",
            errors=errors,
        )
        connection_type = str(values[CONF_CONNECTION_TYPE])
        instance_name = str(values.get(CONF_INSTANCE_NAME) or "Music Assistant")
        ym_instance = str(values.get(CONF_YM_INSTANCE) or BORROW_SOURCE_OWN)
        if connection_type != CONNECTION_TYPE_DIRECT:
            return connection_type, instance_name, ym_instance

        external = str(values.get(CONF_EXTERNAL_BASE_URL) or "")
        base_url = resolve_base_url(session.mass, external or None)
        try:
            derive_smart_home_urls(
                connection_type=CONNECTION_TYPE_DIRECT,
                base_url=base_url,
                cloud_instance_id="",
                direct_client_secret="__validate__",
            )
        except ValueError:
            errors = {"base": "direct_requires_https"}
            connection_default = connection_type
            ym_default = ym_instance
            base_url_default = external
            continue
        collected[CONF_EXTERNAL_BASE_URL] = external
        return connection_type, instance_name, ym_instance


async def _run_cloud(
    session: SetupSession, collected: dict[str, ConfigValueType]
) -> None:
    """Register a public relay slot, show its linking code, and finish setup."""
    data = await session.progress_until(
        register_cloud_instance(session.mass.http_session, platform=None),
        step_id="registering",
        text="registering_cloud",
        expires_in=_CLOUD_CALL_TIMEOUT,
    )
    collected[CONF_CLOUD_INSTANCE_ID] = data["id"]
    collected[CONF_CLOUD_INSTANCE_PASSWORD] = data["password"]
    collected[CONF_CLOUD_CONNECTION_TOKEN] = data["connection_token"]
    errors: dict[str, str] | None = None
    while True:
        await _show_linking_code(session, collected, errors=errors)
        try:
            await session.finish(collected)
            return
        except SetupFlowError as err:
            errors = {"base": err.translation_key or str(err)}


async def _show_linking_code(
    session: SetupSession,
    collected: dict[str, ConfigValueType],
    *,
    errors: dict[str, str] | None,
) -> None:
    """Fetch the relay OTP and wait for confirmation after displaying it."""
    code = await session.progress_until(
        get_cloud_otp(
            session.mass.http_session,
            str(collected[CONF_CLOUD_INSTANCE_ID]),
            SecretStr(str(collected[CONF_CLOUD_CONNECTION_TOKEN])),
        ),
        step_id="fetching_otp",
        text="fetching_otp",
        expires_in=_CLOUD_CALL_TIMEOUT,
    )
    session.progress(step_id="cloud_otp", text="enter_otp_in_yandex_app", image=_code_image(code))
    await session.form(
        [
            ConfigEntry(
                key="label_otp_confirm",
                type=ConfigEntryType.LABEL,
                translation_params=[code],
            )
        ],
        step_id="cloud_confirm",
        errors=errors,
        last_step=True,
    )


def _user_entries(
    connection_default: str,
    ym_default: str,
    base_url_default: str,
    ym_instances: list[tuple[str, str]],
) -> list[ConfigEntry]:
    """Build the initial connection-mode and account-source entries."""
    return [
        ConfigEntry(
            key=CONF_CONNECTION_TYPE,
            type=ConfigEntryType.STRING,
            required=True,
            default_value=CONNECTION_TYPE_CLOUD,
            value=connection_default,
            options=[
                ConfigValueOption(value=CONNECTION_TYPE_CLOUD),
                ConfigValueOption(value=CONNECTION_TYPE_CLOUD_PLUS),
                ConfigValueOption(value=CONNECTION_TYPE_DIRECT),
            ],
        ),
        ConfigEntry(
            key=CONF_INSTANCE_NAME,
            type=ConfigEntryType.STRING,
            required=False,
            default_value="Music Assistant",
        ),
        ConfigEntry(
            key=CONF_YM_INSTANCE,
            type=ConfigEntryType.STRING,
            required=False,
            default_value=BORROW_SOURCE_OWN,
            value=ym_default,
            options=[
                *(
                    ConfigValueOption(value=instance_id, title=f"Yandex Music: {name}")
                    for instance_id, name in ym_instances
                ),
                ConfigValueOption(value=BORROW_SOURCE_OWN),
            ],
        ),
        ConfigEntry(
            key=CONF_EXTERNAL_BASE_URL,
            type=ConfigEntryType.STRING,
            required=False,
            default_value="",
            value=base_url_default,
            depends_on=CONF_CONNECTION_TYPE,
            depends_on_value=CONNECTION_TYPE_DIRECT,
        ),
    ]


def _device_image(user_code: str, verification_url: str) -> str:
    """Render a device code and verification URL as an escaped SVG data URI."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="460" height="180" '
        'viewBox="0 0 460 180" role="img">'
        '<rect width="460" height="180" rx="16" fill="#ffdb4d"/>'
        '<text x="230" y="82" font-family="monospace" font-size="46" font-weight="700" '
        f'text-anchor="middle" fill="#1a1a1a">{escape(user_code)}</text>'
        '<text x="230" y="130" font-family="sans-serif" font-size="16" '
        f'text-anchor="middle" fill="#5a4a00">{escape(verification_url)}</text>'
        "</svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _code_image(code: str) -> str:
    """Render a one-time linking code as an escaped SVG data URI."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="460" height="140" '
        'viewBox="0 0 460 140" role="img">'
        '<rect width="460" height="140" rx="16" fill="#ffdb4d"/>'
        '<text x="230" y="88" font-family="monospace" font-size="52" font-weight="700" '
        f'text-anchor="middle" fill="#1a1a1a">{escape(code)}</text>'
        "</svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
