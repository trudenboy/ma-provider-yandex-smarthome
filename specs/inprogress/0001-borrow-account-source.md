---
id: "0001"
title: "Borrow the Yandex account from a linked Yandex Music provider"
size: S
status: inprogress
priority: P1
effort_minutes: 10
feature_id:
---

## Problem Statement

Skill auto-create runs its own Yandex Passport Device Flow and caches its
own x_token, even when the user already signed into Yandex through the
Yandex Music provider — a second login and a second token for one account.

## Solution Summary

A "Yandex account source" dropdown (same option the other yandex providers
offer): pick a configured Yandex Music instance to borrow its x_token for
skill auto-create, or keep "Use own credentials". When borrowing, the
Device Flow never runs — the borrowed token authenticates the dialogs
session read-only (never persisted into this provider's config, never
rotated), and a rejected/unavailable source reports "re-authenticate the
Yandex Music provider" instead of silently falling back to an own Device
Flow.

## Acceptance Criteria

1. The settings form shows the source dropdown listing every configured
   Yandex Music instance plus "Use own credentials (default)"; a stale
   selection normalizes back to own.
2. With a source selected, auto-create authenticates with the borrowed
   x_token and never opens the Device Flow popup.
3. The borrowed token is never written into this provider's `auth_x_token`
   storage.
4. A linked instance that is missing or holds no x_token fails the
   auto-create step with an actionable message in the status area (no
   Device Flow fallback).
5. With "Use own credentials", behavior is byte-identical to today
   (cached-token fast path, Device Flow fallback, token persistence).

## Test Plan

- `test_dropdown_lists_instances_and_own` — options and default.
- `test_stale_selection_normalizes_to_own`.
- `test_authenticator_no_device_flow_when_disallowed` — cached token
  rejected + `allow_device_flow=False` → LoginFailed mentioning Yandex
  Music, Device Flow never started.
- `test_auto_create_borrow_uses_ym_token_without_persistence` — the
  authenticator receives the YM x_token; `on_token_obtained` absent;
  own storage untouched.
- `test_auto_create_borrow_source_error_lands_in_artifacts` — missing YM
  instance → artifacts FAILED with actionable message.
