"""Small, deterministic language helpers for the rules.

English uses spaCy `en_core_web_sm` (MIT, pinned in pyproject). Hindi and Italian use rules only:
spaCy's Italian models are not under a licence we accept for production, and there is no Hindi model,
so `docs/rules.md` lists which rules are weaker for hi/it.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any

from accesscast.errors import UnknownLanguageError

_WORD_RE = re.compile(r"[\wऀ-ॿ][\wऀ-ॿ'’\-]*", re.UNICODE)
_SENT_RE = re.compile(r"(?<=[.!?।])\s+")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-zÀ-ÿ]")

STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset(
        [
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "if",
            "then",
            "of",
            "to",
            "in",
            "on",
            "at",
            "by",
            "for",
            "with",
            "from",
            "up",
            "down",
            "out",
            "over",
            "under",
            "into",
            "onto",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "am",
            "do",
            "does",
            "did",
            "has",
            "have",
            "had",
            "it",
            "its",
            "this",
            "that",
            "these",
            "those",
            "there",
            "here",
            "he",
            "she",
            "they",
            "them",
            "his",
            "her",
            "their",
            "him",
            "we",
            "you",
            "i",
            "me",
            "my",
            "our",
            "your",
            "as",
            "so",
            "not",
            "no",
            "than",
            "too",
            "very",
            "can",
            "will",
            "just",
            "also",
            "while",
            "which",
            "who",
            "whom",
            "whose",
            "what",
            "when",
            "where",
            "why",
            "how",
            "all",
            "any",
            "each",
            "some",
            "one",
            "two",
        ]
    ),
    "it": frozenset(
        [
            "il",
            "lo",
            "la",
            "i",
            "gli",
            "le",
            "un",
            "uno",
            "una",
            "e",
            "ed",
            "o",
            "ma",
            "se",
            "di",
            "a",
            "da",
            "in",
            "con",
            "su",
            "per",
            "tra",
            "fra",
            "del",
            "dello",
            "della",
            "dei",
            "degli",
            "delle",
            "al",
            "allo",
            "alla",
            "ai",
            "agli",
            "alle",
            "dal",
            "dalla",
            "nel",
            "nella",
            "sul",
            "sulla",
            "è",
            "sono",
            "era",
            "essere",
            "ha",
            "hanno",
            "che",
            "chi",
            "non",
            "si",
            "ci",
            "ne",
            "mi",
            "ti",
            "lui",
            "lei",
            "loro",
            "questo",
            "questa",
            "quello",
            "quella",
            "come",
            "anche",
            "più",
            "molto",
        ]
    ),
    "hi": frozenset(
        [
            "का",
            "की",
            "के",
            "को",
            "में",
            "से",
            "पर",
            "और",
            "या",
            "है",
            "हैं",
            "था",
            "थी",
            "थे",
            "एक",
            "यह",
            "वह",
            "ये",
            "वे",
            "भी",
            "तो",
            "ही",
            "ने",
            "कि",
            "जो",
            "इस",
            "उस",
            "इन",
            "उन",
            "नहीं",
            "हो",
            "रहा",
            "रही",
            "रहे",
            "गया",
            "गई",
            "कर",
            "करता",
            "करती",
            "करते",
        ]
    ),
}

NEGATIONS: dict[str, frozenset[str]] = {
    "en": frozenset(
        {
            "not",
            "never",
            "no",
            "don't",
            "dont",
            "doesn't",
            "didn't",
            "isn't",
            "aren't",
            "wasn't",
            "weren't",
            "won't",
            "can't",
            "cannot",
            "shouldn't",
            "mustn't",
            "n't",
            "nobody",
            "nothing",
            "none",
            "neither",
            "nor",
            "without",
        }
    ),
    "hi": frozenset({"नहीं", "मत", "न", "कभी नहीं", "बिना"}),
    "it": frozenset({"non", "mai", "nessuno", "niente", "nulla", "né", "senza", "nemmeno", "neanche"}),
}

NUMBER_WORDS: dict[str, dict[str, int]] = {
    "en": {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
        "hundred": 100,
        "thousand": 1000,
        "once": 1,
        "twice": 2,
    },
    "it": {
        "zero": 0,
        "uno": 1,
        "una": 1,
        "due": 2,
        "tre": 3,
        "quattro": 4,
        "cinque": 5,
        "sei": 6,
        "sette": 7,
        "otto": 8,
        "nove": 9,
        "dieci": 10,
        "undici": 11,
        "dodici": 12,
        "venti": 20,
        "trenta": 30,
        "cento": 100,
        "mille": 1000,
    },
    "hi": {
        "शून्य": 0,
        "एक": 1,
        "दो": 2,
        "तीन": 3,
        "चार": 4,
        "पांच": 5,
        "पाँच": 5,
        "छह": 6,
        "सात": 7,
        "आठ": 8,
        "नौ": 9,
        "दस": 10,
        "बीस": 20,
        "सौ": 100,
        "हज़ार": 1000,
        "हजार": 1000,
    },
}
_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def check_lang(lang: str) -> str:
    if lang not in STOPWORDS:
        raise UnknownLanguageError(f"unsupported language {lang!r}; no fallback to English")
    return lang


def normalise(text: str) -> str:
    return unicodedata.normalize("NFC", text).replace("’", "'")


def tokens(text: str) -> list[str]:
    return _WORD_RE.findall(normalise(text))


def lower_tokens(text: str) -> list[str]:
    return [t.lower() for t in tokens(text)]


def sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT_RE.split(normalise(text).strip())]
    return [p for p in parts if p]


def word_count(text: str) -> int:
    return len(tokens(text))


def devanagari_fraction(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if _DEVANAGARI.match(c)) / len(letters)


def latin_fraction(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if _LATIN.match(c)) / len(letters)


@lru_cache(maxsize=1)
def _spacy_en() -> Any:
    import spacy

    return spacy.load("en_core_web_sm", disable=["parser"])


@lru_cache(maxsize=4096)
def _doc_en(text: str) -> Any:
    return _spacy_en()(text)


def _simple_lemma(tok: str) -> str:
    t = tok.lower()
    for suf, rep in (("ies", "y"), ("sses", "ss"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if len(t) > len(suf) + 2 and t.endswith(suf):
            return t[: -len(suf)] + rep
    return t


def lemmas(text: str, lang: str) -> list[str]:
    check_lang(lang)
    if lang == "en":
        return [t.lemma_.lower() for t in _doc_en(normalise(text)) if not t.is_punct and not t.is_space]
    return [_simple_lemma(t) for t in tokens(text)]


def content_nouns(text: str, lang: str) -> list[str]:
    """Lemmas of nouns (en via spaCy); for hi/it: non-stopword tokens longer than 2 characters."""
    check_lang(lang)
    if lang == "en":
        return [t.lemma_.lower() for t in _doc_en(normalise(text)) if t.pos_ in ("NOUN",) and len(t.text) > 1]
    sw = STOPWORDS[lang]
    return [_simple_lemma(t) for t in tokens(text) if t.lower() not in sw and len(t) > 2]


_COMMON_CAPS_EN = frozenset({"I", "On", "A", "An", "The", "Screen", "Sign", "Text", "Title", "Slide"})


def _name_token(t: str) -> str:
    """Strip punctuation around a token; empty if it has no letters (spaCy tags "+" or "C." as PROPN)."""
    t = re.sub(r"^[^\w\u0900-\u097F]+|[^\w\u0900-\u097F]+$", "", t)
    return t if any(c.isalpha() for c in t) else ""


def proper_nouns(text: str, lang: str) -> list[str]:
    """Candidate names. en: spaCy PROPN/PERSON; hi/it: capitalised (Latin) tokens not sentence-initial.
    Tokens are stripped of surrounding punctuation; tokens with no letters are never names."""
    check_lang(lang)
    out: list[str] = []

    def add(tok: str) -> None:
        t = _name_token(tok)
        if t and t not in out and t not in _COMMON_CAPS_EN:
            out.append(t)

    if lang == "en":
        doc = _doc_en(normalise(text))
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                for part in ent.text.split():
                    add(part)
        for t in doc:
            if t.pos_ == "PROPN":
                add(t.text)
        return out
    for sent in sentences(text):
        toks = tokens(sent)
        for t in toks[1:]:
            if t[:1].isupper():
                add(t)
    return out


def finite_past_verbs(text: str) -> list[str]:
    """English only: finite verbs in the past tense (spaCy morphology)."""
    doc = _doc_en(normalise(text))
    return [
        t.text
        for t in doc
        if t.pos_ in ("VERB", "AUX") and "Past" in t.morph.get("Tense") and "Fin" in t.morph.get("VerbForm")
    ]


def numbers(text: str, lang: str) -> list[str]:
    """Multiset of numbers as normalised strings (digits and number words)."""
    check_lang(lang)
    t = normalise(text).translate(_DEVANAGARI_DIGITS)
    out = [n.replace(",", ".") for n in _NUM_RE.findall(t)]
    words = NUMBER_WORDS.get(lang, {})
    for tok in lower_tokens(t):
        if tok in words:
            out.append(str(words[tok]))
    return sorted(out)


def negation_count(text: str, lang: str) -> int:
    check_lang(lang)
    neg = NEGATIONS[lang]
    toks = lower_tokens(text)
    n = sum(1 for t in toks if t in neg or t.endswith("n't"))
    if lang == "hi" and "कभी नहीं" in text:
        n -= 1  # counted once, not twice
    return n


def ngrams(seq: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(seq[i : i + n]) for i in range(len(seq) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
