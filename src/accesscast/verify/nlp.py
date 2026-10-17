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
    # Spanish and French: common function words (ours, for the token-based checks on these languages)
    "es": frozenset(
        ["el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "pero", "que", "de", "del", "a", "al", "en", "con", "por", "para", "es", "son", "está", "están", "fue", "ser", "se", "su", "sus", "lo", "le", "les", "me", "te", "nos", "este", "esta", "estos", "estas", "ese", "esa", "eso", "aquí", "allí", "muy", "más", "como", "cuando"]
    ),
    "fr": frozenset(
        ["le", "la", "les", "un", "une", "des", "et", "ou", "mais", "que", "qui", "de", "du", "au", "aux", "en", "dans", "avec", "par", "pour", "est", "sont", "été", "être", "se", "sa", "son", "ses", "ce", "cet", "cette", "ces", "il", "elle", "ils", "elles", "on", "nous", "vous", "très", "plus", "comme", "quand", "ici", "là"]
    ),
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
    "es": frozenset(
        {"no", "nunca", "jamás", "nadie", "nada", "ni", "sin", "tampoco", "ningún", "ninguna", "ninguno"}
    ),
    "fr": frozenset(
        {"pas", "jamais", "rien", "aucun", "aucune", "sans", "ni", "nulle"}
    ),  # "ne" pairs with these
}

NUMBER_WORDS: dict[str, dict[str, int]] = {
    "es": {
        "cero": 0,
        "dos": 2,
        "tres": 3,
        "cuatro": 4,
        "cinco": 5,
        "seis": 6,
        "siete": 7,
        "ocho": 8,
        "nueve": 9,
        "diez": 10,
        "once": 11,
        "doce": 12,
        "veinte": 20,
        "treinta": 30,
        "cuarenta": 40,
        "cincuenta": 50,
        "sesenta": 60,
        "setenta": 70,
        "ochenta": 80,
        "noventa": 90,
    },
    "fr": {  # "neuf" (nine / new) is left out: it would read a number into ordinary sentences
        "zéro": 0,
        "deux": 2,
        "trois": 3,
        "quatre": 4,
        "cinq": 5,
        "six": 6,
        "sept": 7,
        "huit": 8,
        "dix": 10,
        "onze": 11,
        "douze": 12,
        "vingt": 20,
        "trente": 30,
        "quarante": 40,
        "cinquante": 50,
        "soixante": 60,
    },
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


_COMMON_CAPS_EN = frozenset(
    {
        "I",
        "On",
        "A",
        "An",
        "The",
        "Screen",
        "Sign",
        "Text",
        "Title",
        "Slide",
        # celestial bodies are written capitalised but are not people's names (dev: AD009 and
        # CC009 flagged "Moon", "Earth"; docs/incidents.md 2026-10-16)
        "Sun",
        "Moon",
        "Earth",
        "Mercury",
        "Venus",
        "Mars",
        "Jupiter",
        "Saturn",
        "Uranus",
        "Neptune",
        "Pluto",
    }
)


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


_SCALES: dict[str, dict[str, int]] = {
    "es": {"cien": 100, "mil": 1_000, "millón": 1_000_000, "millones": 1_000_000},
    "fr": {
        "cent": 100,
        "mille": 1_000,
        "million": 1_000_000,
        "millions": 1_000_000,
        "milliard": 1_000_000_000,
        "milliards": 1_000_000_000,
    },
    "en": {"hundred": 100, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000},
    "it": {
        "cento": 100,
        "mille": 1_000,
        "mila": 1_000,
        "milione": 1_000_000,
        "milioni": 1_000_000,
        "miliardo": 1_000_000_000,
        "miliardi": 1_000_000_000,
    },
    "hi": {"सौ": 100, "हज़ार": 1_000, "हजार": 1_000, "लाख": 100_000, "करोड़": 10_000_000, "करोड": 10_000_000},
}
_NUM_TOKEN_RE = re.compile(r"\d+(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?|[^\s\d.,;:!?\"'()\[\]]+")


def _num_value(tok: str) -> float:
    """'34,000' / '34.000' → 34000; '2.5' / '2,5' → 2.5 (a separator before exactly 3 digits is thousands)."""
    if re.fullmatch(r"\d+(?:[.,]\d{3})+", tok):
        return float(re.sub(r"[.,]", "", tok))
    return float(tok.replace(",", "."))


def numbers(text: str, lang: str) -> list[str]:
    """Multiset of numbers as normalised values: digits, number words, and scale words (thousand, million, mille,
    milioni, हज़ार, लाख, करोड़) applied to the number before them, so "a million" and "10 लाख" are both 1000000.
    The value 1 is never compared: "one" is also the article in Italian (un, una) and Hindi (एक), and a
    translation may write "one" as "1" (dev false positives, docs/incidents.md 2026-10-16)."""
    check_lang(lang)
    t = normalise(text).translate(_DEVANAGARI_DIGITS)
    t = re.sub(r"(\d)\s+([.,]\d{3})\b", r"\1\2", t)  # ASR writes "34 ,000"
    t = re.sub(
        r"(?<=\d)[ \u00a0\u202f](?=\d{3}(?!\d))", "", t
    )  # French writes 10 000 (space as thousands sign)
    words = NUMBER_WORDS.get(lang, {})
    scales = _SCALES.get(lang, {})
    vals: list[float] = []
    prev_was_number = False
    for tok in _NUM_TOKEN_RE.findall(t):
        low = tok.lower()
        if tok[0].isdigit():
            vals.append(_num_value(tok))
            prev_was_number = True
        elif low in scales:
            if prev_was_number and vals:
                vals[-1] *= scales[low]
            else:
                vals.append(float(scales[low]))  # "a million", "हज़ारों" style without a count
            prev_was_number = True
        elif low in words:
            vals.append(float(words[low]))
            prev_was_number = True
        else:
            prev_was_number = False
    return sorted(f"{v:g}" if v != int(v) else str(int(v)) for v in vals if v != 1)


def kept_names(text: str) -> list[str]:
    """English names a translation must keep word for word: people and organisations (spaCy PERSON, ORG). Places,
    months and the Moon are translated (Luna, giugno), so they are not required."""
    from wordfreq import zipf_frequency

    doc = _doc_en(normalise(text))
    out: list[str] = []
    for ent in doc.ents:
        if ent.label_ not in ("PERSON", "ORG"):
            continue
        parts = [_name_token(p) for p in ent.text.split()]
        parts = [
            p for p in parts if p and p[:1].isupper() and p not in _COMMON_CAPS_EN
        ]  # not "the" in an ORG
        # a lone capitalised common word opening a sentence is an imperative, not a name ("Cook the outer layer")
        opens = ent.start == 0 or doc[ent.start - 1].text in (".", "!", "?", ":", '"', "'")
        if len(parts) == 1 and opens and zipf_frequency(parts[0].lower(), "en") >= 4.0:
            continue
        out += [p for p in parts if p not in out]
    return out


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
