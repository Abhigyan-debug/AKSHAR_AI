"""Day-1 Whisper spike (see "Why the scoring looks like this" in docs/scoring.md).

Question: does Groq Whisper keep a reader's deliberate errors, or does it
"auto-correct" them into the expected word? And can we tell, from Whisper's
own confidence, which transcripts are safe to auto-score?

Normalization, timing, the confidence gate and the rule classifier come from
app/services, so this script checks the real pipeline code against Whisper.

Each row in clips.csv describes one recording in clips/:
  expected           - the target text shown to the reader
  spoken             - what the reader actually said (== expected for control clips)
  error_type
  pause_s            - for long_pause clips, how long the reader stayed silent
  accepted_variants  - other spellings of `expected` that count as correct, "|"-separated
  scoring            - "auto" or "manual" (teacher live-taps; still transcribed)

The target text is never sent as the Whisper `prompt`, because it would bias
the model toward the correct reading.

Usage (from the project root):
  python backend/spike/test_whisper.py
  python backend/spike/test_whisper.py --only hi_05 en_04
  python backend/spike/test_whisper.py --models whisper-large-v3 whisper-large-v3-turbo
"""

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from dotenv import load_dotenv

SPIKE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SPIKE_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import thresholds  # noqa: E402
from app.services.classify_rules import classify_item  # noqa: E402
from app.services.confidence import assess_confidence, item_status  # noqa: E402
from app.services.normalize import compact, is_single_word, matches, normalize  # noqa: E402
from app.services.timing import analyse_timing  # noqa: E402
from app.services.transcribe import transcribe_file  # noqa: E402

CLIPS_DIR = SPIKE_DIR / "clips"
MANIFEST = SPIKE_DIR / "clips.csv"
RESULTS_DIR = SPIKE_DIR / "results"
AUDIO_EXTS = (".wav", ".m4a", ".mp3", ".webm", ".ogg", ".flac", ".mp4", ".mpeg", ".mpga")


@dataclass
class Clip:
    clip_id: str
    lang: str
    expected: str
    spoken: str
    error_type: str
    pause_s: float | None
    notes: str
    scoring: str
    accepted_variants: list[str] = field(default_factory=list)
    audio: Path | None = None

    def as_item(self) -> dict:
        """The clip as a test item, so the rule classifier can run on it."""
        lexical = self.error_type == "lexicalization"
        return {
            "id": self.clip_id,
            "section": "D" if not is_single_word(self.expected) else "C",
            "text": self.expected,
            "is_nonword": lexical,
            "near_real": self.spoken if lexical else None,
            "accepted_variants": self.accepted_variants,
            "scoring": self.scoring,
        }


