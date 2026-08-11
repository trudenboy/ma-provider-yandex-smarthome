"""Root conftest: ensure provider/ is importable and mock MA dependencies for tests."""

from __future__ import annotations

import contextlib
import importlib.util
import sys
import types
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. Mock music_assistant_models so provider imports don't fail
# ---------------------------------------------------------------------------

# StrEnum shim for Python < 3.11
try:
    from enum import StrEnum as _StrEnum
except ImportError:

    class _StrEnum(str, Enum):  # type: ignore[no-redef]  # noqa: UP042
        """Backport of StrEnum for Python < 3.11."""


def _ensure_module(name: str, attrs: dict | None = None) -> types.ModuleType:
    """Create and register a stub module if not already present."""
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    mod.__package__ = name
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    # Set __path__ for packages (allows sub-imports)
    mod.__path__ = []  # type: ignore[attr-defined]
    sys.modules[name] = mod
    return mod


# Create music_assistant_models namespace
_ensure_module("music_assistant_models")


# music_assistant_models.enums
class _PlaybackState(_StrEnum):
    IDLE = "idle"
    PAUSED = "paused"
    PLAYING = "playing"
    UNKNOWN = "unknown"


class _EventType(_StrEnum):
    PLAYER_ADDED = "player_added"
    PLAYER_UPDATED = "player_updated"
    PLAYER_REMOVED = "player_removed"
    AUTH_SESSION = "auth_session"


class _ConfigEntryType(_StrEnum):
    STRING = "string"
    SECURE_STRING = "secure_string"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    LABEL = "label"
    ACTION = "action"


class _ProviderFeature(_StrEnum):
    pass


class _MediaType(_StrEnum):
    ARTIST = "artist"
    ALBUM = "album"
    TRACK = "track"
    PLAYLIST = "playlist"
    RADIO = "radio"
    UNKNOWN = "unknown"


class _RepeatMode(_StrEnum):
    OFF = "off"
    ONE = "one"
    ALL = "all"
    UNKNOWN = "unknown"


class _QueueOption(_StrEnum):
    PLAY = "play"
    REPLACE = "replace"
    NEXT = "next"
    REPLACE_NEXT = "replace_next"
    ADD = "add"
    UNKNOWN = "unknown"


_ensure_module(
    "music_assistant_models.enums",
    {
        "PlaybackState": _PlaybackState,
        "EventType": _EventType,
        "ConfigEntryType": _ConfigEntryType,
        "ProviderFeature": _ProviderFeature,
        "MediaType": _MediaType,
        "RepeatMode": _RepeatMode,
        "QueueOption": _QueueOption,
    },
)


# music_assistant_models.config_entries
class _ConfigEntry:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _ConfigValueOption:
    # Mirrors music_assistant_models.config_entries.ConfigValueOption:
    # ``value`` first, optional ``title``.
    def __init__(self, value=None, title=None):
        self.value = value
        self.title = title


class _ProviderType(_StrEnum):
    MUSIC = "music"
    PLAYER = "player"
    METADATA = "metadata"
    PLUGIN = "plugin"


_prov_enums = sys.modules.get("music_assistant_models.enums")
if _prov_enums is not None and not hasattr(_prov_enums, "ProviderType"):
    _prov_enums.ProviderType = _ProviderType

_ensure_module(
    "music_assistant_models.config_entries",
    {"ConfigEntry": _ConfigEntry, "ConfigValueOption": _ConfigValueOption, "ConfigValueType": str},
)

# music_assistant_models.provider
_ensure_module(
    "music_assistant_models.provider",
    {"ProviderManifest": MagicMock},
)

# music_assistant_models.player
_ensure_module("music_assistant_models.player", {"Player": MagicMock})


# music_assistant_models.event
class _MassEvent:
    def __init__(self, event=None, data=None):
        self.event = event
        self.data = data


_ensure_module("music_assistant_models.event", {"MassEvent": _MassEvent})


# music_assistant_models.errors — needed by ya_passport_auth.ma (the shared
# auth layer imports the MA error types at module level).
class _MusicAssistantError(Exception):
    pass


class _LoginFailed(_MusicAssistantError):
    pass


