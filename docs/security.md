# Security and privacy

Akshar records children's voices and produces sensitive results, so the defaults favour keeping data with the school and showing it only to teachers.

## What is protected, and how

### Teacher access

Every route that reads or changes children, recordings or results needs a teacher token. A teacher gets one by signing in with the school PIN (`TEACHER_PIN`).

- The token is signed with HMAC-SHA256 using `AKSHAR_SECRET` and expires after 12 hours.
- The PIN comparison takes constant time.
- Five wrong PINs from one address within 10 minutes lock that address out for the rest of the window, even with the right PIN.
- The backend will not start if the PIN is shorter than 6 characters or the secret shorter than 32.
- The frontend keeps the token in `sessionStorage`, so it disappears when the tab closes, and sends the teacher back to sign in when the API rejects it.

Only four routes are public: health, sign-in, the parent page and the practice game content. The practice content holds no child data; the child's recommended games come through the parent page's token.

### Parent links

A parent link contains a random 128-bit token (`/p/<token>`). The page shows the Hindi summary and tips but no child code or name. A teacher can make a new link from the report, which stops the old one working. Both the page and the API send `Referrer-Policy: no-referrer` so the token is not passed to other sites, and fonts are self-hosted so the parent page makes no third-party requests.

### Uploads

- Audio type is decided from the file's first bytes, not from its name or the content type the browser sends. Anything that is not webm, ogg, wav, m4a, mp3 or flac is rejected.
- The server reads at most 10 MB plus one byte, then rejects larger files.
- File paths are built from the session number and a known item id, never from user input.

### Personal data

- Children are known only by a code. The API rejects codes with spaces or other characters, which steers teachers away from typing names.
- Recordings and the database stay on the backend's disk. The only data that leaves is each clip, sent to Groq for transcription, and computed facts (no audio, no code) sent to Groq for the summaries.
- A teacher can delete one clip, all of a child's clips, or the child and everything recorded for them.

### Responses

Every API response carries `Cache-Control: no-store` (so shared or school computers don't cache reports), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a default-deny `Content-Security-Policy` and a `Permissions-Policy`. The interactive API docs are off by default. CORS allows only the origins in `CORS_ORIGINS` and only the methods and headers the app uses.

### LLM output

The LLM never decides a result. Its replies must be valid JSON matching a schema, contain no diagnosis wording and, for parents, be in Devanagari; anything else is rejected and replaced with a template. Residual error labels must come from a fixed list. React escapes all rendered text, and the app never injects HTML.

### Dependencies

At the time of writing, `npm audit --omit=dev` and `pip-audit` report no known vulnerabilities.

## What is not covered yet

Be honest with the school about these before real use:

- One shared PIN serves every teacher. There are no individual accounts, roles or audit log of who viewed or changed what.
- A single token cannot be revoked. Changing `AKSHAR_SECRET` signs everyone out.
- The sign-in rate limit is kept in memory. It resets when the server restarts and does not work across several server processes.
- Recordings and the database are not encrypted at rest. Use an encrypted disk.
- The server logs request paths, which include parent link tokens. Restrict access to logs, or rotate the link after sharing if logs are widely readable.
- There is no automatic retention period. Recordings stay until a teacher deletes them.
- Clips are sent to Groq. Check that this matches the school's and parents' consent before use.

## Operator checklist

- [ ] Set a PIN that is not a date or a repeated digit, and share it only with teachers.
- [ ] Generate `AKSHAR_SECRET` with `secrets.token_urlsafe(48)`; never commit `.env`.
- [ ] Serve frontend and backend over HTTPS only.
- [ ] Set `CORS_ORIGINS` to the exact frontend origin.
- [ ] Keep `AKSHAR_API_DOCS=false`.
- [ ] Put storage and the database on an encrypted, backed-up disk.
- [ ] Run a single backend process, or move the rate limiter to shared storage first.
- [ ] Agree a retention period and delete recordings when it ends.
- [ ] Get consent for sending recordings to Groq.
