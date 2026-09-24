# MediAssist AI

**Intelligent Symptom Diagnosis System** — a full-stack healthcare web application built with Flask, NLTK, HTML, CSS, JavaScript and SQLite.

A patient describes their symptoms in ordinary English. The application extracts the medical symptoms using an NLP pipeline, matches them against a curated knowledge base of 28 conditions, and produces a clinical decision support summary with likely conditions, a confidence score, over-the-counter guidance, a food plan, precautions, a recommended department, and a downloadable PDF report.

> **This is an academic project, not a medical device.** It does not diagnose. It cannot examine a patient, order tests, or account for medical history. Every screen and every generated report carries this disclaimer. If symptoms are severe or worsening, the correct action is to contact a doctor or emergency services.

---

## Table of contents

1. [What it does](#what-it-does)
2. [Requirements](#requirements)
3. [Running it in VS Code](#running-it-in-vs-code)
4. [Command reference](#command-reference)
5. [Project structure](#project-structure)
6. [How the NLP pipeline works](#how-the-nlp-pipeline-works)
7. [The matching algorithm](#the-matching-algorithm)
8. [Routes](#routes)
9. [Database schema](#database-schema)
10. [Editing the knowledge base](#editing-the-knowledge-base)
11. [Troubleshooting](#troubleshooting)

---

## What it does

**Core features**

- Patient registration and login, with passwords stored as salted hashes
- Free-text symptom entry with age, gender, severity and duration
- NLTK pipeline: tokenization, stopword removal, lemmatization, POS tagging, keyword extraction
- Symptom extraction with synonym mapping — "loose motions" and "watery stools" both resolve to *diarrhea*
- Disease matching with a confidence percentage
- Over-the-counter medication guidance, food plan, and precautions per condition
- Recommended hospital department
- Consultation history, saved per patient
- Downloadable PDF consultation report

**Enhancements beyond the original specification**

| Enhancement | Why it was added |
|---|---|
| **Emergency red-flag triage** | Phrases such as crushing chest pain spreading to the arm, or difficulty breathing, halt the pipeline and display an urgent-care banner. Ranking ordinary conditions underneath a possible heart attack would bury the only thing that matters. |
| **Negation scoping** | "Fever but no cough" records fever and explicitly *rules out* cough. A plain keyword search would record both. |
| **Differential diagnosis** | Shows the top candidate plus the runners-up. Real symptom sets rarely point at one condition. |
| **Spelling tolerance** | "hedache" and "feever" still resolve. The similarity cutoff is deliberately strict so that "cold" never drifts to "cough". |
| **Weighted scoring** | Key symptoms count more than incidental ones, and symptoms the patient denied reduce a condition's score. |
| **Age-aware notes** | Different self-care advice for children and for older adults. |
| **NLTK fallback pipeline** | If the NLTK corpora are missing, a built-in pure-Python tokenizer and lemmatizer take over instead of the app crashing. |
| **JSON API** | `/api/analyze` returns the full analysis, so the dashboard can show a live reading before the form is submitted. |

---

## Requirements

- **Python 3.9 or newer** (developed against 3.12)
- **VS Code** with the Microsoft **Python** extension
- No database server needed — SQLite is a single file created automatically

---

## Running it in VS Code

### Step 1 — Open the project

Open VS Code, then **File → Open Folder**, and select the `MediAssist-AI` folder.

Open the built-in terminal with **Ctrl + `** (backtick). On macOS that is **Cmd + `**. Every command below is typed into that terminal.

Confirm you are in the right place — this should list `app.py`:

```bash
# Windows
dir

# macOS / Linux
ls
```

### Step 2 — Create a virtual environment

A virtual environment keeps this project's packages separate from the rest of your system.

```bash
# Windows
python -m venv venv

# macOS / Linux
python3 -m venv venv
```

### Step 3 — Activate it

```bash
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Windows Command Prompt (cmd.exe)
venv\Scripts\activate.bat

# macOS / Linux
source venv/bin/activate
```

Your prompt should now begin with `(venv)`.

> **PowerShell blocks the activate script?** If you see *"running scripts is disabled on this system"*, run this once, then activate again:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

### Step 4 — Select the interpreter in VS Code

Press **Ctrl + Shift + P**, type `Python: Select Interpreter`, and choose the one whose path contains `venv`. It will be labelled *Recommended*.

This is what lets the **Run** button and the debugger use your virtual environment. Without it, VS Code uses the system Python and you will get `ModuleNotFoundError` even though the install succeeded.

### Step 5 — Install the dependencies

```bash
pip install -r requirements.txt
```

### Step 6 — Download the NLTK data

```bash
python setup_nltk.py
```

This fetches the tokenizer, stopword list, WordNet lemmatizer and POS tagger. It needs an internet connection and takes under a minute.

You should see `NLTK pipeline is active.` If it reports that the data is incomplete, the app still runs using its built-in fallback pipeline — extraction is just less linguistically precise.

### Step 7 — Create your environment file

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

The defaults work as-is for local development.

### Step 8 — Run it

Press **F5**, or click **Run → Start Debugging**, and pick **MediAssist AI (Flask)**.

Or from the terminal:

```bash
python app.py
```

You will see:

```
 * Running on http://127.0.0.1:5000
```

**Ctrl + click** that link, or open <http://127.0.0.1:5000> in your browser.

### Step 9 — Use it

1. Click **Create an account** and register
2. On the dashboard, describe symptoms in plain English, for example:
   *"I have had a high fever for three days with severe headache, pain behind my eyes and joint pain. There is also a rash on my arms."*
3. Submit to see the analysis
4. Open **History** to revisit a consultation or download its PDF

To stop the server, press **Ctrl + C** in the terminal.

---

## Command reference

The full sequence, for when you already know the steps.

**Windows (PowerShell)**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python setup_nltk.py
copy .env.example .env
python app.py
```

**macOS / Linux**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python setup_nltk.py
cp .env.example .env
python app.py
```

**Returning to the project later** — only the activate step and the run step are needed:

```bash
.\venv\Scripts\Activate.ps1     # Windows
source venv/bin/activate        # macOS / Linux
python app.py
```

**Other useful commands**

```bash
deactivate                      # leave the virtual environment
pip list                        # show installed packages
python -c "from nlp.engine import diagnose; print(diagnose('fever and headache')['primary']['name'])"
```

**Starting the database over.** Delete `database.db` and restart the app; it is recreated empty on the next boot. This erases all accounts and consultations.

---

## Project structure

```
MediAssist-AI/
│
├── app.py                  Flask application, routes, session handling
├── config.py               Configuration read from environment variables
├── setup_nltk.py           One-time NLTK corpora download
├── requirements.txt        Python dependencies
├── .env.example            Template for your local .env
├── database.db             SQLite database (created on first run)
│
├── models/
│   └── models.py           User and Consultation tables
│
├── nlp/                    The NLP engine
│   ├── engine.py           Runs the whole pipeline in one call
│   ├── preprocess.py       Tokenize, stopwords, lemmatize, POS tag
│   ├── extractor.py        Symptom extraction, synonyms, negation, red flags
│   ├── matcher.py          Weighted disease matching and confidence
│   ├── severity.py         Mild / moderate / severe, and duration parsing
│   └── treatment.py        Assembles medication, diet and precautions
│
├── data/                   The knowledge base — plain JSON, safe to edit
│   ├── diseases.json           28 conditions and their weighted symptoms
│   ├── symptom_synonyms.json   114 symptoms and their everyday phrasings
│   ├── medications.json        OTC guidance per condition
│   ├── foodplans.json          Foods to include and avoid
│   ├── precautions.json        Precautions and warning signs
│   └── red_flags.json          Emergency phrases that halt the pipeline
│
├── templates/              Jinja2 pages
├── static/
│   ├── css/style.css       Design system and all styling
│   └── js/main.js          Live analysis, symptom chips, form behaviour
│
├── utils/
│   ├── forms.py            Flask-WTF forms and validation
│   └── report.py           ReportLab PDF generation
│
├── reports/                Generated PDFs
└── .vscode/                Debug and editor configuration
```

---

## How the NLP pipeline works

```
raw text
   │
   ├─ 1. Clean          strip punctuation and noise, normalise case
   ├─ 2. Clause split   "fever but no cough" → ["fever", "no cough"]
   ├─ 3. Tokenize       NLTK word_tokenize, or the fallback tokenizer
   ├─ 4. Stopwords      remove filler, but keep clinical words like "no",
   │                    "severe" and "sudden" that change meaning
   ├─ 5. Lemmatize      "coughing" → "cough",  "aches" → "ache"
   ├─ 6. POS tag        tag words for keyword extraction
   ├─ 7. Extract        match phrases against the synonym index,
   │                    longest phrase first, then relaxed word order,
   │                    then spelling-tolerant matching
   ├─ 8. Negation       anything inside a negation window is recorded
   │                    as denied rather than confirmed
   └─ 9. Red flags      emergency phrases stop everything here
        │
        ▼
   canonical symptoms → matcher → severity → treatment plan
```

**Worked example.** *"Continuous sneezing and runny nose every morning with itchy watery eyes, but no fever at all."*

- Confirmed: `sneezing`, `runny nose`, `itchy eyes`
- Denied: `fever`
- Result: Allergic Rhinitis at 70%, ahead of Common Cold at 49% — precisely *because* fever was ruled out

---

## The matching algorithm

The documented baseline is recall:

```
Recall = (matched symptoms / total symptoms of the disease) × 100
```

The implementation reports that figure as `baseline_score`, then refines it, because recall alone misranks conditions in three ways.

**1. Precision matters too.** A patient reporting ten symptoms of which two match a three-symptom disease scores 67% on recall alone, which overstates the case. Precision — how much of what the patient said the condition actually explains — is combined with recall.

**2. Not all symptoms are equal.** Each symptom carries a weight in `diseases.json`. *Pain behind the eyes* is far more indicative of dengue than *fatigue*, which accompanies almost everything.

**3. Denials are evidence.** A symptom the patient explicitly ruled out counts against any condition that requires it.

Duration also adjusts the score — a fever lasting two weeks fits typhoid better than influenza.

Each result reports its `certainty` as **strong**, **moderate**, **weak** or **inconclusive**. When the top two candidates are close, the interface says so rather than presenting a single answer with false confidence.

---

## Routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Landing page |
| GET, POST | `/register` | Create an account |
| GET, POST | `/login` | Sign in |
| GET | `/logout` | Sign out |
| GET | `/dashboard` | Symptom entry form |
| POST | `/diagnose` | Run the analysis and save it |
| POST | `/api/analyze` | JSON analysis, used for the live reading |
| GET | `/api/symptoms` | Every symptom the system understands |
| GET | `/history` | Past consultations, paginated |
| GET | `/history/<id>` | One saved consultation |
| POST | `/history/<id>/delete` | Delete a consultation |
| GET | `/report/<id>` | Download the PDF report |
| GET | `/conditions` | Browse the knowledge base by department |

Every route that touches patient data requires login and verifies that the record belongs to the signed-in user, so one patient cannot read another's consultations by changing the ID in the URL.

---

## Database schema

**users**

| Column | Type | Notes |
|---|---|---|
| id | Integer | Primary key |
| name | String(120) | |
| email | String(160) | Unique, indexed |
| password_hash | String(255) | Salted hash, never the password itself |
| age | Integer | Optional |
| gender | String(20) | Optional |
| created_at | DateTime | |

**consultations**

| Column | Type | Notes |
|---|---|---|
| id | Integer | Primary key |
| user_id | Integer | Foreign key to `users.id` |
| symptoms_text | Text | What the patient typed |
| extracted_symptoms | Text | JSON list |
| denied_symptoms | Text | JSON list |
| disease / disease_key | String | The top match |
| confidence | Float | Percentage |
| certainty | String(20) | strong / moderate / weak / inconclusive |
| department | String(120) | |
| age / gender / severity / duration | | Captured at consultation time |
| medications, food_eat, food_avoid, precautions, warning_signs | Text | JSON lists |
| differentials | Text | JSON list of the runners-up |
| urgency | String(120) | Suggested next step |
| status | String(20) | ok / emergency / no_symptoms / no_match |
| created_at | DateTime | Indexed |

The treatment plan is stored *with* each consultation rather than looked up later, so an old report still shows the advice that was actually given even if the knowledge base is edited afterwards.

---

## Editing the knowledge base

Everything clinical lives in `data/` as plain JSON. No Python changes are needed.

**Adding a condition** — add an entry to `diseases.json`:

```json
"gastritis": {
  "name": "Gastritis",
  "description": "Inflammation of the stomach lining.",
  "department": "Gastroenterology",
  "typical_duration": "3 to 7 days",
  "self_limiting": true,
  "symptoms": {
    "burning stomach pain": 2.0,
    "nausea": 1.2,
    "bloating": 1.1,
    "loss of appetite": 0.7
  }
}
```

The number after each symptom is its diagnostic weight, roughly **0.4 to 2.0**. A weight near 2.0 marks a symptom that strongly points at this condition and little else; a weight below 0.8 marks a common symptom that accompanies many illnesses. Compare *pain behind eyes* at 2.0 for dengue with *fatigue* at 0.5 — both appear, but only one is informative.

Then add a matching key to `medications.json`, `foodplans.json` and `precautions.json`. Every symptom you list must already exist in `symptom_synonyms.json`, otherwise it can never be matched.

**Teaching a new phrasing** — add it to the list for that symptom in `symptom_synonyms.json`:

```json
"diarrhea": ["diarrhea", "loose motions", "watery stools", "loose stools"]
```

This is the highest-value file to extend. Most missed symptoms are a phrasing the system has not been taught yet.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'flask'`**
The virtual environment is not active, or VS Code is using the wrong interpreter. Check for `(venv)` in your prompt, then redo **Step 4** above.

**PowerShell: "running scripts is disabled on this system"**
Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, then activate again.

**Console warns "NLTK unavailable — using built-in fallback"**
The corpora did not download. Run `python setup_nltk.py`. The app works either way; this only affects linguistic precision.

**`Address already in use` / port 5000 is busy**
Another program holds the port — on macOS it is often AirPlay Receiver. Change the last line of `app.py` to `port=5001`, or stop the other program.

**The page looks unstyled**
A stale cached stylesheet. Hard-refresh with **Ctrl + F5**, or **Cmd + Shift + R** on macOS.

**"No symptoms recognised"**
The phrasing is not in the vocabulary yet. Describe symptoms plainly — *"burning while passing urine"* rather than *"waterworks trouble"* — or add the phrasing to `symptom_synonyms.json`.

**Everything is broken and I want a clean start**
Delete the `venv` folder and `database.db`, then repeat the setup from Step 2.

---

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, vanilla JavaScript |
| Backend | Python, Flask |
| NLP | NLTK, with a pure-Python fallback |
| Database | SQLite via SQLAlchemy |
| Authentication | Flask-Login, Werkzeug password hashing |
| Forms and CSRF | Flask-WTF, WTForms |
| PDF reports | ReportLab |

---

## A note on safety

Symptom checkers carry a real risk: a confident wrong answer can send someone home when they should be in a hospital. The design choices that follow from that are deliberate and worth defending in a viva.

- Emergency phrases **stop** the pipeline instead of being ranked as one option among several
- Results are labelled by certainty, and a close call is stated as a close call
- Medication guidance is over-the-counter only, never a prescription or a dose schedule
- Every condition carries its own *see a doctor if* warning signs, shown on screen and printed in the report
- The fuzzy-matching cutoff is strict, because no match is safer than a wrong match
- Age notes flag that children and older adults need different thresholds
- The disclaimer appears on every screen and in every PDF

---

*Built as a full-stack academic major project demonstrating Flask, NLP and database integration.*
