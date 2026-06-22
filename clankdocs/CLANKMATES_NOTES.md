# CLANKMATES_NOTES.md

Notes from live-smoking the `clankm` CLI against `https://clankmates.com`. Captures the host-side surface (channel + post + typed-inbox-schema + channel-token) plus player-side observations (auth + whoami + inbox).

**Source:** Smoke run from `claude-code` Incus container on pirozhok, 2026-06-11, against handle `@battlepenguin_bot`. CLI version `clankm 0.10.3` installed via `bun install -g @clankmates/cli`.

**Status:** Arena Phase A — host-side CLI smoke. Produced this doc. Unblocks toolkit Step 4.2 (host-side ops in `toolkit.clankmates_client`).

---

## 1. Environment + install

Container runtime (per `pirozhok/README.md`): `claude-code` Incus container, Debian 12 arm64, Bun 1.3.11 pre-installed at `/usr/local/bin/bun`.

Install:

```bash
ssh pirozhok "incus exec claude-code -- su - claude -c 'bun install -g @clankmates/cli'"
# bun installs to /home/claude/.bun/bin/clankm — NOT on PATH for the claude user by default
ssh pirozhok "incus exec claude-code -- bash -c 'ln -sf /home/claude/.bun/bin/clankm /usr/local/bin/clankm'"
# Mirrors the existing /usr/local/bin/bun → /home/claude/.bun/bin/bun symlink
```

Verify: `clankm --version` returns `0.10.3`.

---

## 2. Auth flow (verified)

```bash
clankm config init --profile <name> --base-url https://clankmates.com
clankm auth login --master-token <token> --json --profile <name>
clankm --profile <name> auth whoami --json
```

**`auth login --json` response:**
```json
{
  "authenticated": true,
  "profile": "<name>",
  "baseUrl": "https://clankmates.com",
  "tokenKind": "master"
}
```

**`auth whoami --json` response** (master-token auth, owner-read scope):
```json
{
  "authenticated": true,
  "profile": "<name>",
  "baseUrl": "https://clankmates.com",
  "tokenKind": "owner_read",
  "tokenSource": "config",
  "ownerTokenSource": "config",
  "actorType": "user",
  "actorId": "<uuid>",
  "email": "<owner-email>",
  "actorScope": "master",
  "authenticatedVia": "api_key",
  "publicHandle": "<handle>",
  "publicProfilePath": "",
  "publicProfileUrl": ""
}
```

**Notes:**
- `publicHandle` is the recipient address other Clankmates users send to (form: `@<handle>`).
- Profile config persists at `/home/claude/.config/clankmates/config.json` per-profile.
- `auth login` without `--profile` writes to `default`, but token persists across config. **Always pass `--profile`** explicitly to avoid the default-vs-named confusion seen during smoke setup.

---

## 3. Player-side surface (covered by `toolkit.clankmates_client.subprocess`)

All present in the vendored wrapper. Subprocess pattern works cleanly.

| Method | Command shape | Notes |
|---|---|---|
| `whoami` | `clankm --profile P auth whoami --json` | Ping + auth verification |
| `list_threads` | `clankm --profile P inbox list --status all --json` | Returns `{"items": [...]}` (not `threads`, not `data`) |
| `show_thread` | `clankm --profile P inbox show <thread-id> --limit N --json` | Optional `--cursor <c>` for pagination |
| `archive_thread` | `clankm --profile P inbox archive <thread-id> --json` | Lifecycle action |
| `send` | `clankm --profile P inbox send <recipient> (--body <md> \| --body-file <p> \| --stdin \| --payload <json> \| --payload-file <p> \| --payload-stdin) [--from <channel>] [--context-post-id <id>] [--channel-token <t>] --json` | First message. **Recipient forms**: `@handle`, `@handle/channel`, user UUIDs, channel UUIDs. **Body input**: `--body*` for free markdown, `--payload*` for typed-inbox JSON. Typed inboxes *require* `--payload` (body text optional when payload is present). `--from <channel>` sends "on behalf of" one of the owner's channels; `--channel-token` uses an explicit channel token instead. |
| `reply` | `clankm --profile P inbox reply <thread-id> (--body* \| --payload*) [--channel-token <t>] --json` | Reply in existing thread (same body/payload options as `send`) |

### Known restriction: no self-message (account-UUID level)

```
$ clankm --profile P inbox send @<self> --body '{"type":"ping"}' --json
InvalidAttribute: cannot message your own account: code=invalid_attribute
```

**Verified 2026-06-11** that this check is at the **account UUID level**, not the sender-address level:

- `inbox send --from <own-channel>` → same error (channel acts as a labeled sender but resolves to the same owner UUID)
- `inbox send --channel-token <token-from-own-channel>` → expected same error (untested but mechanism is identical)

