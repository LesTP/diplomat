# Diplomat → Clankmates Arena

## Context

Diplomat's self-play harness runs N faction agents in one process with an in-memory `moderator` and `TestTransport` (`p:\shared\diplomat\src\flows\round_stepped.py`, `p:\shared\diplomat\tests\self_play\game_environment.py`). Production game traffic needs a real public platform: per `PROJECT.md:111` and `NEXT_STEPS.md` §5, that's intended to be Clankmates, with Telegram reserved for the operator coaching/review surface.

The operator has confirmed Clankmates is live but no external game is scheduled. The chosen scope (revised 2026-06-11) is a **single-tenant MVP arena**:

- Publish a **protocol** that any agent (third-party or Diplomat itself) can implement to play.
- Run a **host agent** under our Clankmates handle that posts the protocol manifest, accepts open signups, runs **one game at a time**, scores, archives transcripts. Operator-started; no always-on service deployment required for MVP.
- Plug **our Diplomat agent** in as one participant via a new `ClankmatesTransport` that conforms to the existing `Transport` protocol.
- **Players bring their own Clankmates accounts** (model A; see Decisions below). The host does not provision per-faction Clankmates identities.

**Out of MVP scope** (deferred to v2 "public arena"):
- Concurrent multi-game support — second `join_game` during an active game gets `busy`/`try later`
- SQLite persistence — JSON checkpoint to disk is sufficient for one game at a time
- Systemd / always-on deployment — operator launches the host when they want to run a game
- Leaderboard, ELO, cross-game stats
- Capacity / rate / DOS protection beyond basic input validation

Four design decisions are settled:

1. **Single host channel** for arena-level announcements + per-game inbox threads. Split per-game later if traffic conflicts. No per-faction archive channel for our agent; it's just a participant identity.
2. **Round advance** — hybrid: wall-clock deadline OR early advance when every signed-up faction has submitted a move.
3. **Scoring** — structured moves submitted via Clankmates **typed inboxes** (server-enforced JSON Schema Draft 2020-12); Diplomat's existing `OpenAIStructuredExtractor` (`p:\shared\diplomat\src\modules\extraction\`) narrows to optional summarization of free-text negotiation prose.
4. **Player identity = Clankmates handle (model A)** — each participant signs up with their own Clankmates address. The host's `join_ack` assigns a `faction_id` (just a label for game-internal use). Peer DMs go faction-handle to faction-handle directly. The host does **not** issue per-faction channel tokens or provision per-faction inboxes; players authenticate against Clankmates with their own credentials. Implication: open signup works without per-player provisioning, and any Clankmates user can participate.

## Source artifacts received

Two pieces of ground truth arrived during planning:

1. **`p:\shared\clanker-courts-player-client\`** — cloned from `https://github.com/clankmates/clanker-courts-player-client`. The operator's working Python client for his Clanker Courts arena. Same Clankmates wire protocol, different game.
2. **Screenshot of `clankm inbox schema --help`** confirming the typed-inbox subcommand surface (`show` / `set` / `remove` / `acceptance`) and CLI version `0.10.1`.

Pending:

- **Server source (Elixir).** Useful but not blocking — the player client + the message-types reference together cover the wire-level surface enough to design against.
- **Authoritative protocol doc** at `clanker-courts-server/docs/server-description.md` (per `p:\shared\clanker-courts-player-client\AGENTS.md:17`). The player client's `references/message-types.md` is a derived view; the server doc is the source of truth. Worth requesting when we ask Viktor about the Elixir source.

### Timing & protocol-stability notes (per Viktor's 2026-06-10 comments)

- **The CC protocol is not frozen.** Viktor is finishing local testing and *"may update the server and/or these skills"* before going public. Concrete consequences:
  - Don't deeply couple our `ARENA_PROTOCOL.md` schemas to the current message-types until CC's wire is stable.
  - Track upstream changes in the player client repo (`git pull` periodically) and update the vendored `clankmates.py` in `toolkit.clankmates_client` (per `p:\shared\toolkit\CLANKMATES_CLIENT_PLAN.md` "Upstream tracking" section) accordingly.
  - Treat our `move`, `round_report`, `diplomacy_message` schemas as **derivations** of CC's `order_package`, `movement_phase_report`, `diplomacy_message` — adopt structural changes Viktor makes upstream rather than diverging.
- **Phase G live smoke is gated on Viktor's public game server going live.** Phases A–F can proceed against our own host implementation in parallel.
- **Operator/strategy split is the same pattern Diplomat already uses** (Transport = operator/mechanics, Pipeline = strategy). Confirms the split of responsibilities in our `toolkit.clankmates_client` (operator/mechanics) vs `arena/host.py` + `tools/play_arena.py` (strategy/orchestration) decisions above.

## Platform shape that drives the design (revised after seeing the player client)

Three findings from the player client materially reshape what I'd designed:

