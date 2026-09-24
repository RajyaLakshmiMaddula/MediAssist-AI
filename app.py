"""
app.py
------
MediAssist AI — Flask application entry point.

Run locally:
    python app.py
"""

import json
import logging
import os
from datetime import datetime

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_file, url_for)
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from flask_wtf.csrf import CSRFProtect

from config import config_map
from models.models import Consultation, User, db
from nlp.engine import diagnose
from nlp.extractor import all_known_symptoms
from nlp.matcher import load_diseases
from nlp.preprocess import NLTK_AVAILABLE
from utils.forms import LoginForm, RegisterForm, SymptomForm
from utils.report import build_report

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s %(message)s")
log = logging.getLogger("mediassist")

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Sign in to continue."
login_manager.login_message_category = "info"

csrf = CSRFProtect()


def create_app(config_name: str = None) -> Flask:
    app = Flask(__name__)
    config_name = config_name or os.getenv("FLASK_CONFIG", "default")
    app.config.from_object(config_map[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    os.makedirs(app.config["REPORTS_DIR"], exist_ok=True)

    register_routes(app)

    with app.app_context():
        db.create_all()
        log.info("Database ready at %s", app.config["SQLALCHEMY_DATABASE_URI"])
        log.info("NLP engine: %s", "NLTK" if NLTK_AVAILABLE else "built-in fallback")

    return app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def register_routes(app: Flask):

    @app.context_processor
    def inject_globals():
        return {
            "app_name": app.config["APP_NAME"],
            "tagline": app.config["APP_TAGLINE"],
            "current_year": datetime.utcnow().year,
            "nltk_active": NLTK_AVAILABLE,
        }

    # -- Public ------------------------------------------------------------
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("index.html",
                               disease_count=len(load_diseases()),
                               symptom_count=len(all_known_symptoms()))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        form = RegisterForm()
        if form.validate_on_submit():
            email = form.email.data.strip().lower()
            if User.query.filter_by(email=email).first():
                flash("That email is already registered. Sign in instead.", "error")
                return render_template("register.html", form=form)

            user = User(
                name=form.name.data.strip(),
                email=email,
                age=form.age.data,
                gender=form.gender.data or None,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()

            login_user(user)
            flash(f"Welcome, {user.name.split()[0]}. Your account is ready.", "success")
            return redirect(url_for("dashboard"))

        return render_template("register.html", form=form)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data.strip().lower()).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember.data)
                nxt = request.args.get("next")
                if nxt and nxt.startswith("/"):
                    return redirect(nxt)
                return redirect(url_for("dashboard"))
            flash("Email or password is incorrect.", "error")

        return render_template("login.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You are signed out.", "info")
        return redirect(url_for("index"))

    # -- Dashboard ---------------------------------------------------------
    @app.route("/dashboard")
    @login_required
    def dashboard():
        form = SymptomForm(age=current_user.age, gender=current_user.gender or "")
        recent = (Consultation.query
                  .filter_by(user_id=current_user.id)
                  .order_by(Consultation.created_at.desc())
                  .limit(3).all())
        return render_template("dashboard.html", form=form, recent=recent,
                               examples=EXAMPLE_COMPLAINTS)

    @app.route("/diagnose", methods=["POST"])
    @login_required
    def run_diagnosis():
        form = SymptomForm()
        if not form.validate_on_submit():
            for field, errors in form.errors.items():
                for err in errors:
                    flash(err, "error")
            return redirect(url_for("dashboard"))

        result = diagnose(
            text=form.symptoms.data.strip(),
            age=form.age.data or current_user.age,
            gender=form.gender.data or current_user.gender,
            reported_severity=form.severity.data,
            reported_duration=form.duration.data,
        )

        consultation = _persist(result, form)
        return render_template("diagnosis.html", result=result,
                               consultation=consultation)

    # -- API (used by the dashboard for live analysis) ---------------------
    @app.route("/api/analyze", methods=["POST"])
    @login_required
    def api_analyze():
        payload = request.get_json(silent=True) or {}
        text = (payload.get("symptoms") or "").strip()
        if len(text) < 8:
            return jsonify({"status": "too_short",
                            "message": "Describe your symptoms in a little more detail."}), 400

        result = diagnose(
            text=text,
            age=payload.get("age") or current_user.age,
            gender=payload.get("gender") or current_user.gender,
            reported_severity=payload.get("severity"),
            reported_duration=payload.get("duration"),
        )

        return jsonify({
            "status": result["status"],
            "symptoms": result["symptoms"],
            "denied": result["denied"],
            "severity": result["severity"]["level"],
            "duration": result["severity"]["duration"]["text"],
            "red_flags": result["red_flags"],
            "certainty": result["certainty"],
            "engine": result["nlp_trace"]["engine"],
            "candidates": [
                {"name": c["name"], "confidence": c["confidence"],
                 "department": c["department"], "matched": c["matched"]}
                for c in result["candidates"]
            ],
        })

    @app.route("/api/symptoms")
    @login_required
    def api_symptoms():
        return jsonify({"symptoms": all_known_symptoms()})

    # -- History -----------------------------------------------------------
    @app.route("/history")
    @login_required
    def history():
        page = request.args.get("page", 1, type=int)
        pagination = (Consultation.query
                      .filter_by(user_id=current_user.id)
                      .order_by(Consultation.created_at.desc())
                      .paginate(page=page, per_page=10, error_out=False))
        return render_template("history.html", pagination=pagination,
                               consultations=pagination.items)

    @app.route("/history/<int:consultation_id>")
    @login_required
    def consultation_detail(consultation_id):
        consultation = _owned_consultation(consultation_id)
        return render_template("consultation.html", consultation=consultation)

    @app.route("/history/<int:consultation_id>/delete", methods=["POST"])
    @login_required
    def delete_consultation(consultation_id):
        consultation = _owned_consultation(consultation_id)
        db.session.delete(consultation)
        db.session.commit()
        flash("Consultation deleted.", "info")
        return redirect(url_for("history"))

    @app.route("/report/<int:consultation_id>")
    @login_required
    def download_report(consultation_id):
        consultation = _owned_consultation(consultation_id)
        buffer = build_report(consultation, current_user)
        return send_file(
            buffer, mimetype="application/pdf", as_attachment=True,
            download_name=f"MediAssist_{consultation.reference}.pdf",
        )

    # -- Reference ---------------------------------------------------------
    @app.route("/conditions")
    @login_required
    def conditions():
        diseases = load_diseases()
        grouped = {}
        for key, disease in diseases.items():
            grouped.setdefault(disease["department"], []).append({
                "key": key, **disease,
                "symptom_names": sorted(disease["symptoms"].keys()),
            })
        for items in grouped.values():
            items.sort(key=lambda d: d["name"])
        return render_template("conditions.html",
                               grouped=dict(sorted(grouped.items())),
                               total=len(diseases))

    # -- Error handlers ----------------------------------------------------
    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", code=404,
                               title="Page not found",
                               message="That page does not exist. "
                                       "Check the link or go back to your dashboard."), 404

    @app.errorhandler(500)
    def server_error(_):
        db.session.rollback()
        return render_template("error.html", code=500,
                               title="Something broke on our side",
                               message="The request could not be completed. "
                                       "Try again in a moment."), 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
