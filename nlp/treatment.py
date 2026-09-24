"""
treatment.py
------------
Assembles the care plan for a matched condition: over-the-counter guidance,
what to eat and avoid, precautions, warning signs, and the department to visit.

Everything here is general self-care information, not a prescription.
"""

import json
import os
from functools import lru_cache

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

GENERIC_PLAN = {
    "medications": [
        "Paracetamol may be used for pain or fever if you have no allergy to it",
        "Stay hydrated with water or oral rehydration solution",
        "Do not start antibiotics without a doctor's prescription",
    ],
    "food": {
        "eat": ["Light, freshly cooked home food", "Plenty of fluids", "Seasonal fruits and vegetables"],
        "avoid": ["Outside and reheated food", "Alcohol and smoking", "Heavy fried meals"],
    },
    "precautions": {
        "do": ["Rest adequately", "Monitor your temperature", "Track whether symptoms improve or worsen"],
        "see_doctor_if": ["Symptoms worsen over 48 hours", "Breathing becomes difficult",
                          "You develop chest pain", "Fever persists beyond 3 days"],
    },
}


@lru_cache(maxsize=1)
def _load(filename: str) -> dict:
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def build_plan(disease_key: str, severity_level: str = "Moderate") -> dict:
    """Return the full care plan for a condition, adjusted for severity."""
    medications = _load("medications.json").get(disease_key, GENERIC_PLAN["medications"])
    food = _load("foodplans.json").get(disease_key, GENERIC_PLAN["food"])
    precautions = _load("precautions.json").get(disease_key, GENERIC_PLAN["precautions"])

    urgency, advice = _urgency(disease_key, severity_level)

    return {
        "medications": medications,
        "food_eat": food.get("eat", []),
        "food_avoid": food.get("avoid", []),
        "precautions_do": precautions.get("do", []),
        "see_doctor_if": precautions.get("see_doctor_if", []),
        "urgency": urgency,
        "urgency_advice": advice,
    }


def _urgency(disease_key: str, severity_level: str) -> tuple:
    """Decide how soon the patient should be seen."""
    needs_prompt_care = {
        "pneumonia", "dengue", "typhoid", "malaria", "covid19",
        "peptic_ulcer", "urinary_tract_infection", "asthma",
    }
    needs_testing = {"diabetes", "hypothyroidism", "hypertension", "anemia"}

    if disease_key in needs_prompt_care or severity_level == "Severe":
        return ("See a doctor within 24 hours",
                "This pattern should be examined in person soon. Do not rely on self-care alone.")
    if disease_key in needs_testing:
        return ("Book a consultation and blood tests this week",
                "This condition is confirmed by a laboratory test, not by symptoms alone.")
    if severity_level == "Moderate":
        return ("Self-care now, review in 48 hours",
                "If there is no clear improvement in two days, get examined.")
    return ("Self-care and observation",
            "Most cases settle with rest and fluids. Watch for the warning signs listed below.")


def summarise_text(disease_name: str, confidence: float, department: str) -> str:
    """One-line summary used in history rows and report headers."""
    return f"{disease_name} ({confidence}% confidence) - {department}"
