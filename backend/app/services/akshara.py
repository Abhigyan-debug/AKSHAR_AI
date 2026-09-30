"""Devanagari akshara split (see docs/scoring.md).

An akshara is a consonant cluster (C + virama + ... + C, each C with an
optional nukta) plus an optional matra or final virama, plus anusvara /
chandrabindu / visarga; or an independent vowel plus those signs.

For error classification each akshara is also flattened into phoneme-like
units: every consonant in a cluster except the last carries HALANT (no vowel),
the last carries the akshara's vowel. Comparing units makes conjunct splits
(स्कूल -> सकूल) and simplifications (प्यास -> पास) visible.
"""

import re
import unicodedata
from dataclasses import dataclass

VIRAMA = "्"
NUKTA = "़"
HALANT = "halant"
INHERENT = "a"

_C = "क-हक़-य़ॸ-ॿ"
_V = "ऄ-औॠॡॲ-ॷ"
_M = "ऺऻा-ौॎॏॕ-ॗॢॣ"
_MODS = "ँंः"
_NASALS = "ँं"

_AKSHARA_RE = re.compile(
    rf"(?:[{_C}]{NUKTA}?{VIRAMA})*[{_C}]{NUKTA}?(?:{VIRAMA}|[{_M}])?[{_MODS}]*"
    rf"|[{_V}][{_MODS}]*"
    rf"|\S"
)
_CONSONANT_RE = re.compile(f"[{_C}]")

MATRA_VOWEL = {
    "ा": "aa", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu",
    "ृ": "ri", "ॄ": "rii", "ॅ": "ae", "ॆ": "e_short", "े": "e",
    "ै": "ai", "ॉ": "aw", "ॊ": "o_short", "ो": "o", "ौ": "au",
}
INDEPENDENT_VOWEL = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu", "ऋ": "ri",
    "ऍ": "ae", "ए": "e", "ऐ": "ai", "ऑ": "aw", "ओ": "o", "औ": "au",
}
_VOWEL_SIGN = {v: k for k, v in MATRA_VOWEL.items()}


def vowel_display(vowel: str, nasal: bool = False) -> str:
    """Human-readable vowel for error details: the matra sign, or a label."""
    if vowel == INHERENT:
        text = "(no matra)"
    elif vowel == HALANT:
        text = VIRAMA
    else:
        text = _VOWEL_SIGN.get(vowel, vowel)
    return text + ("ं" if nasal else "")


@dataclass(frozen=True)
class Akshara:
    text: str
    consonants: tuple[str, ...]  # each with its nukta, if any; () for vowels/other
    vowel: str                   # key from MATRA_VOWEL/INDEPENDENT_VOWEL, INHERENT or HALANT
    nasal: bool

    @property
    def is_conjunct(self) -> bool:
        return len(self.consonants) > 1


@dataclass(frozen=True)
class Unit:
    consonant: str | None
    vowel: str
    nasal: bool
    in_cluster: bool
    akshara_index: int

    @property
    def sound(self) -> tuple:
        return (self.consonant, self.vowel, self.nasal)

    @property
    def text(self) -> str:
        cons = self.consonant or ""
        if self.vowel == HALANT:
            return cons + VIRAMA
        if self.vowel == INHERENT:
            vowel = "" if cons else "अ"
        else:
            vowel = _VOWEL_SIGN.get(self.vowel, self.vowel) if cons else next(
                (k for k, v in INDEPENDENT_VOWEL.items() if v == self.vowel), self.vowel
            )
        return cons + vowel + ("ं" if self.nasal else "")


def split_aksharas(text: str) -> list[str]:
    return _AKSHARA_RE.findall(unicodedata.normalize("NFC", text))


def parse_akshara(chunk: str) -> Akshara:
    nasal = any(ch in _NASALS for ch in chunk)
    body = "".join(ch for ch in chunk if ch not in _MODS)
    if body and body[0] in INDEPENDENT_VOWEL:
        return Akshara(chunk, (), INDEPENDENT_VOWEL[body[0]], nasal)
    consonants: list[str] = []
    vowel = INHERENT
    for i, ch in enumerate(body):
        if _CONSONANT_RE.match(ch):
            consonants.append(ch)
        elif ch == NUKTA and consonants:
            consonants[-1] += NUKTA
        elif ch == VIRAMA and i == len(body) - 1:
            vowel = HALANT  # word-final dead consonant
        elif ch in MATRA_VOWEL:
            vowel = MATRA_VOWEL[ch]
    if not consonants:  # stray sign or non-Devanagari character
        return Akshara(chunk, (), chunk, nasal)
    return Akshara(chunk, tuple(consonants), vowel, nasal)


def aksharas(text: str) -> list[Akshara]:
    return [parse_akshara(chunk) for chunk in split_aksharas(text)]


def units(text: str) -> list[Unit]:
    out = []
    for idx, ak in enumerate(aksharas(text)):
        if not ak.consonants:
            out.append(Unit(None, ak.vowel, ak.nasal, False, idx))
            continue
        for cons in ak.consonants[:-1]:
            out.append(Unit(cons, HALANT, False, True, idx))
        out.append(Unit(ak.consonants[-1], ak.vowel, ak.nasal, ak.is_conjunct, idx))
    return out
