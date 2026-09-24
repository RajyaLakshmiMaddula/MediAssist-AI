"""
severity.py
-----------
Grades how serious the complaint sounds.

Severity comes from three places and the highest one wins:
  - words the patient used ("unbearable", "slight")
  - how long it has been going on
  - the severity the patient picked on the form
"""

import re

from nlp.preprocess import clean_text

SEVERE_CUES = {
    "unbearable", "excruciating", "severe", "intense", "extreme", "terrible",
    "worst", "agonizing", "agonising", "unable", "cannot", "crippling",
    "debilitating", "非", "horrible", "awful", "very bad", "too much",
    "10/10", "high grade", "constant", "nonstop", "non-stop",
}

MODERATE_CUES = {
    "moderate", "quite", "fairly", "bothering", "disturbing", "troubling",
    "persistent", "recurring", "on and off", "frequent", "often", "bad",
}

MILD_CUES = {
    "mild", "slight", "slightly", "little", "bit", "minor", "occasional",
    "occasionally", "sometimes", "manageable", "low grade", "barely",
}

LEVELS = ["Mild", "Moderate", "Severe"]
_RANK = {name: i for i, name in enumerate(LEVELS)}


def _from_language(text: str) -> tuple:
    """Grade severity from intensifier words. Returns (level, matched cues)."""
    t = clean_text(text)
    matched = {"Severe": [], "Moderate": [], "Mild": []}

    for cue in SEVERE_CUES:
        if cue and cue in t:
            matched["Severe"].append(cue)
    for cue in MODERATE_CUES:
        if cue in t:
            matched["Moderate"].append(cue)
    for cue in MILD_CUES:
        if re.search(rf"\b{re.escape(cue)}\b", t):
            matched["Mild"].append(cue)

    for level in ("Severe", "Moderate", "Mild"):
        if matched[level]:
            return level, matched[level]
    return "Moderate", []


def parse_duration(text: str) -> dict:
    """Pull a duration out of the text: '3 days', 'two weeks', 'since yesterday'."""
    t = clean_text(text)
    words_to_num = {
        "a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "couple": 2, "few": 3, "several": 4,
    }
    unit_days = {"hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}

    match = re.search(
        r"\b(\d+|a|one|two|three|four|five|six|seven|eight|nine|ten|couple|few|several)\s*"
        r"(hour|hr|day|week|month|year)s?\b", t)
    if match:
        raw = match.group(1)
        count = int(raw) if raw.isdigit() else words_to_num.get(raw, 1)
        unit = match.group(2).replace("hr", "hour")
        return {"text": f"{count} {unit}{'s' if count != 1 else ''}",
                "days": count * unit_days[unit]}

    if "yesterday" in t or "last night" in t:
        return {"text": "1 day", "days": 1}
    if "today" in t or "this morning" in t or "few hours" in t:
        return {"text": "Less than a day", "days": 0}
    return {"text": "Not specified", "days": None}


def assess(text: str, reported_level: str = None, reported_duration: str = None) -> dict:
    """
    Combine language cues, duration and the patient's own rating.

    Duration escalates severity because something that has dragged on for
    weeks deserves attention even when it is described calmly.
    """
    language_level, cues = _from_language(text)
    duration = parse_duration(reported_duration or text)

    candidates = [language_level]
    if reported_level in _RANK:
        candidates.append(reported_level)

    # Duration raises concern but never on its own makes something "severe" —
    # two weeks of mild sneezing is persistent, not severe. It escalates at
    # most to Moderate and adds a note instead.
    duration_note = None
    days = duration["days"]
    if days is not None:
        if days >= 14:
            candidates.append("Moderate")
            duration_note = ("These symptoms have lasted two weeks or more. Regardless of "
                             "how mild they feel, that warrants an in-person assessment.")
        elif days >= 5:
            candidates.append("Moderate")
            duration_note = "Symptoms have continued for several days."

    final = max(candidates, key=lambda lvl: _RANK[lvl])

    return {
        "level": final,
        "score": _RANK[final] + 1,
        "language_level": language_level,
        "reported_level": reported_level or "Not specified",
        "cues": cues[:5],
        "duration": duration,
        "duration_note": duration_note,
    }
