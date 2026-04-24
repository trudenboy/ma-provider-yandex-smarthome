"""Tests for provider/auto_skill.py — DialogsSkillCreator low-level client."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from music_assistant.providers.yandex_smarthome.auto_skill import (
    DIALOGS_API_BASE,
    DIALOGS_DEV_HTML_URL,
    DialogsApiError,
    DialogsCsrfError,
    DialogsDuplicateSkillError,
    DialogsSkillCreator,
    build_draft_payload,
    build_oauth_app_payload,
    check_preconditions,
    derive_auth_urls,
    derive_backend_uri,
    derive_client_id,
)
from music_assistant.providers.yandex_smarthome.constants import (
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_CLOUD_PLUS,
    CONNECTION_TYPE_DIRECT,
)

# ---------------------------------------------------------------------------
# Test helpers: mock aiohttp session matching existing test_cloud.py pattern
# ---------------------------------------------------------------------------


def _mock_response(
    *, status: int = 200, body_text: str = "", body_json: Any = None
) -> AsyncMock:
    """Build a mock aiohttp.ClientResponse.

    If *body_json* is given, ``text()`` returns its JSON-encoded form;
    otherwise ``body_text`` is used verbatim.
    """
    resp = AsyncMock()
    resp.status = status
    if body_json is not None:
        body_text = json.dumps(body_json, ensure_ascii=False)
    resp.text = AsyncMock(return_value=body_text)
    return resp


def _install_ctx(session_method: MagicMock, mock_resp: AsyncMock) -> MagicMock:
    """Attach an async context manager returning *mock_resp* to a session method."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session_method.return_value = ctx
    return ctx


def _make_session() -> MagicMock:
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get = MagicMock()
    session.post = MagicMock()
    session.request = MagicMock()
    return session


# ---------------------------------------------------------------------------
# fetch_csrf
# ---------------------------------------------------------------------------


class TestFetchCsrf:
    """CSRF token extraction from developer console HTML."""

    @pytest.mark.asyncio
    async def test_happy_path_returns_token(self) -> None:
        """CSRF is extracted from the secretkey field in the developer HTML."""
        html = (
            '<html><head><script>'
            'window.state = {"user":{"id":1},"secretkey":"u9c94f1aca53bf156be4abc","foo":"bar"}'
            '</script></head></html>'
        )
        session = _make_session()
        _install_ctx(session.get, _mock_response(status=200, body_text=html))
        creator = DialogsSkillCreator(session)

        token = await creator.fetch_csrf()
        assert token == "u9c94f1aca53bf156be4abc"
        # Verify we hit the expected URL
        session.get.assert_called_once_with(DIALOGS_DEV_HTML_URL)

    @pytest.mark.asyncio
    async def test_regex_miss_raises_csrf_error(self) -> None:
        """Yandex changed the HTML format → clean typed error for fallback."""
        html = "<html>no secretkey here</html>"
        session = _make_session()
        _install_ctx(session.get, _mock_response(status=200, body_text=html))
        creator = DialogsSkillCreator(session)

        with pytest.raises(DialogsCsrfError) as exc_info:
            await creator.fetch_csrf()
        assert exc_info.value.step == "fetch_csrf"

    @pytest.mark.asyncio
    async def test_401_maps_to_auth_error(self) -> None:
        """401 means passport cookies missing/expired — retryable via relogin."""
        session = _make_session()
        _install_ctx(session.get, _mock_response(status=401, body_text="nope"))
        creator = DialogsSkillCreator(session)

        with pytest.raises(DialogsApiError) as exc_info:
            await creator.fetch_csrf()
        assert exc_info.value.http_status == 401
        assert exc_info.value.step == "fetch_csrf"

    @pytest.mark.asyncio
    async def test_empty_token_raises(self) -> None:
        """Regex matched but captured empty string — treat as miss."""
        html = '{"secretkey":""}'
        session = _make_session()
        _install_ctx(session.get, _mock_response(status=200, body_text=html))
        creator = DialogsSkillCreator(session)

        with pytest.raises(DialogsCsrfError):
            await creator.fetch_csrf()


# ---------------------------------------------------------------------------
# create_app
# ---------------------------------------------------------------------------


