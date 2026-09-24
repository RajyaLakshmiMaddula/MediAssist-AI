"""
preprocess.py
-------------
Text preprocessing for the MediAssist NLP pipeline.

Pipeline: cleaning -> tokenization -> lowercasing -> stopword removal
          -> lemmatization -> POS tagging -> keyword extraction

NLTK is the primary engine. Because NLTK corpora are downloaded at runtime and
that download often fails on restricted networks, every NLTK call here is
wrapped so the module degrades to a pure-Python implementation instead of
crashing the application.
"""

import re
import logging

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# NLTK setup
# --------------------------------------------------------------------------
NLTK_AVAILABLE = False
_lemmatizer = None
_stopwords = set()

try:
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords as nltk_stopwords
    from nltk.stem import WordNetLemmatizer

    # Touch each resource once. If any is missing we fall back wholesale
    # rather than half-working.
    word_tokenize("test sentence")
    _stopwords = set(nltk_stopwords.words("english"))
    _lemmatizer = WordNetLemmatizer()
    _lemmatizer.lemmatize("running", pos="v")
    nltk.pos_tag(["test"])

    NLTK_AVAILABLE = True
    log.info("NLTK corpora loaded successfully.")
except Exception as exc:  # pragma: no cover - environment dependent
    log.warning("NLTK unavailable (%s). Using built-in fallback pipeline.", exc)


# --------------------------------------------------------------------------
# Fallback resources
# --------------------------------------------------------------------------
FALLBACK_STOPWORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "you", "your", "he", "him",
    "his", "she", "her", "it", "its", "they", "them", "their", "what", "which",
    "who", "this", "that", "these", "those", "am", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "having", "do", "does", "did",
    "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as",
    "until", "while", "of", "at", "by", "for", "with", "about", "into",
    "through", "during", "before", "after", "to", "from", "up", "down", "in",
    "out", "on", "off", "then", "once", "here", "there", "when", "where",
    "all", "any", "both", "each", "few", "more", "most", "some", "such",
    "only", "own", "same", "so", "than", "too", "very", "s", "t", "can",
    "will", "just", "should", "now", "also", "get", "got", "getting", "feel",
    "feeling", "felt", "having", "since", "days", "day", "week", "weeks",
    "today", "yesterday", "morning", "evening", "night", "please", "doctor",
    "sir", "madam", "hello", "hi",
}

# Words that must never be removed even though they look like stopwords,
# because they carry clinical meaning.
CLINICAL_KEEP = {
    "no", "not", "without", "never", "cannot", "can't", "don't", "doesn't",
    "severe", "mild", "high", "low", "chronic", "acute", "sudden", "sharp",
    "dull", "burning", "left", "right", "both", "very",
}

_IRREGULAR_LEMMAS = {
    "aching": "ache", "aches": "ache", "ached": "ache",
    "paining": "pain", "pains": "pain", "pained": "pain",
    "coughing": "cough", "coughs": "cough", "coughed": "cough",
    "sneezing": "sneeze", "sneezes": "sneeze", "sneezed": "sneeze",
    "vomiting": "vomit", "vomits": "vomit", "vomited": "vomit",
    "swelling": "swell", "swollen": "swell",
    "bleeding": "bleed", "bled": "bleed",
    "burning": "burn", "burnt": "burn", "burned": "burn",
    "breathing": "breathe", "breathes": "breathe",
    "feeling": "feel", "feels": "feel", "felt": "feel",
    "running": "run", "runs": "run", "ran": "run",
    "losing": "lose", "lost": "lose", "loses": "lose",
    "itching": "itch", "itches": "itch", "itchy": "itch",
    "shivering": "shiver", "shivers": "shiver",
    "sweating": "sweat", "sweats": "sweat",
    "worrying": "worry", "worries": "worry", "worried": "worry",
    "tired": "tire", "tiredness": "tire",
    "dizziness": "dizzy", "weakness": "weak", "stiffness": "stiff",
    "numbness": "numb", "tightness": "tight", "heaviness": "heavy",
    "soreness": "sore", "redness": "red", "sickness": "sick",
    "sadness": "sad", "puffiness": "puffy", "blurriness": "blurry",
    "sleeping": "sleep", "sleeps": "sleep", "slept": "sleep",
    "eating": "eat", "ate": "eat", "eats": "eat",
    "urinating": "urinate", "urination": "urinate",
    "heartbeat": "heartbeat",
}