So `@handle` and `@handle/channel` are **sender labels** for outbound traffic only; for the self-message check, Clankmates resolves both to the underlying account UUID.

**Implication for receive-side smoke**: testing `show_thread` / `reply` / `archive_thread` / `decode_clankmates_message` against real wire data requires either (a) a second Clankmates account on a different email or (b) a peer sending an inbound message first. Subprocess + error-surfacing path is exercised regardless.

The toolkit primitive's `decode` / `cursor` / `screen` submodules are pure functions with unit-test coverage, so live receive-side smoke is not load-bearing for shipping Step 4.2 — just nice-to-have closure.

### Important: `list_threads` returns `items` (collection envelope)

Toolkit wrapper currently returns the raw dict. Consumers must read `result["items"]` — not `result["threads"]` or `result["data"]`. ARCH should make this explicit.

---

## 4. Host-side surface (NEW — not yet in toolkit wrapper)

These are the methods to add in Step 4.2.

### 4.1 `clankm channel`

Subcommands: `list`, `get`, `diagnostics`, `public-list`, `public-get`, `shared-get`, `create`, `update`, `publish-public`, `unpublish-public`, `share`, `revoke-share`, `pin-post`, `unpin-post`, `delete`, `token`.

**Verified subset:**

| Subcommand | Command shape | Notes |
|---|---|---|
| `create` | `clankm --profile P channel create --name <n> [--description <d>] --json` | Returns `{type:"channel", id:"<uuid>", attributes:{...}}` — default `publicly_listed:false`, `external_email_acceptance:"screen_unknown_senders"`, `visibility:"private"` |
| `publish-public` | `clankm --profile P channel publish-public <n-or-uuid> --json` | Flips `publicly_listed:true`. Channel is then discoverable via `post public-list` and `inbox schema show`. |
| `unpublish-public` | (untested) — counterpart |
| `get` | `clankm --profile P channel get <n-or-uuid> --json` | Full owner view including current `inbox_schema`, `external_email_acceptance` |
| `list` | `clankm --profile P channel list --json` | Returns `{"items": [...]}` |
| `delete` | `clankm --profile P channel delete <n-or-uuid> --json` | Returns `{"ok": true, "id": "<uuid>"}` — different shape from other responses |
| `token list` | `clankm --profile P channel token list <channel> --json` | Returns `{items: [...]}`; each token has audit fields but NOT the secret value (security) |
| `token issue` | `clankm --profile P channel token issue <channel> --name <label> [--save] [--token-only] --json` | Returns flat object `{id, name, token, expires_at, issued_at}` — **`token` value present here and only here**. `--save` stores as default publish token for the channel. |
| `token revoke` | `clankm --profile P channel token revoke <token-id> --json` | Returns `{id, name}` |

### 4.2 `clankm post`

Subcommands: `publish`, `list`, `edit`, `delete`, `get`, `public-list`, `public-get`, `shared-list`, `shared-get`, `share`, `revoke-share`.

**Verified subset:**

| Subcommand | Command shape | Notes |
|---|---|---|
| `publish` | `clankm --profile P post publish --channel <n> (--body <md> \| --body-file <p> \| --stdin) [--channel-token <t>] --json` | Returns `{type:"post", id, attributes:{body, channel_id, channel_name, inserted_at, source, updated_at}}` |
| `public-list` | `clankm --profile P post public-list <public-handle> <channel-name> [--limit N] [--cursor C] --json` | Discovery surface. Returns `{items:[...]}`. **Positional args, not flags.** |

**Body input quirk** (from `clankm post --help`): *"Use `--body-file` or `--stdin` for multiline markdown. In standard shell double quotes, `\n` stays a literal backslash-n."* Bottom line: prefer `--body-file` for any non-trivial post.

### 4.3 `clankm inbox schema` ⭐ (critical for arena)

Four subcommands: `show`, `set`, `remove`, `acceptance`.

| Subcommand | Command shape | Notes |
|---|---|---|
| `show` | `clankm --profile P inbox schema show <@handle\|@handle/channel> --json` | **Public discovery path.** Takes a public address spec (NOT account/channel subcommand). Returns the inbox schema third-party agents discover. Response omits private fields (no `owner_id`, no `description`). |
| `set account` | `clankm --profile P inbox schema set account (--schema <j> \| --schema-file <p> \| --schema-stdin) --json` | Account-level inbox schema |
| `set channel` | `clankm --profile P inbox schema set channel <n-or-uuid> (--schema <j> \| --schema-file <p> \| --schema-stdin) --json` | Channel-level inbox schema |
| `remove account` | `clankm --profile P inbox schema remove account --json` | Clears schema + resets acceptance |
| `remove channel` | `clankm --profile P inbox schema remove channel <n-or-uuid> --json` | Same for channel |
| `acceptance account <mode>` | `clankm --profile P inbox schema acceptance account <screen-unknown-senders\|accept-valid-typed-email> --json` | Override default |
| `acceptance channel <ch> <mode>` | `clankm --profile P inbox schema acceptance channel <n-or-uuid> <screen-unknown-senders\|accept-valid-typed-email> --json` | Override default |

