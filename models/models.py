"""
models.py
---------
Database schema: one user has many consultations.
"""

import json
from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    consultations = db.relationship(
        "Consultation", backref="patient", lazy=True,
        cascade="all, delete-orphan", order_by="Consultation.created_at.desc()",
    )

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def initials(self) -> str:
        parts = [p for p in self.name.split() if p]
        return "".join(p[0].upper() for p in parts[:2]) or "?"

    def __repr__(self):
        return f"<User {self.email}>"


class Consultation(db.Model):
    __tablename__ = "consultations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    symptoms_text = db.Column(db.Text, nullable=False)
    extracted_symptoms = db.Column(db.Text)     # JSON list
    denied_symptoms = db.Column(db.Text)        # JSON list

    disease = db.Column(db.String(160))
    disease_key = db.Column(db.String(80))
    confidence = db.Column(db.Float)
    certainty = db.Column(db.String(20))
    department = db.Column(db.String(120))

    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    severity = db.Column(db.String(20))
    duration = db.Column(db.String(60))

    medications = db.Column(db.Text)            # JSON list
    food_eat = db.Column(db.Text)               # JSON list
    food_avoid = db.Column(db.Text)             # JSON list
    precautions = db.Column(db.Text)            # JSON list
    warning_signs = db.Column(db.Text)          # JSON list
    differentials = db.Column(db.Text)          # JSON list of {name, confidence}
    urgency = db.Column(db.String(120))

    status = db.Column(db.String(20), default="ok")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # -- JSON helpers ------------------------------------------------------
    @staticmethod
    def _load(value):
        if not value:
            return []
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return []

    @property
    def symptom_list(self):
        return self._load(self.extracted_symptoms)

    @property
    def denied_list(self):
        return self._load(self.denied_symptoms)

    @property
    def medication_list(self):
        return self._load(self.medications)

    @property
    def eat_list(self):
        return self._load(self.food_eat)

    @property
    def avoid_list(self):
        return self._load(self.food_avoid)

    @property
    def precaution_list(self):
        return self._load(self.precautions)

    @property
    def warning_list(self):
        return self._load(self.warning_signs)

    @property
    def differential_list(self):
        return self._load(self.differentials)

    @property
    def reference(self) -> str:
        """Human-friendly consultation reference printed on the report."""
        return f"MA-{self.created_at:%Y%m%d}-{self.id:04d}"

    def __repr__(self):
        return f"<Consultation {self.id} {self.disease}>"
