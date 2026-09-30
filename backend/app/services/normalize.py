"""Text normalization applied before any comparison (see docs/scoring.md).

The same function runs on the target, each accepted variant and the
transcript, so spelling variants that sound the same compare equal while real
reading errors (matra, aspiration, akshara swaps) stay distinct.
"""

import re
import unicodedata

VIRAMA = "्"
NUKTA = "़"
ANUSVARA = "ं"
CHANDRABINDU = "ँ"
_CONSONANT = "[क-ह]"
_NASAL_CONSONANTS = "ङञणनम"
_KEEP_NUKTA_ON = "डढ"  # ड़/ढ़ are different sounds, not spelling variants


def normalize(text: str) -> str:
    """NFC, casefold, then for Devanagari:
      - drop nukta (ज़ -> ज, फ़ -> फ), except on ड़/ढ़
      - chandrabindu -> anusvara (हँस -> हंस)
      - nasal consonant + virama before a consonant -> anusvara (हिन्दी -> हिंदी)
      - collapse gemination (गुब्बारा -> गुबारा)
    Zero-width joiners are dropped; other punctuation (incl. danda) becomes a
    space; whitespace is collapsed.
    """
    # NFC also decomposes precomposed nukta letters (U+0958-095F) into base + nukta.
    text = unicodedata.normalize("NFC", text).casefold()
    text = "".join(
        ch for i, ch in enumerate(text) if not (ch == NUKTA and (i == 0 or text[i - 1] not in _KEEP_NUKTA_ON))
    )
    text = text.replace(CHANDRABINDU, ANUSVARA)
    text = re.sub(f"[{_NASAL_CONSONANTS}]{VIRAMA}(?={_CONSONANT})", ANUSVARA, text)
    text = re.sub(f"({_CONSONANT}){VIRAMA}\\1", r"\1", text)
    kept = []
    for ch in text:
        category = unicodedata.category(ch)
        if category == "Cf":
            continue
        kept.append(ch if category[0] in "LMN" else " ")
    return " ".join("".join(kept).split())


def compact(text: str) -> str:
    """Normalized text with spaces removed."""
    return normalize(text).replace(" ", "")


def is_single_word(text: str) -> bool:
    return len(normalize(text).split()) <= 1


def matches(heard: str, target: str, accepted_variants=()) -> bool:
    """True if `heard` is the target or one of its accepted variants.

    Single-word items ignore spaces, because Whisper may split a nonword into
    real words ("mistop" -> "mis top").
    """
    forms = (target, *accepted_variants)
    if is_single_word(target):
        h = compact(heard)
        return bool(h) and any(h == compact(f) for f in forms)
    h = normalize(heard)
    return bool(h) and any(h == normalize(f) for f in forms)