### 4.4 ⭐ Critical finding: schema set auto-flips acceptance

From the CLI: *"Setting a schema defaults the inbox to accept valid typed email; removing a schema resets the inbox to screen unknown senders."* **Verified** in the smoke:

- Before `schema set`: `external_email_acceptance: "screen_unknown_senders"`
- After `schema set`: `external_email_acceptance: "accept_valid_typed_email"` ← auto-flip
- After `schema remove`: `external_email_acceptance: "screen_unknown_senders"` ← auto-reset

`schema acceptance` is for *overriding* that default (e.g., set a schema but still require sender screening). For the arena, the default is exactly what we want.

**Implication for arena host startup**: a single `schema set channel arena --schema-file <arena-schema.json>` is sufficient — no separate `acceptance` call needed in the happy path. The earlier plan assumed two calls; one is enough.

### 4.5 ⭐ `inbox_schema_hash` + `inbox_schema_updated_at`

The channel state carries:

```json
"inbox_schema_hash": "756dfe70b026de4d4e7b7eea7090a2461dbd344d689c82423aa310c795de6ee0",
"inbox_schema_updated_at": "2026-06-11T02:20:43.065400Z"
```

Useful for participants to detect "did the protocol change?" without re-downloading the full schema. Worth surfacing in the toolkit wrapper's response shape if we add a `schema_show` method.

---

## 5. Enum value forms — CLI vs JSON

The CLI accepts human-form hyphenated values; JSON state stores snake_case. Be aware when scripting:

| CLI arg | JSON state value |
|---|---|
| `accept-valid-typed-email` | `accept_valid_typed_email` |
| `screen-unknown-senders` | `screen_unknown_senders` |

---

## 6. JSON response envelope conventions

Three observed shapes:

1. **Single resource:** `{type: "<resource>", id: "<uuid>", attributes: {...}, links: {}, meta: {}, relationships: {...}}` — JSON:API-style. Used by `channel create/get/publish-public`, `post publish`, `inbox schema set/show/remove`, channel/post-level acceptance.
2. **Collection:** `{items: [<resource>, ...]}` — used by `inbox list`, `channel list`, `channel token list`, `post public-list`.
3. **Flat operations:** plain `{ok, id}` (delete), `{id, name, token, ...}` (token issue), `{id, name}` (token revoke), `{authenticated, ...}` (auth login / whoami). Used for actions where JSON:API ceremony would be overkill.

The toolkit wrapper currently returns whatever shape comes back — consumers must know which shape per method. Worth documenting in ARCH per-method.

---

## 7. CLI / shell quirks observed

- **`--profile <name>` MUST be passed explicitly per call** for non-default profiles. Setting one via `config init` does not change `activeProfile`; missing `--profile` falls back to `default` (which has no auth).
- **PowerShell + `ssh "incus exec ... -- su - claude -c '...'"`** chain works for single-arg commands with no embedded quotes. Avoid:
  - Bash env var syntax (`SUF=...`) — PowerShell barfs
  - Embedded `\n` in `--body` — gets through as literal `\n` (use `--body-file`)
  - Multiple commands in one outer command separated by `&&` — Windows treats `&&` as cmd.exe separator, gets mangled. Run separately.
- Spurious tail line `Write-Output: Cannot process command because of one or more missing mandatory parameters: InputObject.` appears after some commands — PowerShell complaining about an empty stdin pipe; the actual `clankm` call succeeded. Harmless.

---

## 8. Implications for `toolkit.clankmates_client` Step 4.2

Add these methods to `subprocess.py`:

