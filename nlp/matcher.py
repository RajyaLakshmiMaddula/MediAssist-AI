"""
matcher.py
----------
Scores every disease in the knowledge base against the extracted symptoms.

The documented baseline formula is plain recall:

    similarity = matched symptoms / total disease symptoms x 100

That formula has two well-known weaknesses. A disease described by only two
symptoms scores 100% off a single common complaint, and a patient who reports
eight symptoms gets the same score as one who reports two. This engine keeps
the baseline (it is reported alongside the result for transparency) and adds:

  * Symptom weighting  - "pain behind the eyes" is far more telling than "fever",
                         so each symptom carries a discriminative weight.
  * Precision term     - how much of what the patient said the disease explains.
  * Partial credit     - "high fever" partly satisfies "fever".
  * Denial penalty     - explicitly ruled-out symptoms push a disease down.
  * Duration fit       - a 3-week cough fits bronchitis better than a cold.
"""

import json
import os
from functools import lru_cache

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Scoring weights
W_RECALL = 0.60          # how much of the disease picture is present
W_PRECISION = 0.40       # how much of the complaint the disease explains
PARTIAL_CREDIT = 0.60    # credit when a related-but-not-exact symptom matches
DENIAL_PENALTY = 0.18    # per strongly denied symptom
MIN_CONFIDENCE = 12      # below this a match is not worth reporting


@lru_cache(maxsize=1)
def load_diseases() -> dict:
    with open(os.path.join(DATA_DIR, "diseases.json"), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _family_map() -> dict:
    """
    Map each symptom to its related variants.

    Derived automatically: "high fever", "mild fever" and "prolonged fever" all
    share the head word "fever", so they are treated as a family and can give
    each other partial credit.
    """
    all_symptoms = set()
    for disease in load_diseases().values():
        all_symptoms.update(disease["symptoms"].keys())

    families = {}
    for a in all_symptoms:
        related = set()
        a_words = set(a.split())
        for b in all_symptoms:
            if a == b:
                continue
            b_words = set(b.split())
            if a_words < b_words or b_words < a_words:
                related.add(b)
        families[a] = related
    return families


def _duration_fit(disease_key: str, days) -> float:
    """Small bonus or penalty based on how long symptoms have lasted."""
    if days is None:
        return 0.0
    short_lived = {"common_cold", "food_poisoning", "gastroenteritis", "influenza"}
    long_running = {"bronchitis", "typhoid", "arthritis", "hypothyroidism",
                    "diabetes", "hypertension", "anemia", "asthma", "gerd",
                    "peptic_ulcer", "anxiety"}
    if days >= 14:
        if disease_key in short_lived:
            return -0.10
        if disease_key in long_running:
            return 0.08
    if days <= 2 and disease_key in long_running:
        return -0.05
    return 0.0


def score_disease(disease_key: str, disease: dict, user_symptoms: list,
                  denied: list, duration_days=None) -> dict:
    """Score one disease. Returns the breakdown, not just a number."""
    profile = disease["symptoms"]
    families = _family_map()
    user_set = set(user_symptoms)

    matched_exact, matched_partial = [], []
    matched_weight = 0.0
    explained_user = set()
    spent = set()  # a reported symptom can only pay for one disease symptom

    # Exact matches first so they always win over partial credit.
    for symptom, weight in profile.items():
        if symptom in user_set:
            matched_exact.append(symptom)
            matched_weight += weight
            explained_user.add(symptom)
            spent.add(symptom)

    # Then partial credit from related variants, heaviest symptom first.
    for symptom, weight in sorted(profile.items(), key=lambda kv: -kv[1]):
        if symptom in matched_exact:
            continue
        relatives = (families.get(symptom, set()) & user_set) - spent
        if relatives:
            relative = sorted(relatives)[0]
            matched_partial.append((symptom, relative))
            matched_weight += weight * PARTIAL_CREDIT
            explained_user.add(relative)
            spent.add(relative)

    total_weight = sum(profile.values())
    recall = matched_weight / total_weight if total_weight else 0.0
    precision = len(explained_user) / len(user_set) if user_set else 0.0

    raw = (W_RECALL * recall) + (W_PRECISION * precision)

    # Penalise symptoms the patient explicitly ruled out, scaled by how
    # important that symptom is to this disease.
    penalty = 0.0
    conflicting = []
    for symptom in denied:
        if symptom in profile:
            conflicting.append(symptom)
            penalty += DENIAL_PENALTY * (profile[symptom] / 2.0)

    raw = raw - penalty + _duration_fit(disease_key, duration_days)
    confidence = max(0.0, min(raw, 1.0)) * 100

    baseline = (len(matched_exact) + len(matched_partial)) / len(profile) * 100

    return {
        "key": disease_key,
        "name": disease["name"],
        "description": disease["description"],
        "department": disease["department"],
        "typical_duration": disease["typical_duration"],
        "self_limiting": disease.get("self_limiting", False),
        "confidence": round(confidence, 1),
        "baseline_score": round(baseline, 1),
        "recall": round(recall * 100, 1),
        "precision": round(precision * 100, 1),
        "matched": matched_exact,
        "partial": [f"{rel} (related to {sym})" for sym, rel in matched_partial],
        "missing": [s for s in profile if s not in matched_exact
                    and s not in [m[0] for m in matched_partial]],
        "conflicting": conflicting,
        "total_symptoms": len(profile),
    }


def match(user_symptoms: list, denied: list = None, duration_days=None, top_n: int = 4) -> list:
    """Rank all diseases and return the strongest candidates."""
    denied = denied or []
    if not user_symptoms:
        return []

    results = [
        score_disease(key, disease, user_symptoms, denied, duration_days)
        for key, disease in load_diseases().items()
    ]
    results = [r for r in results if r["confidence"] >= MIN_CONFIDENCE and r["matched"]]
    results.sort(key=lambda r: (-r["confidence"], -len(r["matched"])))
    return results[:top_n]


def certainty_label(results: list) -> str:
    """
    Describe how trustworthy the ranking is.

    Two candidates a couple of points apart is not a diagnosis, and the
    interface should say so rather than presenting a false winner.
    """
    if not results:
        return "inconclusive"
    top = results[0]["confidence"]
    gap = top - results[1]["confidence"] if len(results) > 1 else top

    if top < 30:
        return "inconclusive"
    if top >= 60 and gap >= 15:
        return "strong"
    if top >= 40:
        return "moderate"
    return "weak"