def _simple_lemma(word: str) -> str:
    """Rule-based lemmatizer used when WordNet is not available."""
    if word in _IRREGULAR_LEMMAS:
        return _IRREGULAR_LEMMAS[word]
    if len(word) <= 3:
        return word
    for suffix, replacement in (
        ("ies", "y"), ("sses", "ss"), ("ches", "ch"), ("shes", "sh"),
        ("xes", "x"), ("ing", ""), ("ed", ""), ("s", ""),
    ):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            stem = word[: len(word) - len(suffix)] + replacement
            # restore doubled consonants: "stopping" -> "stopp" -> "stop"
            if len(stem) > 3 and stem[-1] == stem[-2] and stem[-1] not in "sl":
                stem = stem[:-1]
            return stem
    return word


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def clean_text(text: str) -> str:
    """Normalise raw user input: lowercase, strip punctuation noise, collapse space."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s',.\-]", " ", text)
    text = text.replace("’", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> list:
    """Split text into word tokens."""
    if NLTK_AVAILABLE:
        try:
            return [t for t in word_tokenize(text) if re.search(r"[a-z0-9]", t)]
        except Exception:
            pass
    return re.findall(r"[a-z0-9']+", text)


def remove_stopwords(tokens: list) -> list:
    """Drop common English words while protecting clinically meaningful ones."""
    stops = (_stopwords if NLTK_AVAILABLE and _stopwords else FALLBACK_STOPWORDS) - CLINICAL_KEEP
    return [t for t in tokens if t not in stops and len(t) > 1]


def lemmatize(tokens: list) -> list:
    """Reduce tokens to dictionary form."""
    if NLTK_AVAILABLE and _lemmatizer is not None:
        out = []
        for t in tokens:
            try:
                lemma = _lemmatizer.lemmatize(t, pos="v")
                lemma = _lemmatizer.lemmatize(lemma, pos="n")
                out.append(lemma)
            except Exception:
                out.append(_simple_lemma(t))
        return out
    return [_simple_lemma(t) for t in tokens]


def pos_tag(tokens: list) -> list:
    """Return (token, tag) pairs. Falls back to a coarse heuristic tagger."""
    if NLTK_AVAILABLE:
        try:
            return nltk.pos_tag(tokens)
        except Exception:
            pass
    tagged = []
    for t in tokens:
        if t.endswith("ing"):
            tagged.append((t, "VBG"))
        elif t.endswith("ly"):
            tagged.append((t, "RB"))
        elif t.endswith(("ous", "ful", "ive", "able", "y")):
            tagged.append((t, "JJ"))
        else:
            tagged.append((t, "NN"))
    return tagged


def extract_keywords(tagged: list) -> list:
    """Keep nouns, adjectives and verbs — the parts of speech that carry symptoms."""
    keep_prefixes = ("NN", "JJ", "VB", "RB")
    return [tok for tok, tag in tagged if tag.startswith(keep_prefixes)]


def split_clauses(text: str) -> list:
    """
    Break input into clauses so negation stays scoped to its own phrase.

    "I have fever but no cough" -> ["i have fever", "no cough"]

    "while" is deliberately not a delimiter. It sits inside ordinary symptom
    phrases - "burning while passing urine" - so splitting there would tear the
    phrase in half and lose the symptom entirely.
    """
    parts = re.split(r"[.,;]|\b(?:but|however|although|though|and also)\b", text)
    return [p.strip() for p in parts if p and p.strip()]


def preprocess(text: str) -> dict:
    """
    Run the full pipeline and return every intermediate stage.

    The stages are returned (not just the final list) so the UI can show the
    user exactly what the NLP engine did with their words.
    """
    cleaned = clean_text(text)
    tokens = tokenize(cleaned)
    no_stops = remove_stopwords(tokens)
    lemmas = lemmatize(no_stops)
    tagged = pos_tag(lemmas)
    keywords = extract_keywords(tagged)

    return {
        "original": text,
        "cleaned": cleaned,
        "tokens": tokens,
        "without_stopwords": no_stops,
        "lemmas": lemmas,
        "pos_tags": tagged,
        "keywords": keywords,
        "clauses": split_clauses(cleaned),
        "engine": "NLTK" if NLTK_AVAILABLE else "Built-in fallback",
    }