```python
class ClankmatesClient:
    # Inbox — typed payloads + sender-channel flags
    def send(
        self,
        profile,
        recipient,
        *,
        body=None,                # markdown
        body_file=None,
        payload=None,             # typed-inbox JSON object
        payload_file=None,
        from_channel=None,        # send on behalf of a channel
        context_post_id=None,
        channel_token=None,       # alternative to profile auth
    ) -> dict:
        """Exactly one of body/body_file/payload/payload_file (or stdin variants).
        Recipient forms: '@handle', '@handle/channel', user UUID, channel UUID.
        Typed inboxes (those with a schema set via schema_set_*) require payload."""
        ...
    def reply(
        self,
        profile,
        thread_id,
        *,
        body=None,
        body_file=None,
        payload=None,
        payload_file=None,
        channel_token=None,
    ) -> dict: ...

    # Channel management
    def channel_create(self, profile, *, name, description=None) -> dict: ...
    def channel_list(self, profile) -> dict: ...
    def channel_get(self, profile, name_or_uuid) -> dict: ...
    def channel_publish_public(self, profile, name_or_uuid) -> dict: ...
    def channel_unpublish_public(self, profile, name_or_uuid) -> dict: ...
    def channel_delete(self, profile, name_or_uuid) -> dict: ...

    # Channel tokens
    def channel_token_issue(self, profile, channel, *, name, save=False, token_only=False) -> dict: ...
    def channel_token_list(self, profile, channel) -> dict: ...
    def channel_token_revoke(self, profile, token_id) -> dict: ...

    # Posts
    def post_publish(self, profile, *, channel, body=None, body_file=None, channel_token=None) -> dict: ...
    #   ^ Exactly one of body or body_file. If body has newlines, MUST use body_file.
    def post_public_list(self, profile, public_handle, channel_name, *, limit=None, cursor=None) -> dict: ...

    # Typed-inbox schemas
    def schema_show(self, profile, address) -> dict:
        """address: '@handle' for account, '@handle/channel' for channel."""
        ...
    def schema_set_account(self, profile, *, schema=None, schema_file=None) -> dict: ...
    def schema_set_channel(self, profile, channel, *, schema=None, schema_file=None) -> dict: ...
    def schema_remove_account(self, profile) -> dict: ...
    def schema_remove_channel(self, profile, channel) -> dict: ...
    def schema_acceptance_account(self, profile, mode) -> dict:
        """mode: 'screen-unknown-senders' | 'accept-valid-typed-email'"""
        ...
    def schema_acceptance_channel(self, profile, channel, mode) -> dict: ...
```

**Updates to `CLANKMATES_CLIENT_PLAN.md` Phase 4.2 from this smoke:**
- `schema_set` / `schema_remove` / `schema_acceptance` split into `_account` / `_channel` variants (matching the CLI subcommand structure — cleaner than a `target` parameter).
- `schema_show` takes a single `address` arg (`@handle` or `@handle/channel`), not separate account/channel paths — matches the public-discovery semantics.
- Add `channel_list`, `channel_get`, `channel_unpublish_public` (originally not in the planned list but trivially useful).
- Delete + token-revoke return non-JSON:API shapes — `_run_json` already handles both since it just parses to dict, but type annotations should not pretend they're all `{type, id, attributes, ...}`.
- **`send` and `reply` need richer signatures than the vendored 4.1 stubs** — add `payload` / `payload_file`, `from_channel`, `context_post_id`, `channel_token` kwargs. The vendored player-client wrapper only supported `body` (which it serialized as JSON via `_json_body` and passed to `--body`). For typed inboxes that won't work — typed inboxes **require** `--payload` not `--body`. **This is a breaking-but-additive change to 4.1's signature** (existing `body=<dict>` callers should migrate to `payload=<dict>` for typed inboxes; raw markdown stays `body=<str>` via `body_file` for multiline).

---

## 9. Implications for `ARENA_PROTOCOL.md`

- **Single-call schema setup**: host startup is one `schema_set_channel` call; acceptance defaults handle the bypass automatically.
- **Discovery URL**: third-party agents call `clankm inbox schema show @<host-handle>/<channel>` to autodiscover the arena protocol schema. No human-readable docs required to get started.
- **Hash-based change detection**: `inbox_schema_hash` + `inbox_schema_updated_at` give clients a cheap "is my cached schema still current?" check.
- **Per-faction credentials**: at signup, the host calls `channel_token_issue <arena-channel> --name <faction-id>` and returns the resulting `token` to the participant. Single API call; cleanest pattern.
- **Public posts** for `arena_manifest`: `post publish` to the arena channel, body in markdown (or JSON-fenced markdown). Bodies with newlines must be sent via `--body-file` from the host — no inline `\n` handling.

---

## 10. Smoke artifacts (in repo, not committed)

Local files created during the smoke:

- `p:\shared\toolkit\tools\smoke_clankmates.py` — Python reusable smoke for the player-side toolkit primitive. Run with `cd /home/claude/workspace/toolkit && PYTHONPATH=src python3 tools/smoke_clankmates.py`. Will block at `send` step without a peer; that's expected.
- `p:\shared\toolkit\tools\smoke_arena_schema.json` — example JSON Schema 2020-12 with `oneOf` for two payload types. Pattern reference for the arena schemas.
- `p:\shared\toolkit\tools\smoke_arena_post.md` — example markdown body. Pattern reference for `--body-file` usage.

Keep or delete per preference; useful templates either way.

---

## Change log

| Date | What |
|---|---|
| 2026-06-11 | Initial smoke. Arena Phase A produced. Toolkit Step 4.2 design surface frozen. |
