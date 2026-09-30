# Setup and deployment

## Requirements

- Python 3.10 or newer
- Node 22 or newer
- A Groq API key (https://console.groq.com/keys)

## Configuration

All settings live in `.env` at the project root. Copy `.env.example` and fill it in.

| Variable | Required | Default | What it does |
|---|---|---|---|
| `GROQ_API_KEY` | yes | | Groq key for transcription and summaries. Without it, uploads go to the teacher verify queue and summaries fall back to a template. |
| `TEACHER_PIN` | yes | | School PIN teachers sign in with. At least 6 characters. |
| `AKSHAR_SECRET` | yes | | Signs teacher tokens. At least 32 characters. Changing it signs every teacher out. |
| `GROQ_STT_MODEL` | no | `whisper-large-v3` | Speech-to-text model. The spike picked this one (see [scoring.md](scoring.md)). |
| `GROQ_LLM_MODEL` | no | `openai/gpt-oss-120b` | Model that writes the summaries. |
| `DEMO_MODE` | no | `false` | `true` serves cached Groq responses for clips and prompts seen before, so a demo keeps working if the API is slow. |
| `CORS_ORIGINS` | no | `http://localhost:5173` | Comma-separated frontend origins allowed to call the API. |
| `AKSHAR_DB_URL` | no | `sqlite:///backend/akshar.db` | Database URL. |
| `AKSHAR_STORAGE` | no | `backend/storage` | Folder for audio clips. |
| `AKSHAR_API_DOCS` | no | `false` | `true` serves the interactive API docs at `/api/docs`. Keep it off in production. |

Generate a secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The frontend reads one optional variable at build time: `VITE_API_BASE`, the backend URL when it runs on a different host (for example `https://api.akshar.example`). In development Vite proxies `/api` to port 8000, so you can leave it unset.

## Running locally

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:create_app --factory --reload      # port 8000

cd frontend
npm install
npm run dev                                          # port 5173
```

The app factory (`create_app`) creates the SQLite database and the storage folder on first start.

## Checks before a release

```bash
cd backend && python -m pytest
cd frontend && npx tsc -b && npx oxlint src && npm run build
npm audit --omit=dev
pip-audit -r backend/requirements.txt
```

## Deploying

A simple setup is the frontend on Vercel and the backend on Render or Railway. Whatever you use:

- Serve both over HTTPS. The API does not terminate TLS itself; put it behind the host's HTTPS proxy.
- Give the backend a persistent disk for `AKSHAR_STORAGE` and the SQLite file, or recordings and results disappear on redeploy.
- Set `CORS_ORIGINS` to the exact frontend origin and build the frontend with `VITE_API_BASE` pointing at the API.
- Configure the frontend host to send every path to `index.html` (single-page app), so links such as `/p/<token>` and `/teacher/child/3` load.
- Run one backend process. The sign-in rate limiter keeps its counts in memory, per process.
- Keep `AKSHAR_API_DOCS` off.

See [security.md](security.md) for the full operator checklist.

## Spike tools

`backend/spike/` holds the day-1 Whisper experiment. `make_tts_clips.py` generates test clips with Edge text-to-speech voices (needs `pip install edge-tts imageio-ffmpeg`), and `test_whisper.py` runs them through Groq and reports which deliberate errors survive transcription. Both use the same services as the app.
