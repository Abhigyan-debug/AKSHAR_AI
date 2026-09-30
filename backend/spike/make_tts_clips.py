"""Generate the spike clips in clips.csv with text-to-speech, for when nobody
can record them. Uses Microsoft Edge neural voices (needs internet) and the
ffmpeg bundled with imageio-ffmpeg.

Each clip speaks the `spoken` column (the deliberate error), with ~0.8 s of
silence before and after. long_pause clips get real silence inserted after the
`pause_after` word.

TTS is clean adult speech, so this is a best-case test for Whisper: if errors
get auto-corrected here, they will be with children too. Re-check with a real
human recording before trusting a good result.

Usage (from the project root):
  pip install edge-tts imageio-ffmpeg
  python backend/spike/make_tts_clips.py              # skips clips that already exist
  python backend/spike/make_tts_clips.py --overwrite
"""

import argparse
import asyncio
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

import edge_tts
import imageio_ffmpeg

SPIKE_DIR = Path(__file__).resolve().parent
CLIPS_DIR = SPIKE_DIR / "clips"
MANIFEST = SPIKE_DIR / "clips.csv"
AUDIO_EXTS = (".wav", ".m4a", ".mp3", ".webm", ".ogg", ".flac", ".mp4", ".mpeg", ".mpga")

# Two voices per language, alternated so the clips aren't all one speaker.
VOICES = {
    "hi": ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"],
    "en": ["en-IN-NeerjaNeural", "en-IN-PrabhatNeural"],
}
RATE = "-15%"  # a bit slower, closer to a child reading aloud
EDGE_PAD_S = 0.8
SAMPLE_RATE = 24000  # Edge TTS mp3 output rate


def split_for_pause(text: str, after_word: str) -> list[str]:
    words = text.split()
    if after_word not in words:
        return [text]
    i = words.index(after_word) + 1
    return [" ".join(words[:i]), " ".join(words[i:])]


async def speak(text: str, voice: str, path: Path) -> None:
    await edge_tts.Communicate(text, voice, rate=RATE).save(str(path))


def join_with_silence(parts: list[Path], gaps: list[float], out: Path) -> None:
    """Concatenate: pad, part0, gap0, part1, ..., pad -> 16 kHz mono wav."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    silences = [EDGE_PAD_S, *gaps, EDGE_PAD_S]
    cmd = [ffmpeg, "-y", "-loglevel", "error"]
    labels = []
    idx = 0
    for i, silence in enumerate(silences):
        cmd += ["-f", "lavfi", "-t", f"{silence}", "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono"]
        labels.append(idx)
        idx += 1
        if i < len(parts):
            cmd += ["-i", str(parts[i])]
            labels.append(idx)
            idx += 1
    norm = "aresample={r},aformat=sample_fmts=fltp:channel_layouts=mono".format(r=SAMPLE_RATE)
    chains = [f"[{n}:a]{norm}[a{n}]" for n in labels]
    concat = "".join(f"[a{n}]" for n in labels) + f"concat=n={len(labels)}:v=0:a=1[out]"
    cmd += ["-filter_complex", ";".join(chains + [concat]), "-map", "[out]", "-ar", "16000", "-ac", "1", str(out)]
    subprocess.run(cmd, check=True)


async def make_clip(row: dict, voice: str, tmp: Path) -> Path:
    clip_id = row["clip_id"]
    pause_after = row.get("pause_after", "").strip()
    texts = split_for_pause(row["spoken"], pause_after) if pause_after else [row["spoken"]]
    gaps = [float(row["pause_s"] or 3)] * (len(texts) - 1)
    parts = []
    for i, text in enumerate(texts):
        part = tmp / f"{clip_id}_{i}.mp3"
        await speak(text, voice, part)
        parts.append(part)
    out = CLIPS_DIR / f"{clip_id}.wav"
    join_with_silence(parts, gaps, out)
    return out


async def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--overwrite", action="store_true", help="replace clips that already exist")
    args = parser.parse_args()

    CLIPS_DIR.mkdir(exist_ok=True)
    with open(MANIFEST, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    counters = {lang: 0 for lang in VOICES}
    with tempfile.TemporaryDirectory() as tmp:
        for row in rows:
            clip_id, lang = row["clip_id"], row["lang"]
            voice = VOICES[lang][counters[lang] % len(VOICES[lang])]
            counters[lang] += 1
            existing = [p for ext in AUDIO_EXTS if (p := CLIPS_DIR / f"{clip_id}{ext}").exists()]
            if existing and not args.overwrite:
                print(f"skip   {clip_id} (exists: {existing[0].name})")
                continue
            out = await make_clip(row, voice, Path(tmp))
            print(f"made   {out.name:<28} {voice:<22} \"{row['spoken']}\"")


if __name__ == "__main__":
    asyncio.run(main())
