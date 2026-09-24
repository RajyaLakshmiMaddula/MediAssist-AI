"""
setup_nltk.py
-------------
Downloads the NLTK corpora that the NLP pipeline uses.

Run this once after installing the requirements:

    python setup_nltk.py

The application deliberately does not download anything at import time. A web
app that reaches out to the internet on every boot is slow and fails badly on
restricted networks, so the download is an explicit, one-time step. Until you
run it, MediAssist still works using the built-in fallback tokenizer and
lemmatizer in nlp/preprocess.py - you will simply see a warning in the console.
"""

import sys

# 'punkt_tab' is what NLTK 3.8.2+ looks for; 'punkt' covers older versions.
# averaged_perceptron_tagger_eng is the renamed tagger in recent releases.
RESOURCES = [
    ("punkt", "sentence and word tokenizer"),
    ("punkt_tab", "tokenizer tables (NLTK 3.8.2+)"),
    ("stopwords", "English stopword list"),
    ("wordnet", "lemmatizer dictionary"),
    ("omw-1.4", "WordNet word forms"),
    ("averaged_perceptron_tagger", "part-of-speech tagger"),
    ("averaged_perceptron_tagger_eng", "POS tagger (newer NLTK naming)"),
]


def main() -> int:
    try:
        import nltk
    except ImportError:
        print("nltk is not installed. Run:  pip install -r requirements.txt")
        return 1

    print("Downloading NLTK data for MediAssist AI\n")

    failed = []
    for resource, description in RESOURCES:
        print(f"  {resource:35s} {description} ... ", end="", flush=True)
        try:
            ok = nltk.download(resource, quiet=True)
            print("done" if ok else "skipped")
            if not ok:
                failed.append(resource)
        except Exception as exc:
            print(f"failed ({exc})")
            failed.append(resource)

    print()

    # Some entries are version-specific aliases, so a few "failures" are normal.
    # What matters is whether the pipeline actually reports NLTK as active.
    try:
        from nlp.preprocess import NLTK_AVAILABLE
        if NLTK_AVAILABLE:
            print("NLTK pipeline is active. You are ready to run:  python app.py")
            return 0
    except Exception as exc:
        print(f"Could not verify the pipeline: {exc}")

    print("NLTK data is incomplete, so the app will use its built-in fallback")
    print("pipeline instead. Everything still works - extraction is just less")
    print("linguistically precise.")
    if failed:
        print(f"\nResources that did not download: {', '.join(failed)}")
        print("If you are behind a proxy or firewall, that is the usual cause.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