class TestCreateApp:
    """POST /apps — returns skill_id on success."""

    @pytest.mark.asyncio
    async def test_happy_path_returns_skill_id(self) -> None:
        """POST /apps returns a skill UUID and sends the expected payload."""
        session = _make_session()
        _install_ctx(
            session.request,
            _mock_response(
                status=200,
                body_json={"result": {"id": "7584419b-6815-4a68-8e32-b9fb111b596d"}},
            ),
        )
        creator = DialogsSkillCreator(session)

        skill_id = await creator.create_app("csrf-token", "My Skill")
        assert skill_id == "7584419b-6815-4a68-8e32-b9fb111b596d"

        # Verify request shape
        method, url = session.request.call_args.args[:2]
        assert method == "POST"
        assert url == f"{DIALOGS_API_BASE}/apps"
        payload = session.request.call_args.kwargs["json"]
        assert payload["channel"] == "smartHome"
        assert payload["language"] == "ru"
        assert payload["isYangoConsole"] is False
        assert payload["appName"] == "My Skill"
        headers = session.request.call_args.kwargs["headers"]
        assert headers["x-csrf-token"] == "csrf-token"

    @pytest.mark.asyncio
    async def test_duplicate_name_raises_typed_error(self) -> None:
        """HTTP 409 with a duplicate-indicator body maps to DialogsDuplicateSkillError."""
        session = _make_session()
        _install_ctx(
            session.request,
            _mock_response(
                status=409,
                body_json={"error": "not_unique", "message": "skill already exists"},
            ),
        )
        creator = DialogsSkillCreator(session)

        with pytest.raises(DialogsDuplicateSkillError) as exc_info:
            await creator.create_app("csrf", "duplicate name")
        assert exc_info.value.http_status == 409

    @pytest.mark.asyncio
    async def test_generic_4xx_raises_api_error(self) -> None:
        """Non-duplicate 4xx surfaces as plain DialogsApiError, not the subclass."""
        session = _make_session()
        _install_ctx(
            session.request,
            _mock_response(status=400, body_text="bad request"),
        )
        creator = DialogsSkillCreator(session)

        with pytest.raises(DialogsApiError) as exc_info:
            await creator.create_app("csrf", "X")
        # Not a duplicate — should be plain DialogsApiError, not subclass
        assert not isinstance(exc_info.value, DialogsDuplicateSkillError)
        assert exc_info.value.http_status == 400

    @pytest.mark.asyncio
    async def test_missing_skill_id_raises(self) -> None:
        """A 200 response without an id field is treated as a protocol break."""
        session = _make_session()
        _install_ctx(
            session.request,
            _mock_response(status=200, body_json={"result": {}}),
        )
        creator = DialogsSkillCreator(session)

        with pytest.raises(DialogsApiError):
            await creator.create_app("csrf", "X")


# ---------------------------------------------------------------------------
# upload_logo
# ---------------------------------------------------------------------------


class TestUploadLogo:
    """POST /apps/{id}/draft/upload-logo — multipart file upload."""

    @pytest.mark.asyncio
    async def test_happy_path_returns_logo_id(self) -> None:
        """upload_logo posts multipart PNG and returns the avatar id."""
        session = _make_session()
        _install_ctx(
            session.post,
            _mock_response(
                status=200,
                body_json={
                    "result": {
                        "id": "be043706-a868-4999-83c8-f17bbd60745d",
                        "url": "https://avatars.mds.yandex.net/...",
                    }
                },
            ),
        )
        creator = DialogsSkillCreator(session)

        logo_id = await creator.upload_logo("csrf", "skill-1", b"\x89PNG\r\n\x1a\n...")
        assert logo_id == "be043706-a868-4999-83c8-f17bbd60745d"

        call = session.post.call_args
        url = call.args[0]
        assert "/draft/upload-logo" in url
        assert "channel=smartHome" in url
        # FormData used for multipart
        assert isinstance(call.kwargs["data"], aiohttp.FormData)
        assert call.kwargs["headers"]["x-csrf-token"] == "csrf"

    @pytest.mark.asyncio
    async def test_upload_500_raises(self) -> None:
        """Server-side 500 surfaces as DialogsApiError carrying the step name."""
        session = _make_session()
        _install_ctx(session.post, _mock_response(status=500, body_text="oops"))
        creator = DialogsSkillCreator(session)

        with pytest.raises(DialogsApiError) as exc_info:
            await creator.upload_logo("csrf", "sk", b"data")
        assert exc_info.value.step == "upload_logo"
        assert exc_info.value.http_status == 500


# ---------------------------------------------------------------------------
# update_draft
# ---------------------------------------------------------------------------