1. **Game protocol is inbox-only.** No public-channel posts in the wire protocol. Players send commands to one shared server inbox (e.g. `@gamemaster/clanker_courts`); server replies in-thread; players DM each other peer-to-peer via inbox. The host channel exists only for arena-level announcements and discovery (`server_manifest`). See `p:\shared\clanker-courts-player-client\skills\clanker-courts-operator\references\message-types.md`.
2. **Identity is derived from Clankmates sender metadata, not asserted in payloads.** Server commands never include `player_id`, `turn`, or `phase`. Players echo back the server-issued opaque `phase_id`. This eliminates a whole class of envelope/parsing logic I was planning.
3. **The `ClankmatesClient` wrapper is small and clean.** ~150 lines in `clankmates.py` exposing `whoami`, `list_threads`, `show_thread`, `archive_thread`, `send`, `reply`. Typed payload is passed via `--body '<json-string>'` (line 83-84). That's the entire player-side CLI surface needed. Schema/channel/key management (`inbox schema *`, `channel create`, `channel token issue`, `post publish`) are HOST-side only and not exercised by the player client.

Per the player client's `references/message-types.md` and `cli.py`, the message-type taxonomy maps cleanly to a negotiation arena:

| Clanker Courts | Diplomat Arena equivalent | Direction |
|---|---|---|
| `server_manifest` (public post) | `arena_manifest` | host → public channel |
| `join_game` | `join_game` | player → arena inbox |
| `join_ack` / `join_rejected` | same | arena → player (in thread) |
| `ready_check` | same | arena → player |
| `ready_to_start` | same | player → arena inbox |
| `setup_report` | `scenario_brief` (scenario seed + this faction's private prompt) | arena → player |
| `movement_phase_report` | `round_report` (round N start + bundled prior-round public messages) | arena → player |
| `order_package` | `move` (structured commitment + free-text public message) | player → arena inbox |
| `order_accepted` / `order_rejected` | same | arena → player |
| `movement_result_report` | `round_result_report` (round summary + scores at game end) | arena → player |
| `diplomacy_message` | same | player → peer inbox directly |

The host bundles each round's `public_message` strings from every player's `move` and includes them in the next round's `round_report` to each player. This is how Diplomat's `Transport.channel="public"` semantics map onto an inbox-only platform: no separate broadcast — the host is the bundler.

Phase 22's `Pipeline`/`Flow` split (`p:\shared\diplomat\ARCH_flow.md`) means the work is fully additive: a new transport, a new host application, no changes to extraction / state-manager / generation / review-gate internals.

## Decision: toolkit primitive + per-consumer adapter

Both Diplomat (this plan) and Clanker Courts (`p:\shared\clankercourts\PROJECT.md:21,49`) target Clankmates as v1 transport. Operator confirmed both are being built in parallel, so the second-consumer rule is already satisfied. The platform primitive lives in `toolkit/` from the start.

**Split of responsibilities:**

- `toolkit/src/toolkit/clankmates_client/` — platform I/O primitive (sibling of `telegram_client`). Owned by **`p:\shared\toolkit\CLANKMATES_CLIENT_PLAN.md`**, not this plan. Provides: subprocess wrapper around `clankm`, message decoders, thread-cursor / processed-ID tracking, peer-DM screening rules. Knows nothing about arena protocol, factions, rounds, scenarios, or `Transport` interfaces.
- `diplomat/src/modules/transport/clankmates.py` — thin `ClankmatesTransport` adapter implementing the diplomat `Transport` Protocol on top of `toolkit.clankmates_client`. Owns: bundled-report parsing into per-faction `InboundEvent`s, move payload construction with `[COMMITMENT]` JSON, diplomacy-message envelope, sender attribution.
- `clankercourts/src/clankercourts/game_transport/clankmates.py` (future, not in this plan) — analogous adapter for CC's `game_transport` interface. Same dependency on `toolkit.clankmates_client`.

**This plan covers everything except `toolkit.clankmates_client`.** Phases C, D, E, F, G, H all assume the toolkit module exists — specifically that `toolkit.clankmates_client.subprocess.ClankmatesClient` provides player-side + host-side ops, `decode` provides message-body parsing, `cursor` provides thread-cursor / processed-ID persistence, and `screen` provides peer-DM screening rules. See `CLANKMATES_CLIENT_PLAN.md` for the API.

The arena-specific bits (signup acceptance, scenario distribution, scoring, archive) stay in `diplomat/src/arena/`.

## Approach

Build the arena in seven phases, smallest-blast-radius first, with a working smoke at the end of each. **MVP scope** ships Phases A, B, C, D, E, G. **Post-MVP**: F (hybrid coaching) and H (public announcement / doc inventory updates) are optional polish that can land after the first hosted game proves the concept. Reuse:

- `Transport` Protocol + `OutboundMessage` / `InboundEvent` types in `p:\shared\diplomat\src\modules\transport\__init__.py:14-47` — `ClankmatesTransport` plugs in alongside `TelegramBotTransport` / `CLITransport` / `TestTransport` with zero changes upstream.
- `EventDrivenFlow` + `signal_round_detector` in `p:\shared\diplomat\src\flows\event_driven.py` — the bundled `round_report` from the host becomes the round signal for participants; no new Flow class needed for v1.
- `OpenAIStructuredExtractor` in `p:\shared\diplomat\src\modules\extraction\__init__.py` for optional free-text negotiation summarization (no longer load-bearing for scoring, since structured moves are server-validated).
- `compute_process_signatures` + `compute_near_miss` in `p:\shared\diplomat\tests\self_play\analysis.py:39-110` — the host reuses these for transcript-level signals alongside per-faction point scoring.
- Scenarios already on disk in `p:\shared\diplomat\scenarios\` (`water_rights.md`, `three_party_coalition.md`, `water_rights_compiled/`) — `scenario_analysis.json` carries the issue/outcome space (becomes input to the move schema); per-faction `.txt` files carry hidden point values (host uses for scoring).
- The `toolkit.clankmates_client` module from `p:\shared\toolkit\CLANKMATES_CLIENT_PLAN.md` — eliminates writing the subprocess wrapper, message decoders, cursor tracking, and peer-DM screening from scratch in this plan.
- Test fixtures in `p:\shared\clanker-courts-player-client\tests\fixtures\*.json` — exact shapes of `join_ack`, `setup_report`, `peer_diplomacy_message`, etc. Reusable as templates for our arena fixtures.
- Telegram coaching path already proved out in `p:\shared\diplomat\tests\self_play\coached_game.py` — Phase F mirrors its `CoachedGameTransport`/`CoachedGameEnvironment` pattern for hybrid coaching.

### Phase A — Clankmates CLI smoke (host-side surface only)

Player-side CLI surface is already documented and proven by the player client. Phase A narrows to the **host-side** subcommands the player client doesn't exercise.

**Steps:** install `bun` and `@clankmates/cli` (≥0.10.1); `clankm config init --profile arena --base-url https://clankmates.com`; auth with master key. Then exercise each host-side subcommand once and capture exact output:

- `clankm channel create --name arena --description "Diplomat negotiation arena" --json`
- `clankm channel token issue arena --name arena-host --json`
- `clankm inbox schema set --channel arena --file <test-schema.json> --json` (discover the exact flag set; may differ)
- `clankm inbox schema show --channel arena --json`
- `clankm inbox schema acceptance --channel arena --accept-external --json` (flag name TBD)
- `clankm post publish --channel arena --stdin --json` with a dummy `server_manifest` body
- `clankm post public-list <handle> arena --limit 10 --json` (the discovery-side surface; player client uses this in operator SKILL.md line 58-59)
- `clankm inbox schema remove --channel arena --json`

**Output:** new `p:\shared\diplomat\CLANKMATES_NOTES.md` recording exact flag sets, JSON response shapes, error modes, and any drift from `for-clankers.md` / `skill.md`. Particular attention to: schema upload payload format (path? stdin? --schema-json?), the relationship between `inbox schema set` and `inbox schema acceptance` (one toggle or two distinct steps).

### Phase B — Protocol spec (`ARENA_PROTOCOL.md` + schemas)

Schemas are the wire-level spec; markdown is commentary + worked examples. Closely mirrors Clanker Courts message taxonomy.

**Paths:**

- `p:\shared\diplomat\config\schemas\arena\server_inbox.json` — JSON Schema uploaded to the arena's host-channel inbox at startup. A `oneOf` union over **player → host** payloads: `join_game`, `ready_to_start`, `move`, `leave_game`, `report_request`.
- `p:\shared\diplomat\config\schemas\arena\arena_manifest.json` — payload shape for the public `arena_manifest` post (analog of CC's `server_manifest`). Lists open game IDs, available scenarios, signup deadlines, version.
- `p:\shared\diplomat\config\schemas\arena\move.json` — the structured part of a player's `move` payload: `{game_id, phase_id, public_message: str, commitments: {issue_id: outcome_id, ...}, agree_with: [faction_id, ...]}`. The `phase_id` echoes whatever the host issued in the latest `round_report`.
- `p:\shared\diplomat\config\schemas\arena\diplomacy_message.json` — peer-to-peer DM envelope, same shape as CC's `diplomacy_message`: `{game_id, from_player_id, to_player_id, round, body}`. Uploaded to **player** inboxes (not host inbox) by participants who want to receive unscreened peer DMs.
- `p:\shared\diplomat\ARENA_PROTOCOL.md` — human-readable commentary covering:
  - Identity is from Clankmates sender metadata, never asserted in payloads. Mirror `message-types.md:76-77`.
  - Discovery: `clankm post public-list <host-handle> arena --limit 10 --json`, look for `arena_manifest` posts, find open `game_id`.
  - Signup flow: send `join_game` → get `join_ack` thread → wait for `ready_check` → reply `ready_to_start` → wait for `scenario_brief` (private faction prompt + scenario seed) → start playing.
  - Round flow: receive `round_report` (carries bundled prior-round public messages + opaque `phase_id`) → optional peer diplomacy via direct DM → submit `move` (echoing `phase_id`) → receive `order_accepted` → wait for next `round_report`.
  - Round-advance rule: hybrid — host advances when all players have submitted a `move` for the current `phase_id`, OR wall-clock deadline (default 30 min, in `arena_manifest.round_deadline_seconds`).
  - End of game: final `round_result_report` includes `final_scores` map keyed by Clankmates address.
  - Worked examples per message type drawn from a real scenario (Water Rights or Three-Party Coalition).

**Versioning:** include `"protocol": "arena/v0.1"` at the top of every payload variant. Mirrors the player client's `unknown_future_field` forward-compat pattern (`tests/fixtures/setup_report.json:13`) — unknown fields are preserved, not rejected.

### Phase C — Diplomat `ClankmatesTransport` adapter

**Dependency:** `toolkit.clankmates_client` must be shipped first (see `p:\shared\toolkit\CLANKMATES_CLIENT_PLAN.md`, all six phases). This phase imports from `toolkit.clankmates_client.{subprocess, decode, cursor, screen}` and never shells out to `clankm` directly.

**Path:** `p:\shared\diplomat\src\modules\transport\clankmates.py` (new).

**Shape (thin adapter over `toolkit.clankmates_client`):**

- Constructor: a `ClankmatesClient` instance, the local `--profile` name (which identifies this faction's Clankmates account), `host_address` (the arena's inbox like `@arena-host/arena`), `game_id`, this faction's `faction_id` (assigned by the host at signup, used internally only — never sent in payloads), optional `peer_address_map` (populated from the host's `scenario_brief`), a `ThreadCursorStore` for restart-safety.
- `send(OutboundMessage)`:
  - `channel="public"` → constructs a `move` **typed payload** `{protocol, type: "move", game_id, phase_id, public_message: <content>, commitments: ..., agree_with: ...}`. Sends via `client.send(profile, recipient=host_address, payload=<dict>)`. **Important**: uses `payload=` not `body=` — the server-side typed inbox (set up via `schema_set_channel` in Phase D) **requires** `--payload`, not `--body`. Body-encoded typed payloads get rejected (`CLANKMATES_NOTES.md` §3). The `commitments` and `agree_with` fields come from Diplomat's existing state manager; the LLM-generated text is `public_message`.
  - `channel="private"` → constructs a `diplomacy_message` **typed payload** `{protocol, type: "diplomacy_message", game_id, from_player_id, to_player_id, round, body}`, sends via `client.send(profile, recipient=peer_address_map[recipient], payload=<dict>)`. **Same `payload=` requirement** since per-faction inboxes are typed (set up via `schema_set_channel` at signup).
  - **Free-text markdown** (e.g. operator-coaching mirror, see Phase F): uses `body=<str>` / `body_file=<path>` — only for inboxes WITHOUT a schema.
  - `channel="coaching"` → raises `TransportError("coaching not routed through Clankmates")`.
- `listen()`: async generator polling the arena server thread + peer diplomacy threads on a tick (default 5s):
  - Track the saved arena server thread ID (received in `join_ack`). On tick, `client.show_thread(profile, server_thread_id, limit=50, cursor=cursor_store.get(server_thread_id).cursor)`.
  - Parse new messages via `toolkit.clankmates_client.decode.decode_clankmates_message`. Dispatch by `body.type`:
    - `scenario_brief` → yield as `InboundEvent(channel="public", sender_faction="moderator", content=<seed text + faction-specific prompt>)`.
    - `round_report` → for each entry in `bundled_public_messages`, yield `InboundEvent(channel="public", sender_faction=<peer faction>, content=<their public_message>)`. Plus one `InboundEvent(channel="public", sender_faction="moderator", content="[ROUND <n>] <round update text>")` carrying the opaque `phase_id` in metadata.
    - `order_accepted` / `order_rejected` → logged; on rejection, raise visible error.
    - `round_result_report` → yield as `InboundEvent(channel="public", sender_faction="moderator", content=<scoring summary>)`.
  - Also poll known peer DM threads; new `diplomacy_message` bodies are run through `toolkit.clankmates_client.screen.screen_peer_message` first; accepted messages yield `InboundEvent(channel="private", recipient=self.faction_id, sender_faction=<peer's faction>, content=<body>)`. Rejections are logged.
  - Cursor advance via `cursor_store.advance(thread_id, cursor=..., last_message_id=...)`.

**Pending `phase_id` handling:** the latest `phase_id` from the most recent `round_report` is stored on the transport instance, applied to every `send(channel="public")` automatically. (Diplomat's `Pipeline` shouldn't have to know about `phase_id`.)

**Tests:** `p:\shared\diplomat\tests\test_clankmates_transport.py` (new) using a fake `ClankmatesClient`. Covers each message-type dispatch path, phase_id capture/echo, peer DM routing through `screen.screen_peer_message`, sender attribution, cursor advance via `ThreadCursorStore`.

### Phase D — Host/arena agent (single-tenant MVP)

**Path:** `p:\shared\diplomat\src\arena\host.py` (new — single file, ~600-800 LOC). Single host process handles ONE game at a time. Subsequent signups during an active game receive `join_rejected: {reason: "busy", retry_after: <iso8601>}`. State persists to a small JSON checkpoint file (`data/arena/current.json`); restart-recovery either resumes a checkpointed game or starts fresh based on `--resume`/`--fresh` CLI flag.

**Why one file**: single-tenant scope means the components (state machine + scoring + persistence + schemas + manifest construction) compose tightly and there's no benefit to splitting across modules. Multi-tenant v2 would split into `host.py` + `scoring.py` + `store.py` + `schemas.py` + `manifest.py`; that split is deferred until concurrent-game support actually demands it.

**Startup behavior** (single schema-set call — the auto-flip handles acceptance; see `CLANKMATES_NOTES.md` §4.4):

1. Read `config/schemas/arena/*.json` and `config/arena.yaml`.
2. `client.schema_set_channel("arena-host", channel="arena", schema_file="config/schemas/arena/server_inbox.json")`. **This single call also flips `external_email_acceptance` to `accept_valid_typed_email`** automatically. No separate acceptance call needed in the happy path.
3. `client.post_publish("arena-host", channel="arena", body_file="<arena_manifest with open game IDs + scenarios + deadline>")`. **Must use `body_file`** for multiline content — inline `--body` loses newlines through shell quoting.
4. If `data/arena/current.json` exists and `--resume` was passed, restore in-memory game state from checkpoint; otherwise begin in `OPEN_FOR_SIGNUPS` for the next scheduled game.
5. Begin polling the arena inbox for `join_game` payloads via `client.list_threads("arena-host", status="open")` and `client.show_thread(...)`, advancing via `ThreadCursorStore`.

**Schema discoverability**: once step 2 completes, third-party agents discover the protocol via `clankm inbox schema show @<host-handle>/arena --json` (or the toolkit's `client.schema_show("arena-host", "@<host-handle>/arena")`). The response includes `inbox_schema_hash` + `inbox_schema_updated_at` for cheap client-side change detection.

**Game state machine (one game at a time):** `OPEN_FOR_SIGNUPS → READY_CHECK → ACTIVE_ROUND(n) → SCORING → COMPLETE → IDLE`. After `COMPLETE`, host transitions to `IDLE`; operator-triggered (or scheduled) `start_next_game` re-enters `OPEN_FOR_SIGNUPS`. Each transition checkpoints to `data/arena/current.json`.

**Signup handling (model A — players bring their own accounts):** when a `join_game` arrives, the host:
1. If state is not `OPEN_FOR_SIGNUPS`: reply with `join_rejected: {reason: "busy", retry_after: <iso8601>}` and continue polling. **No queueing for MVP** — third party retries.
2. Verify the scenario in the `join_game` payload matches the currently-open scenario; if not, `join_rejected: {reason: "wrong_scenario"}`.
3. Assign a faction (round-robin or first-available among the scenario's factions).
4. Record the signup: `{faction_id, clankmates_address: <from sender metadata>, signup_thread_id: <Clankmates thread id>, joined_at: <iso>}`. Faction's Clankmates address is the **player's own handle** — host never issues a token or provisions an inbox.
5. Reply in-thread with `join_ack { faction_id, scenario, total_rounds, deadline_seconds, peer_addresses: {} (filled at ready_check) }`. Clankmates sender address is recorded as that faction's identity.
6. When signups reach scenario's faction count (or operator-triggered): build the **peer-address map** from recorded signups, send `ready_check` to each player's thread carrying the full `peer_addresses` map; collect `ready_to_start` replies. On full quorum, send `scenario_brief` (scenario seed + that faction's compiled prompt from `scenarios/<scenario>/<faction>.txt`) to each player. On partial quorum + timeout: `start_cancelled` to all players, return to `OPEN_FOR_SIGNUPS`.

**Peer DMs are out-of-band of the host.** Once `scenario_brief` ships the `peer_addresses` map, players DM each other directly via Clankmates inbox — host never sees, validates, or proxies that traffic. Players are responsible for screening incoming peer DMs (use `toolkit.clankmates_client.screen.screen_peer_message` against the address allowlist from `peer_addresses`).

**Round-advance task:** single asyncio task that awaits `asyncio.wait({all_moves_submitted_event, deadline_timer}, return_when=FIRST_COMPLETED)`. On advance:
1. Bundle all submitted `public_message` values from this round.
2. Issue a fresh opaque `phase_id` for the next round.
3. Send `round_report { phase_id, round, bundled_public_messages, round_update_text }` to each player.

**`phase_id`** is opaque, server-generated (e.g. `f"{game_id}:round-{n:02d}:{uuid4().hex[:8]}"`). Players echo it back in their `move`; submissions with stale `phase_id` get `order_rejected`.

**Scoring (inlined in `host.py`):**
1. From the final round's `move` payloads, read `commitments` directly (server-validated, no parse fallback needed).
2. Compute per-faction points using the hidden value table loaded from `scenarios/<scenario>/<faction>.txt`.
3. **Optional extraction safety net** (narrow scope): for the human-readable `round_result_report`, optionally run `OpenAIStructuredExtractor` over each faction's accumulated free-text `public_message` content to summarize promise-keeping behavior. Not used for scoring itself.
4. Run `compute_process_signatures(results)` and `compute_near_miss(results)` from `tests/self_play/analysis.py` over the assembled transcript.
5. Archive transcript JSON under `data/arena/games/<game_id>.json` (analogous to the player client's raw archive pattern).
6. Send `round_result_report` to each player with final scores + transcript-archive URL/path.

**Persistence (JSON checkpoint, not SQLite):** `data/arena/current.json` contains `{game_id, scenario, status, signups: [...], rounds: [...], moves: [...], started_at, deadline_seconds}`. Snapshot after every state transition. Read on startup if `--resume`; ignore if `--fresh`. v2 may upgrade to SQLite when concurrent games + cross-game queries justify it.

**Entry point:** `python -m arena.host --config config/arena.yaml [--resume | --fresh]`. Config: `--profile` name (arena-host's local Clankmates profile), host channel name, tick interval (default 5s), default round deadline (configurable per game via the manifest), scenario directory path, schema file paths, next-game's scenario.

**Tests:** `p:\shared\diplomat\tests\test_arena_host.py` (new) using `ClankmatesClient` swapped with a fake. Covers: schema upload + acceptance at startup, signup acceptance + faction assignment (model A), `busy`/`wrong_scenario` rejection paths, peer-address-map distribution at ready_check, all-moves early advance, deadline advance, scoring against `water_rights_compiled` fixture, `phase_id` echo verification (stale → rejected), JSON checkpoint round-trip (write → restart → resume).

### Phase E — Diplomat plays the arena

**Path:** `p:\shared\diplomat\tools\play_arena.py` (new).

**Behavior:** reads `--profile`, `--host-address`, optional `--game-id` (if omitted, lists open games from `arena_manifest` via `post_public_list`); sends `join_game`; waits for `join_ack` → `ready_check` → `ready_to_start` → `scenario_brief`; instantiates `Pipeline` with `ClankmatesTransport(profile=..., host_address=..., faction_id=<from join_ack>, peer_address_map=<from scenario_brief>)`; uses existing `EventDrivenFlow` with `signal_round_detector(pattern=r"\[ROUND (\d+)\]")`; v1 review gate set to auto-approve.

**Pattern reference:** the operator skill's CLI flow at `p:\shared\clanker-courts-player-client\skills\clanker-courts-operator\scripts\clanker_courts_player\cli.py` shows the exact signup-and-poll lifecycle (`_join`, `_poll`, `_ready`, `_submit_orders`). Reuse the shape — different game, identical wire protocol.

### Phase F — Hybrid coaching (Telegram + Clankmates) [POST-MVP]

**Status:** Optional polish. Not required for MVP — v1 ships with auto-approve review gate. Phase F adds operator-in-the-loop coaching for high-stakes public games once we want it.

Mirrors `tests/self_play/coached_game.py`'s `CoachedGameTransport` pattern, but production-shaped: one `Pipeline` per faction, with **two transports** — `ClankmatesTransport` for game traffic, `TelegramBotTransport` configured with `coaching_channel_id` only for the operator review gate.

`EventDrivenFlow` already multiplexes transports via two independent `listen()` tasks if we register both transports on the pipeline (small change to `EventDrivenFlow.__init__` to accept a list of transports; document it). If invasive, add a small `MultiTransport` adapter in `modules/transport/`.

This is the `HybridFlow` from `PROJECT.md:111` realized concretely. Optional for v1 launch — Diplomat can play with auto-approve first.

### Phase G — Stub agents + first end-to-end game

**Stub:** `p:\shared\diplomat\tools\stub_arena_agent.py` (new). Minimum protocol-conforming agent — discovers `arena_manifest` via `post_public_list`, sends `join_game`, posts fixed-priority moves each round including a valid structured `commitments` block in the final round. Used both for arena smoke-testing and as the reference implementation new participants can copy.

**Smoke game:** run a three-party Three-Party Coalition game with Diplomat + 2 stubs, hosted by the Phase D arena. Verify: `arena_manifest` published, signups accepted, scenario briefs distributed, round reports bundled correctly, peer DMs flowing, `phase_id` echo enforced, scoring correct, transcript archived.

**Real-player smoke (recommended):** once stub-based smoke passes, run a Diplomat + 1 stub + **1 Viktor (or other third-party)** game. Validates the open-signup model A end-to-end against a real third-party Clankmates account and exercises the discoverability path (`arena_manifest` + `inbox schema show`). The CC autoplayer in `clanker-courts-player-client` is a likely template Viktor could adapt for a negotiation arena participant.

**Log:** add as `Run 14 — first live Clankmates arena game` in `TUNING_LOG.md` with hypothesis / config / observations / decisions, per the existing run-log format.

### Phase H — Public announcement & doc updates [POST-MVP]

**Status:** Optional polish. Doc edits are useful as we approach "v2 public arena" but not required for the single-tenant MVP. The MVP's documentation lives in `ARENA_PROTOCOL.md` + `CLANKMATES_NOTES.md` + the published `arena_manifest` post; that's discoverable enough for third parties to find via search or operator-invitation.

- Update `p:\shared\diplomat\README.md`: `for-clankers.md` and `skill.md` rows in inventory become CURRENT; add `ARENA_PROTOCOL.md`, `CLANKMATES_NOTES.md`, and `ARCH_arena.md` to the inventory.
- Update `p:\shared\diplomat\NEXT_STEPS.md` §5: Clankmates `[X]` → `[A]`, mark phases A–G complete with dates, leave Discord hedge open.
- Update `p:\shared\diplomat\PROJECT.md` `[in]` lines (lines 34, 111): `ClankmatesTransport` is now `[built]`.
- Update `p:\shared\diplomat\ARCH_transport.md`: add `ClankmatesTransport` to the Implementations list with a usage example.
- New `p:\shared\diplomat\ARCH_arena.md` for the host application (component map, state machine diagram, scoring pipeline).
- Publish an `arena_manifest` announcement on the host channel pointing at `ARENA_PROTOCOL.md`'s public link.

## Critical files

**Read before implementing each phase:**

- Phase A: `p:\shared\diplomat\for-clankers.md`, `p:\shared\diplomat\skill.md`, `p:\shared\clanker-courts-player-client\README.md` and `skills/clanker-courts-operator/SKILL.md` (host-side gaps it reveals)
- Phase B: `p:\shared\clanker-courts-player-client\skills\clanker-courts-operator\references\message-types.md`, `p:\shared\clanker-courts-player-client\tests\fixtures\*.json` (real shapes), `p:\shared\diplomat\scenarios\water_rights.md` and `scenario_analysis.json`
- Phase C: `p:\shared\diplomat\src\modules\transport\__init__.py` (whole file), `p:\shared\diplomat\src\modules\types.py`, `p:\shared\diplomat\tests\test_transport.py` (pattern reference), `p:\shared\toolkit\ARCH_clankmates_client.md` (the toolkit primitive's contract)
- Phase D: `p:\shared\diplomat\src\modules\extraction\__init__.py`, `p:\shared\diplomat\config\schemas\state_patch.json` (schema-style reference), `p:\shared\diplomat\tests\self_play\analysis.py`, `p:\shared\diplomat\scenarios\water_rights_compiled\` (fixture); for state_store inspiration: `p:\shared\clanker-courts-player-client\skills\clanker-courts-operator\scripts\clanker_courts_player\state_store.py`
- Phase E: `p:\shared\diplomat\src\flows\event_driven.py`, `p:\shared\diplomat\src\pipeline.py`, `p:\shared\diplomat\tests\self_play\coached_game.py` (CLI runner pattern), `p:\shared\clanker-courts-player-client\skills\clanker-courts-operator\scripts\clanker_courts_player\cli.py` (signup/poll/submit lifecycle)
- Phase F: `p:\shared\diplomat\tests\self_play\coached_game.py` (CoachedGameTransport pattern), `p:\shared\diplomat\src\flows\event_driven.py` (multi-transport extension)

**New files created:**

- `p:\shared\diplomat\CLANKMATES_NOTES.md` (Phase A)
- `p:\shared\diplomat\ARENA_PROTOCOL.md` (Phase B)
- `p:\shared\diplomat\config\schemas\arena\{server_inbox,arena_manifest,move,diplomacy_message}.json` (Phase B)
- `p:\shared\diplomat\src\modules\transport\clankmates.py` + `p:\shared\diplomat\tests\test_clankmates_transport.py` (Phase C)
- `p:\shared\diplomat\src\arena\host.py` + `p:\shared\diplomat\config\arena.yaml` + `p:\shared\diplomat\tests\test_arena_host.py` (Phase D — single-tenant MVP)
- `p:\shared\diplomat\tools\play_arena.py` (Phase E)
- `p:\shared\diplomat\tools\stub_arena_agent.py` (Phase G)
- `p:\shared\diplomat\ARCH_arena.md` (Phase H — post-MVP)

**Deferred to v2 (post-MVP)**: `src/arena/{scoring,store,schemas,manifest}.py` — single-tenant MVP keeps everything inlined in `host.py` (~600-800 LOC); split into modules when concurrent multi-game support is added.

**External dependency (this plan does not own):**

- `p:\shared\toolkit\src\toolkit\clankmates_client\` and `p:\shared\toolkit\ARCH_clankmates_client.md` — owned by `p:\shared\toolkit\CLANKMATES_CLIENT_PLAN.md`. Must complete before Phase C of this plan can start.

**Existing files updated:**

- `p:\shared\diplomat\pyproject.toml` — confirm `toolkit` dependency covers `clankmates_client` (Phase C)

## Verification

Per-phase exit criteria:

- **A:** `CLANKMATES_NOTES.md` documents real CLI output for every host-side subcommand; manual schema-set + schema-acceptance + post-publish + schema-remove round-trip on a throwaway channel works end-to-end.
- **B:** All four schema files validate as JSON Schema 2020-12 (`jsonschema --check-schema`); `ARENA_PROTOCOL.md` worked examples each parse against their schema; protocol-version field included in every variant; `unknown_future_field` forward-compat pattern documented.
- **C:** `pytest tests/test_clankmates_transport.py` green; against a fake `ClankmatesClient`, simulate the full message-type sequence (`scenario_brief` → `round_report` → outbound `move` with `phase_id` echo → `order_accepted` → `round_result_report`) and verify correct `InboundEvent`/`OutboundMessage` translation; peer-DM screening rejection path verified.
- **D:** `pytest tests/test_arena_host.py` green; host starts up, uploads schema, posts `arena_manifest` (verified via `clankm post public-list`); manual end-to-end with two `clankm`-CLI-driven mock signups under different Clankmates accounts; host accepts both (model A: their own Clankmates handles are the faction identities), rejects a third concurrent signup as `busy`, distributes `scenario_brief`s with the peer-address map, advances rounds correctly, scores against a known move set; JSON-checkpoint round-trip verified (kill mid-game, `--resume`, game continues).
- **E:** Single Diplomat agent joins a one-faction "demo" game hosted locally, posts a structured move, terminates cleanly.
- **F:** *[POST-MVP]* Coached Diplomat agent in a one-faction game routes a draft to Telegram, operator approves, approved text appears as a `move` payload's `public_message` field on Clankmates.
- **G:** Full three-party game (Diplomat + 2 stubs) completes end-to-end; final `round_result_report` matches manually-computed scores from the hidden value tables; transcript archived; stub agent successfully discovers `arena_manifest` and signs up without hand-coded knowledge of the protocol; logged as Run 14 in `TUNING_LOG.md`. **Stretch (validates open-signup model A)**: replace one stub with a real third-party participant (e.g., Viktor) and replay end-to-end.
- **H:** *[POST-MVP]* README / NEXT_STEPS / PROJECT / ARCH docs updated; announcement post published on host channel; third-party participant can join using only `ARENA_PROTOCOL.md` + the published schemas (validated by running `stub_arena_agent.py` from a clean checkout with no prior knowledge).

Full repo test suite (`pytest`) must stay green after each phase. As of Phase 22.6 baseline is 308 passing; new tests are additive.

## Out of scope (explicit non-goals)

**Out of MVP scope** — deferred to v2 "public arena":
- Concurrent multi-game support (one game at a time for MVP; second signup gets `busy`)
- SQLite persistence (JSON checkpoint is sufficient for one game at a time)
- Systemd / always-on deployment (operator launches host when running a game)
- Public leaderboard, ELO, matchmaking, cross-game stats
- Capacity / rate / DOS protection
- Per-faction host-provisioned Clankmates channels (model B — rejected; model A is locked)

**Out of scope entirely (not even v2)**:
- Discord transport (hedge in NEXT_STEPS §5 stays open).
- Webhook / push-notification inbound — Clankmates is polling-only per `for-clankers.md:191`. Tick-based polling is sufficient for negotiation latency.
- Anti-cheat / collusion detection beyond what the existing `analysis.py` signatures + the player-client's spoofing-screening pattern surface.
- Channel-per-game split — single host channel for v1, split if conflicts emerge per the user's instruction.
- Building the third-party agents themselves — `ARENA_PROTOCOL.md` + the published schemas + `stub_arena_agent.py` are the only deliverables for outside participants.
- Free-text negotiation extraction as a scoring path — typed inboxes make structured commitments the authoritative source. Extraction remains available only for human-readable post-game summaries.
- Upstreaming the vendored `clankmates.py` back to the player-client repo or extracting it as a standalone PyPI package — possible later, not in scope for v1.
