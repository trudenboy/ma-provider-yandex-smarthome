# Cloud Plus Setup Guide

Cloud Plus mode allows you to use Music Assistant with Yandex Alice even if you already have the public **Yaha Cloud** skill linked to your Yandex account (e.g., for Home Assistant).

## When to Use Cloud Plus

| Scenario | Mode |
|----------|------|
| No existing Yaha Cloud integration | **cloud** (default) |
| Already using Yaha Cloud for Home Assistant | **cloud_plus** |

Yandex Smart Home only allows **one binding per skill** per account. If Yaha Cloud is already linked, you need a private skill (Cloud Plus) for Music Assistant.

## Architecture

```
Alice → Your private skill → yaha-cloud.ru relay → WebSocket → MA plugin (commands)
State updates → MA plugin → POST dialogs.yandex.net/api/v1/skills/{skill_id}/callback → Alice
```

Both **cloud** and **cloud_plus** use the yaha-cloud.ru WebSocket relay for receiving commands. The difference is how state notifications are sent:
- **cloud**: via yaha-cloud.ru callback relay
- **cloud_plus**: directly to Yandex Dialogs API using your private skill's OAuth token

## Setup Steps

### 1. Register Cloud Instance

In Music Assistant → Settings → Providers → Yandex Smart Home:

1. Set **Connection Type** to `cloud_plus`
2. Click **Register with cloud** — this registers your instance on yaha-cloud.ru
3. Note the **webhook URL** shown in the instructions

### 2. Create a Private Skill

1. Go to [Yandex.Dialogs Developer Console](https://dialogs.yandex.ru/developer/smart-home)
2. Click **Create dialog** → **Smart Home**
3. Fill in the required fields:
   - **Name**: any name (e.g., "Music Assistant")
   - **Webhook URL**: paste the URL from step 1:
     ```
     https://yaha-cloud.ru/api/home_assistant/v1/skill/{your_instance_id}
     ```
4. **Save** the skill. Do NOT publish it — it works as a private (draft) skill.

### 3. Get Skill ID

The skill ID is a UUID visible in your browser's address bar:

```
https://dialogs.yandex.ru/developer/skills/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/
                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                              This is your skill_id
```

### 4. Get OAuth Token

1. Open this URL in your browser:
   ```
   https://oauth.yandex.ru/authorize?response_type=token&client_id=c473ca268cd749d3a8371351a8f2bcbd
   ```
2. Authorize with **the same Yandex account** that owns the skill
3. After redirect, copy the `access_token` from the URL fragment:
   ```
   https://oauth.yandex.ru/verification_code#access_token=YOUR_TOKEN_HERE&...
   ```

### 5. Configure the Plugin

Back in Music Assistant → Yandex Smart Home settings:

1. Enter the **Skill ID** (UUID from step 3)
2. Enter the **Skill OAuth Token** (from step 4)
3. Click **Save**

### 6. Link the Skill

1. Open the **Yandex** app (or Дом с Алисой)
2. Go to **Devices** → **Add device** → **Smart Home**
3. Find your private skill (by the name you gave it in step 2)
4. Click **Get OTP code** in MA settings if prompted for a code
5. Enter the OTP code in the Yandex app

## Troubleshooting

### "Skill not found" in Yandex app
Private (draft) skills are only visible to the Yandex account that created them. Make sure you're using the same account.

### State updates not working
- Verify the OAuth token is valid and from the correct account
- Check MA logs for "State callback failed" messages
- The Yandex Dialogs API returns HTTP 202 (not 200) on success — this is normal

### Duplicate devices
If you have Home Assistant also exposing media players via the public Yaha Cloud skill, you may see duplicates. Either:
- Filter which players are exposed in each integration
- Use only Cloud Plus for media players
