"""Tests for the native Yandex Smart Home setup flow."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest import mock

from ya_passport_auth.ma import BORROW_SOURCE_OWN

from provider.constants import (
    CONF_CLOUD_CONNECTION_TOKEN,
    CONF_CLOUD_INSTANCE_ID,
    CONF_CLOUD_INSTANCE_PASSWORD,
    CONF_CONNECTION_TYPE,
    CONF_EXTERNAL_BASE_URL,
    CONF_YM_INSTANCE,
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_CLOUD_PLUS,
    CONNECTION_TYPE_DIRECT,
)
from provider.setup_flow import _collect_user, _run_cloud, _user_entries

_SETUP_FLOW = "provider.setup_flow"


def _fake_session(*, setup_data: dict[str, Any] | None = None) -> Any:
    """Build a setup-session stand-in whose progress helper awaits inline."""
    session = mock.MagicMock()
    session.mass = mock.MagicMock()
    session.mass.webserver.base_url = "http://ma.local:8095"
    session.flow_id = "flow-id"
    session.context = SimpleNamespace(setup_data=dict(setup_data or {}))
    session.form = mock.AsyncMock(return_value={})
    session.finish = mock.AsyncMock()
    session.progress = mock.MagicMock()

    async def _progress_until(awaitable: Any, **_: Any) -> Any:
        return await awaitable

    session.progress_until = mock.AsyncMock(side_effect=_progress_until)
    return session


def test_user_entries_offer_all_connection_modes() -> None:
    """The first form offers Cloud, Cloud Plus, and Direct modes."""
    entries = _user_entries(CONNECTION_TYPE_CLOUD, BORROW_SOURCE_OWN, "", [])
    connection = {entry.key: entry for entry in entries}[CONF_CONNECTION_TYPE]

    assert [option.value for option in connection.options] == [
        CONNECTION_TYPE_CLOUD,
        CONNECTION_TYPE_CLOUD_PLUS,
        CONNECTION_TYPE_DIRECT,
    ]


async def test_direct_reprompts_when_effective_url_is_not_https() -> None:
    """Direct setup rejects an HTTP public URL before provisioning."""
    session = _fake_session()
    session.form = mock.AsyncMock(
        side_effect=[
            {
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_DIRECT,
                CONF_EXTERNAL_BASE_URL: "http://public.example",
                CONF_YM_INSTANCE: BORROW_SOURCE_OWN,
            },
            {
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_CLOUD,
                CONF_YM_INSTANCE: BORROW_SOURCE_OWN,
            },
        ]
    )

    with mock.patch(f"{_SETUP_FLOW}.list_yandex_music_instances", return_value=[]):
        result = await _collect_user(session, {})

    assert result[0] == CONNECTION_TYPE_CLOUD
    assert session.form.await_args_list[1].kwargs["errors"] == {
        "base": "direct_requires_https"
    }


async def test_cloud_registers_shows_otp_and_finishes() -> None:
    """Cloud setup persists relay credentials after displaying its OTP."""
    session = _fake_session()
    collected: dict[str, Any] = {}
    with (
        mock.patch(
            f"{_SETUP_FLOW}.register_cloud_instance", new_callable=mock.AsyncMock
        ) as register,
        mock.patch(f"{_SETUP_FLOW}.get_cloud_otp", new_callable=mock.AsyncMock) as get_otp,
    ):
        register.return_value = {
            "id": "cloud-id",
            "password": "cloud-password",
            "connection_token": "connection-token",
        }
        get_otp.return_value = "1234"

        await _run_cloud(session, collected)

    assert collected == {
        CONF_CLOUD_INSTANCE_ID: "cloud-id",
        CONF_CLOUD_INSTANCE_PASSWORD: "cloud-password",
        CONF_CLOUD_CONNECTION_TOKEN: "connection-token",
    }
    session.progress.assert_called_once()
    session.finish.assert_awaited_once_with(collected)
