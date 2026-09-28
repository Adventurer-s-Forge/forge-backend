# forge-backend: Public API

Client-facing HTTP API of the Adventurer's Forge backend, as consumed by the React client
(and exploratory tools like Postman/curl). Everything here is served by
`uv run uvicorn forge_backend.main:app` and verified by `tests/test_character_data_routes*.py`
and `tests/test_user_character_data_routes.py`.

## Conventions

- **JSON only.** Request bodies and responses are `application/json`.
- **Errors** use FastAPI's envelope: `{"detail": "..."}` for handler errors (400/404/422
  stand-in) and `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` for request
  validation failures (422).
- **No cookies, no server-side sessions.** Identity is carried per request (see
  Authentication); nothing about the caller is stored server-side.
- **CORS** is configured via `CORSMiddleware` with origins from `config.CORS_ORIGINS`
  (env `CORS_ORIGINS`, default `http://localhost:5173`); allowed methods GET/POST/PUT/DELETE.
- **Reference content is served from the Redis seed only.** The running API never calls
  Open5e (AGENTS.md §2): lists return whatever the deploy-time seed wrote, or `[]` when a
  type is unseeded.

## Authentication

Character endpoints take the user's identity from a request header:

| Header | Required on | Meaning |
|---|---|---|
| `X-User-Id` | `/characters/*` | The acting user's ID. Must be present and non-empty. |

- Missing or empty `X-User-Id` → **422** (`{"detail": "X-User-Id header required"}` for an
  empty value; FastAPI's validation envelope for a missing header).
- This is a **stand-in**: Firebase ID-token verification lands with the auth work
  (`TODO(US-19/auth)` on `get_uid` in `character_data_routes.py`). When it does, expect
  `Authorization: Bearer <token>` and **401** for missing/invalid tokens.
- Enforcement is server-side and keys are namespaced per user (`char:{uid}:{id}`): a
  character is only reachable with the same `X-User-Id` that owns it.

## Reference content

Read-only, unauthenticated. All five lists share one record shape and one behavior.

| Method & path | Returns |
|---|---|
| `GET /races` | race records |
| `GET /classes` | class records (the class-selection source) |
| `GET /backgrounds` | background records |
| `GET /items` | item records |
| `GET /spells` | spell records |

Record shape (the seed envelope):

```json
{
  "type": "class",
  "key": "srd_wizard",
  "name": "Wizard",
  "document": "srd-2014",
  "data": { "...verbatim Open5e v2 record..." }
}
```

- **200**: JSON array of records, ordered by `key`. `[]` if the type is unseeded.

## Health

| Method & path | Auth | Returns |
|---|---|---|
| `GET /health` | none | `{"status": "ok", "seed_counts": {...} \| null}` |

`seed_counts` is the outcome of the startup seeding pass (e.g.
`{"race": 20, "class": 12, ...}`), or `null` when seeding failed or hasn't run (the app
still serves in that case).

## Characters

Character records are shaped `{"owner": ..., "name": ..., "class": ...}` (`class` is
absent until a class is saved). Two route families exist:

- `/characters/*` (US-35): per-request identity via `X-User-Id`; class read/update.
- `/user-character*` (US-18): identity via `user_id` in the path/body; no header.

### `GET /characters/{character_id}`

Fetch one character owned by the requesting user.

| | |
|---|---|
| Auth | `X-User-Id` required |
| **200** | the character record |
| **404** | `{"detail": "character not found"}`: no such id for this user |
| **422** | missing/empty `X-User-Id` |

### `PUT /characters/{character_id}/class`

Save the character's class. Exactly one class per character: a save **replaces** any
previous value (no multi-classing in the MVP).

| | |
|---|---|
| Auth | `X-User-Id` required |
| Body | `{"class": "<value>"}`: `class` required, non-empty string |
| **200** | the updated character record (includes `"class"`) |
| **400** | `{"detail": "unknown class"}`: value is not a seeded class; **nothing is written** |
| **404** | `{"detail": "character not found"}`: checked before class validation |
| **422** | body validation (`class` absent, `null`, or empty) or missing/empty `X-User-Id` |

Accepted `class` values, matched against the seeded class records and persisted **verbatim**:

- the seeded `key` (slug), e.g. `srd_wizard`, or
- the seeded `name`, e.g. `Wizard`.

Precedence when several things are wrong: body validation (422) → unknown character (404) →
unknown class (400). Each failure leaves the record untouched.

### US-18 user-character routes (no header; `user_id` in path/body)

Responses use a `{"status_code", "detail"}` wrapper; errors use FastAPI's `{"detail": ...}`
envelope. Character IDs are `uuid4().hex[:8]` (8 hex chars), collision-checked ×5 against
`char:idx:{uid}`.

| Method & path | Body | **Success** |
|---|---|---|
| `POST /user-character` | `{"user_id": ..., "character_name": ..., "user_name": ...}` (all required strings) | **201** `{"status_code": 201, "detail": {"character_id": "<8-hex id>", "result": 1}}` |
| `GET /user-character/{user_id}/ids` | N/A | **200** `{"status_code": 200, "detail": ["<id>", ...]}` (sorted) |
| `GET /user-character/{user_id}/list` | N/A | **200** `{"status_code": 200, "detail": [<character records>]}` |
| `GET /user-character/{user_id}/{character_id}` | N/A | **200** `{"status_code": 200, "detail": <record>}`; **404** `{"detail": "Character not found!"}` when missing |
| `GET /num-user-characters/{user_id}` | N/A | **200** `{"status_code": 200, "detail": <int>}` (`0` when none) |

Validation failures (missing/empty body fields) use FastAPI's 422 envelope. Duplicate
character-ID collision after 5 generation attempts → **409**
`{"detail": "Character ID collision, retry"}`. Missing character → **404**, unlike the
`null`-returning pre-US-18 shape.


```sh
# Create a character (US-18)
curl -s -X POST localhost:8000/user-character \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "my-user-id", "character_name": "Joe Schmoe", "user_name": "moobelle"}'
# -> 201 {"status_code":201,"detail":{"character_id":"3f2a91c4","result":1}}

# Class list: the class-selection source
curl -s localhost:8000/classes

# Save a class
curl -s -X PUT localhost:8000/characters/3f2a91c4/class \
  -H 'X-User-Id: my-user-id' -H 'Content-Type: application/json' \
  -d '{"class": "Wizard"}'
# -> 200 {"owner":"...","name":"...","class":"Wizard"}

# Fetch the character
curl -s localhost:8000/characters/3f2a91c4 -H 'X-User-Id: my-user-id'

# Unknown class: rejected before any write
curl -s -X PUT localhost:8000/characters/3f2a91c4/class \
  -H 'X-User-Id: my-user-id' -H 'Content-Type: application/json' \
  -d '{"class": "Illiudicor"}'
# -> 400 {"detail":"unknown class"}
```

## Not part of this API (yet)

| Concern | Owner |
|---|---|
| Character deletion (`DELETE`) | US-18 (follow-up; create/list/get/count live) |
| Race selection on a character | US-34 (frontend; backend storage exists) |
| Firebase ID-token auth (401 semantics) | auth story (`TODO(US-19/auth)`) |
| Sharing / read-only access | US-27 … US-31 |
| Derived stats (AC, HP, spell DC, …) | rules-engine stories |
