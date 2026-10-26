# Reverse-sync: upstream PR #6382

Ported from music-assistant/server#6382 into `yandex_smarthome`.

## Summary

Setup forms keep the raised `SetupFlowError` itself as the field error, so its localized message survives across providers and flow aborts. The provider already defines `_collect_skill_token` earlier in the module, so only its error types change; the radar's duplicate copy was dropped while resolving the conflict.
