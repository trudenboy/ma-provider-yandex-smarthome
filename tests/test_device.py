"""Tests for provider/device.py — MA Player ↔ Yandex device mapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from unittest.mock import AsyncMock

import pytest

# Use the PlaybackState from conftest's mock enums
from music_assistant_models.enums import PlaybackState

from provider.constants import (
    INSTANCE_MUTE,
    INSTANCE_ON,
    INSTANCE_PAUSE,
    INSTANCE_VOLUME,
    YANDEX_DEVICE_TYPE_RECEIVER,
)
from provider.device import (
    execute_capability_action,
    get_device_description,
    get_device_state,
    is_player_exposable,
    make_error_action_result,
    make_error_device_state,
)
from provider.schema import (
    CapabilityAction,
    CapabilityActionState,
    YandexCapabilityType,
)


@dataclass
class MockDeviceInfo:
    model: str = "Test Speaker"


@dataclass
class MockPlayer:
    """Minimal mock of music_assistant_models.player.Player."""

    player_id: str = "test_player_1"
    name: str = "Living Room Speaker"
    available: bool = True
    enabled: bool = True
    powered: bool | None = True
    playback_state: PlaybackState = PlaybackState.IDLE
    volume_level: int | None = 50
    volume_muted: bool | None = False
    synced_to: str | None = None
    device_info: MockDeviceInfo | None = None
    supported_features: set[str] = field(default_factory=set)


class MockPlayers:
    """Mock of mass.players controller."""

    def __init__(self) -> None:
        self.cmd_play = AsyncMock()
        self.cmd_stop = AsyncMock()
        self.cmd_pause = AsyncMock()
        self.cmd_volume_set = AsyncMock()
        self.cmd_volume_mute = AsyncMock()


@dataclass
class MockMass:
    players: MockPlayers = field(default_factory=MockPlayers)


# ---------------------------------------------------------------------------
# Tests: get_device_description
# ---------------------------------------------------------------------------


class TestGetDeviceDescription:
    def test_basic_description(self):
        player = MockPlayer()
        desc = get_device_description(player)
        assert desc.id == "test_player_1"
        assert desc.name == "Living Room Speaker"
        assert desc.type == YANDEX_DEVICE_TYPE_RECEIVER
        assert len(desc.capabilities) == 4

    def test_capability_types(self):
        player = MockPlayer()
        desc = get_device_description(player)
        types = [c.type for c in desc.capabilities]
        assert YandexCapabilityType.ON_OFF in types
        assert YandexCapabilityType.RANGE in types
        assert YandexCapabilityType.TOGGLE in types

    def test_volume_range_params(self):
        player = MockPlayer()
        desc = get_device_description(player)
        range_cap = next(c for c in desc.capabilities if c.type == YandexCapabilityType.RANGE)
        assert range_cap.parameters is not None
        assert range_cap.parameters.instance == "volume"
        assert range_cap.parameters.range is not None
        assert range_cap.parameters.range.min == 0
        assert range_cap.parameters.range.max == 100

    def test_device_info_model(self):
        player = MockPlayer(device_info=MockDeviceInfo(model="KEF LS50"))
        desc = get_device_description(player)
        assert desc.device_info is not None
        assert desc.device_info.model == "KEF LS50"

    def test_device_info_default(self):
        player = MockPlayer()
        desc = get_device_description(player)
        assert desc.device_info is not None
        assert desc.device_info.model == "MA Player"


# ---------------------------------------------------------------------------
# Tests: get_device_state
# ---------------------------------------------------------------------------


class TestGetDeviceState:
    def test_idle_state(self):
        player = MockPlayer(playback_state=PlaybackState.IDLE, volume_level=30, volume_muted=False)
        state = get_device_state(player)
        assert state.id == "test_player_1"

        by_instance = {c.state.instance: c.state.value for c in state.capabilities}
        assert by_instance[INSTANCE_ON] is False  # idle → not on
        assert by_instance[INSTANCE_VOLUME] == 30
        assert by_instance[INSTANCE_MUTE] is False
        assert by_instance[INSTANCE_PAUSE] is False

    def test_playing_state(self):
        player = MockPlayer(playback_state=PlaybackState.PLAYING, volume_level=75)
        state = get_device_state(player)

        by_instance = {c.state.instance: c.state.value for c in state.capabilities}
        assert by_instance[INSTANCE_ON] is True
        assert by_instance[INSTANCE_VOLUME] == 75
        assert by_instance[INSTANCE_PAUSE] is False

    def test_paused_state(self):
        player = MockPlayer(playback_state=PlaybackState.PAUSED, volume_level=50)
        state = get_device_state(player)

        by_instance = {c.state.instance: c.state.value for c in state.capabilities}
        assert by_instance[INSTANCE_ON] is True  # paused is still "on"
        assert by_instance[INSTANCE_PAUSE] is True

    def test_none_volume(self):
        player = MockPlayer(volume_level=None, volume_muted=None)
        state = get_device_state(player)

        by_instance = {c.state.instance: c.state.value for c in state.capabilities}
        assert by_instance[INSTANCE_VOLUME] == 0
        assert by_instance[INSTANCE_MUTE] is False


# ---------------------------------------------------------------------------
# Tests: execute_capability_action
# ---------------------------------------------------------------------------


class TestExecuteCapabilityAction:
    @pytest.mark.asyncio
    async def test_on_off_true_plays(self):
        mass = MockMass()
        action = CapabilityAction(
            type=YandexCapabilityType.ON_OFF,
            state=CapabilityActionState(instance="on", value=True),
        )
        result = await execute_capability_action(mass, "p1", action)
        mass.players.cmd_play.assert_awaited_once_with("p1")
        assert result.action_result.status == "DONE"

    @pytest.mark.asyncio
    async def test_on_off_false_stops(self):
        mass = MockMass()
        action = CapabilityAction(
            type=YandexCapabilityType.ON_OFF,
            state=CapabilityActionState(instance="on", value=False),
        )
        result = await execute_capability_action(mass, "p1", action)
        mass.players.cmd_stop.assert_awaited_once_with("p1")
        assert result.action_result.status == "DONE"

    @pytest.mark.asyncio
    async def test_volume_absolute(self):
        mass = MockMass()
        action = CapabilityAction(
            type=YandexCapabilityType.RANGE,
            state=CapabilityActionState(instance="volume", value=65),
        )
        result = await execute_capability_action(mass, "p1", action)
        mass.players.cmd_volume_set.assert_awaited_once_with("p1", 65)
        assert result.action_result.status == "DONE"

    @pytest.mark.asyncio
    async def test_volume_relative_up(self):
        mass = MockMass()
        action = CapabilityAction(
            type=YandexCapabilityType.RANGE,
            state=CapabilityActionState(instance="volume", value=10, relative=True),
        )
        result = await execute_capability_action(mass, "p1", action, current_volume=50)
        mass.players.cmd_volume_set.assert_awaited_once_with("p1", 60)
        assert result.state.value == 60

    @pytest.mark.asyncio
    async def test_volume_relative_clamp_max(self):
        mass = MockMass()
        action = CapabilityAction(
            type=YandexCapabilityType.RANGE,
            state=CapabilityActionState(instance="volume", value=20, relative=True),
        )
        result = await execute_capability_action(mass, "p1", action, current_volume=90)
        mass.players.cmd_volume_set.assert_awaited_once_with("p1", 100)
        assert result.state.value == 100

    @pytest.mark.asyncio
    async def test_volume_relative_clamp_min(self):
        mass = MockMass()
        action = CapabilityAction(
            type=YandexCapabilityType.RANGE,
            state=CapabilityActionState(instance="volume", value=-20, relative=True),
        )
        result = await execute_capability_action(mass, "p1", action, current_volume=10)
        mass.players.cmd_volume_set.assert_awaited_once_with("p1", 0)
        assert result.state.value == 0

    @pytest.mark.asyncio
    async def test_mute_toggle(self):
        mass = MockMass()
        action = CapabilityAction(
            type=YandexCapabilityType.TOGGLE,
            state=CapabilityActionState(instance="mute", value=True),
        )
        result = await execute_capability_action(mass, "p1", action)
        mass.players.cmd_volume_mute.assert_awaited_once_with("p1", True)
        assert result.action_result.status == "DONE"

    @pytest.mark.asyncio
    async def test_pause_true(self):
        mass = MockMass()
        action = CapabilityAction(
            type=YandexCapabilityType.TOGGLE,
            state=CapabilityActionState(instance="pause", value=True),
        )
        result = await execute_capability_action(mass, "p1", action)
        mass.players.cmd_pause.assert_awaited_once_with("p1")
        assert result.action_result.status == "DONE"

    @pytest.mark.asyncio
    async def test_pause_false_plays(self):
        mass = MockMass()
        action = CapabilityAction(
            type=YandexCapabilityType.TOGGLE,
            state=CapabilityActionState(instance="pause", value=False),
        )
        result = await execute_capability_action(mass, "p1", action)
        mass.players.cmd_play.assert_awaited_once_with("p1")

    @pytest.mark.asyncio
    async def test_unknown_capability_returns_error(self):
        mass = MockMass()
        action = CapabilityAction(
            type="devices.capabilities.unknown",
            state=CapabilityActionState(instance="foo", value=42),
        )
        result = await execute_capability_action(mass, "p1", action)
        assert result.action_result.status == "ERROR"
        assert result.action_result.error_code == "INVALID_ACTION"

    @pytest.mark.asyncio
    async def test_command_exception_returns_error(self):
        mass = MockMass()
        mass.players.cmd_play.side_effect = RuntimeError("Connection lost")
        action = CapabilityAction(
            type=YandexCapabilityType.ON_OFF,
            state=CapabilityActionState(instance="on", value=True),
        )
        result = await execute_capability_action(mass, "p1", action)
        assert result.action_result.status == "ERROR"
        assert result.action_result.error_code == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Tests: is_player_exposable
# ---------------------------------------------------------------------------


class TestIsPlayerExposable:
    def test_normal_player(self):
        assert is_player_exposable(MockPlayer()) is True

    def test_unavailable(self):
        assert is_player_exposable(MockPlayer(available=False)) is False

    def test_disabled(self):
        assert is_player_exposable(MockPlayer(enabled=False)) is False

    def test_synced_to_another(self):
        assert is_player_exposable(MockPlayer(synced_to="other_player")) is False


# ---------------------------------------------------------------------------
# Tests: error helpers
# ---------------------------------------------------------------------------


class TestErrorHelpers:
    def test_make_error_device_state(self):
        state = make_error_device_state("p1")
        assert state.id == "p1"
        assert state.error_code == "DEVICE_UNREACHABLE"
        assert state.capabilities == []

    def test_make_error_action_result(self):
        actions = [
            CapabilityAction(
                type=YandexCapabilityType.ON_OFF,
                state=CapabilityActionState(instance="on", value=True),
            ),
            CapabilityAction(
                type=YandexCapabilityType.RANGE,
                state=CapabilityActionState(instance="volume", value=50),
            ),
        ]
        results = make_error_action_result("p1", actions)
        assert len(results) == 2
        assert all(r.action_result.status == "ERROR" for r in results)
        assert all(r.action_result.error_code == "DEVICE_UNREACHABLE" for r in results)
