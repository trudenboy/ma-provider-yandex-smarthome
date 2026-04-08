"""Constants for Yandex Smart Home provider."""

from __future__ import annotations

# Config entry keys
CONF_CLOUD_TOKEN = "cloud_token"
CONF_INSTANCE_NAME = "instance_name"

# Yandex Smart Home API
YANDEX_SMARTHOME_API_BASE = "https://dialogs.yandex.net/api/v1"

# Device type for MA players exposed to Yandex Smart Home
YANDEX_SMARTHOME_DEVICE_TYPE = "devices.types.media_device"
DEVICE_TYPE_MEDIA_RECEIVER = "devices.types.media_device.receiver"

# Capability types
CAPABILITY_ON_OFF = "devices.capabilities.on_off"
CAPABILITY_RANGE = "devices.capabilities.range"
CAPABILITY_TOGGLE = "devices.capabilities.toggle"

# Capability instances
INSTANCE_VOLUME = "volume"
INSTANCE_MUTE = "mute"
INSTANCE_PAUSE = "pause"

# State update interval (seconds)
STATE_UPDATE_INTERVAL = 5