class TestUpdateDraft:
    """PATCH /apps/{id}/draft/update — accepts arbitrary payload dict."""

    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        """PATCH goes to the right URL with the forwarded payload and CSRF header."""
        session = _make_session()
        _install_ctx(
            session.request,
            _mock_response(status=200, body_json={"result": {"ok": True}}),
        )
        creator = DialogsSkillCreator(session)

        payload = {"name": "Music Assistant", "channel": "smartHome"}
        await creator.update_draft("csrf", "skill-1", payload)

        method, url = session.request.call_args.args[:2]
        assert method == "PATCH"
        assert url == f"{DIALOGS_API_BASE}/apps/skill-1/draft/update"
        assert session.request.call_args.kwargs["json"] == payload


# ---------------------------------------------------------------------------
# create_oauth_app
# ---------------------------------------------------------------------------


class TestCreateOAuthApp:
    """POST /oauth/apps — returns oauth_app_id."""

    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        """create_oauth_app builds the correct payload and returns the new id."""
        session = _make_session()
        _install_ctx(
            session.request,
            _mock_response(
                status=200,
                body_json={"result": {"id": "oauth-uuid-123"}},
            ),
        )
        creator = DialogsSkillCreator(session)

        oauth_id = await creator.create_oauth_app(
            "csrf",
            name="My Skill",
            client_id="yandex_smart_home:inst1",
            client_secret="secret",
            authorize_url="https://yaha-cloud.ru/oauth/authorize",
            token_url="https://yaha-cloud.ru/oauth/token",
            refresh_url="https://yaha-cloud.ru/oauth/token",
        )
        assert oauth_id == "oauth-uuid-123"

        payload = session.request.call_args.kwargs["json"]
        assert payload["clientId"] == "yandex_smart_home:inst1"
        assert payload["clientSecret"] == "secret"
        assert payload["authorizationUrl"] == "https://yaha-cloud.ru/oauth/authorize"
        assert payload["scope"] == ""


# ---------------------------------------------------------------------------
# attach_oauth
# ---------------------------------------------------------------------------


class TestAttachOAuth:
    """POST /apps/{id}/oauthApp — links oauth_app to skill."""

    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        """attach_oauth sends POST with channel query + oauthAppId body."""
        session = _make_session()
        _install_ctx(
            session.request,
            _mock_response(status=200, body_json={"result": "oauth-id"}),
        )
        creator = DialogsSkillCreator(session)

        await creator.attach_oauth("csrf", "skill-1", "oauth-1")

        method, url = session.request.call_args.args[:2]
        assert method == "POST"
        assert "channel=smartHome" in url
        assert session.request.call_args.kwargs["json"] == {"oauthAppId": "oauth-1"}


# ---------------------------------------------------------------------------
# request_deploy
# ---------------------------------------------------------------------------


class TestRequestDeploy:
    """POST /apps/{id}/draft/request-deploy — publishes draft."""

    @pytest.mark.asyncio
    async def test_happy_path_empty_body(self) -> None:
        """Request-deploy uses an empty body and relies on the URL query only."""
        session = _make_session()
        _install_ctx(session.post, _mock_response(status=200, body_json={"result": {}}))
        creator = DialogsSkillCreator(session)

        await creator.request_deploy("csrf", "skill-1")

        call = session.post.call_args
        url = call.args[0]
        assert "request-deploy" in url
        assert "channel=smartHome" in url
        # No body (only headers)
        assert "data" not in call.kwargs
        assert "json" not in call.kwargs
        assert call.kwargs["headers"]["x-csrf-token"] == "csrf"

    @pytest.mark.asyncio
    async def test_deploy_accepts_2xx_variants(self) -> None:
        """Some publish responses are 202/204 depending on server side."""
        for status in (201, 202, 204):
            session = _make_session()
            _install_ctx(session.post, _mock_response(status=status, body_text=""))
            creator = DialogsSkillCreator(session)
            await creator.request_deploy("csrf", "skill-1")  # must not raise


# ---------------------------------------------------------------------------
# list_existing_skills
# ---------------------------------------------------------------------------


