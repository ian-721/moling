# M0-B backend deployment and rollback

## Required target

Deploy `backend/Dockerfile` behind a managed HTTPS ingress with a persistent
PostgreSQL database. The container listens on port 8000; TLS terminates at the
platform ingress. Do not expose the container directly over public HTTP.

The startup command runs `alembic upgrade head` before starting Uvicorn.
Migrations are repeatable and the readiness probe checks only database
connectivity. `/healthz` and `/readyz` do not expose user counts, remaining
budget, secrets, or model credentials.

## Required production configuration

Inject these through the deployment platform's secret/config manager:

- `MOLING_ENV=production`
- `MODEL_PROVIDER=deepseek`
- `DEEPSEEK_API_KEY` (secret)
- `PROVIDER_USER_ID_SALT` (independent high-entropy secret, at least 32 UTF-8
  bytes)
- `TOKEN_HASH_PEPPER` (independent high-entropy secret, at least 32 UTF-8
  bytes; changing it invalidates all access tokens)
- `DATABASE_URL` (secret): on Railway, reference the PostgreSQL service's
  standard `DATABASE_URL` directly; do not copy its value into source or
  rebuild it from separate credential fields
- every authentication, registration, rate, quota, lease, and budget variable
  listed in `backend/.env.example`
- `VISION_FALLBACK_ENABLED=false`
- `DEBUG_IMAGE_SAVE_ENABLED=false`

Production startup deliberately fails when these controls are implicit, when
PostgreSQL or DeepSeek is not selected, or when Vision/image persistence is
enabled.

The backend binds an exact leading `postgresql://` scheme to
`postgresql+psycopg://` internally so SQLAlchemy and Alembic use the installed
psycopg 3 driver. It does not parse or reserialize the username, password,
percent-encoding, host, port, database, query, or fragment. An already explicit
`postgresql+psycopg://` URL remains unchanged, as do SQLite development and
test URLs.

Never manually copy, split, decode, encode, or reassemble the database
password. The complete `DATABASE_URL` must remain in the deployment platform's
Secret/reference mechanism and must not be committed to Git, pasted into a PR
or chat, or written to ordinary application or deployment logs.

## Deployment verification

1. Build the image without any `.env` file in its context.
2. Run `python scripts/deployment_preflight.py` inside the runtime Secret
   environment; it rejects known placeholder markers, outer whitespace and
   short HMAC secrets without printing values or opening a network connection.
3. Run migrations against a staging PostgreSQL database.
4. Run the default probe-only `scripts/remote_https_smoke.py` against an
   explicitly supplied HTTPS hostname.
5. With staging writes and model cost explicitly authorized, add
   `--exercise-api` to register a disposable installation, reuse its Token,
   read/patch Profile, read Usage, exercise normal/deep DeepSeek replies,
   validate provider/model/degradation/response fields, replay a request ID,
   verify a changed payload conflicts, and prove Usage increases only for the
   two original successful provider calls.
6. Confirm platform and ingress logs contain no Authorization header, token
   hash, note text, recent context, full reply, database URL or Secret.

The complete pre-deploy, post-deploy, quota/budget, log and data-preserving
rollback protocol is
`docs/deployment/M0B3A_REAL_ENVIRONMENT_PREFLIGHT.md`.

## Rollback

Roll back the application image first. The M0-B migration is additive; the
previous M0-A image cannot use the new authentication API but does not require
dropping tables. Do not run the destructive Alembic downgrade in production.
If a forward migration fails, stop rollout, preserve database logs, correct the
migration, and roll forward from the last successful revision.

No paid cloud resource is created by this repository. A real deployment still
requires an explicitly authorized platform, HTTPS hostname, PostgreSQL
credential, and DeepSeek key.
