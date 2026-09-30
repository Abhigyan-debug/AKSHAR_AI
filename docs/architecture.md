# Architecture

Akshar has two parts: a React single-page app and a FastAPI backend with SQLite. Audio and results stay on the backend's own disk. The only outside service is Groq, which receives each audio clip for transcription and a summary of computed facts for the written summaries.

```
phone / laptop browser
  React + Vite + Tailwind + Motion
  │  /api (bearer token for teacher routes)
  ▼
FastAPI  ──►  Groq Whisper (whisper-large-v3)       audio clip → transcript + timestamps
  │      ──►  Groq LLM (openai/gpt-oss-120b)        facts → teacher and parent summaries
  ▼
SQLite (child, session, item_result, report) + audio files on disk
```

## One item, from microphone to result

1. Child mode records the item with `MediaRecorder` and stops after 5 seconds of silence or at a maximum length (15 s per item, 120 s for the story). An upload queue sends clips in the background and retries network failures, so the child never waits.
2. `POST /api/sessions/{id}/items/{item_id}/audio` checks the file by its bytes, stores it, and calls Whisper. If Groq fails, the clip is kept and the item goes to teacher verify.
3. `analyse_item` runs the pipeline in `backend/app/services/`:
   - `confidence.py` decides the item's status. Manual items are live-tapped; items with low Whisper confidence, an empty transcript or the wrong script become `teacher_verify`; the rest are `auto`.
   - `normalize.py` makes spelling variants compare equal (nukta, chandrabindu, gemination).
   - `classify_rules.py` compares the transcript with the target using `akshara.py` (Devanagari akshara split) and `align.py` (Levenshtein alignment) and labels each error.
   - `timing.py` turns Whisper's word timestamps into hesitation, slow start and slow decoding flags.
4. The result is saved in `item_result`. The status never changes afterwards; a teacher's decision sets `verified` or `live_tap` instead, so the report can still say how many items were auto-scored.

## One session, from last item to report

`POST /api/sessions/{id}/finish` calls `store.build_report`:

1. `llm.label_residual_errors` asks the LLM to label word errors the rules left as `unclassified`, choosing only from an allowed list.
2. `risk.compute_risk` computes per-language accuracies, words correct per minute and a weighted error score, then applies the decision table.
3. `llm.generate_summaries` writes the teacher and parent text, or a template while the result is still pending.

Every later teacher decision (`PATCH /api/results/{id}`) recomputes the risk. The AI summary is written automatically the first time the result is final with an empty verify queue; after that a change only marks it out of date.

See [scoring.md](scoring.md) for the rules themselves.

## Data model

| Table | Holds |
|---|---|
| `child` | code (letters, digits, `-`, `_`; no names), grade, home language |
| `session` | child, status (`in_progress` or `finished`), whether the sound game was included |
| `item_result` | one per item per session: transcript, word timestamps, errors, status, teacher decision, confidence, timing, audio path |
| `report` | one per session: metrics, scoring breakdown, risk level, reasons, summaries, parent link token |

## Frontend

| Path | Page | Access |
|---|---|---|
| `/` | Landing page | public |
| `/login` | Teacher sign in | public |
| `/p/:token` | Parent page (Hindi, read aloud) | anyone with the link |
| `/practice`, `/practice/:token` | Practice games, all or ordered for one child | public |
| `/child` | Pick or create a child code | teacher |
| `/child/run/:sessionId` | Child reading screen | teacher's device |
| `/teacher` | Class dashboard | teacher |
| `/teacher/child/:childId` | Child report and verify queue | teacher |

The teacher pages load the chart and QR libraries lazily, so a child's phone never downloads them. Fonts are self-hosted with `@fontsource`, which keeps the parent page free of third-party requests.

## Code map

```
backend/app/
  main.py          create_app(): config, CORS, security headers, routers
  security.py      AuthConfig (PIN, tokens, rate limit), require_teacher, sniff_audio
  db.py            SQLModel tables
  config.py        loads config/thresholds.json and the item bank
  routes/          auth, children, tests, sessions, reports, parent, deps
  services/
    transcribe.py  Groq call, verbose_json parsing, DEMO_MODE cache
    normalize.py   comparison rules
    akshara.py     akshara split and phoneme-like units
    align.py       Levenshtein alignment
    classify_rules.py  error labels
    confidence.py  status gate
    timing.py      timing flags
    analyse.py     one item end to end, teacher decisions, scoring breakdown
    risk.py        risk engine
    llm.py         summaries and residual labels
    store.py       rows ↔ results, report (re)build
    bank.py        item bank lookups
    cache.py       DEMO_MODE response cache
frontend/src/
  api.ts           typed API client, bearer token, 401 handling
  lib/             auth (token), recorder, uploadQueue, speech, diff, wav, labels
  components/      ui, child, report, TeacherHeader
  pages/           Home, Login, ChildSetup, ChildRun, TeacherDashboard, ChildReport, Parent
```
