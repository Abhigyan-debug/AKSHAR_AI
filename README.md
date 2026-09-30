# Akshar

Akshar is a reading-aloud screener for Indian primary schools. A child reads letters, words, made-up words and a short story aloud in Hindi and in English on a phone. Akshar transcribes each clip, sorts the mistakes into the error patterns linked to reading difficulty, and compares the two languages. The teacher gets a report with the audio evidence, and the parent gets a short explanation in Hindi that the phone can read aloud.

Akshar is a screener, not a diagnosis. It never says a child is dyslexic. It says who may need reading support, English practice or a specialist check, and every cut-off it uses is illustrative and not clinically validated.

Built for Round 1 of the AI with Education hackathon.

## How it works

1. The teacher signs in with the school PIN, picks a child code (no names) and hands over the phone.
2. The child reads one item at a time. Letters and sound-game answers are scored by the teacher with a small tap strip at the bottom of the screen; everything else is recorded and uploaded in the background.
3. Groq Whisper (`whisper-large-v3`) transcribes each clip. Rule-based code compares the transcript with the target, akshara by akshara, and labels errors such as matra confusions, aspiration errors, look-alike letter swaps, b/d reversals and made-up words read as real words. Items the speech model was unsure about go to a verify queue instead of into the result.
4. A deterministic risk engine combines both languages into one of five results: low risk, English exposure gap, needs Hindi reading support, needs reading support, or needs specialist check.
5. An LLM (`openai/gpt-oss-120b` on Groq) turns those facts into a short teacher summary in English and a parent summary with three home tips in Hindi. It never decides the result.
6. Six five-minute practice games, ordered by the child's own error pattern, give daily practice at home and in class with an adult alongside.

The design decisions and the evidence behind them are in the [docs](docs/) folder.

## Quick start

You need Python 3.10 or newer, Node 22 and a Groq API key.

```bash
# 1. Configuration
cp .env.example .env
# Fill in GROQ_API_KEY, TEACHER_PIN (6+ characters) and AKSHAR_SECRET:
python -c "import secrets; print(secrets.token_urlsafe(48))"

# 2. Backend (http://localhost:8000)
cd backend
pip install -r requirements.txt
uvicorn app.main:create_app --factory --reload

# 3. Frontend (http://localhost:5173), in a second terminal
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, choose "Teacher sign in" and enter the PIN from `.env`. The backend refuses to start without `TEACHER_PIN` and `AKSHAR_SECRET`.

## Tests

```bash
cd backend && python -m pytest        # 197 tests: rules, risk, LLM (faked), API, security, practice content
cd frontend && npx tsc -b && npx oxlint src && npm run build
```

The backend tests never call Groq. Timing and confidence tests use real `whisper-large-v3` responses saved from the spike in `backend/tests/fixtures/`.

## Project layout

```
backend/
  app/main.py           FastAPI app factory, security headers, routes under /api
  app/security.py       teacher PIN sign-in, signed tokens, upload checks
  app/routes/           auth, children, tests, sessions, reports, parent
  app/services/         transcribe, normalize, akshara, align, classify_rules,
                        confidence, timing, analyse, risk, llm, store, cache
  config/thresholds.json  all cut-offs and weights (provisional)
  data/tests/{hi,en}.json the original test items
  data/practice.json    practice game content (never overlaps the test)
  spike/                the day-1 Whisper experiment and its clips
  tests/                pytest suite
frontend/
  src/pages/            Home, Login, ChildSetup, ChildRun, TeacherDashboard, ChildReport, Parent, Practice
  src/practice/         the practice games
  src/components/, src/lib/
docs/                   setup, architecture, scoring, API, security, test content, design, practice
PRODUCT.md              product context: users, purpose, principles, evidence on hand
```

## Documentation

- [Setup and deployment](docs/setup.md)
- [Architecture](docs/architecture.md)
- [Scoring: error rules, risk logic and the LLM](docs/scoring.md)
- [API reference](docs/api.md)
- [Security and privacy](docs/security.md)
- [Writing test content](docs/test-content.md)
- [Design system and motion](docs/design.md)
- [Practice games and the research behind them](docs/practice.md)

## Known limits

- Every threshold was calibrated on synthetic (text-to-speech) voices. Tune them on real children before relying on any result.
- Whisper sometimes mishears a correct Hindi word with high confidence. In testing, खेत came back as कित and पैसा as बैसा, and both were scored as errors. Teachers can override any item.
- English results count only after a teacher confirms them, which means roughly 20 taps per child in the verify queue.
- One shared PIN covers all teachers. There are no per-teacher accounts or audit log yet.
- Microphone capture was tested in a desktop browser with a simulated input. Test on the phones your school will use, including whether they have a Hindi voice for the parent page.