def load_clips(only: list[str] | None) -> list[Clip]:
    clips = []
    with open(MANIFEST, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            clip_id = row["clip_id"].strip()
            if only and not any(clip_id.startswith(p) for p in only):
                continue
            audio = next(
                (CLIPS_DIR / f"{clip_id}{ext}" for ext in AUDIO_EXTS if (CLIPS_DIR / f"{clip_id}{ext}").exists()),
                None,
            )
            pause = (row.get("pause_s") or "").strip()
            variants = [v.strip() for v in (row.get("accepted_variants") or "").split("|") if v.strip()]
            clips.append(
                Clip(
                    clip_id=clip_id,
                    lang=row["lang"].strip(),
                    expected=row["expected"].strip(),
                    spoken=row["spoken"].strip(),
                    error_type=row["error_type"].strip(),
                    pause_s=float(pause) if pause else None,
                    notes=(row.get("notes") or "").strip(),
                    scoring=(row.get("scoring") or "auto").strip() or "auto",
                    accepted_variants=variants,
                    audio=audio,
                )
            )
    return clips


def judge(clip: Clip, heard: str, hesitation: bool, has_words: bool) -> str:
    """What the transcript says happened, compared with what was actually spoken."""
    if clip.error_type == "none":
        return "OK" if matches(heard, clip.expected, clip.accepted_variants) else "MISHEARD"
    if clip.error_type == "long_pause":
        if not has_words:
            return "NO_TIMESTAMPS"
        return "PAUSE_FOUND" if hesitation else "PAUSE_MISSED"
    if matches(heard, clip.spoken):
        return "KEPT"
    if matches(heard, clip.expected, clip.accepted_variants):
        return "AUTOCORRECTED"
    h = compact(heard)
    closer = "spoken" if SequenceMatcher(None, h, compact(clip.spoken)).ratio() >= SequenceMatcher(
        None, h, compact(clip.expected)
    ).ratio() else "expected"
    return f"OTHER (closer to {closer})"


def is_right(verdict: str) -> bool:
    return verdict in ("OK", "KEPT", "PAUSE_FOUND")


def print_clip(clip, heard, verdict, status, timing, conf, rule_labels) -> None:
    print(f"\n[{clip.clip_id}] {clip.error_type} ({clip.lang})")
    print(f"  expected : {clip.expected}" + (f"  (also accepted: {', '.join(clip.accepted_variants)})" if clip.accepted_variants else ""))
    if clip.spoken != clip.expected:
        print(f"  spoken   : {clip.spoken}")
    print(f"  heard    : {heard}")
    print(f"  verdict  : {verdict}")
    extra = ""
    if status == "teacher_verify":
        extra = f"  <- {', '.join(conf.reasons)}"
    elif status == "manual":
        extra = "  <- teacher live-taps; transcript kept as evidence"
    print(f"  status   : {status}{extra}")
    if rule_labels:
        print(f"  rules    : {rule_labels}")
    if conf.avg_logprob is not None:
        print(f"  conf     : avg_logprob {conf.avg_logprob:.2f}, no_speech_prob {conf.no_speech_prob:.2f}")
    if timing.start_latency_s is not None:
        flags = [kind.upper() for kind, _ in timing.flags()]
        print(
            f"  timing   : start {timing.start_latency_s:.2f}s, longest gap {timing.max_gap_s:.2f}s, "
            f"longest word {timing.max_word_s:.2f}s" + (f"  [{' '.join(flags)}]" if flags else "")
        )
    else:
        print("  timing   : no word timestamps returned")
    if clip.lang == "hi" and heard.strip() and not any("ऀ" <= ch <= "ॿ" for ch in heard):
        print("  warning  : Hindi clip transcribed without Devanagari")


def summarize(model: str, rows: list[dict]) -> None:
    print(f"\n=== {model} ===")
    auto = [r for r in rows if r["status"] == "auto"]
    verify = [r for r in rows if r["status"] == "teacher_verify"]
    manual = [r for r in rows if r["status"] == "manual"]
    n = len(rows)

    wrong_auto = [r for r in auto if not is_right(r["verdict"])]
    print(f"  auto-scored               : {len(auto)}/{n} ({100 * len(auto) / n:.0f}%)  right {len(auto) - len(wrong_auto)}, wrong {len(wrong_auto)}")
    for r in wrong_auto:
        print(f"    WRONG AUTO-SCORE        : {r['clip_id']} heard '{r['heard']}' ({r['verdict']})")
    caught = sum(1 for r in verify if not is_right(r["verdict"]))
    print(f"  sent to teacher verify    : {len(verify)}/{n} ({100 * len(verify) / n:.0f}%)  would have been wrong: {caught}")
    print(f"  live tap (manual)         : {len(manual)}/{n} ({100 * len(manual) / n:.0f}%)")

    text_errors = [r for r in rows if r["error_type"] not in ("none", "long_pause")]
    if text_errors:
        kept = sum(1 for r in text_errors if r["verdict"] == "KEPT")
        auto_c = sum(1 for r in text_errors if r["verdict"] == "AUTOCORRECTED")
        print(f"  deliberate errors kept    : {kept}/{len(text_errors)}  (auto-corrected: {auto_c}; ignores gating)")
        labelled = [r for r in text_errors if r["verdict"] == "KEPT" and r["status"] == "auto"]
        if labelled:
            ok = sum(1 for r in labelled if r["error_type"] in r["rules"])
            print(f"  rules labelled them right : {ok}/{len(labelled)}  (auto-scored, kept errors)")
    pauses = [r for r in rows if r["error_type"] == "long_pause"]
    if pauses:
        print(f"  long pauses detected      : {sum(1 for r in pauses if r['verdict'] == 'PAUSE_FOUND')}/{len(pauses)}")
    others = [r for r in rows if r["error_type"] != "long_pause"]
    false_hes = [r["clip_id"] for r in others if r["hesitation"]]
    print(f"  hesitation false alarms   : {len(false_hes)}/{len(others)}" + (f"  {false_hes}" if false_hes else ""))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(BACKEND_DIR / ".env")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=[os.getenv("GROQ_STT_MODEL", "whisper-large-v3")])
    parser.add_argument("--only", nargs="+", help="clip_id prefixes to run")
    args = parser.parse_args()

    if not os.getenv("GROQ_API_KEY"):
        sys.exit("GROQ_API_KEY is not set. Copy .env.example to .env and fill it in.")

    clips = load_clips(args.only)
    missing = [c.clip_id for c in clips if c.audio is None]
    clips = [c for c in clips if c.audio is not None]
    if missing:
        print(f"Skipping {len(missing)} clip(s) with no audio in {CLIPS_DIR}: {', '.join(missing)}")
    if not clips:
        sys.exit("No clips to run.")

    cfg = thresholds()
    run_dir = RESULTS_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_rows = []

    for model in args.models:
        print(f"\n##### {model} #####")
        (run_dir / model).mkdir(parents=True, exist_ok=True)
        model_rows = []
        for clip in clips:
            try:
                tr = transcribe_file(clip.audio, clip.lang, model=model)
            except Exception as exc:  # keep going; one bad clip shouldn't kill the spike
                print(f"\n[{clip.clip_id}] ERROR: {exc}")
                continue
            (run_dir / model / f"{clip.clip_id}.json").write_text(
                json.dumps(tr.raw, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            timing = analyse_timing(tr.words, None, cfg, multi_word=not is_single_word(clip.expected))
            conf = assess_confidence(tr.segments, tr.text, cfg)
            status = item_status(clip.scoring, conf)
            verdict = judge(clip, tr.text, timing.hesitation, bool(tr.words))
            rules = classify_item(clip.as_item(), tr.text, clip.lang)
            rule_labels = ", ".join(f"{e.type}({e.detail})" for e in rules.errors)
            print_clip(clip, tr.text, verdict, status, timing, conf, rule_labels)
            model_rows.append(
                {
                    "model": model,
                    "clip_id": clip.clip_id,
                    "lang": clip.lang,
                    "error_type": clip.error_type,
                    "expected": clip.expected,
                    "spoken": clip.spoken,
                    "heard": tr.text,
                    "verdict": verdict,
                    "status": status,
                    "rules": rule_labels,
                    "avg_logprob": conf.avg_logprob,
                    "no_speech_prob": conf.no_speech_prob,
                    "start_latency_s": timing.start_latency_s,
                    "max_gap_s": timing.max_gap_s,
                    "max_word_s": timing.max_word_s,
                    "hesitation": timing.hesitation,
                }
            )
        summary_rows.extend(model_rows)
        summarize(model, model_rows)

    if summary_rows:
        out = run_dir / "summary.csv"
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_rows)
        print(f"\nRaw responses and summary.csv saved to {run_dir}")


if __name__ == "__main__":
    main()
