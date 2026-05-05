# Voice command logic — Yandex Dialogs «Навык» (custom skill)

This document describes how the experimental dialog-skill webhook
parses Russian voice commands from Alice and resolves them to MA
playback actions. Implementation lives in
[`provider/dialogs_nlu.py`](../provider/dialogs_nlu.py),
[`provider/dialogs_player.py`](../provider/dialogs_player.py), and
[`provider/dialogs.py`](../provider/dialogs.py) (HTTP handler).

## Wire format

Yandex sends a POST to
`{external_base_url}/api/yandex_dialogs/webhook/{secret}` with a JSON
envelope shaped like:

```json
{
  "session": {
    "skill_id": "<our-skill-uuid>",
    "session_id": "<per-conversation>",
    "user_id":   "<per-Yandex-account>",
    "new":       true | false
  },
  "request": {
    "command": "включи металлику на проигрывателе",
    "original_utterance": "Алиса, попроси Музыкальный Ассистент включить металлику на проигрывателе"
  },
  "version": "1.0"
}
```

Yandex strips its own activation prefix (`Алиса, попроси <skill-name>`)
from `command`; we get the *raw user phrase* in `command` and only that
goes through the parser.

## Parse pipeline (`parse_command`)

Steps applied in order to `request.command`:

1. **Punctuation normalisation** — strip `! ? . , ; : « » " „ "` and
   collapse whitespace. Apostrophes and hyphens inside words are kept
   (`rock'n'roll`, `rock-n-roll`).
2. **Defensive `Алиса,` prefix strip** — Yandex usually does this on
   its side, but we drop a leading vocative if present.
3. **Trailing player-hint extraction** — regex `\s+на\s+(?P<hint>.+?)\s*$`
   pulls the suffix introduced by the Russian preposition `на`. The
   hint can be multi-word (e.g. `на кухонной колонке`).
4. **Verb strip** — leading imperative / infinitive verb of the
   "play / turn on / launch" family is removed. Accepted forms:
   - `включи` / `включите` / `включай` / `включайте` / `включить`
   - `поставь` / `поставьте` / `поставить`
   - `запусти` / `запустите` / `запустить`
   - `сыграй` / `сыграйте` / `сыграть`
   - `играй` / `играйте`
   - `послушай` / `послушайте` / `послушать`

5. **Kind classification** — the remaining text is matched against
   ordered prefix patterns. First match wins:

   | Marker prefix              | `kind`     | `radio_mode` | Notes                                     |
   |----------------------------|------------|--------------|-------------------------------------------|
   | `мою/свою/нашу волну`      | `my_wave`  | `True`       | yandex_music rotor `user:onyourwave`      |
   | `моё/мое радио`            | `my_wave`  | `True`       | same                                      |
   | `плейлист X` / `подборку X`| `playlist` | `False`      |                                           |
   | `альбом X` / `пластинку X` | `album`    | `False`      |                                           |
   | `исполнителя/группу X`     | `artist`   | `True`       | starts artist radio                       |
   | `песню/трек/композицию X`  | `track`    | `False`      |                                           |
   | `радио X`                  | `genre`    | `True`       | yandex_music genre rotor (artist fallback)|
   | `жанр X`                   | `genre`    | `True`       | same                                      |
   | *(no marker)*              | `search`   | `True`       | catch-all; see *Search prioritisation*    |

## Player resolution (`resolve_player`)

Filters all `mass.players.all_players()` to candidates that are
**available**, **enabled**, **not synced to a leader**, and (optionally)
inside the user's `Exposed Players` list. Then matches the hint:

1. **Both sides normalised** — lowercase, strip punctuation, strip a
   trailing Russian inflection suffix (`-ого -ому -ыми -ой -ом -ым -ы
   -е -у -а -и -й -ь`, longest first). So *"Кухня"* and *"на кухне"*
   both reduce to *"кухн"* and match exactly.
2. **Tier order**: exact normalised match → starts-with → contains.
   First non-empty tier wins; multiple matches in the same tier sort
   alphabetically and pick the first (with a WARNING log).
