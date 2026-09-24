"""
engine.py
---------
Runs the whole pipeline in one call so the Flask layer stays thin.

    text in  ->  preprocess  ->  extract  ->  severity  ->  match  ->  treat
             ->  structured result out
"""

from nlp import extractor, matcher, severity, treatment


def diagnose(text: str, age=None, gender=None, reported_severity=None,
             reported_duration=None) -> dict:
    """Analyse a symptom description and return a complete consultation result."""
    extraction = extractor.extract_symptoms(text)
    grading = severity.assess(text, reported_severity, reported_duration)

    result = {
        "input": text,
        "age": age,
        "gender": gender,
        "symptoms": extraction["symptoms"],
        "evidence": extraction["evidence"],
        "denied": extraction["denied"],
        "red_flags": extraction["red_flags"],
        "severity": grading,
        "nlp_trace": extraction["trace"],
        "candidates": [],
        "primary": None,
        "plan": None,
        "certainty": "inconclusive",
        "status": "ok",
    }

    # An emergency phrase stops the pipeline. Ranking conditions underneath a
    # possible stroke would bury the only thing that matters.
    if extraction["red_flags"]:
        result["status"] = "emergency"
        return result

    if not extraction["symptoms"]:
        result["status"] = "no_symptoms"
        return result

    candidates = matcher.match(
        extraction["symptoms"],
        denied=extraction["denied"],
        duration_days=grading["duration"]["days"],
    )
    result["candidates"] = candidates
    result["certainty"] = matcher.certainty_label(candidates)

    if not candidates:
        result["status"] = "no_match"
        return result

    primary = candidates[0]
    result["primary"] = primary
    result["plan"] = treatment.build_plan(primary["key"], grading["level"])

    # Age-specific notes. These change what counts as safe self-care.
    notes = []
    try:
        age_val = int(age) if age is not None else None
    except (TypeError, ValueError):
        age_val = None

    if age_val is not None:
        if age_val < 12:
            notes.append("Children need weight-based dosing. Never give aspirin to a child.")
        elif age_val >= 60:
            notes.append("Older adults can deteriorate quickly with mild-looking symptoms. "
                         "Lower your threshold for seeing a doctor.")
    result["age_notes"] = notes

    return result