class _ResourceTemporarilyUnavailable(_MusicAssistantError):
    pass


class _InvalidDataError(_MusicAssistantError):
    pass


_ensure_module(
    "music_assistant_models.errors",
    {
        "MusicAssistantError": _MusicAssistantError,
        "LoginFailed": _LoginFailed,
        "ResourceTemporarilyUnavailable": _ResourceTemporarilyUnavailable,
        "InvalidDataError": _InvalidDataError,
    },
)

# ---------------------------------------------------------------------------
# 2. Mock music_assistant server modules
# ---------------------------------------------------------------------------

_ensure_module("music_assistant")
_ensure_module("music_assistant.models")
_ensure_module("music_assistant.mass", {"MusicAssistant": MagicMock})


class _PluginProvider:
    """Minimal stub of music_assistant.models.plugin.PluginProvider."""

    def __init__(self, mass=None, manifest=None, config=None, supported_features=None):
        self.mass = mass
        self.manifest = manifest
        self.config = config or MagicMock()
        self.supported_features = supported_features or set()
        self.logger = MagicMock()

    def get_setup_value(self, key, default=None):
        """Read setup data, falling back to legacy config values."""
        setup_data = getattr(self.config, "setup_data", None)
        if isinstance(setup_data, dict) and key in setup_data:
            return setup_data[key]
        return self.config.get_value(key, default)

    def _update_setup_data(self, key, value, immediate=True):
        """Update the in-memory setup-data stand-in used by provider tests."""
        setup_data = getattr(self.config, "setup_data", None)
        if not isinstance(setup_data, dict):
            setup_data = {}
            self.config.setup_data = setup_data
        setup_data[key] = value

    async def handle_async_init(self):
        pass

    async def loaded_in_mass(self):
        pass

    async def unload(self, is_removed=False):
        pass


_ensure_module("music_assistant.models.plugin", {"PluginProvider": _PluginProvider})
_ensure_module("music_assistant.models", {"ProviderInstanceType": MagicMock})


class _SetupFlowError(Exception):
    """Minimal setup-flow error carrying a translation key."""

    def __init__(self, message: str = "", translation_key: str | None = None):
        super().__init__(message)
        self.translation_key = translation_key


class _AbortFlow(Exception):
    """Minimal setup-flow abort carrying a translation key."""

    def __init__(self, translation_key: str):
        super().__init__(translation_key)
        self.translation_key = translation_key


_ensure_module(
    "music_assistant.models.setup_flow",
    {"AbortFlow": _AbortFlow, "SetupFlowError": _SetupFlowError},
)

# ---------------------------------------------------------------------------
# 3. Make provider/ importable as both 'provider' and
#    'music_assistant.providers.yandex_smarthome'
# ---------------------------------------------------------------------------

_provider_path = Path(__file__).parent / "provider"

# Ensure parent namespace packages exist
for _pkg in ("music_assistant.providers",):
    if _pkg not in sys.modules:
        _mod = types.ModuleType(_pkg)
        _mod.__path__ = []  # type: ignore[attr-defined]
        _mod.__package__ = _pkg
        sys.modules[_pkg] = _mod

# Insert provider/ into sys.path so its modules are importable
if str(_provider_path) not in sys.path:
    sys.path.insert(0, str(_provider_path))

# Register a package alias so `from music_assistant.providers.yandex_smarthome.X import Y` works
_spec = importlib.util.spec_from_file_location(
    "music_assistant.providers.yandex_smarthome",
    _provider_path / "__init__.py",
    submodule_search_locations=[str(_provider_path)],
)
if _spec and "music_assistant.providers.yandex_smarthome" not in sys.modules:
    _pkg_mod = importlib.util.module_from_spec(_spec)
    _pkg_mod.__path__ = [str(_provider_path)]  # type: ignore[attr-defined]
    _pkg_mod.__package__ = "music_assistant.providers.yandex_smarthome"
    sys.modules["music_assistant.providers.yandex_smarthome"] = _pkg_mod
    with contextlib.suppress(
        Exception
    ):  # provider __init__ may have MA-specific imports; best-effort
        _spec.loader.exec_module(_pkg_mod)  # type: ignore[union-attr]
