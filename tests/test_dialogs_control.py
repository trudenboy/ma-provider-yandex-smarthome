"""Tests for provider/dialogs_control.py — playback control NLU + executor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from provider.dialogs_control import (
    ParsedControl,
    control_confirmation,
    execute_control,
    parse_control,
)


class TestParseControl:
    """Table-driven tests for parse_control across all action families."""

    @pytest.mark.parametrize(
        ("phrase", "expected_action", "expected_value", "expected_hint"),
        [
            # pause
            ("пауза", "pause", None, None),
            ("на паузу", "pause", None, None),
            ("поставь на паузу", "pause", None, None),
            ("останови музыку", "pause", None, None),
            ("пауза на кухне", "pause", None, "кухне"),
            ("поставь на паузу на кухне", "pause", None, "кухне"),
            # resume
            ("продолжи", "resume", None, None),
            ("продолжить", "resume", None, None),
            ("включи снова", "resume", None, None),
            ("возобнови", "resume", None, None),
            # stop
            ("стоп", "stop", None, None),
            ("останови", "stop", None, None),
            ("выключи", "stop", None, None),
            ("выключи музыку", "stop", None, None),
            ("стоп на спальне", "stop", None, "спальне"),
            # next
            ("следующая", "next", None, None),
            ("следующий трек", "next", None, None),
            ("дальше", "next", None, None),
            ("переключи", "next", None, None),
            # previous
            ("предыдущая", "previous", None, None),
            ("предыдущий трек", "previous", None, None),
            ("назад", "previous", None, None),
            ("вернись", "previous", None, None),
            # volume relative
            ("громче", "volume_up", None, None),
            ("сделай громче", "volume_up", None, None),
            ("прибавь", "volume_up", None, None),
            ("прибавь громкость", "volume_up", None, None),
            ("тише", "volume_down", None, None),
            ("сделай тише", "volume_down", None, None),
            ("убавь", "volume_down", None, None),
            ("убавь громкость", "volume_down", None, None),
            ("громче на кухне", "volume_up", None, "кухне"),
            # volume set
            ("громкость 50", "volume_set", 50, None),
            ("громкость на 30", "volume_set", 30, None),
            ("громкость на 30 процентов", "volume_set", 30, None),
            ("сделай громкость 75", "volume_set", 75, None),
            ("громкость 50 на кухне", "volume_set", 50, "кухне"),
            # volume set clamping
            ("громкость 200", "volume_set", 100, None),
            # mute / unmute
            ("приглуши", "mute", None, None),
            ("выключи звук", "mute", None, None),
            ("беззвучно", "mute", None, None),
            ("включи звук", "unmute", None, None),
            ("сделай звук", "unmute", None, None),
            # alice prefix tolerated
            ("Алиса, пауза", "pause", None, None),
        ],
    )
    def test_parse(
        self,
        phrase: str,
        expected_action: str,
        expected_value: int | None,
        expected_hint: str | None,
    ) -> None:
        """Each parametrized phrase maps to the expected ParsedControl."""
        result = parse_control(phrase)
        assert result is not None, f"phrase={phrase!r} returned None"
        assert result.action == expected_action, f"phrase={phrase!r}"
        assert result.value == expected_value, f"phrase={phrase!r}"
        assert result.player_hint == expected_hint, f"phrase={phrase!r}"

    @pytest.mark.parametrize(
        "phrase",
        [
            "",
            "включи Metallica",
            "включи джаз на кухне",
            "включи песню Yesterday",
            "включи мою волну",
            "что-то непонятное",
            "включи альбом Black Album",
        ],
    )
    def test_play_phrases_return_none(self, phrase: str) -> None:
        """Phrases that should fall through to the play parser return None."""
        assert parse_control(phrase) is None


class TestControlConfirmation:
    """Tests for the user-facing confirmation strings."""

    @pytest.mark.parametrize(
        ("action", "value", "expected"),
        [
            ("pause", None, "Пауза."),
            ("resume", None, "Продолжаю."),
            ("stop", None, "Остановил."),
            ("next", None, "Следующая."),
            ("previous", None, "Предыдущая."),
            ("volume_up", None, "Громче."),
            ("volume_down", None, "Тише."),
            ("volume_set", 50, "Громкость 50."),
            ("mute", None, "Звук выключен."),
            ("unmute", None, "Звук включен."),
        ],
    )
    def test_confirmation(self, action: str, value: int | None, expected: str) -> None:
        """Confirmation text matches the expected per-action template."""
        ctrl = ParsedControl(action=action, value=value)  # type: ignore[arg-type]
        assert control_confirmation(ctrl) == expected


@pytest.mark.asyncio
class TestExecuteControl:
    """Tests that execute_control dispatches to the correct MA call."""

    def _make_mass(self) -> MagicMock:
        mass = MagicMock()
        mass.player_queues = MagicMock()
        mass.player_queues.pause = AsyncMock()
        mass.player_queues.resume = AsyncMock()
        mass.player_queues.stop = AsyncMock()
        mass.player_queues.next = AsyncMock()
        mass.player_queues.previous = AsyncMock()
        mass.players = MagicMock()
        mass.players.cmd_volume_up = AsyncMock()
        mass.players.cmd_volume_down = AsyncMock()
        mass.players.cmd_volume_set = AsyncMock()
        mass.players.cmd_volume_mute = AsyncMock()
        return mass

    def _player(self) -> MagicMock:
        player = MagicMock()
        player.player_id = "p1"
        return player

    async def test_pause_calls_pause(self) -> None:
        """action=pause invokes mass.player_queues.pause."""
        mass = self._make_mass()
        await execute_control(mass, ParsedControl(action="pause"), self._player())
        mass.player_queues.pause.assert_awaited_once_with("p1")

    async def test_resume_calls_resume(self) -> None:
        """action=resume invokes mass.player_queues.resume."""
        mass = self._make_mass()
        await execute_control(mass, ParsedControl(action="resume"), self._player())
        mass.player_queues.resume.assert_awaited_once_with("p1")

    async def test_stop_calls_stop(self) -> None:
        """action=stop invokes mass.player_queues.stop."""
        mass = self._make_mass()
        await execute_control(mass, ParsedControl(action="stop"), self._player())
        mass.player_queues.stop.assert_awaited_once_with("p1")

    async def test_next_calls_next(self) -> None:
        """action=next invokes mass.player_queues.next."""
        mass = self._make_mass()
        await execute_control(mass, ParsedControl(action="next"), self._player())
        mass.player_queues.next.assert_awaited_once_with("p1")

    async def test_previous_calls_previous(self) -> None:
        """action=previous invokes mass.player_queues.previous."""
        mass = self._make_mass()
        await execute_control(mass, ParsedControl(action="previous"), self._player())
        mass.player_queues.previous.assert_awaited_once_with("p1")

    async def test_volume_up(self) -> None:
        """action=volume_up invokes cmd_volume_up."""
        mass = self._make_mass()
        await execute_control(mass, ParsedControl(action="volume_up"), self._player())
        mass.players.cmd_volume_up.assert_awaited_once_with("p1")

    async def test_volume_down(self) -> None:
        """action=volume_down invokes cmd_volume_down."""
        mass = self._make_mass()
        await execute_control(mass, ParsedControl(action="volume_down"), self._player())
        mass.players.cmd_volume_down.assert_awaited_once_with("p1")

    async def test_volume_set(self) -> None:
        """action=volume_set invokes cmd_volume_set with the requested value."""
        mass = self._make_mass()
        await execute_control(
            mass, ParsedControl(action="volume_set", value=42), self._player()
        )
        mass.players.cmd_volume_set.assert_awaited_once_with("p1", 42)

    async def test_volume_set_none_falls_back_to_zero(self) -> None:
        """volume_set with value=None defaults to 0 (defensive)."""
        mass = self._make_mass()
        await execute_control(
            mass, ParsedControl(action="volume_set", value=None), self._player()
        )
        mass.players.cmd_volume_set.assert_awaited_once_with("p1", 0)

    async def test_mute(self) -> None:
        """action=mute invokes cmd_volume_mute(True)."""
        mass = self._make_mass()
        await execute_control(mass, ParsedControl(action="mute"), self._player())
        mass.players.cmd_volume_mute.assert_awaited_once_with("p1", True)

    async def test_unmute(self) -> None:
        """action=unmute invokes cmd_volume_mute(False)."""
        mass = self._make_mass()
        await execute_control(mass, ParsedControl(action="unmute"), self._player())
        mass.players.cmd_volume_mute.assert_awaited_once_with("p1", False)

    async def test_underlying_failure_is_swallowed(self) -> None:
        """An exception from the MA call is logged + swallowed (no re-raise)."""
        mass = self._make_mass()
        mass.player_queues.pause = AsyncMock(side_effect=RuntimeError("boom"))
        # Must not raise.
        await execute_control(mass, ParsedControl(action="pause"), self._player())