EXAMPLE_COMPLAINTS = [
    "I have had a high fever for three days with severe headache, pain behind my eyes and joint pain. There is also a rash on my arms.",
    "Continuous sneezing and runny nose every morning with itchy watery eyes, but no fever at all.",
    "Burning sensation while passing urine since yesterday, going to the toilet very often and the urine looks cloudy.",
    "Dry cough for two weeks with breathlessness when I climb stairs, and I have lost my sense of smell.",
    "Severe throbbing headache on one side, light hurts my eyes and I feel like vomiting.",
]


def _persist(result: dict, form) -> Consultation:
    """Save a diagnosis result as a consultation record."""
    primary = result.get("primary") or {}
    plan = result.get("plan") or {}

    consultation = Consultation(
        user_id=current_user.id,
        symptoms_text=result["input"],
        extracted_symptoms=json.dumps(result["symptoms"]),
        denied_symptoms=json.dumps(result["denied"]),
        disease=primary.get("name"),
        disease_key=primary.get("key"),
        confidence=primary.get("confidence"),
        certainty=result.get("certainty"),
        department=primary.get("department"),
        age=form.age.data or current_user.age,
        gender=form.gender.data or current_user.gender,
        severity=result["severity"]["level"],
        duration=result["severity"]["duration"]["text"],
        medications=json.dumps(plan.get("medications", [])),
        food_eat=json.dumps(plan.get("food_eat", [])),
        food_avoid=json.dumps(plan.get("food_avoid", [])),
        precautions=json.dumps(plan.get("precautions_do", [])),
        warning_signs=json.dumps(plan.get("see_doctor_if", [])),
        differentials=json.dumps([
            {"name": c["name"], "confidence": c["confidence"],
             "department": c["department"]}
            for c in result.get("candidates", [])
        ]),
        urgency=plan.get("urgency"),
        status=result["status"],
    )
    db.session.add(consultation)
    db.session.commit()
    return consultation


def _owned_consultation(consultation_id: int) -> Consultation:
    """Fetch a consultation, refusing access to other patients' records."""
    consultation = db.session.get(Consultation, consultation_id)
    if consultation is None or consultation.user_id != current_user.id:
        abort(404)
    return consultation


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