3. **Generic-word fallback** — if the hint contains a generic Russian
   stem for "speaker" / "player" (`колонк`, `плеер`, `проигрыватель`,
   `динамик`, `акустик`, `устройств`, etc.) and no specific name
   matched, fall through to:
   - the *default player* (last-used player for this session, if any);
   - the only exposed player when there's just one.
4. **No hint at all** — same fallback (default → single exposed),
   useful for follow-up commands in the same session.
5. **Otherwise** — return `None` and the handler responds *"Не нашёл
   колонку «<hint>». Скажи, например: на кухне."*

> Player names match against MA's `player.name`, *not* aliases set in
> the Yandex Smart Home app — Yandex does not forward those into the
> dialog skill payload. To use a custom voice name, rename the player
> in MA itself.

## Content resolution (`resolve_query`)

Dispatches by `parsed.kind`:

- `track` → `mass.music.search(media_types=[TRACK])` → first track
- `artist` → `mass.music.search(media_types=[ARTIST])` → first artist
- `album` → `mass.music.search(media_types=[ALBUM])` → first album
- `playlist` → `mass.music.search(media_types=[PLAYLIST])` → first playlist
- `my_wave` → yandex_music rotor `user:onyourwave`; first track URI
- `genre` → yandex_music genre rotor; falls back to artist search
- `search` → all four media types; **picker order:
  artists > albums > tracks > playlists**

### Search prioritisation rationale

For unqualified queries (`включи Iron Maiden`) users typically say a
band / artist name. Picking the artist first (with `radio_mode=True`)
matches that intent: MA starts an artist radio that keeps playing
related music. Playlists are de-prioritised — when the user wants a
playlist they say `плейлист <name>` explicitly.

If the user says a song name (`включи Yesterday`) the artists tier is
empty, so we fall through to `albums > tracks > playlists` — typically
landing on the track.

## Playback (`play_for_alice`)

After resolving:

1. If the player has a `power` feature and is currently `powered=False`,
   send `mass.players.cmd_power(player_id, True)`.
2. `mass.player_queues.play_media(queue_id=player_id, media=media,
   radio_mode=parsed.radio_mode)`. The call is fired via
   `self._mass.create_task(...)` so the webhook returns within
   Yandex's 4.5 s response budget; the actual stream start happens in
   the background.

## Session memory

The webhook handler keeps an in-memory `OrderedDict[session_id, (player_id, ts)]`
with a 200-entry LRU cap and 1-hour TTL. When a follow-up command in
the same conversation has no `на <player>` suffix, `resolve_player`
gets the previous session's player as `default_id` so the user can say
*"включи мою волну"* after *"включи джаз на кухне"* and the кухня
player is reused.

## Examples

| Voice command                                  | `kind`     | `query`           | `radio_mode` | `player_hint`     |
|------------------------------------------------|------------|-------------------|--------------|-------------------|
| `включи Metallica`                             | `search`   | `metallica`       | `True`       | (none)            |
| `включи Metallica на кухне`                    | `search`   | `metallica`       | `True`       | `кухне`           |
| `включить Iron Maiden на проигрывателе`        | `search`   | `iron maiden`     | `True`       | `проигрывателе`   |
| `включи песню Yesterday`                       | `track`    | `yesterday`       | `False`      | (none)            |
| `включи альбом Black Album на спальне`         | `album`    | `black album`     | `False`      | `спальне`         |
| `включи группу Beatles`                        | `artist`   | `beatles`         | `True`       | (none)            |
| `включи плейлист утренний джаз`                | `playlist` | `утренний джаз`   | `False`      | (none)            |
| `включи мою волну`                             | `my_wave`  | (empty)           | `True`       | (none)            |
| `включи жанр джаз на кухне`                    | `genre`    | `джаз`            | `True`       | `кухне`           |
| `сыграй Metallica на колонке`                  | `search`   | `metallica`       | `True`       | `колонке`         |
| `послушать рок`                                | `search`   | `рок`             | `True`       | (none)            |

## Debug

Set log level for `music_assistant.providers.yandex_smarthome.dialogs_nlu`
to `DEBUG` to see the parsed command + player resolution details for
every voice request. Useful for diagnosing mismatched hints / unexpected
search results.
