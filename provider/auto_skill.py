"""Low-level client for the undocumented dialogs.yandex.ru developer API.

Implements the 8-step sequence captured from Chrome DevTools HAR for
creating a Smart Home skill with account-linking:

    1. GET  /developer                       → extract CSRF (secretkey)
    2. GET  /developer/app-store-api/snapshot → existing skills list (optional)
    3. POST /developer/app-store-api/apps                      → skill_id
    4. POST /developer/app-store-api/apps/{id}/draft/upload-logo → logo_id
    5. PATCH /developer/app-store-api/apps/{id}/draft/update    → settings
    6. POST /developer/app-store-api/oauth/apps                → oauth_app_id
    7. POST /developer/app-store-api/apps/{id}/oauthApp        → bind oauth
    8. POST /developer/app-store-api/apps/{id}/draft/request-deploy → publish

This is an UNDOCUMENTED, PRIVATE API. It may break at any time. The
caller is responsible for surfacing that risk to the user (see
``provider.auto_skill_ui``).

Authentication: passport session cookies (``Session_id`` / ``sessionid2``)
must already be present in the supplied ``aiohttp.ClientSession``'s
cookie jar. Obtain them via ``ya_passport_auth.PassportClient``:

    creds = await client.login_device_code(...)
    await client.refresh_passport_cookies(creds.x_token)
    creator = DialogsSkillCreator(client._session)

The CSRF token (returned by ``fetch_csrf``) must be passed as the
``x-csrf-token`` header on every mutating request.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

import aiohttp

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "DIALOGS_API_BASE",
    "DIALOGS_CSRF_REGEX",
    "DIALOGS_DEV_BASE",
    "DIALOGS_DEV_HTML_URL",
    "DialogsApiError",
    "DialogsCsrfError",
    "DialogsDuplicateSkillError",
    "DialogsSkillCreator",
]

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoints / patterns
# ---------------------------------------------------------------------------
DIALOGS_DEV_BASE = "https://dialogs.yandex.ru"
DIALOGS_DEV_HTML_URL = f"{DIALOGS_DEV_BASE}/developer"
DIALOGS_API_BASE = f"{DIALOGS_DEV_BASE}/developer/app-store-api"

# The developer console embeds a CSRF token in its HTML as:
#   ..."secretkey":"u9c94f1aca53bf156be4..."...
# Captured from HAR 2026-04-24. If Yandex re-renders differently, this
# regex will miss and ``fetch_csrf`` raises ``DialogsCsrfError`` so the
# user falls back to manual setup.
DIALOGS_CSRF_REGEX = re.compile(r'"secretkey":"([^"]+)"')

SMART_HOME_CHANNEL = "smartHome"
_MAX_HTML_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MiB

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DialogsApiError(Exception):
    """Base error for dialogs.yandex.ru API failures."""

    def __init__(
        self,
        message: str,
        *,
        step: str,
        http_status: int | None = None,
        yandex_error: str | None = None,
    ) -> None:
        """Initialise with the pipeline step that failed for clearer messages."""
        super().__init__(message)
        self.step = step
        self.http_status = http_status
        self.yandex_error = yandex_error


class DialogsCsrfError(DialogsApiError):
    """Raised when the CSRF token cannot be extracted from the developer page."""


class DialogsDuplicateSkillError(DialogsApiError):
    """Raised when create_app rejects because a skill with the same name exists."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class DialogsSkillCreator:
    """Thin async wrapper over dialogs.yandex.ru developer-console API.

    Every method is idempotent on the transport layer: a single call
    either succeeds or raises. Retry / state-machine logic lives in the
    orchestrator (see :func:`auto_create_skill`).
    """

    __slots__ = ("_logger", "_session")

    def __init__(
        self,
        session: aiohttp.ClientSession,
        logger: logging.Logger | None = None,
    ) -> None:
        """Take a session that already carries Passport auth cookies."""
        self._session = session
        self._logger = logger or _LOGGER

    # -----------------------------------------------------------------------
    # Step 1: CSRF token extraction
    # -----------------------------------------------------------------------

    async def fetch_csrf(self) -> str:
        """Fetch the developer page HTML and extract the CSRF ``secretkey``.

        Caller uses the returned value as the ``x-csrf-token`` header on
        all mutating requests. Returns a fresh token on every call; the
        orchestrator caches it for the duration of a single attempt.
        """
        async with self._session.get(DIALOGS_DEV_HTML_URL) as resp:
            if resp.status == 401:
                raise DialogsApiError(
                    "not authenticated — passport session cookies missing or expired",
                    step="fetch_csrf",
                    http_status=401,
                )
            if resp.status != 200:
                raise DialogsApiError(
                    f"dialogs.yandex.ru/developer returned HTTP {resp.status}",
                    step="fetch_csrf",
                    http_status=resp.status,
                )
            # Guard against unbounded response size (T5 pattern from ya-passport-auth)
            html = await resp.text()
        if len(html) > _MAX_HTML_RESPONSE_BYTES:
            raise DialogsApiError(
                "developer page response exceeded size cap",
                step="fetch_csrf",
            )

        match = DIALOGS_CSRF_REGEX.search(html)
        if not match:
            raise DialogsCsrfError(
                "could not locate CSRF token in developer page HTML — "
                "Yandex may have changed the rendering format",
                step="fetch_csrf",
            )
        token = match.group(1).strip()
        if not token:
            raise DialogsCsrfError(
                "CSRF token matched but is empty",
                step="fetch_csrf",
            )
        self._logger.debug("dialogs CSRF token fetched (len=%d)", len(token))
        return token

    # -----------------------------------------------------------------------
    # Step 2: list existing skills (for duplicate-name detection)
    # -----------------------------------------------------------------------

    async def list_existing_skills(self, csrf: str) -> list[dict[str, Any]]:
        """Return the user's existing skills from the snapshot endpoint.

        The dashboard uses this to populate its skill list; we use it to
        warn the user before they hit a duplicate-name 4xx on create_app.
        """
        url = f"{DIALOGS_API_BASE}/snapshot"
        data = await self._get_json(url, csrf=csrf, step="list_existing_skills")
        result = data.get("result")
        if not isinstance(result, dict):
            return []
        skills = result.get("skills")
        if not isinstance(skills, list):
            return []
        return [s for s in skills if isinstance(s, dict)]

    # -----------------------------------------------------------------------
    # Step 3: create the skill app
    # -----------------------------------------------------------------------

    async def create_app(self, csrf: str, name: str) -> str:
        """Create a Smart Home skill with the given name.

        Returns the newly-minted ``skill_id`` (UUID). Raises
        :class:`DialogsDuplicateSkillError` if the name is already taken
        by another skill on this account.
        """
        url = f"{DIALOGS_API_BASE}/apps"
        payload = {
            "channel": SMART_HOME_CHANNEL,
            "language": "ru",
            "isYangoConsole": False,
            "appName": name,
        }
        data = await self._post_json(url, payload, csrf=csrf, step="create_app")
        result = data.get("result")
        if not isinstance(result, dict):
            raise DialogsApiError(
                "create_app response missing 'result' object",
                step="create_app",
            )
        skill_id = result.get("id") or result.get("skill_id")
        if not isinstance(skill_id, str) or not skill_id:
            raise DialogsApiError(
                "create_app response missing skill id",
                step="create_app",
            )
        self._logger.info("dialogs skill created: id=%s name=%r", skill_id, name)
        return skill_id

    # -----------------------------------------------------------------------
    # Step 4: upload logo
    # -----------------------------------------------------------------------

    async def upload_logo(self, csrf: str, skill_id: str, png: bytes) -> str:
        """Upload a PNG logo for the skill.

        Returns a ``logo_id`` that must be referenced in ``update_draft``.
        The logo file is sent as multipart with the field name ``file``
        and filename ``icon.png`` (matching the HAR capture).
        """
        url = (
            f"{DIALOGS_API_BASE}/apps/{skill_id}/draft/upload-logo"
            f"?channel={SMART_HOME_CHANNEL}"
        )
        form = aiohttp.FormData()
        form.add_field(
            "file",
            png,
            filename="icon.png",
            content_type="image/png",
        )
        headers = {"x-csrf-token": csrf}
        async with self._session.post(url, data=form, headers=headers) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise DialogsApiError(
                    f"upload_logo HTTP {resp.status}: {body[:200]}",
                    step="upload_logo",
                    http_status=resp.status,
                )
            data = _try_json(body)
        result = data.get("result") if isinstance(data, dict) else None
        if not isinstance(result, dict):
            raise DialogsApiError(
                "upload_logo response missing 'result'",
                step="upload_logo",
            )
        logo_id = result.get("id")
        if not isinstance(logo_id, str) or not logo_id:
            raise DialogsApiError(
                "upload_logo response missing logo id",
                step="upload_logo",
            )
        return logo_id

    # -----------------------------------------------------------------------
    # Step 5: update draft settings
    # -----------------------------------------------------------------------

    async def update_draft(
        self, csrf: str, skill_id: str, payload: Mapping[str, Any]
    ) -> None:
        """PATCH the skill draft with backend URL / publishing metadata."""
        url = f"{DIALOGS_API_BASE}/apps/{skill_id}/draft/update"
        await self._patch_json(url, dict(payload), csrf=csrf, step="update_draft")

    # -----------------------------------------------------------------------
    # Step 6: create OAuth app (account-linking)
    # -----------------------------------------------------------------------

    async def create_oauth_app(
        self,
        csrf: str,
        *,
        name: str,
        client_id: str,
        client_secret: str,
        authorize_url: str,
        token_url: str,
        refresh_url: str,
    ) -> str:
        """Create the OAuth app that powers account-linking in the skill.

        Returns the OAuth-app UUID which is then bound to the skill via
        ``attach_oauth``.
        """
        url = f"{DIALOGS_API_BASE}/oauth/apps"
        payload = {
            "name": name,
            "clientId": client_id,
            "clientSecret": client_secret,
            "authorizationUrl": authorize_url,
            "tokenUrl": token_url,
            "refreshTokenUrl": refresh_url,
            "scope": "",
            "yandexClientId": "",
        }
        data = await self._post_json(url, payload, csrf=csrf, step="create_oauth_app")
        result = data.get("result")
        if not isinstance(result, dict):
            raise DialogsApiError(
                "create_oauth_app response missing 'result'",
                step="create_oauth_app",
            )
        oauth_app_id = result.get("id")
        if not isinstance(oauth_app_id, str) or not oauth_app_id:
            raise DialogsApiError(
                "create_oauth_app response missing oauth app id",
                step="create_oauth_app",
            )
        return oauth_app_id

    # -----------------------------------------------------------------------
    # Step 7: bind OAuth app to the skill
    # -----------------------------------------------------------------------

    async def attach_oauth(
        self, csrf: str, skill_id: str, oauth_app_id: str
    ) -> None:
        """Attach an existing OAuth app to the skill's account-linking slot."""
        url = (
            f"{DIALOGS_API_BASE}/apps/{skill_id}/oauthApp"
            f"?channel={SMART_HOME_CHANNEL}"
        )
        payload = {"oauthAppId": oauth_app_id}
        await self._post_json(url, payload, csrf=csrf, step="attach_oauth")

    # -----------------------------------------------------------------------
    # Step 8: publish (send for moderation)
    # -----------------------------------------------------------------------

    async def request_deploy(self, csrf: str, skill_id: str) -> None:
        """Send the draft to moderation / publish.

        Body is empty; all params are in the query string. Returns on
        2xx; otherwise raises.
        """
        url = (
            f"{DIALOGS_API_BASE}/apps/{skill_id}/draft/request-deploy"
            f"?channel={SMART_HOME_CHANNEL}"
        )
        headers = {"x-csrf-token": csrf}
        async with self._session.post(url, headers=headers) as resp:
            body = await resp.text()
            if resp.status not in (200, 201, 202, 204):
                raise DialogsApiError(
                    f"request_deploy HTTP {resp.status}: {body[:200]}",
                    step="request_deploy",
                    http_status=resp.status,
                )

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    async def _get_json(
        self, url: str, *, csrf: str, step: str
    ) -> dict[str, Any]:
        headers = {"x-csrf-token": csrf}
        async with self._session.get(url, headers=headers) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise DialogsApiError(
                    f"GET {url} HTTP {resp.status}: {body[:200]}",
                    step=step,
                    http_status=resp.status,
                )
            data = _try_json(body)
        if not isinstance(data, dict):
            raise DialogsApiError(
                f"GET {url} returned non-object JSON",
                step=step,
            )
        return data

    async def _post_json(
        self, url: str, payload: dict[str, Any], *, csrf: str, step: str
    ) -> dict[str, Any]:
        return await self._send_json("POST", url, payload, csrf=csrf, step=step)

    async def _patch_json(
        self, url: str, payload: dict[str, Any], *, csrf: str, step: str
    ) -> dict[str, Any]:
        return await self._send_json("PATCH", url, payload, csrf=csrf, step=step)

    async def _send_json(
        self,
        method: str,
        url: str,
        payload: dict[str, Any],
        *,
        csrf: str,
        step: str,
    ) -> dict[str, Any]:
        headers = {
            "x-csrf-token": csrf,
            "content-type": "application/json",
        }
        async with self._session.request(
            method, url, json=payload, headers=headers
        ) as resp:
            body = await resp.text()
            if resp.status == 409 or (
                resp.status in (400, 422) and _looks_like_duplicate(body)
            ):
                raise DialogsDuplicateSkillError(
                    f"{step}: skill with this name already exists",
                    step=step,
                    http_status=resp.status,
                    yandex_error=_extract_error_code(body),
                )
            if resp.status not in (200, 201, 202):
                raise DialogsApiError(
                    f"{method} {url} HTTP {resp.status}: {body[:200]}",
                    step=step,
                    http_status=resp.status,
                    yandex_error=_extract_error_code(body),
                )
            data = _try_json(body)
        if not isinstance(data, dict):
            raise DialogsApiError(
                f"{method} {url} returned non-object JSON",
                step=step,
            )
        return data


# ---------------------------------------------------------------------------
# Module-private helpers
# ---------------------------------------------------------------------------


def _try_json(body: str) -> Any:
    """Parse JSON defensively — return None on any error."""
    if not body:
        return None
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        return None


def _looks_like_duplicate(body: str) -> bool:
    """Heuristic for whether a 4xx body indicates a duplicate-name error."""
    if not body:
        return False
    lowered = body.lower()
    return any(
        kw in lowered
        for kw in ("already exists", "duplicate", "exists with name", "not_unique")
    )


def _extract_error_code(body: str) -> str | None:
    """Pull Yandex error code/message out of a 4xx response body (best-effort)."""
    data = _try_json(body)
    if not isinstance(data, dict):
        return None
    for key in ("error", "errorCode", "message", "code"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None
