# `ClinicaNLP` — Intelligent Clinical Dialogue & Health Records Analyzer

**ClinicaNLP** is a Natural Language Processing (NLP) platform engineered for healthcare and medical dialogue intelligence. It automatically converts unorganized doctor-patient consultation transcripts and clinical notes into standardized **SOAP medical documentation**, extracts **clinical entities (NER)**, translates complex medical jargon into **plain patient language**, computes **patient distress & tone scores**, and alerts clinicians to **critical emergency red flags**.

![ClinicaNLP Banner](public/logo.svg)

---

## Key Features

### 1. Automated Clinical SOAP Note Generation
- **Standardized Medical Documentation**: Automatically extracts and synthesizes unstructured conversation into gold standard medical format:
  - **S (Subjective)**: Patient symptoms, pain descriptions, onset, duration, and personal/family medical history.
  - **O (Objective)**: Vitals (BP, heart rate, respiratory rate, SpO2), physical exam observations (heart sounds, pulmonary crackles, edema), and laboratory/imaging results.
  - **A (Assessment)**: Primary diagnoses, clinical staging, and differentials (e.g. Stage 2 Essential Hypertension, Angina Pectoris).
  - **P (Plan)**: Prescribed medications, dosages, administration routes, lab orders, dietary precautions, and follow-up timeline.
- **One-Click EHR Copy**: Instantly copy the formatted SOAP note directly to clipboard for Electronic Health Record entry.

### 2. Medical Named Entity Recognition (NER)
- **Clinical Ontology Tagging**: Extracts and color-codes entities across 5 distinct clinical categories:
  - **Symptoms & Physical Complaints** (e.g., exertional dyspnea, retrosternal tightness, palpitations, polydipsia, neuropathy)
  - **Diagnoses & Conditions** (e.g., Essential Hypertension, Type 2 Diabetes, Angina, COPD, Myocardial Infarction)
  - **Medications & Dosages** (e.g., Lisinopril 20mg, Metformin 500mg bid, Sublingual Nitroglycerin 0.4mg PRN)
  - **Anatomical Body Systems** (Cardiovascular, Respiratory, Endocrine, Neurological, Musculoskeletal)
  - **Diagnostic Tests & Labs** (12-Lead ECG, Exercise Stress Echocardiogram, HbA1c, Fasting Blood Glucose, Chest CT)

### 3. Medical Jargon Simplification & Patient Glossary
- **Patient-Accessible Translation**: Matches clinical terms against an ontology dictionary to give simple, plain-language patient explanations:
  - *Dyspnea* → **Shortness of breath**
  - *Retrosternal* → **Behind the breastbone / center of chest**
  - *Myocardial Infarction* → **Heart attack**
  - *Sublingual* → **Dissolved under the tongue for rapid absorption**
  - *Polydipsia* → **Excessive, unquenchable thirst**
  - *PRN* → **As needed (take only when acute symptoms occur)**

### 4. Patient Distress, Anxiety & Bedside Tone Scoring
- **Clinical Sentiment Polarity**: Evaluates patient dialogue turns for anxiety triggers, fear of myocardial infarction, and distress level.
- **Clinician Empathy Index**: Measures physician reassurance phrases and bedside communication quality.

### 5. Emergency Red Flags & Critical Safety Alerts
- Scans transcripts for emergency clinical patterns (e.g., chest pain radiating to left arm/jaw requiring Nitroglycerin and 911 activation, or severe hypoglycemia warnings).

### 6. Interactive Viva Demonstration Cases
- One-click case study buttons pre-loaded for instant viva demo:
  - 🫀 **Cardiology**: Exertional Angina & Stage 2 Hypertension
  - 🩸 **Endocrinology**: Type 2 Diabetes Mellitus & Peripheral Neuropathy
  - 📋 **Inpatient Discharge Note**: Community-Acquired Pneumonia & COPD Exacerbation

### 7. Audio Narration & Multi-Format Export
- **Web Speech TTS**: Listen to patient instructions or consultation summaries with native browser speech synthesis.
- **Export Options**: Download reports as Markdown (`.md`) or JSON (`.json`).

---

## NLP Architecture & Core Concepts (Viva Cheat Sheet)

| Concept | Implementation in ClinicaNLP |
|---|---|
| **Sentence & Word Tokenization** | Splits raw doctor-patient speech into sentences and individual tokens via NLTK `sent_tokenize` and `word_tokenize`. |
| **Stopword Removal** | Filters out uninformative English grammatical stopwords (`the`, `is`, `at`, `on`). |
| **Lemmatization & POS Tagging** | Normalizes inflected word variants to base roots via WordNet Lemmatizer (`lemmatize`). |
| **Medical Named Entity Recognition (NER)** | Pattern-based and ontology matching across clinical symptoms, diagnoses, drugs, and body systems. |
| **Extractive Summarization** | Frequency-weighted sentence scoring selecting the most salient factual sentences without rewording. |
| **Clinical Sentiment Analysis** | Lexicon-weighted VADER sentiment determining patient distress vs physician reassurance. |
| **Health Literacy Readability** | Flesch-Kincaid Grade Level and Reading Ease formulas measuring communication complexity. |

---

## How to Run Locally

### 1. One-Click Launch (Recommended)
Double-click `run_all.bat` or run in PowerShell:
```powershell
.\run_all.ps1
```

This starts:
- **FastAPI NLP Backend**: `http://127.0.0.1:8000` (API Docs: `http://127.0.0.1:8000/docs`)
- **React Frontend**: `http://localhost:3000`

### 2. Running Automated Tests
Execute the backend test suite:
```bash
.\.venv\Scripts\pytest backend/test_server.py
```
All 12 clinical and NLP integration tests will execute against the FastAPI server.

---

## License
MIT License • Natural Language Processing Mini-Project (50 Marks)