"""
extractor.py
------------
Turns free-text complaints into a structured list of canonical symptoms.

Three things happen here that a plain keyword search would get wrong:

1. Synonym mapping  - "loose motions" and "watery stools" both become "diarrhea".
2. Negation scoping - "fever but no cough" records fever and explicitly denies cough.
3. Red-flag triage  - phrases suggesting an emergency are surfaced before any
                      diagnosis is attempted.
"""

import json
import os
import re
from difflib import SequenceMatcher
from functools import lru_cache

from nlp.preprocess import preprocess, clean_text, lemmatize, tokenize

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

NEGATION_CUES = {
    "no", "not", "without", "never", "none", "denies", "deny", "negative",
    "cannot", "cant", "dont", "doesnt", "didnt", "havent", "hasnt", "isnt",
    "arent", "wasnt", "free", "absent", "nil",
}

# How many tokens after a negation cue stay inside its scope.
NEGATION_WINDOW = 4


@lru_cache(maxsize=1)
def load_synonyms() -> dict:
    with open(os.path.join(DATA_DIR, "symptom_synonyms.json"), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_red_flags() -> dict:
    with open(os.path.join(DATA_DIR, "red_flags.json"), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _phrase_index():
    """
    Build {normalised phrase -> canonical symptom}, longest phrase first.

    Matching longest-first matters: "high fever" must win over "fever", and
    "loss of smell" must win over the generic "loss".
    """
    index = {}
    for canonical, phrases in load_synonyms().items():
        for phrase in set(phrases + [canonical]):
            index[_normalise(phrase)] = canonical
    return sorted(index.items(), key=lambda kv: -len(kv[0].split()))


def _normalise(text: str) -> str:
    """Lowercase, lemmatize each word, and collapse whitespace."""
    cleaned = clean_text(text)
    return " ".join(lemmatize(tokenize(cleaned)))


def _negated_spans(clause: str) -> list:
    """Return (start, end) token index ranges that fall under a negation cue."""
    words = clause.split()
    spans = []
    for i, w in enumerate(words):
        if w.strip("'") in NEGATION_CUES:
            spans.append((i, min(len(words), i + 1 + NEGATION_WINDOW)))
    return spans


def _in_negated_span(position: int, length: int, spans: list) -> bool:
    return any(start <= position < end or start < position + length <= end
               for start, end in spans)


def _phrase_present(phrase: str, words: list, window: int = 5) -> bool:
    """
    True when every content word of the phrase appears close together.

    Literal substring matching is not good enough for red flags. A patient
    writing "chest pain spreading to my left arm" must still trigger the stored
    phrase "chest pain spreading to arm" — the two extra words in the middle
    cannot be allowed to hide a possible heart attack.
    """
    targets = _content_words(_normalise(phrase))
    if not targets:
        return False

    positions, used = [], set()
    for target in targets:
        hit = next((i for i, w in enumerate(words) if w == target and i not in used), None)
        if hit is None:
            return False
        used.add(hit)
        positions.append(hit)

    return max(positions) - min(positions) <= window + len(targets)


def detect_red_flags(text: str) -> list:
    """Find phrases that mean 'stop and get help now' rather than 'here is a diagnosis'."""
    words = _normalise(text).split()
    found = []
    for flag in load_red_flags()["flags"]:
        for phrase in flag["phrases"]:
            if _phrase_present(phrase, words):
                found.append({
                    "id": flag["id"],
                    "matched": phrase,
                    "message": flag["message"],
                    "support": flag.get("support", False),
                })
                break
    return found


FILLER = {"sensation", "feeling", "problem", "issue", "trouble", "little",
          "bit", "lot", "very", "really", "quite", "some", "my", "the", "a",
          "of", "in", "on", "at", "to", "is", "are", "and", "with", "while",
          "when", "since", "for", "i", "have", "has", "had", "been", "am",
          "was", "get", "getting", "got", "look", "seem", "feel"}


def _content_words(phrase: str) -> list:
    """Words that actually carry meaning in a symptom phrase."""
    return [w for w in phrase.split() if w not in FILLER]


def _windowed_match(phrase_words: list, words: list, consumed: list, window: int = 6):
    """
    Find a phrase whose words all appear close together but not necessarily in
    order or adjacent.

    This is what lets "burning sensation while passing urine" match the stored
    phrase "burning while passing urine", and "urine looks cloudy" match
    "cloudy urine". Requiring at least two content words keeps it from firing
    on single common words.
    """
    if len(phrase_words) < 2:
        return None

    positions = []
    for target in phrase_words:
        hit = next((i for i, w in enumerate(words)
                    if w == target and not consumed[i] and i not in positions), None)
        if hit is None:
            return None
        positions.append(hit)

    start, end = min(positions), max(positions)
    if end - start >= window + len(phrase_words):
        return None
    return start, end + 1


@lru_cache(maxsize=1)
def _single_word_index() -> dict:
    """{one-word phrase -> canonical} for the spelling-tolerant pass."""
    return {phrase: canonical for phrase, canonical in _phrase_index()
            if len(phrase.split()) == 1 and len(phrase) >= 4}


@lru_cache(maxsize=2048)
def _fuzzy_lookup(word: str, cutoff: float = 0.86):
    """
    Map a misspelt word onto a known symptom word, or None.

    The cutoff is deliberately strict. "hedache" should reach "headache", but
    "cold" must never drift to "cough" - in a medical tool a confident wrong
    match is far more harmful than no match at all, so anything borderline is
    left for the user to rephrase.
    """
    vocab = _single_word_index()
    if word in vocab:
        return vocab[word]

    best, best_score = None, 0.0
    for candidate, canonical in vocab.items():
        # Length guard keeps short words from matching each other.
        if abs(len(candidate) - len(word)) > 2:
            continue
        score = SequenceMatcher(None, word, candidate).ratio()
        if score > best_score:
            best, best_score = canonical, score

    return best if best_score >= cutoff else None


def extract_symptoms(text: str) -> dict:
    """
    Extract canonical symptoms from free text.

    Returns the confirmed symptoms, the explicitly denied ones, the red flags,
    and the full preprocessing trace for display.
    """
    trace = preprocess(text)
    index = _phrase_index()

    confirmed, denied = {}, {}

    for clause in trace["clauses"]:
        normalised = _normalise(clause)
        if not normalised:
            continue
        words = normalised.split()
        spans = _negated_spans(normalised)
        consumed = [False] * len(words)

        def record(start, end, canonical):
            for j in range(start, end):
                consumed[j] = True
            bucket = denied if _in_negated_span(start, end - start, spans) else confirmed
            bucket.setdefault(canonical, clause.strip())

        # Pass 1: exact contiguous phrases, longest first.
        for phrase, canonical in index:
            plen = len(phrase.split())
            if plen == 0 or plen > len(words):
                continue
            for i in range(len(words) - plen + 1):
                if any(consumed[i:i + plen]):
                    continue
                if " ".join(words[i:i + plen]) != phrase:
                    continue
                record(i, i + plen, canonical)

        # Pass 2: the same phrases with filler words and word order relaxed.
        for phrase, canonical in index:
            if canonical in confirmed or canonical in denied:
                continue
            content = _content_words(phrase)
            hit = _windowed_match(content, words, consumed)
            if hit:
                record(hit[0], hit[1], canonical)

        # Pass 3: spelling tolerance. Patients type "hedache" and "feever", and
        # a system that silently finds nothing is worse than one that asks.
        for i, word in enumerate(words):
            if consumed[i] or len(word) < 4 or word in FILLER:
                continue
            canonical = _fuzzy_lookup(word)
            if canonical and canonical not in confirmed and canonical not in denied:
                record(i, i + 1, canonical)

    # A symptom stated positively somewhere wins over a denial elsewhere.
    for symptom in list(denied):
        if symptom in confirmed:
            denied.pop(symptom)

    return {
        "symptoms": list(confirmed.keys()),
        "evidence": confirmed,
        "denied": list(denied.keys()),
        "red_flags": detect_red_flags(text),
        "trace": trace,
    }


def all_known_symptoms() -> list:
    """Every canonical symptom the system understands, for the UI suggestion chips."""
    return sorted(load_synonyms().keys())
