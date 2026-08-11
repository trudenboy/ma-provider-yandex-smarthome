"""Cached-token authenticator adapter for ``ya-dialogs-api``."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import aiohttp
    from ya_dialogs_api import AuthenticatorCM


def make_authenticator(*, cached_x_token: str) -> AuthenticatorCM:
    """
    Build a dialogs authenticator from a Yandex Passport x-token.

    Device Flow belongs to the provider setup flow. This adapter only
    exchanges the supplied token for Passport cookies and deliberately lets
    authentication errors propagate to that flow's retry policy.

    :param cached_x_token: Yandex Passport x-token obtained by setup or read
        from a linked Yandex Music provider.
    :return: A no-argument async context manager factory for ``auto_create_skill``.
    """

    @asynccontextmanager
    async def _cm() -> AsyncIterator[aiohttp.ClientSession]:
        from ya_passport_auth import ClientConfig, PassportClient  # noqa: PLC0415
        from ya_passport_auth.config import DEFAULT_ALLOWED_HOSTS  # noqa: PLC0415
        from ya_passport_auth.credentials import SecretStr  # noqa: PLC0415

        config = ClientConfig(
            allowed_hosts=DEFAULT_ALLOWED_HOSTS | frozenset({"dialogs.yandex.ru"})
        )
        async with PassportClient.create(config=config) as client:
            await client.refresh_passport_cookies(SecretStr(cached_x_token))
            yield client._session

    return _cm
