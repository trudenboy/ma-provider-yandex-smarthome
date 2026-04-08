"""
Yandex Smart Home Plugin Provider.

Bridges Music Assistant players to the Yandex Smart Home ecosystem,
allowing Alice voice control of playback, volume, and transport.

The plugin:
1. Listens for MA player events (added, removed, updated)
2. Exposes them as Yandex Smart Home media_device devices
3. Handles capability actions (on_off, volume, pause) from Alice
4. Reports state changes back to Yandex

Connection modes:
- Cloud: WebSocket relay through yaha-cloud.ru (no public URL needed)
- Direct: HTTP webhook endpoint that Yandex calls directly (requires public URL) [v0.2]
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from music_assistant.models.plugin import PluginProvider

from .cloud import CloudManager
from .constants import (
    CLOUD_CALLBACK_URL,
    CONF_CLOUD_CONNECTION_TOKEN,
    CONF_CLOUD_INSTANCE_PASSWORD,
    CONF_CONNECTION_TYPE,
    CONF_INSTANCE_NAME,
    CONNECTION_TYPE_CLOUD,
)
from .handlers import (
    build_response,
    handle_device_list,
    handle_devices_action,
    handle_devices_query,
    handle_user_unlink,
    parse_action_payload,
)
from .notifier import StateNotifier
from .schema import CloudRequest

if TYPE_CHECKING:
    pass


class YandexSmartHomePlugin(PluginProvider):
    """Plugin provider that exposes MA players to Yandex Alice via Smart Home API.

    Follows the same pattern as the HASS plugin provider: subscribes to MA events,
    maintains a mapping of MA players to Yandex Smart Home devices, and handles
    capability actions from Alice by translating them to MA player commands.
    """

    _cloud_manager: CloudManager | None = None
    _state_notifier: StateNotifier | None = None
    _cloud_task: Any = None

    async def handle_async_init(self) -> None:
        """Handle async initialization of the plugin."""
        self._connection_type = self.config.get_value(CONF_CONNECTION_TYPE) or CONNECTION_TYPE_CLOUD
        self._instance_name = self.config.get_value(CONF_INSTANCE_NAME) or "Music Assistant"
        self._cloud_token = self.config.get_value(CONF_CLOUD_INSTANCE_PASSWORD) or ""
        self._connection_token = self.config.get_value(CONF_CLOUD_CONNECTION_TOKEN) or ""

        self.logger.info(
            "Yandex Smart Home plugin init (mode=%s, name=%s)",
            self._connection_type,
            self._instance_name,
        )

    async def loaded_in_mass(self) -> None:
        """Call after the provider has been loaded.

        Starts cloud WebSocket connection and state notifier.
        """
        self.logger.info("Yandex Smart Home plugin loaded")

        if self._connection_type == CONNECTION_TYPE_CLOUD:
            await self._start_cloud_mode()
        else:
            self.logger.warning(
                "Direct mode not yet implemented — use cloud mode"
            )

    async def _start_cloud_mode(self) -> None:
        """Initialize and start cloud relay connection + state notifier."""
        if not self._connection_token:
            self.logger.error(
                "Cloud connection token not configured — "
                "register an instance at yaha-cloud.ru and set the connection token"
            )
            return

        session = self.mass.http_session

        # Cloud WebSocket manager
        self._cloud_manager = CloudManager(
            session=session,
            connection_token=self._connection_token,
            on_request=self._handle_cloud_request,
            logger=self.logger,
        )
        self._cloud_task = self.mass.create_task(
            self._cloud_manager.connect(),
            task_id="yandex_smarthome_cloud",
        )

        # State notifier
        auth_header = {"Authorization": f"Bearer {self._cloud_token}"}
        callback_url = f"{CLOUD_CALLBACK_URL}/state"

        self._state_notifier = StateNotifier(
            mass=self.mass,
            session=session,
            user_id=self._instance_name,
            callback_url=callback_url,
            auth_header=auth_header,
            logger=self.logger,
        )
        await self._state_notifier.start()

    async def _handle_cloud_request(self, request: CloudRequest) -> dict[str, Any]:
        """Route incoming cloud WS request to the appropriate handler."""
        action = request.action
        request_id = request.request_id
        message = request.message or {}

        self.logger.debug("Cloud request: action=%s, request_id=%s", action, request_id)

        try:
            if action == "/v1.0/user/devices":
                payload = await handle_device_list(self.mass)
                return build_response(request_id, asdict(payload))

            if action == "/v1.0/user/devices/query":
                device_ids = [d["id"] for d in message.get("devices", [])]
                payload = await handle_devices_query(self.mass, device_ids)
                return build_response(request_id, asdict(payload))

            if action == "/v1.0/user/devices/action":
                action_payload = parse_action_payload(message)
                payload = await handle_devices_action(self.mass, action_payload)
                return build_response(request_id, asdict(payload))

            if action == "/v1.0/user/unlink":
                payload = await handle_user_unlink()
                return build_response(request_id, payload)

            self.logger.warning("Unknown cloud action: %s", action)
            return build_response(request_id, {})

        except Exception:
            self.logger.exception("Error handling cloud request: %s", action)
            return build_response(request_id, {})

    async def unload(self, is_removed: bool = False) -> None:
        """Handle unload/close of the provider.

        Called when provider is deregistered (e.g. MA exiting or config reloading).
        is_removed will be set to True when the provider is removed from the configuration.
        """
        self.logger.info("Yandex Smart Home plugin unloading (removed=%s)", is_removed)

        if self._state_notifier:
            await self._state_notifier.stop()
            self._state_notifier = None

        if self._cloud_manager:
            await self._cloud_manager.disconnect()
            self._cloud_manager = None

        if self._cloud_task and not self._cloud_task.done():
            self._cloud_task.cancel()
            self._cloud_task = None