class TestListExistingSkills:
    """GET /snapshot — returns existing skills or empty on malformed JSON."""

    @pytest.mark.asyncio
    async def test_returns_skill_dicts(self) -> None:
        """Snapshot is parsed into a list of skill dicts."""
        session = _make_session()
        _install_ctx(
            session.get,
            _mock_response(
                status=200,
                body_json={
                    "result": {
                        "skills": [
                            {"id": "s1", "name": "First"},
                            {"id": "s2", "name": "Second"},
                        ]
                    }
                },
            ),
        )
        creator = DialogsSkillCreator(session)

        skills = await creator.list_existing_skills("csrf")
        assert len(skills) == 2
        assert skills[0]["name"] == "First"

    @pytest.mark.asyncio
    async def test_raises_when_malformed(self) -> None:
        """Non-JSON snapshot body is a protocol break — raise instead of hiding it."""
        session = _make_session()
        _install_ctx(session.get, _mock_response(status=200, body_text="not json"))
        creator = DialogsSkillCreator(session)

        with pytest.raises(DialogsApiError):
            await creator.list_existing_skills("csrf")


# ---------------------------------------------------------------------------
# Payload builders + preconditions (pure functions)
# ---------------------------------------------------------------------------


def _mass_with_base_url(base_url: str) -> MagicMock:
    mass = MagicMock()
    mass.webserver.base_url = base_url
    return mass


class TestDeriveBackendUri:
    """derive_backend_uri routes per-mode."""

    def test_cloud_plus_uses_yaha_relay_constant(self) -> None:
        """cloud_plus always points at the fixed yaha-cloud webhook."""
        mass = _mass_with_base_url("https://my-ma.example.com")
        assert (
            derive_backend_uri(mass, CONNECTION_TYPE_CLOUD_PLUS)
            == "https://yaha-cloud.ru/api/yandex_smart_home"
        )

    def test_direct_uses_ma_base_plus_api_path(self) -> None:
        """Direct concatenates MA base_url with the provider's API path."""
        mass = _mass_with_base_url("https://my-ma.example.com/")
        # Trailing slash on base_url should be stripped so the full URL is clean.
        assert (
            derive_backend_uri(mass, CONNECTION_TYPE_DIRECT)
            == "https://my-ma.example.com/api/yandex_smarthome/v1.0"
        )

    def test_cloud_raises(self) -> None:
        """Plain 'cloud' mode has no custom skill — function must reject it."""
        mass = _mass_with_base_url("https://x")
        with pytest.raises(ValueError, match="connection_type"):
            derive_backend_uri(mass, CONNECTION_TYPE_CLOUD)


class TestDeriveAuthUrls:
    """derive_auth_urls returns (authorize_url, token_url)."""

    def test_cloud_plus_urls(self) -> None:
        """cloud_plus uses yaha-cloud OAuth endpoints."""
        mass = _mass_with_base_url("https://x")
        auth, token = derive_auth_urls(mass, CONNECTION_TYPE_CLOUD_PLUS)
        assert auth == "https://yaha-cloud.ru/oauth/authorize"
        assert token == "https://yaha-cloud.ru/oauth/token"

    def test_direct_urls_use_ma_base(self) -> None:
        """Direct uses the MA webserver's own authorize/token endpoints."""
        mass = _mass_with_base_url("https://ma.example.com")
        auth, token = derive_auth_urls(mass, CONNECTION_TYPE_DIRECT)
        assert auth == "https://ma.example.com/api/yandex_smarthome/auth/authorize"
        assert token == "https://ma.example.com/api/yandex_smarthome/auth/token"


class TestDeriveClientId:
    """derive_client_id formats the OAuth client_id per mode."""

    def test_cloud_plus_templated(self) -> None:
        """cloud_plus wraps the instance_id in the yaha protocol prefix."""
        assert (
            derive_client_id(CONNECTION_TYPE_CLOUD_PLUS, "abc123")
            == "yandex_smart_home:abc123"
        )

    def test_cloud_plus_missing_instance_raises(self) -> None:
        """Empty instance_id is a configuration bug — raise early."""
        with pytest.raises(ValueError, match="cloud_instance_id"):
            derive_client_id(CONNECTION_TYPE_CLOUD_PLUS, "")

    def test_direct_fixed_value(self) -> None:
        """Direct mode uses the fixed Yandex social redirect base."""
        assert (
            derive_client_id(CONNECTION_TYPE_DIRECT, "")
            == "https://social.yandex.net/"
        )


