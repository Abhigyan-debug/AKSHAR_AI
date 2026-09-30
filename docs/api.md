# API reference

All routes are under `/api`. Request and response bodies are JSON unless noted.

Teacher routes need `Authorization: Bearer <token>` from `POST /api/auth/login`. Without a valid token they return `401`. Public routes are marked below.

## Sign in

### `POST /api/auth/login` (public)

```json
{ "pin": "<school PIN>" }
```

Returns `{ "token": "…", "expires_at": 1790000000 }`. Tokens last 12 hours. A wrong PIN returns `401`; five wrong PINs from one address within 10 minutes return `429` until the window passes.

### `GET /api/health` (public)

Returns `{ "ok": true }`.

## Children

| Method | Path | Body | Returns |
|---|---|---|---|
| `POST` | `/api/children` | `{ "code": "R01", "grade": 3, "home_lang": "Hindi" }` | the child (`201`); `409` if the code exists; `422` if the code has anything but letters, digits, `-` or `_` |
| `GET` | `/api/children` | | all children |
| `GET` | `/api/children/{id}` | | one child |
| `GET` | `/api/children/{id}/report` | | child, latest session, report, every item result |
| `DELETE` | `/api/children/{id}` | | removes the child, sessions, results, reports and recordings (`204`) |
| `DELETE` | `/api/children/{id}/audio` | | removes every recording of the child; scores stay (`204`) |

## Test items

`GET /api/tests/{lang}` with `lang` = `hi` or `en` returns the item bank from `backend/data/tests/`. See [test-content.md](test-content.md).

## Sessions

### `POST /api/sessions`

```json
{ "child_id": 1, "include_sound_game": true }
```

### `POST /api/sessions/{id}/items/{item_id}/audio`

Multipart form:

| Field | Required | Notes |
|---|---|---|
| `file` | yes | webm, ogg, wav, m4a, mp3 or flac, up to 10 MB. The type is checked from the file's bytes; anything else returns `415`. |
| `live_tap` | for manual items only | `correct`, `incorrect` or `skipped`. Manual items without it, and auto items with it, return `422`. |

Returns the item result. Uploading the same item again replaces the earlier clip and result. A finished session returns `409`.

### `POST /api/sessions/{id}/finish`

Marks the session finished, labels leftover errors, computes the risk and writes the summaries. Call it again to refresh an out-of-date summary. Returns `{ "session": …, "report": … }`.

### `POST /api/sessions/{id}/parent-link`

Creates a new parent link token. The old link stops working. Returns `{ "parent_token": "…" }`.

## Results

### `PATCH /api/results/{id}`

```json
{ "decision": "incorrect", "words_correct": 35 }
```

`decision` is `correct`, `incorrect` or `skipped`. On a manual item it corrects the live tap. On the passage, `correct` means the AI heard it right, and `incorrect` needs `words_correct` (the teacher's own count). The response has the updated result and, for finished sessions, the recomputed report.

## Class and audio

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/class/summary` | one row per child: latest result, items waiting for a check, session status |
| `GET` | `/api/audio/{result_id}` | the clip with its audio content type; `404` once deleted |
| `DELETE` | `/api/audio/{result_id}` | deletes one clip (`204`); the score stays |

## Parent page

### `GET /api/parent/{token}` (public)

Returns the Hindi label, summary, three tips, generic places to get help (shown for results that need support) and the disclaimer. It carries no child code or name. `ready` is `false` while the result is pending or provisional. `practice` lists practice game ids, the child's own error pattern first (empty until the result is final).

### `GET /api/practice` (public)

The practice game content from `backend/data/practice.json`. It holds no child data. See [practice.md](practice.md).

## Response headers

Every response carries `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a restrictive `Content-Security-Policy` and a `Permissions-Policy`. The interactive docs at `/api/docs` are off unless `AKSHAR_API_DOCS=true`.
