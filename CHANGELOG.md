# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] — v0.2.0

### Added
- **Next/Previous track** — `range(channel)` capability with relative actions ("Алиса, дальше/назад")
- **Input source selection** — `mode(input_source)` capability maps MA source_list to Yandex modes (up to 10 sources)
- **Player filter** — config option to select which MA players are exposed to Yandex Smart Home

### Changed
- Updated README with full capabilities table, installation guide, and voice commands

## [0.1.0] — 2025-01-XX

### Added
- Initial plugin provider for Yandex Smart Home integration
- Cloud relay connection via yaha-cloud.ru WebSocket
- Cloud Plus mode with private skill support via Yandex.Dialogs
- Auto-registration config flow with OTP code generation
- Device registration and discovery (media_device.receiver)
- Capabilities: on_off, range(volume), toggle(mute), toggle(pause)
- State reporting to Yandex with 1s debounce and hourly heartbeat
- Discovery notifications on player add/remove
