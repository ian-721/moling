# M0-B v0.8 remote-install protocol and recovery baseline

## Anonymous device identity

On first launch Android creates a random installation UUID and calls:

```http
POST /api/auth/device/register
Content-Type: application/json

{"installationId":"<random UUID>"}
```

The server stores only an HMAC digest of the installation ID, creates a
`principal_type=device` principal and a principal-keyed profile with
`assistant_name=墨灵`, then returns one 256-bit opaque bearer token. Only the
token HMAC is stored in PostgreSQL/SQLite. Android encrypts the token with a
non-exportable Android Keystore AES-256-GCM key; encrypted token preferences
are excluded from backup and device transfer.

Submitting an existing installation ID without its current bearer token
returns a conflict. An authenticated installation can rotate its token; all
previous active tokens for that principal are revoked. If Android receives
401 and no longer has a valid token, it clears the token and cached role name,
creates a new installation UUID, and registers at most once. The old
installation ID is never treated as a credential.

All protected routes use:

```http
Authorization: Bearer <opaque token>
```

`GET/PATCH /api/profile`, `GET /api/usage`, and
`POST /api/notebook/reply` derive the principal only from that token. Identity
and `assistantName` fields in a reply body are ignored. Profile rows, usage
windows, and idempotency keys are all joined by `principal_id`, never by name.

## Quota and idempotency transaction

Before a provider call the backend atomically:

1. locks the principal;
2. checks the principal minute window;
3. reserves one daily and monthly request;
4. locks and reserves global monthly CNY budget;
5. creates or reacquires `(principal_id, request_id)` with a bounded lease.

Provider success converts the reservation to actual request/token/cost usage
and persists a safe response snapshot. Provider failure releases daily,
monthly, and budget reservations. Minute rate attempts remain bounded.

The same principal, request ID, and fingerprint replays the stored success
without a provider call. A changed fingerprint returns 409. A live lease
returns `request_in_progress`; an expired lease can be recovered with the same
request ID. Different principals may use the same request ID.

## Android local state machine

Room database version 1 contains:

- `pages`
- `strokes` (x, y, timestamp, pressure, color, width)
- `notebook_turns`
- `reply_outbox`

The durable request states are:

```text
RECOGNIZING
→ READY_TO_SEND
→ SENDING
→ SUCCEEDED
→ ABSORBED

SENDING → RETRYABLE_FAILED → SENDING
SENDING → PERMANENT_FAILED
```

A completed stroke is inserted immediately. “回应” first creates a Room
transaction containing the request ID, selected stroke IDs, turn, and outbox;
recognition/network work starts only after that transaction succeeds. Failure
returns selected strokes to editable state. Provider success is stored before
the overlay is revealed. Absorption deletes only the stored stroke snapshot,
so strokes written during the animation survive.

On process restart, pages/strokes/turns are restored; interrupted `SENDING`
outbox rows become `RETRYABLE_FAILED`, and retry reuses the same request ID.
A late response is saved to its turn but only the current active request may
replace the visible overlay.

Recent context uses the current cached server profile name, not a hard-coded
“墨灵：” prefix.