class TestBuildDraftPayload:
    """Snapshot coverage for the 100+-field draft/update payload."""

    def test_cloud_plus_snapshot(self, snapshot) -> None:  # type: ignore[no-untyped-def]
        """cloud_plus draft payload matches the captured HAR shape."""
        payload = build_draft_payload(
            connection_type=CONNECTION_TYPE_CLOUD_PLUS,
            skill_name="Music Assistant",
            backend_uri="https://yaha-cloud.ru/api/yandex_smart_home",
            logo_id="be043706-a868-4999-83c8-f17bbd60745d",
            developer_name="alice",
        )
        assert payload == snapshot

    def test_direct_snapshot(self, snapshot) -> None:  # type: ignore[no-untyped-def]
        """Direct draft payload matches the captured HAR shape."""
        payload = build_draft_payload(
            connection_type=CONNECTION_TYPE_DIRECT,
            skill_name="Music Assistant",
            backend_uri="https://ma.example.com/api/yandex_smarthome/v1.0",
            logo_id=None,
            developer_name="alice",
        )
        assert payload == snapshot

    def test_invalid_mode_raises(self) -> None:
        """Plain 'cloud' has no auto-create path."""
        with pytest.raises(ValueError, match="connection_type"):
            build_draft_payload(
                connection_type=CONNECTION_TYPE_CLOUD,
                skill_name="x",
                backend_uri="https://x",
                logo_id=None,
            )


class TestBuildOAuthAppPayload:
    """OAuth-app payload is simpler — both modes round-trip the given fields."""

    def test_cloud_plus_snapshot(self, snapshot) -> None:  # type: ignore[no-untyped-def]
        """cloud_plus payload uses literal 'secret' and the yaha-prefixed client_id."""
        payload = build_oauth_app_payload(
            skill_name="Music Assistant",
            client_id="yandex_smart_home:abc123",
            client_secret="secret",
            authorize_url="https://yaha-cloud.ru/oauth/authorize",
            token_url="https://yaha-cloud.ru/oauth/token",
        )
        assert payload == snapshot

    def test_direct_snapshot(self, snapshot) -> None:  # type: ignore[no-untyped-def]
        """Direct payload uses social.yandex.net client_id and a per-install secret."""
        payload = build_oauth_app_payload(
            skill_name="Music Assistant",
            client_id="https://social.yandex.net/",
            client_secret="abc123deadbeef",
            authorize_url="https://ma.example.com/api/yandex_smarthome/auth/authorize",
            token_url="https://ma.example.com/api/yandex_smarthome/auth/token",
        )
        assert payload == snapshot


class TestCheckPreconditions:
    """check_preconditions rejects invalid configurations early."""

    def test_cloud_plus_requires_instance(self) -> None:
        """cloud_plus without a registered cloud instance is rejected."""
        mass = _mass_with_base_url("https://x")
        with pytest.raises(ValueError, match="yaha-cloud instance"):
            check_preconditions(
                connection_type=CONNECTION_TYPE_CLOUD_PLUS,
                mass=mass,
                cloud_instance_id="",
                direct_client_secret="",
            )

    def test_cloud_plus_with_instance_ok(self) -> None:
        """cloud_plus with a registered instance_id passes."""
        mass = _mass_with_base_url("https://x")
        check_preconditions(
            connection_type=CONNECTION_TYPE_CLOUD_PLUS,
            mass=mass,
            cloud_instance_id="abc",
            direct_client_secret="",
        )

    def test_direct_requires_https_base_url(self) -> None:
        """Direct rejects non-HTTPS base URLs (Yandex won't accept)."""
        mass = _mass_with_base_url("http://ma.local:8095")
        with pytest.raises(ValueError, match="HTTPS"):
            check_preconditions(
                connection_type=CONNECTION_TYPE_DIRECT,
                mass=mass,
                cloud_instance_id="",
                direct_client_secret="secret",
            )

    def test_direct_requires_client_secret(self) -> None:
        """Direct rejects empty client_secret (would break account-linking)."""
        mass = _mass_with_base_url("https://ma.example.com")
        with pytest.raises(ValueError, match="Client Secret"):
            check_preconditions(
                connection_type=CONNECTION_TYPE_DIRECT,
                mass=mass,
                cloud_instance_id="",
                direct_client_secret="",
            )

    def test_direct_happy_path(self) -> None:
        """Direct with HTTPS base URL and a secret passes."""
        mass = _mass_with_base_url("https://ma.example.com")
        check_preconditions(
            connection_type=CONNECTION_TYPE_DIRECT,
            mass=mass,
            cloud_instance_id="",
            direct_client_secret="my-secret",
        )

    def test_cloud_mode_rejected(self) -> None:
        """Plain 'cloud' never uses a custom skill — reject."""
        mass = _mass_with_base_url("https://x")
        with pytest.raises(ValueError, match="cloud_plus or direct"):
            check_preconditions(
                connection_type=CONNECTION_TYPE_CLOUD,
                mass=mass,
                cloud_instance_id="",
                direct_client_secret="",
            )
