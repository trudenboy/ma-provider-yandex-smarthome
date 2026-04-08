"""MA Player ↔ Yandex Smart Home device mapper.

Maps Music Assistant Player state to Yandex Smart Home device descriptions,
capability states, and action execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .constants import (
    ERROR_DEVICE_UNREACHABLE,
    ERROR_INTERNAL_ERROR,
    ERROR_INVALID_ACTION,
    INSTANCE_MUTE,
    INSTANCE_ON,
    INSTANCE_PAUSE,
    INSTANCE_VOLUME,
    UNIT_PERCENT,
    YANDEX_DEVICE_TYPE_RECEIVER,
)
from .schema import (
    ActionResult,
    CapabilityAction,
    CapabilityActionResult,
    CapabilityDescription,
    CapabilityInstanceState,
    CapabilityParameters,
    CapabilityState,
    DeviceDescription,
    DeviceState,
    RangeParameters,
    YandexCapabilityType,
    YandexDeviceInfo,
)

if TYPE_CHECKING:
    from music_assistant_models.player import Player

_LOGGER = logging.getLogger(__name__)


def _volume_range_params() -> CapabilityParameters:
    """Build range parameters for volume capability."""
    return CapabilityParameters(
        instance=INSTANCE_VOLUME,
        range=RangeParameters(min=0, max=100, precision=1),
        unit=UNIT_PERCENT,
    )


def get_device_description(player: Player) -> DeviceDescription:
    """Build a Yandex Smart Home device description from an MA player."""
    capabilities = [
        CapabilityDescription(type=YandexCapabilityType.ON_OFF),
        CapabilityDescription(
            type=YandexCapabilityType.RANGE,
            parameters=_volume_range_params(),
        ),
        CapabilityDescription(
            type=YandexCapabilityType.TOGGLE,
            parameters=CapabilityParameters(instance=INSTANCE_MUTE),
        ),
        CapabilityDescription(
            type=YandexCapabilityType.TOGGLE,
            parameters=CapabilityParameters(instance=INSTANCE_PAUSE),
        ),
    ]

    model = "MA Player"
    if hasattr(player, "device_info") and player.device_info:
        model = getattr(player.device_info, "model", model) or model

    return DeviceDescription(
        id=player.player_id,
        name=player.name,
        type=YANDEX_DEVICE_TYPE_RECEIVER,
        capabilities=capabilities,
        device_info=YandexDeviceInfo(model=model),
    )


def get_device_state(player: Player) -> DeviceState:
    """Read current MA player state and convert to Yandex capability states."""
    from music_assistant_models.enums import PlaybackState

    is_playing = player.playback_state in (PlaybackState.PLAYING, PlaybackState.PAUSED)
    is_paused = player.playback_state == PlaybackState.PAUSED
    volume = player.volume_level if player.volume_level is not None else 0
    muted = player.volume_muted if player.volume_muted is not None else False

    return DeviceState(
        id=player.player_id,
        capabilities=[
            CapabilityState(
                type=YandexCapabilityType.ON_OFF,
                state=CapabilityInstanceState(instance=INSTANCE_ON, value=is_playing),
            ),
            CapabilityState(
                type=YandexCapabilityType.RANGE,
                state=CapabilityInstanceState(instance=INSTANCE_VOLUME, value=volume),
            ),
            CapabilityState(
                type=YandexCapabilityType.TOGGLE,
                state=CapabilityInstanceState(instance=INSTANCE_MUTE, value=muted),
            ),
            CapabilityState(
                type=YandexCapabilityType.TOGGLE,
                state=CapabilityInstanceState(instance=INSTANCE_PAUSE, value=is_paused),
            ),
        ],
    )


async def execute_capability_action(
    mass: Any,
    player_id: str,
    action: CapabilityAction,
    current_volume: int = 0,
) -> CapabilityActionResult:
    """Execute a Yandex capability action by calling the corresponding MA player command.

    Returns a CapabilityActionResult with success or error status.
    """
    instance = action.state.instance
    value = action.state.value

    try:
        if action.type == YandexCapabilityType.ON_OFF:
            if value:
                await mass.players.cmd_play(player_id)
            else:
                await mass.players.cmd_stop(player_id)

        elif action.type == YandexCapabilityType.RANGE and instance == INSTANCE_VOLUME:
            if action.state.relative:
                target = max(0, min(100, current_volume + int(value)))
            else:
                target = max(0, min(100, int(value)))
            await mass.players.cmd_volume_set(player_id, target)
            value = target

        elif action.type == YandexCapabilityType.TOGGLE and instance == INSTANCE_MUTE:
            await mass.players.cmd_volume_mute(player_id, bool(value))

        elif action.type == YandexCapabilityType.TOGGLE and instance == INSTANCE_PAUSE:
            if value:
                await mass.players.cmd_pause(player_id)
            else:
                await mass.players.cmd_play(player_id)

        else:
            return CapabilityActionResult(
                type=action.type,
                state=CapabilityInstanceState(instance=instance, value=value),
                action_result=ActionResult(
                    status="ERROR",
                    error_code=ERROR_INVALID_ACTION,
                    error_message=f"Unknown capability: {action.type}/{instance}",
                ),
            )

    except Exception:
        _LOGGER.exception("Error executing action %s/%s on %s", action.type, instance, player_id)
        return CapabilityActionResult(
            type=action.type,
            state=CapabilityInstanceState(instance=instance, value=value),
            action_result=ActionResult(
                status="ERROR",
                error_code=ERROR_INTERNAL_ERROR,
            ),
        )

    return CapabilityActionResult(
        type=action.type,
        state=CapabilityInstanceState(instance=instance, value=value),
        action_result=ActionResult(status="DONE"),
    )


def is_player_exposable(player: Player) -> bool:
    """Determine whether an MA player should be exposed to Yandex Smart Home."""
    if not player.available:
        return False
    if not player.enabled:
        return False
    # Don't expose players that are synced to another player (they are controlled via leader)
    if player.synced_to:
        return False
    return True


def make_error_device_state(device_id: str) -> DeviceState:
    """Create an error DeviceState for an unreachable device."""
    return DeviceState(
        id=device_id,
        error_code=ERROR_DEVICE_UNREACHABLE,
        error_message="Device is not available",
    )


def make_error_action_result(
    device_id: str, actions: list[CapabilityAction]
) -> list[CapabilityActionResult]:
    """Create error action results for all capabilities of an unreachable device."""
    return [
        CapabilityActionResult(
            type=a.type,
            state=CapabilityInstanceState(instance=a.state.instance, value=a.state.value),
            action_result=ActionResult(
                status="ERROR",
                error_code=ERROR_DEVICE_UNREACHABLE,
            ),
        )
        for a in actions
    ]
