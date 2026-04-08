"""Constants for Yandex Smart Home provider."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Config entry keys
# ---------------------------------------------------------------------------
CONF_INSTANCE_NAME = "instance_name"
CONF_CLOUD_TOKEN = "cloud_token"
CONF_CONNECTION_TYPE = "connection_type"
CONF_CLOUD_INSTANCE_ID = "cloud_instance_id"
CONF_CLOUD_CONNECTION_TOKEN = "cloud_connection_token"
CONF_SKILL_ID = "skill_id"

# ---------------------------------------------------------------------------
# Connection types
# ---------------------------------------------------------------------------
CONNECTION_TYPE_CLOUD = "cloud"
CONNECTION_TYPE_DIRECT = "direct"

# ---------------------------------------------------------------------------
# Cloud relay — yaha-cloud.ru (dext0r's relay service)
# ---------------------------------------------------------------------------
CLOUD_BASE_URL = "https://yaha-cloud.ru"
CLOUD_WS_URL = "wss://yaha-cloud.ru/api/home_assistant/v1/connect"
CLOUD_REGISTER_URL = f"{CLOUD_BASE_URL}/api/home_assistant/v1/instance/register"
CLOUD_CALLBACK_URL = f"{CLOUD_BASE_URL}/api/home_assistant/v2/callback"

# Platform identifier sent to the cloud relay
CLOUD_PLATFORM = "music_assistant"

# ---------------------------------------------------------------------------
# Direct mode — Yandex Dialogs API
# ---------------------------------------------------------------------------
YANDEX_DIALOGS_CALLBACK_URL = "https://dialogs.yandex.net/api/v1/skills"

# ---------------------------------------------------------------------------
# Timing (seconds)
# ---------------------------------------------------------------------------
STATE_REPORT_DELAY = 1.0  # debounce window for batched state reports
STATE_HEARTBEAT_INTERVAL = 3600  # report all states hourly
STATE_INITIAL_REPORT_DELAY = 15  # initial report after startup
CLOUD_RECONNECT_MIN = 2  # initial reconnect delay
CLOUD_RECONNECT_MAX = 180  # max reconnect delay (exponential backoff cap)
CLOUD_HEARTBEAT_INTERVAL = 45  # WebSocket heartbeat

# ---------------------------------------------------------------------------
# Yandex Smart Home API — device & capability constants
# ---------------------------------------------------------------------------
YANDEX_DEVICE_TYPE_MEDIA = "devices.types.media_device"
YANDEX_DEVICE_TYPE_RECEIVER = "devices.types.media_device.receiver"

CAPABILITY_ON_OFF = "devices.capabilities.on_off"
CAPABILITY_RANGE = "devices.capabilities.range"
CAPABILITY_TOGGLE = "devices.capabilities.toggle"

INSTANCE_ON = "on"
INSTANCE_VOLUME = "volume"
INSTANCE_MUTE = "mute"
INSTANCE_PAUSE = "pause"

UNIT_PERCENT = "unit.percent"

# ---------------------------------------------------------------------------
# Yandex Smart Home API — response codes
# ---------------------------------------------------------------------------
RESPONSE_OK = "DONE"
ERROR_DEVICE_UNREACHABLE = "DEVICE_UNREACHABLE"
ERROR_INVALID_ACTION = "INVALID_ACTION"
ERROR_INTERNAL_ERROR = "INTERNAL_ERROR"
ERROR_DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
