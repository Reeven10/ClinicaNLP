"""
Automated Pytest Suite for ClinicaNLP Backend
Tests all clinical and multimodal NLP endpoints:
- Health & Service Information
- Medical Named Entity Recognition (NER)
- Clinical SOAP Note Generation
- Medical Jargon Simplification & Explanations
- Patient Distress & Clinician Empathy Scoring
- Clinical Red Flags & Emergency Alert Detection
- Medication Schedule & Orders Extraction
- Pre-loaded Clinical Samples Retrieval
- Extractive Summarization & Readability Metrics
- WordNet Similar Words & Smart Quiz Generator
"""

import pytest
from fastapi.testclient import TestClient
from backend.server import app

client = TestClient(app)

CLINICAL_SAMPLE = (
    "Doctor: Good morning, Mr. Bennett. How have you been feeling? "
    "Patient: Good morning, Dr. Vance. Honestly, I have been quite worried. "
    "Whenever I walk up the stairs, I feel this sudden tightness and dull pressure across my chest. "
    "And I get very short of breath, gasping for air. "
    "Doctor: That shortness of breath—or exertional dyspnea—is very important. "
    "Does it radiate to your jaw or down your left arm? "
    "Patient: Yes, it radiated slightly into my left shoulder. My father had a heart attack at age 58, which causes me panic. "
    "Doctor: The nurse recorded your blood pressure at 148/92 mmHg, indicating stage 2 hypertension. "
    "Lungs are clear with no pulmonary rales. "
    "I am prescribing Lisinopril 20 milligrams once daily and sublingual Nitroglycerin 0.4 milligrams PRN. "
    "If chest pain does not resolve within five minutes, you must call 911 immediately. "
    "We will perform an ECG today and schedule an exercise stress echocardiogram next Thursday."
)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "ClinicaNLP" in data["service"]


def test_clinical_consultation_analysis():
    response = client.post("/api/clinical/consultation-analysis", json={"document": {"text": CLINICAL_SAMPLE}})
    assert response.status_code == 200
    data = response.json()
    
    assert "entities" in data
    assert "soap_note" in data
    assert "jargon_simplification" in data
    assert "distress_and_sentiment" in data
    assert "red_flags" in data
    assert "medication_schedule" in data
    assert "readability" in data
    assert "summary" in data

    # Verify Medical NER
    entities = data["entities"]
    symptoms = [s["name"].lower() for s in entities["symptoms"]]
    assert any("dyspnea" in s or "shortness of breath" in s or "chest" in s for s in symptoms)
    
    # Verify SOAP note
    soap = data["soap_note"]
    assert len(soap["subjective"]) > 0
    assert len(soap["objective"]) > 0
    assert len(soap["assessment"]) > 0
    assert len(soap["plan"]) > 0

    # Verify Jargon Simplification
    jargon = data["jargon_simplification"]
    assert jargon["total_jargon_found"] > 0
    terms = [j["term"].lower() for j in jargon["jargon_list"]]
    assert any("dyspnea" in t or "hypertension" in t or "sublingual" in t for t in terms)

    # Verify Red Flags
    red_flags = data["red_flags"]
    assert red_flags["total_critical_flags"] > 0


def test_clinical_soap_note_endpoint():
    res = client.post("/api/clinical/soap-note", json={"document": {"text": CLINICAL_SAMPLE}})
    assert res.status_code == 200
    data = res.json()
    assert "subjective" in data
    assert "objective" in data
    assert "assessment" in data
    assert "plan" in data


def test_clinical_ner_endpoint():
    res = client.post("/api/clinical/ner", json={"document": {"text": CLINICAL_SAMPLE}})
    assert res.status_code == 200
    data = res.json()
    assert "symptoms" in data
    assert "conditions" in data
    assert "medications" in data
    assert "body_systems" in data
    assert "diagnostic_tests" in data


def test_clinical_jargon_endpoint():
    res = client.post("/api/clinical/jargon-simplify", json={"document": {"text": CLINICAL_SAMPLE}})
    assert res.status_code == 200
    data = res.json()
    assert "jargon_list" in data
    assert data["total_jargon_found"] > 0


def test_clinical_red_flags_endpoint():
    res = client.post("/api/clinical/red-flags", json={"document": {"text": CLINICAL_SAMPLE}})
    assert res.status_code == 200
    data = res.json()
    assert "red_flags" in data
    assert data["total_critical_flags"] >= 1


def test_clinical_samples_endpoint():
    res = client.get("/api/clinical/samples")
    assert res.status_code == 200
    data = res.json()
    assert "cardiology" in data
    assert len(data["cardiology"]) > 100


def test_extractive_summary():
    res = client.post("/api/ytb-summary-01", json={"text": CLINICAL_SAMPLE, "word_count": 150})
    assert res.status_code == 200
    assert "summary" in res.json()
    assert len(res.json()["summary"]) > 0


def test_similar_words():
    res = client.post("/api/ytb-similarwords-01", json={"words": ["hypertension", "patient"]})
    assert res.status_code == 200
    data = res.json()
    assert "hypertension" in data
    assert "synms" in data["hypertension"]


def test_readability():
    res = client.post("/api/nlp/readability", json={"document": {"text": CLINICAL_SAMPLE}})
    assert res.status_code == 200
    data = res.json()
    assert "score" in data
    assert "grade" in data
    assert "stats" in data
    assert data["stats"]["words"] > 0


def test_action_items():
    res = client.post("/api/nlp/action-items", json={"document": {"text": CLINICAL_SAMPLE}})
    assert res.status_code == 200
    data = res.json()
    assert "action_items" in data
    assert len(data["action_items"]) >= 1


def test_flashcards():
    res = client.post("/api/nlp/flashcards", json={"document": {"text": CLINICAL_SAMPLE}})
    assert res.status_code == 200
    cards = res.json().get("flashcards", [])
    assert len(cards) > 0
    assert "term" in cards[0]
    assert "definition" in cards[0]
